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
from aow_calculator import bereken_aow_datum
from loan_projection import projecteer_hypotheekdelen

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
from adviesrapport_v2.scenario_status import (
    derive_death_status,
    derive_retirement_status,
    derive_disability_status,
    derive_unemployment_status,
    derive_relationship_status,
)
from adviesrapport_v2.texts import ADVICE_RISK_LABELS

# CSS class mapping voor scenario checks in template
_STATUS_CSS_CLASS = {
    "affordable": "ok",
    "resolved": "ok",
    "attention": "warning",
    "shortfall": "warning",
}

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


def generate_sections(
    dossier: dict,
    aanvraag: dict,
    options: AdviesrapportOptions,
) -> tuple[list[dict], dict]:
    """Normaliseer data, bereken alles, bouw secties.

    Args:
        dossier: Volledige rij uit Supabase `dossiers` tabel
        aanvraag: Volledige rij uit Supabase `aanvragen` tabel
        options: Adviesrapport opties (uit Lovable dialog)

    Returns:
        (sections, context) — context bevat tussenresultaten voor preview/PDF.
    """
    # --- Stap 1-2: Normaliseer data ---
    data = extract_dossier_data(dossier, aanvraag)
    logger.info("Data genormaliseerd: hypotheek=%.0f, leningdelen=%d",
                data.hypotheek_bedrag, len(data.leningdelen))

    # --- Stap 3: Max hypotheek ---
    max_hypotheek, toetsrente_start = _bereken_max_hypotheek(data)
    logger.info("Max hypotheek: %.0f, toetsrente: %.3f%%", max_hypotheek, toetsrente_start * 100)

    # --- Stap 4: Maandlasten ---
    bruto_maandlast, netto_maandlast = _bereken_maandlasten(data)
    logger.info("Maandlasten: bruto=%.0f, netto=%.0f", bruto_maandlast, netto_maandlast)

    # --- Stap 5: Risico-scenario's ---
    hypotheek_delen_api = [ld.to_api_dict() for ld in data.leningdelen_voor_api]
    ingangsdatum = date.today().isoformat()

    common_risk_params = dict(
        toetsrente=toetsrente_start,
        energielabel=data.financiering.energielabel,
        verduurzamings_maatregelen=0,
        limieten_bkr_geregistreerd=data.limieten_bkr,
        studievoorschot_studielening=data.studielening_maandlast,
        erfpachtcanon_per_jaar=data.erfpachtcanon_per_maand,
        jaarlast_overige_kredieten=data.overige_kredieten_maandlast,
        geadviseerd_hypotheekbedrag=data.totale_hypotheekschuld,
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

    # Voeg restschuld toe per AOW-scenario (nodig voor status-derivatie)
    for sc in aow_scenarios:
        peildatum_str = sc.get("peildatum", "")
        if peildatum_str and ingangsdatum:
            try:
                from datetime import date as _date
                peil = _date.fromisoformat(peildatum_str)
                start_dt = _date.fromisoformat(ingangsdatum)
                elapsed = max(0, (peil.year - start_dt.year) * 12 + (peil.month - start_dt.month))
                restschuld = sum(
                    _restschuld_leningdeel(ld, elapsed)
                    for ld in data.leningdelen_voor_api
                )
                if data.financiering.is_wijziging and not data.bestaande_in_leningdelen:
                    if data.financiering.is_oversluiten:
                        totaal_bestaand = sum(h.hoofdsom for h in data.bestaande_hypotheken)
                        restschuld += max(0, totaal_bestaand - data.financiering.koopsom)
                    else:
                        restschuld += data.financiering.koopsom
                sc["restschuld_op_peildatum"] = round(restschuld)
            except (ValueError, TypeError):
                pass

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
            nabestaandenpensioen_bij_overlijden_aanvrager=data.aanvrager.inkomen.nabestaandenpensioen,
            nabestaandenpensioen_bij_overlijden_partner=data.partner.inkomen.nabestaandenpensioen if data.partner else 0,
            heeft_kind_onder_18=data.heeft_kind_onder_18,
            geboortedatum_jongste_kind=data.geboortedatum_jongste_kind or None,
            **common_risk_params,
        )
        overlijden_scenarios = (overl_result or {}).get("scenarios", [])

    # 5c: AO-scenario's — overslaan als alle personen al AOW-gerechtigd zijn
    _vandaag = date.today()
    try:
        _aow_datum_aanvrager = bereken_aow_datum(date.fromisoformat(data.aanvrager.geboortedatum))
        _aanvrager_is_aow = _vandaag >= _aow_datum_aanvrager
    except (ValueError, TypeError):
        _aanvrager_is_aow = False

    _partner_is_aow = False
    if data.partner and data.partner.geboortedatum:
        try:
            _aow_datum_partner = bereken_aow_datum(date.fromisoformat(data.partner.geboortedatum))
            _partner_is_aow = _vandaag >= _aow_datum_partner
        except (ValueError, TypeError):
            pass

    _alle_personen_aow = _aanvrager_is_aow and (data.alleenstaand or _partner_is_aow)

    ao_scenarios = []
    ww_scenarios = []

    if _alle_personen_aow:
        logger.info("Alle personen AOW-gerechtigd — AO/WW-scenario's overgeslagen")
    else:
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
            inkomen_overig_aanvrager=data.aanvrager.inkomen.overig + data.aanvrager.inkomen.overig_tijdelijk,
            inkomen_loondienst_partner=data.partner.inkomen.loondienst if data.partner else 0,
            inkomen_onderneming_partner=data.partner.inkomen.onderneming if data.partner else 0,
            inkomen_roz_partner=data.partner.inkomen.roz if data.partner else 0,
            inkomen_overig_partner=(data.partner.inkomen.overig + data.partner.inkomen.overig_tijdelijk) if data.partner else 0,
            ao_percentage=options.ao_percentage,
            benutting_rvc_percentage=options.benutting_rvc_percentage,
            loondoorbetaling_pct_jaar1_aanvrager=options.loondoorbetaling_pct_jaar1_aanvrager,
            loondoorbetaling_pct_jaar2_aanvrager=options.loondoorbetaling_pct_jaar2_aanvrager,
            loondoorbetaling_pct_jaar1_partner=options.loondoorbetaling_pct_jaar1_partner,
            loondoorbetaling_pct_jaar2_partner=options.loondoorbetaling_pct_jaar2_partner,
            aov_dekking_bruto_jaar_aanvrager=data.aov_dekking_aanvrager,
            aov_dekking_bruto_jaar_partner=data.aov_dekking_partner,
            woonlastenverzekering_ao_bruto_jaar=data.woonlastenverzekering_ao,
            arbeidsverleden_jaren_tm_2015=options.arbeidsverleden_jaren_tm_2015,
            arbeidsverleden_jaren_vanaf_2016=options.arbeidsverleden_jaren_vanaf_2016,
            **common_risk_params,
        )
        ao_scenarios = (ao_result or {}).get("scenarios", [])

        # Filter scenario's van personen die al AOW-gerechtigd zijn
        if _aanvrager_is_aow:
            ao_scenarios = [s for s in ao_scenarios if s.get("wie") != "aanvrager"]
        if _partner_is_aow:
            ao_scenarios = [s for s in ao_scenarios if s.get("wie") != "partner"]

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
            inkomen_overig_aanvrager=data.aanvrager.inkomen.overig + data.aanvrager.inkomen.overig_tijdelijk,
            inkomen_loondienst_partner=data.partner.inkomen.loondienst if data.partner else 0,
            inkomen_onderneming_partner=data.partner.inkomen.onderneming if data.partner else 0,
            inkomen_roz_partner=data.partner.inkomen.roz if data.partner else 0,
            inkomen_overig_partner=(data.partner.inkomen.overig + data.partner.inkomen.overig_tijdelijk) if data.partner else 0,
            arbeidsverleden_jaren_totaal_aanvrager=options.arbeidsverleden_jaren_totaal_aanvrager,
            arbeidsverleden_pre2016_boven10_aanvrager=options.arbeidsverleden_pre2016_boven10_aanvrager,
            arbeidsverleden_vanaf2016_boven10_aanvrager=options.arbeidsverleden_vanaf2016_boven10_aanvrager,
            arbeidsverleden_jaren_totaal_partner=options.arbeidsverleden_jaren_totaal_partner,
            arbeidsverleden_pre2016_boven10_partner=options.arbeidsverleden_pre2016_boven10_partner,
            arbeidsverleden_vanaf2016_boven10_partner=options.arbeidsverleden_vanaf2016_boven10_partner,
            woonlastenverzekering_ww_bruto_jaar=data.woonlastenverzekering_ww,
            **common_risk_params,
        )
        ww_scenarios = (ww_result or {}).get("scenarios", [])

        # Filter scenario's van personen die al AOW-gerechtigd zijn
        if _aanvrager_is_aow:
            ww_scenarios = [s for s in ww_scenarios if s.get("wie") != "aanvrager"]
        if _partner_is_aow:
            ww_scenarios = [s for s in ww_scenarios if s.get("wie") != "partner"]

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

    # --- Beschikbare buffer (spaargeld/beleggingen minus inbreng) ---
    beschikbare_buffer = data.beschikbare_buffer
    logger.info("Beschikbare buffer: %.0f", beschikbare_buffer)

    # --- Stap 7: Scenario checks ---
    scenario_checks = _bepaal_scenario_checks(
        data, max_hypotheek, aow_scenarios, overlijden_scenarios,
        ao_scenarios, ww_scenarios, max_hyp_aanvrager_alleen, max_hyp_partner_alleen,
        beschikbare_buffer=beschikbare_buffer,
    )

    # --- Stap 8: Pensioen chart data ---
    pensioen_chart_data = _build_pensioen_chart_data(
        data=data,
        aow_scenarios=aow_scenarios,
        max_hypotheek_huidig=max_hypotheek,
        hypotheek_delen_api=hypotheek_delen_api,
        toetsrente=toetsrente_start,
        inkomen_aanvrager_aow=inkomen_aanvrager_aow,
        inkomen_partner_aow=inkomen_partner_aow,
    )

    # --- Stap 9: Bouw secties ---
    sections = []

    sections.append(build_summary_section(
        data=data,
        max_hypotheek=max_hypotheek,
        netto_maandlast=netto_maandlast,
        bruto_maandlast=bruto_maandlast,
        scenario_checks=scenario_checks,
    ))

    sections.append(build_client_profile_section(
        options=options,
        alleenstaand=data.alleenstaand,
    ))

    sections.append(build_current_situation_section(data))

    sections.append(build_financing_section(data, bruto_maandlast))

    sections.append(build_retirement_section(
        data=data,
        aow_scenarios=aow_scenarios,
        pensioen_chart_data=pensioen_chart_data,
        max_hypotheek_huidig=max_hypotheek,
        beschikbare_buffer=beschikbare_buffer,
    ))

    sections.append(build_risk_death_section(
        data=data,
        overlijden_scenarios=overlijden_scenarios,
        max_hypotheek_huidig=max_hypotheek,
        beschikbare_buffer=beschikbare_buffer,
    ))

    if ao_scenarios:
        sections.append(build_risk_disability_section(
            data=data,
            ao_scenarios=ao_scenarios,
            max_hypotheek_huidig=max_hypotheek,
            ao_percentage=options.ao_percentage,
            benutting_rvc=options.benutting_rvc_percentage,
            beschikbare_buffer=beschikbare_buffer,
        ))

    if ww_scenarios:
        sections.append(build_risk_unemployment_section(
            data=data,
            ww_scenarios=ww_scenarios,
            max_hypotheek_huidig=max_hypotheek,
            buffer_months=None,
            beschikbare_buffer=beschikbare_buffer,
        ))

    relatie_section = build_risk_relationship_section(
        data=data,
        max_hyp_aanvrager_alleen=max_hyp_aanvrager_alleen,
        max_hyp_partner_alleen=max_hyp_partner_alleen,
        max_hypotheek_huidig=max_hypotheek,
        beschikbare_buffer=beschikbare_buffer,
    )
    if relatie_section:
        sections.append(relatie_section)

    sections.append(build_closing_section())

    # --- Context: tussenresultaten voor preview/PDF ---
    klantnaam = data.aanvrager.naam
    if data.partner:
        klantnaam = f"{data.aanvrager.naam} en {data.partner.naam}"

    rapport_datum = options.report_date or date.today().strftime("%d-%m-%Y")
    context = {
        "data": data,
        "max_hypotheek": max_hypotheek,
        "bruto_maandlast": bruto_maandlast,
        "netto_maandlast": netto_maandlast,
        "scenario_checks": scenario_checks,
        "aow_scenarios": aow_scenarios,
        "overlijden_scenarios": overlijden_scenarios,
        "ao_scenarios": ao_scenarios,
        "ww_scenarios": ww_scenarios,
        "max_hyp_aanvrager_alleen": max_hyp_aanvrager_alleen,
        "max_hyp_partner_alleen": max_hyp_partner_alleen,
        "meta": {
            "title": "Persoonlijk Hypotheekadvies",
            "date": rapport_datum,
            "dossierNumber": options.dossier_nummer or "",
            "advisor": options.advisor_name,
            "customerName": klantnaam,
            "propertyAddress": data.financiering.adres,
        },
        "bedrijf": BEDRIJF,
    }

    return sections, context


