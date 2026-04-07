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
    # Identificatie: paspoort/ID zijn leidend. Rijbewijs NIET gebruiken
    # (kan van ex-partner zijn, is geen geldig legitimatiebewijs voor hypotheek)
    "paspoort": [_PERSOON_MAP, _IDENTITEIT_MAP],
    "id_kaart": [_PERSOON_MAP, _IDENTITEIT_MAP],
    # rijbewijs: bewust NIET gemapped (kan van ex-partner zijn, geen geldig legitimatiebewijs)

    # Inkomen: WGV > loonstrook > jaaropgave. IBL apart.
    "werkgeversverklaring": [_WERKGEVER_MAP, _DIENSTVERBAND_MAP, _WGV_INKOMEN_MAP],
    "salarisstrook": [_WGV_INKOMEN_MAP, _WERKGEVER_MAP, _DIENSTVERBAND_MAP],
    "loonstrook": [_WGV_INKOMEN_MAP, _WERKGEVER_MAP, _DIENSTVERBAND_MAP],
    "inkomen_ibl": [_IBL_MAP],
    "jaaropgave": [_BANK_MAP, _WGV_INKOMEN_MAP],

    # Woning: taxatierapport leidend, koopovereenkomst secundair
    "taxatierapport": [_WONING_MAP],
    "koopovereenkomst": [_WONING_MAP],
    "concept_koopovereenkomst": [_WONING_MAP],
    "verkoopovereenkomst": [_WONING_MAP],
    "energielabel": [_WONING_MAP],
    "koop_aanneemovereenkomst": [_WONING_MAP],
    "kadaster_eigendom": [_WONING_MAP],

    # Hypotheek: hypotheekoverzicht leidend. GEEN adres mappen (komt uit Lovable).
    "hypotheekoverzicht": [_HYPOTHEEK_MAP, _WONING_MAP],  # _ADRES_MAP VERWIJDERD
    "kadaster_hypotheek": [_HYPOTHEEK_MAP],

    # Financieel
    "bankafschrift": [_BANK_MAP],
    "nota_van_afrekening": [_HYPOTHEEK_MAP],
    "vermogensoverzicht": [_BANK_MAP],

    # Verplichtingen
    "leningoverzicht": [_VERPLICHTING_MAP],
    "bkr": [_VERPLICHTING_MAP],
    "bkr_registratie": [_VERPLICHTING_MAP],

    # Pensioen
    "pensioenspecificatie": [_PENSIOEN_MAP],
    "upo": [_PENSIOEN_MAP],

    # Juridisch: alleen persoon + woning, GEEN adres
    "echtscheidingsconvenant": [_WONING_MAP, _HYPOTHEEK_MAP, _PERSOON_MAP],
    "akte_van_verdeling": [_PERSOON_MAP, _WONING_MAP],

    # IB-aangifte: GEEN adres mappen (komt uit Lovable)
    "ib_aangifte": [_PERSOON_MAP],
    "aangifte_inkomstenbelasting": [_PERSOON_MAP],
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

    # Zorg dat verplichte structuur compleet is (voorkom Lovable crashes)
    _ensure_required_structure(merged_data)

    # Bouw check_vragen uit stap 3 beslissingen
    check_vragen = _build_check_vragen_from_beslissingen(beslissingen or [])

    # Python-gegenereerde checkvragen (onafhankelijk van Claude stap 3)
    _add_python_check_vragen(check_vragen, merged_data, extracted_fields)

    logger.info("Field mapper: %d velden gemapped, %d checkvragen", len(velden), len(check_vragen))
    return merged_data, velden, check_vragen


