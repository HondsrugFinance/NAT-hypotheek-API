"""
Risico Scenario Berekeningen

AOW-scenario's:
- Berekent maximale hypotheek op toekomstige AOW-momenten
- Hypotheekdelen geprojecteerd via loan_projection
- Inkomens volgens opgave (huidig vs AOW-niveau)

Overlijdensscenario's:
- Alleen bij stellen (alleenstaande = "NEE")
- Hypotheek op startdatum (geen projectie)
- Nabestaande wordt alleenstaande
- Inkomen = eigen + nabestaandenpensioen + eventueel ANW

AO-scenario's:
- Per persoon, drie fasen: loondoorbetaling, WGA LGU, WGA loonaanvulling
- Hypotheekdelen geprojecteerd naar moment van elke fase
- Loondienst → WIA-regels, Onderneming/ROZ → direct % reductie
- AOV/woonlastenverzekering telt mee als inkomen

Werkloosheidsscenario's:
- Loondienst → WW-uitkering (70% structureel), daarna 0
- Onderneming/ROZ → valt volledig weg (geen WW)
- Overig → ongewijzigd
- Woonlastenverzekering WW telt mee als inkomen
- Per persoon per WW-jaar + na-WW scenario
- Hypotheek op startdatum (geen projectie — tijdelijk risico)
"""

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from aow_calculator import bereken_aow_datum
from loan_projection import projecteer_hypotheekdelen
from calculator_final import calculate
from anw_nabestaanden import bereken_nabestaanden_inkomen
from wia_calculator import bereken_wia_bruto_jaar, _bereken_lgu_duur
from ww_calculator import bereken_ww_bruto_jaar, bereken_ww_duur


def bereken_aow_scenarios(
    hypotheek_delen: list[dict],
    ingangsdatum_hypotheek: str,
    geboortedatum_aanvrager: str,
    inkomen_aanvrager_huidig: float,
    inkomen_aanvrager_aow: float,
    alleenstaande: str = "JA",
    geboortedatum_partner: str = None,
    inkomen_partner_huidig: float = 0,
    inkomen_partner_aow: float = 0,
    toetsrente: float = 0.05,
    energielabel: str = "Geen (geldig) Label",
    verduurzamings_maatregelen: float = 0,
    limieten_bkr_geregistreerd: float = 0,
    studievoorschot_studielening: float = 0,
    erfpachtcanon_per_jaar: float = 0,
    jaarlast_overige_kredieten: float = 0,
    geadviseerd_hypotheekbedrag: float = 0,
) -> dict:
    """
    Bereken maximale hypotheek op AOW-momenten.

    Args:
        hypotheek_delen: Leningdelen met rente_aftrekbaar_tot
        ingangsdatum_hypotheek: Start hypotheek (YYYY-MM-DD)
        geboortedatum_aanvrager: YYYY-MM-DD
        inkomen_aanvrager_huidig: Huidig bruto jaarinkomen aanvrager
        inkomen_aanvrager_aow: Inkomen aanvrager vanaf AOW-datum
        alleenstaande: "JA" of "NEE"
        geboortedatum_partner: YYYY-MM-DD (alleen bij stel)
        inkomen_partner_huidig: Huidig bruto jaarinkomen partner
        inkomen_partner_aow: Inkomen partner vanaf AOW-datum
        toetsrente: Oorspronkelijke toetsrente (bijv. 0.04664)
        energielabel: Energielabel woning
        verduurzamings_maatregelen: EBV/EBB bedrag
        limieten_bkr_geregistreerd: BKR limieten
        studievoorschot_studielening: Studielening maandbedrag
        erfpachtcanon_per_jaar: Erfpachtcanon per maand (API *12 intern)
        jaarlast_overige_kredieten: Overige kredieten maandlast (API *12 intern)
        geadviseerd_hypotheekbedrag: Geadviseerd bedrag voor tekort-berekening

    Returns:
        dict met:
        - scenarios: lijst van scenario-resultaten
        - geadviseerd_hypotheekbedrag: meegegeven bedrag
    """
    start = date.fromisoformat(ingangsdatum_hypotheek)
    geb_aanvrager = date.fromisoformat(geboortedatum_aanvrager)
    aow_datum_aanvrager = bereken_aow_datum(geb_aanvrager)

    geb_partner = None
    aow_datum_partner = None
    if alleenstaande == "NEE" and geboortedatum_partner:
        geb_partner = date.fromisoformat(geboortedatum_partner)
        aow_datum_partner = bereken_aow_datum(geb_partner)

    scenarios = []

    # --- Scenario: AOW aanvrager ---
    if aow_datum_aanvrager > date.today():
        elapsed = _maanden_verschil(start, aow_datum_aanvrager)
        projected = projecteer_hypotheekdelen(
            hypotheek_delen, elapsed, aow_datum_aanvrager
        )

        # Inkomen op AOW-datum aanvrager
        ink_aanvrager = inkomen_aanvrager_aow
        ink_partner = inkomen_partner_huidig  # partner werkt nog

        # Als partner ook al AOW op dit moment
        if aow_datum_partner and aow_datum_aanvrager >= aow_datum_partner:
            ink_partner = inkomen_partner_aow

        # ontvangt_aow: JA als hoogste verdiener AOW is
        aanvrager_is_aow = True
        partner_is_aow = (aow_datum_partner is not None
                          and aow_datum_aanvrager >= aow_datum_partner)
        ontvangt_aow = _bepaal_ontvangt_aow(
            ink_aanvrager, ink_partner, aanvrager_is_aow, partner_is_aow,
            alleenstaande
        )

        result = _bereken_scenario(
            naam=f"AOW aanvrager ({aow_datum_aanvrager.strftime('%d-%m-%Y')})",
            categorie="aow",
            van_toepassing_op="aanvrager",
            hypotheek_delen=projected,
            inkomen_aanvrager=ink_aanvrager,
            inkomen_partner=ink_partner,
            alleenstaande=alleenstaande,
            ontvangt_aow=ontvangt_aow,
            toetsrente=toetsrente,
            energielabel=energielabel,
            verduurzamings_maatregelen=verduurzamings_maatregelen,
            limieten_bkr=limieten_bkr_geregistreerd,
            studievoorschot=studievoorschot_studielening,
            erfpacht=erfpachtcanon_per_jaar,
            jaarlast=jaarlast_overige_kredieten,
            geadviseerd=geadviseerd_hypotheekbedrag,
            peildatum=aow_datum_aanvrager,
        )
        scenarios.append(result)

    # --- Scenario: AOW partner ---
    if (alleenstaande == "NEE" and aow_datum_partner
            and aow_datum_partner > date.today()
            and aow_datum_partner != aow_datum_aanvrager):
        elapsed = _maanden_verschil(start, aow_datum_partner)
        projected = projecteer_hypotheekdelen(
            hypotheek_delen, elapsed, aow_datum_partner
        )

        # Op AOW-datum partner: aanvrager is sowieso AOW (of niet)
        ink_partner = inkomen_partner_aow
        if aow_datum_partner >= aow_datum_aanvrager:
            ink_aanvrager = inkomen_aanvrager_aow
        else:
            ink_aanvrager = inkomen_aanvrager_huidig

        aanvrager_is_aow = aow_datum_partner >= aow_datum_aanvrager
        partner_is_aow = True
        ontvangt_aow = _bepaal_ontvangt_aow(
            ink_aanvrager, ink_partner, aanvrager_is_aow, partner_is_aow,
            alleenstaande
        )

        result = _bereken_scenario(
            naam=f"AOW partner ({aow_datum_partner.strftime('%d-%m-%Y')})",
            categorie="aow",
            van_toepassing_op="partner",
            hypotheek_delen=projected,
            inkomen_aanvrager=ink_aanvrager,
            inkomen_partner=ink_partner,
            alleenstaande=alleenstaande,
            ontvangt_aow=ontvangt_aow,
            toetsrente=toetsrente,
            energielabel=energielabel,
            verduurzamings_maatregelen=verduurzamings_maatregelen,
            limieten_bkr=limieten_bkr_geregistreerd,
            studievoorschot=studievoorschot_studielening,
            erfpacht=erfpachtcanon_per_jaar,
            jaarlast=jaarlast_overige_kredieten,
            geadviseerd=geadviseerd_hypotheekbedrag,
            peildatum=aow_datum_partner,
        )
        scenarios.append(result)

    return {
        "scenarios": scenarios,
        "geadviseerd_hypotheekbedrag": geadviseerd_hypotheekbedrag,
    }


