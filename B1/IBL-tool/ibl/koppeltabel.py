"""Koppeltabel Combinatie Betaaltermijnen conform Appendix 8 IBL Rekenregels v8.1.1.

Bevat de mapping tussen maandelijkse en vierwekelijkse datumreeksen,
plus omrekenfuncties voor betaaltermijn-conversie (§5.6).
"""

from datetime import date
from decimal import Decimal
from copy import deepcopy

from .models import LoonItem, Betaaltermijn

# ---------------------------------------------------------------------------
# Koppeltabel data (uit Bijlage-Koppeltabel-Combinatie-Betaaltermijnen.pdf)
# ---------------------------------------------------------------------------

# Maandelijks → Vierwekelijks: de overeenkomende vierwekelijkse datumreeks
# voor elke maandelijkse datumreeks.
MAAND_NAAR_VIERWEEK: dict[tuple[date, date], tuple[date, date]] = {
    # 2023
    (date(2023, 1, 1), date(2023, 1, 31)): (date(2023, 1, 1), date(2023, 1, 29)),
    (date(2023, 2, 1), date(2023, 2, 28)): (date(2023, 1, 30), date(2023, 2, 26)),
    (date(2023, 3, 1), date(2023, 3, 31)): (date(2023, 2, 27), date(2023, 3, 26)),
    (date(2023, 4, 1), date(2023, 4, 30)): (date(2023, 3, 27), date(2023, 4, 23)),
    (date(2023, 5, 1), date(2023, 5, 31)): (date(2023, 4, 24), date(2023, 5, 21)),
    (date(2023, 6, 1), date(2023, 6, 30)): (date(2023, 5, 22), date(2023, 6, 18)),
    (date(2023, 7, 1), date(2023, 7, 31)): (date(2023, 6, 19), date(2023, 7, 16)),
    (date(2023, 8, 1), date(2023, 8, 31)): (date(2023, 8, 14), date(2023, 9, 10)),
    (date(2023, 9, 1), date(2023, 9, 30)): (date(2023, 9, 11), date(2023, 10, 8)),
    (date(2023, 10, 1), date(2023, 10, 31)): (date(2023, 10, 9), date(2023, 11, 5)),
    (date(2023, 11, 1), date(2023, 11, 30)): (date(2023, 11, 6), date(2023, 12, 3)),
    (date(2023, 12, 1), date(2023, 12, 31)): (date(2023, 12, 4), date(2023, 12, 31)),
    # 2024
    (date(2024, 1, 1), date(2024, 1, 31)): (date(2024, 1, 1), date(2024, 1, 28)),
    (date(2024, 2, 1), date(2024, 2, 29)): (date(2024, 1, 29), date(2024, 2, 25)),
    (date(2024, 3, 1), date(2024, 3, 31)): (date(2024, 2, 26), date(2024, 3, 24)),
    (date(2024, 4, 1), date(2024, 4, 30)): (date(2024, 3, 25), date(2024, 4, 21)),
    (date(2024, 5, 1), date(2024, 5, 31)): (date(2024, 4, 22), date(2024, 5, 19)),
    (date(2024, 6, 1), date(2024, 6, 30)): (date(2024, 5, 20), date(2024, 6, 16)),
    (date(2024, 7, 1), date(2024, 7, 31)): (date(2024, 7, 15), date(2024, 8, 11)),
    (date(2024, 8, 1), date(2024, 8, 31)): (date(2024, 8, 12), date(2024, 9, 8)),
    (date(2024, 9, 1), date(2024, 9, 30)): (date(2024, 9, 9), date(2024, 10, 6)),
    (date(2024, 10, 1), date(2024, 10, 31)): (date(2024, 10, 7), date(2024, 11, 3)),
    (date(2024, 11, 1), date(2024, 11, 30)): (date(2024, 11, 4), date(2024, 12, 1)),
    (date(2024, 12, 1), date(2024, 12, 31)): (date(2024, 12, 2), date(2024, 12, 31)),
    # 2025
    (date(2025, 1, 1), date(2025, 1, 31)): (date(2025, 1, 1), date(2025, 1, 26)),
    (date(2025, 2, 1), date(2025, 2, 28)): (date(2025, 1, 27), date(2025, 2, 23)),
    (date(2025, 3, 1), date(2025, 3, 31)): (date(2025, 2, 24), date(2025, 3, 23)),
    (date(2025, 4, 1), date(2025, 4, 30)): (date(2025, 3, 24), date(2025, 4, 20)),
    (date(2025, 5, 1), date(2025, 5, 31)): (date(2025, 4, 21), date(2025, 5, 18)),
    (date(2025, 6, 1), date(2025, 6, 30)): (date(2025, 5, 19), date(2025, 6, 15)),
    (date(2025, 7, 1), date(2025, 7, 31)): (date(2025, 7, 14), date(2025, 8, 10)),
    (date(2025, 8, 1), date(2025, 8, 31)): (date(2025, 8, 11), date(2025, 9, 7)),
    (date(2025, 9, 1), date(2025, 9, 30)): (date(2025, 9, 8), date(2025, 10, 5)),
    (date(2025, 10, 1), date(2025, 10, 31)): (date(2025, 10, 6), date(2025, 11, 2)),
    (date(2025, 11, 1), date(2025, 11, 30)): (date(2025, 11, 3), date(2025, 11, 30)),
    (date(2025, 12, 1), date(2025, 12, 31)): (date(2025, 12, 1), date(2025, 12, 31)),
    # 2026
    (date(2026, 1, 1), date(2026, 1, 31)): (date(2026, 1, 1), date(2026, 1, 25)),
    (date(2026, 2, 1), date(2026, 2, 28)): (date(2026, 1, 26), date(2026, 2, 22)),
    (date(2026, 3, 1), date(2026, 3, 31)): (date(2026, 2, 23), date(2026, 3, 22)),
    (date(2026, 4, 1), date(2026, 4, 30)): (date(2026, 3, 23), date(2026, 4, 19)),
    (date(2026, 5, 1), date(2026, 5, 31)): (date(2026, 4, 20), date(2026, 5, 17)),
    (date(2026, 6, 1), date(2026, 6, 30)): (date(2026, 6, 15), date(2026, 7, 12)),
    (date(2026, 7, 1), date(2026, 7, 31)): (date(2026, 7, 13), date(2026, 8, 9)),
    (date(2026, 8, 1), date(2026, 8, 31)): (date(2026, 8, 10), date(2026, 9, 6)),
    (date(2026, 9, 1), date(2026, 9, 30)): (date(2026, 9, 7), date(2026, 10, 4)),
    (date(2026, 10, 1), date(2026, 10, 31)): (date(2026, 10, 5), date(2026, 11, 1)),
    (date(2026, 11, 1), date(2026, 11, 30)): (date(2026, 11, 2), date(2026, 11, 29)),
    (date(2026, 12, 1), date(2026, 12, 31)): (date(2026, 11, 30), date(2026, 12, 31)),
}