def generate_report(
    dossier: dict,
    aanvraag: dict,
    options: AdviesrapportOptions,
    text_overrides: dict | None = None,
) -> bytes:
    """Genereer adviesrapport PDF vanuit Supabase data.

    Args:
        dossier: Volledige rij uit Supabase `dossiers` tabel
        aanvraag: Volledige rij uit Supabase `aanvragen` tabel
        options: Adviesrapport opties (uit Lovable dialog)
        text_overrides: Optioneel dict met aangepaste teksten per sectie-id

    Returns:
        PDF bytes
    """
    sections, ctx = generate_sections(dossier, aanvraag, options)

    if text_overrides:
        _apply_text_overrides(sections, text_overrides)

    rapport = {
        "meta": ctx["meta"],
        "bedrijf": ctx["bedrijf"],
        "sections": sections,
    }

    pdf_bytes = pdf_generator.genereer_adviesrapport_pdf(rapport)
    logger.info("PDF gegenereerd: %d bytes", len(pdf_bytes))
    return pdf_bytes


def build_preview_response(sections: list[dict], ctx: dict) -> dict:
    """Bouw preview JSON met bewerkbare teksten + per-persoon nummers.

    Wordt gebruikt door het preview endpoint om de frontend van data te voorzien
    zodat de adviseur teksten kan bekijken/bewerken vóór PDF-generatie.
    """
    data = ctx["data"]
    hypotheek = data.totale_hypotheekschuld

    EDITABLE_SECTIONS = {
        "summary", "retirement", "risk-death", "risk-disability",
        "risk-unemployment", "risk-relationship",
    }

    preview_sections = []
    for section in sections:
        sid = section.get("id", "")

        # Bewerkbare teksten: alleen voor relevante secties
        editable = None
        if sid in EDITABLE_SECTIONS:
            editable = {
                "narratives": section.get("narratives") or [],
                "conclusion": section.get("conclusion") or [],
            }

        # Per-persoon nummers uit raw scenario data
        per_person = _extract_per_person(sid, ctx, hypotheek)

        preview_sections.append({
            "id": sid,
            "title": section.get("title", ""),
            "editable_texts": editable,
            "per_person": per_person,
        })

    return {
        "meta": ctx["meta"],
        "geadviseerd_hypotheekbedrag": round(hypotheek),
        "max_hypotheek": round(ctx["max_hypotheek"]),
        "bruto_maandlast": round(ctx["bruto_maandlast"]),
        "netto_maandlast": round(ctx["netto_maandlast"]),
        "scenario_checks": ctx["scenario_checks"],
        "sections": preview_sections,
    }


