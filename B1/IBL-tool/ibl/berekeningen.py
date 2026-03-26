"""Berekeningsformules A/B/C/D conform §4 IBL Rekenregels v8.1.1."""

import calendar
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from typing import Optional

from .models import (
    SamengevoegdContract, ContractBlok, Betaaltermijn, BerekeningType,
    Tussenresultaat, LoonItem,
    GRENSWAARDE_URENPERCENTAGE,
    UWV_UITKERING_LOONHEFFINGENNUMMERS,
    jaar_perioden, perioden_voor,
)
from .pieken import analyseer_pieken
from .koppeltabel import (
    heeft_gemixte_betaaltermijnen,
    reken_contract_om_naar_mrl_betaaltermijn,
    reken_items_om,
)

ZERO = Decimal("0")
HONDERD = Decimal("100")


# ---------------------------------------------------------------------------
# Uren- en Parttimepercentage (§3.2 en §5.2)
# ---------------------------------------------------------------------------

def _bepaal_pt_percentage(
    items: list[LoonItem],
    betaaltermijn: Betaaltermijn,
    tussenresultaat: Tussenresultaat,
) -> Decimal:
    """Bepaal parttimepercentage, inclusief tussenresultaat registratie."""
    jp = jaar_perioden(betaaltermijn)

    u3 = sum(items[i].aantal_uur for i in range(min(3, len(items))))
    ujr = sum(items[i].aantal_uur for i in range(min(jp, len(items))))

    tussenresultaat.u3 = u3
    tussenresultaat.ujr = ujr

    if ujr == ZERO:
        tussenresultaat.urenpercentage = ZERO
        return ZERO

    urenpercentage = (u3 / 3) / (ujr / jp) * HONDERD
    tussenresultaat.urenpercentage = urenpercentage

    if urenpercentage >= GRENSWAARDE_URENPERCENTAGE:
        tussenresultaat.parttimepercentage = HONDERD
        return HONDERD

    # Bereken parttimepercentage
    upt3 = min(items[i].aantal_uur for i in range(min(3, len(items))))
    start_idx = 3
    end_idx = min(3 + jp, len(items))
    uptjr_periodes = end_idx - start_idx
    if uptjr_periodes > 0:
        uptjr = sum(items[i].aantal_uur for i in range(start_idx, end_idx)) / uptjr_periodes
    else:
        uptjr = ZERO

    tussenresultaat.upt3 = upt3
    tussenresultaat.uptjr = uptjr

    if uptjr == ZERO:
        tussenresultaat.parttimepercentage = ZERO
        return ZERO

    pt = min(upt3 / uptjr * HONDERD, HONDERD)
    tussenresultaat.parttimepercentage = pt
    return pt


# ---------------------------------------------------------------------------
# A-Berekening  (§4.1)
# ---------------------------------------------------------------------------

def bereken_a(
    contract: SamengevoegdContract,
    pensioen_maand: Decimal,
) -> tuple[Decimal, BerekeningType, Tussenresultaat]:
    """A-Berekening: Vast contract, ≥ 2 jaar loonhistorie, bestendig.

    I = I3 + I9 × PT%
    Z = max(∑ netto_bijtelling 12 periodes, 0)
    Toetsinkomen = max(I - Z, 0) + pensioen × jp
    """
    items_origineel = contract.loon_items_gesorteerd()
    tr = Tussenresultaat()

    # PT% op originele items (§5.6.4: uitzondering, geen omrekening)
    bt_origineel = contract.betaaltermijn
    pt = _bepaal_pt_percentage(items_origineel, bt_origineel, tr)

    # Omrekening bij gemixte betaaltermijnen (§5.6.5)
    if heeft_gemixte_betaaltermijnen(items_origineel):
        items, bt = reken_contract_om_naar_mrl_betaaltermijn(items_origineel)
    else:
        items = items_origineel
        bt = bt_origineel

    jp = jaar_perioden(bt)

    # Piekanalyse (alleen ENIP voor A)
    sv_gecorrigeerd, piek_info = analyseer_pieken(items, BerekeningType.A, bt)
    tr.gemiddeld_jaarinkomen = piek_info.get("gji")

    # I3
    i3 = sum(sv_gecorrigeerd[i] for i in range(min(3, len(sv_gecorrigeerd))))
    tr.i3 = i3

    # I9
    i9_end = perioden_voor("12", bt)
    i9 = sum(sv_gecorrigeerd[i] for i in range(3, min(i9_end, len(sv_gecorrigeerd))))
    tr.i9 = i9

    # I
    inkomen = i3 + i9 * pt / HONDERD
    tr.i_jr = inkomen

    # Z (Auto van de zaak)
    z_items = items[:min(jp, len(items))]
    z = sum(li.netto_bijtelling for li in z_items)
    z = max(z, ZERO)
    tr.z_jr = z

    # Toetsinkomen
    basis = max(inkomen - z, ZERO)
    pensioen_jaar = pensioen_maand * jp
    tr.eigen_bijdrage_pensioen_maand = pensioen_maand
    tr.eigen_bijdrage_pensioen_jaar = pensioen_jaar

    toetsinkomen = basis + pensioen_jaar
    toetsinkomen = toetsinkomen.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return toetsinkomen, BerekeningType.A, tr