# Vierwekelijks → Maandelijks: de overeenkomende maandelijkse datumreeks
# voor elke vierwekelijkse datumreeks.
VIERWEEK_NAAR_MAAND: dict[tuple[date, date], tuple[date, date]] = {
    # 2023
    (date(2023, 1, 1), date(2023, 1, 29)): (date(2023, 1, 1), date(2023, 1, 31)),
    (date(2023, 1, 30), date(2023, 2, 26)): (date(2023, 2, 1), date(2023, 2, 28)),
    (date(2023, 2, 27), date(2023, 3, 26)): (date(2023, 3, 1), date(2023, 3, 31)),
    (date(2023, 3, 27), date(2023, 4, 23)): (date(2023, 4, 1), date(2023, 4, 30)),
    (date(2023, 4, 24), date(2023, 5, 21)): (date(2023, 5, 1), date(2023, 5, 31)),
    (date(2023, 5, 22), date(2023, 6, 18)): (date(2023, 6, 1), date(2023, 6, 30)),
    (date(2023, 6, 19), date(2023, 7, 16)): (date(2023, 7, 1), date(2023, 7, 31)),
    (date(2023, 7, 17), date(2023, 8, 13)): (date(2023, 7, 1), date(2023, 7, 31)),
    (date(2023, 8, 14), date(2023, 9, 10)): (date(2023, 8, 1), date(2023, 8, 31)),
    (date(2023, 9, 11), date(2023, 10, 8)): (date(2023, 9, 1), date(2023, 9, 30)),
    (date(2023, 10, 9), date(2023, 11, 5)): (date(2023, 10, 1), date(2023, 10, 31)),
    (date(2023, 11, 6), date(2023, 12, 3)): (date(2023, 11, 1), date(2023, 11, 30)),
    (date(2023, 12, 4), date(2023, 12, 31)): (date(2023, 12, 1), date(2023, 12, 31)),
    # 2024
    (date(2024, 1, 1), date(2024, 1, 28)): (date(2024, 1, 1), date(2024, 1, 31)),
    (date(2024, 1, 29), date(2024, 2, 25)): (date(2024, 2, 1), date(2024, 2, 29)),
    (date(2024, 2, 26), date(2024, 3, 24)): (date(2024, 3, 1), date(2024, 3, 31)),
    (date(2024, 3, 25), date(2024, 4, 21)): (date(2024, 4, 1), date(2024, 4, 30)),
    (date(2024, 4, 22), date(2024, 5, 19)): (date(2024, 5, 1), date(2024, 5, 31)),
    (date(2024, 5, 20), date(2024, 6, 16)): (date(2024, 6, 1), date(2024, 6, 30)),
    (date(2024, 6, 17), date(2024, 7, 14)): (date(2024, 6, 1), date(2024, 6, 30)),
    (date(2024, 7, 15), date(2024, 8, 11)): (date(2024, 7, 1), date(2024, 7, 31)),
    (date(2024, 8, 12), date(2024, 9, 8)): (date(2024, 8, 1), date(2024, 8, 31)),
    (date(2024, 9, 9), date(2024, 10, 6)): (date(2024, 9, 1), date(2024, 9, 30)),
    (date(2024, 10, 7), date(2024, 11, 3)): (date(2024, 10, 1), date(2024, 10, 31)),
    (date(2024, 11, 4), date(2024, 12, 1)): (date(2024, 11, 1), date(2024, 11, 30)),
    (date(2024, 12, 2), date(2024, 12, 31)): (date(2024, 12, 1), date(2024, 12, 31)),
    # 2025
    (date(2025, 1, 1), date(2025, 1, 26)): (date(2025, 1, 1), date(2025, 1, 31)),
    (date(2025, 1, 27), date(2025, 2, 23)): (date(2025, 2, 1), date(2025, 2, 28)),
    (date(2025, 2, 24), date(2025, 3, 23)): (date(2025, 3, 1), date(2025, 3, 31)),
    (date(2025, 3, 24), date(2025, 4, 20)): (date(2025, 4, 1), date(2025, 4, 30)),
    (date(2025, 4, 21), date(2025, 5, 18)): (date(2025, 5, 1), date(2025, 5, 31)),
    (date(2025, 5, 19), date(2025, 6, 15)): (date(2025, 6, 1), date(2025, 6, 30)),
    (date(2025, 6, 16), date(2025, 7, 13)): (date(2025, 6, 1), date(2025, 6, 30)),
    (date(2025, 7, 14), date(2025, 8, 10)): (date(2025, 7, 1), date(2025, 7, 31)),
    (date(2025, 8, 11), date(2025, 9, 7)): (date(2025, 8, 1), date(2025, 8, 31)),
    (date(2025, 9, 8), date(2025, 10, 5)): (date(2025, 9, 1), date(2025, 9, 30)),
    (date(2025, 10, 6), date(2025, 11, 2)): (date(2025, 10, 1), date(2025, 10, 31)),
    (date(2025, 11, 3), date(2025, 11, 30)): (date(2025, 11, 1), date(2025, 11, 30)),
    (date(2025, 12, 1), date(2025, 12, 31)): (date(2025, 12, 1), date(2025, 12, 31)),
    # 2026
    (date(2026, 1, 1), date(2026, 1, 25)): (date(2026, 1, 1), date(2026, 1, 31)),
    (date(2026, 1, 26), date(2026, 2, 22)): (date(2026, 2, 1), date(2026, 2, 28)),
    (date(2026, 2, 23), date(2026, 3, 22)): (date(2026, 3, 1), date(2026, 3, 31)),
    (date(2026, 3, 23), date(2026, 4, 19)): (date(2026, 4, 1), date(2026, 4, 30)),
    (date(2026, 4, 20), date(2026, 5, 17)): (date(2026, 5, 1), date(2026, 5, 31)),
    (date(2026, 5, 18), date(2026, 6, 14)): (date(2026, 5, 1), date(2026, 5, 31)),
    (date(2026, 6, 15), date(2026, 7, 12)): (date(2026, 6, 1), date(2026, 6, 30)),
    (date(2026, 7, 13), date(2026, 8, 9)): (date(2026, 7, 1), date(2026, 7, 31)),
    (date(2026, 8, 10), date(2026, 9, 6)): (date(2026, 8, 1), date(2026, 8, 31)),
    (date(2026, 9, 7), date(2026, 10, 4)): (date(2026, 9, 1), date(2026, 9, 30)),
    (date(2026, 10, 5), date(2026, 11, 1)): (date(2026, 10, 1), date(2026, 10, 31)),
    (date(2026, 11, 2), date(2026, 11, 29)): (date(2026, 11, 1), date(2026, 11, 30)),
    (date(2026, 11, 30), date(2026, 12, 31)): (date(2026, 12, 1), date(2026, 12, 31)),
}