def _add_python_check_vragen(check_vragen: list, merged_data: dict, extracted_fields: list):
    """Voeg checkvragen toe die Python zelf kan detecteren, onafhankelijk van stap 3."""
    existing_types = {cv.get("id") for cv in check_vragen}

    # Inkomen keuze: als WGV + IBL beide beschikbaar
    for person, prefix in [("aanvrager", "inkomenAanvrager"), ("partner", "inkomenPartner")]:
        inkomen = merged_data.get(prefix, [])
        if not inkomen:
            continue

        jaarbedrag = inkomen[0].get("jaarbedrag")
        ibl = inkomen[0].get("loondienst", {}).get("gemiddeldJaarToetsinkomen")

        if jaarbedrag and ibl and f"inkomen_keuze_{person}" not in existing_types:
            check_vragen.append({
                "id": f"inkomen_keuze_{person}",
                "vraag": f"Welk inkomen hanteren voor de {person}?",
                "opties": [
                    {"label": f"WGV: \u20ac {jaarbedrag:,.0f}".replace(",", "."), "pad": f"{prefix}[0].jaarbedrag", "waarde": jaarbedrag},
                    {"label": f"IBL: \u20ac {ibl:,.0f}".replace(",", "."), "pad": f"{prefix}[0].jaarbedrag", "waarde": ibl},
                ],
                "bron": "werkgeversverklaring, UWV",
                "evidence": "Twee inkomensberekeningen beschikbaar",
                "categorie": "inkomen",
                "pad": f"{prefix}[0].jaarbedrag",
                "aanbeveling": 0,
            })

    # Doelstelling: altijd als checkvraag als die niet al bestaat
    if "doelstelling" not in existing_types and not merged_data.get("doelstelling"):
        # Detecteer mogelijke doelstelling uit documenten
        has_koop = any(ef.get("sectie") == "koopovereenkomst" for ef in extracted_fields)
        has_hyp = any(ef.get("sectie") == "hypotheekoverzicht" for ef in extracted_fields)
        has_echtscheiding = any(ef.get("sectie") in ("echtscheidingsconvenant", "akte_van_verdeling") for ef in extracted_fields)

        opties = []
        if has_koop:
            opties.append({"label": "Aankoop bestaande bouw", "pad": "doelstelling", "waarde": "aankoop_bestaande_bouw"})
        if has_echtscheiding:
            opties.append({"label": "Partner uitkopen", "pad": "doelstelling", "waarde": "partner_uitkopen"})
        if has_hyp and not has_koop:
            opties.append({"label": "Hypotheek verhogen", "pad": "doelstelling", "waarde": "hypotheek_verhogen"})
            opties.append({"label": "Hypotheek oversluiten", "pad": "doelstelling", "waarde": "hypotheek_oversluiten"})

        if opties:
            check_vragen.append({
                "id": "doelstelling",
                "vraag": "Wat is het doel van deze hypotheekaanvraag?",
                "opties": opties,
                "bron": "",
                "evidence": "Afgeleid uit aanwezige documenten",
                "categorie": "algemeen",
                "pad": "doelstelling",
                "aanbeveling": 0,
            })


