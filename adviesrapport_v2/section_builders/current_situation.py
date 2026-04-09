"""Huidige situatie sectie — persoonsgegevens, inkomen, vermogen, woningen, etc."""

from adviesrapport_v2.field_mapper import (
    NormalizedDossierData, AFLOSVORM_DISPLAY, _map_aflosvorm,
)
from adviesrapport_v2.formatters import format_bedrag, format_datum, format_looptijd_jaren, format_percentage
from adviesrapport_v2.section_builders._align import align_tables_in_columns


def _inkomen_tabel(persoon, is_aow: bool = False) -> dict:
    """Bouw inkomen-tabel voor één persoon.

    Als is_aow=True: toon AOW-uitkering + pensioen + overig (huidige situatie).
    Anders: toon loondienst/onderneming/uitkering etc.
    """
    ink = persoon.inkomen
    rows = []
    totaal = 0

    if is_aow:
        # Persoon is AOW-gerechtigd: toon AOW-inkomen als huidig inkomen
        if ink.aow_uitkering > 0:
            rows.append(["AOW-uitkering", format_bedrag(ink.aow_uitkering)])
            totaal += ink.aow_uitkering
        if ink.pensioen > 0:
            rows.append(["Pensioen", format_bedrag(ink.pensioen)])
            totaal += ink.pensioen
        if ink.overig > 0:
            rows.append(["Overig inkomen", format_bedrag(ink.overig)])
            totaal += ink.overig
        if ink.partneralimentatie_ontvangen > 0:
            rows.append(["Partneralimentatie ontvangen", format_bedrag(ink.partneralimentatie_ontvangen)])
            totaal += ink.partneralimentatie_ontvangen
    else:
        if ink.loondienst > 0:
            rows.append(["Loondienst", format_bedrag(ink.loondienst)])
            totaal += ink.loondienst
        if ink.onderneming > 0:
            rows.append(["Onderneming", format_bedrag(ink.onderneming)])
            totaal += ink.onderneming
        if ink.roz > 0:
            rows.append(["ROZ", format_bedrag(ink.roz)])
            totaal += ink.roz
        if ink.uitkering > 0:
            rows.append(["Uitkering", format_bedrag(ink.uitkering)])
            totaal += ink.uitkering
        overig_totaal = ink.overig + ink.overig_tijdelijk
        if overig_totaal > 0:
            rows.append(["Overig inkomen", format_bedrag(overig_totaal)])
            totaal += overig_totaal
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


def _resolve_eigenaar(eigenaar: str, data: "NormalizedDossierData") -> str:
    """Map eigenaar-waarde naar echte naam (voornaam achternaam)."""
    if not eigenaar:
        return "-"
    lower = eigenaar.lower().strip()
    if lower == "aanvrager":
        return data.aanvrager.naam or "Aanvrager"
    if lower == "partner" and data.partner:
        return data.partner.naam or "Partner"
    if lower in ("gezamenlijk", "beiden"):
        return "Gezamenlijk"
    return eigenaar.replace("_", " ").capitalize()


def _persoon_rows(persoon) -> list[dict]:
    """Bouw persoonsgegevens rijen voor één persoon, inclusief conditionele velden."""
    rows = [
        {"label": "Naam", "value": persoon.voorletters_achternaam or persoon.naam},
        {"label": "Geboortedatum", "value": format_datum(persoon.geboortedatum)},
        {"label": "Adres", "value": persoon.adres},
        {"label": "Postcode en plaats", "value": persoon.postcode_plaats},
        {"label": "Telefoon", "value": persoon.telefoon},
        {"label": "E-mail", "value": persoon.email},
    ]
    # #5: Eerder gehuwd (alleen als Ja)
    if persoon.eerder_gehuwd:
        rows.append({"label": "Eerder gehuwd", "value": "Ja"})
        if persoon.datum_echtscheiding:
            rows.append({"label": "Datum echtscheiding", "value": format_datum(persoon.datum_echtscheiding)})
    # #6: Weduwe/weduwnaar (alleen als Ja)
    if persoon.weduwe_weduwnaar:
        rows.append({"label": "Weduwe/weduwnaar", "value": "Ja"})
    return rows


