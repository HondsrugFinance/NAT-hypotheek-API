"""Huidige situatie sectie — persoonsgegevens, inkomen, vermogen."""

from adviesrapport_v2.field_mapper import NormalizedDossierData
from adviesrapport_v2.formatters import format_bedrag, format_datum


def _inkomen_tabel(persoon, label_prefix: str = "") -> dict:
    """Bouw inkomen-tabel voor één persoon."""
    ink = persoon.inkomen
    rows = []
    totaal = 0

    if ink.loondienst > 0:
        rows.append(["Loondienst", format_bedrag(ink.loondienst)])
        totaal += ink.loondienst
    if ink.onderneming > 0:
        rows.append(["Onderneming", format_bedrag(ink.onderneming)])
        totaal += ink.onderneming
    if ink.roz > 0:
        rows.append(["ROZ", format_bedrag(ink.roz)])
        totaal += ink.roz
    if ink.overig > 0:
        rows.append(["Overig inkomen", format_bedrag(ink.overig)])
        totaal += ink.overig
    if ink.partneralimentatie_ontvangen > 0:
        rows.append(["Partneralimentatie ontvangen", format_bedrag(ink.partneralimentatie_ontvangen)])
        totaal += ink.partneralimentatie_ontvangen

    if not rows:
        rows.append(["Geen inkomen opgegeven", "€ 0"])

    return {
        "headers": ["Type", "Bedrag"],
        "rows": rows,
        "totals": ["Totaal", format_bedrag(totaal)],
    }


def _inkomen_aow_tabel(persoon, aow_jaar: str = "") -> dict:
    """Bouw inkomen na AOW-tabel voor één persoon."""
    ink = persoon.inkomen
    rows = []
    totaal = 0

    if ink.aow_uitkering > 0:
        rows.append(["AOW-uitkering", format_bedrag(ink.aow_uitkering)])
        totaal += ink.aow_uitkering
    if ink.pensioen > 0:
        rows.append(["Pensioen", format_bedrag(ink.pensioen)])
        totaal += ink.pensioen
    if ink.overig > 0:
        rows.append(["Overig inkomen", format_bedrag(ink.overig)])
        totaal += ink.overig

    if not rows:
        rows.append(["Geen AOW-inkomen opgegeven", "€ 0"])

    return {
        "headers": ["Type", "Bedrag"],
        "rows": rows,
        "totals": ["Totaal", format_bedrag(totaal)],
    }


def build_current_situation_section(data: NormalizedDossierData) -> dict:
    """Bouw de huidige situatie sectie met subsections."""
    subsections = []

    # --- Persoonsgegevens ---
    if data.alleenstaand:
        a = data.aanvrager
        subsections.append({
            "subtitle": "Persoonsgegevens",
            "rows": [
                {"label": "Naam", "value": a.voorletters_achternaam or a.naam},
                {"label": "Geboortedatum", "value": format_datum(a.geboortedatum)},
                {"label": "Adres", "value": a.adres},
                {"label": "Postcode en plaats", "value": a.postcode_plaats},
                {"label": "Telefoon", "value": a.telefoon},
                {"label": "E-mail", "value": a.email},
            ],
        })
    else:
        # Stel: columns layout
        a = data.aanvrager
        p = data.partner
        subsections.append({
            "subtitle": "Persoonsgegevens",
            "columns": [
                {
                    "title": a.naam,
                    "rows": [
                        {"label": "Naam", "value": a.voorletters_achternaam or a.naam},
                        {"label": "Geboortedatum", "value": format_datum(a.geboortedatum)},
                        {"label": "Adres", "value": a.adres},
                        {"label": "Postcode en plaats", "value": a.postcode_plaats},
                        {"label": "Telefoon", "value": a.telefoon},
                        {"label": "E-mail", "value": a.email},
                    ],
                },
                {
                    "title": p.naam,
                    "rows": [
                        {"label": "Naam", "value": p.voorletters_achternaam or p.naam},
                        {"label": "Geboortedatum", "value": format_datum(p.geboortedatum)},
                        {"label": "Adres", "value": p.adres},
                        {"label": "Postcode en plaats", "value": p.postcode_plaats},
                        {"label": "Telefoon", "value": p.telefoon},
                        {"label": "E-mail", "value": p.email},
                    ],
                },
            ],
        })

    # --- Gezinssituatie ---
    gezin_rows = [
        {"label": "Burgerlijke staat",
         "value": "Alleenstaand" if data.alleenstaand else "Gehuwd"},
    ]
    if data.huwelijkse_voorwaarden:
        gezin_rows.append({"label": "Huwelijkse voorwaarden", "value": data.huwelijkse_voorwaarden})

    gezin_sub = {"subtitle": "Gezinssituatie", "rows": gezin_rows}
    if data.kinderen:
        gezin_sub["list_items"] = data.kinderen
        gezin_sub["list_label"] = "Kinderen"
    subsections.append(gezin_sub)

    # --- Inkomen ---
    if data.alleenstaand:
        subsections.append({
            "subtitle": "Inkomen",
            "tables": [_inkomen_tabel(data.aanvrager)],
        })
    else:
        subsections.append({
            "subtitle": "Inkomen",
            "columns": [
                {"title": data.aanvrager.naam, "tables": [_inkomen_tabel(data.aanvrager)]},
                {"title": data.partner.naam, "tables": [_inkomen_tabel(data.partner)]},
            ],
        })

    # --- Inkomen na AOW ---
    if data.aanvrager.inkomen.totaal_aow > 0 or (data.partner and data.partner.inkomen.totaal_aow > 0):
        if data.alleenstaand:
            subsections.append({
                "subtitle": "Inkomen na AOW",
                "tables": [_inkomen_aow_tabel(data.aanvrager)],
            })
        else:
            subsections.append({
                "subtitle": "Inkomen na AOW",
                "columns": [
                    {"title": data.aanvrager.naam, "tables": [_inkomen_aow_tabel(data.aanvrager)]},
                    {"title": data.partner.naam, "tables": [_inkomen_aow_tabel(data.partner)]},
                ],
            })

    # --- Vermogen ---
    # TODO: vermogensgegevens worden later toegevoegd als Supabase schema bekend is

    return {
        "id": "current-situation",
        "title": "Huidige situatie",
        "visible": True,
        "subsections": subsections,
    }
