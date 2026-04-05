"""Deterministische field mapper: extracted_fields → AanvraagData.

Vervangt de Claude smart_mapper call. Python vertaalt, AI analyseert.

Stap 2 (Claude) produceert `extracted_fields` met gestandaardiseerde veldnamen.
Deze mapper vertaalt die naar AanvraagData paden — deterministisch, geen AI nodig.

Beslissingen (keuzemomenten) komen uit stap 3 dossier-analyse, niet uit dit bestand.
"""

import logging
from typing import Any

logger = logging.getLogger("nat-api.field-mapper-v2")


# ---------------------------------------------------------------------------
# Mapping tabel: (sectie, veldnaam) → AanvraagData pad
# Sectie = document_type uit extracted_fields (of "inkomen_ibl" voor IBL)
# Veldnaam = key in extracted_fields.fields dict
# Pad = dot-notatie pad in AanvraagData
#
# {persoon} wordt vervangen door "aanvrager" of "partner" op basis van
# het persoon-veld in extracted_fields.
# ---------------------------------------------------------------------------

# Persoonsgegevens (paspoort, ID-kaart)
_PERSOON_MAP = {
    "voornaam": "{persoon}.persoon.voornamen",
    "voornamen": "{persoon}.persoon.voornamen",
    "achternaam": "{persoon}.persoon.achternaam",
    "tussenvoegsel": "{persoon}.persoon.tussenvoegsel",
    "voorletters": "{persoon}.persoon.voorletters",
    "geboortedatum": "{persoon}.persoon.geboortedatum",
    "geboorteplaats": "{persoon}.persoon.geboorteplaats",
    "geboorteland": "{persoon}.persoon.geboorteland",
    "nationaliteit": "{persoon}.persoon.nationaliteit",
    "geslacht": "{persoon}.persoon.geslacht",
    "roepnaam": "{persoon}.persoon.roepnaam",
}

# Legitimatie (paspoort, ID-kaart)
_IDENTITEIT_MAP = {
    "documentnummer": "{persoon}.identiteit.legitimatienummer",
    "legitimatienummer": "{persoon}.identiteit.legitimatienummer",
    "bsn": "{persoon}.identiteit.bsn",
    "documentsoort": "{persoon}.identiteit.legitimatiesoort",
    "legitimatiesoort": "{persoon}.identiteit.legitimatiesoort",
    "afgiftedatum": "{persoon}.identiteit.afgiftedatum",
    "geldigTot": "{persoon}.identiteit.geldigTot",
    "verlooptDatum": "{persoon}.identiteit.geldigTot",
    "afgifteplaats": "{persoon}.identiteit.afgifteplaats",
    "afgifteland": "{persoon}.identiteit.afgifteland",
}

# Adres (uit diverse bronnen)
_ADRES_MAP = {
    "straat": "{persoon}.adresContact.straat",
    "huisnummer": "{persoon}.adresContact.huisnummer",
    "toevoeging": "{persoon}.adresContact.toevoeging",
    "postcode": "{persoon}.adresContact.postcode",
    "woonplaats": "{persoon}.adresContact.woonplaats",
    "plaats": "{persoon}.adresContact.woonplaats",
    "land": "{persoon}.adresContact.land",
    "email": "{persoon}.adresContact.email",
    "emailadres": "{persoon}.adresContact.email",
    "telefoonnummer": "{persoon}.adresContact.telefoonnummer",
    "telefoon": "{persoon}.adresContact.telefoonnummer",
}

# Werkgever (uit WGV)
_WERKGEVER_MAP = {
    "werkgeverNaam": "inkomen{Persoon}[0].loondienst.werkgever.naamWerkgever",
    "werkgeverAdres": "inkomen{Persoon}[0].loondienst.werkgever.adresWerkgever",
    "werkgeverPostcode": "inkomen{Persoon}[0].loondienst.werkgever.postcodeWerkgever",
    "werkgeverHuisnummer": "inkomen{Persoon}[0].loondienst.werkgever.huisnummer",
    "werkgeverPlaats": "inkomen{Persoon}[0].loondienst.werkgever.vestigingsplaats",
    "kvkNummer": "inkomen{Persoon}[0].loondienst.werkgever.kvkNummer",
    "rsin": "inkomen{Persoon}[0].loondienst.werkgever.rsin",
}