def build_current_situation_section(
    data: NormalizedDossierData,
    aanvrager_is_aow: bool = False,
    partner_is_aow: bool = False,
) -> dict:
    """Bouw de huidige situatie sectie met subsections."""
    subsections = []

    # --- Persoonsgegevens ---
    if data.alleenstaand:
        a = data.aanvrager
        subsections.append({
            "subtitle": "Persoonsgegevens",
            "rows": _persoon_rows(a),
        })
    else:
        # Stel: columns layout
        a = data.aanvrager
        p = data.partner
        subsections.append({
            "subtitle": "Persoonsgegevens",
            "columns": [
                {"title": a.naam, "rows": _persoon_rows(a)},
                {"title": p.naam, "rows": _persoon_rows(p)},
            ],
        })

    # --- Gezinssituatie ---
    gezin_rows = [
        {"label": "Burgerlijke staat", "value": data.burgerlijke_staat},
    ]
    if data.huwelijkse_voorwaarden:
        bs_lower = data.burgerlijke_staat.lower()
        if bs_lower == "samenwonend":
            label_hw = "Samenlevingsvorm"
        elif bs_lower == "geregistreerd partnerschap":
            label_hw = "Voorwaarden"
        else:
            label_hw = "Huwelijkse voorwaarden"
        gezin_rows.append({"label": label_hw, "value": data.huwelijkse_voorwaarden})

    gezin_sub = {"subtitle": "Gezinssituatie", "rows": gezin_rows}
    if data.kinderen:
        gezin_sub["list_items"] = data.kinderen
        gezin_sub["list_label"] = "Kinderen"
    subsections.append(gezin_sub)

    # --- Werkgever ---
    if data.werkgever_aanvrager or data.werkgever_partner:
        if data.alleenstaand and data.werkgever_aanvrager:
            wg = data.werkgever_aanvrager
            wg_rows = [{"label": "Werkgever", "value": wg.naam}]
            if wg.dienstverband:
                wg_rows.append({"label": "Dienstverband", "value": wg.dienstverband})
            if wg.datum_in_dienst:
                wg_rows.append({"label": "In dienst sinds", "value": format_datum(wg.datum_in_dienst)})
            # #23: Flexibel inkomen (3 jaar)
            if data.aanvrager.flexibel_inkomen_3j:
                wg_rows.append({"label": "Flexibel inkomen (3 jaar)", "value": "Ja"})
            # #24: Arbeidsmarktscan
            if data.aanvrager.arbeidsmarktscan_fase:
                wg_rows.append({"label": "Arbeidsmarktscan", "value": data.aanvrager.arbeidsmarktscan_fase})
            subsections.append({"subtitle": "Werkgever", "rows": wg_rows})
        elif not data.alleenstaand:
            cols = []
            for persoon, wg in [
                (data.aanvrager, data.werkgever_aanvrager),
                (data.partner if data.partner else None, data.werkgever_partner),
            ]:
                naam = persoon.naam if persoon else "Partner"
                if wg:
                    wg_rows = [{"label": "Werkgever", "value": wg.naam}]
                    if wg.dienstverband:
                        wg_rows.append({"label": "Dienstverband", "value": wg.dienstverband})
                    if wg.datum_in_dienst:
                        wg_rows.append({"label": "In dienst sinds", "value": format_datum(wg.datum_in_dienst)})
                    # #23: Flexibel inkomen (3 jaar)
                    if persoon and persoon.flexibel_inkomen_3j:
                        wg_rows.append({"label": "Flexibel inkomen (3 jaar)", "value": "Ja"})
                    # #24: Arbeidsmarktscan
                    if persoon and persoon.arbeidsmarktscan_fase:
                        wg_rows.append({"label": "Arbeidsmarktscan", "value": persoon.arbeidsmarktscan_fase})
                    cols.append({"title": naam, "rows": wg_rows})
                else:
                    cols.append({"title": naam, "rows": [{"label": "Werkgever", "value": "-"}]})
            subsections.append({"subtitle": "Werkgever", "columns": cols})

    # --- Inkomen ---
    # Bij AOW-gerechtigden: toon AOW+pensioen als huidig inkomen
    if data.alleenstaand:
        subsections.append({
            "subtitle": "Inkomen",
            "tables": [_inkomen_tabel(data.aanvrager, is_aow=aanvrager_is_aow)],
        })
    else:
        inkomen_cols = [
            {"title": data.aanvrager.naam, "tables": [_inkomen_tabel(data.aanvrager, is_aow=aanvrager_is_aow)]},
            {"title": data.partner.naam, "tables": [_inkomen_tabel(data.partner, is_aow=partner_is_aow)]},
        ]
        align_tables_in_columns(inkomen_cols)
        subsections.append({
            "subtitle": "Inkomen",
            "columns": inkomen_cols,
        })

    # --- Inkomen na AOW ---
    # Alleen tonen voor personen die nog NIET AOW-gerechtigd zijn
    a_heeft_aow_data = not aanvrager_is_aow and data.aanvrager.inkomen.totaal_aow > 0
    p_heeft_aow_data = (not partner_is_aow and data.partner and data.partner.inkomen.totaal_aow > 0)

    if a_heeft_aow_data or p_heeft_aow_data:
        if data.alleenstaand:
            if a_heeft_aow_data:
                subsections.append({
                    "subtitle": "Inkomen na AOW",
                    "tables": [_inkomen_aow_tabel(data.aanvrager)],
                })
        else:
            # Stel: alleen kolommen tonen voor personen die nog niet AOW zijn
            if a_heeft_aow_data and p_heeft_aow_data:
                # Beiden nog niet AOW → twee kolommen
                aow_cols = [
                    {"title": data.aanvrager.naam, "tables": [_inkomen_aow_tabel(data.aanvrager)]},
                    {"title": data.partner.naam, "tables": [_inkomen_aow_tabel(data.partner)]},
                ]
                align_tables_in_columns(aow_cols)
                subsections.append({
                    "subtitle": "Inkomen na AOW",
                    "columns": aow_cols,
                })
            elif a_heeft_aow_data:
                # Alleen aanvrager nog niet AOW
                subsections.append({
                    "subtitle": f"Inkomen na AOW — {data.aanvrager.naam}",
                    "tables": [_inkomen_aow_tabel(data.aanvrager)],
                })
            elif p_heeft_aow_data:
                # Alleen partner nog niet AOW
                subsections.append({
                    "subtitle": f"Inkomen na AOW — {data.partner.naam}",
                    "tables": [_inkomen_aow_tabel(data.partner)],
                })

    # --- Bestaande woning ---
    for i, woning in enumerate(data.bestaande_woningen):
        label = "Bestaande woning" if len(data.bestaande_woningen) == 1 else f"Bestaande woning {i+1}"
        w_rows = []
        if woning.adres:
            w_rows.append({"label": "Adres", "value": woning.adres})
        if woning.postcode_plaats:
            w_rows.append({"label": "Postcode en plaats", "value": woning.postcode_plaats})
        # #37: Eigenaar woning
        if woning.eigenaar:
            w_rows.append({"label": "Eigenaar", "value": _resolve_eigenaar(woning.eigenaar, data)})
        # #38: Eigendomsverhouding (alleen als gezamenlijk en niet 50/50)
        if (woning.eigenaar.lower() in ("gezamenlijk", "beiden")
                and woning.eigendom_aanvrager > 0
                and woning.eigendom_partner > 0
                and not (woning.eigendom_aanvrager == 50 and woning.eigendom_partner == 50)):
            w_rows.append({"label": "Eigendomsverhouding",
                           "value": f"{woning.eigendom_aanvrager:.0f}% / {woning.eigendom_partner:.0f}%"})
        # #39: Woningtoepassing
        if woning.woontoepassing:
            w_rows.append({"label": "Woningtoepassing", "value": woning.woontoepassing.replace("_", " ").capitalize()})
        if woning.marktwaarde > 0:
            w_rows.append({"label": "Marktwaarde", "value": format_bedrag(woning.marktwaarde)})
        if woning.woz_waarde > 0:
            w_rows.append({"label": "WOZ-waarde", "value": format_bedrag(woning.woz_waarde)})
        if woning.energielabel:
            w_rows.append({"label": "Energielabel", "value": woning.energielabel})
        if woning.status:
            w_rows.append({"label": "Status", "value": woning.status.replace("_", " ").capitalize()})
        if woning.erfpacht:
            if woning.erfpachtcanon > 0:
                w_rows.append({"label": "Erfpacht", "value": f"Ja (canon {format_bedrag(woning.erfpachtcanon)} p/j)"})
            else:
                w_rows.append({"label": "Erfpacht", "value": "Ja"})
        # #42: Huur per maand
        if woning.huur_per_maand > 0:
            w_rows.append({"label": "Huur per maand", "value": format_bedrag(woning.huur_per_maand)})
        if w_rows:
            subsections.append({"subtitle": label, "rows": w_rows})

    # --- Bestaande hypotheek ---
    for i, hyp in enumerate(data.bestaande_hypotheken):
        label = "Bestaande hypotheek" if len(data.bestaande_hypotheken) == 1 else f"Bestaande hypotheek {i+1}"
        h_rows = []
        if hyp.verstrekker:
            h_rows.append({"label": "Hypotheekverstrekker", "value": hyp.verstrekker})
        h_rows.append({"label": "NHG", "value": "Ja" if hyp.nhg else "Nee"})
        if hyp.hoofdsom > 0:
            h_rows.append({"label": "Oorspronkelijke hoofdsom", "value": format_bedrag(hyp.hoofdsom)})
        if hyp.restschuld > 0:
            h_rows.append({"label": "Huidige restschuld", "value": format_bedrag(hyp.restschuld)})

        sub = {"subtitle": label, "rows": h_rows}

        # Leningdelen tabel (uitgebreid)
        if hyp.leningdelen:
            # Bepaal welke kolommen relevant zijn (niet alles is altijd ingevuld)
            has_looptijd = any(ld.get("looptijd") for ld in hyp.leningdelen)
            has_rentevast = any(ld.get("rentevast") for ld in hyp.leningdelen)
            has_ingangsdatum = any(ld.get("ingangsdatum") for ld in hyp.leningdelen)

            headers = ["Leningdeel", "Bedrag", "Aflosvorm", "Rente"]
            if has_looptijd:
                headers.append("Looptijd")
            if has_rentevast:
                headers.append("Rentevast")
            if has_ingangsdatum:
                headers.append("Ingangsdatum")

            ld_rows = []
            for j, ld in enumerate(hyp.leningdelen, 1):
                bedrag = format_bedrag(ld.get("bedrag", 0))
                rente = f"{ld.get('rente', 0):.2f}%".replace(".", ",") if ld.get("rente") else "-"
                aflosvorm = ld.get("aflosvorm", "-")
                if aflosvorm:
                    aflosvorm = AFLOSVORM_DISPLAY.get(
                        _map_aflosvorm(aflosvorm), aflosvorm.capitalize()
                    )

                row = [str(j), bedrag, aflosvorm, rente]
                if has_looptijd:
                    looptijd = ld.get("looptijd", 0)
                    row.append(format_looptijd_jaren(looptijd) if looptijd else "-")
                if has_rentevast:
                    rv = ld.get("rentevast", 0)
                    row.append(f"{rv} jaar" if rv else "-")
                if has_ingangsdatum:
                    igd = ld.get("ingangsdatum", "")
                    row.append(format_datum(igd) if igd else "-")

                ld_rows.append(row)
            sub["tables"] = [{
                "headers": headers,
                "rows": ld_rows,
            }]

        subsections.append(sub)

    # --- Vermogen ---
    if data.vermogen:
        # #62: Eigenaar kolom toevoegen als er eigenaar-info beschikbaar is
        has_eigenaar = any(item.eigenaar for item in data.vermogen)
        v_rows = []
        totaal = 0
        for item in data.vermogen:
            label_parts = [item.type_display]
            if item.maatschappij:
                label_parts.append(f"({item.maatschappij})")
            omschrijving = " ".join(label_parts)
            if has_eigenaar:
                v_rows.append([omschrijving, _resolve_eigenaar(item.eigenaar, data), format_bedrag(item.saldo)])
            else:
                v_rows.append([omschrijving, format_bedrag(item.saldo)])
            totaal += item.saldo

        if has_eigenaar:
            headers = ["Omschrijving", "Eigenaar", "Bedrag"]
            totals = ["Totaal", "", format_bedrag(totaal)]
        else:
            headers = ["Omschrijving", "Bedrag"]
            totals = ["Totaal", format_bedrag(totaal)]

        subsections.append({
            "subtitle": "Vermogen",
            "tables": [{
                "headers": headers,
                "rows": v_rows,
                "totals": totals,
            }],
        })

    # --- Verplichtingen ---
    if data.verplichtingen_details:
        v_rows = []
        for vpl in data.verplichtingen_details:
            omschr = vpl["type"]
            detail = vpl.get("omschrijving") or ""
            if detail:
                # Verwijder geneste haakjes: "DUO (Studieschuld)" → "DUO - Studieschuld"
                clean = detail.replace("(", "- ").replace(")", "").strip().rstrip("- ").strip()
                omschr = f"{vpl['type']} ({clean})"
            elif vpl.get("maatschappij"):
                # Fallback: gebruik maatschappij als omschrijving ontbreekt
                omschr = f"{vpl['type']} ({vpl['maatschappij']})"
            maandbedrag = format_bedrag(vpl["maandbedrag"]) + " p/m" if vpl["maandbedrag"] > 0 else "-"
            saldo = format_bedrag(vpl["saldo"]) if vpl["saldo"] > 0 else "-"
            v_rows.append([omschr, saldo, maandbedrag])

        subsections.append({
            "subtitle": "Verplichtingen",
            "tables": [{
                "headers": ["Omschrijving", "Saldo", "Maandlast"],
                "rows": v_rows,
            }],
        })

    # --- Voorzieningen / Verzekeringen ---
    if data.verzekeringen:
        v_rows = []
        for verz in data.verzekeringen:
            aanbieder = verz.aanbieder or "-"
            type_display = verz.type_display

            # Resolve "aanvrager"/"partner" naar echte namen
            vz = verz.verzekerde.lower().strip() if verz.verzekerde else ""
            if vz == "aanvrager":
                verzekerde = data.aanvrager.naam or "Aanvrager"
            elif vz == "partner" and data.partner:
                verzekerde = data.partner.naam or "Partner"
            elif verz.verzekerde:
                verzekerde = verz.verzekerde.replace("_", " ").capitalize()
            else:
                verzekerde = "-"

            # Bepaal het juiste dekkingsbedrag per type
            type_lower = verz.type.lower()
            if "lijfrente" in type_lower:
                bedrag = verz.dekking
                dekking = format_bedrag(bedrag) + " p/j" if bedrag > 0 else "-"
            elif "arbeidsongeschiktheid" in type_lower or type_lower == "aov":
                bedrag = verz.dekking_aov or verz.dekking
                dekking = format_bedrag(bedrag) + " p/j" if bedrag > 0 else "-"
            elif "woonlasten" in type_lower:
                parts = []
                if verz.dekking_ao > 0:
                    parts.append(f"AO: {format_bedrag(verz.dekking_ao)} p/j")
                if verz.dekking_ww > 0:
                    parts.append(f"WW: {format_bedrag(verz.dekking_ww)} p/j")
                dekking = ", ".join(parts) if parts else "-"
            else:
                dekking = format_bedrag(verz.dekking) if verz.dekking > 0 else "-"
            v_rows.append([aanbieder, type_display, verzekerde, dekking])

        subsections.append({
            "subtitle": "Voorzieningen",
            "tables": [{
                "headers": ["Aanbieder", "Type", "Verzekerde", "Uitkering"],
                "rows": v_rows,
            }],
        })

    return {
        "id": "current-situation",
        "title": "Huidige situatie",
        "visible": True,
        "subsections": subsections,
    }
