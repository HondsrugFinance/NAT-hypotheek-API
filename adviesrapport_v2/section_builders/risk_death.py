"""Overlijden sectie — alleen bij stel."""

import re

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
    beschikbare_buffer: float = 0,
) -> dict:
    """Bouw de overlijden sectie."""
    hypotheek = data.totale_hypotheekschuld

    # Alleenstaand: LTV-perspectief (kan de hypotheek afgelost worden uit woningverkoop?)
    if data.alleenstaand:
        woningwaarde = data.financiering.woningwaarde or data.financiering.koopsom
        ltv = (hypotheek / woningwaarde * 100) if woningwaarde > 0 else 0

        if ltv <= 100:
            intro = (
                "Bij overlijden zal de woning verkocht moeten worden om de hypotheek af te lossen. "
                "Op basis van de huidige woningwaarde is de opbrengst voldoende om de volledige hypotheek af te lossen."
            )
            status_class = "ok"
        else:
            restschuld = hypotheek - woningwaarde
            intro = (
                f"Bij overlijden zal de woning verkocht moeten worden om de hypotheek af te lossen. "
                f"Op basis van de huidige woningwaarde resteert na verkoop een schuld van {format_bedrag(restschuld)}."
            )
            status_class = "warning"

        rows = [
            {"label": "Woningwaarde", "value": format_bedrag(woningwaarde)},
            {"label": "Hypotheek", "value": format_bedrag(hypotheek)},
            {"label": "Schuld-marktwaardeverhouding (LTV)", "value": f"{ltv:.1f}%", "bold": True},
        ]

        disclaimer = (
            "De woningwaarde is gebaseerd op de huidige marktwaarde. "
            "Toekomstige waardeontwikkelingen kunnen afwijken."
        )

        # Chart data: twee staven (woningwaarde vs hypotheek)
        chart_data = {
            "type": "comparison",
            "bars": [
                {"label": "Woningwaarde", "value": round(woningwaarde)},
                {"label": "Hypotheek", "value": round(hypotheek)},
            ],
            "hypotheek": round(hypotheek),
        }

        return {
            "id": "risk-death",
            "title": "Overlijden",
            "visible": True,
            "narratives": [intro],
            "rows": rows,
            "conclusion": [disclaimer],
            "chart_data": chart_data,
            "_status_class": status_class,
        }

    # --- Verzekeringen ---
    orv_list = [v for v in (data.verzekeringen or []) if "overlijden" in v.type.lower()]
    has_orv = len(orv_list) > 0
    has_life_insurance = any(
        "leven" in v.type.lower() for v in (data.verzekeringen or [])
    )

    # --- Per-partner vergelijking ---
    partner_results = []  # (naam_overledene, nabestaande_naam, has_shortfall)
    shortfall_amounts = []
    for sc in overlijden_scenarios:
        max_hyp = sc.get("max_hypotheek_annuitair", 0)
        vta = sc.get("van_toepassing_op", "")
        if vta == "aanvrager":
            naam_overledene = data.aanvrager.korte_naam
            naam_nabestaande = data.partner.korte_naam if data.partner else "Partner"
        else:
            naam_overledene = data.partner.korte_naam if data.partner else "Partner"
            naam_nabestaande = data.aanvrager.korte_naam
        tekort = max(0, hypotheek - max_hyp)
        partner_results.append((naam_overledene, naam_nabestaande, max_hyp < hypotheek))
        shortfall_amounts.append(tekort)

    per_partner_shortfall = [r[2] for r in partner_results]

    # --- Status derivatie (datagedreven) ---
    status_result = derive_death_status(
        has_partner=True,
        has_orv=has_orv,
        per_partner_shortfall=per_partner_shortfall,
        buffer=beschikbare_buffer,
        shortfall_amounts=shortfall_amounts,
    )

    # --- Analysis sentences (alleen bij ongelijke uitkomst) ---
    analysis_sentences = None
    buffer_used_inline = False
    has_mixed_outcomes = len(per_partner_shortfall) == 2 and per_partner_shortfall[0] != per_partner_shortfall[1]
    if has_mixed_outcomes:
        advice_key = "consider_solution_existing" if has_orv else "consider_solution"
        analysis_sentences = []
        for i, (naam_overledene, naam_nabestaande, has_shortfall) in enumerate(partner_results):
            if has_shortfall:
                analysis_sentences.append(
                    f"Bij overlijden van {naam_overledene} ontstaat er op basis van deze berekening "
                    f"een financieel tekort voor {naam_nabestaande}."
                )
                # Buffer dekt dit tekort → buffer-tekst vervangt verzekeringsadvies
                if shortfall_amounts[i] > 0 and beschikbare_buffer >= shortfall_amounts[i]:
                    analysis_sentences.append(DEATH_TEXT["nuance"]["buffer_covers_shortfall"])
                    buffer_used_inline = True
                else:
                    analysis_sentences.append(DEATH_TEXT["advice"][advice_key])
            else:
                analysis_sentences.append(
                    f"Bij overlijden van {naam_overledene} blijft de hypotheek "
                    f"op basis van deze berekening betaalbaar."
                )
                analysis_sentences.append(DEATH_TEXT["advice"]["no_action"])

    # --- Nuance keys ---
    max_tekort_dood = max(shortfall_amounts) if shortfall_amounts else 0
    buffer_dekt_alles = beschikbare_buffer > 0 and max_tekort_dood > 0 and beschikbare_buffer >= max_tekort_dood
    buffer_dekt_deels = beschikbare_buffer > 0 and max_tekort_dood > 0 and not buffer_dekt_alles

    nuance_keys = compact_keys(
        ("existing_orv", has_orv),
        ("existing_life_insurance", has_life_insurance),
        ("buffer_covers_shortfall", buffer_dekt_alles and not buffer_used_inline),
        ("buffer_partial", buffer_dekt_deels and not buffer_used_inline),
    )

    # --- Render teksten ---
    all_paragraphs = render_standard_scenario(
        text=DEATH_TEXT,
        status=status_result["status"],
        advice_type=status_result["advice_type"],
        nuance_keys=nuance_keys,
        analysis_sentences=analysis_sentences,
        include_advice=not has_mixed_outcomes,
    )
    narratives = all_paragraphs[:1]
    conclusion = all_paragraphs[1:]

    # --- Columns per scenario ---
    columns = []
    for sc in overlijden_scenarios:
        naam = sc.get("naam", "Overlijden")
        naam = re.sub(r'\baanvrager\b', data.aanvrager.titel_naam, naam, flags=re.IGNORECASE)
        if data.partner:
            naam = re.sub(r'\bpartner\b', data.partner.titel_naam, naam, flags=re.IGNORECASE)
        van_toepassing_op = sc.get("van_toepassing_op", "")
        anw_details = sc.get("anw_details") or {}

        nabestaande_inkomen = sc.get("inkomen_aanvrager", 0) + sc.get("inkomen_partner", 0)
        max_hyp = sc.get("max_hypotheek_annuitair", 0)

        if van_toepassing_op == "aanvrager":
            nabestaande_naam = data.partner.korte_naam if data.partner else "Partner"
        else:
            nabestaande_naam = data.aanvrager.korte_naam

        col_rows = [
            {"label": f"Totaal inkomen {nabestaande_naam}", "value": format_bedrag(nabestaande_inkomen), "bold": True},
        ]

        eigen_inkomen = anw_details.get("eigen_inkomen_jaar", 0)
        nabestaandenpensioen = anw_details.get("nabestaandenpensioen_jaar", 0)
        anw_bruto = anw_details.get("anw_bruto_jaar", 0)

        if eigen_inkomen > 0:
            col_rows.append({"label": f"Inkomen {nabestaande_naam}", "value": format_bedrag(eigen_inkomen), "sub": True})
        if nabestaandenpensioen > 0:
            col_rows.append({"label": "Nabestaandenpensioen", "value": format_bedrag(nabestaandenpensioen), "sub": True})
        if anw_bruto > 0:
            col_rows.append({"label": "ANW-uitkering", "value": format_bedrag(anw_bruto), "sub": True})

        if not anw_details:
            if sc.get("inkomen_aanvrager", 0) > 0 and van_toepassing_op != "aanvrager":
                col_rows.append({"label": f"Inkomen {data.aanvrager.korte_naam}", "value": format_bedrag(sc["inkomen_aanvrager"]), "sub": True})
            if sc.get("inkomen_partner", 0) > 0 and van_toepassing_op != "partner":
                col_rows.append({"label": f"Inkomen {data.partner.korte_naam}", "value": format_bedrag(sc["inkomen_partner"]), "sub": True})

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