def _ensure_required_structure(data: dict):
    """Garandeer dat de verplichte structuur aanwezig is zodat Lovable niet crasht.

    Lovable verwacht bepaalde arrays en objecten. Als de mapper ze niet vult
    maar er WEL gerelateerde data is, moeten de verplichte velden met defaults
    worden aangevuld.
    """
    import uuid

    # hypotheekInschrijvingen: elk item moet id, onderpandWoningIds, eigenaar, rangorde hebben
    for inschrijving in data.get("hypotheekInschrijvingen", []):
        if "id" not in inschrijving:
            inschrijving["id"] = str(uuid.uuid4())
        if "onderpandWoningIds" not in inschrijving:
            # Koppel aan eerste woning als die er is
            woningen = data.get("woningen", [])
            inschrijving["onderpandWoningIds"] = [woningen[0]["id"]] if woningen and "id" in woningen[0] else []
        if "eigenaar" not in inschrijving:
            inschrijving["eigenaar"] = ""
        if "rangorde" not in inschrijving:
            inschrijving["rangorde"] = 1
        if "inschrijving" not in inschrijving:
            inschrijving["inschrijving"] = None  # Lovable verwacht dit veld
        # nhg: moet boolean zijn, niet string
        if isinstance(inschrijving.get("nhg"), str):
            inschrijving["nhg"] = inschrijving["nhg"].lower() in ("ja", "true", "yes")

    # hypotheken: elk item moet id, inschrijvingId, leningdelen array hebben
    for hyp in data.get("hypotheken", []):
        if "id" not in hyp:
            hyp["id"] = str(uuid.uuid4())
        if "inschrijvingId" not in hyp:
            # Koppel aan eerste inschrijving als die er is
            inschr = data.get("hypotheekInschrijvingen", [])
            hyp["inschrijvingId"] = inschr[0]["id"] if inschr else ""
        # Leningdelen: elk moet id hebben
        for ld in hyp.get("leningdelen", []):
            if "id" not in ld:
                ld["id"] = str(uuid.uuid4())

    # woningen: elk item moet id hebben
    for woning in data.get("woningen", []):
        if "id" not in woning:
            woning["id"] = str(uuid.uuid4())

    # vermogenSectie: moet items array hebben
    if "vermogenSectie" in data:
        if "items" not in data["vermogenSectie"]:
            data["vermogenSectie"]["items"] = []
        if "iban" not in data["vermogenSectie"]:
            data["vermogenSectie"]["iban"] = {"ibanAanvrager": "", "ibanPartner": ""}

    # verplichtingen: elk item moet id hebben
    for verpl in data.get("verplichtingen", []):
        if "id" not in verpl:
            verpl["id"] = str(uuid.uuid4())

    # inkomen items: elk moet id hebben
    for prefix in ("inkomenAanvrager", "inkomenPartner"):
        for item in data.get(prefix, []):
            if "id" not in item:
                item["id"] = str(uuid.uuid4())


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

            # Nabestaandenpensioen
            nb_partner = fields.get("nabestaandenpensioenPartner")
            nb_kinderen = fields.get("nabestaandenpensioenKinderen")
            pensioenleeftijd = fields.get("pensioenleeftijd")

            if nb_partner:
                _set_nested(merged_data, f"inkomen{p}[0].pensioenData.partnerpensioen.verzekerdVoor", nb_partner)
                velden.append({
                    "pad": f"inkomen{p}[0].pensioenData.partnerpensioen.verzekerdVoor",
                    "label": "Nabestaandenpensioen partner",
                    "waarde": nb_partner,
                    "waarde_display": _format_display(nb_partner, "nabestaandenpensioenPartner"),
                    "bron": sectie, "status": "nieuw", "source": "extracted",
                })

            if nb_kinderen:
                _set_nested(merged_data, f"inkomen{p}[0].pensioenData.wezenpensioen.verzekerd", nb_kinderen)
                velden.append({
                    "pad": f"inkomen{p}[0].pensioenData.wezenpensioen.verzekerd",
                    "label": "Wezenpensioen",
                    "waarde": nb_kinderen,
                    "waarde_display": _format_display(nb_kinderen, "nabestaandenpensioenKinderen"),
                    "bron": sectie, "status": "nieuw", "source": "extracted",
                })

            if pensioenleeftijd:
                _set_nested(merged_data, f"inkomen{p}[1].pensioenData.ouderdomspensioen.ingangsdatum", str(pensioenleeftijd))
                velden.append({
                    "pad": f"inkomen{p}[1].pensioenData.ouderdomspensioen.ingangsdatum",
                    "label": "Pensioenleeftijd",
                    "waarde": pensioenleeftijd,
                    "waarde_display": str(pensioenleeftijd),
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

        # Achternaam + tussenvoegsel split
        # Case 1: achternaam bevat een tussenvoegsel (bijv. "van Hall" → "van" + "Hall")
        # Case 2: achternaam mist, zoek in extracted_fields
        _TUSSENVOEGSELS = {
            "de", "den", "der", "het", "ten", "ter", "van", "in",
            "de la", "in de", "in den", "in het", "in 't",
            "op de", "op den", "op het", "op 't",
            "van de", "van den", "van der", "van het", "van 't",
            "uit de", "uit den", "uit het", "uit 't",
            "aan de", "aan den", "aan het", "aan 't",
            "bij de", "bij den", "bij het",
            "onder de", "onder het", "over de", "over het",
            "voor de", "voor den",
            "van de la", "uit de la",
        }

        def _split_naam(full_name):
            """Split een volledige achternaam in tussenvoegsel + achternaam."""
            parts = full_name.split()
            if len(parts) < 2:
                return "", full_name
            best_tv = ""
            for i in range(len(parts) - 1):
                candidate = " ".join(parts[:i+1]).lower()
                if candidate in _TUSSENVOEGSELS:
                    best_tv = " ".join(parts[:i+1]).lower()
            if best_tv:
                achternaam = " ".join(parts[len(best_tv.split()):])
                return best_tv, achternaam
            return "", full_name

        achternaam = persoon_data.get("achternaam", "")
        tussenvoegsel = persoon_data.get("tussenvoegsel", "")

        if achternaam and not tussenvoegsel and " " in achternaam:
            # Case 1: achternaam bevat waarschijnlijk een tussenvoegsel
            tv, naam = _split_naam(achternaam)
            if tv:
                _set_nested(merged_data, f"{person_prefix}.persoon.tussenvoegsel", tv)
                _set_nested(merged_data, f"{person_prefix}.persoon.achternaam", naam)
                logger.info("Achternaam gesplitst: '%s' -> tv='%s', naam='%s'", achternaam, tv, naam)

        elif not achternaam:
            # Case 2: achternaam mist, zoek in extracted_fields
            for ef in extracted_fields:
                if ef.get("persoon", "") not in (person_prefix, "gezamenlijk"):
                    continue
                if ef.get("sectie", "") not in ("paspoort", "id_kaart"):
                    continue
                fields = ef.get("fields", {})
                full_name = fields.get("naam", "") or fields.get("achternaam_volledig", "") or fields.get("achternaam", "")
                if not full_name:
                    continue
                tv, naam = _split_naam(full_name)
                if tv:
                    _set_nested(merged_data, f"{person_prefix}.persoon.tussenvoegsel", tv)
                _set_nested(merged_data, f"{person_prefix}.persoon.achternaam", naam)
                logger.info("Achternaam uit extractie: '%s' -> tv='%s', naam='%s'", full_name, tv, naam)
                break

        # Roepnaam: eerste voornaam als Lovable het niet al heeft
        if voornamen and not persoon_data.get("roepnaam"):
            roepnaam = voornamen.split()[0] if voornamen.split() else ""
            if roepnaam:
                _set_nested(merged_data, f"{person_prefix}.persoon.roepnaam", roepnaam)

        # GeldigTot berekenen als die mist maar afgiftedatum er is
        # Paspoort: geldig 10 jaar na afgiftedatum
        ident = merged_data.get(person_prefix, {}).get("identiteit", {})
        if ident.get("afgiftedatum") and not ident.get("geldigTot"):
            try:
                from datetime import datetime, timedelta
                afgifte = ident["afgiftedatum"]
                if isinstance(afgifte, str) and len(afgifte) == 10:
                    dt = datetime.strptime(afgifte, "%Y-%m-%d")
                    geldig_tot = dt.replace(year=dt.year + 10)
                    _set_nested(merged_data, f"{person_prefix}.identiteit.geldigTot", geldig_tot.strftime("%Y-%m-%d"))
                    logger.info("geldigTot berekend: %s + 10 jaar = %s", afgifte, geldig_tot.strftime("%Y-%m-%d"))
            except (ValueError, TypeError):
                pass

        # Legitimatiesoort ALTIJD afleiden uit welke documenten er zijn
        # (step 2 levert dit niet betrouwbaar)
        current_soort = merged_data.get(person_prefix, {}).get("identiteit", {}).get("legitimatiesoort", "")
        if not current_soort or current_soort not in ("paspoort", "europese_id"):
            has_paspoort = any(
                ef.get("sectie") == "paspoort" and ef.get("persoon", "") in (person_prefix, "gezamenlijk")
                for ef in extracted_fields
            )
            has_id = any(
                ef.get("sectie") == "id_kaart" and ef.get("persoon", "") in (person_prefix, "gezamenlijk")
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