def _bereken_scenario(
    naam: str,
    categorie: str,
    van_toepassing_op: str,
    hypotheek_delen: list[dict],
    inkomen_aanvrager: float,
    inkomen_partner: float,
    alleenstaande: str,
    ontvangt_aow: str,
    toetsrente: float,
    energielabel: str,
    verduurzamings_maatregelen: float,
    limieten_bkr: float,
    studievoorschot: float,
    erfpacht: float,
    jaarlast: float,
    geadviseerd: float,
    peildatum: date,
) -> dict:
    """Voer NAT berekening uit voor een enkel scenario."""
    inputs = {
        'hoofd_inkomen_aanvrager': inkomen_aanvrager,
        'hoofd_inkomen_partner': inkomen_partner,
        'alleenstaande': alleenstaande,
        'ontvangt_aow': ontvangt_aow,
        'energielabel': energielabel,
        'verduurzamings_maatregelen': verduurzamings_maatregelen,
        'limieten_bkr_geregistreerd': limieten_bkr,
        'studievoorschot_studielening': studievoorschot,
        'erfpachtcanon_per_jaar': erfpacht,
        'jaarlast_overige_kredieten': jaarlast,
        'hypotheek_delen': hypotheek_delen,
        # Oorspronkelijke toetsrente als c_toets_rente meegeven.
        # Na projectie zijn alle RVPs 0 (< 120), dus alle delen
        # gebruiken c_toets_rente → gewogen rente = toetsrente.
        'c_toets_rente': toetsrente,
        'c_actuele_10jr_rente': toetsrente,
    }

    result = calculate(inputs)
    scenario1 = result.get('scenario1')

    if scenario1:
        max_annuitair = scenario1['annuitair']['max_box1']
        max_niet_annuitair = scenario1['niet_annuitair']['max_box1']
        # Gebruik altijd annuitaire toets (GHF-norm)
        max_hypotheek = max_annuitair
    else:
        max_hypotheek = 0

    tekort = max(0, geadviseerd - max_hypotheek) if geadviseerd > 0 else 0
    percentage = round(max_hypotheek / geadviseerd * 100) if geadviseerd > 0 else 0

    debug = result.get('debug', {})

    return {
        "naam": naam,
        "categorie": categorie,
        "van_toepassing_op": van_toepassing_op,
        "peildatum": peildatum.isoformat(),
        "inkomen_aanvrager": inkomen_aanvrager,
        "inkomen_partner": inkomen_partner,
        "ontvangt_aow": ontvangt_aow,
        "max_hypotheek_annuitair": round(scenario1['annuitair']['max_box1'], 2) if scenario1 else 0,
        "max_hypotheek_niet_annuitair": round(scenario1['niet_annuitair']['max_box1'], 2) if scenario1 else 0,
        "toets_inkomen": debug.get('toets_inkomen', 0),
        "toets_rente": debug.get('toets_rente', 0),
        "woonquote": debug.get('woonquote_box1', 0),
        "tekort": round(tekort, 2),
        "percentage_van_geadviseerd": percentage,
        "hypotheek_delen_geprojecteerd": hypotheek_delen,
    }