# Dienstverband (uit WGV)
_DIENSTVERBAND_MAP = {
    "functie": "inkomen{Persoon}[0].loondienst.dienstverband.functie",
    "soortDienstverband": "inkomen{Persoon}[0].loondienst.dienstverband.soortDienstverband",
    "datumInDienst": "inkomen{Persoon}[0].loondienst.dienstverband.inDienstSinds",
    "inDienstSinds": "inkomen{Persoon}[0].loondienst.dienstverband.inDienstSinds",
    "arbeidsovereenkomstOnbepaaldeTijd": "inkomen{Persoon}[0].loondienst.dienstverband.soortDienstverband",
    "directeurAandeelhouder": "inkomen{Persoon}[0].loondienst.dienstverband.directeurAandeelhouder",
    "proeftijd": "inkomen{Persoon}[0].loondienst.dienstverband.proeftijd",
    "proeftijdVerstreken": "inkomen{Persoon}[0].loondienst.dienstverband.proeftijdVerstreken",
    "loonbeslag": "inkomen{Persoon}[0].loondienst.dienstverband.loonbeslag",
    "onderhandseLening": "inkomen{Persoon}[0].loondienst.dienstverband.onderhandseLening",
}

# WGV inkomen bedragen
_WGV_INKOMEN_MAP = {
    "brutoJaarsalaris": "inkomen{Persoon}[0].loondienst.werkgeversverklaringCalc.brutoSalaris",
    "brutoMaandloon": "inkomen{Persoon}[0].loondienst.werkgeversverklaringCalc.brutoSalaris",
    "vakantiegeldBedrag": "inkomen{Persoon}[0].loondienst.werkgeversverklaringCalc.vakantiegeldBedrag",
    "vakantiegeldPercentage": "inkomen{Persoon}[0].loondienst.werkgeversverklaringCalc.vakantiegeldPercentage",
    "eindejaarsuitkering": "inkomen{Persoon}[0].loondienst.werkgeversverklaringCalc.eindejaarsuitkering",
    "onregelmatigheidstoeslag": "inkomen{Persoon}[0].loondienst.werkgeversverklaringCalc.onregelmatigheidstoeslag",
    "overwerk": "inkomen{Persoon}[0].loondienst.werkgeversverklaringCalc.overwerk",
    "provisie": "inkomen{Persoon}[0].loondienst.werkgeversverklaringCalc.provisie",
    "dertiendeMaand": "inkomen{Persoon}[0].loondienst.werkgeversverklaringCalc.dertiendeMaand",
    "totaalWgvInkomen": "inkomen{Persoon}[0].jaarbedrag",
}

# IBL inkomen
_IBL_MAP = {
    "gemiddeldJaarToetsinkomen": "inkomen{Persoon}[0].loondienst.gemiddeldJaarToetsinkomen",
    "maandelijksePensioenbijdrage": "inkomen{Persoon}[0].loondienst.maandelijksePensioenbijdrage",
}

# Woning / onderpand
_WONING_MAP = {
    "straat": "woningen[0].straat",
    "huisnummer": "woningen[0].huisnummer",
    "toevoeging": "woningen[0].toevoeging",
    "postcode": "woningen[0].postcode",
    "woonplaats": "woningen[0].woonplaats",
    "woningtype": "woningen[0].typeWoning",
    "soortOnderpand": "woningen[0].soortOnderpand",
    "typeWoning": "woningen[0].typeWoning",
    "marktwaarde": "woningen[0].waardeWoning",
    "taxatiewaarde": "woningen[0].waardeWoning",
    "waardeVastgesteldMet": "woningen[0].waardeVastgesteldMet",
    "wozWaarde": "woningen[0].wozWaarde",
    "energielabel": "woningen[0].energielabel",
    "bouwjaar": "woningen[0].bouwjaar",
    "erfpacht": "woningen[0].erfpacht",
    "jaarlijkseErfpacht": "woningen[0].jaarlijkseErfpacht",
    "eigenaar": "woningen[0].eigenaar",
    "eigendomAandeelAanvrager": "woningen[0].eigendomAandeelAanvrager",
    "eigendomAandeelPartner": "woningen[0].eigendomAandeelPartner",
    "woningToepassing": "woningen[0].woningToepassing",
    "woningstatus": "woningen[0].woningstatus",
}

