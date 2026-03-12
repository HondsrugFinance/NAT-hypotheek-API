"""Arbeidsongeschiktheid sectie — AO-scenario's per persoon."""

import re

from adviesrapport_v2.field_mapper import NormalizedDossierData
from adviesrapport_v2.formatters import format_bedrag
from adviesrapport_v2.scenario_status import derive_disability_status
from adviesrapport_v2.section_builders._align import align_columns_at_totaal
from adviesrapport_v2.texts import (
    DISABILITY_TEXT,
    compact_keys,
    render_standard_scenario,
)


def build_risk_disability_section(
    data: NormalizedDossierData,
    ao_scenarios: list[dict],
    max_hypotheek_huidig: float,
    ao_percentage: float = 50,
    benutting_rvc: float = 50,
) -> dict:
    """Bouw de arbeidsongeschiktheid sectie."""
    hypotheek = data.hypotheek_bedrag

    # --- Verzekeringen ---
    aov_list = [v for v in (data.verzekeringen or []) if "arbeidsongeschikt" in v.type.lower()]
    has_aov = len(aov_list) > 0

    # --- Groepeer scenarios per persoon ---
    personen = {}
    for sc in ao_scenarios:
        vta = sc.get("van_toepassing_op", "aanvrager")
        if vta not in personen:
            personen[vta] = []
        personen[vta].append(sc)

    # --- Per-partner vergelijking ---
    per_partner_shortfall = []
    partner_names = []
    for persoon_key, scenarios in personen.items():
        naam = data.aanvrager.korte_naam if persoon_key == "aanvrager" else (data.partner.korte_naam if data.partner else "Partner")
        partner_names.append(naam)
        # Slechtste fase (laagste max_hypotheek, skip loondoorbetaling)
        worst_max_hyp = min(
            (sc.get("max_hypotheek_annuitair", 0) for sc in scenarios
             if "loondoorbetaling" not in sc.get("naam", "").lower()),
            default=0,
        )
        per_partner_shortfall.append(worst_max_hyp < hypotheek)

    # --- Status derivatie (datagedreven) ---
    status_result = derive_disability_status(
        has_aov=has_aov,
        per_partner_shortfall=per_partner_shortfall,
    )

    # --- Nuance keys ---
    nuance_keys = compact_keys(
        ("aov_used", has_aov),
    )

    # --- Analysis sentences (alleen bij ongelijke uitkomst bij stel) ---
    analysis_sentences = None
    has_mixed_outcomes = not data.alleenstaand and len(per_partner_shortfall) == 2 and per_partner_shortfall[0] != per_partner_shortfall[1]
    if has_mixed_outcomes:
        advice_key = "refer_to_specialist_existing" if has_aov else "refer_to_specialist"
        analysis_sentences = []
        for naam, has_shortfall in zip(partner_names, per_partner_shortfall):
            if has_shortfall:
                analysis_sentences.append(
                    f"Bij arbeidsongeschiktheid van {naam} ontstaat er op basis van deze berekening "
                    f"een financieel tekort."
                )
                analysis_sentences.append(DISABILITY_TEXT["advice"][advice_key])
            else:
                analysis_sentences.append(
                    f"Bij arbeidsongeschiktheid van {naam} blijft de hypotheek "
                    f"op basis van deze berekening betaalbaar."
                )
                analysis_sentences.append(DISABILITY_TEXT["advice"]["no_action"])

    # --- Render teksten ---
    all_paragraphs = render_standard_scenario(
        text=DISABILITY_TEXT,
        status=status_result["status"],
        advice_type=status_result["advice_type"],
        nuance_keys=nuance_keys,
        analysis_sentences=analysis_sentences,
        include_advice=not has_mixed_outcomes,
    )
    narratives = all_paragraphs[:1]

    # Uitgangspunten per inkomenstype
    aanvrager_is_ondernemer = (
        data.aanvrager.inkomen.onderneming > 0
        and data.aanvrager.inkomen.loondienst == 0
    )
    partner_is_ondernemer = (
        data.partner is not None
        and data.partner.inkomen.onderneming > 0
        and data.partner.inkomen.loondienst == 0
    )

    if data.alleenstaand or data.partner is None:
        # Alleenstaand → één zin
        rvc = 100 if aanvrager_is_ondernemer else int(benutting_rvc)
        uitgangspunten = (
            f"Voor de berekening zijn wij uitgegaan van een {int(ao_percentage)}% "
            f"arbeidsongeschiktheid en {rvc}% benutten van de "
            f"restverdiencapaciteit."
        )
    elif aanvrager_is_ondernemer == partner_is_ondernemer:
        # Beiden zelfde type → één gedeelde zin
        rvc = 100 if aanvrager_is_ondernemer else int(benutting_rvc)
        uitgangspunten = (
            f"Voor de berekening zijn wij uitgegaan van een {int(ao_percentage)}% "
            f"arbeidsongeschiktheid en {rvc}% benutten van de "
            f"restverdiencapaciteit."
        )
    else:
        # Mixed: per-persoon zinnen
        rvc_a = 100 if aanvrager_is_ondernemer else int(benutting_rvc)
        rvc_p = 100 if partner_is_ondernemer else int(benutting_rvc)
        uitgangspunten = (
            f"Voor {data.aanvrager.voornaam} zijn wij uitgegaan van een {int(ao_percentage)}% "
            f"arbeidsongeschiktheid en {rvc_a}% benutten van de restverdiencapaciteit. "
            f"Voor {data.partner.voornaam} zijn wij uitgegaan van een {int(ao_percentage)}% "
            f"arbeidsongeschiktheid en {rvc_p}% benutten van de restverdiencapaciteit."
        )

    narratives[0] = narratives[0] + " " + uitgangspunten

    conclusion = all_paragraphs[1:]

    # Specialist-disclaimer bij advies tot onderzoek
    if status_result["status"] != "affordable":
        conclusion.append(
            "Wij bemiddelen niet in voorzieningen voor arbeidsongeschiktheid. "
            "Raadpleeg hiervoor een externe specialist."
        )

    columns = []
    for persoon_key, scenarios in personen.items():
        if persoon_key == "aanvrager":
            titel = f"Arbeidsongeschiktheid - {data.aanvrager.titel_naam}" if not data.alleenstaand else data.aanvrager.titel_naam
        else:
            titel = f"Arbeidsongeschiktheid - {data.partner.titel_naam}" if data.partner else "Partner"

        col_rows = []
        fasen = [{"label": "Huidig", "max_hypotheek": max_hypotheek_huidig}]

        for sc in scenarios:
            naam = sc.get("naam", "")

            # Loondoorbetaling overslaan
            if "loondoorbetaling" in naam.lower():
                continue

            inkomen = sc.get("inkomen_aanvrager", 0) + sc.get("inkomen_partner", 0)
            max_hyp = sc.get("max_hypotheek_annuitair", 0)

            fase_label = _extract_fase_label(naam)

            col_rows.append({"label": fase_label, "value": format_bedrag(inkomen), "bold": True})

            if sc.get("inkomen_aanvrager", 0) > 0:
                col_rows.append({
                    "label": f"Inkomen {data.aanvrager.korte_naam}",
                    "value": format_bedrag(sc["inkomen_aanvrager"]),
                    "sub": True,
                })
            if data.partner and sc.get("inkomen_partner", 0) > 0:
                col_rows.append({
                    "label": f"Inkomen {data.partner.korte_naam}",
                    "value": format_bedrag(sc["inkomen_partner"]),
                    "sub": True,
                })
            col_rows.append({"label": "", "value": ""})

            fasen.append({"label": fase_label, "max_hypotheek": max_hyp})

        chart_data = {
            "type": "vergelijk_fasen",
            "fasen": fasen,
            "geadviseerd_hypotheekbedrag": hypotheek,
        }

        columns.append({"title": titel, "rows": col_rows, "chart_data": chart_data})

    align_columns_at_totaal(columns)

    return {
        "id": "risk-disability",
        "title": "Arbeidsongeschiktheid",
        "visible": True,
        "narratives": narratives,
        "columns": columns,
        "conclusion": conclusion,
    }


def _extract_fase_label(scenario_naam: str) -> str:
    """Haal fase-label uit scenario naam.

    'AO aanvrager — WGA loongerelateerd' → 'WGA loongerelateerd'
    """
    cleaned = re.sub(r'^AO\s+(aanvrager|partner)\s*[—–\-]\s*', '', scenario_naam, flags=re.IGNORECASE)
    cleaned = cleaned.strip()
    if cleaned:
        return cleaned[0].upper() + cleaned[1:]
    return scenario_naam
