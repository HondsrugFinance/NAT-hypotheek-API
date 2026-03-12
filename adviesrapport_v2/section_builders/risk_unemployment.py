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
) -> dict:
    """Bouw de werkloosheid sectie."""
    hypotheek = data.hypotheek_bedrag

    has_partner_income = (
        data.partner is not None
        and data.inkomen_partner_huidig > 0
    )

    # --- Status derivatie ---
    status_result = derive_unemployment_status(buffer_months=buffer_months)

    # --- Nuance keys ---
    nuance_keys = compact_keys(
        ("partner_income_used", has_partner_income),
    )

    # --- Render teksten ---
    all_paragraphs = render_standard_scenario(
        text=UNEMPLOYMENT_TEXT,
        status=status_result["status"],
        advice_type=status_result["advice_type"],
        nuance_keys=nuance_keys,
    )
    narratives = all_paragraphs[:1]
    conclusion = all_paragraphs[1:]

    # --- Groepeer per persoon ---
    personen = {}
    for sc in ww_scenarios:
        vta = sc.get("van_toepassing_op", "aanvrager")
        if vta not in personen:
            personen[vta] = []
        personen[vta].append(sc)

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
