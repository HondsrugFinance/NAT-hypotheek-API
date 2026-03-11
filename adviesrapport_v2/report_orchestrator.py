"""Report orchestrator — leest Supabase, berekent, bouwt secties, genereert PDF.

Flow:
1. Lees dossier + aanvraag uit Supabase
2. Normaliseer data (field_mapper)
3. Bereken max hypotheek (calculator_final — direct Python call)
4. Bereken maandlasten (monthly_costs — direct Python call)
5. Bereken risico-scenario's (risk_scenarios — direct Python call)
6. Bereken relatiebeëindiging (2x calculator_final, alleen stel)
7. Leid scenario_checks af
8. Bouw 13 secties (section_builders)
9. Assembleer rapport dict
10. Genereer PDF (pdf_generator)
"""

import json
import logging
import os
from datetime import date, timedelta

import calculator_final
import risk_scenarios
import pdf_generator

from monthly_costs.domain.calculator import MortgageCalculator
from monthly_costs.schemas.input import (
    MonthlyCostsRequest, LoanPart, Partner, LoanType, Box,
)

from adviesrapport_v2.field_mapper import (
    NormalizedDossierData, NormalizedLeningdeel, extract_dossier_data,
)
from adviesrapport_v2.schemas import AdviesrapportOptions
from adviesrapport_v2.formatters import format_bedrag, format_datum

from adviesrapport_v2.section_builders.summary import build_summary_section
from adviesrapport_v2.section_builders.client_profile import build_client_profile_section
from adviesrapport_v2.section_builders.current_situation import build_current_situation_section
from adviesrapport_v2.section_builders.financing import build_financing_section
from adviesrapport_v2.section_builders.retirement import build_retirement_section
from adviesrapport_v2.section_builders.risk_death import build_risk_death_section
from adviesrapport_v2.section_builders.risk_disability import build_risk_disability_section
from adviesrapport_v2.section_builders.risk_unemployment import build_risk_unemployment_section
from adviesrapport_v2.section_builders.risk_relationship import build_risk_relationship_section
from adviesrapport_v2.section_builders.closing import build_closing_section

logger = logging.getLogger("nat-api.adviesrapport_v2.orchestrator")

BEDRIJF = {
    "naam": "Hondsrug Finance B.V.",
    "adres": "Marktstraat 21, 9401 JG Assen",
    "email": "info@hondsrugfinance.nl",
    "telefoon": "088 400 2700",
    "kvk": "KVK 93276699",
}

# Aflosvorm mapping voor monthly_costs API
LOAN_TYPE_MAP = {
    "Annuïteit": LoanType.ANNUITY,
    "Lineair": LoanType.LINEAR,
    "Aflosvrij": LoanType.INTEREST_ONLY,
    "Spaarhypotheek": LoanType.ANNUITY,  # Spaar berekend als annuïteit
}