# ---------------------------------------------------------------------------
# B-Berekening  (§4.2)
# ---------------------------------------------------------------------------

def bereken_b(
    contract: SamengevoegdContract,
    pensioen_maand: Decimal,
) -> tuple[Decimal, BerekeningType, Tussenresultaat]:
    """B-Berekening: Vast contract, bestendigheid faalt of < 2 jaar.

    Toetsinkomen = min(I2jr - Z2jr, Ijr - Zjr)
    I2jr = (I3 + I21 × PT%) / 2
    Ijr  = I3 + I9 × PT%
    """
    items_origineel = contract.loon_items_gesorteerd()
    tr = Tussenresultaat()

    # PT% op originele items (§5.6.4: uitzondering, geen omrekening)
    bt_origineel = contract.betaaltermijn
    pt = _bepaal_pt_percentage(items_origineel, bt_origineel, tr)

    # Omrekening bij gemixte betaaltermijnen (§5.6.5)
    if heeft_gemixte_betaaltermijnen(items_origineel):
        items, bt = reken_contract_om_naar_mrl_betaaltermijn(items_origineel)
    else:
        items = items_origineel
        bt = bt_origineel

    jp = jaar_perioden(bt)

    # Piekanalyse (EIP + ENIP)
    sv_gecorrigeerd, piek_info = analyseer_pieken(items, BerekeningType.B, bt)
    tr.gemiddeld_periode_inkomen = piek_info.get("gpi")
    tr.gemiddeld_jaarinkomen = piek_info.get("gji")

    # I3
    i3 = sum(sv_gecorrigeerd[i] for i in range(min(3, len(sv_gecorrigeerd))))
    tr.i3 = i3

    # I9 (periodes 4-12)
    p12 = perioden_voor("12", bt)
    i9 = sum(sv_gecorrigeerd[i] for i in range(3, min(p12, len(sv_gecorrigeerd))))
    tr.i9 = i9

    # I21 (periodes 4-24)
    p24 = perioden_voor("24", bt)
    i21 = sum(sv_gecorrigeerd[i] for i in range(3, min(p24, len(sv_gecorrigeerd))))
    tr.i21 = i21

    # Ijr = I3 + I9 × PT%
    ijr = i3 + i9 * pt / HONDERD
    tr.i_jr = ijr

    # I2jr = (I3 + I21 × PT%) / 2
    i2jr = (i3 + i21 * pt / HONDERD) / 2
    tr.i_2jr = i2jr

    # Z2jr
    z2jr_items = items[:min(p24, len(items))]
    z2jr_som = sum(li.netto_bijtelling for li in z2jr_items)
    z2jr = max(z2jr_som, ZERO) / 2
    tr.z_2jr = z2jr

    # Zjr
    zjr_items = items[:min(p12, len(items))]
    zjr = sum(li.netto_bijtelling for li in zjr_items)
    zjr = max(zjr, ZERO)
    tr.z_jr = zjr

    # Toetsinkomen = min(I2jr - Z2jr, Ijr - Zjr)
    optie_2jr = i2jr - z2jr
    optie_jr = ijr - zjr
    basis = max(min(optie_2jr, optie_jr), ZERO)

    pensioen_jaar = pensioen_maand * jp
    tr.eigen_bijdrage_pensioen_maand = pensioen_maand
    tr.eigen_bijdrage_pensioen_jaar = pensioen_jaar

    toetsinkomen = basis + pensioen_jaar
    toetsinkomen = toetsinkomen.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return toetsinkomen, BerekeningType.B, tr


# ---------------------------------------------------------------------------
# D-Berekening  (§4.4)
# ---------------------------------------------------------------------------

def bereken_d(
    contract: SamengevoegdContract,
    pensioen_maand: Decimal,
) -> tuple[Decimal, BerekeningType, Tussenresultaat]:
    """D-Berekening: Niet-vast contract, < 3 jaar loonhistorie.

    I = laagste SV Loon van 4 recentste periodes × jp
    Z = netto bijtelling meest recente periode × jp
    """
    bt = contract.betaaltermijn
    jp = jaar_perioden(bt)
    items = contract.loon_items_gesorteerd()
    tr = Tussenresultaat()

    if len(items) < 4:
        # Te weinig periodes
        return ZERO, BerekeningType.D, tr

    # Laagste SV Loon van de 4 meest recente periodes
    laagste = min(items[i].sv_loon for i in range(4))
    inkomen = laagste * jp

    # Z = netto bijtelling meest recente × jp
    z = items[0].netto_bijtelling * jp
    z = max(z, ZERO)
    tr.z_jr = z

    basis = max(inkomen - z, ZERO)
    pensioen_jaar = pensioen_maand * jp
    tr.eigen_bijdrage_pensioen_maand = pensioen_maand
    tr.eigen_bijdrage_pensioen_jaar = pensioen_jaar

    toetsinkomen = basis + pensioen_jaar
    toetsinkomen = toetsinkomen.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return toetsinkomen, BerekeningType.D, tr


