"""Overlijden sectie — alleen bij stel."""

from adviesrapport_v2.field_mapper import NormalizedDossierData
from adviesrapport_v2.formatters import format_bedrag


def build_risk_death_section(
    data: NormalizedDossierData,
    overlijden_scenarios: list[dict],
    max_hypotheek_huidig: float,
) -> dict:
    """Bouw de overlijden sectie.

    Args:
        data: Genormaliseerde dossier data
        overlijden_scenarios: Resultaat van risk_scenarios met categorie "overlijden"
        max_hypotheek_huidig: Huidige max hypotheek
    """
    hypotheek = data.hypotheek_bedrag

    # Alleenstaand: kort verhaal
    if data.alleenstaand:
        return {
            "id": "risk-death",
            "title": "Overlijden",
            "visible": True,
            "narratives": [
                "Bij overlijden ontstaat geen financieel risico voor een partner.",
            ],
            "advisor_note": "U bent alleenstaand. Bij overlijden wordt de woning "
                            "onderdeel van de nalatenschap.",
        }

    # Stel: per partner een column
    narratives = [
        "Bij overlijden van één van de partners daalt het "
        "huishoudinkomen. Hieronder de gevolgen per scenario.",
    ]

    columns = []
    tekorten = []

    for sc in overlijden_scenarios:
        naam = sc.get("naam", "Overlijden")
        van_toepassing_op = sc.get("van_toepassing_op", "")
        anw_details = sc.get("anw_details") or {}

        # Wie overlijdt? → resterend inkomen is van de nabestaande
        nabestaande_inkomen = sc.get("inkomen_aanvrager", 0) + sc.get("inkomen_partner", 0)
        max_hyp = sc.get("max_hypotheek_annuitair", 0)

        # Bepaal naam nabestaande
        if van_toepassing_op == "aanvrager":
            nabestaande_naam = data.partner.naam if data.partner else "Partner"
        else:
            nabestaande_naam = data.aanvrager.naam

        col_rows = [
            {"label": f"Totaal inkomen {nabestaande_naam}", "value": format_bedrag(nabestaande_inkomen), "bold": True},
        ]

        # Fix 10: Gedetailleerde breakdown uit anw_details
        eigen_inkomen = anw_details.get("eigen_inkomen_jaar", 0)
        nabestaandenpensioen = anw_details.get("nabestaandenpensioen_jaar", 0)
        anw_bruto = anw_details.get("anw_bruto_jaar", 0)

        if eigen_inkomen > 0:
            col_rows.append({"label": f"Inkomen uit loondienst", "value": format_bedrag(eigen_inkomen), "sub": True})
        if nabestaandenpensioen > 0:
            col_rows.append({"label": "Nabestaandenpensioen", "value": format_bedrag(nabestaandenpensioen), "sub": True})
        if anw_bruto > 0:
            col_rows.append({"label": "ANW-uitkering", "value": format_bedrag(anw_bruto), "sub": True})

        # Fallback: als geen anw_details, toon oude breakdown
        if not anw_details:
            if sc.get("inkomen_aanvrager", 0) > 0 and van_toepassing_op != "aanvrager":
                col_rows.append({"label": f"Inkomen {data.aanvrager.naam}", "value": format_bedrag(sc["inkomen_aanvrager"]), "sub": True})
            if sc.get("inkomen_partner", 0) > 0 and van_toepassing_op != "partner":
                col_rows.append({"label": f"Inkomen {data.partner.naam}", "value": format_bedrag(sc["inkomen_partner"]), "sub": True})

        col_rows.append({"label": "", "value": ""})  # Spacer
        col_rows.append({"label": "Maximale hypotheek", "value": format_bedrag(max_hyp), "sub": True})

        chart_data = {
            "type": "overlijden_vergelijk",
            "huidig_max_hypotheek": max_hypotheek_huidig,
            "max_hypotheek_na_overlijden": max_hyp,
            "geadviseerd_hypotheekbedrag": hypotheek,
        }

        columns.append({"title": naam, "rows": col_rows, "chart_data": chart_data})

        if hypotheek > max_hyp:
            tekort = hypotheek - max_hyp
            tekorten.append((naam, tekort))

    section = {
        "id": "risk-death",
        "title": "Overlijden",
        "visible": True,
        "narratives": narratives,
        "columns": columns,
    }

    if tekorten:
        grootste = max(tekorten, key=lambda x: x[1])
        section["advisor_note"] = (
            f"Bij {grootste[0].lower()} ontstaat een tekort van "
            f"{format_bedrag(grootste[1])}. Wij adviseren een "
            "overlijdensrisicoverzekering (ORV) te overwegen."
        )

    return section