def generate_report(
    dossier: dict,
    aanvraag: dict,
    options: AdviesrapportOptions,
) -> bytes:
    """Genereer adviesrapport PDF vanuit Supabase data.

    Args:
        dossier: Volledige rij uit Supabase `dossiers` tabel
        aanvraag: Volledige rij uit Supabase `aanvragen` tabel
        options: Adviesrapport opties (uit Lovable dialog)

    Returns:
        PDF bytes
    """
    # --- Stap 1-2: Normaliseer data ---
    data = extract_dossier_data(dossier, aanvraag)
    logger.info("Data genormaliseerd: hypotheek=%.0f, leningdelen=%d",
                data.hypotheek_bedrag, len(data.leningdelen))

    # Override opties uit dialog
    if options.hypotheekverstrekker:
        data.financiering.hypotheekverstrekker = options.hypotheekverstrekker
    data.financiering.nhg = options.nhg

    # --- Stap 3: Max hypotheek ---
    max_hypotheek = _bereken_max_hypotheek(data)
    logger.info("Max hypotheek: %.0f", max_hypotheek)

    # --- Stap 4: Maandlasten ---
    bruto_maandlast, netto_maandlast = _bereken_maandlasten(data)
    logger.info("Maandlasten: bruto=%.0f, netto=%.0f", bruto_maandlast, netto_maandlast)

    # --- Stap 5: Risico-scenario's ---
    hypotheek_delen_api = [ld.to_api_dict() for ld in data.leningdelen_voor_api]
    ingangsdatum = date.today().isoformat()

    # Gemeenschappelijke parameters voor alle risk_scenarios calls
    common_risk_params = dict(
        toetsrente=0.05,
        energielabel=data.financiering.energielabel,
        verduurzamings_maatregelen=0,
        limieten_bkr_geregistreerd=data.limieten_bkr,
        studievoorschot_studielening=data.studielening_maandlast,
        erfpachtcanon_per_jaar=data.erfpachtcanon_per_maand,
        jaarlast_overige_kredieten=data.overige_kredieten_maandlast,
        geadviseerd_hypotheekbedrag=data.hypotheek_bedrag,
    )

    # AOW-inkomen: gebruik data uit Supabase, of schat op basis van standaard AOW
    inkomen_aanvrager_aow = data.inkomen_aanvrager_aow
    inkomen_partner_aow = data.inkomen_partner_aow

    if inkomen_aanvrager_aow == 0 and data.inkomen_aanvrager_huidig > 0:
        inkomen_aanvrager_aow = _schat_aow_inkomen(data.alleenstaand)
        data.aanvrager.inkomen.aow_uitkering = inkomen_aanvrager_aow
        logger.info("AOW aanvrager geschat op %.0f (geen data in Supabase)", inkomen_aanvrager_aow)
    if data.partner and inkomen_partner_aow == 0 and data.inkomen_partner_huidig > 0:
        inkomen_partner_aow = _schat_aow_inkomen(data.alleenstaand)
        data.partner.inkomen.aow_uitkering = inkomen_partner_aow
        logger.info("AOW partner geschat op %.0f (geen data in Supabase)", inkomen_partner_aow)

    # 5a: AOW-scenario's
    aow_result = _safe_call(
        "AOW scenarios",
        risk_scenarios.bereken_aow_scenarios,
        hypotheek_delen=hypotheek_delen_api,
        ingangsdatum_hypotheek=ingangsdatum,
        geboortedatum_aanvrager=data.aanvrager.geboortedatum,
        inkomen_aanvrager_huidig=data.inkomen_aanvrager_huidig,
        inkomen_aanvrager_aow=inkomen_aanvrager_aow,
        alleenstaande="NEE" if not data.alleenstaand else "JA",
        geboortedatum_partner=data.partner.geboortedatum if data.partner else None,
        inkomen_partner_huidig=data.inkomen_partner_huidig,
        inkomen_partner_aow=inkomen_partner_aow,
        **common_risk_params,
    )
    aow_scenarios = (aow_result or {}).get("scenarios", [])

    # 5b: Overlijden (alleen stel)
    overlijden_scenarios = []
    if not data.alleenstaand and data.partner:
        overl_result = _safe_call(
            "Overlijden scenarios",
            risk_scenarios.bereken_overlijdens_scenarios,
            hypotheek_delen=hypotheek_delen_api,
            geboortedatum_aanvrager=data.aanvrager.geboortedatum,
            inkomen_aanvrager_huidig=data.inkomen_aanvrager_huidig,
            geboortedatum_partner=data.partner.geboortedatum,
            inkomen_partner_huidig=data.inkomen_partner_huidig,
            nabestaandenpensioen_bij_overlijden_aanvrager=options.nabestaandenpensioen_bij_overlijden_aanvrager,
            nabestaandenpensioen_bij_overlijden_partner=options.nabestaandenpensioen_bij_overlijden_partner,
            heeft_kind_onder_18=options.heeft_kind_onder_18,
            geboortedatum_jongste_kind=options.geboortedatum_jongste_kind,
            **common_risk_params,
        )
        overlijden_scenarios = (overl_result or {}).get("scenarios", [])

    # 5c: AO-scenario's
    ao_result = _safe_call(
        "AO scenarios",
        risk_scenarios.bereken_ao_scenarios,
        hypotheek_delen=hypotheek_delen_api,
        ingangsdatum_hypotheek=ingangsdatum,
        geboortedatum_aanvrager=data.aanvrager.geboortedatum,
        alleenstaande="NEE" if not data.alleenstaand else "JA",
        geboortedatum_partner=data.partner.geboortedatum if data.partner else None,
        inkomen_loondienst_aanvrager=data.aanvrager.inkomen.loondienst,
        inkomen_onderneming_aanvrager=data.aanvrager.inkomen.onderneming,
        inkomen_roz_aanvrager=data.aanvrager.inkomen.roz,
        inkomen_overig_aanvrager=data.aanvrager.inkomen.overig,
        inkomen_loondienst_partner=data.partner.inkomen.loondienst if data.partner else 0,
        inkomen_onderneming_partner=data.partner.inkomen.onderneming if data.partner else 0,
        inkomen_roz_partner=data.partner.inkomen.roz if data.partner else 0,
        inkomen_overig_partner=data.partner.inkomen.overig if data.partner else 0,
        ao_percentage=options.ao_percentage,
        benutting_rvc_percentage=options.benutting_rvc_percentage,
        loondoorbetaling_pct_jaar1_aanvrager=options.loondoorbetaling_pct_jaar1_aanvrager,
        loondoorbetaling_pct_jaar2_aanvrager=options.loondoorbetaling_pct_jaar2_aanvrager,
        loondoorbetaling_pct_jaar1_partner=options.loondoorbetaling_pct_jaar1_partner,
        loondoorbetaling_pct_jaar2_partner=options.loondoorbetaling_pct_jaar2_partner,
        aov_dekking_bruto_jaar_aanvrager=options.aov_dekking_bruto_jaar_aanvrager,
        aov_dekking_bruto_jaar_partner=options.aov_dekking_bruto_jaar_partner,
        woonlastenverzekering_ao_bruto_jaar=options.woonlastenverzekering_ao_bruto_jaar,
        arbeidsverleden_jaren_tm_2015=options.arbeidsverleden_jaren_tm_2015,
        arbeidsverleden_jaren_vanaf_2016=options.arbeidsverleden_jaren_vanaf_2016,
        **common_risk_params,
    )
    ao_scenarios = (ao_result or {}).get("scenarios", [])

    # 5d: Werkloosheid
    ww_result = _safe_call(
        "WW scenarios",
        risk_scenarios.bereken_werkloosheid_scenarios,
        hypotheek_delen=hypotheek_delen_api,
        ingangsdatum_hypotheek=ingangsdatum,
        geboortedatum_aanvrager=data.aanvrager.geboortedatum,
        alleenstaande="NEE" if not data.alleenstaand else "JA",
        geboortedatum_partner=data.partner.geboortedatum if data.partner else None,
        inkomen_loondienst_aanvrager=data.aanvrager.inkomen.loondienst,
        inkomen_onderneming_aanvrager=data.aanvrager.inkomen.onderneming,
        inkomen_roz_aanvrager=data.aanvrager.inkomen.roz,
        inkomen_overig_aanvrager=data.aanvrager.inkomen.overig,
        inkomen_loondienst_partner=data.partner.inkomen.loondienst if data.partner else 0,
        inkomen_onderneming_partner=data.partner.inkomen.onderneming if data.partner else 0,
        inkomen_roz_partner=data.partner.inkomen.roz if data.partner else 0,
        inkomen_overig_partner=data.partner.inkomen.overig if data.partner else 0,
        arbeidsverleden_jaren_totaal_aanvrager=options.arbeidsverleden_jaren_totaal_aanvrager,
        arbeidsverleden_pre2016_boven10_aanvrager=options.arbeidsverleden_pre2016_boven10_aanvrager,
        arbeidsverleden_vanaf2016_boven10_aanvrager=options.arbeidsverleden_vanaf2016_boven10_aanvrager,
        arbeidsverleden_jaren_totaal_partner=options.arbeidsverleden_jaren_totaal_partner,
        arbeidsverleden_pre2016_boven10_partner=options.arbeidsverleden_pre2016_boven10_partner,
        arbeidsverleden_vanaf2016_boven10_partner=options.arbeidsverleden_vanaf2016_boven10_partner,
        woonlastenverzekering_ww_bruto_jaar=options.woonlastenverzekering_ww_bruto_jaar,
        **common_risk_params,
    )
    ww_scenarios = (ww_result or {}).get("scenarios", [])

    # --- Stap 6: Relatiebeëindiging (alleen stel) ---
    max_hyp_aanvrager_alleen = 0
    max_hyp_partner_alleen = 0
    if not data.alleenstaand and data.partner:
        max_hyp_aanvrager_alleen = _bereken_max_hypotheek_alleenstaand(
            data.aanvrager.inkomen.hoofd_inkomen, data.financiering.energielabel,
        )
        max_hyp_partner_alleen = _bereken_max_hypotheek_alleenstaand(
            data.partner.inkomen.hoofd_inkomen, data.financiering.energielabel,
        )

    # --- Stap 7: Scenario checks ---
    scenario_checks = _bepaal_scenario_checks(
        data, max_hypotheek, aow_scenarios, overlijden_scenarios,
        ao_scenarios, ww_scenarios, max_hyp_aanvrager_alleen, max_hyp_partner_alleen,
    )

    # --- Stap 8: Pensioen chart data ---
    pensioen_chart_data = _build_pensioen_chart_data(data, aow_scenarios, max_hypotheek)

    # --- Stap 9: Bouw secties ---
    sections = []

    # Samenvatting
    sections.append(build_summary_section(
        data=data,
        max_hypotheek=max_hypotheek,
        netto_maandlast=netto_maandlast,
        bruto_maandlast=bruto_maandlast,
        scenario_checks=scenario_checks,
    ))

    # Klantprofiel
    sections.append(build_client_profile_section(
        options=options,
        alleenstaand=data.alleenstaand,
    ))

    # Huidige situatie
    sections.append(build_current_situation_section(data))

    # Financiering
    sections.append(build_financing_section(data, bruto_maandlast))

    # Pensioen
    sections.append(build_retirement_section(
        data=data,
        aow_scenarios=aow_scenarios,
        pensioen_chart_data=pensioen_chart_data,
        max_hypotheek_huidig=max_hypotheek,
    ))

    # Overlijden
    sections.append(build_risk_death_section(
        data=data,
        overlijden_scenarios=overlijden_scenarios,
        max_hypotheek_huidig=max_hypotheek,
    ))

    # AO
    if ao_scenarios:
        sections.append(build_risk_disability_section(
            data=data,
            ao_scenarios=ao_scenarios,
            max_hypotheek_huidig=max_hypotheek,
            ao_percentage=options.ao_percentage,
            benutting_rvc=options.benutting_rvc_percentage,
        ))

    # WW
    if ww_scenarios:
        sections.append(build_risk_unemployment_section(
            data=data,
            ww_scenarios=ww_scenarios,
            max_hypotheek_huidig=max_hypotheek,
        ))

    # Relatiebeëindiging
    relatie_section = build_risk_relationship_section(
        data=data,
        max_hyp_aanvrager_alleen=max_hyp_aanvrager_alleen,
        max_hyp_partner_alleen=max_hyp_partner_alleen,
        max_hypotheek_huidig=max_hypotheek,
    )
    if relatie_section:
        sections.append(relatie_section)

    # Afsluiting
    sections.append(build_closing_section())

    # --- Stap 10: Assembleer rapport dict ---
    klantnaam = data.aanvrager.naam
    if data.partner:
        klantnaam = f"{data.aanvrager.naam} en {data.partner.naam}"

    rapport_datum = options.report_date or date.today().strftime("%d-%m-%Y")
    rapport = {
        "meta": {
            "title": "Persoonlijk Hypotheekadvies",
            "date": rapport_datum,
            "dossierNumber": options.dossier_nummer or "",
            "advisor": options.advisor_name,
            "customerName": klantnaam,
            "propertyAddress": data.financiering.adres,
        },
        "bedrijf": BEDRIJF,
        "sections": sections,
    }

    # --- Stap 11: Genereer PDF ---
    pdf_bytes = pdf_generator.genereer_adviesrapport_pdf(rapport)
    logger.info("PDF gegenereerd: %d bytes", len(pdf_bytes))

    return pdf_bytes


