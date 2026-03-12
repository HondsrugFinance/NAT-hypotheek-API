"""Werkloosheid sectie — WW-scenario's per persoon."""

import re

from adviesrapport_v2.field_mapper import NormalizedDossierData
from adviesrapport_v2.formatters import format_bedrag
from adviesrapport_v2.scenario_status import derive_unemployment_status
from adviesrapport_v2.section_builders._align import align_columns_at_totaal
from adviesrapport_v2.texts import (
    UNEMPLOYMENT_TEXT,
    render_standard_scenario,
)


def build_risk_unemployment_section(
    data: NormalizedDossierData,
    ww_scenarios: list[dict],
    max_hypotheek_huidig: float,
    buffer_months: float | None = None,
) -> dict:
    """Bouw de werkloosheid sectie."""
    hypotheek = data.hypotheek_bedrag

    # --- Groepeer per persoon ---
    personen = {}
    for sc in ww_scenarios:
        vta = sc.get("van_toepassing_op", "aanvrager")
        if vta not in personen:
            personen[vta] = []
        personen[vta].append(sc)

    # --- Per-partner vergelijking ---
    per_partner_shortfall = []
    partner_names = []
    for persoon_key, scenarios in personen.items():
        naam = data.aanvrager.naam if persoon_key == "aanvrager" else (data.partner.naam if data.partner else "Partner")
        partner_names.append(naam)
        # Slechtste fase (laagste max_hypotheek)
        worst_max_hyp = min(
            (sc.get("max_hypotheek_annuitair", 0) for sc in scenarios),
            default=0,
        )
        per_partner_shortfall.append(worst_max_hyp < hypotheek)

    # --- Status derivatie (datagedreven) ---
    status_result = derive_unemployment_status(
        buffer_months=buffer_months,
        per_partner_shortfall=per_partner_shortfall,
    )

    # --- Nuance keys ---
    nuance_keys: list[str] = []

    # --- Analysis sentences (alleen bij ongelijke uitkomst bij stel) ---
    analysis_sentences = None
    has_mixed_outcomes = not data.alleenstaand and len(per_partner_shortfall) == 2 and per_partner_shortfall[0] != per_partner_shortfall[1]
    if has_mixed_outcomes:
        analysis_sentences = []
        for naam, has_shortfall in zip(partner_names, per_partner_shortfall):
            if has_shortfall:
                analysis_sentences.append(
                    f"Bij werkloosheid van {naam} ontstaat er op basis van deze berekening "
                    f"een financieel tekort."
                )
                analysis_sentences.append(UNEMPLOYMENT_TEXT["advice"]["consider_solution"])
            else:
                analysis_sentences.append(
                    f"Bij werkloosheid van {naam} blijft de hypotheek "
                    f"op basis van deze berekening betaalbaar."
                )
                analysis_sentences.append(UNEMPLOYMENT_TEXT["advice"]["no_action"])

    # --- Render teksten ---
    all_paragraphs = render_standard_scenario(
        text=UNEMPLOYMENT_TEXT,
        status=status_result["status"],
        advice_type=status_result["advice_type"],
        nuance_keys=nuance_keys,
        analysis_sentences=analysis_sentences,
        include_advice=not has_mixed_outcomes,
    )
    narratives = all_paragraphs[:1]
    conclusion = all_paragraphs[1:]

    columns = []
    for persoon_key, scenarios in personen.items():
        if persoon_key == "aanvrager":
            titel = f"Werkloosheid - {data.aanvrager.naam}" if not data.alleenstaand else data.aanvrager.naam
        else:
            titel = f"Werkloosheid - {data.partner.naam}" if data.partner else "Partner"

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
                    "label": f"Inkomen {data.aanvrager.naam}",
                    "value": format_bedrag(sc["inkomen_aanvrager"]),
                    "sub": True,
                })
            if data.partner and sc.get("inkomen_partner", 0) > 0:
                col_rows.append({
                    "label": f"Inkomen {data.partner.naam}",
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
    if "werkloosheid" in lower or "ww" in lower:
        return "Tijdens WW"
    return scenario_naam