def _bepaal_ontvangt_aow(
    inkomen_aanvrager: float,
    inkomen_partner: float,
    aanvrager_is_aow: bool,
    partner_is_aow: bool,
    alleenstaande: str,
) -> str:
    """
    Bepaal of AOW-woonquotes gebruikt moeten worden.

    Regel: als de hoogste verdiener AOW-gerechtigd is → JA.
    Bij alleenstaande: alleen aanvrager relevant.
    """
    if alleenstaande == "JA":
        return "JA" if aanvrager_is_aow else "NEE"

    if inkomen_aanvrager >= inkomen_partner:
        return "JA" if aanvrager_is_aow else "NEE"
    else:
        return "JA" if partner_is_aow else "NEE"


def bereken_overlijdens_scenarios(
    hypotheek_delen: list[dict],
    geboortedatum_aanvrager: str,
    inkomen_aanvrager_huidig: float,
    geboortedatum_partner: str,
    inkomen_partner_huidig: float,
    nabestaandenpensioen_bij_overlijden_aanvrager: float = 0,
    nabestaandenpensioen_bij_overlijden_partner: float = 0,
    heeft_kind_onder_18: bool = False,
    geboortedatum_jongste_kind: str = None,
    toetsrente: float = 0.05,
    energielabel: str = "Geen (geldig) Label",
    verduurzamings_maatregelen: float = 0,
    limieten_bkr_geregistreerd: float = 0,
    studievoorschot_studielening: float = 0,
    erfpachtcanon_per_jaar: float = 0,
    jaarlast_overige_kredieten: float = 0,
    geadviseerd_hypotheekbedrag: float = 0,
) -> dict:
    """
    Bereken maximale hypotheek bij overlijden aanvrager of partner.

    Alleen bij stellen. Hypotheek op startdatum (geen projectie).
    Nabestaande wordt alleenstaande, inkomen wijzigt.

    Args:
        hypotheek_delen: Leningdelen op startdatum (origineel)
        geboortedatum_aanvrager/partner: YYYY-MM-DD
        inkomen_aanvrager/partner_huidig: Huidig bruto jaarinkomen
        nabestaandenpensioen_bij_overlijden_aanvrager: Jaarbedrag dat partner
            ontvangt als aanvrager overlijdt (uit pensioenregeling)
        nabestaandenpensioen_bij_overlijden_partner: Jaarbedrag dat aanvrager
            ontvangt als partner overlijdt
        heeft_kind_onder_18: Voor ANW-recht bepaling
        geboortedatum_jongste_kind: YYYY-MM-DD (optioneel)
        (overige parameters: zelfde als bij AOW-scenario's)

    Returns:
        dict met scenarios[] en geadviseerd_hypotheekbedrag
    """
    peildatum = date.today()
    geb_aanvrager = date.fromisoformat(geboortedatum_aanvrager)
    geb_partner = date.fromisoformat(geboortedatum_partner)
    geb_kind = (date.fromisoformat(geboortedatum_jongste_kind)
                if geboortedatum_jongste_kind else None)

    aow_datum_aanvrager = bereken_aow_datum(geb_aanvrager)
    aow_datum_partner = bereken_aow_datum(geb_partner)

    scenarios = []

    # --- Scenario 1: Aanvrager overlijdt → partner is nabestaande ---
    anw_partner = bereken_nabestaanden_inkomen(
        geboortedatum_nabestaande=geb_partner,
        peildatum=peildatum,
        heeft_kind_onder_18=heeft_kind_onder_18,
        geboortedatum_jongste_kind=geb_kind,
        woonsituatie="alone",
        inkomen_loondienst_maand=inkomen_partner_huidig / 12,
        nabestaandenpensioen_maand=nabestaandenpensioen_bij_overlijden_aanvrager / 12,
    )

    # Totaal inkomen partner als nabestaande (jaarbedrag)
    inkomen_partner_na = (
        inkomen_partner_huidig
        + nabestaandenpensioen_bij_overlijden_aanvrager
        + anw_partner['anw_bruto_jaar']
    )

    # Als partner al AOW: voeg AOW-verschil toe (alleenstaand > samenwonend)
    partner_heeft_aow = peildatum >= aow_datum_partner
    ontvangt_aow_1 = "JA" if partner_heeft_aow else "NEE"

    result1 = _bereken_scenario(
        naam="Overlijden aanvrager",
        categorie="overlijden",
        van_toepassing_op="aanvrager",
        hypotheek_delen=hypotheek_delen,
        inkomen_aanvrager=inkomen_partner_na,  # partner wordt "aanvrager"
        inkomen_partner=0,
        alleenstaande="JA",
        ontvangt_aow=ontvangt_aow_1,
        toetsrente=toetsrente,
        energielabel=energielabel,
        verduurzamings_maatregelen=verduurzamings_maatregelen,
        limieten_bkr=limieten_bkr_geregistreerd,
        studievoorschot=studievoorschot_studielening,
        erfpacht=erfpachtcanon_per_jaar,
        jaarlast=jaarlast_overige_kredieten,
        geadviseerd=geadviseerd_hypotheekbedrag,
        peildatum=peildatum,
    )
    result1['anw_details'] = {
        'anw_eligible': anw_partner['anw_eligible'],
        'anw_reason': anw_partner['anw_eligible_reason'],
        'anw_bruto_jaar': anw_partner['anw_bruto_jaar'],
        'anw_einddatum': anw_partner['anw_einddatum'],
        'nabestaandenpensioen_jaar': nabestaandenpensioen_bij_overlijden_aanvrager,
        'eigen_inkomen_jaar': inkomen_partner_huidig,
        'totaal_inkomen_jaar': round(inkomen_partner_na, 2),
    }
    scenarios.append(result1)

    # --- Scenario 2: Partner overlijdt → aanvrager is nabestaande ---
    anw_aanvrager = bereken_nabestaanden_inkomen(
        geboortedatum_nabestaande=geb_aanvrager,
        peildatum=peildatum,
        heeft_kind_onder_18=heeft_kind_onder_18,
        geboortedatum_jongste_kind=geb_kind,
        woonsituatie="alone",
        inkomen_loondienst_maand=inkomen_aanvrager_huidig / 12,
        nabestaandenpensioen_maand=nabestaandenpensioen_bij_overlijden_partner / 12,
    )

    inkomen_aanvrager_na = (
        inkomen_aanvrager_huidig
        + nabestaandenpensioen_bij_overlijden_partner
        + anw_aanvrager['anw_bruto_jaar']
    )

    aanvrager_heeft_aow = peildatum >= aow_datum_aanvrager
    ontvangt_aow_2 = "JA" if aanvrager_heeft_aow else "NEE"

    result2 = _bereken_scenario(
        naam="Overlijden partner",
        categorie="overlijden",
        van_toepassing_op="partner",
        hypotheek_delen=hypotheek_delen,
        inkomen_aanvrager=inkomen_aanvrager_na,
        inkomen_partner=0,
        alleenstaande="JA",
        ontvangt_aow=ontvangt_aow_2,
        toetsrente=toetsrente,
        energielabel=energielabel,
        verduurzamings_maatregelen=verduurzamings_maatregelen,
        limieten_bkr=limieten_bkr_geregistreerd,
        studievoorschot=studievoorschot_studielening,
        erfpacht=erfpachtcanon_per_jaar,
        jaarlast=jaarlast_overige_kredieten,
        geadviseerd=geadviseerd_hypotheekbedrag,
        peildatum=peildatum,
    )
    result2['anw_details'] = {
        'anw_eligible': anw_aanvrager['anw_eligible'],
        'anw_reason': anw_aanvrager['anw_eligible_reason'],
        'anw_bruto_jaar': anw_aanvrager['anw_bruto_jaar'],
        'anw_einddatum': anw_aanvrager['anw_einddatum'],
        'nabestaandenpensioen_jaar': nabestaandenpensioen_bij_overlijden_partner,
        'eigen_inkomen_jaar': inkomen_aanvrager_huidig,
        'totaal_inkomen_jaar': round(inkomen_aanvrager_na, 2),
    }
    scenarios.append(result2)

    return {
        "scenarios": scenarios,
        "geadviseerd_hypotheekbedrag": geadviseerd_hypotheekbedrag,
    }