# ---------------------------------------------------------------------------
# Betaaltermijn detectie
# ---------------------------------------------------------------------------

def is_vierwekelijks(item: LoonItem) -> bool:
    """Bepaal of een loonitem een vierwekelijkse periode is (~28 dagen)."""
    return item.dagen <= 29


def is_maandelijks(item: LoonItem) -> bool:
    """Bepaal of een loonitem een maandelijkse periode is (28-31 dagen, kalendermaand)."""
    return item.periode_start.day == 1 and item.dagen >= 28 and item.dagen <= 31


def detecteer_betaaltermijn(item: LoonItem) -> Betaaltermijn:
    """Bepaal de betaaltermijn van een individueel loonitem."""
    if item.dagen == 28:
        return Betaaltermijn.VIERWEKELIJKS
    if item.periode_start.day == 1 and 28 <= item.dagen <= 31:
        return Betaaltermijn.MAANDELIJKS
    # Standaard: maandelijks (conform Appendix 7)
    return Betaaltermijn.MAANDELIJKS


def heeft_gemixte_betaaltermijnen(items: list[LoonItem]) -> bool:
    """Controleer of een lijst loon items gemixte betaaltermijnen bevat."""
    if len(items) < 2:
        return False
    termijnen = {detecteer_betaaltermijn(li) for li in items}
    return len(termijnen) > 1