# ═══════════════════════════════════════════════════════════════════════
# Helper functies
# ═══════════════════════════════════════════════════════════════════════

def _safe_call(label: str, func, **kwargs):
    """Roep een functie aan en log fouten zonder te crashen."""
    try:
        return func(**kwargs)
    except Exception as e:
        logger.error("%s mislukt: %s", label, e, exc_info=True)
        return None


def _bereken_leeftijd(geboortedatum: str) -> int:
    """Bereken leeftijd uit geboortedatum string (YYYY-MM-DD). Fallback: 35."""
    if not geboortedatum:
        return 35
    try:
        geb = date.fromisoformat(geboortedatum)
        vandaag = date.today()
        leeftijd = vandaag.year - geb.year
        if (vandaag.month, vandaag.day) < (geb.month, geb.day):
            leeftijd -= 1
        return max(18, min(120, leeftijd))
    except (ValueError, TypeError):
        return 35


def _schat_aow_inkomen(alleenstaand: bool) -> float:
    """Schat bruto AOW-jaarinkomen als Supabase geen AOW/pensioen-bedragen bevat.

    Leest de officiële bedragen uit config/anw.json.
    Alleenstaand: ~€ 20.929/jr, samenwonend per persoon: ~€ 14.379/jr.
    """
    try:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config", "anw.json",
        )
        with open(config_path, "r", encoding="utf-8") as f:
            aow = json.load(f).get("aow_maandbedragen", {})
        if alleenstaand:
            return aow.get("alleenstaand_jaarbedrag_incl_vakantiegeld", 20929)
        return aow.get("samenwonend_jaarbedrag_incl_vakantiegeld_pp", 14379)
    except Exception:
        return 20929 if alleenstaand else 14379