# Hypotheek
_HYPOTHEEK_MAP = {
    "geldverstrekker": "hypotheekInschrijvingen[0].geldverstrekker",
    "hypotheeknummer": "hypotheken[0].hypotheeknummer",
    "hoofdsom": "hypotheken[0].hoofdsom",
    "inschrijving": "hypotheekInschrijvingen[0].inschrijving",
    "nhg": "hypotheekInschrijvingen[0].nhg",
}

# Leningdelen (in hypotheek)
_LENINGDEEL_MAP = {
    "bedrag": "hypotheken[0].leningdelen[{idx}].bedrag",
    "rentePercentage": "hypotheken[0].leningdelen[{idx}].rentePercentage",
    "rentepercentage": "hypotheken[0].leningdelen[{idx}].rentePercentage",
    "aflosvorm": "hypotheken[0].leningdelen[{idx}].aflosvorm",
    "ingangsdatum": "hypotheken[0].leningdelen[{idx}].ingangsdatum",
    "looptijd": "hypotheken[0].leningdelen[{idx}].looptijd",
    "einddatum": "hypotheken[0].leningdelen[{idx}].einddatum",
    "ingangsdatumRvp": "hypotheken[0].leningdelen[{idx}].ingangsdatumRvp",
    "renteVastPeriode": "hypotheken[0].leningdelen[{idx}].renteVastPeriode",
    "einddatumRvp": "hypotheken[0].leningdelen[{idx}].einddatumRvp",
    "renteAftrekTot": "hypotheken[0].leningdelen[{idx}].renteAftrekTot",
    "fiscaalRegime": "hypotheken[0].leningdelen[{idx}].fiscaalRegime",
}

# Pensioen (uit pensioenspecificatie / UPO)
_PENSIOEN_MAP = {
    "ouderdomspensioenTotaalExclAow": "inkomen{Persoon}[1].jaarbedrag",
    "aowBedrag": "inkomen{Persoon}[2].jaarbedrag",
    "nabestaandenpensioenPartner": "inkomen{Persoon}[0].pensioenData.partnerpensioen.verzekerdVoor",
    "pensioenleeftijd": "inkomen{Persoon}[0].pensioenData.ouderdomspensioen.ingangsdatum",
}

# Verplichtingen
_VERPLICHTING_MAP = {
    "kredietbedrag": "verplichtingen[{idx}].kredietbedrag",
    "maandbedrag": "verplichtingen[{idx}].maandbedrag",
    "saldo": "verplichtingen[{idx}].saldo",
    "kredietnummer": "verplichtingen[{idx}].kredietnummer",
}

# Bankgegevens
_BANK_MAP = {
    "iban": "vermogenSectie.iban.iban{Persoon}",
    "ibanAanvrager": "vermogenSectie.iban.ibanAanvrager",
    "ibanPartner": "vermogenSectie.iban.ibanPartner",
}

# Sectie → mapping tabel koppeling
# Sommige secties gebruiken meerdere mappings
_SECTIE_MAPPINGS: dict[str, list[dict]] = {
    "paspoort": [_PERSOON_MAP, _IDENTITEIT_MAP],
    "id_kaart": [_PERSOON_MAP, _IDENTITEIT_MAP],
    "rijbewijs": [_PERSOON_MAP, _IDENTITEIT_MAP],
    "werkgeversverklaring": [_WERKGEVER_MAP, _DIENSTVERBAND_MAP, _WGV_INKOMEN_MAP],
    "salarisstrook": [_WGV_INKOMEN_MAP],
    "inkomen_ibl": [_IBL_MAP],
    "taxatierapport": [_WONING_MAP],
    "hypotheekoverzicht": [_HYPOTHEEK_MAP, _ADRES_MAP, _WONING_MAP],
    "kadaster_eigendom": [_WONING_MAP],
    "kadaster_hypotheek": [_HYPOTHEEK_MAP],
    "jaaropgave": [_BANK_MAP, _WGV_INKOMEN_MAP],
    "bankafschrift": [_BANK_MAP],
    "echtscheidingsconvenant": [_WONING_MAP, _HYPOTHEEK_MAP],
    "akte_van_verdeling": [_PERSOON_MAP, _WONING_MAP],
    "koopovereenkomst": [_WONING_MAP],
    "pensioenspecificatie": [_PENSIOEN_MAP],
    "upo": [_PENSIOEN_MAP],
    # Documenten die vaak adresgegevens bevatten
    "aangifte_inkomstenbelasting": [_PERSOON_MAP, _ADRES_MAP],
    "loonstrook": [_WGV_INKOMEN_MAP, _WERKGEVER_MAP],
    "nota_van_afrekening": [_HYPOTHEEK_MAP],
    "bkr_registratie": [],  # Verplichtingen apart afhandelen
}

