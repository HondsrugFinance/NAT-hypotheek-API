"""Samenvatting sectie — highlights, scenario checks, advies tekst."""

from adviesrapport_v2.field_mapper import NormalizedDossierData
from adviesrapport_v2.formatters import format_bedrag


def build_summary_section(
    data: NormalizedDossierData,
    max_hypotheek: float,
    netto_maandlast: float,
    bruto_maandlast: float,
    scenario_checks: list[dict],
    hypotheekverstrekker: str = "",
) -> dict:
    """Bouw de samenvatting sectie."""
    fin = data.financiering
    hypotheek = data.hypotheek_bedrag
    woningwaarde = fin.woningwaarde

    # Schuld-marktwaardeverhouding
    smv = (hypotheek / woningwaarde * 100) if woningwaarde > 0 else 0

    # Highlight status: warning als hypotheek > max
    hyp_status = "warning" if hypotheek > max_hypotheek else "ok"

    highlights = [
        {
            "label": "Hypotheek",
            "value": format_bedrag(hypotheek),
            "note": f"Verantwoord hypotheekbedrag: {format_bedrag(max_hypotheek)}",
            "status": hyp_status,
        },
        {
            "label": "Hypotheekverstrekker",
            "value": hypotheekverstrekker or fin.hypotheekverstrekker or "n.b.",
            "note": "Met NHG" if fin.nhg else "Zonder NHG",
            "status": "ok",
        },
        {
            "label": "Maandlast",
            "value": f"{format_bedrag(netto_maandlast)} netto",
            "note": f"Bruto: {format_bedrag(bruto_maandlast)}",
            "status": "ok",
        },
        {
            "label": "Woningwaarde",
            "value": format_bedrag(woningwaarde),
            "note": f"Schuld-marktwaardeverhouding {smv:.1f}%".replace(".", ","),
            "status": "ok",
        },
    ]

    # Aflosvorm-samenvatting
    aflosvormen = list(set(ld.aflosvorm_display for ld in data.leningdelen_voor_api))
    if len(aflosvormen) == 1:
        hypotheekvorm_tekst = f"{aflosvormen[0]}hypotheek"
    else:
        hypotheekvorm_tekst = f"Combinatie van {', '.join(a.lower() for a in aflosvormen[:-1])} en {aflosvormen[-1].lower()}"

    # RVP: pak de meest voorkomende
    rvps = [ld.rvp for ld in data.leningdelen_voor_api]
    rvp_mnd = max(set(rvps), key=rvps.count) if rvps else 120
    rvp_jaren = rvp_mnd // 12

    mortgage_summary = [
        {"label": "Hypotheekvorm", "value": hypotheekvorm_tekst},
        {"label": "Rentevastperiode", "value": f"{rvp_jaren} jaar"},
    ]

    # Narratives
    if data.alleenstaand:
        intro = (
            f"U wilt een hypotheek afsluiten voor {data.financiering.adres or 'de aangekochte woning'}."
        )
    else:
        intro = (
            f"U wilt samen een hypotheek afsluiten voor de aankoop van een "
            f"woning aan {data.financiering.adres or 'het opgegeven adres'}."
        )

    narratives = [
        intro,
        "Op basis van uw financiële situatie, uw wensen en de geldende "
        "leennormen hebben wij beoordeeld dat de geadviseerde financiering "
        "passend is binnen uw situatie.",
    ]
    if fin.nhg:
        narratives.append("De hypotheek wordt aangevraagd met Nationale Hypotheek Garantie.")

    return {
        "id": "summary",
        "title": "Samenvatting advies",
        "visible": True,
        "narratives": narratives,
        "highlights": highlights,
        "mortgage_summary": mortgage_summary,
        "scenario_checks": scenario_checks,
    }