def _bereken_max_hypotheek(data: NormalizedDossierData) -> float:
    """Bereken maximale hypotheek via calculator_final."""
    hypotheek_delen = [ld.to_api_dict() for ld in data.leningdelen_voor_api]

    # Fallback als er geen leningdelen zijn
    if not hypotheek_delen:
        hypotheek_delen = [{
            "aflos_type": "Annuïteit",
            "org_lpt": 360,
            "rest_lpt": 360,
            "hoofdsom_box1": data.hypotheek_bedrag or 300000,
            "hoofdsom_box3": 0,
            "rvp": 120,
            "werkelijke_rente": 0.05,
            "inleg_overig": 0,
        }]

    inputs = {
        "hoofd_inkomen_aanvrager": data.inkomen_aanvrager_huidig,
        "hoofd_inkomen_partner": data.inkomen_partner_huidig,
        "alleenstaande": "NEE" if not data.alleenstaand else "JA",
        "ontvangt_aow": "NEE",
        "energielabel": data.financiering.energielabel,
        "verduurzamings_maatregelen": 0,
        "limieten_bkr_geregistreerd": data.limieten_bkr,
        "studievoorschot_studielening": data.studielening_maandlast,
        "erfpachtcanon_per_jaar": data.erfpachtcanon_per_maand,
        "jaarlast_overige_kredieten": data.overige_kredieten_maandlast,
        "hypotheek_delen": hypotheek_delen,
    }

    result = _safe_call("Max hypotheek", calculator_final.calculate, inputs=inputs)
    if not result:
        return 0

    scenario1 = result.get("scenario1")
    if not scenario1:
        return 0

    return max(
        scenario1["annuitair"]["max_box1"],
        scenario1["niet_annuitair"]["max_box1"],
    )


