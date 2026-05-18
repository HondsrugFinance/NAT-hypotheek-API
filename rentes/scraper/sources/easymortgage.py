"""EasyMortgage / Hypotheekrente.nl scraper.

Beide sites (easymortgage.nl EN hypotheekrente.nl) zijn van dezelfde organisatie
en gebruiken exact dezelfde HTML-structuur. We scrapen hypotheekrente.nl (NL) als
primaire bron — dat is de Nederlandse markt.

URL-patronen:
  hypotheekrente.nl:  /rente/{periode}/{ltv}/{energielabel}/
  easymortgage.nl:    /rates/{period}/{ltv}/{energielabel}/

Periodes (NL): variabele-rente, 1-jaar-rentevast, ..., 30-jaar-rentevast
LTV: nhg, 60, 80, 90, 100
Energielabel: a, b, c, d, e, f, g

HTML-structuur:
  <tr class="interests__item">
    <td class="interests__item-brand">
      <img title="ABN Amro">                     → banknaam
    </td>
    <td class="interests__item-name visible-mobile">Budget</td>  → productnaam
    <td class="interests__item-rates hidden-mobile">
      <div class="rate rate--active">4.05%</div>  → actieve rente voor huidige LTV
    </td>
  </tr>
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from rentes.scraper.base import BaseScraper
from rentes.scraper.models import ScrapedRate, ScrapeResult

logger = logging.getLogger("nat-api.scraper.easymortgage")


# --- URL-configuratie ---

BASE_URL_NL = "https://www.hypotheekrente.nl"
BASE_URL_EN = "https://www.easymortgage.nl"

# Periodes: (url_segment_nl, url_segment_en, rentevaste_periode_jaren)
PERIODES = [
    ("variabele-rente",    "variable-rate",   0),
    ("1-jaar-rentevast",   "1-year-fixed",    1),
    ("2-jaar-rentevast",   "2-year-fixed",    2),
    ("3-jaar-rentevast",   "3-year-fixed",    3),
    ("4-jaar-rentevast",   "4-year-fixed",    4),
    ("5-jaar-rentevast",   "5-year-fixed",    5),
    ("6-jaar-rentevast",   "6-year-fixed",    6),
    ("7-jaar-rentevast",   "7-year-fixed",    7),
    ("10-jaar-rentevast",  "10-year-fixed",  10),
    ("12-jaar-rentevast",  "12-year-fixed",  12),
    ("15-jaar-rentevast",  "15-year-fixed",  15),
    ("17-jaar-rentevast",  "17-year-fixed",  17),
    ("20-jaar-rentevast",  "20-year-fixed",  20),
    ("25-jaar-rentevast",  "25-year-fixed",  25),
    ("30-jaar-rentevast",  "30-year-fixed",  30),
]

# LTV-niveaus: (url_segment, database_categorie)
LTV_NIVEAUS = [
    ("nhg", "NHG"),
    ("60",  "60"),
    ("80",  "80"),
    ("90",  "90"),
    ("100", "100"),
]

# We scrapen alleen energielabel 'a' (= laagste rente) en 'g' (= geen korting).
# Het verschil is de energielabel-korting.
ENERGIELABELS = ["a", "g"]


class EasyMortgageScraper(BaseScraper):
    """Scraper voor hypotheekrente.nl (NL) en easymortgage.nl (EN)."""

    name = "easymortgage"
    priority = 10  # primaire bron
    request_delay = 1.5  # seconden tussen requests

    def __init__(self, use_nl: bool = True):
        super().__init__()
        self.base_url = BASE_URL_NL if use_nl else BASE_URL_EN
        self.use_nl = use_nl

    def _build_url(self, periode_idx: int, ltv_segment: str, energielabel: str) -> str:
        """Bouw de URL voor een specifieke combinatie."""
        nl_seg, en_seg, _ = PERIODES[periode_idx]
        segment = nl_seg if self.use_nl else en_seg
        prefix = "rente" if self.use_nl else "rates"
        return f"{self.base_url}/{prefix}/{segment}/{ltv_segment}/{energielabel}/"

    async def scrape(self) -> ScrapeResult:
        """Scrape alle combinaties van periode × LTV × energielabel."""
        start = time.time()
        all_rates: list[ScrapedRate] = []
        errors: list[str] = []
        pages_fetched = 0
        structure_hash = None

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            for pi, (_, _, rvp) in enumerate(PERIODES):
                for ltv_seg, ltv_cat in LTV_NIVEAUS:
                    for label in ENERGIELABELS:
                        url = self._build_url(pi, ltv_seg, label)
                        try:
                            resp = await self._fetch(client, url)
                            pages_fetched += 1

                            rates, page_hash = self._parse_page(
                                resp.text, rvp, ltv_cat, label
                            )
                            all_rates.extend(rates)

                            # Bewaar eerste hash als structuur-fingerprint
                            if structure_hash is None:
                                structure_hash = page_hash

                        except Exception as e:
                            msg = f"Fout bij {url}: {e}"
                            logger.error("[easymortgage] %s", msg)
                            errors.append(msg)

                        await self._rate_limit()

        duration = time.time() - start
        logger.info(
            "[easymortgage] Klaar: %d rentes van %d pagina's in %.1fs (%d fouten)",
            len(all_rates), pages_fetched, duration, len(errors),
        )

        result = ScrapeResult(
            bron=self.name,
            success=len(errors) == 0 and len(all_rates) > 0,
            rates=all_rates,
            errors=errors,
            duration_seconds=duration,
            pages_fetched=pages_fetched,
        )
        return result

    def _parse_page(
        self,
        html: str,
        rentevaste_periode: int,
        ltv_categorie: str,
        energielabel: str,
    ) -> tuple[list[ScrapedRate], str]:
        """Parse één pagina en retourneer (rates, structure_hash).

        De structure_hash is een hash van de CSS-klassen in de tabel,
        zodat we kunnen detecteren als de site-layout wijzigt.
        """
        soup = BeautifulSoup(html, "lxml")

        # Structuur-fingerprint: hash van de eerste tabel-header
        header = soup.select_one("thead.interests__header")
        structure_hash = ""
        if header:
            structure_hash = hashlib.md5(
                str(header).encode()
            ).hexdigest()[:12]

        # Parse alle rij-items
        rows = soup.select("tr.interests__item")
        rates: list[ScrapedRate] = []

        for row in rows:
            try:
                rate = self._parse_row(row, rentevaste_periode, ltv_categorie, energielabel)
                if rate:
                    rates.append(rate)
            except Exception as e:
                logger.debug("[easymortgage] Fout bij rij parsing: %s", e)

        return rates, structure_hash

    def _parse_row(
        self,
        row,
        rentevaste_periode: int,
        ltv_categorie: str,
        energielabel: str,
    ) -> ScrapedRate | None:
        """Parse één <tr class='interests__item'> rij."""

        # 1. Banknaam uit <img title="...">
        img = row.select_one("td.interests__item-brand img[title]")
        if not img:
            return None
        raw_bank = img["title"].strip()

        # 2. Productnaam uit <td class="interests__item-name visible-mobile">
        product_td = row.select_one("td.interests__item-name.visible-mobile")
        raw_product = product_td.get_text(strip=True) if product_td else raw_bank

        # 3. Actieve rente uit <div class="rate rate--active">
        rate_div = row.select_one("div.rate.rate--active")
        if not rate_div:
            # Fallback: mobile rate
            rate_td = row.select_one("td.interests__item-rate.visible-mobile")
            if not rate_td:
                return None
            rate_text = rate_td.get_text(strip=True)
        else:
            rate_text = rate_div.get_text(strip=True)

        # Parse percentage: "3.98%" → 3.98
        rate_match = re.search(r"([\d.]+)%", rate_text)
        if not rate_match:
            return None
        rente = float(rate_match.group(1))

        # 4. Normaliseer namen
        canonical_bank = self.normalize_geldverstrekker(raw_bank)
        if not canonical_bank:
            return None

        canonical_product = self.normalize_productlijn(canonical_bank, raw_product)

        return ScrapedRate(
            geldverstrekker=canonical_bank,
            productlijn=canonical_product,
            aflosvorm="annuitair",  # easymortgage toont annuitair/lineair (zelfde rente)
            rentevaste_periode=rentevaste_periode,
            ltv_categorie=ltv_categorie,
            rente=rente,
            bron=self.name,
            raw_geldverstrekker=raw_bank,
            raw_productlijn=raw_product,
        )
