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
# Alle gangbare periodes. Banken die een periode niet aanbieden krijgen lege rates.
PERIODES_MAANDEN = [
    1,    # variabel
    12,   # 1 jaar
    24,   # 2 jaar
    36,   # 3 jaar
    48,   # 4 jaar
    60,   # 5 jaar
    72,   # 6 jaar
    84,   # 7 jaar
    120,  # 10 jaar
    144,  # 12 jaar
    180,  # 15 jaar
    240,  # 20 jaar
    300,  # 25 jaar
    360,  # 30 jaar
]

def periode_maanden_naar_jaren(maanden: int) -> int:
    """Converteer maanden naar rentevaste periode in jaren (0 = variabel)."""
    if maanden == 1:
        return 0  # variabel
    return maanden // 12

# Basis-rente scrape met label "G" (= 0% korting bij alle banken, matcht
# wat banken publiceren als "Geen energielabel beschikbaar").
ENERGIELABELS = ["G"]

# Voor kortingen-derivation: vergelijk label A/B/C/D vs G.
# Side-scrape doet 1 call per label op een ankerpunt (10jr 80% LTV annuitair),
# en gebruikt het verschil als korting voor alle producten van die bank.
ENERGIELABELS_VOOR_KORTING = ["A", "B", "C", "D"]
KORTING_ANKER_PERIODE_MND = 120  # 10 jaar (meest representatief)
KORTING_ANKER_LTV_SEGMENT = 80   # 80% LTV

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

    async def _mark_token_expired(self) -> None:
        """Markeer token-expiry in scraper_credentials voor monitoring/diagnostiek.

        Playwright auto-refresh werkt niet (Fastlane SSO is sessiegebonden) —
        handmatige refresh nodig via POST /rentes/scraper/set-credentials.
        """
        from rentes.scraper.credentials_store import mark_403
        await mark_403("fastlane")
        logger.error(
            "[fastlane] 403 Invalid token — manuele refresh nodig: "
            "POST /rentes/scraper/set-credentials met nieuwe token uit fastlane.fdta.nl"
        )

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

    async def _preflight_check(self) -> tuple[bool, str | None]:
        """Test of credentials werken door 1 simpele call te doen.

        Returns (ok, error_message). Bij 403 markeert ook expiry in Supabase.
        """
        url = self._build_ltv_url(AFLOSVORMEN["annuitair"], 120, "C", False)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=self._headers())
            if resp.status_code == 200:
                return True, None
            if resp.status_code == 403:
                await self._mark_token_expired()
                return False, (
                    "Token expired (403). Refresh nodig: "
                    "POST /rentes/scraper/set-credentials met nieuwe token uit fastlane.fdta.nl DevTools"
                )
            return False, f"Preflight onverwacht status {resp.status_code}: {resp.text[:200]}"
        except Exception as e:
            return False, f"Preflight exception: {type(e).__name__}: {e}"

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

        # 2. Pre-flight check: bij 403 → falen met instructie
        ok, error_msg = await self._preflight_check()
        if not ok:
            return ScrapeResult(
                bron=self.name, success=False,
                errors=[error_msg or "Pre-flight check mislukt"],
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

            # 2. Energielabel-kortingen afleiden: scrape label A/B/C/D op ankerpunt,
            # vergelijk met basis (label G) op zelfde punt → delta = korting
            all_kortingen: list = []
            try:
                ankur_rates = await self._scrape_kortingen(client)
                all_kortingen.extend(ankur_rates)
                pages_fetched += len(ENERGIELABELS_VOOR_KORTING) + 1  # +1 voor basis-call
            except Exception as e:
                msg = f"Fout bij kortingen-scrape: {e}"
                logger.error("[fastlane] %s", msg)
                errors.append(msg)

            # 3. Overbruggingsrentes (1 call, alle producten) — nog niet geïmplementeerd,
            # response heeft alleen finDataCode. Wordt later toegevoegd.

        duration = time.time() - start
        logger.info(
            "[fastlane] Klaar: %d rentes + %d kortingen, %d calls in %.1fs (%d fouten)",
            len(all_rates), len(all_kortingen), pages_fetched, duration, len(errors),
        )

        return ScrapeResult(
            bron=self.name,
            success=len(all_rates) > 0,
            rates=all_rates,
            kortingen=all_kortingen,
            errors=errors,
            duration_seconds=duration,
            pages_fetched=pages_fetched,
        )

    async def _scrape_kortingen(self, client: httpx.AsyncClient) -> list:
        """Bereken energielabel-korting per geldverstrekker.

        Doet 1 call met label G (basis) en 1 call per label A/B/C/D op het ankerpunt
        (10jr annuïtair, 80% LTV, geen NHG). Verschil = korting voor dat label.

        Banken hebben meestal label-onafhankelijke kortingen die voor alle periodes/LTVs
        gelden. Het is dus voldoende om dit op één ankerpunt te bepalen.

        Returns lijst van ScrapedKorting (1 per geldverstrekker × productlijn).
        """
        from rentes.scraper.models import ScrapedKorting

        # Basis-rentes ophalen (label G) — als die er al zijn vanuit hoofdscrape kunnen we dat hergebruiken
        # Voor eenvoud: aparte call.
        anker_url = self._build_ltv_url(
            AFLOSVORMEN["annuitair"], KORTING_ANKER_PERIODE_MND, "G", False,
        )
        resp = await self._fetch_fastlane(client, anker_url)
        basis_data = resp.json()
        await self._rate_limit()

        # Per (geldverstrekker, productlijn): basis-rente op 80% LTV (index 6 = 80% in riskCategories)
        # riskCategories: [50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110]
        basis_per_product: dict[tuple[str, str], float] = {}
        for product in basis_data.get("labels", []):
            raw_name = product.get("name", "").strip()
            gv, pl = self._split_fastlane_label(raw_name)
            if not gv:
                continue
            interests = product.get("interests", [])
            if len(interests) > 6 and interests[6].get("percentage"):
                try:
                    basis_per_product[(gv, pl)] = float(interests[6]["percentage"])
                except (ValueError, TypeError):
                    pass

        # Per label-keuze: scrape, bereken delta per product
        kortingen_per_product: dict[tuple[str, str], dict[str, float]] = {}
        for label in ENERGIELABELS_VOOR_KORTING:
            url = self._build_ltv_url(
                AFLOSVORMEN["annuitair"], KORTING_ANKER_PERIODE_MND, label, False,
            )
            resp = await self._fetch_fastlane(client, url)
            data = resp.json()
            await self._rate_limit()

            for product in data.get("labels", []):
                raw_name = product.get("name", "").strip()
                gv, pl = self._split_fastlane_label(raw_name)
                if not gv:
                    continue
                interests = product.get("interests", [])
                if len(interests) > 6 and interests[6].get("percentage"):
                    try:
                        rate = float(interests[6]["percentage"])
                    except (ValueError, TypeError):
                        continue
                    basis = basis_per_product.get((gv, pl))
                    if basis is not None:
                        korting = round(rate - basis, 4)  # negatief = korting
                        if (gv, pl) not in kortingen_per_product:
                            kortingen_per_product[(gv, pl)] = {}
                        kortingen_per_product[(gv, pl)][label] = korting

        # Bouw ScrapedKorting objects (1 per gv × productlijn, met staffel dict)
        result = []
        for (gv, pl), staffel in kortingen_per_product.items():
            # Voor labels die niet apart gescraped zijn maar wel logisch dezelfde korting hebben:
            # ING/ABN AMRO etc geven A+, A++, A+++, A++++ allemaal dezelfde korting als A
            if "A" in staffel:
                for premium_label in ["A+", "A++", "A+++", "A++++"]:
                    staffel[premium_label] = staffel["A"]
            # E/F/G hebben geen korting (basis)
            for zero_label in ["E", "F", "G"]:
                staffel[zero_label] = 0.0

            result.append(ScrapedKorting(
                geldverstrekker=gv,
                productlijn=pl,
                korting_type="energielabel",
                staffel=staffel,
                bron=self.name,
                omschrijving="Energielabel-korting (afgeleid van 10jr annuïtair 80% LTV ankerpunt)",
            ))

        logger.info("[fastlane] Kortingen afgeleid voor %d producten", len(result))
        return result

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