def _bereken_max_hypotheek_alleenstaand(inkomen: float, energielabel: str) -> float:
    """Bereken max hypotheek als alleenstaande (voor relatiebeëindiging)."""
    inputs = {
        "hoofd_inkomen_aanvrager": inkomen,
        "hoofd_inkomen_partner": 0,
        "alleenstaande": "JA",
        "ontvangt_aow": "NEE",
        "energielabel": energielabel,
        "hypotheek_delen": [{
            "aflos_type": "Annuïteit",
            "org_lpt": 360,
            "rest_lpt": 360,
            "hoofdsom_box1": 300000,
            "hoofdsom_box3": 0,
            "rvp": 120,
            "werkelijke_rente": 0.05,
            "inleg_overig": 0,
        }],
    }

    result = _safe_call("Max hypotheek alleenstaand", calculator_final.calculate, inputs=inputs)
    if not result:
        return 0

    scenario1 = result.get("scenario1")
    if not scenario1:
        return 0

    return scenario1["annuitair"]["max_box1"]


def _bereken_maandlasten(data: NormalizedDossierData) -> tuple[float, float]:
    """Bereken bruto en netto maandlasten via monthly_costs module.

    Returns:
        (bruto_maandlast, netto_maandlast)
    """
    if not data.leningdelen_voor_api:
        return 0, 0

    try:
        # Bouw loan parts
        loan_parts = []
        for i, ld in enumerate(data.leningdelen_voor_api):
            loan_type = LOAN_TYPE_MAP.get(ld.aflos_type, LoanType.ANNUITY)
            box = Box.BOX1 if ld.bedrag_box1 > 0 else Box.BOX3
            principal = ld.bedrag_box1 if ld.bedrag_box1 > 0 else ld.bedrag_box3

            if principal <= 0:
                continue

            loan_parts.append(LoanPart(
                id=f"deel_{i+1}",
                principal=principal,
                interest_rate=ld.werkelijke_rente * 100,  # Module verwacht percentage
                term_years=ld.org_lpt // 12,
                loan_type=loan_type,
                box=box,
            ))

        if not loan_parts:
            return 0, 0

        # Partners — bereken leeftijd uit geboortedatum
        age_aanvrager = _bereken_leeftijd(data.aanvrager.geboortedatum)
        partners = [Partner(
            id="aanvrager",
            taxable_income=data.inkomen_aanvrager_huidig,
            age=age_aanvrager,
            is_aow=False,
        )]
        if data.partner:
            age_partner = _bereken_leeftijd(data.partner.geboortedatum)
            partners.append(Partner(
                id="partner",
                taxable_income=data.inkomen_partner_huidig,
                age=age_partner,
                is_aow=False,
            ))

        request = MonthlyCostsRequest(
            fiscal_year=2026,
            woz_value=data.financiering.woningwaarde or 300000,
            loan_parts=loan_parts,
            partners=partners,
        )

        calc = MortgageCalculator(fiscal_year=2026)
        response = calc.calculate(request)

        bruto = float(response.total_gross_monthly)
        netto = float(response.net_monthly_cost)
        return bruto, netto

    except Exception as e:
        logger.error("Maandlasten berekening mislukt: %s", e, exc_info=True)
        return 0, 0