# ---------------------------------------------------------------------------
# Validatie betaaltermijn-wisseling (§5.6.3)
# ---------------------------------------------------------------------------

def valideer_betaaltermijn_wisseling(
    items: list[LoonItem],
) -> tuple[bool, str]:
    """Valideer dat een contract maximaal 1 betaaltermijn-wisseling heeft,
    en dat deze op een kalenderjaarsgrens plaatsvindt.

    Returns: (ok, foutmelding)
    """
    if len(items) < 2:
        return True, ""

    # Sorteer op periode_start (oudst eerst)
    gesorteerd = sorted(items, key=lambda li: li.periode_start)

    wisselingen = []
    vorige_bt = detecteer_betaaltermijn(gesorteerd[0])

    for li in gesorteerd[1:]:
        huidige_bt = detecteer_betaaltermijn(li)
        if huidige_bt != vorige_bt:
            wisselingen.append(li.periode_start)
            vorige_bt = huidige_bt

    if len(wisselingen) > 1:
        return False, (
            "IBL-berekening niet mogelijk: meerdere wisselingen van "
            "betaaltermijn gedetecteerd binnen hetzelfde contract."
        )

    if len(wisselingen) == 1:
        # Wisseling moet op kalenderjaarsgrens (januari of rond jaareinde)
        wisseldatum = wisselingen[0]
        if wisseldatum.month != 1:
            return False, (
                "IBL-berekening niet mogelijk: wisseling van betaaltermijn "
                f"niet op kalenderjaarsgrens (gevonden: {wisseldatum})."
            )

    return True, ""


