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
    "eerderGehuwd": "{persoon}.persoon.eerderGehuwd",
    "datumEchtscheiding": "{persoon}.persoon.datumEchtscheiding",
    "weduweWeduwnaar": "{persoon}.persoon.weduweWeduwnaar",
}

# Legitimatie (paspoort, ID-kaart)
_IDENTITEIT_MAP = {
    "documentnummer": "{persoon}.identiteit.legitimatienummer",
    "legitimatienummer": "{persoon}.identiteit.legitimatienummer",
    # bsn: bewust NIET gemapped (privacy, staat in _SKIP_FIELDS)
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
    "gemiddeldUrenPerWeek": "inkomen{Persoon}[0].loondienst.dienstverband.gemiddeldUrenPerWeek",
    "beroepstype": "inkomen{Persoon}[0].loondienst.dienstverband.beroepstype",
    "dienstbetrekkingBijFamilie": "inkomen{Persoon}[0].loondienst.dienstverband.dienstbetrekkingBijFamilie",
    "einddatumContract": "inkomen{Persoon}[0].loondienst.dienstverband.einddatumContract",
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
    "structureelFlexibelBudget": "inkomen{Persoon}[0].loondienst.werkgeversverklaringCalc.structureelFlexibelBudget",
    "variabelBrutoJaarinkomen": "inkomen{Persoon}[0].loondienst.werkgeversverklaringCalc.variabelBrutoJaarinkomen",
    "vastToeslagOpHetInkomen": "inkomen{Persoon}[0].loondienst.werkgeversverklaringCalc.vastToeslagOpHetInkomen",
    "vebAfgelopen12Maanden": "inkomen{Persoon}[0].loondienst.werkgeversverklaringCalc.vebAfgelopen12Maanden",
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

# Pensioen — wordt NIET via simpele mapping afgehandeld maar via _set_derived_fields
# omdat pensioen volledige inkomen-items vereist met type="pensioen" en type="uitkering"
_PENSIOEN_MAP = {}  # leeg — pensioen gaat via speciale logica

# Verplichtingen
_VERPLICHTING_MAP = {
    "kredietbedrag": "verplichtingen[0].kredietbedrag",
    "maandbedrag": "verplichtingen[0].maandbedrag",
    "saldo": "verplichtingen[0].saldo",
    "kredietnummer": "verplichtingen[0].kredietnummer",
    "type": "verplichtingen[0].type",
    "maatschappij": "verplichtingen[0].maatschappij",
    "status": "verplichtingen[0].status",
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
    "salarisstrook": [_WGV_INKOMEN_MAP, _WERKGEVER_MAP, _DIENSTVERBAND_MAP],
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
    "loonstrook": [_WGV_INKOMEN_MAP, _WERKGEVER_MAP, _DIENSTVERBAND_MAP],
    # IB-aangifte bevat persoonsgegevens + adres
    "ib_aangifte": [_PERSOON_MAP, _ADRES_MAP],
    "aangifte_inkomstenbelasting": [_PERSOON_MAP, _ADRES_MAP],
    # Verplichtingen
    "leningoverzicht": [_VERPLICHTING_MAP],
    "bkr": [_VERPLICHTING_MAP],
    "bkr_registratie": [_VERPLICHTING_MAP],
    # Woningdocumenten
    "concept_koopovereenkomst": [_WONING_MAP],
    "verkoopovereenkomst": [_WONING_MAP],
    "energielabel": [_WONING_MAP],
    "koop_aanneemovereenkomst": [_WONING_MAP],
    # Financieel
    "nota_van_afrekening": [_HYPOTHEEK_MAP],
    "vermogensoverzicht": [_BANK_MAP],
    # Juridisch
    "beschikking_rechtbank": [_PERSOON_MAP],
}

# Velden die NOOIT ingevuld mogen worden door de mapper
_SKIP_FIELDS = {
    "einddatum",  # Default = AOW-datum in Lovable, niet overschrijven
    "bsn",        # Privacy-gevoelig, niet opslaan in aanvraag (backlog: zwartlakken)
    # WGV sub-inkomens: alleen het totaal (totaalWgvInkomen) telt
    "brutoJaarsalaris", "brutoMaandloon",
    "vakantiegeldBedrag", "vakantiegeldPercentage",
    "eindejaarsuitkering", "onregelmatigheidstoeslag",
    "overwerk", "provisie", "dertiendeMaand",
    "structureelFlexibelBudget", "variabelBrutoJaarinkomen",
    "vastToeslagOpHetInkomen", "vebAfgelopen12Maanden",
    "pensioenbijdragePercentage",
}

# _SKIP_IF_ZERO niet meer nodig — WGV deelbedragen staan nu in _SKIP_FIELDS
_SKIP_IF_ZERO: set[str] = set()

# Waarde-transformaties voor dropdown-velden
_BOOL_TO_JA_NEE = {True: "Ja", False: "Nee", "True": "Ja", "False": "Nee", "true": "Ja", "false": "Nee", "Ja": "Ja", "Nee": "Nee"}

_VALUE_TRANSFORMS: dict[str, dict] = {
    "geslacht": {"M": "man", "V": "vrouw", "m": "man", "v": "vrouw", "Man": "man", "Vrouw": "vrouw"},
    "legitimatiesoort": {
        "Paspoort": "paspoort", "paspoort": "paspoort",
        "ID-kaart": "europese_id", "Europese ID": "europese_id", "ID kaart": "europese_id",
        "rijbewijs": None,  # Rijbewijs is geen geldig legitimatietype voor hypotheek → negeren
    },
    "directeurAandeelhouder": _BOOL_TO_JA_NEE,
    "proeftijd": _BOOL_TO_JA_NEE,
    "proeftijdVerstreken": _BOOL_TO_JA_NEE,
    "loonbeslag": _BOOL_TO_JA_NEE,
    "onderhandseLening": _BOOL_TO_JA_NEE,
    "dienstbetrekkingBijFamilie": _BOOL_TO_JA_NEE,
    "nhg": _BOOL_TO_JA_NEE,
    "erfpacht": _BOOL_TO_JA_NEE,

    # Dienstverband: document-tekst → Lovable dropdown
    "soortDienstverband": {
        "arbeidsovereenkomst voor onbepaalde tijd": "Loondienst – vast",
        "arbeidsovereenkomst voor bepaalde tijd": "Loondienst – zonder intentieverklaring",
        "arbeidsovereenkomst onbepaalde tijd": "Loondienst – vast",
        "arbeidsovereenkomst bepaalde tijd": "Loondienst – zonder intentieverklaring",
        "vast": "Loondienst – vast",
        "onbepaalde tijd": "Loondienst – vast",
        "bepaalde tijd": "Loondienst – zonder intentieverklaring",
        "Loondienst – vast": "Loondienst – vast",
    },

    # Type woning: document-tekst → Lovable dropdown (woning/appartement/overig)
    "typeWoning": {
        "Tussen-/schakelwoning": "woning", "tussenwoning": "woning",
        "Vrijstaande woning": "woning", "vrijstaand": "woning",
        "Hoekwoning": "woning", "hoekwoning": "woning",
        "2-onder-1-kap": "woning", "2-onder-1-kapwoning": "woning",
        "Semi-bungalow": "woning", "Bungalow": "woning",
        "Rijtjeswoning": "woning", "Geschakelde woning": "woning",
        "woning": "woning", "Woning": "woning",
        "appartement": "appartement", "Appartement": "appartement",
        "Galerijflat": "appartement", "Bovenwoning": "appartement",
        "Benedenwoning": "appartement", "Maisonnette": "appartement",
        "appartementsrecht": "appartement",
    },

    # Soort onderpand: document-tekst → Lovable dropdown
    "soortOnderpand": {
        "Tussen-/schakelwoning": "tussenwoning", "Tussenwoning": "tussenwoning",
        "Vrijstaande woning": "vrijstaand", "Vrijstaand": "vrijstaand",
        "Semi-bungalow": "vrijstaand", "Bungalow": "vrijstaand",
        "Hoekwoning": "hoekwoning",
        "2-onder-1-kap": "2-onder-1-kap", "2-onder-1-kapwoning": "2-onder-1-kap",
        "Galerijflat": "galerijflat", "galerijflat": "galerijflat",
        "Bovenwoning": "bovenwoning", "Benedenwoning": "benedenwoning",
        "Maisonnette": "maisonnette",
        "appartementsrecht": "galerijflat",
        "Woning": "tussenwoning",  # generieke fallback
        "Woonboerderij": "woonboerderij",
    },

    # Energielabel
    "energielabel": {
        "Onbekend": "geen_label", "onbekend": "geen_label",
        "Geen label": "geen_label", "geen label": "geen_label",
        "N.v.t.": "geen_label",
    },

    # Woning toepassing
    "woningToepassing": {
        "eigenbewoond": "eigen_woning", "eigen bewoning": "eigen_woning",
        "Eigen bewoning": "eigen_woning", "eigen_woning": "eigen_woning",
        "huur": "huurwoning", "huurwoning": "huurwoning",
    },

    # Woning status
    "woningstatus": {
        "verkregen_via_verdeling": "behouden",
        "bestaande bouw": None,  # Geen geldige woningstatus → weglaten
        "Bestaande bouw": None,
        "behouden": "behouden", "verkopen": "verkopen",
        "verkocht_onder_voorbehoud": "verkocht_onder_voorbehoud",
        "verkocht_definitief": "verkocht_definitief",
    },

    # Waarde vastgesteld met
    "waardeVastgesteldMet": {
        "taxatierapport": "taxatierapport", "Taxatierapport": "taxatierapport",
        "desktoptaxatie": "desktoptaxatie", "Desktoptaxatie": "desktoptaxatie",
        "akte van verdeling": None,  # Geen geldige optie → weglaten
    },

    # Eigenaar: probeer te matchen, anders weglaten
    "eigenaar": {
        "gezamenlijk": "gezamenlijk", "Gezamenlijk": "gezamenlijk",
        "aanvrager": "aanvrager", "Aanvrager": "aanvrager",
        "partner": "partner", "Partner": "partner",
        "Volle eigendom": None,  # Niet te mappen zonder context → weglaten
        "verkoper": None,  # Niet relevant → weglaten
    },
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
    # Lege strings → None (niet invullen)
    if value == "" or value is None:
        return None

    # Skip 0-waarden voor WGV deelbedragen (ruis)
    if field_name in _SKIP_IF_ZERO and (value == 0 or value == 0.0):
        return None

    if field_name in _VALUE_TRANSFORMS:
        transforms = _VALUE_TRANSFORMS[field_name]
        if value in transforms:
            return transforms[value]
        # String versie proberen
        str_val = str(value).strip()
        if str_val in transforms:
            return transforms[str_val]
        # Lowercase proberen
        if str_val.lower() in {k.lower() if isinstance(k, str) else k: k for k in transforms}:
            for k, v in transforms.items():
                if isinstance(k, str) and k.lower() == str_val.lower():
                    return v

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
    # Sorteer extracted_fields op bronprioriteit: paspoort > id_kaart > rijbewijs > rest
    # Dit zorgt dat paspoort-data altijd voorrang krijgt boven rijbewijs
    _BRON_PRIORITEIT = {
        "paspoort": 0, "id_kaart": 1, "rijbewijs": 2,
        "werkgeversverklaring": 3, "salarisstrook": 4, "loonstrook": 4,
        "inkomen_ibl": 5, "taxatierapport": 6, "hypotheekoverzicht": 7,
        "kadaster_eigendom": 8, "kadaster_hypotheek": 9,
        "koopovereenkomst": 10, "jaaropgave": 11, "bankafschrift": 12,
    }
    sorted_fields = sorted(
        extracted_fields,
        key=lambda ef: _BRON_PRIORITEIT.get(ef.get("sectie", ""), 99),
    )

    merged_data: dict = {}
    velden: list[dict] = []
    seen_pads: set[str] = set()

    for ef in sorted_fields:
        sectie = ef.get("sectie", "")
        persoon = ef.get("persoon", "aanvrager")
        fields = ef.get("fields", {})

        if not fields or not sectie:
            continue

        # Zoek de mapping-tabellen voor deze sectie
        mappings = _SECTIE_MAPPINGS.get(sectie, [])
        if not mappings:
            logger.warning("Unmapped sectie: '%s' (%d velden overgeslagen)", sectie, len(fields))
            continue

        # Speciaal: leningdelen array (uit hypotheekoverzicht)
        if "leningdelen" in fields and isinstance(fields["leningdelen"], list):
            for idx, ld in enumerate(fields["leningdelen"]):
                if not isinstance(ld, dict):
                    continue
                for ld_field, ld_value in ld.items():
                    if ld_field in _SKIP_FIELDS:
                        continue
                    ld_value = _transform_value(ld_field, ld_value)
                    if ld_value is None:
                        continue
                    if ld_field in _LENINGDEEL_MAP:
                        pad = _LENINGDEEL_MAP[ld_field].replace("{idx}", str(idx))
                        if pad not in seen_pads:
                            seen_pads.add(pad)
                            _set_nested(merged_data, pad, ld_value)
                            velden.append({
                                "pad": pad, "label": _field_label(ld_field),
                                "waarde": ld_value, "waarde_display": _format_display(ld_value, ld_field),
                                "bron": sectie, "status": "nieuw", "source": "extracted",
                            })

        for field_name, value in fields.items():
            if field_name in _SKIP_FIELDS or field_name == "leningdelen":
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
                # Veld niet in mapping → loggen zodat we het kunnen toevoegen
                logger.warning("Unmapped field: sectie=%s veld=%s waarde=%s", sectie, field_name, str(value)[:50])
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
                "waarde_display": _format_display(value, field_name),
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

        # Pensioen: maak aparte inkomen-items met type="pensioen" en "uitkering"
        if sectie in ("pensioenspecificatie", "upo"):
            fields = ef.get("fields", {})
            pensioen_bedrag = fields.get("ouderdomspensioenTotaalExclAow")
            aow_bedrag = fields.get("aowBedrag")

            if pensioen_bedrag:
                pensioen_prefix = f"inkomen{p}[1]"
                _set_nested(merged_data, f"{pensioen_prefix}.type", "pensioen")
                _set_nested(merged_data, f"{pensioen_prefix}.soort", "ouderdomspensioen")
                _set_nested(merged_data, f"{pensioen_prefix}.inkomstenbron", "Pensioenfonds")
                _set_nested(merged_data, f"{pensioen_prefix}.jaarbedrag", pensioen_bedrag)
                velden.append({
                    "pad": f"{pensioen_prefix}.jaarbedrag",
                    "label": "Ouderdomspensioen (excl. AOW)",
                    "waarde": pensioen_bedrag,
                    "waarde_display": _format_display(pensioen_bedrag, "jaarbedrag"),
                    "bron": sectie, "status": "nieuw", "source": "extracted",
                })

            if aow_bedrag:
                aow_prefix = f"inkomen{p}[2]"
                _set_nested(merged_data, f"{aow_prefix}.type", "uitkering")
                _set_nested(merged_data, f"{aow_prefix}.soort", "AOW")
                _set_nested(merged_data, f"{aow_prefix}.inkomstenbron", "Sociale Verzekeringsbank")
                _set_nested(merged_data, f"{aow_prefix}.jaarbedrag", aow_bedrag)
                _set_nested(merged_data, f"{aow_prefix}.isAOW", True)
                velden.append({
                    "pad": f"{aow_prefix}.jaarbedrag",
                    "label": "AOW-uitkering",
                    "waarde": aow_bedrag,
                    "waarde_display": _format_display(aow_bedrag, "jaarbedrag"),
                    "bron": sectie, "status": "nieuw", "source": "extracted",
                })


    # Afgeleide velden na alle extracties
    for person_prefix in ["aanvrager", "partner"]:
        persoon_data = merged_data.get(person_prefix, {}).get("persoon", {})

        # Voorletters afleiden uit voornamen
        voornamen = persoon_data.get("voornamen", "")
        if voornamen and not persoon_data.get("voorletters"):
            voorletters = ".".join(n[0].upper() for n in voornamen.split() if n) + "."
            _set_nested(merged_data, f"{person_prefix}.persoon.voorletters", voorletters)
            velden.append({
                "pad": f"{person_prefix}.persoon.voorletters", "label": "Voorletters",
                "waarde": voorletters, "waarde_display": voorletters,
                "bron": "(afgeleid)", "status": "nieuw", "source": "inferred",
            })

        # Roepnaam: eerste voornaam als Lovable het niet al heeft
        if voornamen and not persoon_data.get("roepnaam"):
            roepnaam = voornamen.split()[0] if voornamen.split() else ""
            if roepnaam:
                _set_nested(merged_data, f"{person_prefix}.persoon.roepnaam", roepnaam)

        # Legitimatiesoort afleiden uit welke documenten er zijn
        ident = merged_data.get(person_prefix, {}).get("identiteit", {})
        if ident.get("legitimatienummer") and not ident.get("legitimatiesoort"):
            # Check of er een paspoort-extractie is voor deze persoon
            has_paspoort = any(
                ef.get("sectie") in ("paspoort",) and ef.get("persoon", "") in (person_prefix, "gezamenlijk")
                for ef in extracted_fields
            )
            has_id = any(
                ef.get("sectie") in ("id_kaart",) and ef.get("persoon", "") in (person_prefix, "gezamenlijk")
                for ef in extracted_fields
            )
            if has_paspoort:
                _set_nested(merged_data, f"{person_prefix}.identiteit.legitimatiesoort", "paspoort")
            elif has_id:
                _set_nested(merged_data, f"{person_prefix}.identiteit.legitimatiesoort", "europese_id")

    # heeftPartner afleiden
    has_partner_docs = any(ef.get("persoon") == "partner" for ef in extracted_fields)
    if has_partner_docs and not merged_data.get("heeftPartner"):
        _set_nested(merged_data, "heeftPartner", True)


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
    "ondernemersinkomen": "inkomen{Persoon}[0].jaarbedrag",
}

_BESLISSING_CATEGORIE_MAP = {
    "inkomen_keuze": "inkomen",
    "geldverstrekker": "hypotheek",
    "doelstelling": "algemeen",
    "ondernemersinkomen": "inkomen",
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


# Velden die GEEN bedrag zijn, ook al zijn het getallen ≥ 100
_NOT_CURRENCY_FIELDS = {
    "bouwjaar", "eigendomAandeelAanvrager", "eigendomAandeelPartner",
    "bsn", "legitimatienummer", "hypotheeknummer", "kredietnummer",
    "kvkNummer", "rsin", "looptijd", "renteVastPeriode",
    "gemiddeldUrenPerWeek", "telefoonnummer", "huisnummer",
    "postcode", "iban", "ibanAanvrager", "ibanPartner",
}


def _format_display(value: Any, field_name: str = "") -> str:
    """Format waarde voor weergave in UI."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Ja" if value else "Nee"
    if isinstance(value, (int, float)):
        # Niet-bedrag velden: geen € teken
        if field_name in _NOT_CURRENCY_FIELDS:
            return str(int(value)) if value == int(value) else str(value)
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
