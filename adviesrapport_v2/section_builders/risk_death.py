"""Overlijden sectie — alleen bij stel."""

from adviesrapport_v2.field_mapper import NormalizedDossierData
from adviesrapport_v2.formatters import format_bedrag
from adviesrapport_v2.scenario_status import derive_death_status
from adviesrapport_v2.section_builders._align import align_columns_at_totaal
from adviesrapport_v2.texts import (
    DEATH_SINGLE_TEXT,
    DEATH_TEXT,
    compact_keys,
    render_standard_scenario,
)


def build_risk_death_section(
    data: NormalizedDossierData,
    overlijden_scenarios: list[dict],
    max_hypotheek_huidig: float,
) -> dict:
    """Bouw de overlijden sectie."""
    hypotheek = data.hypotheek_bedrag

    # Alleenstaand: kort verhaal
    if data.alleenstaand:
        return {
            "id": "risk-death",
            "title": "Overlijden",
            "visible": True,
            "narratives": [DEATH_SINGLE_TEXT],
        }

    # --- Verzekeringen ---
    orv_list = [v for v in (data.verzekeringen or []) if "overlijden" in v.type.lower()]
    has_orv = len(orv_list) > 0
    has_life_insurance = any(
        "leven" in v.type.lower() for v in (data.verzekeringen or [])
    )

    # --- Status derivatie ---
    status_result = derive_death_status(
        has_partner=True,
        has_orv=has_orv,
    )

    # --- Nuance keys ---
    nuance_keys = compact_keys(
        ("existing_orv", has_orv),
        ("existing_life_insurance", has_life_insurance),
        ("employer_provisions_unknown", True),
    )

    # --- Render teksten ---
    all_paragraphs = render_standard_scenario(
        text=DEATH_TEXT,
        status=status_result["status"],
        advice_type=status_result["advice_type"],
        nuance_keys=nuance_keys,
    )
    narratives = all_paragraphs[:1]
    conclusion = all_paragraphs[1:]

    # --- Columns per scenario ---
    columns = []
    for sc in overlijden_scenarios:
        naam = sc.get("naam", "Overlijden")
        van_toepassing_op = sc.get("van_toepassing_op", "")
        anw_details = sc.get("anw_details") or {}

        nabestaande_inkomen = sc.get("inkomen_aanvrager", 0) + sc.get("inkomen_partner", 0)
        max_hyp = sc.get("max_hypotheek_annuitair", 0)

        if van_toepassing_op == "aanvrager":
            nabestaande_naam = data.partner.naam if data.partner else "Partner"
        else:
            nabestaande_naam = data.aanvrager.naam

        col_rows = [
            {"label": f"Totaal inkomen {nabestaande_naam}", "value": format_bedrag(nabestaande_inkomen), "bold": True},
        ]

        eigen_inkomen = anw_details.get("eigen_inkomen_jaar", 0)
        nabestaandenpensioen = anw_details.get("nabestaandenpensioen_jaar", 0)
        anw_bruto = anw_details.get("anw_bruto_jaar", 0)

        if eigen_inkomen > 0:
            col_rows.append({"label": "Inkomen uit loondienst", "value": format_bedrag(eigen_inkomen), "sub": True})
        if nabestaandenpensioen > 0:
            col_rows.append({"label": "Nabestaandenpensioen", "value": format_bedrag(nabestaandenpensioen), "sub": True})
        if anw_bruto > 0:
            col_rows.append({"label": "ANW-uitkering", "value": format_bedrag(anw_bruto), "sub": True})

        if not anw_details:
            if sc.get("inkomen_aanvrager", 0) > 0 and van_toepassing_op != "aanvrager":
                col_rows.append({"label": f"Inkomen {data.aanvrager.naam}", "value": format_bedrag(sc["inkomen_aanvrager"]), "sub": True})
            if sc.get("inkomen_partner", 0) > 0 and van_toepassing_op != "partner":
                col_rows.append({"label": f"Inkomen {data.partner.naam}", "value": format_bedrag(sc["inkomen_partner"]), "sub": True})

        col_rows.append({"label": "", "value": ""})
        col_rows.append({"label": "Maximale hypotheek", "value": format_bedrag(max_hyp), "sub": True})

        chart_data = {
            "type": "overlijden_vergelijk",
            "huidig_max_hypotheek": max_hypotheek_huidig,
            "max_hypotheek_na_overlijden": max_hyp,
            "geadviseerd_hypotheekbedrag": hypotheek,
        }

        columns.append({"title": naam, "rows": col_rows, "chart_data": chart_data})

    align_columns_at_totaal(columns)

    return {
        "id": "risk-death",
        "title": "Overlijden",
        "visible": True,
        "narratives": narratives,
        "columns": columns,
        "conclusion": conclusion,
    }