# Velden die NIET ingevuld mogen worden door de mapper
# (Lovable heeft defaults die niet overschreven mogen worden)
_SKIP_FIELDS = {
    "einddatum",  # Default = AOW-datum in Lovable
}

# Waarde-transformaties voor dropdown-velden
_VALUE_TRANSFORMS: dict[str, dict[str, str]] = {
    "geslacht": {"M": "man", "V": "vrouw", "m": "man", "v": "vrouw", "Man": "man", "Vrouw": "vrouw"},
    "legitimatiesoort": {
        "Paspoort": "paspoort", "paspoort": "paspoort",
        "ID-kaart": "europese_id", "Europese ID": "europese_id", "ID kaart": "europese_id",
    },
    "directeurAandeelhouder": {"True": "Ja", "true": "Ja", "False": "Nee", "false": "Nee", True: "Ja", False: "Nee"},
    "proeftijd": {"True": "Ja", "true": "Ja", "False": "Nee", "false": "Nee", True: "Ja", False: "Nee"},
    "loonbeslag": {"True": "Ja", "true": "Ja", "False": "Nee", "false": "Nee", True: "Ja", False: "Nee"},
    "onderhandseLening": {"True": "Ja", "true": "Ja", "False": "Nee", "false": "Nee", True: "Ja", False: "Nee"},
}


def _resolve_persoon_pad(pad_template: str, persoon: str) -> str:
    """Vervang {persoon} en {Persoon} placeholders in pad.

    {persoon} → "aanvrager" of "partner"
    {Persoon} → "Aanvrager" of "Partner" (voor inkomenAanvrager/inkomenPartner)
    """
    p = "aanvrager" if persoon in ("aanvrager", "gezamenlijk") else "partner"
    P = p.capitalize()
    return pad_template.replace("{persoon}", p).replace("{Persoon}", P)


def _transform_value(field_name: str, value: Any) -> Any:
    """Transformeer waarden naar Lovable-compatibele formaten."""
    if field_name in _VALUE_TRANSFORMS:
        transforms = _VALUE_TRANSFORMS[field_name]
        if value in transforms:
            return transforms[value]
        # String versie proberen
        if str(value) in transforms:
            return transforms[str(value)]

    # Lege strings → None (niet invullen)
    if value == "" or value is None:
        return None

    return value


def _set_nested(data: dict, pad: str, value: Any):
    """Zet een waarde in een genest dict via dot-notatie met array-support."""
    segments = []
    for part in pad.split("."):
        if "[" in part:
            key, rest = part.split("[", 1)
            segments.append(key)
            segments.append(int(rest.rstrip("]")))
        else:
            segments.append(part)

    current = data
    for i, segment in enumerate(segments[:-1]):
        next_segment = segments[i + 1]
        if isinstance(segment, int):
            while len(current) <= segment:
                current.append({})
            current = current[segment]
        elif isinstance(next_segment, int):
            if segment not in current or not isinstance(current.get(segment), list):
                current[segment] = []
            current = current[segment]
        else:
            if segment not in current or not isinstance(current.get(segment), dict):
                current[segment] = {}
            current = current[segment]

    last = segments[-1]
    if isinstance(last, int):
        while len(current) <= last:
            current.append({})
        current[last] = value
    else:
        current[last] = value


