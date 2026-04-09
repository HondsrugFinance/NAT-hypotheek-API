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
    # Eigendomsverdeling: niet tonen bij 50/50 (default stel) of 100/0 (alleenstaand/één eigenaar)
    _is_default_verdeling = (
        (fin.eigendom_aanvrager == 50 and fin.eigendom_partner == 50)
        or (fin.eigendom_aanvrager == 100 and fin.eigendom_partner == 0)
    )
    if not _is_default_verdeling:
        if data.alleenstaand:
            onderpand_rows.append({"label": "Eigendomsverdeling",
                                   "value": f"{fin.eigendom_aanvrager:.0f}%"})
        else:
            onderpand_rows.append({"label": "Eigendomsverdeling",
                                   "value": f"{fin.eigendom_aanvrager:.0f}% / {fin.eigendom_partner:.0f}%"})
    subsections.append({"subtitle": "Onderpand", "rows": onderpand_rows})

    # --- Financieringsopzet ---
    opzet_rows = []
    is_nieuwbouw_project = "project" in fin.type_woning.lower()
    is_nieuwbouw_eigen_beheer = "eigen beheer" in fin.type_woning.lower()

    # Aankoopposten (afhankelijk van woningtype en flow)
    if fin.is_wijziging and fin.is_oversluiten:
        # Oversluiten: "Huidige hypotheek" bovenaan als basis (matcht Lovable)
        opzet_rows.append({"label": "Huidige hypotheek", "value": format_bedrag(fin.koopsom)})
    elif fin.is_wijziging:
        # Verhogen/uitkopen: huidige hypotheek komt onderaan
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
        # Bij uitkoop: "Uitkoop partner" altijd als eerste post
        if fin.is_uitkopen and fin.uitkoop_partner > 0:
            opzet_rows.append({"label": "Uitkoop partner", "value": format_bedrag(fin.uitkoop_partner)})
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
        # Uitkoop partner (niet-uitkoop flows: normaal in de lijst)
        if not fin.is_uitkopen and fin.uitkoop_partner > 0:
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
    kosten_excl_koopsom = (
        fin.kosten_koper + fin.verbouwing + fin.ebv_ebb
        + fin.consumptief + fin.meerwerk + fin.bouwrente
        + fin.boeterente + fin.uitkoop_partner + fin.afkoop_erfpacht
        + fin.oversluiten_leningen
        + extra_aankoop_totaal + extra_kosten_totaal
    )
    if fin.is_wijziging and fin.is_oversluiten:
        # Oversluiten: totaal INCLUSIEF huidige hypotheek (als basis)
        totale_investering = fin.koopsom + kosten_excl_koopsom
    elif fin.is_wijziging:
        # Verhogen: totaal ZONDER huidige hypotheek
        totale_investering = kosten_excl_koopsom
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

    if fin.is_wijziging and fin.is_oversluiten:
        # Oversluiten: de nieuwe hypotheek vervangt de oude
        opzet_rows.append({"label": "Hypotheek", "value": format_bedrag(data.hypotheek_bedrag), "bold": True})
    elif fin.is_wijziging:
        # Verhogen: Nieuwe hypotheek → Huidige hypotheek → Totale hypotheek
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

    # Bepaal welke herkomst-types in de hoofdtabel getoond worden
    # Aankoop: nieuw + meenemen | Verhogen/Oversluiten: nieuw | Uitkoop: nieuw + bestaand
    # "elders" altijd apart (andere geldverstrekker)
    toon_in_tabel: set[str] = {"nieuw"}
    if not fin.is_wijziging:
        toon_in_tabel.add("meenemen")
    elif fin.is_uitkopen:
        toon_in_tabel.add("bestaand")

    # Split leningdelen: hoofd vs elders
    hoofd_ld = [ld for ld in data.leningdelen
                if not ld.is_overbrugging and ld.herkomst in toon_in_tabel]
    elders_ld = [ld for ld in data.leningdelen
                 if not ld.is_overbrugging and ld.herkomst == "elders"]

    # Footnotes tracking
    has_meeneem = not fin.is_wijziging and any(ld.herkomst == "meenemen" for ld in hoofd_ld)
    # Leningdelen tabel (hoofdtabel)
    ld_headers = ["Leningdeel", "Bedrag", "Aflosvorm", "Looptijd",
                  "Rentevast", "Rente %", "Aftrekbaar", "Bruto p/m"]
    ld_rows = []
    totaal_bedrag = 0
    totaal_bruto = 0

    for i, ld in enumerate(hoofd_ld, 1):
        bedrag = ld.totaal_bedrag
        totaal_bedrag += bedrag
        bruto_pm = _bruto_maandlast_leningdeel(ld)
        totaal_bruto += bruto_pm
        is_bestaand = ld.herkomst in ("bestaand", "meenemen")

        # * marker bij meeneemhypotheek
        marker = "*" if ld.herkomst == "meenemen" else ""

        # Looptijd: restant voor bestaand/meenemen, anders origineel
        if is_bestaand and ld.restant_looptijd is not None:
            looptijd_display = format_looptijd_jaren(ld.restant_looptijd)
        else:
            looptijd_display = format_looptijd_jaren(ld.org_lpt)

        # RVP: restant voor bestaand/meenemen, anders origineel
        if is_bestaand and ld.restant_rvp is not None:
            rvp_display = format_rvp_jaren(ld.restant_rvp)
        else:
            rvp_display = format_rvp_jaren(ld.rvp)

        # Aftrekbaar: gebruik restant_aftrekbaar als gevuld (bijv. voor-2013 regime),
        # anders originele looptijd
        if ld.bedrag_box1 <= 0:
            aftrekbaar = "n.v.t."
        elif ld.restant_aftrekbaar is not None:
            aftrekbaar = format_looptijd_jaren(ld.restant_aftrekbaar)
        else:
            aftrekbaar = format_looptijd_jaren(ld.org_lpt)

        ld_rows.append([
            f"{i}{marker}",
            format_bedrag(bedrag),
            ld.aflosvorm_display,
            looptijd_display,
            rvp_display,
            format_percentage(ld.werkelijke_rente),
            aftrekbaar,
            format_bedrag(bruto_pm),
        ])

    totals = ["", format_bedrag(totaal_bedrag), "", "", "", "", "",
              format_bedrag(totaal_bruto)]

    footnotes = []
    if has_meeneem:
        footnotes.append("*betreft een meeneemhypotheek")

    constructie_sub = {
        "subtitle": "Hypotheekconstructie",
        "rows": constructie_rows,
        "tables": [{
            "headers": ld_headers,
            "rows": ld_rows,
            "totals": totals,
        }],
        "footnotes": footnotes,
    }
    subsections.append(constructie_sub)

    # --- Leningdeel elders (aparte geldverstrekker) ---
    if elders_ld:
        for ld in elders_ld:
            bedrag = ld.totaal_bedrag
            bruto_pm = _bruto_maandlast_leningdeel(ld)
            if ld.bedrag_box1 <= 0:
                aftrekbaar = "n.v.t."
            elif ld.restant_aftrekbaar is not None:
                aftrekbaar = format_looptijd_jaren(ld.restant_aftrekbaar)
            else:
                aftrekbaar = format_looptijd_jaren(ld.org_lpt)
            rvp_display = format_rvp_jaren(ld.restant_rvp) if ld.restant_rvp is not None else format_rvp_jaren(ld.rvp)

            elders_rows = [
                {"label": "Hypotheekverstrekker", "value": ld.verstrekker or "Elders"},
            ]
            elders_table = {
                "headers": ld_headers,
                "rows": [[
                    "1",
                    format_bedrag(bedrag),
                    ld.aflosvorm_display,
                    format_looptijd_jaren(ld.org_lpt),
                    rvp_display,
                    format_percentage(ld.werkelijke_rente),
                    aftrekbaar,
                    format_bedrag(bruto_pm),
                ]],
            }
            subsections.append({
                "subtitle": "Leningdeel elders",
                "rows": elders_rows,
                "tables": [elders_table],
            })

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