def bereken_ao_scenarios(
    hypotheek_delen: list[dict],
    ingangsdatum_hypotheek: str,
    geboortedatum_aanvrager: str,
    alleenstaande: str = "JA",
    geboortedatum_partner: str = None,
    # Inkomensverdeling aanvrager (bruto jaarbedragen)
    inkomen_loondienst_aanvrager: float = 0,
    inkomen_onderneming_aanvrager: float = 0,
    inkomen_roz_aanvrager: float = 0,
    inkomen_overig_aanvrager: float = 0,
    # Inkomensverdeling partner
    inkomen_loondienst_partner: float = 0,
    inkomen_onderneming_partner: float = 0,
    inkomen_roz_partner: float = 0,
    inkomen_overig_partner: float = 0,
    # AO parameters
    ao_percentage: float = 50,
    benutting_rvc_percentage: float = 50,
    # Loondoorbetaling
    loondoorbetaling_pct_jaar1_aanvrager: float = 1.0,
    loondoorbetaling_pct_jaar2_aanvrager: float = 0.70,
    loondoorbetaling_pct_jaar1_partner: float = 1.0,
    loondoorbetaling_pct_jaar2_partner: float = 0.70,
    # Verzekeringen (bruto jaarbedragen)
    aov_dekking_bruto_jaar_aanvrager: float = 0,
    aov_dekking_bruto_jaar_partner: float = 0,
    woonlastenverzekering_ao_bruto_jaar: float = 0,
    # Arbeidsverleden (voor LGU-duur)
    arbeidsverleden_jaren_tm_2015: int = 10,
    arbeidsverleden_jaren_vanaf_2016: int = 5,
    # Standaard
    toetsrente: float = 0.05,
    energielabel: str = "Geen (geldig) Label",
    verduurzamings_maatregelen: float = 0,
    limieten_bkr_geregistreerd: float = 0,
    studievoorschot_studielening: float = 0,
    erfpachtcanon_per_jaar: float = 0,
    jaarlast_overige_kredieten: float = 0,
    geadviseerd_hypotheekbedrag: float = 0,
) -> dict:
    """
    Bereken maximale hypotheek bij arbeidsongeschiktheid.

    Per persoon drie fasen (als loondienst > 0):
    1. Loondoorbetaling (jaar 2 rate)
    2. WGA loongerelateerd
    3. WGA loonaanvulling

    Zonder loondienst (alleen onderneming/ROZ): één scenario met
    directe inkomensreductie, geen WIA.

    Inkomens die beïnvloed worden door AO:
    - Loondienst → WIA-regels (wia_calculator.py)
    - Onderneming/ROZ → inkomen × (1 - AO%)
    - Overig (lijfrente, huur, etc.) → ongewijzigd
    - AOV/woonlastenverzekering → komt erbij als extra dekking
    """
    scenarios = []
    start = date.fromisoformat(ingangsdatum_hypotheek)
    today = date.today()
    ao_frac = ao_percentage / 100
    benutting_frac = benutting_rvc_percentage / 100

    # Bouw per-persoon data
    personen = []

    personen.append({
        "wie": "aanvrager",
        "loondienst": inkomen_loondienst_aanvrager,
        "onderneming": inkomen_onderneming_aanvrager,
        "roz": inkomen_roz_aanvrager,
        "overig": inkomen_overig_aanvrager,
        "pct_y2": loondoorbetaling_pct_jaar2_aanvrager,
        "aov": aov_dekking_bruto_jaar_aanvrager,
        "ander_totaal": (inkomen_loondienst_partner + inkomen_onderneming_partner
                         + inkomen_roz_partner + inkomen_overig_partner),
    })

    if alleenstaande == "NEE" and geboortedatum_partner:
        personen.append({
            "wie": "partner",
            "loondienst": inkomen_loondienst_partner,
            "onderneming": inkomen_onderneming_partner,
            "roz": inkomen_roz_partner,
            "overig": inkomen_overig_partner,
            "pct_y2": loondoorbetaling_pct_jaar2_partner,
            "aov": aov_dekking_bruto_jaar_partner,
            "ander_totaal": (inkomen_loondienst_aanvrager + inkomen_onderneming_aanvrager
                             + inkomen_roz_aanvrager + inkomen_overig_aanvrager),
        })

    for p in personen:
        wie = p["wie"]

        # Componenten die altijd hetzelfde zijn (ongeacht fase)
        rest_onderneming = p["onderneming"] * (1 - ao_frac)
        rest_roz = p["roz"] * (1 - ao_frac)
        verzekeringen = p["aov"] + woonlastenverzekering_ao_bruto_jaar
        vast_ao_inkomen = rest_onderneming + rest_roz + p["overig"] + verzekeringen

        has_loondienst = p["loondienst"] > 0

        if has_loondienst:
            sv_loon = p["loondienst"]
            maandloon = sv_loon / 12
            rvc_maand = maandloon * (1 - ao_frac)
            actual_wage_maand = rvc_maand * benutting_frac
            actual_wage_jaar = actual_wage_maand * 12

            # === Fase 1: Loondoorbetaling (jaar 2) ===
            ldb_inkomen = p["pct_y2"] * p["loondienst"]
            totaal_ldb = ldb_inkomen + vast_ao_inkomen

            peil_ldb = today + timedelta(weeks=52)
            elapsed_ldb = max(0, _maanden_verschil(start, peil_ldb))
            projected_ldb = projecteer_hypotheekdelen(
                hypotheek_delen, elapsed_ldb, peil_ldb
            )

            ink_a, ink_p = _verdeel_inkomen(
                wie, totaal_ldb, p["ander_totaal"]
            )
            result = _bereken_scenario(
                naam=f"AO {wie} — loondoorbetaling",
                categorie="ao",
                van_toepassing_op=wie,
                hypotheek_delen=projected_ldb,
                inkomen_aanvrager=ink_a,
                inkomen_partner=ink_p,
                alleenstaande=alleenstaande,
                ontvangt_aow="NEE",
                toetsrente=toetsrente,
                energielabel=energielabel,
                verduurzamings_maatregelen=verduurzamings_maatregelen,
                limieten_bkr=limieten_bkr_geregistreerd,
                studievoorschot=studievoorschot_studielening,
                erfpacht=erfpachtcanon_per_jaar,
                jaarlast=jaarlast_overige_kredieten,
                geadviseerd=geadviseerd_hypotheekbedrag,
                peildatum=peil_ldb,
            )
            result['ao_details'] = {
                'fase': 'loondoorbetaling',
                'ao_percentage': ao_percentage,
                'loondienst_component': round(ldb_inkomen, 2),
                'onderneming_component': round(rest_onderneming, 2),
                'roz_component': round(rest_roz, 2),
                'overig': round(p["overig"], 2),
                'verzekeringen': round(verzekeringen, 2),
                'wia_uitkering': 0,
                'totaal_getroffen_persoon': round(totaal_ldb, 2),
            }
            scenarios.append(result)

            # === Fase 2: WGA loongerelateerd ===
            wia_lgu = bereken_wia_bruto_jaar(
                ao_percentage=ao_percentage,
                sv_loon_jaar=sv_loon,
                feitelijk_loon_maand=actual_wage_maand,
                fase="lgu",
                employment_history_years_to_2015=arbeidsverleden_jaren_tm_2015,
                employment_history_years_from_2016=arbeidsverleden_jaren_vanaf_2016,
            )
            totaal_lgu = wia_lgu['totaal_bruto_jaar'] + vast_ao_inkomen

            peil_lgu = today + timedelta(weeks=104)
            elapsed_lgu = max(0, _maanden_verschil(start, peil_lgu))
            projected_lgu = projecteer_hypotheekdelen(
                hypotheek_delen, elapsed_lgu, peil_lgu
            )

            ink_a, ink_p = _verdeel_inkomen(
                wie, totaal_lgu, p["ander_totaal"]
            )
            result = _bereken_scenario(
                naam=f"AO {wie} — WGA loongerelateerd",
                categorie="ao",
                van_toepassing_op=wie,
                hypotheek_delen=projected_lgu,
                inkomen_aanvrager=ink_a,
                inkomen_partner=ink_p,
                alleenstaande=alleenstaande,
                ontvangt_aow="NEE",
                toetsrente=toetsrente,
                energielabel=energielabel,
                verduurzamings_maatregelen=verduurzamings_maatregelen,
                limieten_bkr=limieten_bkr_geregistreerd,
                studievoorschot=studievoorschot_studielening,
                erfpacht=erfpachtcanon_per_jaar,
                jaarlast=jaarlast_overige_kredieten,
                geadviseerd=geadviseerd_hypotheekbedrag,
                peildatum=peil_lgu,
            )
            result['ao_details'] = {
                'fase': 'wga_loongerelateerd',
                'ao_percentage': ao_percentage,
                'benutting_rvc': benutting_rvc_percentage,
                'wia_status': wia_lgu['status'],
                'wia_uitkering_jaar': wia_lgu['uwv_uitkering_bruto_jaar'],
                'loon_uit_arbeid_jaar': round(actual_wage_jaar, 2),
                'onderneming_component': round(rest_onderneming, 2),
                'roz_component': round(rest_roz, 2),
                'overig': round(p["overig"], 2),
                'verzekeringen': round(verzekeringen, 2),
                'totaal_getroffen_persoon': round(totaal_lgu, 2),
            }
            scenarios.append(result)

            # === Fase 3: WGA loonaanvulling ===
            wia_la = bereken_wia_bruto_jaar(
                ao_percentage=ao_percentage,
                sv_loon_jaar=sv_loon,
                feitelijk_loon_maand=actual_wage_maand,
                fase="na_lgu",
                employment_history_years_to_2015=arbeidsverleden_jaren_tm_2015,
                employment_history_years_from_2016=arbeidsverleden_jaren_vanaf_2016,
            )
            totaal_la = wia_la['totaal_bruto_jaar'] + vast_ao_inkomen

            lgu_duur = _bereken_lgu_duur(
                arbeidsverleden_jaren_tm_2015,
                arbeidsverleden_jaren_vanaf_2016,
            )
            peil_la = today + timedelta(weeks=104) + relativedelta(months=lgu_duur)
            elapsed_la = max(0, _maanden_verschil(start, peil_la))
            projected_la = projecteer_hypotheekdelen(
                hypotheek_delen, elapsed_la, peil_la
            )

            ink_a, ink_p = _verdeel_inkomen(
                wie, totaal_la, p["ander_totaal"]
            )
            result = _bereken_scenario(
                naam=f"AO {wie} — WGA loonaanvulling",
                categorie="ao",
                van_toepassing_op=wie,
                hypotheek_delen=projected_la,
                inkomen_aanvrager=ink_a,
                inkomen_partner=ink_p,
                alleenstaande=alleenstaande,
                ontvangt_aow="NEE",
                toetsrente=toetsrente,
                energielabel=energielabel,
                verduurzamings_maatregelen=verduurzamings_maatregelen,
                limieten_bkr=limieten_bkr_geregistreerd,
                studievoorschot=studievoorschot_studielening,
                erfpacht=erfpachtcanon_per_jaar,
                jaarlast=jaarlast_overige_kredieten,
                geadviseerd=geadviseerd_hypotheekbedrag,
                peildatum=peil_la,
            )
            result['ao_details'] = {
                'fase': wia_la['status'],
                'ao_percentage': ao_percentage,
                'benutting_rvc': benutting_rvc_percentage,
                'wia_status': wia_la['status'],
                'wia_uitkering_jaar': wia_la['uwv_uitkering_bruto_jaar'],
                'loon_uit_arbeid_jaar': round(actual_wage_jaar, 2),
                'onderneming_component': round(rest_onderneming, 2),
                'roz_component': round(rest_roz, 2),
                'overig': round(p["overig"], 2),
                'verzekeringen': round(verzekeringen, 2),
                'totaal_getroffen_persoon': round(totaal_la, 2),
                'lgu_duur_maanden': lgu_duur,
            }
            scenarios.append(result)

        else:
            # Geen loondienst: directe inkomensreductie, geen WIA
            totaal = vast_ao_inkomen

            elapsed = max(0, _maanden_verschil(start, today))
            projected = projecteer_hypotheekdelen(
                hypotheek_delen, elapsed, today
            )

            ink_a, ink_p = _verdeel_inkomen(
                wie, totaal, p["ander_totaal"]
            )
            result = _bereken_scenario(
                naam=f"AO {wie} — arbeidsongeschikt",
                categorie="ao",
                van_toepassing_op=wie,
                hypotheek_delen=projected,
                inkomen_aanvrager=ink_a,
                inkomen_partner=ink_p,
                alleenstaande=alleenstaande,
                ontvangt_aow="NEE",
                toetsrente=toetsrente,
                energielabel=energielabel,
                verduurzamings_maatregelen=verduurzamings_maatregelen,
                limieten_bkr=limieten_bkr_geregistreerd,
                studievoorschot=studievoorschot_studielening,
                erfpacht=erfpachtcanon_per_jaar,
                jaarlast=jaarlast_overige_kredieten,
                geadviseerd=geadviseerd_hypotheekbedrag,
                peildatum=today,
            )
            result['ao_details'] = {
                'fase': 'geen_loondienst',
                'ao_percentage': ao_percentage,
                'onderneming_component': round(rest_onderneming, 2),
                'roz_component': round(rest_roz, 2),
                'overig': round(p["overig"], 2),
                'verzekeringen': round(verzekeringen, 2),
                'totaal_getroffen_persoon': round(totaal, 2),
            }
            scenarios.append(result)

    return {
        "scenarios": scenarios,
        "geadviseerd_hypotheekbedrag": geadviseerd_hypotheekbedrag,
    }


