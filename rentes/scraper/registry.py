"""ScraperRegistry — registreert en beheert alle scraper-bronnen."""

from __future__ import annotations

from rentes.scraper.base import BaseScraper


class ScraperRegistry:
    """Centraal register van alle beschikbare scrapers."""

    def __init__(self):
        self._scrapers: dict[str, BaseScraper] = {}

    def register(self, scraper: BaseScraper) -> None:
        self._scrapers[scraper.name] = scraper

    def get(self, name: str) -> BaseScraper | None:
        return self._scrapers.get(name)

    def all(self) -> list[BaseScraper]:
        """Alle scrapers, gesorteerd op prioriteit (laagste eerst = meest betrouwbaar)."""
        return sorted(self._scrapers.values(), key=lambda s: s.priority)

    def names(self) -> list[str]:
        return list(self._scrapers.keys())


# Globale registry
registry = ScraperRegistry()


def register_all():
    """Registreer alle beschikbare scrapers.

    Volgorde van prioriteit:
    1. Fastlane (priority=1) — primair: complete data via Hypotheekbond API
       - 96 producten, 13 LTV-staffels, 4 aflosvormen, NHG-tarieven
       - Vereist FASTLANE_AUTH_TOKEN + FASTLANE_USER_HASH env vars
    2. Easymortgage (priority=10) — alleen voor cross-validatie als ENABLE_EASYMORTGAGE=1
       - Beperkte data (5 LTV-staffels), publieke vergelijkingssite
    """
    import os

    from rentes.scraper.sources.fastlane import FastlaneScraper

    # Fastlane is alleen actief als de credentials beschikbaar zijn
    if os.environ.get("FASTLANE_AUTH_TOKEN") and os.environ.get("FASTLANE_USER_HASH"):
        if not registry.get("fastlane"):
            registry.register(FastlaneScraper())

    # Easymortgage alleen actief als expliciet aangezet (voor cross-validatie)
    if os.environ.get("ENABLE_EASYMORTGAGE", "").lower() in ("1", "true", "yes"):
        from rentes.scraper.sources.easymortgage import EasyMortgageScraper
        if not registry.get("easymortgage"):
            registry.register(EasyMortgageScraper())
