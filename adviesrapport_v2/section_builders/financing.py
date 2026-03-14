"""Financiering sectie — onderpand, financieringsopzet, hypotheekconstructie."""

from adviesrapport_v2.field_mapper import NormalizedDossierData
from adviesrapport_v2.formatters import (
    format_bedrag, format_percentage, format_looptijd_jaren, format_rvp_jaren,
)


def build_financing_section(
    data: NormalizedDossierData,
    bruto_maandlast: float = 0,
) -> dict:
    """Bouw de financiering sectie met subsections."""
    fin = data.financiering
    subsections = []

    # --- Onderpand ---
    onderpand_rows = []
    has_adres = bool(fin.adres and fin.adres.strip(", "))
    if has_adres:
        onderpand_rows.append({"label": "Adres", "value": fin.adres})
    onderpand_rows.append({"label": "Type woning", "value": fin.type_woning})
    # #66: Plannummer + bouwnummer (nieuwbouw)
    if fin.plannummer:
        onderpand_rows.append({"label": "Plannummer project", "value": fin.plannummer})
    if fin.bouwnummer:
        onderpand_rows.append({"label": "Bouwnummer onderpand", "value": fin.bouwnummer})
    onderpand_rows.append({"label": "Marktwaarde", "value": format_bedrag(fin.woningwaarde)})
    # #68: Marktwaarde na verbouwing (alleen als hoger dan gewone marktwaarde)
    if fin.marktwaarde_na_verbouwing > fin.woningwaarde:
        onderpand_rows.append({"label": "Marktwaarde na verbouwing", "value": format_bedrag(fin.marktwaarde_na_verbouwing)})
    if fin.woz_waarde > 0:
        onderpand_rows.append({"label": "WOZ-waarde", "value": format_bedrag(fin.woz_waarde)})
    onderpand_rows.append({"label": "Energielabel", "value": fin.energielabel})
    # #67: Erfpacht details onderpand
    if fin.erfpacht_onderpand:
        if fin.erfpachtcanon_onderpand > 0:
            onderpand_rows.append({"label": "Erfpacht", "value": f"Ja (canon {format_bedrag(fin.erfpachtcanon_onderpand)} p/j)"})
        else:
            onderpand_rows.append({"label": "Erfpacht", "value": "Ja"})
    # #70: Eigendomsverdeling (alleen als niet 50/50)
    if not (fin.eigendom_aanvrager == 50 and fin.eigendom_partner == 50):
        onderpand_rows.append({"label": "Eigendomsverdeling",
                               "value": f"{fin.eigendom_aanvrager:.0f}% / {fin.eigendom_partner:.0f}%"})
    subsections.append({"subtitle": "Onderpand", "rows": onderpand_rows})

    # --- Financieringsopzet ---
    opzet_rows = []
    is_nieuwbouw_project = "project" in fin.type_woning.lower()
    is_nieuwbouw_eigen_beheer = "eigen beheer" in fin.type_woning.lower()

    # Aankoopposten (afhankelijk van woningtype en flow)
    if fin.is_wijziging:
        # Wijziging flow: huidige hypotheek komt onderaan, niet bovenaan
        pass
    elif is_nieuwbouw_project:
        if fin.koopsom_grond > 0:
            opzet_rows.append({"label": "Koopsom grond", "value": format_bedrag(fin.koopsom_grond)})
        if fin.aanneemsom > 0:
            opzet_rows.append({"label": "Aanneemsom", "value": format_bedrag(fin.aanneemsom)})
        if fin.meerwerk > 0:
            opzet_rows.append({"label": "Meerwerk", "value": format_bedrag(fin.meerwerk)})
        if fin.bouwrente > 0:
            opzet_rows.append({"label": "Bouwrente", "value": format_bedrag(fin.bouwrente)})
        # Fallback: als geen deelposten maar wel koopsom
        if not opzet_rows and fin.koopsom > 0:
            opzet_rows.append({"label": "Koop-/aanneemsom", "value": format_bedrag(fin.koopsom)})
    elif is_nieuwbouw_eigen_beheer:
        if fin.koopsom_kavel > 0:
            opzet_rows.append({"label": "Koopsom kavel", "value": format_bedrag(fin.koopsom_kavel)})
        if fin.sloop_oude_woning > 0:
            opzet_rows.append({"label": "Sloop oude woning", "value": format_bedrag(fin.sloop_oude_woning)})
        if fin.bouw_woning > 0:
            opzet_rows.append({"label": "Bouw woning", "value": format_bedrag(fin.bouw_woning)})
        if fin.meerwerk > 0:
            opzet_rows.append({"label": "Meerwerk", "value": format_bedrag(fin.meerwerk)})
        if fin.bouwrente > 0:
            opzet_rows.append({"label": "Bouwrente", "value": format_bedrag(fin.bouwrente)})
        # Fallback
        if not opzet_rows and fin.koopsom > 0:
            opzet_rows.append({"label": "Aankoop", "value": format_bedrag(fin.koopsom)})
    else:
        # Bestaande bouw (aankoop)
        opzet_rows.append({"label": "Aankoop", "value": format_bedrag(fin.koopsom)})

    if fin.is_wijziging:
        # Wijziging volgorde: investering → kosten → custom (matcht Lovable)
        # Investering items
        if fin.verbouwing > 0:
            opzet_rows.append({"label": "Verbouwing", "value": format_bedrag(fin.verbouwing)})
        # EBV en EBB apart tonen
        if fin.ebv > 0:
            opzet_rows.append({"label": "EBV", "value": format_bedrag(fin.ebv)})
        if fin.ebb > 0:
            opzet_rows.append({"label": "EBB", "value": format_bedrag(fin.ebb)})
        if fin.afkoop_erfpacht > 0:
            opzet_rows.append({"label": "Afkoop erfpacht", "value": format_bedrag(fin.afkoop_erfpacht)})
        if fin.oversluiten_leningen > 0:
            opzet_rows.append({"label": "Oversluiten leningen", "value": format_bedrag(fin.oversluiten_leningen)})
        if fin.consumptief > 0:
            opzet_rows.append({"label": "Consumptief", "value": format_bedrag(fin.consumptief)})
        if fin.boeterente > 0:
            opzet_rows.append({"label": "Boeterente", "value": format_bedrag(fin.boeterente)})
        if fin.uitkoop_partner > 0:
            opzet_rows.append({"label": "Uitkoop partner", "value": format_bedrag(fin.uitkoop_partner)})
        # Extra posten aankoop/investering (custom)
        for ep in fin.extra_posten_aankoop:
            opzet_rows.append({"label": ep["label"], "value": format_bedrag(ep["value"])})
        # Kosten items
        if fin.advies_bemiddeling > 0:
            opzet_rows.append({"label": "Hypotheekadvies", "value": format_bedrag(fin.advies_bemiddeling)})
        if fin.taxatiekosten > 0:
            opzet_rows.append({"label": "Taxatiekosten", "value": format_bedrag(fin.taxatiekosten)})
        if fin.notariskosten > 0:
            opzet_rows.append({"label": "Notariskosten", "value": format_bedrag(fin.notariskosten)})
        if fin.nhg_kosten > 0:
            opzet_rows.append({"label": "NHG-premie", "value": format_bedrag(fin.nhg_kosten)})
        # Extra posten kosten (custom)
        for ep in fin.extra_posten_kosten:
            opzet_rows.append({"label": ep["label"], "value": format_bedrag(ep["value"])})
    else:
        # Aankoop volgorde (ongewijzigd)
        # Extra posten aankoop (custom)
        for ep in fin.extra_posten_aankoop:
            opzet_rows.append({"label": ep["label"], "value": format_bedrag(ep["value"])})

        # Individuele kostenposten (alleen tonen als > 0)
        if fin.overdrachtsbelasting > 0:
            opzet_rows.append({"label": "Overdrachtsbelasting", "value": format_bedrag(fin.overdrachtsbelasting)})
        if fin.notariskosten > 0:
            opzet_rows.append({"label": "Notariskosten", "value": format_bedrag(fin.notariskosten)})
        if fin.verbouwing > 0:
            opzet_rows.append({"label": "Verbouwing", "value": format_bedrag(fin.verbouwing)})
        if fin.ebv_ebb > 0:
            opzet_rows.append({"label": "EBB", "value": format_bedrag(fin.ebv_ebb)})
        if fin.consumptief > 0:
            opzet_rows.append({"label": "Consumptief", "value": format_bedrag(fin.consumptief)})
        if fin.aankoopmakelaar > 0:
            opzet_rows.append({"label": "Aankoopmakelaar", "value": format_bedrag(fin.aankoopmakelaar)})
        if fin.advies_bemiddeling > 0:
            opzet_rows.append({"label": "Hypotheekadvies", "value": format_bedrag(fin.advies_bemiddeling)})
        if fin.taxatiekosten > 0:
            opzet_rows.append({"label": "Taxatiekosten", "value": format_bedrag(fin.taxatiekosten)})
        if fin.bankgarantie > 0:
            opzet_rows.append({"label": "Bankgarantie", "value": format_bedrag(fin.bankgarantie)})
        if fin.nhg_kosten > 0:
            opzet_rows.append({"label": "NHG-premie", "value": format_bedrag(fin.nhg_kosten)})
        if fin.boeterente > 0:
            opzet_rows.append({"label": "Boeterente", "value": format_bedrag(fin.boeterente)})
        if fin.uitkoop_partner > 0:
            opzet_rows.append({"label": "Uitkoop partner", "value": format_bedrag(fin.uitkoop_partner)})
        if fin.afkoop_erfpacht > 0:
            opzet_rows.append({"label": "Afkoop erfpacht", "value": format_bedrag(fin.afkoop_erfpacht)})
        if fin.oversluiten_leningen > 0:
            opzet_rows.append({"label": "Oversluiten leningen", "value": format_bedrag(fin.oversluiten_leningen)})
        # Extra posten kosten (custom)
        for ep in fin.extra_posten_kosten:
            opzet_rows.append({"label": ep["label"], "value": format_bedrag(ep["value"])})

    # Totaal investering
    extra_aankoop_totaal = sum(ep["value"] for ep in fin.extra_posten_aankoop)
    extra_kosten_totaal = sum(ep["value"] for ep in fin.extra_posten_kosten)
    if fin.is_wijziging:
        # Wijziging: totaal ZONDER huidige hypotheek
        totale_investering = (
            fin.kosten_koper + fin.verbouwing + fin.ebv_ebb
            + fin.consumptief + fin.meerwerk + fin.bouwrente
            + fin.boeterente + fin.uitkoop_partner + fin.afkoop_erfpacht
            + fin.oversluiten_leningen
            + extra_aankoop_totaal + extra_kosten_totaal
        )
    else:
        totale_investering = (
            fin.koopsom + fin.kosten_koper + fin.verbouwing + fin.ebv_ebb
            + fin.consumptief + fin.meerwerk + fin.bouwrente
            + fin.koopsom_grond + fin.aanneemsom
            + fin.koopsom_kavel + fin.sloop_oude_woning + fin.bouw_woning
            + fin.boeterente + fin.uitkoop_partner + fin.afkoop_erfpacht
            + fin.oversluiten_leningen
            + extra_aankoop_totaal + extra_kosten_totaal
        )
    opzet_rows.append({"label": "Totaal", "value": format_bedrag(totale_investering), "bold": True})
    opzet_rows.append({"label": "", "value": ""})  # Spacer

    # Overbrugging (aftrekpost)
    overbrugging = fin.overbrugging
    if not overbrugging:
        # Zoek overbrugging in leningdelen
        for ld in data.leningdelen:
            if ld.is_overbrugging:
                overbrugging += ld.totaal_bedrag
    if overbrugging > 0:
        opzet_rows.append({"label": "Overbrugging", "value": f"-/{format_bedrag(overbrugging)}"})

    # Eigen middelen (aftrekposten)
    if fin.eigen_middelen > 0:
        opzet_rows.append({"label": "Af: Eigen geld", "value": f"-/{format_bedrag(fin.eigen_middelen)}"})
    if fin.schenking_inbreng > 0:
        opzet_rows.append({"label": "Af: Schenking", "value": f"-/{format_bedrag(fin.schenking_inbreng)}"})
    if fin.overwaarde > 0:
        opzet_rows.append({"label": "Af: Overwaarde", "value": f"-/{format_bedrag(fin.overwaarde)}"})

    # Extra posten eigen middelen (custom)
    for ep in fin.extra_posten_eigen_middelen:
        opzet_rows.append({"label": f"Af: {ep['label']}", "value": f"-/{format_bedrag(ep['value'])}"})

    if fin.is_wijziging:
        # Wijziging: Nieuwe hypotheek → Huidige hypotheek → Totale hypotheek
        opzet_rows.append({"label": "Nieuwe hypotheek", "value": format_bedrag(data.hypotheek_bedrag), "bold": True})
        opzet_rows.append({"label": "Huidige hypotheek", "value": format_bedrag(fin.koopsom)})
        opzet_rows.append({"label": "Totale hypotheek", "value": format_bedrag(data.totale_hypotheekschuld), "bold": True})
    else:
        opzet_rows.append({"label": "Hypotheek", "value": format_bedrag(data.totale_hypotheekschuld), "bold": True})
    subsections.append({"subtitle": "Financieringsopzet", "rows": opzet_rows})

    # --- Hypotheekconstructie ---
    constructie_rows = []
    if fin.hypotheekverstrekker:
        constructie_rows.append({"label": "Hypotheekverstrekker", "value": fin.hypotheekverstrekker})
    constructie_rows.append({"label": "NHG", "value": "Ja" if fin.nhg else "Nee"})

    # Leningdelen tabel
    ld_headers = ["Leningdeel", "Bedrag", "Aflosvorm", "Looptijd",
                  "Rentevast", "Rente %", "Aftrekbaar", "Bruto p/m"]
    ld_rows = []
    totaal_bedrag = 0
    totaal_bruto = 0

    for i, ld in enumerate(data.leningdelen, 1):
        bedrag = ld.totaal_bedrag
        totaal_bedrag += bedrag

        # Bruto maandlast per leningdeel (vereenvoudigd)
        bruto_pm = _bruto_maandlast_leningdeel(ld)
        totaal_bruto += bruto_pm

        # Aftrekbaar looptijd (box1 = volledige looptijd, box3 = n.v.t.)
        aftrekbaar = format_looptijd_jaren(ld.org_lpt) if ld.bedrag_box1 > 0 else "n.v.t."

        ld_rows.append([
            str(i),
            format_bedrag(bedrag),
            ld.aflosvorm_display,
            format_looptijd_jaren(ld.org_lpt),
            format_rvp_jaren(ld.rvp),
            format_percentage(ld.werkelijke_rente),
            aftrekbaar,
            format_bedrag(bruto_pm),
        ])

    totals = ["", format_bedrag(totaal_bedrag), "", "", "", "", "",
              format_bedrag(totaal_bruto)]

    constructie_sub = {
        "subtitle": "Hypotheekconstructie",
        "rows": constructie_rows,
        "tables": [{
            "headers": ld_headers,
            "rows": ld_rows,
            "totals": totals,
        }],
    }
    subsections.append(constructie_sub)

    return {
        "id": "financing",
        "title": "Financiering",
        "visible": True,
        "subsections": subsections,
    }


def _bruto_maandlast_leningdeel(ld) -> float:
    """Bereken bruto maandlast per leningdeel (vereenvoudigd).

    Annuïteit: A = P * (r * (1+r)^n) / ((1+r)^n - 1)
    Lineair: aflossing + rente
    Aflossingsvrij: alleen rente
    """
    bedrag = ld.totaal_bedrag
    r = ld.werkelijke_rente / 12  # Maandrente
    n = ld.org_lpt  # Looptijd in maanden

    if bedrag <= 0 or n <= 0:
        return 0

    if ld.aflos_type == "Aflosvrij":
        return bedrag * r

    if ld.aflos_type == "Lineair":
        aflossing = bedrag / n
        rente = bedrag * r
        return aflossing + rente

    # Annuïteit (en overige)
    if r <= 0:
        return bedrag / n
    fn = (1 + r) ** n
    return bedrag * (r * fn) / (fn - 1)
