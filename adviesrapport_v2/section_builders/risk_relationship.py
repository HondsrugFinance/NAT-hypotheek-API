"""Relatiebeëindiging sectie — alleen bij stel."""

from adviesrapport_v2.field_mapper import NormalizedDossierData
from adviesrapport_v2.formatters import format_bedrag
from adviesrapport_v2.scenario_status import derive_relationship_status
from adviesrapport_v2.texts import RELATIONSHIP_TEXT


def build_risk_relationship_section(
    data: NormalizedDossierData,
    max_hyp_aanvrager_alleen: float,
    max_hyp_partner_alleen: float,
    max_hypotheek_huidig: float,
    beschikbare_buffer: float = 0,
) -> dict | None:
    """Bouw de relatiebeëindiging sectie (alleen bij stel)."""
    if data.alleenstaand or not data.partner:
        return None

    hypotheek = data.totale_hypotheekschuld

    # --- Status derivatie ---
    status_result = derive_relationship_status(
        max_hyp_aanvrager=max_hyp_aanvrager_alleen,
        max_hyp_partner=max_hyp_partner_alleen,
        hypotheek=hypotheek,
        buffer=beschikbare_buffer,
    )

    # --- Narratives (intro) ---
    narratives = [RELATIONSHIP_TEXT["intro"]]

    # --- Conclusion: per-partner observaties + awareness + disclaimer ---
    aanvrager_ok = status_result["applicant_status"] == "affordable"
    partner_ok = status_result["partner_status"] == "affordable"

    analysis: list[str] = []
    if aanvrager_ok == partner_ok:
        # Beiden zelfde uitkomst → één gedeelde zin
        if aanvrager_ok:
            analysis.append(
                f"Bij relatiebeëindiging kan zowel {data.aanvrager.korte_naam} als "
                f"{data.partner.korte_naam} de hypotheek op basis van deze berekening "
                f"blijven betalen."
            )
        else:
            analysis.append(
                f"Bij relatiebeëindiging kan zowel {data.aanvrager.korte_naam} als "
                f"{data.partner.korte_naam} de hypotheek op basis van deze berekening "
                f"niet zelfstandig betalen."
            )
    else:
        # Ongelijke uitkomst → per-partner zinnen
        for naam, can_afford in [
            (data.aanvrager.korte_naam, aanvrager_ok),
            (data.partner.korte_naam, partner_ok),
        ]:
            if can_afford:
                analysis.append(
                    f"Bij relatiebeëindiging kan {naam} de hypotheek op basis "
                    f"van deze berekening blijven betalen."
                )
            else:
                analysis.append(
                    f"Bij relatiebeëindiging kan {naam} de hypotheek op basis "
                    f"van deze berekening niet zelfstandig betalen."
                )

    # Awareness toevoegen
    analysis.append(RELATIONSHIP_TEXT["advice"]["awareness_only"])

    conclusion = [" ".join(analysis)]

    # Disclaimer
    if RELATIONSHIP_TEXT.get("disclaimer"):
        conclusion.append(RELATIONSHIP_TEXT["disclaimer"])

    # --- Columns ---
    columns = [
        {
            "title": f"{data.aanvrager.titel_naam} alleen",
            "rows": [
                {"label": "Resterend inkomen", "value": format_bedrag(data.inkomen_aanvrager_huidig), "bold": True},
                {"label": f"Inkomen {data.aanvrager.korte_naam}", "value": format_bedrag(data.inkomen_aanvrager_huidig), "sub": True},
                {"label": "Maximale hypotheek", "value": format_bedrag(max_hyp_aanvrager_alleen), "sub": True},
            ],
            "chart_data": {
                "type": "overlijden_vergelijk",
                "huidig_max_hypotheek": max_hypotheek_huidig,
                "max_hypotheek_na_overlijden": max_hyp_aanvrager_alleen,
                "geadviseerd_hypotheekbedrag": hypotheek,
                "label_bar1": "Huidig",
                "label_bar2": "Na scheiding",
            },
        },
        {
            "title": f"{data.partner.titel_naam} alleen",
            "rows": [
                {"label": "Resterend inkomen", "value": format_bedrag(data.inkomen_partner_huidig), "bold": True},
                {"label": f"Inkomen {data.partner.korte_naam}", "value": format_bedrag(data.inkomen_partner_huidig), "sub": True},
                {"label": "Maximale hypotheek", "value": format_bedrag(max_hyp_partner_alleen), "sub": True},
            ],
            "chart_data": {
                "type": "overlijden_vergelijk",
                "huidig_max_hypotheek": max_hypotheek_huidig,
                "max_hypotheek_na_overlijden": max_hyp_partner_alleen,
                "geadviseerd_hypotheekbedrag": hypotheek,
                "label_bar1": "Huidig",
                "label_bar2": "Na scheiding",
            },
        },
    ]

    return {
        "id": "risk-relationship",
        "title": "Relatiebeëindiging",
        "visible": True,
        "narratives": narratives,
        "columns": columns,
        "conclusion": conclusion,
    }
