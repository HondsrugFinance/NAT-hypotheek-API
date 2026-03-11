"""Arbeidsongeschiktheid sectie — AO-scenario's per persoon."""

from adviesrapport_v2.field_mapper import NormalizedDossierData, NormalizedVerzekering
from adviesrapport_v2.formatters import format_bedrag


def build_risk_disability_section(
    data: NormalizedDossierData,
    ao_scenarios: list[dict],
    max_hypotheek_huidig: float,
    ao_percentage: float = 50,
    benutting_rvc: float = 50,
) -> dict:
    """Bouw de arbeidsongeschiktheid sectie.

    Args:
        data: Genormaliseerde dossier data
        ao_scenarios: AO-scenario's uit risk_scenarios (categorie "ao")
        max_hypotheek_huidig: Huidige max hypotheek
        ao_percentage: AO-percentage (bijv. 50)
        benutting_rvc: Benutting restverdiencapaciteit (bijv. 50)
    """
    hypotheek = data.hypotheek_bedrag

    narratives = []
    if data.alleenstaand:
        narratives.append(
            f"Wij hebben beoordeeld wat de gevolgen zijn als u {ao_percentage:.0f}% "
            f"arbeidsongeschikt raakt. Bij uw dienstverband ({data.aanvrager.dienstverband.lower()}) "
            f"gaan wij uit van {benutting_rvc:.0f}% benutting van de restverdiencapaciteit."
        )
    else:
        narratives.append(
            f"Wij hebben beoordeeld wat de gevolgen zijn als één van u "
            f"{ao_percentage:.0f}% arbeidsongeschikt raakt. Bij loondienst gaan wij uit van "
            f"{benutting_rvc:.0f}% benutting van de restverdiencapaciteit."
        )

    # Groepeer scenarios per persoon
    personen = {}
    for sc in ao_scenarios:
        vta = sc.get("van_toepassing_op", "aanvrager")
        if vta not in personen:
            personen[vta] = []
        personen[vta].append(sc)

    columns = []
    min_max_hyp = max_hypotheek_huidig

    for persoon_key, scenarios in personen.items():
        if persoon_key == "aanvrager":
            titel = f"Arbeidsongeschiktheid - {data.aanvrager.naam}" if not data.alleenstaand else data.aanvrager.naam
        else:
            titel = f"Arbeidsongeschiktheid - {data.partner.naam}" if data.partner else "Partner"

        col_rows = []
        fasen = [{"label": "Huidig", "max_hypotheek": max_hypotheek_huidig}]

        for sc in scenarios:
            naam = sc.get("naam", "")
            inkomen = sc.get("inkomen_aanvrager", 0) + sc.get("inkomen_partner", 0)
            max_hyp = sc.get("max_hypotheek_annuitair", 0)

            # Korte fase-naam
            fase_label = _extract_fase_label(naam)

            col_rows.append({"label": fase_label, "value": format_bedrag(inkomen), "bold": True})

            # Breakdown per persoon
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
            min_max_hyp = min(min_max_hyp, max_hyp)

        chart_data = {
            "type": "vergelijk_fasen",
            "fasen": fasen,
            "geadviseerd_hypotheekbedrag": hypotheek,
        }

        columns.append({"title": titel, "rows": col_rows, "chart_data": chart_data})

    section = {
        "id": "risk-disability",
        "title": "Arbeidsongeschiktheid",
        "visible": True,
        "narratives": narratives,
        "columns": columns,
    }

    # Bestaande AOV dekking
    aov_list = [v for v in (data.verzekeringen or []) if "arbeidsongeschikt" in v.type.lower()]

    # Advisor note als max hypotheek daalt
    if min_max_hyp < hypotheek:
        verschil = hypotheek - min_max_hyp
        if aov_list:
            aov_tekst = ", ".join(
                f"{v.aanbieder} ({format_bedrag(v.dekking)})" for v in aov_list
            )
            section["advisor_note"] = (
                f"Bij {ao_percentage:.0f}% AO daalt uw maximale hypotheek met "
                f"{format_bedrag(verschil)}. U heeft reeds een AOV afgesloten "
                f"bij {aov_tekst}. Controleer of de dekking voldoende is."
            )
        else:
            section["advisor_note"] = (
                f"Bij {ao_percentage:.0f}% AO daalt uw maximale hypotheek met "
                f"{format_bedrag(verschil)}. Een AOV-verzekering verdient overweging."
            )
    elif aov_list:
        aov_tekst = ", ".join(
            f"{v.aanbieder} ({format_bedrag(v.dekking)})" for v in aov_list
        )
        section["advisor_note"] = (
            f"U heeft een AOV afgesloten bij {aov_tekst}."
        )

    return section


def _extract_fase_label(scenario_naam: str) -> str:
    """Haal fase-label uit scenario naam.

    'AO aanvrager — WGA loongerelateerd' → 'WGA loongerelateerd'
    'AO partner — loondoorbetaling' → 'Loondoorbetaling'
    """
    import re
    # Verwijder prefix "AO aanvrager — " of "AO partner — "
    cleaned = re.sub(r'^AO\s+(aanvrager|partner)\s*[—–\-]\s*', '', scenario_naam, flags=re.IGNORECASE)
    cleaned = cleaned.strip()
    if cleaned:
        return cleaned[0].upper() + cleaned[1:]
    return scenario_naam