def map_extracted_to_form(
    extracted_fields: list[dict],
    beslissingen: list[dict] | None = None,
) -> tuple[dict, list[dict], list[dict]]:
    """Vertaal extracted_fields naar AanvraagData + checkvragen.

    Args:
        extracted_fields: Lijst van dicts met sectie, persoon, fields
        beslissingen: Keuzemomenten uit stap 3 dossier-analyse

    Returns:
        (merged_data, velden, check_vragen)
        - merged_data: AanvraagData dict (direct bruikbaar als prefill)
        - velden: Lijst van gemapte velden (voor UI: pad, label, waarde, bron)
        - check_vragen: Lijst van keuzemomenten (uit beslissingen)
    """
    merged_data: dict = {}
    velden: list[dict] = []
    seen_pads: set[str] = set()

    for ef in extracted_fields:
        sectie = ef.get("sectie", "")
        persoon = ef.get("persoon", "aanvrager")
        fields = ef.get("fields", {})

        if not fields or not sectie:
            continue

        # Zoek de mapping-tabellen voor deze sectie
        mappings = _SECTIE_MAPPINGS.get(sectie, [])
        if not mappings:
            logger.debug("Geen mapping voor sectie '%s', overslaan", sectie)
            continue

        for field_name, value in fields.items():
            if field_name in _SKIP_FIELDS:
                continue

            value = _transform_value(field_name, value)
            if value is None:
                continue

            # Zoek het pad in de mapping-tabellen
            target_pad = None
            for mapping in mappings:
                if field_name in mapping:
                    target_pad = mapping[field_name]
                    break

            if not target_pad:
                # Veld niet in mapping → overslaan (geen onbekende velden invullen)
                continue

            # Vervang persoon-placeholders
            target_pad = _resolve_persoon_pad(target_pad, persoon)

            # Deduplicatie: eerste bron wint (tenzij de huidige None/0 is)
            if target_pad in seen_pads:
                continue
            seen_pads.add(target_pad)

            # Zet in merged_data
            _set_nested(merged_data, target_pad, value)

            # Registreer als veld voor UI
            velden.append({
                "pad": target_pad,
                "label": _field_label(field_name),
                "waarde": value,
                "waarde_display": _format_display(value),
                "bron": sectie,
                "status": "nieuw",
                "source": "extracted",
            })

    # Zet vaste waarden die afleidbaar zijn
    _set_derived_fields(merged_data, extracted_fields, velden)

    # Bouw check_vragen uit stap 3 beslissingen
    check_vragen = _build_check_vragen_from_beslissingen(beslissingen or [])

    logger.info("Field mapper: %d velden gemapped, %d checkvragen", len(velden), len(check_vragen))
    return merged_data, velden, check_vragen


def _set_derived_fields(merged_data: dict, extracted_fields: list[dict], velden: list[dict]):
    """Zet velden die afleidbaar zijn uit de context."""
    # Inkomen type en soortBerekening
    has_wgv = any(ef.get("sectie") == "werkgeversverklaring" for ef in extracted_fields)
    has_ibl = any(ef.get("sectie") == "inkomen_ibl" for ef in extracted_fields)

    for ef in extracted_fields:
        persoon = ef.get("persoon", "aanvrager")
        sectie = ef.get("sectie", "")
        p = "Aanvrager" if persoon in ("aanvrager", "gezamenlijk") else "Partner"
        prefix = f"inkomen{p}[0]"

        if sectie == "werkgeversverklaring":
            _set_nested(merged_data, f"{prefix}.type", "loondienst")
            _set_nested(merged_data, f"{prefix}.loondienst.soortBerekening",
                        "werkgeversverklaring" if has_wgv else "inkomensbepaling_loondienst")

            # Werkgever naam ook als inkomstenbron
            werkgever = ef.get("fields", {}).get("werkgeverNaam", "")
            if werkgever:
                _set_nested(merged_data, f"{prefix}.inkomstenbron", werkgever)

            # Ingangsdatum uit dienstverband
            datum = ef.get("fields", {}).get("datumInDienst") or ef.get("fields", {}).get("inDienstSinds")
            if datum:
                _set_nested(merged_data, f"{prefix}.ingangsdatum", datum)


