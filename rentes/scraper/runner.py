"""ScrapeOrchestrator — run scrapers, valideer, sla op in Supabase."""

from __future__ import annotations

import asyncio
import logging
import os
from collections import defaultdict
from datetime import date, datetime, timezone

import httpx

from rentes.scraper.models import ScrapedRate, ScrapeResult, ValidationReport
from rentes.scraper.registry import register_all, registry
from rentes.scraper.validator import cross_validate, trend_check, _rate_key

logger = logging.getLogger("nat-api.scraper.runner")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")


def _supabase_headers() -> dict[str, str]:
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


class ScrapeOrchestrator:
    """Hoofdorkestratie: run scrapers → valideer → sla op."""

    def __init__(self, dry_run: bool = False, single_source: str | None = None):
        self.dry_run = dry_run
        self.single_source = single_source

    async def run(self) -> dict:
        """Voer een volledige scrape-run uit.

        Returns dict met samenvatting voor de API-response.
        """
        register_all()

        # 1. Bepaal welke scrapers we runnen
        if self.single_source:
            scraper = registry.get(self.single_source)
            if not scraper:
                return {"error": f"Onbekende bron: {self.single_source}"}
            scrapers = [scraper]
        else:
            scrapers = registry.all()

        if not scrapers:
            return {"error": "Geen scrapers geregistreerd"}

        # 2. Run alle scrapers (parallel als meerdere)
        logger.info("[runner] Start scrape-run: %s (dry_run=%s)",
                     [s.name for s in scrapers], self.dry_run)

        results: list[ScrapeResult] = await asyncio.gather(
            *[s.scrape() for s in scrapers],
            return_exceptions=True,
        )

        # Verwerk exceptions
        processed_results: list[ScrapeResult] = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error("[runner] Scraper %s crashed: %s", scrapers[i].name, r)
                processed_results.append(ScrapeResult(
                    bron=scrapers[i].name, success=False,
                    errors=[str(r)],
                ))
            else:
                processed_results.append(r)

        # 3. Verzamel alle geldige rates
        all_rates: list[ScrapedRate] = []
        for r in processed_results:
            if r.success:
                all_rates.extend(r.rates)

        if not all_rates:
            return self._build_summary(processed_results, ValidationReport(), stored=0)

        # 4. Cross-validatie (als meerdere bronnen)
        validation = cross_validate(processed_results)

        # 5. Haal vorige rentes op voor trendcheck
        previous = await self._load_previous_rates()
        changes, trend_quarantined = trend_check(all_rates, previous)
        validation.changes = changes
        validation.quarantined.extend(trend_quarantined)

        # 6. Bepaal welke rates we opslaan
        quarantined_keys = {
            tuple(q["key"]) for q in validation.quarantined
        }

        # Dedupliceer: neem per key de rate van de meest betrouwbare bron (laagste priority)
        best_rates: dict[tuple, ScrapedRate] = {}
        for r in processed_results:
            if not r.success:
                continue
            scraper = registry.get(r.bron)
            priority = scraper.priority if scraper else 99
            for rate in r.rates:
                key = _rate_key(rate)
                if key in quarantined_keys:
                    continue
                if key not in best_rates:
                    best_rates[key] = rate

        # 7. Opslaan
        stored = 0
        if not self.dry_run and best_rates:
            stored = await self._store_rates(list(best_rates.values()))
            validation.stored = stored

        # 8. Log run
        await self._log_run(processed_results, validation)

        return self._build_summary(processed_results, validation, stored)

    async def _load_previous_rates(self) -> dict[tuple, float]:
        """Laad meest recente rentes uit Supabase voor trendcheck."""
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            return {}

        try:
            url = f"{SUPABASE_URL}/rest/v1/hypotheekrentes"
            params = {
                "select": "geldverstrekker,productlijn,aflosvorm,rentevaste_periode,ltv_staffel,peildatum",
                "order": "peildatum.desc",
                "bron": "eq.scraper",
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers=_supabase_headers(), params=params)
                resp.raise_for_status()

            rows = resp.json()

            # Per (gv, product, aflosvorm, rvp) → ltv_staffel → per ltv_cat de rente
            result: dict[tuple, float] = {}
            seen: set[tuple[str, str, str, int]] = set()

            for row in rows:
                base_key = (row["geldverstrekker"], row["productlijn"],
                            row["aflosvorm"], row["rentevaste_periode"])
                if base_key in seen:
                    continue  # al de meest recente gezien
                seen.add(base_key)

                staffel = row.get("ltv_staffel") or {}
                for ltv_cat, rente in staffel.items():
                    if rente is not None:
                        key = (*base_key, ltv_cat)
                        result[key] = float(rente)

            return result
        except Exception as e:
            logger.warning("[runner] Kan vorige rentes niet laden: %s", e)
            return {}

    async def _store_rates(self, rates: list[ScrapedRate]) -> int:
        """Sla rentes op in Supabase via upsert.

        We groeperen per (geldverstrekker, productlijn, aflosvorm, rvp)
        en bouwen per groep één ltv_staffel dict.
        """
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            logger.warning("[runner] Geen Supabase config — kan niet opslaan")
            return 0

        # Groepeer per basis-key
        grouped: dict[tuple, dict[str, float]] = defaultdict(dict)
        for rate in rates:
            base_key = (rate.geldverstrekker, rate.productlijn,
                        rate.aflosvorm, rate.rentevaste_periode)
            grouped[base_key][rate.ltv_categorie] = rate.rente

        peildatum = date.today().isoformat()
        rows = []
        for (gv, prod, aflos, rvp), staffel in grouped.items():
            rows.append({
                "geldverstrekker": gv,
                "productlijn": prod,
                "aflosvorm": aflos,
                "rentevaste_periode": rvp,
                "ltv_staffel": staffel,
                "peildatum": peildatum,
                "bron": "scraper",
            })

        # Check welke renten handmatig zijn ingevuld (niet overschrijven)
        manual_keys = await self._get_manual_keys()
        filtered_rows = []
        skipped = 0
        for row in rows:
            key = (row["geldverstrekker"], row["productlijn"],
                   row["aflosvorm"], row["rentevaste_periode"])
            if key in manual_keys:
                skipped += 1
                continue
            filtered_rows.append(row)

        if skipped:
            logger.info("[runner] %d tarieven overgeslagen (handmatige override)", skipped)

        if not filtered_rows:
            return 0

        # Batch upsert (Supabase PostgREST)
        url = f"{SUPABASE_URL}/rest/v1/hypotheekrentes"
        headers = _supabase_headers()
        headers["Prefer"] = "resolution=merge-duplicates,return=minimal"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=headers, json=filtered_rows)
                resp.raise_for_status()

            logger.info("[runner] %d tarieven opgeslagen in Supabase", len(filtered_rows))
            return len(filtered_rows)
        except Exception as e:
            logger.error("[runner] Fout bij opslaan: %s", e)
            return 0

    async def _get_manual_keys(self) -> set[tuple]:
        """Haal keys op van handmatig ingevoerde tarieven (niet overschrijven)."""
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            return set()

        try:
            url = f"{SUPABASE_URL}/rest/v1/hypotheekrentes"
            params = {
                "select": "geldverstrekker,productlijn,aflosvorm,rentevaste_periode",
                "bron": "eq.handmatig",
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=_supabase_headers(), params=params)
                resp.raise_for_status()

            return {
                (r["geldverstrekker"], r["productlijn"], r["aflosvorm"], r["rentevaste_periode"])
                for r in resp.json()
            }
        except Exception as e:
            logger.warning("[runner] Kan handmatige keys niet laden: %s", e)
            return set()

    async def _log_run(self, results: list[ScrapeResult], validation: ValidationReport):
        """Log de scrape-run naar Supabase scraper_logs tabel."""
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            return

        for r in results:
            row = {
                "bron": r.bron,
                "success": r.success,
                "rates_scraped": len(r.rates),
                "rates_stored": validation.stored,
                "warnings": len(validation.warnings),
                "errors": len(r.errors),
                "error_messages": r.errors[:10],
                "duration_seconds": round(r.duration_seconds, 2),
                "pages_fetched": r.pages_fetched,
                "changes_detected": len(validation.changes),
                "quarantined": len(validation.quarantined),
            }

            try:
                url = f"{SUPABASE_URL}/rest/v1/scraper_logs"
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, headers=_supabase_headers(), json=row)
                    resp.raise_for_status()
            except Exception as e:
                logger.warning("[runner] Kan scraper_log niet opslaan: %s", e)

    def _build_summary(
        self,
        results: list[ScrapeResult],
        validation: ValidationReport,
        stored: int,
    ) -> dict:
        """Bouw een samenvatting voor de API-response."""
        return {
            "status": "ok" if all(r.success for r in results) else "partial",
            "dry_run": self.dry_run,
            "bronnen": [
                {
                    "naam": r.bron,
                    "success": r.success,
                    "rates_scraped": len(r.rates),
                    "pages_fetched": r.pages_fetched,
                    "duration_seconds": round(r.duration_seconds, 1),
                    "errors": r.errors[:5],
                }
                for r in results
            ],
            "totaal_rates": validation.total_rates,
            "opgeslagen": stored,
            "wijzigingen": len(validation.changes),
            "wijzigingen_details": [
                {
                    "bank": c.geldverstrekker,
                    "product": c.productlijn,
                    "periode": c.rentevaste_periode,
                    "ltv": c.ltv_categorie,
                    "oud": c.oude_rente,
                    "nieuw": c.nieuwe_rente,
                    "verschil": c.verschil,
                }
                for c in validation.changes[:50]
            ],
            "waarschuwingen": len(validation.warnings),
            "quarantaine": len(validation.quarantined),
            "quarantaine_details": validation.quarantined[:20],
        }
