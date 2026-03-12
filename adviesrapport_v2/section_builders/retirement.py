"""Pensioen sectie — AOW-scenario's met chart data."""

from adviesrapport_v2.field_mapper import NormalizedDossierData
from adviesrapport_v2.formatters import format_bedrag
from adviesrapport_v2.scenario_status import derive_retirement_status
from adviesrapport_v2.section_builders._align import align_columns_at_totaal
from adviesrapport_v2.texts import (
    RETIREMENT_TEXT,
    compact_keys,
    render_standard_scenario,
)


def build_retirement_section(
    data: NormalizedDossierData,
    aow_scenarios: list[dict],
    pensioen_chart_data: dict | None,
    max_hypotheek_huidig: float,
) -> dict:
    """Bouw de pensioen sectie."""
    hypotheek = data.hypotheek_bedrag

    # --- Status derivatie ---
    status_result = derive_retirement_status(
        aow_scenarios=aow_scenarios,
        hypotheek=hypotheek,
    )

    # --- Nuance keys ---
    has_partner = not data.alleenstaand and data.partner is not None
    has_annuity_income = (
        (data.aanvrager.inkomen.overig > 0)
        or (has_partner and data.partner.inkomen.overig > 0)
    )
    gross_income_total = data.inkomen_aanvrager_huidig + data.inkomen_partner_huidig
    pension_income_total = (
        data.aanvrager.inkomen.aow_uitkering + data.aanvrager.inkomen.pensioen
        + (data.partner.inkomen.aow_uitkering if data.partner else 0)
        + (data.partner.inkomen.pensioen if data.partner else 0)
    )

    nuance_keys = compact_keys(
        ("couple_two_aow", has_partner),
        ("income_decrease", pension_income_total < gross_income_total),
        ("annuity_income_used", has_annuity_income),
    )

    # --- Render teksten ---
    all_paragraphs = render_standard_scenario(
        text=RETIREMENT_TEXT,
        status=status_result["status"],
        advice_type=status_result["advice_type"],
        nuance_keys=nuance_keys,
    )
    narratives = all_paragraphs[:1]  # Intro boven data
    conclusion = all_paragraphs[1:]  # Rest onder data

    # --- AOW/pensioen uitsplitsing ---
    aow_aanvrager = data.aanvrager.inkomen.aow_uitkering
    pensioen_aanvrager = data.aanvrager.inkomen.pensioen
    aow_partner = data.partner.inkomen.aow_uitkering if data.partner else 0
    pensioen_partner = data.partner.inkomen.pensioen if data.partner else 0

    if data.alleenstaand:
        rows = []
        for sc in aow_scenarios:
            naam = sc.get("naam", "AOW")
            ink_totaal = sc.get("inkomen_aanvrager", 0) + sc.get("inkomen_partner", 0)
            rows.append({
                "label": f"Totaal inkomen na {naam}",
                "value": format_bedrag(ink_totaal),
                "bold": True,
            })
            if aow_aanvrager > 0:
                rows.append({"label": "AOW-uitkering", "value": format_bedrag(aow_aanvrager), "sub": True})
            if pensioen_aanvrager > 0:
                rows.append({"label": "Pensioen", "value": format_bedrag(pensioen_aanvrager), "sub": True})
            if aow_aanvrager == 0 and pensioen_aanvrager == 0 and sc.get("inkomen_aanvrager", 0) > 0:
                rows.append({
                    "label": f"Inkomen {data.aanvrager.naam or 'aanvrager'}",
                    "value": format_bedrag(sc["inkomen_aanvrager"]),
                    "sub": True,
                })
            rows.append({"label": "", "value": ""})
            rows.append({
                "label": "Maximale hypotheek na AOW",
                "value": format_bedrag(sc.get("max_hypotheek_annuitair", 0)),
            })

        section = {
            "id": "retirement",
            "title": "Pensioen",
            "visible": True,
            "narratives": narratives,
            "rows": rows,
            "conclusion": conclusion,
        }
    else:
        columns = []
        for sc in aow_scenarios:
            naam = sc.get("naam", "AOW")
            naam_lower = naam.lower()
            col_rows = []

            ink_aanvrager = sc.get("inkomen_aanvrager", 0)
            ink_partner = sc.get("inkomen_partner", 0)
            totaal = ink_aanvrager + ink_partner

            aanvrager_op_aow = "aanvrager" in naam_lower or "partner" in naam_lower
            partner_op_aow = "partner" in naam_lower

            if ink_aanvrager > 0:
                col_rows.append({
                    "label": f"Inkomen {data.aanvrager.naam}",
                    "value": format_bedrag(ink_aanvrager),
                    "sub": True,
                })
                if aanvrager_op_aow and aow_aanvrager > 0:
                    col_rows.append({"label": "  AOW-uitkering", "value": format_bedrag(aow_aanvrager), "sub": True})
                if aanvrager_op_aow and pensioen_aanvrager > 0:
                    col_rows.append({"label": "  Pensioen", "value": format_bedrag(pensioen_aanvrager), "sub": True})
            if ink_partner > 0 and data.partner:
                col_rows.append({
                    "label": f"Inkomen {data.partner.naam}",
                    "value": format_bedrag(ink_partner),
                    "sub": True,
                })
                if partner_op_aow and aow_partner > 0:
                    col_rows.append({"label": "  AOW-uitkering", "value": format_bedrag(aow_partner), "sub": True})
                if partner_op_aow and pensioen_partner > 0:
                    col_rows.append({"label": "  Pensioen", "value": format_bedrag(pensioen_partner), "sub": True})

            col_rows.append({
                "label": "Totaal inkomen",
                "value": format_bedrag(totaal),
                "bold": True,
            })
            col_rows.append({"label": "", "value": ""})
            col_rows.append({
                "label": "Maximale hypotheek",
                "value": format_bedrag(sc.get("max_hypotheek_annuitair", 0)),
                "sub": True,
            })

            columns.append({"title": naam, "rows": col_rows})

        align_columns_at_totaal(columns)

        section = {
            "id": "retirement",
            "title": "Pensioen",
            "visible": True,
            "narratives": narratives,
            "columns": columns,
            "conclusion": conclusion,
        }

    if pensioen_chart_data:
        section["chart_data"] = pensioen_chart_data

    return section
