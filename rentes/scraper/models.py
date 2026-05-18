"""Datamodellen voor de rente-scraper."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ScrapedRate:
    """Eén geschraapte rente uit een bron."""

    geldverstrekker: str          # Canonical naam (na normalisatie)
    productlijn: str              # Productnaam
    aflosvorm: str                # annuitair | lineair | aflossingsvrij
    rentevaste_periode: int       # Jaren (0 = variabel)
    ltv_categorie: str            # "NHG", "60", "70", "80", "90", "100"
    rente: float                  # Percentage, bijv. 3.96
    bron: str                     # "easymortgage", "handelsbanken", etc.
    scrape_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Originele naam zoals gescraped (voor debugging)
    raw_geldverstrekker: str = ""
    raw_productlijn: str = ""


@dataclass
class ScrapedKorting:
    """Eén geschraapte korting (bijv. energielabel-staffel) per geldverstrekker."""

    geldverstrekker: str
    productlijn: str
    korting_type: str             # "energielabel", "betaalrekening", etc.
    staffel: dict[str, float]     # {"A": -0.20, "B": -0.12, ...}
    bron: str
    omschrijving: str = ""


@dataclass
class ScrapeResult:
    """Resultaat van één scraper-run."""

    bron: str
    success: bool
    rates: list[ScrapedRate] = field(default_factory=list)
    kortingen: list[ScrapedKorting] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    pages_fetched: int = 0


@dataclass
class RateChange:
    """Eén rentewijziging t.o.v. vorige waarde."""

    geldverstrekker: str
    productlijn: str
    aflosvorm: str
    rentevaste_periode: int
    ltv_categorie: str
    oude_rente: float
    nieuwe_rente: float
    verschil: float  # nieuwe - oude


@dataclass
class ValidationReport:
    """Resultaat van cross-validatie."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_rates: int = 0
    stored: int = 0
    skipped_manual: int = 0
    changes: list[RateChange] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)    # afwijking 0.05-0.20%
    quarantined: list[dict] = field(default_factory=list)  # afwijking > 0.20% of bron-conflict
    errors: list[str] = field(default_factory=list)
