"""Voorverwerking: samenvoegen contracten, verlofregel, betaaltermijn bepaling."""

from collections import defaultdict
from copy import deepcopy
from decimal import Decimal
from datetime import date, timedelta
from typing import Optional

from .models import (
    ContractBlok, SamengevoegdContract, LoonItem,
    Contractvorm, Betaaltermijn,
    VASTE_CONTRACTVORMEN, NIET_VAST_CONTRACTVORMEN, NIET_SCHRIFTELIJK_ONBEPAALD,
)


def bepaal_betaaltermijn(loon_items: list[LoonItem]) -> Betaaltermijn:
    """Bepaal of de loon items maandelijks of vierwekelijks zijn.

    Vierwekelijks: periodelengte is exact 28 dagen.
    Maandelijks: periodelengte is 28-31 dagen (kalendermaand).
    """
    if not loon_items:
        return Betaaltermijn.MAANDELIJKS

    # Tel periodes met exact 28 dagen vs andere
    count_28 = sum(1 for li in loon_items if li.dagen == 28)
    count_other = len(loon_items) - count_28

    # Als meerderheid 28 dagen is → vierwekelijks
    if count_28 > count_other:
        return Betaaltermijn.VIERWEKELIJKS
    return Betaaltermijn.MAANDELIJKS


def bepaal_contractvorm(contractvorm_raw: Optional[str], jaren_loonhistorie: int) -> Contractvorm:
    """Bepaal of een contract Vast of Niet-Vast is op basis van de contractvorm string."""
    if contractvorm_raw is None:
        return Contractvorm.NIET_VAST

    cv = contractvorm_raw.strip().lower()

    # Check vaste contractvormen
    for vast_cv in VASTE_CONTRACTVORMEN:
        if cv == vast_cv.lower():
            return Contractvorm.VAST

    # Speciaal geval: niet-schriftelijk onbepaald
    if cv == NIET_SCHRIFTELIJK_ONBEPAALD.lower():
        if jaren_loonhistorie >= 3:
            return Contractvorm.VAST
        return Contractvorm.NIET_VAST

    # Check niet-vaste contractvormen
    for niet_vast_cv in NIET_VAST_CONTRACTVORMEN:
        if cv == niet_vast_cv.lower():
            return Contractvorm.NIET_VAST

    # Onbekende contractvorm → niet-vast
    return Contractvorm.NIET_VAST


def _periodes_sluiten_aan(items_a: list[LoonItem], items_b: list[LoonItem]) -> bool:
    """Controleer of twee sets loon items aansluitende datumreeksen hebben.

    Aansluiting: de einddatum van de oudste periode van set A is 1 dag voor
    de startdatum van de nieuwste periode van set B, of er is overlap van max 1 dag.
    """
    if not items_a or not items_b:
        return False

    # Sorteer beide sets op datum
    a_oudste = min(items_a, key=lambda li: li.periode_start)
    b_nieuwste = max(items_b, key=lambda li: li.periode_eind)

    # items_a is recenter, items_b is ouder
    # Dus items_b moet aansluiten op items_a
    a_oudste_start = a_oudste.periode_start
    b_nieuwste_eind = b_nieuwste.periode_eind

    # Aansluiting: verschil van max 1 dag tussen einde B en begin A
    verschil = (a_oudste_start - b_nieuwste_eind).days
    return verschil <= 2  # 1 dag verschil = aansluitend (bijv. 30-nov → 01-dec)


def _hebben_overlap_in_periode(items_a: list[LoonItem], items_b: list[LoonItem],
                                meest_recente_periode: date, vorige_periode: date) -> bool:
    """Controleer of twee contracten tegelijkertijd actief zijn in de MRL en vorige periode."""
    for li_a in items_a:
        for li_b in items_b:
            # Overlap: beide hebben een loonitem in dezelfde periode
            if (li_a.periode_start == li_b.periode_start and
                    li_a.periode_eind == li_b.periode_eind):
                return True
    return False


def _mag_samenvoegen(blok_a: ContractBlok, blok_b: ContractBlok) -> bool:
    """Controleer of twee blokken samengevoegd mogen worden (§5.5.2).

    Criteria:
    1. Datumreeksen sluiten aan (geen gat)
    2. Geen overlap in MRL en vorige periode
    3. Zelfde betaaltermijn voor de aansluitende periodes
    """
    if not blok_a.loon_items or not blok_b.loon_items:
        return False

    # blok_a is recenter, blok_b is ouder
    return _periodes_sluiten_aan(blok_a.loon_items, blok_b.loon_items)


def _groepeer_samenvoegbaar(
    blokken: list[ContractBlok],
) -> list[list[ContractBlok]]:
    """Groepeer blokken die samengevoegd mogen worden.

    Blokken die niet aansluiten worden als aparte groepen behandeld.
    Input: blokken gesorteerd op meest recente loonitem (nieuwste eerst).
    """
    if len(blokken) <= 1:
        return [blokken]

    groepen: list[list[ContractBlok]] = [[blokken[0]]]

    for blok in blokken[1:]:
        # Probeer bij een bestaande groep te voegen
        toegevoegd = False
        for groep in groepen:
            # Check of dit blok aansluit op het oudste blok in de groep
            oudste_in_groep = min(
                groep,
                key=lambda b: min(li.periode_start for li in b.loon_items),
            )
            if _mag_samenvoegen(oudste_in_groep, blok):
                groep.append(blok)
                toegevoegd = True
                break

        if not toegevoegd:
            groepen.append([blok])

    return groepen