# ---------------------------------------------------------------------------
# Omrekening (§5.6.5 en §5.6.6)
# ---------------------------------------------------------------------------

def _zoek_doelperiodes(
    bron_start: date,
    bron_eind: date,
    doel_betaaltermijn: Betaaltermijn,
) -> list[tuple[date, date]]:
    """Zoek alle doelperiodes die overlappen met een bronperiode.

    Gebruikt de koppeltabel om alle bekende doelperiode-datumreeksen te kennen,
    en selecteert die met overlap.

    Returns: lijst van (start, eind) tuples, gesorteerd op startdatum.
    """
    # Alle bekende doelperiode-datumreeksen ophalen
    if doel_betaaltermijn == Betaaltermijn.VIERWEKELIJKS:
        # Doelperiodes zijn vierwekelijks: dit zijn de keys van VIERWEEK_NAAR_MAAND
        alle_doelperiodes = list(VIERWEEK_NAAR_MAAND.keys())
    else:
        # Doelperiodes zijn maandelijks: dit zijn de keys van MAAND_NAAR_VIERWEEK
        alle_doelperiodes = list(MAAND_NAAR_VIERWEEK.keys())

    # Zoek alle doelperiodes die overlappen met de bronperiode
    doelen = []
    for doel_start, doel_eind in alle_doelperiodes:
        if bron_start <= doel_eind and bron_eind >= doel_start:
            doelen.append((doel_start, doel_eind))

    return sorted(doelen) if doelen else [(bron_start, bron_eind)]


def _bereken_aandeel(
    bron_start: date,
    bron_eind: date,
    doel_start: date,
    doel_eind: date,
) -> Decimal:
    """Bereken het aandeel van een doelperiode in een bronperiode.

    Aandeel = dagen van doelperiode die in bronperiode vallen / totaal dagen bronperiode.
    """
    # Overlap berekenen
    overlap_start = max(bron_start, doel_start)
    overlap_eind = min(bron_eind, doel_eind)

    if overlap_start > overlap_eind:
        return Decimal("0")

    dagen_overlap = (overlap_eind - overlap_start).days + 1
    dagen_bron = (bron_eind - bron_start).days + 1

    return Decimal(str(dagen_overlap)) / Decimal(str(dagen_bron))


