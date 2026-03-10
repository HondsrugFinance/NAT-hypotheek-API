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
    if fin.adres:
        onderpand_rows.append({"label": "Adres", "value": fin.adres})
    onderpand_rows.append({"label": "Type woning", "value": fin.type_woning})
    onderpand_rows.append({"label": "Marktwaarde", "value": format_bedrag(fin.woningwaarde)})
    onderpand_rows.append({"label": "Energielabel", "value": fin.energielabel})
    subsections.append({"subtitle": "Onderpand", "rows": onderpand_rows})

    # --- Financieringsopzet ---
    totale_investering = data.totale_investering
    opzet_rows = [
        {"label": "Koopsom", "value": format_bedrag(fin.koopsom)},
    ]
    if fin.kosten_koper > 0:
        opzet_rows.append({"label": "Kosten koper", "value": format_bedrag(fin.kosten_koper)})
    opzet_rows.append({"label": "Totale investering", "value": format_bedrag(totale_investering), "bold": True})
    opzet_rows.append({"label": "", "value": ""})  # Spacer
    if fin.eigen_middelen > 0:
        opzet_rows.append({"label": "Eigen middelen", "value": format_bedrag(fin.eigen_middelen)})
    opzet_rows.append({"label": "Benodigd hypotheekbedrag", "value": format_bedrag(data.hypotheek_bedrag), "bold": True})
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