def _filter_atypische_periodes(items: list[LoonItem]) -> list[LoonItem]:
    """Appendix 7: Verwijder periodes met atypische lengte.

    Geldige periodes:
    - Maandelijks: 28-31 dagen (kalendermaand)
    - Vierwekelijks: 28 dagen
    - Periodes > 35 dagen of < 7 dagen worden als atypisch beschouwd
      (jaarlijks, halfjaarlijks, of foutief)
    """
    return [li for li in items if 7 <= li.dagen <= 35]


def samenvoeg_contracten(blokken: list[ContractBlok]) -> list[SamengevoegdContract]:
    """Voeg contractblokken samen volgens de IBL rekenregels.

    Regels:
    - Blokken zonder contractvorm worden genegeerd (conform rekenregels)
    - Blokken bij dezelfde werkgever (zelfde loonheffingennummer) worden
      samengevoegd als ze aansluiten, geen overlap hebben in MRL periode,
      en dezelfde betaaltermijn hebben
    - De contractvorm van het meest recente blok bepaalt het type
    """
    # Stap 1: Filter blokken zonder contractvorm
    geldige_blokken = [b for b in blokken if b.heeft_contractvorm]

    # Stap 2: Groepeer per werkgever (naam + loonheffingennummer, Appendix 1)
    per_werkgever: dict[tuple[str, str], list[ContractBlok]] = defaultdict(list)
    for blok in geldige_blokken:
        key = (blok.werkgever_naam, blok.loonheffingennummer)
        per_werkgever[key].append(blok)

    resultaten = []

    for (wg_naam, lhn), wg_blokken in per_werkgever.items():
        # Sorteer blokken op meest recente loonitem (nieuwste eerst)
        wg_blokken.sort(
            key=lambda b: max(li.periode_eind for li in b.loon_items),
            reverse=True
        )

        # Probeer blokken samen te voegen (§5.5.2)
        # Criteria: aaneensluitend, geen overlap in MRL, zelfde betaaltermijn
        samenvoeg_groepen = _groepeer_samenvoegbaar(wg_blokken)

        for groep in samenvoeg_groepen:
            samengevoegde_items: list[LoonItem] = []
            meest_recente_contractvorm = groep[0].contractvorm

            for blok in groep:
                samengevoegde_items.extend(deepcopy(blok.loon_items))

            # Verwijder duplicaten (zelfde periode)
            unieke_items: dict[tuple, LoonItem] = {}
            for li in samengevoegde_items:
                key = (li.periode_start, li.periode_eind)
                if key not in unieke_items:
                    unieke_items[key] = li

            alle_items = sorted(
                unieke_items.values(),
                key=lambda li: li.periode_eind, reverse=True,
            )

            # Appendix 7: Filter atypische periodes
            alle_items = _filter_atypische_periodes(alle_items)
            if not alle_items:
                continue

            # Bepaal betaaltermijn
            betaaltermijn = bepaal_betaaltermijn(alle_items)

            # Bepaal jaren loonhistorie
            if alle_items:
                nieuwste = max(li.periode_eind for li in alle_items)
                oudste = min(li.periode_start for li in alle_items)
                jaren = (nieuwste - oudste).days / 365.25
            else:
                jaren = 0

            # Bepaal contractvorm
            contractvorm = bepaal_contractvorm(meest_recente_contractvorm, int(jaren))

            resultaten.append(SamengevoegdContract(
                werkgever_naam=groep[0].werkgever_naam,
                loonheffingennummer=lhn,
                contractvorm_raw=meest_recente_contractvorm or "",
                contractvorm=contractvorm,
                betaaltermijn=betaaltermijn,
                loon_items=alle_items,
                is_uitkering_uwv=groep[0].is_uitkering_uwv,
            ))

    return resultaten


def pas_verlofregel_toe(contract: SamengevoegdContract) -> SamengevoegdContract:
    """Pas de verlofregel toe: verwijder verlofperiodes (0 uren) onder voorwaarden.

    Voorwaarden:
    - Alleen bij Vast Contract
    - Geen combinatie van betaaltermijnen
    - Verlofperiode niet in meest recente 3 periodes
    - Maximaal 6 aaneengesloten periodes
    - Exact zelfde uren vóór en ná de verlofperiode
    """
    if contract.contractvorm != Contractvorm.VAST:
        return contract

    items = contract.loon_items_gesorteerd()  # Meest recent eerst
    if len(items) < 5:  # Minimaal nodig om verlof te detecteren
        return contract

    # Zoek verlofperiodes (0 uren) buiten de eerste 3 periodes
    verlof_indices = []
    for idx in range(3, len(items)):
        if items[idx].aantal_uur == Decimal("0"):
            verlof_indices.append(idx)

    if not verlof_indices:
        return contract

    # Vind aaneengesloten groepen van verlofperiodes
    groepen = []
    huidige_groep = [verlof_indices[0]]
    for idx in verlof_indices[1:]:
        if idx == huidige_groep[-1] + 1:
            huidige_groep.append(idx)
        else:
            groepen.append(huidige_groep)
            huidige_groep = [idx]
    groepen.append(huidige_groep)

    # Alleen meest recente verlofperiode toepassen
    if not groepen:
        return contract

    groep = groepen[0]  # Meest recente groep (items zijn aflopend gesorteerd)

    # Controleer maximaal 6 periodes
    if len(groep) > 6:
        return contract

    # Controleer uren vóór en ná
    idx_voor = groep[0] - 1  # Periode vóór verlof (recenter)
    idx_na = groep[-1] + 1  # Periode ná verlof (ouder)

    if idx_voor < 0 or idx_na >= len(items):
        return contract

    if items[idx_voor].aantal_uur != items[idx_na].aantal_uur:
        return contract

    # Verlofregel toepassen: verwijder verlofperiodes
    nieuwe_items = [li for idx, li in enumerate(items) if idx not in groep]

    result = deepcopy(contract)
    result.loon_items = nieuwe_items
    return result
