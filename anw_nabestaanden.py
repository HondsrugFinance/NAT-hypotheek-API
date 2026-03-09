"""
ANW Nabestaanden Calculator

Berekent bruto ANW-uitkering en totaal inkomen van de achterblijvende partner
na overlijden. Gebruikt voor het overlijdensrisico-scenario in het adviesrapport.

Twee periodes:
- Periode A: vóór AOW-leeftijd → mogelijk ANW + eigen inkomen + nabestaandenpensioen
- Periode B: vanaf AOW-leeftijd → AOW + eigen inkomen + nabestaandenpensioen (ANW stopt)

ANW-bedragen en regels worden geladen uit config/anw.json.
Halfjaarlijks bijwerken (1 jan + 1 jul).

Bronnen:
- SVB ANW voorwaarden en bedragen
- SVB ANW inkomsten en korting
- Rijksoverheid ANW
"""

import os
import json
from datetime import date
from dateutil.relativedelta import relativedelta

from aow_calculator import bereken_aow_datum

# Config laden
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, 'config', 'anw.json'), 'r', encoding='utf-8') as f:
    ANW_CONFIG = json.load(f)

ANW_RULES = ANW_CONFIG['anw']
AOW_BEDRAGEN = ANW_CONFIG['aow_maandbedragen']


