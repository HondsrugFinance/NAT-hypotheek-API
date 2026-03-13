"""Pensioen sectie — AOW-scenario's met chart data."""

import re

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
    beschikbare_buffer: float = 0,
) -> dict:
    """Bouw de pensioen sectie."""
    hypotheek = data.hypotheek_bedrag

    # --- Status derivatie ---
    status_result = derive_retirement_status(
        aow_scenarios=aow_scenarios,
        hypotheek=hypotheek,
        buffer=beschikbare_buffer,
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

    # --- Buffer nuance ---
    # Bereken max tekort over alle scenarios
    _max_tekort_pensioen = 0
    for sc in aow_scenarios:
        _max_hyp = max(sc.get("max_hypotheek_annuitair", 0), sc.get("max_hypotheek_niet_annuitair", 0))
        _schuld = sc.get("restschuld_op_peildatum", hypotheek)
        if _schuld > 0 and _schuld > _max_hyp:
            _max_tekort_pensioen = max(_max_tekort_pensioen, _schuld - _max_hyp)
    buffer_dekt_alles = beschikbare_buffer > 0 and _max_tekort_pensioen > 0 and beschikbare_buffer >= _max_tekort_pensioen
    buffer_dekt_deels = beschikbare_buffer > 0 and _max_tekort_pensioen > 0 and not buffer_dekt_alles

    nuance_keys = compact_keys(
        ("couple_two_aow", has_partner),
        ("income_decrease", pension_income_total < gross_income_total),
        ("annuity_income_used", has_annuity_income),
        ("buffer_covers_shortfall", buffer_dekt_alles),
        ("buffer_partial", buffer_dekt_deels),
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

    voornaam_a = data.aanvrager.korte_naam
    voornaam_p = data.partner.korte_naam if data.partner else "Partner"
    overig_a = data.aanvrager.inkomen.overig
    overig_p = data.partner.inkomen.overig if data.partner else 0

    if data.alleenstaand:
        rows = []
        for sc in aow_scenarios:
            naam = sc.get("naam", "AOW")
            naam = re.sub(r'\baanvrager\b', data.aanvrager.titel_naam, naam, flags=re.IGNORECASE)
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
            if overig_a > 0:
                rows.append({"label": f"Inkomen {voornaam_a}", "value": format_bedrag(overig_a), "sub": True})
            if aow_aanvrager == 0 and pensioen_aanvrager == 0 and overig_a == 0 and sc.get("inkomen_aanvrager", 0) > 0:
                rows.append({
                    "label": f"Inkomen {voornaam_a}",
                    "value": format_bedrag(sc["inkomen_aanvrager"]),
                    "sub": True,
                })
            rows.append({"label": "", "value": ""})
            max_hyp = max(
                0,
                sc.get("max_hypotheek_annuitair", 0),
                sc.get("max_hypotheek_niet_annuitair", 0),
            )
            rows.append({
                "label": "Maximale hypotheek na AOW",
                "value": format_bedrag(max_hyp),
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
            raw_naam = sc.get("naam", "AOW")
            raw_lower = raw_naam.lower()
            # Display-naam: vervang "aanvrager"/"partner" door echte namen
            naam = re.sub(r'\baanvrager\b', data.aanvrager.titel_naam, raw_naam, flags=re.IGNORECASE)
            if data.partner:
                naam = re.sub(r'\bpartner\b', data.partner.titel_naam, naam, flags=re.IGNORECASE)
            col_rows = []

            ink_aanvrager = sc.get("inkomen_aanvrager", 0)
            ink_partner = sc.get("inkomen_partner", 0)
            totaal = ink_aanvrager + ink_partner

            aanvrager_op_aow = "aanvrager" in raw_lower or "partner" in raw_lower
            partner_op_aow = "partner" in raw_lower

            if aanvrager_op_aow:
                if aow_aanvrager > 0:
                    col_rows.append({"label": f"AOW-uitkering {voornaam_a}", "value": format_bedrag(aow_aanvrager), "sub": True})
                if pensioen_aanvrager > 0:
                    col_rows.append({"label": f"Pensioen {voornaam_a}", "value": format_bedrag(pensioen_aanvrager), "sub": True})
                if overig_a > 0:
                    col_rows.append({"label": f"Inkomen {voornaam_a}", "value": format_bedrag(overig_a), "sub": True})
            elif ink_aanvrager > 0:
                col_rows.append({
                    "label": f"Inkomen {voornaam_a}",
                    "value": format_bedrag(ink_aanvrager),
                    "sub": True,
                })
            if data.partner:
                if partner_op_aow:
                    if aow_partner > 0:
                        col_rows.append({"label": f"AOW-uitkering {voornaam_p}", "value": format_bedrag(aow_partner), "sub": True})
                    if pensioen_partner > 0:
                        col_rows.append({"label": f"Pensioen {voornaam_p}", "value": format_bedrag(pensioen_partner), "sub": True})
                    if overig_p > 0:
                        col_rows.append({"label": f"Inkomen {voornaam_p}", "value": format_bedrag(overig_p), "sub": True})
                elif ink_partner > 0:
                    col_rows.append({
                        "label": f"Inkomen {voornaam_p}",
                        "value": format_bedrag(ink_partner),
                        "sub": True,
                    })

            col_rows.append({
                "label": "Totaal inkomen",
                "value": format_bedrag(totaal),
                "bold": True,
            })
            col_rows.append({"label": "", "value": ""})
            max_hyp = max(
                0,
                sc.get("max_hypotheek_annuitair", 0),
                sc.get("max_hypotheek_niet_annuitair", 0),
            )
            col_rows.append({
                "label": "Maximale hypotheek",
                "value": format_bedrag(max_hyp),
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