# ---------------------------------------------------------------------------
# C-Berekening  (§4.3) - Multi-contract
# ---------------------------------------------------------------------------

def _genereer_maandperiodes(eind_datum: date, aantal: int) -> list[tuple[date, date]]:
    """Genereer kalendermaandperiodes, meest recent eerst."""
    periodes = []
    jaar = eind_datum.year
    maand = eind_datum.month
    for _ in range(aantal):
        start = date(jaar, maand, 1)
        eind = date(jaar, maand, calendar.monthrange(jaar, maand)[1])
        periodes.append((start, eind))
        maand -= 1
        if maand < 1:
            maand = 12
            jaar -= 1
    return periodes


@dataclass
class _CPeriode:
    """Geaggregeerde periode-data voor C-berekening."""
    periode_start: date
    periode_eind: date
    sv_loon_totaal: Decimal = Decimal("0")
    sv_loon_uwv: Decimal = Decimal("0")
    uren_excl_uitkering: Decimal = Decimal("0")
    waarde_privegebruik: Decimal = Decimal("0")
    eigen_bijdrage: Decimal = Decimal("0")

    @property
    def uitkeringspercentage(self) -> Decimal:
        if self.sv_loon_totaal <= ZERO:
            return ZERO
        return self.sv_loon_uwv / self.sv_loon_totaal

    @property
    def netto_bijtelling(self) -> Decimal:
        return self.waarde_privegebruik - self.eigen_bijdrage

    def als_loon_item(self) -> LoonItem:
        """Converteer naar LoonItem voor pieken-analyse."""
        return LoonItem(
            periode_start=self.periode_start,
            periode_eind=self.periode_eind,
            aantal_uur=self.uren_excl_uitkering,
            sv_loon=self.sv_loon_totaal,
        )


def _aggregeer_periodes(
    blokken: list[ContractBlok],
    amrl_eind: date,
    aantal_periodes: int,
) -> list[_CPeriode]:
    """Aggregeer loon items per kalendermaand over alle blokken.

    Returns: lijst van _CPeriode, meest recent eerst.
    """
    periodes = _genereer_maandperiodes(amrl_eind, aantal_periodes)
    resultaat = []

    for p_start, p_eind in periodes:
        cp = _CPeriode(periode_start=p_start, periode_eind=p_eind)

        for blok in blokken:
            is_uwv = blok.loonheffingennummer in UWV_UITKERING_LOONHEFFINGENNUMMERS
            for li in blok.loon_items:
                if li.periode_start == p_start and li.periode_eind == p_eind:
                    cp.sv_loon_totaal += li.sv_loon
                    if is_uwv:
                        cp.sv_loon_uwv += li.sv_loon
                    else:
                        cp.uren_excl_uitkering += li.aantal_uur
                    if li.waarde_privegebruik_auto:
                        cp.waarde_privegebruik += li.waarde_privegebruik_auto
                    if li.eigen_bijdrage_auto:
                        cp.eigen_bijdrage += li.eigen_bijdrage_auto

        resultaat.append(cp)

    return resultaat


def _converteer_blokken_naar_doel_bt(
    blokken: list[ContractBlok],
    doel_betaaltermijn: Betaaltermijn,
) -> list[ContractBlok]:
    """Converteer vierwekelijkse items in blokken naar doelbetaaltermijn (§5.6.6).

    Blokken die al de doelbetaaltermijn hebben worden ongewijzigd doorgegeven.
    Blokken met vierwekelijkse items worden gekopieerd met omgerekende items.
    """
    from copy import deepcopy
    from .koppeltabel import detecteer_betaaltermijn as _detect_bt

    resultaat = []
    for blok in blokken:
        # Check of dit blok items heeft met andere betaaltermijn
        heeft_andere = any(
            _detect_bt(li) != doel_betaaltermijn for li in blok.loon_items
        )
        if not heeft_andere:
            resultaat.append(blok)
            continue

        # Omrekening nodig: converteer items
        omgerekende_items = reken_items_om(blok.loon_items, doel_betaaltermijn)
        nieuw_blok = deepcopy(blok)
        nieuw_blok.loon_items = omgerekende_items
        resultaat.append(nieuw_blok)

    return resultaat


