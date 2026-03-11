"""Werkloosheid sectie — WW-scenario's per persoon."""

import re

from adviesrapport_v2.field_mapper import NormalizedDossierData
from adviesrapport_v2.formatters import format_bedrag
from adviesrapport_v2.section_builders._align import align_columns_at_totaal


def build_risk_unemployment_section(
    data: NormalizedDossierData,
    ww_scenarios: list[dict],
    max_hypotheek_huidig: float,
) -> dict:
    """Bouw de werkloosheid sectie.

    Args:
        data: Genormaliseerde dossier data
        ww_scenarios: WW-scenario's uit risk_scenarios (categorie "ww")
        max_hypotheek_huidig: Huidige max hypotheek
    """
    hypotheek = data.hypotheek_bedrag

    # Groepeer per persoon
    personen = {}
    for sc in ww_scenarios:
        vta = sc.get("van_toepassing_op", "aanvrager")
        if vta not in personen:
            personen[vta] = []
        personen[vta].append(sc)

    # Narratives: WW-duur per persoon
    narrative_parts = []
    for persoon_key, scenarios in personen.items():
        naam = data.aanvrager.naam if persoon_key == "aanvrager" else (data.partner.naam if data.partner else "Partner")
        ww_duur_sc = [sc for sc in scenarios if "ww" in sc.get("naam", "").lower() and "na ww" not in sc.get("naam", "").lower()]
        if ww_duur_sc:
            duur = _extract_ww_duur(ww_duur_sc[0])
            if duur:
                narrative_parts.append(f"{naam} heeft recht op {duur} WW-uitkering.")
            else:
                narrative_parts.append(f"{naam} heeft recht op WW-uitkering.")

    narratives = [" ".join(narrative_parts)] if narrative_parts else [
        "Wij hebben beoordeeld wat de gevolgen zijn bij werkloosheid."
    ]

    columns = []
    min_max_hyp_na_ww = max_hypotheek_huidig

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

            # Breakdown
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
            col_rows.append({"label": "", "value": ""})  # Spacer

            fasen.append({"label": fase_label, "max_hypotheek": max_hyp})

            if "na ww" in naam.lower():
                min_max_hyp_na_ww = min(min_max_hyp_na_ww, max_hyp)

        chart_data = {
            "type": "vergelijk_fasen",
            "fasen": fasen,
            "geadviseerd_hypotheekbedrag": hypotheek,
        }

        columns.append({"title": titel, "rows": col_rows, "chart_data": chart_data})

    align_columns_at_totaal(columns)

    section = {
        "id": "risk-unemployment",
        "title": "Werkloosheid",
        "visible": True,
        "narratives": narratives,
        "columns": columns,
    }

    if min_max_hyp_na_ww < hypotheek:
        section["advisor_note"] = (
            "Na afloop van de WW-periode daalt uw maximale hypotheek "
            "fors. Wij adviseren een financiële buffer van minimaal "
            "6 maanden netto lasten aan te houden."
        )

    return section


def _extract_ww_duur(scenario: dict) -> str:
    """Haal WW-duur uit scenario dict.

    Leest ww_details.ww_duur_maanden (int) uit het scenario.
    Fallback: regex op scenario naam.
    """
    ww_details = scenario.get("ww_details") or {}
    maanden = ww_details.get("ww_duur_maanden", 0)
    if maanden and maanden > 0:
        return f"{maanden} maanden"

    # Fallback: regex op naam
    naam = scenario.get("naam", "")
    match = re.search(r'(\d+)\s*maanden?', naam, re.IGNORECASE)
    if match:
        return f"{match.group(1)} maanden"
    return ""


def _extract_ww_fase_label(scenario_naam: str) -> str:
    """Haal fase-label uit scenario naam.

    'Werkloosheid aanvrager — 13 maanden WW' → 'Tijdens WW'
    'Na WW aanvrager' → 'Na WW'
    """
    lower = scenario_naam.lower()
    if "na ww" in lower:
        return "Na WW"
    if "werkloosheid" in lower or "ww" in lower:
        return "Tijdens WW"
    return scenario_naam