def reken_items_om(
    items: list[LoonItem],
    doel_betaaltermijn: Betaaltermijn,
) -> list[LoonItem]:
    """Reken loon items om naar een andere betaaltermijn (§5.6.5.1).

    Per bronperiode die een andere betaaltermijn heeft dan het doel:
    1. Bepaal doelperiode(s) via koppeltabel
    2. Bereken aandeel per doelperiode
    3. Verdeel SV-loon, uren, waarde privegebruik, eigen bijdrage

    Items die al de juiste betaaltermijn hebben worden ongewijzigd doorgegeven.

    Returns: nieuwe lijst van LoonItems met doelbetaaltermijn-datums.
    """
    resultaat: list[LoonItem] = []

    for item in items:
        item_bt = detecteer_betaaltermijn(item)

        if item_bt == doel_betaaltermijn:
            # Geen omrekening nodig
            resultaat.append(deepcopy(item))
            continue

        # Omrekening nodig
        doelperiodes = _zoek_doelperiodes(
            item.periode_start, item.periode_eind, doel_betaaltermijn
        )

        for doel_start, doel_eind in doelperiodes:
            aandeel = _bereken_aandeel(
                item.periode_start, item.periode_eind,
                doel_start, doel_eind,
            )

            if aandeel <= Decimal("0"):
                continue

            nieuw_item = LoonItem(
                periode_start=doel_start,
                periode_eind=doel_eind,
                aantal_uur=item.aantal_uur * aandeel,
                sv_loon=item.sv_loon * aandeel,
                eigen_bijdrage_auto=(
                    item.eigen_bijdrage_auto * aandeel
                    if item.eigen_bijdrage_auto else None
                ),
                waarde_privegebruik_auto=(
                    item.waarde_privegebruik_auto * aandeel
                    if item.waarde_privegebruik_auto else None
                ),
            )
            resultaat.append(nieuw_item)

    # Combineer items met dezelfde doelperiode (meerdere bronnen → 1 doel)
    return _combineer_gelijke_periodes(resultaat)


def _combineer_gelijke_periodes(items: list[LoonItem]) -> list[LoonItem]:
    """Combineer LoonItems met dezelfde datumreeks."""
    per_periode: dict[tuple[date, date], LoonItem] = {}

    for item in items:
        key = (item.periode_start, item.periode_eind)
        if key in per_periode:
            bestaand = per_periode[key]
            bestaand.aantal_uur += item.aantal_uur
            bestaand.sv_loon += item.sv_loon
            if item.eigen_bijdrage_auto is not None:
                if bestaand.eigen_bijdrage_auto is None:
                    bestaand.eigen_bijdrage_auto = item.eigen_bijdrage_auto
                else:
                    bestaand.eigen_bijdrage_auto += item.eigen_bijdrage_auto
            if item.waarde_privegebruik_auto is not None:
                if bestaand.waarde_privegebruik_auto is None:
                    bestaand.waarde_privegebruik_auto = item.waarde_privegebruik_auto
                else:
                    bestaand.waarde_privegebruik_auto += item.waarde_privegebruik_auto
        else:
            per_periode[key] = deepcopy(item)

    return sorted(per_periode.values(), key=lambda li: li.periode_eind, reverse=True)


def reken_contract_om_naar_mrl_betaaltermijn(
    items: list[LoonItem],
) -> tuple[list[LoonItem], Betaaltermijn]:
    """Reken een contract om naar de betaaltermijn van het MRL (§5.6.5).

    De betaaltermijn van het Meest Recente Loonitem is leidend.
    Historische periodes met een andere betaaltermijn worden omgerekend.

    Returns: (omgerekende items, MRL betaaltermijn)
    """
    if not items:
        return items, Betaaltermijn.MAANDELIJKS

    # MRL = meest recent (gesorteerd meest recent eerst aangenomen)
    gesorteerd = sorted(items, key=lambda li: li.periode_eind, reverse=True)
    mrl = gesorteerd[0]
    mrl_bt = detecteer_betaaltermijn(mrl)

    if not heeft_gemixte_betaaltermijnen(items):
        return items, mrl_bt

    omgerekend = reken_items_om(items, mrl_bt)
    return omgerekend, mrl_bt