def bereken_nabestaanden_inkomen(
    geboortedatum_nabestaande: date,
    peildatum: date = None,
    # ANW-recht voorwaarden
    heeft_kind_onder_18: bool = False,
    geboortedatum_jongste_kind: date = None,
    ao_percentage: float = 0,
    woonsituatie: str = "alone",
    overledene_was_anw_verzekerd: bool = True,
    # Inkomsten nabestaande (bruto per maand)
    inkomen_loondienst_maand: float = 0,
    inkomen_zelfstandig_maand: float = 0,
    nabestaandenpensioen_maand: float = 0,
    lijfrente_van_partner_maand: float = 0,
    buitenlands_nabestaanden_uitkering_maand: float = 0,
    overig_partial_offset_maand: float = 0,
    overig_full_offset_maand: float = 0,
    # AOW
    opbouwpercentage_aow: float = 1.0,
) -> dict:
    """
    Bereken bruto inkomen achterblijvende partner na overlijden.

    Args:
        geboortedatum_nabestaande: Geboortedatum overlevende partner
        peildatum: Berekeningsdatum (default: vandaag)

        -- ANW voorwaarden --
        heeft_kind_onder_18: Thuiswonend kind onder 18
        geboortedatum_jongste_kind: Voor bepaling einddatum ANW
        ao_percentage: Arbeidsongeschiktheidspercentage (0-100)
        woonsituatie: "alone" | "cost_sharer" | "joint_household"
        overledene_was_anw_verzekerd: Was de overledene ANW-verzekerd?

        -- Inkomsten (bruto per maand) --
        inkomen_loondienst_maand: Loon uit dienstverband
        inkomen_zelfstandig_maand: Winst uit onderneming
        nabestaandenpensioen_maand: Pensioen van pensioenfonds (kort ANW NIET)
        lijfrente_van_partner_maand: Lijfrente van overleden partner (kort ANW NIET)
        buitenlands_nabestaanden_uitkering_maand: Wettelijke nabestaandenuitkering
            uit ander land (kort ANW VOLLEDIG)
        overig_partial_offset_maand: Overig inkomen met gedeeltelijke korting
        overig_full_offset_maand: Overig inkomen met volledige korting

        -- AOW --
        opbouwpercentage_aow: Fractie AOW-opbouw (0-1, default volledig)

    Returns:
        dict met:
        - anw_eligible: bool
        - anw_eligible_reason: str
        - anw_bruto_maand: float
        - anw_bruto_jaar: float
        - anw_einddatum: str (ISO) of None
        - aow_datum: str (ISO)
        - heeft_aow_bereikt: bool
        - aow_bruto_maand: float
        - aow_bruto_jaar: float
        - totaal_bruto_maand: float
        - totaal_bruto_jaar: float
        - inkomen_details: dict (uitsplitsing)
        - review_flags: list[str]
    """
    if peildatum is None:
        peildatum = date.today()

    aow_datum = bereken_aow_datum(geboortedatum_nabestaande)
    heeft_aow_bereikt = peildatum >= aow_datum
    review_flags = []

    # --- ANW eligibility ---
    anw_eligible, anw_reason = _bepaal_anw_recht(
        heeft_aow_bereikt=heeft_aow_bereikt,
        overledene_verzekerd=overledene_was_anw_verzekerd,
        heeft_kind_onder_18=heeft_kind_onder_18,
        geboortedatum_jongste_kind=geboortedatum_jongste_kind,
        peildatum=peildatum,
        ao_percentage=ao_percentage,
        woonsituatie=woonsituatie,
    )

    # --- ANW berekening ---
    anw_bruto_maand = 0.0
    if anw_eligible:
        anw_bruto_maand = _bereken_anw_bruto(
            woonsituatie=woonsituatie,
            inkomen_loondienst_maand=inkomen_loondienst_maand,
            inkomen_zelfstandig_maand=inkomen_zelfstandig_maand,
            overig_partial_offset_maand=overig_partial_offset_maand,
            buitenlands_uitkering_maand=buitenlands_nabestaanden_uitkering_maand,
            overig_full_offset_maand=overig_full_offset_maand,
        )

    # --- ANW einddatum ---
    anw_einddatum = _bepaal_anw_einddatum(
        anw_eligible=anw_eligible,
        aow_datum=aow_datum,
        geboortedatum_jongste_kind=geboortedatum_jongste_kind,
        ao_percentage=ao_percentage,
    )

    # --- AOW berekening ---
    aow_bruto_maand = 0.0
    if heeft_aow_bereikt:
        aow_bruto_maand = _bereken_aow_bruto(woonsituatie, opbouwpercentage_aow)

    # --- Totaal bruto ---
    # Nabestaandenpensioen en lijfrente van partner korten ANW NIET
    # maar tellen WEL mee voor totaal inkomen
    totaal_bruto_maand = (
        inkomen_loondienst_maand
        + inkomen_zelfstandig_maand
        + nabestaandenpensioen_maand
        + lijfrente_van_partner_maand
        + buitenlands_nabestaanden_uitkering_maand
        + overig_partial_offset_maand
        + overig_full_offset_maand
        + anw_bruto_maand
        + aow_bruto_maand
    )

    # --- Review flags ---
    if buitenlands_nabestaanden_uitkering_maand > 0:
        review_flags.append("buitenlandse_nabestaandenuitkering_handmatig_beoordelen")

    if woonsituatie in ("commercial_relation", "care_exception"):
        review_flags.append("woonsituatie_handmatig_beoordelen")

    if opbouwpercentage_aow < 1.0:
        review_flags.append("onvolledige_aow_opbouw")

    return {
        "anw_eligible": anw_eligible,
        "anw_eligible_reason": anw_reason,
        "anw_bruto_maand": round(anw_bruto_maand, 2),
        "anw_bruto_jaar": round(anw_bruto_maand * 12, 2),
        "anw_einddatum": anw_einddatum.isoformat() if anw_einddatum else None,
        "aow_datum": aow_datum.isoformat(),
        "heeft_aow_bereikt": heeft_aow_bereikt,
        "aow_bruto_maand": round(aow_bruto_maand, 2),
        "aow_bruto_jaar": round(aow_bruto_maand * 12, 2),
        "totaal_bruto_maand": round(totaal_bruto_maand, 2),
        "totaal_bruto_jaar": round(totaal_bruto_maand * 12, 2),
        "inkomen_details": {
            "loondienst_maand": inkomen_loondienst_maand,
            "zelfstandig_maand": inkomen_zelfstandig_maand,
            "nabestaandenpensioen_maand": nabestaandenpensioen_maand,
            "lijfrente_partner_maand": lijfrente_van_partner_maand,
            "anw_maand": round(anw_bruto_maand, 2),
            "aow_maand": round(aow_bruto_maand, 2),
        },
        "review_flags": review_flags,
    }


def _bepaal_anw_recht(
    heeft_aow_bereikt: bool,
    overledene_verzekerd: bool,
    heeft_kind_onder_18: bool,
    geboortedatum_jongste_kind: date,
    peildatum: date,
    ao_percentage: float,
    woonsituatie: str,
) -> tuple[bool, str]:
    """Bepaal of de nabestaande recht heeft op ANW."""

    if not overledene_verzekerd:
        return False, "Overledene was niet ANW-verzekerd"

    if heeft_aow_bereikt:
        return False, "Nabestaande heeft AOW-leeftijd bereikt"

    if woonsituatie == "joint_household":
        return False, "Gezamenlijke huishouding — geen ANW-recht"

    # Check kind onder 18
    kind_onder_18_op_peildatum = False
    if heeft_kind_onder_18 and geboortedatum_jongste_kind:
        leeftijd_kind = relativedelta(peildatum, geboortedatum_jongste_kind)
        kind_onder_18_op_peildatum = leeftijd_kind.years < 18
    elif heeft_kind_onder_18:
        # Geen geboortedatum, neem aan dat het klopt
        kind_onder_18_op_peildatum = True

    if kind_onder_18_op_peildatum:
        return True, "Thuiswonend kind onder 18 jaar"

    if ao_percentage >= ANW_RULES['minimum_ao_percentage']:
        return True, f"Arbeidsongeschikt >= {ANW_RULES['minimum_ao_percentage']}%"

    return False, "Geen kind onder 18 en niet >= 45% arbeidsongeschikt"


