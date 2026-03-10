"""Pensioen sectie — AOW-scenario's met chart data."""

from adviesrapport_v2.field_mapper import NormalizedDossierData
from adviesrapport_v2.formatters import format_bedrag


def build_retirement_section(
    data: NormalizedDossierData,
    aow_scenarios: list[dict],
    pensioen_chart_data: dict | None,
    max_hypotheek_huidig: float,
) -> dict:
    """Bouw de pensioen sectie.

    Args:
        data: Genormaliseerde dossier data
        aow_scenarios: Resultaat van bereken_aow_scenarios()["scenarios"]
        pensioen_chart_data: Chart data met jaren + max hypotheek + restschuld
        max_hypotheek_huidig: Huidige max hypotheek (voor vergelijking)
    """
    hypotheek = data.hypotheek_bedrag

    # Narratives
    narratives = [
        "Wij hebben gekeken naar uw verwachte inkomenssituatie na "
        "pensionering op basis van de bij ons bekende pensioeninformatie.",
    ]

    # Bepaal of hypotheek onder water komt
    scenario_tekorten = []
    for sc in aow_scenarios:
        max_hyp = sc.get("max_hypotheek_annuitair", 0)
        if hypotheek > max_hyp:
            scenario_tekorten.append(sc)

    if scenario_tekorten:
        narratives.append(
            "Na pensionering daalt de maximale hypotheek onder het geadviseerde "
            "hypotheekbedrag. Wij adviseren om de gevolgen hiervan bewust mee "
            "te nemen in uw financiële planning."
        )

    # Columns voor stel, rows voor alleenstaand
    if data.alleenstaand:
        # Alleenstaand: rows met inkomen na AOW
        rows = []
        for sc in aow_scenarios:
            naam = sc.get("naam", "AOW")
            rows.append({
                "label": f"Inkomen na {naam}",
                "value": format_bedrag(sc.get("inkomen_aanvrager", 0) + sc.get("inkomen_partner", 0)),
                "bold": True,
            })
            if sc.get("inkomen_aanvrager", 0) > 0:
                rows.append({
                    "label": f"Inkomen {data.aanvrager.naam or 'aanvrager'}",
                    "value": format_bedrag(sc["inkomen_aanvrager"]),
                    "sub": True,
                })
            rows.append({
                "label": f"Maximale hypotheek na AOW",
                "value": format_bedrag(sc.get("max_hypotheek_annuitair", 0)),
            })

        section = {
            "id": "retirement",
            "title": "Pensioen",
            "visible": True,
            "narratives": narratives,
            "rows": rows,
        }
    else:
        # Stel: columns per AOW-moment
        columns = []
        for sc in aow_scenarios:
            naam = sc.get("naam", "AOW")
            col_rows = []

            # Inkomens-breakdown
            ink_aanvrager = sc.get("inkomen_aanvrager", 0)
            ink_partner = sc.get("inkomen_partner", 0)
            totaal = ink_aanvrager + ink_partner

            if ink_aanvrager > 0:
                col_rows.append({
                    "label": f"Inkomen {data.aanvrager.naam}",
                    "value": format_bedrag(ink_aanvrager),
                    "sub": True,
                })
            if ink_partner > 0:
                col_rows.append({
                    "label": f"Inkomen {data.partner.naam}",
                    "value": format_bedrag(ink_partner),
                    "sub": True,
                })
            col_rows.append({
                "label": "Totaal inkomen",
                "value": format_bedrag(totaal),
                "bold": True,
            })
            col_rows.append({"label": "", "value": ""})  # Spacer
            col_rows.append({
                "label": "Maximale hypotheek",
                "value": format_bedrag(sc.get("max_hypotheek_annuitair", 0)),
                "sub": True,
            })

            columns.append({"title": naam, "rows": col_rows})

        section = {
            "id": "retirement",
            "title": "Pensioen",
            "visible": True,
            "narratives": narratives,
            "columns": columns,
        }

    # Chart data
    if pensioen_chart_data:
        section["chart_data"] = pensioen_chart_data

    # Advisor note
    if scenario_tekorten:
        section["advisor_note"] = (
            "Na pensionering daalt de maximale hypotheek onder het geadviseerde "
            "bedrag. Wij adviseren om extra aflossingen of aanvullende "
            "pensioenopbouw te overwegen."
        )

    return section
