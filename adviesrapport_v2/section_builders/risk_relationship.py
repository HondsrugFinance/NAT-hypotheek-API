"""Relatiebeëindiging sectie — alleen bij stel."""

from adviesrapport_v2.field_mapper import NormalizedDossierData
from adviesrapport_v2.formatters import format_bedrag


def build_risk_relationship_section(
    data: NormalizedDossierData,
    max_hyp_aanvrager_alleen: float,
    max_hyp_partner_alleen: float,
    max_hypotheek_huidig: float,
) -> dict | None:
    """Bouw de relatiebeëindiging sectie (alleen bij stel).

    Args:
        data: Genormaliseerde dossier data
        max_hyp_aanvrager_alleen: Max hypotheek aanvrager als alleenstaande
        max_hyp_partner_alleen: Max hypotheek partner als alleenstaande
        max_hypotheek_huidig: Huidige max hypotheek (samen)

    Returns:
        None als alleenstaand, anders de sectie dict.
    """
    if data.alleenstaand or not data.partner:
        return None

    hypotheek = data.hypotheek_bedrag

    narratives = [
        "Bij relatiebeëindiging valt het inkomen van de partner weg. "
        "Er is geen recht op nabestaandenpensioen.",
    ]

    columns = [
        {
            "title": f"{data.aanvrager.naam} alleen",
            "rows": [
                {"label": "Resterend inkomen", "value": format_bedrag(data.inkomen_aanvrager_huidig), "bold": True},
                {"label": f"Inkomen {data.aanvrager.naam}", "value": format_bedrag(data.inkomen_aanvrager_huidig), "sub": True},
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
            "title": f"{data.partner.naam} alleen",
            "rows": [
                {"label": "Resterend inkomen", "value": format_bedrag(data.inkomen_partner_huidig), "bold": True},
                {"label": f"Inkomen {data.partner.naam}", "value": format_bedrag(data.inkomen_partner_huidig), "sub": True},
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

    section = {
        "id": "risk-relationship",
        "title": "Relatiebeëindiging",
        "visible": True,
        "narratives": narratives,
        "columns": columns,
    }

    # Advisor note
    min_hyp = min(max_hyp_aanvrager_alleen, max_hyp_partner_alleen)
    if min_hyp < hypotheek:
        section["advisor_note"] = (
            "Bij relatiebeëindiging moet de hypotheek door één inkomen "
            "gedragen worden. Partneralimentatie kan het inkomen "
            "aanvullen maar is niet gegarandeerd op lange termijn."
        )

    return section