def _apply_text_overrides(sections: list[dict], overrides: dict) -> None:
    """Vervang narratives/conclusion in sections met aangepaste teksten.

    overrides format: { "retirement": { "narratives": [...], "conclusion": [...] } }
    Alleen niet-None waarden worden vervangen.
    """
    for section in sections:
        sid = section.get("id", "")
        override = overrides.get(sid)
        if not override:
            continue
        if isinstance(override, dict):
            if override.get("narratives") is not None:
                section["narratives"] = override["narratives"]
            if override.get("conclusion") is not None:
                section["conclusion"] = override["conclusion"]


def _extract_per_person(
    section_id: str, ctx: dict, hypotheek: float,
) -> list[dict] | None:
    """Extraheer per-persoon scenario-bedragen uit raw scenario data."""
    data = ctx["data"]
    naam_aanvrager = (data.aanvrager.naam or "Aanvrager").split()[0]
    naam_partner = ((data.partner.naam if data.partner else None) or "Partner").split()[0]

    def _naam_voor(wie: str) -> str:
        return naam_partner if wie == "partner" else naam_aanvrager

    if section_id == "retirement":
        aow_scenarios = ctx.get("aow_scenarios") or []
        if not aow_scenarios:
            return None
        result = []
        for sc in aow_scenarios:
            max_hyp = max(
                sc.get("max_hypotheek_annuitair", 0),
                sc.get("max_hypotheek_niet_annuitair", 0),
            )
            werkelijk = sc.get("restschuld_op_peildatum", round(hypotheek))
            result.append({
                "naam": _naam_voor(sc.get("van_toepassing_op", "aanvrager")),
                "label": sc.get("naam", ""),
                "max_hypotheek": round(max_hyp),
                "werkelijke_hypotheek": round(werkelijk),
                "verschil": round(max_hyp - werkelijk),
            })
        return result

    if section_id == "risk-death":
        scenarios = ctx.get("overlijden_scenarios") or []
        if not scenarios:
            return None
        # Groepeer per van_toepassing_op, pak slechtste per persoon
        personen: dict[str, list] = {}
        for sc in scenarios:
            personen.setdefault(sc.get("van_toepassing_op", "aanvrager"), []).append(sc)
        result = []
        for wie in ("aanvrager", "partner"):
            scs = personen.get(wie, [])
            if not scs:
                continue
            worst = min(scs, key=lambda s: s.get("max_hypotheek_annuitair", 0))
            max_hyp = worst.get("max_hypotheek_annuitair", 0)
            # Naam = de nabestaande (de ander overlijdt)
            nabestaande = naam_partner if wie == "aanvrager" else naam_aanvrager
            result.append({
                "naam": nabestaande,
                "label": f"Bij overlijden {_naam_voor(wie)}",
                "max_hypotheek": round(max_hyp),
                "werkelijke_hypotheek": round(hypotheek),
                "verschil": round(max_hyp - hypotheek),
            })
        return result or None

    if section_id == "risk-disability":
        scenarios = ctx.get("ao_scenarios") or []
        if not scenarios:
            return None
        personen: dict[str, list] = {}
        for sc in scenarios:
            personen.setdefault(sc.get("van_toepassing_op", "aanvrager"), []).append(sc)
        result = []
        for wie in ("aanvrager", "partner"):
            scs = personen.get(wie, [])
            if not scs:
                continue
            # Slechtste scenario excl. loondoorbetaling
            non_ld = [s for s in scs if "loondoorbetaling" not in s.get("naam", "").lower()]
            if not non_ld:
                non_ld = scs
            worst = min(non_ld, key=lambda s: s.get("max_hypotheek_annuitair", 0))
            max_hyp = worst.get("max_hypotheek_annuitair", 0)
            result.append({
                "naam": _naam_voor(wie),
                "label": worst.get("naam", f"AO {_naam_voor(wie)}"),
                "max_hypotheek": round(max_hyp),
                "werkelijke_hypotheek": round(hypotheek),
                "verschil": round(max_hyp - hypotheek),
            })
        return result or None

    if section_id == "risk-unemployment":
        scenarios = ctx.get("ww_scenarios") or []
        if not scenarios:
            return None
        personen: dict[str, list] = {}
        for sc in scenarios:
            personen.setdefault(sc.get("van_toepassing_op", "aanvrager"), []).append(sc)
        result = []
        for wie in ("aanvrager", "partner"):
            scs = personen.get(wie, [])
            if not scs:
                continue
            worst = min(scs, key=lambda s: s.get("max_hypotheek_annuitair", 0))
            max_hyp = worst.get("max_hypotheek_annuitair", 0)
            result.append({
                "naam": _naam_voor(wie),
                "label": worst.get("naam", f"WW {_naam_voor(wie)}"),
                "max_hypotheek": round(max_hyp),
                "werkelijke_hypotheek": round(hypotheek),
                "verschil": round(max_hyp - hypotheek),
            })
        return result or None

    if section_id == "risk-relationship":
        max_a = ctx.get("max_hyp_aanvrager_alleen", 0)
        max_p = ctx.get("max_hyp_partner_alleen", 0)
        if max_a == 0 and max_p == 0:
            return None
        result = []
        if max_a > 0:
            result.append({
                "naam": naam_aanvrager,
                "label": f"{naam_aanvrager} alleen",
                "max_hypotheek": round(max_a),
                "werkelijke_hypotheek": round(hypotheek),
                "verschil": round(max_a - hypotheek),
            })
        if max_p > 0:
            result.append({
                "naam": naam_partner,
                "label": f"{naam_partner} alleen",
                "max_hypotheek": round(max_p),
                "werkelijke_hypotheek": round(hypotheek),
                "verschil": round(max_p - hypotheek),
            })
        return result or None

    return None


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