def bereken_c(
    alle_blokken: list[ContractBlok],
    amrl_eind: date,
    pensioen_maand: Decimal,
    betaaltermijn: Betaaltermijn = Betaaltermijn.MAANDELIJKS,
) -> tuple[Decimal, BerekeningType, Tussenresultaat]:
    """C-Berekening: Niet-vast contract, ≥ 3 jaar loonhistorie (multi-contract).

    Toetsinkomen = min(I3jr - Z3jr, Ijr - Zjr)
    I3jr = (I3i + I33i × PT%) / 3
    Ijr  = I3e + I9e × PT%

    Args:
        alle_blokken: Alle contractblokken die meedoen (excl. werkgever-uitkeringen,
                       incl. UWV-uitkeringen en reguliere contracten).
        amrl_eind: Einddatum van het Algemeen Meest Recent Loonitem.
        pensioen_maand: Eigen bijdrage pensioen per maand.
        betaaltermijn: Betaaltermijn (standaard maandelijks voor C).
    """
    # §5.6.6: Bij gemixte betaaltermijnen, vierwekelijkse items omrekenen
    # naar maandelijks (tenzij ALLE MRLs vierwekelijks zijn).
    werk_blokken = _converteer_blokken_naar_doel_bt(alle_blokken, betaaltermijn)

    jp = jaar_perioden(betaaltermijn)
    p12 = perioden_voor("12", betaaltermijn)
    p36 = perioden_voor("36", betaaltermijn)
    tr = Tussenresultaat()

    # Stap 1-4: Aggregeer PeriodeInkomen per periode
    c_periodes = _aggregeer_periodes(werk_blokken, amrl_eind, p36)

    # Maak virtuele LoonItems voor pieken-analyse
    virtuele_items = [cp.als_loon_item() for cp in c_periodes]

    # PT% op berekeningsniveau (uren excl. uitkeringen)
    pt = _bepaal_pt_percentage(virtuele_items, betaaltermijn, tr)

    # Stap 5-6: Piekanalyse (EIP + ENIP)
    sv_gecorrigeerd, piek_info = analyseer_pieken(virtuele_items, BerekeningType.C, betaaltermijn)
    tr.gemiddeld_periode_inkomen = piek_info.get("gpi")
    tr.gemiddeld_jaarinkomen = piek_info.get("gji")

    # Stap 7: I3i (inclusief UWV uitkeringen)
    i3i = sum(sv_gecorrigeerd[i] for i in range(min(3, len(sv_gecorrigeerd))))
    tr.i3 = i3i

    # Stap 8: I33i (periodes 4-36, inclusief UWV uitkeringen)
    i33i = sum(sv_gecorrigeerd[i] for i in range(3, min(p36, len(sv_gecorrigeerd))))
    tr.i33 = i33i

    # Stap 9: I3jr = (I3i + I33i × PT%) / 3
    i3jr = (i3i + i33i * pt / HONDERD) / 3
    tr.i_3jr = i3jr

    # Stap 10: I3e (exclusief uitkeringen)
    i3e = ZERO
    for i in range(min(3, len(sv_gecorrigeerd))):
        uitk_pct = c_periodes[i].uitkeringspercentage
        i3e += sv_gecorrigeerd[i] * (1 - uitk_pct)

    # Stap 11: I9e (exclusief uitkeringen)
    i9e = ZERO
    for i in range(3, min(p12, len(sv_gecorrigeerd))):
        uitk_pct = c_periodes[i].uitkeringspercentage
        i9e += sv_gecorrigeerd[i] * (1 - uitk_pct)
    tr.i9 = i9e

    # Stap 12: Ijr = I3e + I9e × PT%
    ijr = i3e + i9e * pt / HONDERD
    tr.i_jr = ijr

    # Auto van de zaak
    # Z3jr
    z3jr_som = sum(c_periodes[i].netto_bijtelling for i in range(min(p36, len(c_periodes))))
    z3jr = max(z3jr_som, ZERO) / 3
    tr.z_3jr = z3jr

    # Zjr
    zjr_som = sum(c_periodes[i].netto_bijtelling for i in range(min(p12, len(c_periodes))))
    zjr = max(zjr_som, ZERO)
    tr.z_jr = zjr

    # Stap 13: Toetsinkomen = min(I3jr - Z3jr, Ijr - Zjr)
    optie_3jr = i3jr - z3jr
    optie_jr = ijr - zjr
    basis = max(min(optie_3jr, optie_jr), ZERO)

    pensioen_jaar = pensioen_maand * jp
    tr.eigen_bijdrage_pensioen_maand = pensioen_maand
    tr.eigen_bijdrage_pensioen_jaar = pensioen_jaar

    toetsinkomen = basis + pensioen_jaar
    toetsinkomen = toetsinkomen.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return toetsinkomen, BerekeningType.C, tr
