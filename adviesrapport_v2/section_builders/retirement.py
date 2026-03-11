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

    # Fix 9: Pensioen breakdown — toon AOW/pensioen uitsplitsing per persoon
    # Haal AOW en pensioen apart uit de NormalizedInkomen als beschikbaar
    aow_aanvrager = data.aanvrager.inkomen.aow_uitkering
    pensioen_aanvrager = data.aanvrager.inkomen.pensioen
    aow_partner = data.partner.inkomen.aow_uitkering if data.partner else 0
    pensioen_partner = data.partner.inkomen.pensioen if data.partner else 0

    if data.alleenstaand:
        # Alleenstaand: rows met inkomen na AOW
        rows = []
        for sc in aow_scenarios:
            naam = sc.get("naam", "AOW")
            ink_totaal = sc.get("inkomen_aanvrager", 0) + sc.get("inkomen_partner", 0)
            rows.append({
                "label": f"Totaal inkomen na {naam}",
                "value": format_bedrag(ink_totaal),
                "bold": True,
            })
            # Breakdown: AOW en pensioen apart als beschikbaar
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
            rows.append({"label": "", "value": ""})  # Spacer
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
        }
    else:
        # Stel: columns per AOW-moment
        columns = []
        for sc in aow_scenarios:
            naam = sc.get("naam", "AOW")
            col_rows = []

            ink_aanvrager = sc.get("inkomen_aanvrager", 0)
            ink_partner = sc.get("inkomen_partner", 0)
            totaal = ink_aanvrager + ink_partner

            # Per-persoon breakdown met AOW/pensioen uitsplitsing
            if ink_aanvrager > 0:
                col_rows.append({
                    "label": f"Inkomen {data.aanvrager.naam}",
                    "value": format_bedrag(ink_aanvrager),
                    "sub": True,
                })
                if aow_aanvrager > 0:
                    col_rows.append({"label": "  AOW-uitkering", "value": format_bedrag(aow_aanvrager), "sub": True})
                if pensioen_aanvrager > 0:
                    col_rows.append({"label": "  Pensioen", "value": format_bedrag(pensioen_aanvrager), "sub": True})
            if ink_partner > 0 and data.partner:
                col_rows.append({
                    "label": f"Inkomen {data.partner.naam}",
                    "value": format_bedrag(ink_partner),
                    "sub": True,
                })
                if aow_partner > 0:
                    col_rows.append({"label": "  AOW-uitkering", "value": format_bedrag(aow_partner), "sub": True})
                if pensioen_partner > 0:
                    col_rows.append({"label": "  Pensioen", "value": format_bedrag(pensioen_partner), "sub": True})

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