def _bereken_max_hypotheek(data: NormalizedDossierData) -> tuple[float, float]:
    """Bereken maximale hypotheek via calculator_final.

    Returns:
        (max_hypotheek, toetsrente) — toetsrente is de gewogen rente
        die de calculator gebruikt (nodig voor pensioengrafiek).
    """
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

    # Bepaal ontvangt_aow: JA als de hoogste verdiener AOW-gerechtigd is
    from aow_calculator import bereken_aow_datum as _bereken_aow
    _vandaag = date.today()
    _ink_a = data.inkomen_aanvrager_huidig
    _ink_p = data.inkomen_partner_huidig

    try:
        _a_is_aow = _vandaag >= _bereken_aow(date.fromisoformat(data.aanvrager.geboortedatum))
    except (ValueError, TypeError):
        _a_is_aow = False

    _p_is_aow = False
    if data.partner and data.partner.geboortedatum:
        try:
            _p_is_aow = _vandaag >= _bereken_aow(date.fromisoformat(data.partner.geboortedatum))
        except (ValueError, TypeError):
            pass

    if data.alleenstaand:
        _ontvangt_aow = "JA" if _a_is_aow else "NEE"
    elif _a_is_aow and _p_is_aow:
        _ontvangt_aow = "JA"
    elif _a_is_aow and _ink_a >= _ink_p:
        _ontvangt_aow = "JA"
    elif _p_is_aow and _ink_p > _ink_a:
        _ontvangt_aow = "JA"
    else:
        _ontvangt_aow = "NEE"

    inputs = {
        "hoofd_inkomen_aanvrager": data.inkomen_aanvrager_huidig,
        "hoofd_inkomen_partner": data.inkomen_partner_huidig,
        "alleenstaande": "NEE" if not data.alleenstaand else "JA",
        "ontvangt_aow": _ontvangt_aow,
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
        return 0, 0.05

    scenario1 = result.get("scenario1")
    if not scenario1:
        return 0, 0.05

    debug = result.get("debug", {})
    toetsrente = debug.get("toets_rente", 0.05)

    max_hyp = max(
        0,
        scenario1["annuitair"]["max_box1"],
        scenario1["niet_annuitair"]["max_box1"],
    )
    return max_hyp, toetsrente


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

    return max(0, scenario1["annuitair"]["max_box1"])


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
                term_years=ld.org_lpt / 12,
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
    beschikbare_buffer: float = 0,
) -> list[dict]:
    """Bepaal scenario check statussen voor samenvatting.

    Gebruikt de gecentraliseerde status-derivatie functies en
    ADVICE_RISK_LABELS voor weergave (afgedekt / aandachtspunt / tekort aanwezig).
    """
    hypotheek = data.totale_hypotheekschuld
    has_partner = not data.alleenstaand and data.partner is not None
    orv_list = [v for v in (data.verzekeringen or []) if "overlijden" in v.type.lower()]
    aov_list = [v for v in (data.verzekeringen or []) if "arbeidsongeschikt" in v.type.lower()]
    checks = []

    def _check(label: str, status_class: str, status_label: str):
        return {
            "label": label,
            "status": status_label,
            "status_class": status_class,
        }

    def _pair_check(label: str, shortfalls: list[bool]):
        """Bepaal kleur op basis van per-partner shortfalls.

        Groen: beiden afgedekt, Oranje: één aandachtspunt, Rood: beiden tekort.
        """
        n_shortfall = sum(shortfalls)
        if n_shortfall == 0:
            return _check(label, "ok", "afgedekt")
        if has_partner and n_shortfall < len(shortfalls):
            return _check(label, "partial", "aandachtspunt")
        return _check(label, "warning", "aandachtspunt")

    # Pensioen
    ret_status = derive_retirement_status(aow_scenarios=aow_scenarios, hypotheek=hypotheek, buffer=beschikbare_buffer)
    ret_key = ret_status["status"]
    checks.append(_check("Pensionering", _STATUS_CSS_CLASS.get(ret_key, "warning"), ADVICE_RISK_LABELS[ret_key]))

    # Overlijden (alleen stel)
    if has_partner and overlijden_scenarios:
        personen_ov: dict[str, list] = {}
        for sc in overlijden_scenarios:
            personen_ov.setdefault(sc.get("van_toepassing_op", "aanvrager"), []).append(sc)
        ov_shortfalls = []
        ov_shortfall_amounts = []
        for persoon_key in ("aanvrager", "partner"):
            scs = personen_ov.get(persoon_key, [])
            worst = min((sc.get("max_hypotheek_annuitair", 0) for sc in scs), default=0) if scs else 0
            ov_shortfalls.append(worst < hypotheek)
            ov_shortfall_amounts.append(max(0, hypotheek - worst))
        ov_status = derive_death_status(
            has_partner=True, has_orv=len(orv_list) > 0,
            per_partner_shortfall=ov_shortfalls,
            buffer=beschikbare_buffer, shortfall_amounts=ov_shortfall_amounts,
        )
        ov_key = ov_status["status"]
        checks.append(_check("Overlijden", _STATUS_CSS_CLASS.get(ov_key, "warning"), ADVICE_RISK_LABELS[ov_key]))

    # AO
    if ao_scenarios:
        personen_ao: dict[str, list] = {}
        for sc in ao_scenarios:
            personen_ao.setdefault(sc.get("van_toepassing_op", "aanvrager"), []).append(sc)
        ao_shortfalls = []
        ao_shortfall_amounts = []
        for persoon_key in ("aanvrager", "partner") if has_partner else ("aanvrager",):
            scs = personen_ao.get(persoon_key, [])
            worst = min(
                (sc.get("max_hypotheek_annuitair", 0) for sc in scs
                 if "loondoorbetaling" not in sc.get("naam", "").lower()), default=0,
            ) if scs else 0
            ao_shortfalls.append(worst < hypotheek)
            ao_shortfall_amounts.append(max(0, hypotheek - worst))
        ao_status = derive_disability_status(
            has_aov=len(aov_list) > 0,
            per_partner_shortfall=ao_shortfalls,
            buffer=beschikbare_buffer, shortfall_amounts=ao_shortfall_amounts,
        )
        ao_key = ao_status["status"]
        checks.append(_check("Arbeidsongeschiktheid", _STATUS_CSS_CLASS.get(ao_key, "warning"), ADVICE_RISK_LABELS[ao_key]))

    # WW
    if ww_scenarios:
        personen_ww: dict[str, list] = {}
        for sc in ww_scenarios:
            personen_ww.setdefault(sc.get("van_toepassing_op", "aanvrager"), []).append(sc)
        ww_shortfalls = []
        ww_shortfall_amounts = []
        for persoon_key in ("aanvrager", "partner") if has_partner else ("aanvrager",):
            scs = personen_ww.get(persoon_key, [])
            worst = min((sc.get("max_hypotheek_annuitair", 0) for sc in scs), default=0) if scs else 0
            ww_shortfalls.append(worst < hypotheek)
            ww_shortfall_amounts.append(max(0, hypotheek - worst))
        ww_status = derive_unemployment_status(
            buffer_months=None,
            per_partner_shortfall=ww_shortfalls,
            buffer=beschikbare_buffer, shortfall_amounts=ww_shortfall_amounts,
        )
        ww_key = ww_status["status"]
        checks.append(_check("Werkloosheid", _STATUS_CSS_CLASS.get(ww_key, "warning"), ADVICE_RISK_LABELS[ww_key]))

    # Relatiebeëindiging
    if has_partner:
        rel_status = derive_relationship_status(
            max_hyp_aanvrager=max_hyp_aanvrager_alleen,
            max_hyp_partner=max_hyp_partner_alleen,
            hypotheek=hypotheek,
            buffer=beschikbare_buffer,
        )
        rel_shortfalls = [
            rel_status["applicant_status"] != "affordable",
            rel_status["partner_status"] != "affordable",
        ]
        checks.append(_pair_check("Relatiebeëindiging", rel_shortfalls))

    return checks


