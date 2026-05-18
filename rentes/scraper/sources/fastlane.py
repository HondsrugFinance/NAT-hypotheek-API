"""Fastlane / Nationale Hypotheekbond — Hypotheekrentes scraper.

Dit is de PRIMAIRE bron. Fastlane biedt:
- 96 producten van 52+ geldverstrekkers
- 13 LTV-staffels per product (50%-110% in stappen van 5%)
- NHG-tarieven (apart op te vragen)
- 4 aflosvormen: Annuitair (58), Lineair (55), Aflossingsvrij (52), Spaar (61)
- Alle rentevaste periodes (variabel + 1-30 jaar)
- 11 energielabels (A++++ t/m G)
- Overbruggingsrentes (vast + variabel) per geldverstrekker

API endpoints:
  GET /v1/filter/ltv/{aflosvorm}/{periode_mnd}/{label}/2/{nhg}/1/ja
       -> Alle 13 LTV-staffels in 1 call (snelste)

  GET /v1/filter/rvp/{periodes_csv}/{ltv}/{aflosvorm}/{label}/2/{nhg}/1/ja
       -> Alle periodes in 1 call voor 1 specifieke LTV

  GET /v1/filter/bridging-loan
       -> Overbruggingsrentes voor alle producten

Authenticatie:
  authorization: {token}  (statische token uit Hondsrug Finance account)
  x-user-hash:  {hash}    (gebruiker-identificatie)
  origin: https://fastlane.fdta.nl

Strategie:
  Voor elke (aflosvorm × periode × energielabel × nhg) doen we 1 LTV-call
  die alle 13 staffels voor alle 96 producten in 1 response geeft.

Volume:
  4 aflosvormen × 12 periodes × 3 labels × 2 nhg = 288 calls voor de
  meest gangbare combinaties. Met 0.3s rate limit = ~90 seconden.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
import urllib.parse
from dataclasses import dataclass

import httpx

from rentes.scraper.base import BaseScraper
from rentes.scraper.models import ScrapedRate, ScrapeResult

logger = logging.getLogger("nat-api.scraper.fastlane")


# --- API configuratie ---

API_BASE = "https://fds2.fdta.nl"

# Aflosvormen (Fastlane product-type IDs)
AFLOSVORMEN = {
    "annuitair":     58,
    "lineair":       55,
    "aflossingsvrij": 52,
    "spaar":         61,
}

# Rentevaste periodes in MAANDEN (Fastlane gebruikt maanden, niet jaren)
# 1 = variabel (1 maand), de rest is jaren * 12
# Default: 7 meest-gebruikte periodes. Volledige lijst via PERIODES_MAANDEN_FULL.
PERIODES_MAANDEN = [
    1,    # variabel
    12,   # 1 jaar
    60,   # 5 jaar
    120,  # 10 jaar
    180,  # 15 jaar
    240,  # 20 jaar
    360,  # 30 jaar
]

PERIODES_MAANDEN_FULL = [
    1, 12, 24, 36, 60, 72, 84, 120, 144, 180, 204, 240, 300, 360,
]

def periode_maanden_naar_jaren(maanden: int) -> int:
    """Converteer maanden naar rentevaste periode in jaren (0 = variabel)."""
    if maanden == 1:
        return 0  # variabel
    return maanden // 12

# Energielabels die we standaard scrapen (alleen C voor basis-rente).
# Energielabel-kortingen worden apart afgeleid (via A vs G vergelijk).
ENERGIELABELS = ["C"]
ENERGIELABELS_VOOR_KORTING_DERIVATION = ["A", "G"]

# LTV-staffel mapping: index in riskCategories array → onze database LTV-categorie
# riskCategories order: 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110
LTV_INDEX_TO_CATEGORIE = {
    0: "50",
    1: "55",
    2: "60",
    3: "65",
    4: "70",
    5: "75",
    6: "80",
    7: "85",
    8: "90",
    9: "95",
    10: "100",
    11: "105",
    12: "106plus",  # 110% mapt naar onze ">106%" categorie
}


class FastlaneScraper(BaseScraper):
    """Primaire bron: Fastlane / Nationale Hypotheekbond API."""

    name = "fastlane"
    priority = 1  # HOOGSTE prioriteit — meest betrouwbare bron
    request_delay = 0.3  # Fastlane staat snelle calls toe
    max_retries = 3
    timeout = 20.0

    def __init__(self,
                 auth_token: str | None = None,
                 user_hash: str | None = None,
                 aflosvormen: list[str] | None = None,
                 energielabels: list[str] | None = None,
                 with_nhg: bool = True):
        super().__init__()
        # Credentials worden lazy geladen in scrape() via get_credentials()
        # om credentials uit Supabase boven env vars te prefereren.
        self.auth_token = auth_token
        self.user_hash = user_hash
        self.aflosvormen = aflosvormen or list(AFLOSVORMEN.keys())
        self.energielabels = energielabels or ENERGIELABELS
        self.with_nhg = with_nhg
        self._token_refreshed_this_run = False

    async def _ensure_credentials(self) -> bool:
        """Laad credentials uit Supabase store (fallback: env vars).
        Returns True als credentials beschikbaar zijn."""
        if self.auth_token and self.user_hash:
            return True
        from rentes.scraper.credentials_store import get_credentials
        token, uhash = await get_credentials("fastlane")
        if token and uhash:
            self.auth_token = token
            self.user_hash = uhash
            return True
        logger.warning(
            "[fastlane] Geen credentials gevonden (Supabase + env vars beide leeg)"
        )
        return False

    async def _refresh_credentials(self) -> bool:
        """Trigger Playwright login om nieuwe credentials te krijgen.
        Returns True als refresh succesvol. Mag maar 1x per scrape-run."""
        if self._token_refreshed_this_run:
            logger.warning("[fastlane] Token al gerefresht deze run — geef op")
            return False
        self._token_refreshed_this_run = True

        from rentes.scraper.fastlane_auth import refresh_and_store_fastlane_credentials
        from rentes.scraper.credentials_store import mark_403

        await mark_403("fastlane")
        logger.warning("[fastlane] 403 ontvangen — start token-refresh via Playwright")

        new_token, new_hash = await refresh_and_store_fastlane_credentials()
        if new_token and new_hash:
            self.auth_token = new_token
            self.user_hash = new_hash
            logger.info("[fastlane] Token-refresh geslaagd, hervat scrape")
            return True
        logger.error("[fastlane] Token-refresh mislukt")
        return False

    def _headers(self) -> dict[str, str]:
        return {
            "authorization": self.auth_token,
            "x-user-hash": self.user_hash,
            "origin": "https://fastlane.fdta.nl",
            "referer": "https://fastlane.fdta.nl/",
            "user-agent": self._user_agent,
            "accept": "*/*",
            "accept-language": "nl-NL,nl;q=0.9,en;q=0.8",
        }

    def _build_ltv_url(self, aflosvorm_id: int, periode_mnd: int,
                       energielabel: str, nhg: bool) -> str:
        """Bouw URL voor het LTV-endpoint (geeft alle 13 staffels in 1 call)."""
        nhg_val = "ja" if nhg else "nee"
        el = urllib.parse.quote(energielabel)
        return f"{API_BASE}/v1/filter/ltv/{aflosvorm_id}/{periode_mnd}/{el}/2/{nhg_val}/1/ja"

    def _build_bridging_url(self) -> str:
        return f"{API_BASE}/v1/filter/bridging-loan"

    async def _preflight_check(self) -> bool:
        """Test of credentials werken door 1 simpele call te doen.
        Bij 403 → automatisch refresh via Playwright.
        Returns True als credentials werken na (eventuele) refresh."""
        url = self._build_ltv_url(AFLOSVORMEN["annuitair"], 120, "C", False)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=self._headers())
            if resp.status_code == 200:
                return True
            if resp.status_code == 403:
                logger.warning("[fastlane] Preflight: 403 — token expired, refresh")
                if await self._refresh_credentials():
                    # Retry met nieuwe credentials
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.get(url, headers=self._headers())
                    return resp.status_code == 200
                return False
            logger.warning("[fastlane] Preflight onverwacht status %d", resp.status_code)
            return False
        except Exception as e:
            logger.error("[fastlane] Preflight mislukt: %s", e)
            return False

    async def scrape(self) -> ScrapeResult:
        """Scrape alle combinaties: aflosvorm × periode × energielabel × nhg."""
        start = time.time()
        all_rates: list[ScrapedRate] = []
        errors: list[str] = []
        pages_fetched = 0

        # 1. Laad credentials (Supabase → env vars fallback)
        if not await self._ensure_credentials():
            return ScrapeResult(
                bron=self.name, success=False,
                errors=["Geen credentials beschikbaar (Supabase + env vars beide leeg)"],
            )

        # 2. Pre-flight check: bij 403 → auto-refresh
        if not await self._preflight_check():
            return ScrapeResult(
                bron=self.name, success=False,
                errors=["Pre-flight check mislukt — credentials werken niet en refresh is gefaald"],
            )

        nhg_options = [True, False] if self.with_nhg else [False]
        total_calls = (
            len(self.aflosvormen) * len(PERIODES_MAANDEN)
            * len(self.energielabels) * len(nhg_options) + 1
        )
        logger.info("[fastlane] Start scrape: %d calls (%d aflosvormen × %d periodes × %d labels × %d nhg)",
                     total_calls, len(self.aflosvormen), len(PERIODES_MAANDEN),
                     len(self.energielabels), len(nhg_options))

        async with httpx.AsyncClient(timeout=self.timeout, headers=self._headers()) as client:
            # 1. Hoofd-scraping: alle rente-combinaties
            for aflosvorm_naam in self.aflosvormen:
                aflosvorm_id = AFLOSVORMEN[aflosvorm_naam]

                for periode_mnd in PERIODES_MAANDEN:
                    rvp_jaren = periode_maanden_naar_jaren(periode_mnd)

                    for energielabel in self.energielabels:
                        for nhg in nhg_options:
                            url = self._build_ltv_url(
                                aflosvorm_id, periode_mnd, energielabel, nhg
                            )
                            try:
                                resp = await self._fetch_fastlane(client, url)
                                pages_fetched += 1

                                rates = self._parse_ltv_response(
                                    resp.json(),
                                    aflosvorm=aflosvorm_naam,
                                    rentevaste_periode=rvp_jaren,
                                    energielabel=energielabel,
                                    nhg=nhg,
                                )
                                all_rates.extend(rates)

                                # Log iedere 10 calls voortgang
                                if pages_fetched % 10 == 0:
                                    elapsed = time.time() - start
                                    logger.info("[fastlane] Voortgang: %d/%d (%.0f%%) — %d rates — %.1fs",
                                                 pages_fetched, total_calls,
                                                 100 * pages_fetched / total_calls,
                                                 len(all_rates), elapsed)
                            except Exception as e:
                                msg = f"Fout bij {url}: {e}"
                                logger.error("[fastlane] %s", msg)
                                errors.append(msg)

                            await self._rate_limit()

            # 2. Overbruggingsrentes (1 call, alle producten)
            try:
                resp = await self._fetch_fastlane(client, self._build_bridging_url())
                pages_fetched += 1
                bridging_rates = self._parse_bridging_response(resp.json())
                all_rates.extend(bridging_rates)
            except Exception as e:
                msg = f"Fout bij overbrugging: {e}"
                logger.error("[fastlane] %s", msg)
                errors.append(msg)

        duration = time.time() - start
        logger.info(
            "[fastlane] Klaar: %d rentes van %d calls in %.1fs (%d fouten)",
            len(all_rates), pages_fetched, duration, len(errors),
        )

        return ScrapeResult(
            bron=self.name,
            success=len(all_rates) > 0,
            rates=all_rates,
            errors=errors,
            duration_seconds=duration,
            pages_fetched=pages_fetched,
        )

    async def _fetch_fastlane(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        """Wrapper rond _fetch met Fastlane-specifieke headers."""
        return await self._fetch(client, url, headers=self._headers())

    def _parse_ltv_response(
        self,
        data: dict,
        aflosvorm: str,
        rentevaste_periode: int,
        energielabel: str,
        nhg: bool,
    ) -> list[ScrapedRate]:
        """Parse een /v1/filter/ltv/... response.

        Response structuur:
          {
            "riskCategories": [{"label": "50%"}, {"label": "55%"}, ...],
            "labels": [
              {
                "finDataCode": "...",
                "name": "ING Hypotheek",
                "interests": [
                  {"percentage": "4.13", "onlyForExistingCustomers": false},
                  {"percentage": "4.13", ...},
                  ...
                ]
              }
            ]
          }
        """
        rates: list[ScrapedRate] = []
        risk_categories = data.get("riskCategories", [])
        labels = data.get("labels", [])

        for product in labels:
            raw_name = product.get("name", "").strip()
            if not raw_name:
                continue

            # Probeer naam te splitsen in geldverstrekker + productlijn
            canonical_gv, canonical_product = self._split_fastlane_label(raw_name)
            if not canonical_gv:
                continue  # onbekende geldverstrekker — overslaan

            interests = product.get("interests", [])
            for idx, interest in enumerate(interests):
                # Skip lege rates
                percentage_str = interest.get("percentage", "")
                if not percentage_str or percentage_str.strip() == "":
                    continue

                # Skip "only for existing customers" tarieven (verwarrend in scraper)
                if interest.get("onlyForExistingCustomers"):
                    continue

                try:
                    rente = float(percentage_str)
                except (ValueError, TypeError):
                    continue

                # Map index naar LTV-categorie
                if nhg:
                    # Bij NHG=ja krijgen we 13x dezelfde NHG-rente.
                    # We slaan alleen de eerste op als "NHG".
                    if idx > 0:
                        continue
                    ltv_categorie = "NHG"
                else:
                    ltv_categorie = LTV_INDEX_TO_CATEGORIE.get(idx)
                    if ltv_categorie is None:
                        continue

                rates.append(ScrapedRate(
                    geldverstrekker=canonical_gv,
                    productlijn=canonical_product,
                    aflosvorm=aflosvorm,
                    rentevaste_periode=rentevaste_periode,
                    ltv_categorie=ltv_categorie,
                    rente=rente,
                    bron=self.name,
                    raw_geldverstrekker=raw_name,
                    raw_productlijn=raw_name,
                ))

        return rates

    def _parse_bridging_response(self, data: list) -> list[ScrapedRate]:
        """Parse /v1/filter/bridging-loan response.

        Helaas levert die response alleen finDataCode (hash), geen naam.
        We slaan deze daarom op met de hash als identifier en proberen
        ze later te matchen via andere calls (waar zowel naam als finDataCode in zitten).
        """
        # TODO: cache finDataCode → naam mapping uit een eerdere LTV-call
        # Voor nu: skip overbrugging in eerste versie
        return []

    def _split_fastlane_label(self, full_name: str) -> tuple[str | None, str]:
        """Splits een Fastlane label-naam zoals 'ING Hypotheek' of
        'ABN AMRO Budget Hypotheek' in (canonical_geldverstrekker, productlijn).

        Strategie:
        1. Check direct in name_aliases.json voor exacte match
        2. Probeer vanaf langste prefix te matchen met geldverstrekkers.json
        3. De rest is de productlijn
        """
        from rentes.scraper.base import get_canonical_names, get_aliases, get_product_aliases

        canonical = get_canonical_names()
        gv_aliases = get_aliases().get("geldverstrekkers", {})

        # 1. Probeer vanaf langste prefix
        # Sorteer canonical namen op lengte (langste eerst) zodat "ABN AMRO" matched vóór "ABN"
        all_names = sorted(canonical | set(gv_aliases.keys()), key=len, reverse=True)

        for name in all_names:
            # Match case-insensitive aan begin van full_name
            if full_name.lower().startswith(name.lower() + " ") or full_name.lower() == name.lower():
                # Resolve naar canonical
                if name in canonical:
                    canonical_gv = name
                else:
                    canonical_gv = gv_aliases.get(name)
                    if not canonical_gv:
                        continue

                # Productlijn = de rest na de geldverstrekker-naam
                rest = full_name[len(name):].strip()
                if not rest:
                    rest = "Hypotheek"

                # Map de productlijn via aliases
                canonical_product = self.normalize_productlijn(canonical_gv, rest)
                return canonical_gv, canonical_product

        # Geen match
        logger.debug("[fastlane] Geen match voor product: '%s'", full_name)
        return None, full_name