def _bereken_anw_bruto(
    woonsituatie: str,
    inkomen_loondienst_maand: float,
    inkomen_zelfstandig_maand: float,
    overig_partial_offset_maand: float,
    buitenlands_uitkering_maand: float,
    overig_full_offset_maand: float,
) -> float:
    """
    Bereken bruto ANW na inkomenskorting.

    Inkomen categorieën:
    - Gedeeltelijke korting: loondienst, zelfstandig, overig partial
      → eerste vrijlating vrij, daarboven 2/3 korting
    - Volledige korting: buitenlandse uitkering, overig full
      → volledig in mindering
    - Geen korting: nabestaandenpensioen, lijfrente partner
      → niet meegerekend (aangeroepen buiten deze functie)
    """
    # Basisbedrag
    if woonsituatie == "cost_sharer":
        base = ANW_RULES['kostendeler_bruto_maand'] + ANW_RULES['kostendeler_vakantiegeld_maand']
    else:
        base = ANW_RULES['bruto_maandbedrag'] + ANW_RULES['vakantiegeld_maand']

    # Volledige korting
    full_offset = buitenlands_uitkering_maand + overig_full_offset_maand

    # Gedeeltelijke korting
    partial_income = (
        inkomen_loondienst_maand
        + inkomen_zelfstandig_maand
        + overig_partial_offset_maand
    )

    # Als partial income > nihil-grens → geen ANW
    if partial_income > ANW_RULES['inkomensgrens_nihil_maand']:
        return 0.0

    # Vrijlating, daarboven 2/3 korting
    excess = max(0, partial_income - ANW_RULES['vrijlating_gedeeltelijke_korting_maand'])
    partial_deduction = ANW_RULES['kortingsfractie'] * excess

    anw = max(0, base - full_offset - partial_deduction)
    return round(anw, 2)


def _bepaal_anw_einddatum(
    anw_eligible: bool,
    aow_datum: date,
    geboortedatum_jongste_kind: date,
    ao_percentage: float,
) -> date | None:
    """
    Bepaal wanneer de ANW stopt.

    ANW stopt bij het eerste van:
    - AOW-leeftijd nabestaande
    - Jongste kind wordt 18 (als dat de enige grond is)
    """
    if not anw_eligible:
        return None

    einddatums = [aow_datum]

    if geboortedatum_jongste_kind:
        kind_18 = geboortedatum_jongste_kind + relativedelta(years=18)
        einddatums.append(kind_18)

    # Bij AO is einddatum = AOW (tenzij AO verbetert, maar dat modelleren we niet)
    return min(einddatums)


def _bereken_aow_bruto(woonsituatie: str, opbouwpercentage: float) -> float:
    """Bereken bruto AOW per maand (incl. vakantiegeld)."""
    if woonsituatie == "alone":
        bedrag = (AOW_BEDRAGEN['alleenstaand_bruto_maand']
                  + AOW_BEDRAGEN['alleenstaand_vakantiegeld_maand'])
    else:
        bedrag = (AOW_BEDRAGEN['samenwonend_bruto_maand_pp']
                  + AOW_BEDRAGEN['samenwonend_vakantiegeld_maand_pp'])

    return round(bedrag * opbouwpercentage, 2)


def bereken_nabestaanden_jaarbedrag(
    geboortedatum_nabestaande: date,
    peildatum: date = None,
    heeft_kind_onder_18: bool = False,
    geboortedatum_jongste_kind: date = None,
    ao_percentage: float = 0,
    woonsituatie: str = "alone",
    inkomen_loondienst_maand: float = 0,
    nabestaandenpensioen_maand: float = 0,
) -> float:
    """
    Vereenvoudigde functie: geeft totaal bruto jaarbedrag terug.

    Handig voor directe integratie in risk_scenarios.py.
    Gaat uit van standaard situatie (overledene verzekerd, geen buitenland).
    """
    result = bereken_nabestaanden_inkomen(
        geboortedatum_nabestaande=geboortedatum_nabestaande,
        peildatum=peildatum,
        heeft_kind_onder_18=heeft_kind_onder_18,
        geboortedatum_jongste_kind=geboortedatum_jongste_kind,
        ao_percentage=ao_percentage,
        woonsituatie=woonsituatie,
        inkomen_loondienst_maand=inkomen_loondienst_maand,
        nabestaandenpensioen_maand=nabestaandenpensioen_maand,
    )
    return result["totaal_bruto_jaar"]