def _bepaal_scenario_checks(
    data: NormalizedDossierData,
    max_hypotheek: float,
    aow_scenarios: list,
    overlijden_scenarios: list,
    ao_scenarios: list,
    ww_scenarios: list,
    max_hyp_aanvrager_alleen: float,
    max_hyp_partner_alleen: float,
) -> list[dict]:
    """Bepaal scenario check statussen (ok/warning) voor samenvatting."""
    hypotheek = data.hypotheek_bedrag
    checks = []

    # Pensioen
    aow_ok = all(
        sc.get("max_hypotheek_annuitair", 0) >= hypotheek
        for sc in aow_scenarios
    ) if aow_scenarios else True
    checks.append({"label": "Pensionering", "status": "ok" if aow_ok else "warning"})

    # Overlijden (alleen stel)
    if not data.alleenstaand and overlijden_scenarios:
        overl_ok = all(
            sc.get("max_hypotheek_annuitair", 0) >= hypotheek
            for sc in overlijden_scenarios
        )
        checks.append({"label": "Overlijden", "status": "ok" if overl_ok else "warning"})

    # AO
    if ao_scenarios:
        ao_ok = all(
            sc.get("max_hypotheek_annuitair", 0) >= hypotheek
            for sc in ao_scenarios
        )
        checks.append({"label": "Arbeidsongeschiktheid", "status": "ok" if ao_ok else "warning"})

    # WW
    if ww_scenarios:
        ww_ok = all(
            sc.get("max_hypotheek_annuitair", 0) >= hypotheek
            for sc in ww_scenarios
        )
        checks.append({"label": "Werkloosheid", "status": "ok" if ww_ok else "warning"})

    # Relatiebeëindiging
    if not data.alleenstaand and data.partner:
        relatie_ok = (
            max_hyp_aanvrager_alleen >= hypotheek
            and max_hyp_partner_alleen >= hypotheek
        )
        checks.append({"label": "Relatiebeëindiging", "status": "ok" if relatie_ok else "warning"})

    return checks


