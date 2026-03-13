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
    hypotheek = data.totale_hypotheekschuld
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

    # Narratives — woningtype bepalen voor intro-zin
    is_nieuwbouw = "nieuwbouw" in fin.type_woning.lower() or "project" in fin.type_woning.lower()
    woning_label = "nieuwbouwwoning" if is_nieuwbouw else "woning"
    adres_tekst = data.financiering.adres
    has_adres = bool(adres_tekst and adres_tekst.strip(", "))
    samen = "" if data.alleenstaand else " samen"

    if fin.is_wijziging:
        # Wijziging flow: verhoging/oversluiting/uitkoop
        if has_adres:
            intro = f"U wilt{samen} een aanvullende hypotheek afsluiten op uw woning aan {adres_tekst}."
        else:
            intro = f"U wilt{samen} een aanvullende hypotheek afsluiten."
    elif data.alleenstaand:
        if has_adres:
            intro = f"U wilt een hypotheek afsluiten voor de aankoop van een {woning_label} aan {adres_tekst}."
        else:
            intro = f"U wilt een hypotheek afsluiten voor de aankoop van een {woning_label}."
    else:
        if has_adres:
            intro = (
                f"U wilt samen een hypotheek afsluiten voor de aankoop van een "
                f"{woning_label} aan {adres_tekst}."
            )
        else:
            intro = f"U wilt samen een hypotheek afsluiten voor de aankoop van een {woning_label}."

    # Advies en onderbouwing — specifieke advies-paragraaf
    verstrekker = hypotheekverstrekker or fin.hypotheekverstrekker or "de geldverstrekker"
    nhg_tekst = " met Nationale Hypotheek Garantie (NHG)" if fin.nhg else ""

    advies = (
        f"Wij adviseren een hypotheek van {format_bedrag(hypotheek)} bij {verstrekker}, "
        f"met {hypotheekvorm_tekst.lower()} als aflossingsvorm en een rentevaste periode "
        f"van {rvp_jaren} jaar{nhg_tekst}. "
        f"De bruto maandlast bedraagt {format_bedrag(bruto_maandlast)} en de netto maandlast "
        f"{format_bedrag(netto_maandlast)}."
    )

    verantwoord = (
        f"Op basis van de geldende leennormen is een verantwoord hypotheekbedrag van "
        f"{format_bedrag(max_hypotheek)} berekend. "
    )
    if hypotheek <= max_hypotheek:
        verantwoord += "Het geadviseerde hypotheekbedrag valt binnen deze norm."
    else:
        verantwoord += (
            f"Het geadviseerde hypotheekbedrag overschrijdt deze norm met "
            f"{format_bedrag(hypotheek - max_hypotheek)}."
        )

    narratives = [intro, advies, verantwoord]
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