def _build_pensioen_chart_data(
    data: NormalizedDossierData,
    aow_scenarios: list,
    max_hypotheek_huidig: float,
    hypotheek_delen_api: list[dict] = None,
    toetsrente: float = 0.05,
    inkomen_aanvrager_aow: float = 0,
    inkomen_partner_aow: float = 0,
) -> dict | None:
    """Bouw pensioen chart data voor SVG grafiek.

    Per jaar wordt de maximale hypotheek berekend op basis van:
    - Geprojecteerde leningdelen (rest_lpt daalt, aflossing loopt)
    - Vaste toetsrente (RVP daalt niet voor deze berekening)
    - Inkomen: huidig vóór AOW, AOW-inkomen erna
    """
    hypotheek = data.totale_hypotheekschuld
    start_jaar = date.today().year
    alleenstaande = "NEE" if not data.alleenstaand else "JA"

    # Parse AOW-momenten met datum, inkomen en label (met voornaam)
    naam_aanvrager = (data.aanvrager.naam or "aanvr.").split()[0]
    naam_partner = ((data.partner.naam if data.partner else None) or "partner").split()[0]

    # Bepaal AOW-jaren per persoon direct uit geboortedatum (niet uit scenario's)
    aow_jaar_aanvrager = None
    aow_jaar_partner = None
    try:
        _aow_dt = bereken_aow_datum(date.fromisoformat(data.aanvrager.geboortedatum))
        aow_jaar_aanvrager = _aow_dt.year
    except (ValueError, TypeError):
        pass
    if data.partner and data.partner.geboortedatum:
        try:
            _aow_dt_p = bereken_aow_datum(date.fromisoformat(data.partner.geboortedatum))
            aow_jaar_partner = _aow_dt_p.year
        except (ValueError, TypeError):
            pass

    # AOW markers voor de grafiek
    aow_events = []
    if aow_jaar_aanvrager:
        aow_events.append((aow_jaar_aanvrager, "aanvrager", f"AOW {naam_aanvrager}"))
    if aow_jaar_partner:
        aow_events.append((aow_jaar_partner, "partner", f"AOW {naam_partner}"))
    aow_events.sort(key=lambda x: x[0])

    # Tijdspan: altijd 30 jaar
    n_jaren = 30

    # Gemeenschappelijke calculator-input (ongewijzigd per jaar)
    base_inputs = {
        "alleenstaande": alleenstaande,
        "energielabel": data.financiering.energielabel,
        "verduurzamings_maatregelen": 0,
        "limieten_bkr_geregistreerd": data.limieten_bkr,
        "studievoorschot_studielening": data.studielening_maandlast,
        "erfpachtcanon_per_jaar": data.erfpachtcanon_per_maand,
        "jaarlast_overige_kredieten": data.overige_kredieten_maandlast,
        "c_toets_rente": toetsrente,
        "c_actuele_10jr_rente": toetsrente,
    }

    # Bouw jaren array
    jaren = []
    delen_api = hypotheek_delen_api or [ld.to_api_dict() for ld in data.leningdelen_voor_api]

    for y in range(n_jaren):
        jaar = start_jaar + y
        elapsed_mnd = y * 12

        # Restschuld: som van alle leningdelen
        restschuld = sum(
            _restschuld_leningdeel(ld, elapsed_mnd)
            for ld in data.leningdelen_voor_api
        )
        # Bij wijziging: bestaande hypotheek(en) erbij tellen
        # NIET als bestaande_in_leningdelen=True (dan zitten ze al in leningdelen)
        if data.financiering.is_wijziging and not data.bestaande_in_leningdelen:
            if data.financiering.is_oversluiten:
                totaal_bestaand = sum(h.hoofdsom for h in data.bestaande_hypotheken)
                restschuld += max(0, totaal_bestaand - data.financiering.koopsom)
            else:
                restschuld += data.financiering.koopsom

        # Max hypotheek: projecteer leningen + bereken met juist inkomen
        if y == 0:
            max_hyp = max_hypotheek_huidig
        else:
            peildatum = date(jaar, 1, 1)
            projected = projecteer_hypotheekdelen(delen_api, elapsed_mnd, peildatum)

            # Renteaftrek: als restant_aftrekbaar verstreken, verplaats box1 → box3
            for i, ld in enumerate(data.leningdelen_voor_api):
                if ld.restant_aftrekbaar is not None and elapsed_mnd >= ld.restant_aftrekbaar:
                    if i < len(projected):
                        pd = projected[i]
                        box1 = pd.get("hoofdsom_box1", 0)
                        if box1 > 0:
                            pd["hoofdsom_box3"] = pd.get("hoofdsom_box3", 0) + box1
                            pd["hoofdsom_box1"] = 0

            # Inkomen: bepaal per datum welke inkomensitems actief zijn
            ink_a = data.aanvrager.inkomen.totaal_op_datum(peildatum)
            ink_p = data.partner.inkomen.totaal_op_datum(peildatum) if data.partner else 0
            aanvrager_is_aow = aow_jaar_aanvrager and jaar >= aow_jaar_aanvrager
            partner_is_aow = aow_jaar_partner and jaar >= aow_jaar_partner

            # ontvangt_aow: JA als hoogste verdiener AOW is (voor woonquote-tabel)
            ontvangt_aow = "NEE"
            if alleenstaande == "JA":
                ontvangt_aow = "JA" if aanvrager_is_aow else "NEE"
            elif aanvrager_is_aow or partner_is_aow:
                if ink_a >= ink_p and aanvrager_is_aow:
                    ontvangt_aow = "JA"
                elif ink_p > ink_a and partner_is_aow:
                    ontvangt_aow = "JA"

            # Verplichtingen: bepaal per datum welke nog actief zijn
            verpl = data.verplichtingen_op_datum(peildatum)

            inputs = {
                **base_inputs,
                "hoofd_inkomen_aanvrager": ink_a,
                "hoofd_inkomen_partner": ink_p,
                "ontvangt_aow": ontvangt_aow,
                "hypotheek_delen": projected,
                # Override verplichtingen met datum-afhankelijke waarden
                "studievoorschot_studielening": verpl["studielening"],
                "jaarlast_overige_kredieten": verpl["overige_kredieten"],
                "limieten_bkr_geregistreerd": verpl["limieten"],
            }

            try:
                result = calculator_final.calculate(inputs)
                s1 = result.get("scenario1")
                if s1:
                    max_hyp = max(
                        0,
                        s1["annuitair"]["max_box1"],
                        s1["niet_annuitair"]["max_box1"],
                    )
                else:
                    max_hyp = 0
            except Exception:
                max_hyp = 0

        jaren.append({
            "jaar": jaar,
            "max_hypotheek": round(max_hyp),
            "restschuld": round(restschuld),
        })

    # AOW markers voor verticale lijnen in de grafiek
    aow_markers = [{"jaar": aj, "label": lbl} for aj, _wie, lbl in aow_events]

    return {
        "geadviseerd_hypotheekbedrag": hypotheek,
        "jaren": jaren,
        "aow_markers": aow_markers,
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
