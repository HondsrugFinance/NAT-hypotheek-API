"""BaseScraper ABC — gedeelde logica voor alle scraper-bronnen."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from abc import ABC, abstractmethod
from pathlib import Path

import httpx

from rentes.scraper.models import ScrapedRate, ScrapeResult

logger = logging.getLogger("nat-api.scraper")

_DIR = Path(__file__).parent
_ALIASES_PATH = _DIR / "name_aliases.json"


def _load_aliases() -> dict[str, str]:
    """Laad naamnormalisatie mapping (scraped naam → canonical naam)."""
    if _ALIASES_PATH.exists():
        with open(_ALIASES_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _load_canonical_names() -> set[str]:
    """Laad canonical namen uit geldverstrekkers.json."""
    config_path = Path(__file__).parent.parent.parent / "config" / "geldverstrekkers.json"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("geldverstrekkers", []))
    return set()


# Singleton caches
_aliases: dict[str, str] | None = None
_canonical: set[str] | None = None


def get_aliases() -> dict[str, str]:
    global _aliases
    if _aliases is None:
        _aliases = _load_aliases()
    return _aliases


def get_canonical_names() -> set[str]:
    global _canonical
    if _canonical is None:
        _canonical = _load_canonical_names()
    return _canonical


# Productlijn-aliassen (scraped → canonical)
def _load_product_aliases() -> dict[str, dict[str, str]]:
    """Laad productlijn-aliassen uit name_aliases.json (key: 'productlijnen')."""
    if _ALIASES_PATH.exists():
        with open(_ALIASES_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("productlijnen", {})
    return {}


_product_aliases: dict[str, dict[str, str]] | None = None


def get_product_aliases() -> dict[str, dict[str, str]]:
    global _product_aliases
    if _product_aliases is None:
        _product_aliases = _load_product_aliases()
    return _product_aliases


# User-Agents roteren om blokkades te voorkomen
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]


class BaseScraper(ABC):
    """Abstract base class voor alle rente-scrapers."""

    name: str = "base"
    priority: int = 50  # lagere = betrouwbaarder

    # Rate limiting: seconden tussen requests naar dezelfde host
    request_delay: float = 2.0
    max_retries: int = 3
    timeout: float = 15.0

    def __init__(self):
        self._user_agent = random.choice(_USER_AGENTS)

    @abstractmethod
    async def scrape(self) -> ScrapeResult:
        """Scrape rentes van deze bron. Retourneert ScrapeResult."""
        ...

    async def _fetch(self, client: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response:
        """HTTP GET met retry en rate limiting."""
        headers = kwargs.pop("headers", {})
        headers.setdefault("User-Agent", self._user_agent)
        headers.setdefault("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
        headers.setdefault("Accept-Language", "nl-NL,nl;q=0.9,en;q=0.8")

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = await client.get(url, headers=headers, **kwargs)
                resp.raise_for_status()
                return resp
            except (httpx.HTTPStatusError, httpx.TransportError) as e:
                last_error = e
                if attempt < self.max_retries:
                    wait = self.request_delay * attempt + random.uniform(0, 1)
                    logger.warning(
                        "[%s] Poging %d/%d mislukt voor %s: %s — wacht %.1fs",
                        self.name, attempt, self.max_retries, url, e, wait,
                    )
                    await asyncio.sleep(wait)

        raise last_error  # type: ignore[misc]

    async def _rate_limit(self):
        """Wacht tussen requests."""
        jitter = random.uniform(0, self.request_delay * 0.3)
        await asyncio.sleep(self.request_delay + jitter)

    def normalize_geldverstrekker(self, raw_name: str) -> str | None:
        """Normaliseer scraped naam naar canonical naam uit geldverstrekkers.json.

        Returns None als geen match gevonden — deze rate wordt overgeslagen.
        """
        raw = raw_name.strip()
        aliases = get_aliases()
        canonical = get_canonical_names()

        # 1. Exacte match met canonical
        if raw in canonical:
            return raw

        # 2. Check aliassen
        gv_aliases = aliases.get("geldverstrekkers", {})
        if raw in gv_aliases:
            return gv_aliases[raw]

        # 3. Case-insensitive match
        raw_lower = raw.lower()
        for name in canonical:
            if name.lower() == raw_lower:
                return name

        # 4. Geen match
        logger.warning("[%s] Onbekende geldverstrekker: '%s'", self.name, raw)
        return None

    def normalize_productlijn(self, geldverstrekker: str, raw_product: str) -> str:
        """Normaliseer productnaam. Retourneert canonical naam of origineel."""
        aliases = get_product_aliases()
        gv_products = aliases.get(geldverstrekker, {})
        return gv_products.get(raw_product, raw_product)