def _build_check_vragen_from_beslissingen(beslissingen: list[dict]) -> list[dict]:
    """Vertaal stap 3 beslissingen naar check_vragen format voor de frontend."""
    check_vragen = []
    for b in beslissingen:
        opties = []
        for opt in b.get("opties", []):
            opties.append({
                "label": opt.get("label", ""),
                "pad": _beslissing_type_to_pad(b.get("type", ""), b.get("persoon", "aanvrager")),
                "waarde": opt.get("waarde"),
            })

        check_vragen.append({
            "id": b.get("type", "onbekend"),
            "vraag": b.get("vraag", ""),
            "opties": opties,
            "bron": ", ".join(o.get("bron", "") for o in b.get("opties", []) if o.get("bron")),
            "evidence": b.get("reden", ""),
            "categorie": _beslissing_type_to_categorie(b.get("type", "")),
            "pad": _beslissing_type_to_pad(b.get("type", ""), b.get("persoon", "aanvrager")),
            "aanbeveling": b.get("aanbeveling", 0),
        })
    return check_vragen


# Mapping van beslissing-type naar AanvraagData pad
_BESLISSING_PAD_MAP = {
    "inkomen_keuze": "inkomen{Persoon}[0].jaarbedrag",
    "geldverstrekker": "hypotheekInschrijvingen[0].geldverstrekker",
    "doelstelling": "doelstelling",
}

_BESLISSING_CATEGORIE_MAP = {
    "inkomen_keuze": "inkomen",
    "geldverstrekker": "hypotheek",
    "doelstelling": "algemeen",
}


def _beslissing_type_to_pad(beslissing_type: str, persoon: str = "aanvrager") -> str:
    template = _BESLISSING_PAD_MAP.get(beslissing_type, beslissing_type)
    return _resolve_persoon_pad(template, persoon)


def _beslissing_type_to_categorie(beslissing_type: str) -> str:
    return _BESLISSING_CATEGORIE_MAP.get(beslissing_type, "overig")


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

_FIELD_LABELS = {
    "voornaam": "Voornamen", "voornamen": "Voornamen",
    "achternaam": "Achternaam", "tussenvoegsel": "Tussenvoegsel",
    "voorletters": "Voorletters", "roepnaam": "Roepnaam",
    "geboortedatum": "Geboortedatum", "geboorteplaats": "Geboorteplaats",
    "geboorteland": "Geboorteland", "nationaliteit": "Nationaliteit",
    "geslacht": "Geslacht",
    "documentnummer": "Legitimatienummer", "legitimatienummer": "Legitimatienummer",
    "bsn": "BSN", "documentsoort": "Legitimatiesoort",
    "legitimatiesoort": "Legitimatiesoort",
    "afgiftedatum": "Afgiftedatum", "geldigTot": "Geldig tot",
    "afgifteplaats": "Afgifteplaats",
    "straat": "Straat", "huisnummer": "Huisnummer",
    "postcode": "Postcode", "woonplaats": "Woonplaats",
    "email": "E-mailadres", "emailadres": "E-mailadres",
    "telefoonnummer": "Telefoonnummer",
    "werkgeverNaam": "Werkgever", "functie": "Functie",
    "inDienstSinds": "In dienst sinds", "datumInDienst": "In dienst sinds",
    "brutoJaarsalaris": "Bruto jaarsalaris",
    "totaalWgvInkomen": "Totaal WGV inkomen",
    "vakantiegeldBedrag": "Vakantiegeld",
    "gemiddeldJaarToetsinkomen": "Gemiddeld jaar toetsinkomen (IBL)",
    "maandelijksePensioenbijdrage": "Maandelijkse pensioenbijdrage",
    "geldverstrekker": "Geldverstrekker", "hoofdsom": "Hoofdsom",
    "marktwaarde": "Marktwaarde", "taxatiewaarde": "Taxatiewaarde",
    "wozWaarde": "WOZ-waarde", "energielabel": "Energielabel",
    "iban": "IBAN", "ibanAanvrager": "IBAN aanvrager",
}


def _field_label(field_name: str) -> str:
    return _FIELD_LABELS.get(field_name, field_name.replace("_", " ").title())


def _format_display(value: Any) -> str:
    """Format waarde voor weergave in UI."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Ja" if value else "Nee"
    if isinstance(value, (int, float)):
        if abs(value) >= 100:
            return f"€ {value:,.0f}".replace(",", ".")
        return str(value)
    s = str(value)
    # Datum: YYYY-MM-DD → DD-MM-YYYY
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        try:
            return f"{s[8:10]}-{s[5:7]}-{s[0:4]}"
        except (IndexError, ValueError):
            pass
    return s
