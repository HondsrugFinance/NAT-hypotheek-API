"""Datamodellen voor de IBL Toetsinkomen Calculator."""

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date
from enum import Enum
from typing import Optional


# --- Enums ---

class Contractvorm(Enum):
    VAST = "vast"
    NIET_VAST = "niet_vast"


class Betaaltermijn(Enum):
    MAANDELIJKS = "maandelijks"      # 12 periodes per jaar
    VIERWEKELIJKS = "vierwekelijks"  # 13 periodes per jaar


class BerekeningType(Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


# --- Vaste contractvormen (uit Appendix 6 rekenregels) ---

VASTE_CONTRACTVORMEN = {
    "schriftelijke arbeidsovereenkomst voor onbepaalde tijd, geen oproepovereenkomst",
    "publiekrechtelijke aanstelling voor onbepaalde tijd",
}

# "niet schriftelijke arbeidsovereenkomst voor onbepaalde tijd, geen oproepovereenkomst"
# is Vast als loonhistorie >= 3 jaar, anders Niet-Vast. Dit wordt apart afgehandeld.

NIET_VAST_CONTRACTVORMEN = {
    "schriftelijke arbeidsovereenkomst voor onbepaalde tijd, oproepovereenkomst",
    "niet schriftelijke arbeidsovereenkomst voor onbepaalde tijd, oproepovereenkomst",
    "schriftelijke arbeidsovereenkomst voor bepaalde tijd, geen oproepovereenkomst",
    "schriftelijke arbeidsovereenkomst voor bepaalde tijd, oproepovereenkomst",
    "niet schriftelijke arbeidsovereenkomst voor bepaalde tijd, geen oproepovereenkomst",
    "niet schriftelijke arbeidsovereenkomst voor bepaalde tijd, oproepovereenkomst",
    "publiekrechtelijke aanstelling voor bepaalde tijd",
}

NIET_SCHRIFTELIJK_ONBEPAALD = (
    "niet schriftelijke arbeidsovereenkomst voor onbepaalde tijd, geen oproepovereenkomst"
)

# UWV-uitkering loonheffingennummers (uit bijlage)
UWV_UITKERING_LOONHEFFINGENNUMMERS = {
    "810220350L02",
    "810220350L04",
    "810220350L20",
    "810220350L23",
    "810220350L26",
    "810220350L53",
}

# --- Constanten ---

GRENSWAARDE_URENPERCENTAGE = Decimal("93.7")
GRENSWAARDE_BESTENDIGHEID_STIJGING = Decimal("120")  # 120%
URENGRENS_MAANDELIJKS = Decimal("200")
URENGRENS_VIERWEKELIJKS = Decimal("184")


# --- Dataclasses ---

@dataclass
class LoonItem:
    """Een enkele regel uit het UWV Verzekeringsbericht."""
    periode_start: date
    periode_eind: date
    aantal_uur: Decimal
    sv_loon: Decimal
    eigen_bijdrage_auto: Optional[Decimal] = None
    waarde_privegebruik_auto: Optional[Decimal] = None

    @property
    def netto_bijtelling(self) -> Decimal:
        """Waarde privégebruik auto minus eigen bijdrage auto."""
        if self.waarde_privegebruik_auto is None:
            return Decimal("0.00")
        eb = self.eigen_bijdrage_auto or Decimal("0.00")
        return self.waarde_privegebruik_auto - eb

    @property
    def dagen(self) -> int:
        """Aantal kalenderdagen in deze periode."""
        return (self.periode_eind - self.periode_start).days + 1

    def __repr__(self):
        return (f"LoonItem({self.periode_start} t/m {self.periode_eind}, "
                f"uur={self.aantal_uur}, sv={self.sv_loon})")


@dataclass
class ContractBlok:
    """Een blok loongegevens onder één contractheader uit het VZB."""
    werkgever_naam: str
    loonheffingennummer: str
    verzekerde_wetten: str
    contractvorm: Optional[str]  # None als rubriek ontbreekt
    loon_items: list[LoonItem] = field(default_factory=list)

    @property
    def is_uitkering_uwv(self) -> bool:
        return self.loonheffingennummer in UWV_UITKERING_LOONHEFFINGENNUMMERS

    @property
    def heeft_contractvorm(self) -> bool:
        return self.contractvorm is not None and self.contractvorm.strip() != ""


@dataclass
class SamengevoegdContract:
    """Een (eventueel samengevoegd) contract bij dezelfde werkgever."""
    werkgever_naam: str
    loonheffingennummer: str
    contractvorm_raw: str  # Meest recente contractvorm string
    contractvorm: Contractvorm  # Vast of Niet-Vast
    betaaltermijn: Betaaltermijn
    loon_items: list[LoonItem] = field(default_factory=list)
    is_uitkering_uwv: bool = False
    is_actief: bool = True

    @property
    def meest_recent_loonitem(self) -> Optional[LoonItem]:
        if not self.loon_items:
            return None
        return max(self.loon_items, key=lambda li: li.periode_eind)

    @property
    def oudste_loonitem(self) -> Optional[LoonItem]:
        if not self.loon_items:
            return None
        return min(self.loon_items, key=lambda li: li.periode_start)

    def loon_items_gesorteerd(self) -> list[LoonItem]:
        """Loon items gesorteerd van meest recent naar oudst."""
        return sorted(self.loon_items, key=lambda li: li.periode_eind, reverse=True)

    def perioden_count(self) -> int:
        """Aantal periodes met loongegevens."""
        return len(self.loon_items)


@dataclass
class Tussenresultaat:
    """Alle tussenwaarden voor audit trail."""
    # Uren
    u3: Optional[Decimal] = None
    ujr: Optional[Decimal] = None
    urenpercentage: Optional[Decimal] = None

    # Parttime
    upt3: Optional[Decimal] = None
    uptjr: Optional[Decimal] = None
    parttimepercentage: Optional[Decimal] = None

    # Bestendigheidstoets
    bestendigheid_criterium1_ratio: Optional[Decimal] = None
    bestendigheid_criterium1_geslaagd: Optional[bool] = None
    bestendigheid_criterium2_geslaagd: Optional[bool] = None
    bestendigheid_geslaagd: Optional[bool] = None

    # Inkomensdelen
    i3: Optional[Decimal] = None
    i9: Optional[Decimal] = None
    i21: Optional[Decimal] = None
    i33: Optional[Decimal] = None
    i_jr: Optional[Decimal] = None
    i_2jr: Optional[Decimal] = None
    i_3jr: Optional[Decimal] = None

    # Auto van de zaak
    z_jr: Optional[Decimal] = None
    z_2jr: Optional[Decimal] = None
    z_3jr: Optional[Decimal] = None

    # Pieken
    gemiddeld_periode_inkomen: Optional[Decimal] = None
    gemiddeld_jaarinkomen: Optional[Decimal] = None
    gemiddeld_jaarinkomen_1jr: Optional[Decimal] = None
    gemiddeld_jaarinkomen_3jr: Optional[Decimal] = None

    # Pensioen
    eigen_bijdrage_pensioen_maand: Decimal = Decimal("0.00")
    eigen_bijdrage_pensioen_jaar: Optional[Decimal] = None


@dataclass
class IBLResultaat:
    """Eindresultaat van een IBL-berekening."""
    aanvrager_naam: str
    aanmaakdatum: date
    werkgever_naam: str
    berekening_type: BerekeningType
    toetsinkomen: Decimal
    tussenresultaat: Tussenresultaat
    waarschuwingen: list[str] = field(default_factory=list)


# --- Helper functies ---

def perioden_voor(label: str, betaaltermijn: Betaaltermijn) -> int:
    """Vertaal logische periodeaantallen naar werkelijke aantallen per betaaltermijn.

    Maandelijks:    3→3, 9→9,  12→12, 24→24, 36→36
    Vierwekelijks:  3→3, 9→10, 12→13, 24→26, 36→39
    """
    mapping = {
        Betaaltermijn.MAANDELIJKS: {
            "3": 3, "4": 4, "9": 9, "12": 12, "21": 21, "24": 24, "33": 33, "36": 36,
        },
        Betaaltermijn.VIERWEKELIJKS: {
            "3": 3, "4": 4, "9": 10, "12": 13, "21": 22, "24": 26, "33": 36, "36": 39,
        },
    }
    return mapping[betaaltermijn][label]


def jaar_perioden(betaaltermijn: Betaaltermijn) -> int:
    """Aantal periodes in een jaar: 12 (maandelijks) of 13 (vierwekelijks)."""
    return 12 if betaaltermijn == Betaaltermijn.MAANDELIJKS else 13
