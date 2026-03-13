"""Werkloosheid sectie — WW-scenario's per persoon."""

import re

from adviesrapport_v2.field_mapper import NormalizedDossierData
from adviesrapport_v2.formatters import format_bedrag
from adviesrapport_v2.scenario_status import derive_unemployment_status
from adviesrapport_v2.section_builders._align import align_columns_at_totaal
from adviesrapport_v2.texts import (
    UNEMPLOYMENT_TEXT,
    compact_keys,
    render_standard_scenario,
)


def build_risk_unemployment_section(
    data: NormalizedDossierData,
    ww_scenarios: list[dict],
    max_hypotheek_huidig: float,
    buffer_months: float | None = None,
    beschikbare_buffer: float = 0,
) -> dict:
    """Bouw de werkloosheid sectie."""
    hypotheek = data.hypotheek_bedrag

    # --- Ondernemer-detectie per persoon ---
    aanvrager_is_ondernemer = (
        data.aanvrager.inkomen.onderneming > 0
        and data.aanvrager.inkomen.loondienst == 0
    )
    partner_is_ondernemer = (
        data.partner is not None
        and data.partner.inkomen.onderneming > 0
        and data.partner.inkomen.loondienst == 0
    )
    alle_ondernemers = aanvrager_is_ondernemer and (
        data.alleenstaand or data.partner is None or partner_is_ondernemer
    )

    # --- Groepeer per persoon ---
    personen = {}
    for sc in ww_scenarios:
        vta = sc.get("van_toepassing_op", "aanvrager")
        if vta not in personen:
            personen[vta] = []
        personen[vta].append(sc)

    # --- Per-partner vergelijking ---
    per_partner_shortfall = []
    shortfall_amounts = []
    partner_names = []
    per_partner_is_ondernemer = []
    for persoon_key, scenarios in personen.items():
        naam = data.aanvrager.korte_naam if persoon_key == "aanvrager" else (data.partner.korte_naam if data.partner else "Partner")
        partner_names.append(naam)
        is_ond = aanvrager_is_ondernemer if persoon_key == "aanvrager" else partner_is_ondernemer
        per_partner_is_ondernemer.append(is_ond)
        # Slechtste fase (laagste max_hypotheek)
        worst_max_hyp = min(
            (sc.get("max_hypotheek_annuitair", 0) for sc in scenarios),
            default=0,
        )
        tekort = max(0, hypotheek - worst_max_hyp)
        per_partner_shortfall.append(worst_max_hyp < hypotheek)
        shortfall_amounts.append(tekort)

    # --- Status derivatie (datagedreven) ---
    status_result = derive_unemployment_status(
        buffer_months=buffer_months,
        per_partner_shortfall=per_partner_shortfall,
        buffer=beschikbare_buffer,
        shortfall_amounts=shortfall_amounts,
    )

    # --- Nuance keys ---
    max_tekort_ww = max(shortfall_amounts) if shortfall_amounts else 0
    buffer_dekt_alles = beschikbare_buffer > 0 and max_tekort_ww > 0 and beschikbare_buffer >= max_tekort_ww
    buffer_dekt_deels = beschikbare_buffer > 0 and max_tekort_ww > 0 and not buffer_dekt_alles

    nuance_keys = compact_keys(
        ("buffer_covers_shortfall", buffer_dekt_alles),
        ("buffer_partial", buffer_dekt_deels),
    )

    # --- Analysis sentences ---
    # Bij mixed inkomenstype (ondernemer + loondienst) altijd per-persoon zinnen
    has_mixed_income_type = (
        not data.alleenstaand
        and len(per_partner_is_ondernemer) == 2
        and per_partner_is_ondernemer[0] != per_partner_is_ondernemer[1]
    )
    has_mixed_outcomes = (
        not data.alleenstaand
        and len(per_partner_shortfall) == 2
        and per_partner_shortfall[0] != per_partner_shortfall[1]
    )
    force_per_person = has_mixed_outcomes or has_mixed_income_type

    analysis_sentences = None
    if force_per_person:
        analysis_sentences = []
        for naam, has_shortfall, is_ond in zip(
            partner_names, per_partner_shortfall, per_partner_is_ondernemer
        ):
            if has_shortfall:
                analysis_sentences.append(
                    f"Bij werkloosheid van {naam} ontstaat er op basis van deze berekening "
                    f"een financieel tekort."
                )
                if is_ond:
                    analysis_sentences.append(UNEMPLOYMENT_TEXT["advice"]["no_provisions_entrepreneur"])
                else:
                    analysis_sentences.append(UNEMPLOYMENT_TEXT["advice"]["consider_solution"])
            else:
                analysis_sentences.append(
                    f"Bij werkloosheid van {naam} blijft de hypotheek "
                    f"op basis van deze berekening betaalbaar."
                )
                analysis_sentences.append(UNEMPLOYMENT_TEXT["advice"]["no_action"])

    # --- Render teksten ---
    # Bij alle ondernemers met tekort: gebruik ondernemer-advies i.p.v. standaard
    advice_type = status_result["advice_type"]
    if alle_ondernemers and any(per_partner_shortfall) and not force_per_person:
        advice_type = "no_provisions_entrepreneur"

    all_paragraphs = render_standard_scenario(
        text=UNEMPLOYMENT_TEXT,
        status=status_result["status"],
        advice_type=advice_type,
        nuance_keys=nuance_keys,
        analysis_sentences=analysis_sentences,
        include_advice=not force_per_person,
    )
    narratives = all_paragraphs[:1]
    conclusion = all_paragraphs[1:]

    # Bij alleen ondernemers: verwijder de indicatief-disclaimer
    if alle_ondernemers:
        disclaimer = UNEMPLOYMENT_TEXT.get("disclaimer", "")
        conclusion = [p for p in conclusion if p != disclaimer]

    # Specialist-zin: niet tonen bij alleen ondernemers
    if not alle_ondernemers and status_result["status"] != "affordable":
        conclusion.append(
            "Wij bemiddelen niet in voorzieningen voor werkloosheid. "
            "Raadpleeg hiervoor een externe specialist."
        )

    columns = []
    for persoon_key, scenarios in personen.items():
        if persoon_key == "aanvrager":
            titel = f"Werkloosheid - {data.aanvrager.titel_naam}" if not data.alleenstaand else data.aanvrager.titel_naam
        else:
            titel = f"Werkloosheid - {data.partner.titel_naam}" if data.partner else "Partner"

        col_rows = []
        fasen = [{"label": "Huidig", "max_hypotheek": max_hypotheek_huidig}]

        for sc in scenarios:
            naam = sc.get("naam", "")
            inkomen = sc.get("inkomen_aanvrager", 0) + sc.get("inkomen_partner", 0)
            max_hyp = sc.get("max_hypotheek_annuitair", 0)

            fase_label = _extract_ww_fase_label(naam)

            col_rows.append({"label": fase_label, "value": format_bedrag(inkomen), "bold": True})

            if sc.get("inkomen_aanvrager", 0) > 0:
                col_rows.append({
                    "label": f"Inkomen {data.aanvrager.korte_naam}",
                    "value": format_bedrag(sc["inkomen_aanvrager"]),
                    "sub": True,
                })
            if data.partner and sc.get("inkomen_partner", 0) > 0:
                col_rows.append({
                    "label": f"Inkomen {data.partner.korte_naam}",
                    "value": format_bedrag(sc["inkomen_partner"]),
                    "sub": True,
                })
            col_rows.append({"label": "", "value": ""})

            fasen.append({"label": fase_label, "max_hypotheek": max_hyp})

        chart_data = {
            "type": "vergelijk_fasen",
            "fasen": fasen,
            "geadviseerd_hypotheekbedrag": hypotheek,
        }

        columns.append({"title": titel, "rows": col_rows, "chart_data": chart_data})

    align_columns_at_totaal(columns)

    return {
        "id": "risk-unemployment",
        "title": "Werkloosheid",
        "visible": True,
        "narratives": narratives,
        "columns": columns,
        "conclusion": conclusion,
    }


def _extract_ww_duur(scenario: dict) -> str:
    """Haal WW-duur uit scenario dict."""
    ww_details = scenario.get("ww_details") or {}
    maanden = ww_details.get("ww_duur_maanden", 0)
    if maanden and maanden > 0:
        return f"{maanden} maanden"

    naam = scenario.get("naam", "")
    match = re.search(r'(\d+)\s*maanden?', naam, re.IGNORECASE)
    if match:
        return f"{match.group(1)} maanden"
    return ""


def _extract_ww_fase_label(scenario_naam: str) -> str:
    """Haal fase-label uit scenario naam."""
    lower = scenario_naam.lower()
    if "na ww" in lower:
        return "Na WW"
    # Ondernemer-scenario: "Werkloosheid {wie} — werkloos"
    if "— werkloos" in lower:
        return "Werkloos"
    if "werkloosheid" in lower or "ww" in lower:
        return "Tijdens WW"
    return scenario_naam