def _build_pensioen_chart_data(
    data: NormalizedDossierData,
    aow_scenarios: list,
    max_hypotheek_huidig: float,
) -> dict | None:
    """Bouw pensioen chart data voor SVG grafiek."""
    if not aow_scenarios:
        return None

    hypotheek = data.hypotheek_bedrag

    # Bepaal tijdsperiode
    start_jaar = date.today().year
    n_jaren = 30

    # Max hypotheek op AOW-datum
    if aow_scenarios:
        max_hyp_aow = min(sc.get("max_hypotheek_annuitair", 0) for sc in aow_scenarios)
    else:
        max_hyp_aow = max_hypotheek_huidig

    # Bepaal AOW-jaar (vroegste AOW)
    aow_peildatums = [sc.get("peildatum", "") for sc in aow_scenarios]
    aow_jaren = []
    for pd in aow_peildatums:
        try:
            aow_jaren.append(int(pd[:4]))
        except (ValueError, IndexError):
            pass
    aow_jaar = min(aow_jaren) if aow_jaren else start_jaar + 30

    # Bouw jaren array met restschuld + max hypotheek
    jaren = []
    for y in range(n_jaren):
        jaar = start_jaar + y
        elapsed_mnd = y * 12

        # Restschuld: som van alle leningdelen
        restschuld = sum(
            _restschuld_leningdeel(ld, elapsed_mnd)
            for ld in data.leningdelen_voor_api
        )

        # Max hypotheek: lineair interpoleren
        if jaar <= aow_jaar:
            t = y / max(1, aow_jaar - start_jaar)
            max_hyp = max_hypotheek_huidig + (max_hyp_aow - max_hypotheek_huidig) * t
        else:
            max_hyp = max_hyp_aow

        jaren.append({
            "jaar": jaar,
            "max_hypotheek": round(max_hyp),
            "restschuld": round(restschuld),
        })

    return {
        "geadviseerd_hypotheekbedrag": hypotheek,
        "jaren": jaren,
    }


def _restschuld_leningdeel(ld: NormalizedLeningdeel, elapsed_mnd: int) -> float:
    """Bereken restschuld na elapsed_mnd maanden."""
    bedrag = ld.totaal_bedrag
    if elapsed_mnd <= 0:
        return bedrag
    if ld.aflos_type in ("Aflosvrij",):
        return bedrag
    if ld.aflos_type == "Lineair":
        if elapsed_mnd >= ld.org_lpt:
            return 0
        return max(0, bedrag - (bedrag / ld.org_lpt) * elapsed_mnd)
    # Annuïteit
    if elapsed_mnd >= ld.org_lpt:
        return 0
    r = ld.werkelijke_rente / 12
    if r <= 0:
        return max(0, bedrag - (bedrag / ld.org_lpt) * elapsed_mnd)
    fn = (1 + r) ** ld.org_lpt
    pmt = bedrag * (r * fn) / (fn - 1)
    fe = (1 + r) ** elapsed_mnd
    return max(0, bedrag * fe - pmt * (fe - 1) / r)