def bereken_werkloosheid_scenarios(
    hypotheek_delen: list[dict],
    ingangsdatum_hypotheek: str,
    geboortedatum_aanvrager: str,
    alleenstaande: str = "JA",
    geboortedatum_partner: str = None,
    # Inkomensverdeling aanvrager (bruto jaarbedragen)
    inkomen_loondienst_aanvrager: float = 0,
    inkomen_onderneming_aanvrager: float = 0,
    inkomen_roz_aanvrager: float = 0,
    inkomen_overig_aanvrager: float = 0,
    # Inkomensverdeling partner
    inkomen_loondienst_partner: float = 0,
    inkomen_onderneming_partner: float = 0,
    inkomen_roz_partner: float = 0,
    inkomen_overig_partner: float = 0,
    # Arbeidsverleden (voor WW-duur)
    arbeidsverleden_jaren_totaal_aanvrager: int = 0,
    arbeidsverleden_pre2016_boven10_aanvrager: int = 0,
    arbeidsverleden_vanaf2016_boven10_aanvrager: int = 0,
    arbeidsverleden_jaren_totaal_partner: int = 0,
    arbeidsverleden_pre2016_boven10_partner: int = 0,
    arbeidsverleden_vanaf2016_boven10_partner: int = 0,
    # Verzekeringen (bruto jaarbedragen)
    woonlastenverzekering_ww_bruto_jaar: float = 0,
    # Standaard
    toetsrente: float = 0.05,
    energielabel: str = "Geen (geldig) Label",
    verduurzamings_maatregelen: float = 0,
    limieten_bkr_geregistreerd: float = 0,
    studievoorschot_studielening: float = 0,
    erfpachtcanon_per_jaar: float = 0,
    jaarlast_overige_kredieten: float = 0,
    geadviseerd_hypotheekbedrag: float = 0,
) -> dict:
    """
    Bereken maximale hypotheek bij werkloosheid.

    Inkomens die door werkloosheid beïnvloed worden:
    - Loondienst → WW-uitkering (70%), daarna 0
    - Onderneming → valt volledig weg (geen WW)
    - ROZ → valt volledig weg (geen WW)
    - Overig → ongewijzigd
    - Woonlastenverzekering WW → extra inkomen

    Per persoon met loondienst: per WW-jaar + na-WW.
    Per persoon zonder loondienst maar met onderneming/ROZ: één scenario (alles weg).
    Hypotheek op startdatum (geen projectie — tijdelijk risico).
    """
    import math
    scenarios = []

    personen = []
    personen.append({
        "wie": "aanvrager",
        "loondienst": inkomen_loondienst_aanvrager,
        "onderneming": inkomen_onderneming_aanvrager,
        "roz": inkomen_roz_aanvrager,
        "overig": inkomen_overig_aanvrager,
        "ander_totaal": (inkomen_loondienst_partner + inkomen_onderneming_partner
                         + inkomen_roz_partner + inkomen_overig_partner),
        "av_totaal": arbeidsverleden_jaren_totaal_aanvrager,
        "av_pre2016": arbeidsverleden_pre2016_boven10_aanvrager,
        "av_vanaf2016": arbeidsverleden_vanaf2016_boven10_aanvrager,
    })

    if alleenstaande == "NEE" and geboortedatum_partner:
        personen.append({
            "wie": "partner",
            "loondienst": inkomen_loondienst_partner,
            "onderneming": inkomen_onderneming_partner,
            "roz": inkomen_roz_partner,
            "overig": inkomen_overig_partner,
            "ander_totaal": (inkomen_loondienst_aanvrager + inkomen_onderneming_aanvrager
                             + inkomen_roz_aanvrager + inkomen_overig_aanvrager),
            "av_totaal": arbeidsverleden_jaren_totaal_partner,
            "av_pre2016": arbeidsverleden_pre2016_boven10_partner,
            "av_vanaf2016": arbeidsverleden_vanaf2016_boven10_partner,
        })

    for p in personen:
        wie = p["wie"]
        has_loondienst = p["loondienst"] > 0
        has_onderneming_roz = (p["onderneming"] + p["roz"]) > 0

        # Alleen scenario als persoon getroffen inkomen heeft
        if not has_loondienst and not has_onderneming_roz:
            continue

        # Vast inkomen dat blijft: overig + woonlastenverzekering WW
        vast_inkomen = p["overig"] + woonlastenverzekering_ww_bruto_jaar

        if has_loondienst:
            # --- Met loondienst: WW-fase(n) + na-WW ---
            # Onderneming/ROZ vallen ook volledig weg bij werkloosheid

            # WW-duur berekenen
            ww_duur = bereken_ww_duur(
                employment_years_total_relevant=p["av_totaal"],
                employment_years_pre2016_above10=p["av_pre2016"],
                employment_years_from2016_above10=p["av_vanaf2016"],
            )

            # WW-uitkering berekenen (70% structureel, maand 3+)
            ww_result = bereken_ww_bruto_jaar(
                sv_loon_jaar=p["loondienst"],
                employment_years_total_relevant=p["av_totaal"],
                employment_years_pre2016_above10=p["av_pre2016"],
                employment_years_from2016_above10=p["av_vanaf2016"],
                ww_maand_nummer=3,  # structureel: 70%
            )

            ww_inkomen_jaar = ww_result['ww_benefit_gross_year']
            # Tijdens WW: onderneming/ROZ vallen ook weg
            totaal_ww = ww_inkomen_jaar + vast_inkomen

            # Aantal WW-jaren (afgerond omhoog)
            ww_jaren = max(1, math.ceil(ww_duur / 12))

            for jaar in range(1, ww_jaren + 1):
                naam = f"Werkloosheid {wie} — jaar {jaar}"
                if ww_jaren == 1:
                    naam = f"Werkloosheid {wie}"

                ink_a, ink_p = _verdeel_inkomen(wie, totaal_ww, p["ander_totaal"])

                result = _bereken_scenario(
                    naam=naam,
                    categorie="werkloosheid",
                    van_toepassing_op=wie,
                    hypotheek_delen=hypotheek_delen,
                    inkomen_aanvrager=ink_a,
                    inkomen_partner=ink_p,
                    alleenstaande=alleenstaande,
                    ontvangt_aow="NEE",
                    toetsrente=toetsrente,
                    energielabel=energielabel,
                    verduurzamings_maatregelen=verduurzamings_maatregelen,
                    limieten_bkr=limieten_bkr_geregistreerd,
                    studievoorschot=studievoorschot_studielening,
                    erfpacht=erfpachtcanon_per_jaar,
                    jaarlast=jaarlast_overige_kredieten,
                    geadviseerd=geadviseerd_hypotheekbedrag,
                    peildatum=date.today(),
                )
                result['ww_details'] = {
                    'fase': 'ww',
                    'ww_jaar': jaar,
                    'ww_duur_maanden': ww_duur,
                    'ww_percentage': 70,
                    'ww_maandloon': ww_result['ww_month_wage'],
                    'ww_uitkering_jaar': round(ww_inkomen_jaar, 2),
                    'loondienst_origineel': round(p["loondienst"], 2),
                    'onderneming_origineel': round(p["onderneming"], 2),
                    'roz_origineel': round(p["roz"], 2),
                    'overig': round(p["overig"], 2),
                    'woonlastenverzekering_ww': round(woonlastenverzekering_ww_bruto_jaar, 2),
                    'totaal_getroffen_persoon': round(totaal_ww, 2),
                }
                scenarios.append(result)

            # Na-WW: geen WW meer, loondienst/onderneming/ROZ = 0
            totaal_na_ww = vast_inkomen
            ink_a, ink_p = _verdeel_inkomen(wie, totaal_na_ww, p["ander_totaal"])

            result_na = _bereken_scenario(
                naam=f"Na WW {wie}",
                categorie="werkloosheid",
                van_toepassing_op=wie,
                hypotheek_delen=hypotheek_delen,
                inkomen_aanvrager=ink_a,
                inkomen_partner=ink_p,
                alleenstaande=alleenstaande,
                ontvangt_aow="NEE",
                toetsrente=toetsrente,
                energielabel=energielabel,
                verduurzamings_maatregelen=verduurzamings_maatregelen,
                limieten_bkr=limieten_bkr_geregistreerd,
                studievoorschot=studievoorschot_studielening,
                erfpacht=erfpachtcanon_per_jaar,
                jaarlast=jaarlast_overige_kredieten,
                geadviseerd=geadviseerd_hypotheekbedrag,
                peildatum=date.today(),
            )
            result_na['ww_details'] = {
                'fase': 'na_ww',
                'ww_duur_maanden': ww_duur,
                'loondienst_origineel': round(p["loondienst"], 2),
                'onderneming_origineel': round(p["onderneming"], 2),
                'roz_origineel': round(p["roz"], 2),
                'overig': round(p["overig"], 2),
                'woonlastenverzekering_ww': round(woonlastenverzekering_ww_bruto_jaar, 2),
                'totaal_getroffen_persoon': round(totaal_na_ww, 2),
            }
            scenarios.append(result_na)

        else:
            # --- Alleen onderneming/ROZ, geen loondienst → alles weg, geen WW ---
            totaal = vast_inkomen
            ink_a, ink_p = _verdeel_inkomen(wie, totaal, p["ander_totaal"])

            result = _bereken_scenario(
                naam=f"Werkloosheid {wie} — werkloos",
                categorie="werkloosheid",
                van_toepassing_op=wie,
                hypotheek_delen=hypotheek_delen,
                inkomen_aanvrager=ink_a,
                inkomen_partner=ink_p,
                alleenstaande=alleenstaande,
                ontvangt_aow="NEE",
                toetsrente=toetsrente,
                energielabel=energielabel,
                verduurzamings_maatregelen=verduurzamings_maatregelen,
                limieten_bkr=limieten_bkr_geregistreerd,
                studievoorschot=studievoorschot_studielening,
                erfpacht=erfpachtcanon_per_jaar,
                jaarlast=jaarlast_overige_kredieten,
                geadviseerd=geadviseerd_hypotheekbedrag,
                peildatum=date.today(),
            )
            result['ww_details'] = {
                'fase': 'geen_loondienst',
                'onderneming_origineel': round(p["onderneming"], 2),
                'roz_origineel': round(p["roz"], 2),
                'overig': round(p["overig"], 2),
                'woonlastenverzekering_ww': round(woonlastenverzekering_ww_bruto_jaar, 2),
                'totaal_getroffen_persoon': round(totaal, 2),
            }
            scenarios.append(result)

    return {
        "scenarios": scenarios,
        "geadviseerd_hypotheekbedrag": geadviseerd_hypotheekbedrag,
    }


def _verdeel_inkomen(wie: str, inkomen_getroffen: float, inkomen_ander: float):
    """Verdeel inkomen over aanvrager/partner velden voor NAT calculator."""
    if wie == "aanvrager":
        return inkomen_getroffen, inkomen_ander
    else:
        return inkomen_ander, inkomen_getroffen


def _maanden_verschil(van: date, tot: date) -> int:
    """Bereken het aantal maanden tussen twee datums."""
    rd = relativedelta(tot, van)
    return rd.years * 12 + rd.months
