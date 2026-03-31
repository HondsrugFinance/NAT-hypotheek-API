"""Import service — vergelijk extracties met aanvraag/berekening en importeer velden.

Twee contexten:
- "aanvraag": alle velden, target_aanvraag paden (voor AanvraagData structuur)
- "berekening": subset, target_berekening paden (voor invoer structuur)

Alleen velden die daadwerkelijk ingevuld kunnen worden zijn importeerbaar.
De rest blijft in de extractie-verzamelbak.
"""

import logging
import os

import httpx

logger = logging.getLogger("nat-api.import-service")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")


# ---------------------------------------------------------------------------
# Veld-mapping: alleen velden relevant voor hypotheek-tool
#
# Elk veld heeft:
#   label          — Nederlandse leesbare naam
#   categorie      — groepering in de UI
#   value_type     — "text", "date", "currency", "number", "boolean", "percent"
#   target_aanvraag  — pad in AanvraagData (voor aanvraag-pagina)
#   target_berekening — pad in invoer (voor berekening-pagina), None = niet toonbaar
#
# target_aanvraag notatie:
#   persoon.X, identiteit.X, werkgever.X, dienstverband.X, wgv.X,
#   loondienst.X, onderpand.X, financiering.X, pensioen.X, hypotheek.X,
#   vermogen.X, verplichtingen.X
#
# target_berekening notatie:
#   klantGegevens.X{P}  — {P} wordt "Aanvrager" of "Partner" op basis van persoon
#   inkomenGegevens.X{P} — idem
#   inkomenGegevens.X    — geen persoon-suffix (bijv. erfpachtcanon)
#   onderpand.X          — haalbaarheidsBerekeningen[0].onderpand.X
#   berekeningen.X       — berekeningen[0].X
# ---------------------------------------------------------------------------
IMPORTABLE_FIELDS: dict[str, dict] = {
    # --- Persoonsgegevens ---
    "achternaam":       {"label": "Achternaam", "categorie": "Persoonsgegevens", "value_type": "text",
                         "target_aanvraag": "persoon.achternaam", "target_berekening": "klantGegevens.achternaam{P}"},
    "voornamen":        {"label": "Voornamen", "categorie": "Persoonsgegevens", "value_type": "text",
                         "target_aanvraag": "persoon.voornamen", "target_berekening": None},
    "voorletters":      {"label": "Voorletters", "categorie": "Persoonsgegevens", "value_type": "text",
                         "target_aanvraag": "persoon.voorletters", "target_berekening": None},
    "roepnaam":         {"label": "Roepnaam", "categorie": "Persoonsgegevens", "value_type": "text",
                         "target_aanvraag": "persoon.roepnaam", "target_berekening": "klantGegevens.roepnaam{P}"},
    "geboortedatum":    {"label": "Geboortedatum", "categorie": "Persoonsgegevens", "value_type": "date",
                         "target_aanvraag": "persoon.geboortedatum", "target_berekening": "klantGegevens.geboortedatum{P}"},
    "geboorteplaats":   {"label": "Geboorteplaats", "categorie": "Persoonsgegevens", "value_type": "text",
                         "target_aanvraag": "persoon.geboorteplaats", "target_berekening": None},
    "geboorteland":     {"label": "Geboorteland", "categorie": "Persoonsgegevens", "value_type": "text",
                         "target_aanvraag": "persoon.geboorteland", "target_berekening": None},
    "nationaliteit":    {"label": "Nationaliteit", "categorie": "Persoonsgegevens", "value_type": "text",
                         "target_aanvraag": "persoon.nationaliteit", "target_berekening": None},
    "geslacht":         {"label": "Geslacht", "categorie": "Persoonsgegevens", "value_type": "text",
                         "target_aanvraag": "persoon.geslacht", "target_berekening": None},
    "bsn":              {"label": "BSN", "categorie": "Persoonsgegevens", "value_type": "text",
                         "target_aanvraag": "persoon.bsn", "target_berekening": None},

    # --- Adres ---
    "adresWerknemer":   {"label": "Adres", "categorie": "Adres", "value_type": "text",
                         "target_aanvraag": "persoon.adres", "target_berekening": None},

    # --- Legitimatie ---
    "documentnummer":       {"label": "Documentnummer", "categorie": "Legitimatie", "value_type": "text",
                             "target_aanvraag": "identiteit.legitimatienummer", "target_berekening": None},
    "legitimatienummer":    {"label": "Documentnummer", "categorie": "Legitimatie", "value_type": "text",
                             "target_aanvraag": "identiteit.legitimatienummer", "target_berekening": None},
    "geldigTot":            {"label": "Geldig tot", "categorie": "Legitimatie", "value_type": "date",
                             "target_aanvraag": "identiteit.geldigTot", "target_berekening": None},
    "documentGeldigTot":    {"label": "Geldig tot", "categorie": "Legitimatie", "value_type": "date",
                             "target_aanvraag": "identiteit.geldigTot", "target_berekening": None},
    "verloopdatum":         {"label": "Geldig tot", "categorie": "Legitimatie", "value_type": "date",
                             "target_aanvraag": "identiteit.geldigTot", "target_berekening": None},
    "afgifteplaats":        {"label": "Afgifteplaats", "categorie": "Legitimatie", "value_type": "text",
                             "target_aanvraag": "identiteit.afgifteplaats", "target_berekening": None},
    "afgiftedatum":         {"label": "Afgiftedatum", "categorie": "Legitimatie", "value_type": "date",
                             "target_aanvraag": "identiteit.afgiftedatum", "target_berekening": None},

    # --- Werkgever ---
    "werkgeverNaam":        {"label": "Werkgever", "categorie": "Werkgever", "value_type": "text",
                             "target_aanvraag": "werkgever.naamWerkgever", "target_berekening": None},
    "naamWerkgever":        {"label": "Werkgever", "categorie": "Werkgever", "value_type": "text",
                             "target_aanvraag": "werkgever.naamWerkgever", "target_berekening": None},
    "functie":              {"label": "Functie", "categorie": "Werkgever", "value_type": "text",
                             "target_aanvraag": "dienstverband.functie", "target_berekening": None},
    "inDienstSinds":        {"label": "In dienst sinds", "categorie": "Werkgever", "value_type": "date",
                             "target_aanvraag": "dienstverband.inDienstSinds", "target_berekening": None},
    "datumInDienst":        {"label": "In dienst sinds", "categorie": "Werkgever", "value_type": "date",
                             "target_aanvraag": "dienstverband.inDienstSinds", "target_berekening": None},
    "kvkNummer":            {"label": "KvK-nummer", "categorie": "Werkgever", "value_type": "text",
                             "target_aanvraag": "werkgever.kvkNummer", "target_berekening": None},
    "adresWerkgever":       {"label": "Adres werkgever", "categorie": "Werkgever", "value_type": "text",
                             "target_aanvraag": "werkgever.adresWerkgever", "target_berekening": None},
    "vestigingsplaats":     {"label": "Vestigingsplaats", "categorie": "Werkgever", "value_type": "text",
                             "target_aanvraag": "werkgever.vestigingsplaats", "target_berekening": None},
    "dienstverbandType":    {"label": "Soort dienstverband", "categorie": "Werkgever", "value_type": "text",
                             "target_aanvraag": "dienstverband.soortDienstverband", "target_berekening": None},
    "soortDienstverband":   {"label": "Soort dienstverband", "categorie": "Werkgever", "value_type": "text",
                             "target_aanvraag": "dienstverband.soortDienstverband", "target_berekening": None},
    "proeftijd":            {"label": "Proeftijd", "categorie": "Werkgever", "value_type": "boolean",
                             "target_aanvraag": "dienstverband.proeftijd", "target_berekening": None},
    "loonbeslag":           {"label": "Loonbeslag", "categorie": "Werkgever", "value_type": "boolean",
                             "target_aanvraag": "dienstverband.loonbeslag", "target_berekening": None},

    # --- Inkomen (WGV) ---
    "brutoJaarsalaris":             {"label": "Bruto jaarsalaris", "categorie": "Inkomen", "value_type": "currency",
                                     "target_aanvraag": "wgv.brutoSalaris", "target_berekening": None},
    "brutoSalaris":                 {"label": "Bruto jaarsalaris", "categorie": "Inkomen", "value_type": "currency",
                                     "target_aanvraag": "wgv.brutoSalaris", "target_berekening": None},
    "vakantiegeld":                 {"label": "Vakantiegeld", "categorie": "Inkomen", "value_type": "currency",
                                     "target_aanvraag": "wgv.vakantiegeldBedrag", "target_berekening": None},
    "vakantiegeldBedrag":           {"label": "Vakantiegeld", "categorie": "Inkomen", "value_type": "currency",
                                     "target_aanvraag": "wgv.vakantiegeldBedrag", "target_berekening": None},
    "vakantiegeldPercentage":       {"label": "Vakantiegeld %", "categorie": "Inkomen", "value_type": "percent",
                                     "target_aanvraag": "wgv.vakantiegeldPercentage", "target_berekening": None},
    "eindejaarsuitkering":          {"label": "Eindejaarsuitkering", "categorie": "Inkomen", "value_type": "currency",
                                     "target_aanvraag": "wgv.eindejaarsuitkering", "target_berekening": None},
    "onregelmatigheidstoeslag":     {"label": "Onregelmatigheidstoeslag", "categorie": "Inkomen", "value_type": "currency",
                                     "target_aanvraag": "wgv.onregelmatigheidstoeslag", "target_berekening": None},
    "overwerk":                     {"label": "Overwerk", "categorie": "Inkomen", "value_type": "currency",
                                     "target_aanvraag": "wgv.overwerk", "target_berekening": None},
    "provisie":                     {"label": "Provisie", "categorie": "Inkomen", "value_type": "currency",
                                     "target_aanvraag": "wgv.provisie", "target_berekening": None},
    "dertiendeMaand":               {"label": "13e maand", "categorie": "Inkomen", "value_type": "currency",
                                     "target_aanvraag": "wgv.dertiendeMaand", "target_berekening": None},
    "compensatieUren":              {"label": "Compensatie-uren", "categorie": "Inkomen", "value_type": "currency",
                                     "target_aanvraag": "wgv.structureelFlexibelBudget", "target_berekening": None},
    "totaalWgvInkomen":             {"label": "Totaal WGV inkomen", "categorie": "Inkomen", "value_type": "currency",
                                     "target_aanvraag": "wgv.totaalWgvInkomen",
                                     "target_berekening": "inkomenGegevens.hoofdinkomen{P}"},
    "structureelFlexibelBudget":    {"label": "Structureel flexibel budget", "categorie": "Inkomen", "value_type": "currency",
                                     "target_aanvraag": "wgv.structureelFlexibelBudget", "target_berekening": None},
    "variabelBrutoJaarinkomen":     {"label": "Variabel bruto jaarinkomen", "categorie": "Inkomen", "value_type": "currency",
                                     "target_aanvraag": "wgv.variabelBrutoJaarinkomen", "target_berekening": None},
    "vastToeslagOpHetInkomen":      {"label": "Vaste toeslag", "categorie": "Inkomen", "value_type": "currency",
                                     "target_aanvraag": "wgv.vastToeslagOpHetInkomen", "target_berekening": None},
    "vebAfgelopen12Maanden":        {"label": "VEB afgelopen 12 mnd", "categorie": "Inkomen", "value_type": "currency",
                                     "target_aanvraag": "wgv.vebAfgelopen12Maanden", "target_berekening": None},

    # --- Inkomen (IBL) ---
    "gemiddeldJaarToetsinkomen":    {"label": "IBL toetsinkomen", "categorie": "Inkomen", "value_type": "currency",
                                     "target_aanvraag": "loondienst.gemiddeldJaarToetsinkomen",
                                     "target_berekening": "inkomenGegevens.hoofdinkomen{P}"},
    "toetsinkomen":                 {"label": "IBL toetsinkomen", "categorie": "Inkomen", "value_type": "currency",
                                     "target_aanvraag": "loondienst.gemiddeldJaarToetsinkomen",
                                     "target_berekening": "inkomenGegevens.hoofdinkomen{P}"},
    "iblToetsinkomen":              {"label": "IBL toetsinkomen", "categorie": "Inkomen", "value_type": "currency",
                                     "target_aanvraag": "loondienst.gemiddeldJaarToetsinkomen",
                                     "target_berekening": "inkomenGegevens.hoofdinkomen{P}"},

    # --- Pensioenbijdrage ---
    "maandelijksePensioenbijdrage": {"label": "Pensioenbijdrage (mnd)", "categorie": "Inkomen", "value_type": "currency",
                                     "target_aanvraag": "loondienst.maandelijksePensioenbijdrage", "target_berekening": None},
    "pensioenbijdrage":             {"label": "Pensioenbijdrage (mnd)", "categorie": "Inkomen", "value_type": "currency",
                                     "target_aanvraag": "loondienst.maandelijksePensioenbijdrage", "target_berekening": None},
    "pensioenbijdragePercentage":   {"label": "Pensioenbijdrage %", "categorie": "Inkomen", "value_type": "percent",
                                     "target_aanvraag": "loondienst.pensioenbijdragePercentage", "target_berekening": None},

    # --- Onderpand / Woning ---
    "koopprijs":            {"label": "Koopsom", "categorie": "Onderpand", "value_type": "currency",
                             "target_aanvraag": "financiering.aankoopsomWoning",
                             "target_berekening": "berekeningen.aankoopsomWoning"},
    "aankoopsom":           {"label": "Koopsom", "categorie": "Onderpand", "value_type": "currency",
                             "target_aanvraag": "financiering.aankoopsomWoning",
                             "target_berekening": "berekeningen.aankoopsomWoning"},
    "marktwaarde":          {"label": "Marktwaarde", "categorie": "Onderpand", "value_type": "currency",
                             "target_aanvraag": "onderpand.marktwaarde",
                             "target_berekening": "onderpand.marktwaarde"},
    "wozWaarde":            {"label": "WOZ-waarde", "categorie": "Onderpand", "value_type": "currency",
                             "target_aanvraag": "onderpand.wozWaarde",
                             "target_berekening": "berekeningen.wozWaarde"},
    "energielabel":         {"label": "Energielabel", "categorie": "Onderpand", "value_type": "text",
                             "target_aanvraag": "onderpand.energielabel",
                             "target_berekening": "onderpand.energielabel"},
    "bouwjaar":             {"label": "Bouwjaar", "categorie": "Onderpand", "value_type": "number",
                             "target_aanvraag": "onderpand.bouwjaar", "target_berekening": None},
    "woonoppervlakte":      {"label": "Woonoppervlakte (m\u00b2)", "categorie": "Onderpand", "value_type": "number",
                             "target_aanvraag": "onderpand.woonoppervlakte", "target_berekening": None},
    "leveringsdatum":       {"label": "Leveringsdatum", "categorie": "Onderpand", "value_type": "date",
                             "target_aanvraag": "onderpand.leveringsdatum", "target_berekening": None},
    "jaarlijkseErfpacht":   {"label": "Erfpachtcanon (jaar)", "categorie": "Onderpand", "value_type": "currency",
                             "target_aanvraag": "onderpand.jaarlijkseErfpacht",
                             "target_berekening": "inkomenGegevens.erfpachtcanon"},
    "erfpacht":             {"label": "Erfpacht", "categorie": "Onderpand", "value_type": "boolean",
                             "target_aanvraag": "onderpand.erfpacht", "target_berekening": None},
    "taxatiedatum":         {"label": "Taxatiedatum", "categorie": "Onderpand", "value_type": "date",
                             "target_aanvraag": "onderpand.taxatiedatum", "target_berekening": None},
    "waardeNaVerbouwing":   {"label": "Waarde na verbouwing", "categorie": "Onderpand", "value_type": "currency",
                             "target_aanvraag": "onderpand.marktwaardeNaVerbouwing", "target_berekening": None},
    "totaalVerbouwingskosten": {"label": "Verbouwingskosten", "categorie": "Onderpand", "value_type": "currency",
                                "target_aanvraag": "financiering.verbouwing",
                                "target_berekening": "berekeningen.verbouwing"},
    "vraagprijs":           {"label": "Vraagprijs", "categorie": "Onderpand", "value_type": "currency",
                             "target_aanvraag": "onderpand.vraagprijs", "target_berekening": None},

    # --- Pensioen (UPO) ---
    "ouderdomspensioenTotaalExclAow":  {"label": "Ouderdomspensioen (excl AOW)", "categorie": "Pensioen", "value_type": "currency",
                                         "target_aanvraag": "pensioen.ouderdomspensioen", "target_berekening": None},
    "nabestaandenpensioenPartner":     {"label": "Nabestaandenpensioen partner", "categorie": "Pensioen", "value_type": "currency",
                                         "target_aanvraag": "pensioen.partnerpensioen", "target_berekening": None},
    "nabestaandenpensioenKinderen":    {"label": "Wezenpensioen", "categorie": "Pensioen", "value_type": "currency",
                                         "target_aanvraag": "pensioen.wezenpensioen", "target_berekening": None},

    # --- Hypotheek (bestaand) ---
    "geldverstrekker":      {"label": "Geldverstrekker", "categorie": "Hypotheek", "value_type": "text",
                             "target_aanvraag": "hypotheek.geldverstrekker", "target_berekening": None},
    "restschuld":           {"label": "Restschuld", "categorie": "Hypotheek", "value_type": "currency",
                             "target_aanvraag": "hypotheek.restschuld", "target_berekening": None},
    "oorspronkelijkBedrag": {"label": "Oorspronkelijk bedrag", "categorie": "Hypotheek", "value_type": "currency",
                             "target_aanvraag": "hypotheek.oorspronkelijkBedrag", "target_berekening": None},
    "maandlast":            {"label": "Maandlast", "categorie": "Hypotheek", "value_type": "currency",
                             "target_aanvraag": "hypotheek.maandlast", "target_berekening": None},
    "einddatumRentevast":   {"label": "Einddatum rentevast", "categorie": "Hypotheek", "value_type": "date",
                             "target_aanvraag": "hypotheek.einddatumRentevast", "target_berekening": None},
    "rentePercentage":      {"label": "Rente %", "categorie": "Hypotheek", "value_type": "percent",
                             "target_aanvraag": "hypotheek.rentePercentage", "target_berekening": None},

    # --- Bankgegevens ---
    "iban":                 {"label": "IBAN", "categorie": "Bankgegevens", "value_type": "text",
                             "target_aanvraag": "vermogen.iban", "target_berekening": None},
    "rekeningnummer":       {"label": "IBAN", "categorie": "Bankgegevens", "value_type": "text",
                             "target_aanvraag": "vermogen.iban", "target_berekening": None},

    # --- Verplichtingen / Echtscheiding ---
    "partneralimentatieBedrag":  {"label": "Partneralimentatie", "categorie": "Echtscheiding", "value_type": "currency",
                                  "target_aanvraag": "verplichtingen.partneralimentatie",
                                  "target_berekening": "inkomenGegevens.partneralimentatieBetalen{P}"},
    "kinderalimentatieBedrag":   {"label": "Kinderalimentatie", "categorie": "Echtscheiding", "value_type": "currency",
                                  "target_aanvraag": "verplichtingen.kinderalimentatie", "target_berekening": None},
    "datumScheiding":            {"label": "Datum scheiding", "categorie": "Echtscheiding", "value_type": "date",
                                  "target_aanvraag": "persoon.datumEchtscheiding", "target_berekening": None},
}

# Aliases: Nederlandse veldnamen (lowercase) → camelCase key in IMPORTABLE_FIELDS
_DUTCH_ALIASES: dict[str, str | None] = {
    "bruto jaarsalaris": "brutoJaarsalaris",
    "bruto jaarloon": "brutoJaarsalaris",
    "datum in dienst": "datumInDienst",
    "type dienstverband": "dienstverbandType",
    "werkgever": "werkgeverNaam",
    "koopprijs": "koopprijs",
    "leveringsdatum": "leveringsdatum",
    "erfpacht": "erfpacht",
    "marktwaarde": "marktwaarde",
    "taxatiedatum": "taxatiedatum",
    "waarde na verbouwing": "waardeNaVerbouwing",
    "vraagprijs": "vraagprijs",
    "woonoppervlakte": "woonoppervlakte",
    "energielabel": "energielabel",
    "geldverstrekker": "geldverstrekker",
    "oorspronkelijk bedrag": "oorspronkelijkBedrag",
    "restschuld": "restschuld",
    "rente": "rentePercentage",
    "maandlast": "maandlast",
    "einddatum rentevast": "einddatumRentevast",
    "rekeningnummer (iban)": "rekeningnummer",
    "datum scheiding": "datumScheiding",
    "partneralimentatie bedrag": "partneralimentatieBedrag",
    "kinderalimentatie bedrag": "kinderalimentatieBedrag",
    "totaal verbouwingskosten": "totaalVerbouwingskosten",
    "achternaam": "achternaam",
    "voorletters": "voorletters",
    "geboortedatum": "geboortedatum",
    "geboorteplaats": "geboorteplaats",
    "nationaliteit": "nationaliteit",
    "documentnummer": "documentnummer",
    "verloopdatum": "verloopdatum",
    # Niet-importeerbare velden (None = bewust overslaan)
    "volledige naam": None, "overige inkomensbestandsdelen": None,
    "proeftijd verlopen": None, "periode": None, "bijzondere beloningen": None,
    "pensioenfonds": None, "bruto bedrag": None, "ingangsdatum": None,
    "adres": None, "datum bankgarantie": None, "ontbindende voorwaarden datum": None,
    "registratiedatum": None, "bank": None, "saldo": None, "datum": None,
    "totaal vermogen": None, "kredietverstrekker": None, "type lening": None,
    "einddatum": None, "verdeling vermogen": None, "datum afgifte": None,
    "resultaat": None, "toetsdatum": None, "hypotheekbedrag": None,
    "eigenaar": None, "aandeel": None, "kadastrale aanduiding": None,
    "inschrijving bedrag": None, "specificatie per post": None,
    "leningnummer": None, "bruto maandloon": None, "loonheffing": None, "jaar": None,
}


def _resolve_field(name: str) -> dict | None:
    """Resolve veldnaam naar mapping dict of None als niet importeerbaar."""
    if name in IMPORTABLE_FIELDS:
        return IMPORTABLE_FIELDS[name]

    lowered = name.lower().strip()
    alias = _DUTCH_ALIASES.get(lowered)
    if alias is not None and alias in IMPORTABLE_FIELDS:
        return IMPORTABLE_FIELDS[alias]

    return None


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def _sb_headers(access_token: str | None = None) -> dict:
    key = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
    token = access_token or key
    return {
        "apikey": key,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Hoofd-functie
# ---------------------------------------------------------------------------

async def get_available_imports(
    dossier_id: str,
    aanvraag_id: str | None = None,
    context: str = "aanvraag",
    access_token: str | None = None,
) -> dict:
    """Vergelijk beschikbare extracties met huidige aanvraag/berekening data.

    Args:
        context: "aanvraag" of "berekening" — bepaalt welke velden en target-paden.
    """
    headers = _sb_headers(access_token)
    target_key = "target_aanvraag" if context == "aanvraag" else "target_berekening"

    # Haal alle extracted_fields op voor dit dossier
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/extracted_fields",
            headers=headers,
            params={
                "select": "id,sectie,persoon,fields,field_confidence,status,created_at",
                "dossier_id": f"eq.{dossier_id}",
                "status": "in.(pending_review,accepted)",
                "order": "created_at.desc",
            },
        )
        resp.raise_for_status()
        all_fields = resp.json()

    # Haal IBL resultaten op
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/extracted_fields",
            headers=headers,
            params={
                "select": "id,sectie,persoon,fields,field_confidence,status,created_at",
                "dossier_id": f"eq.{dossier_id}",
                "sectie": "eq.inkomen_ibl",
                "order": "created_at.desc",
            },
        )
        resp.raise_for_status()
        ibl_fields = resp.json()
        all_fields.extend(ibl_fields)

    # Haal huidige data op (aanvraag of berekening)
    huidige_data = {}
    if aanvraag_id:
        table = "aanvragen" if context == "aanvraag" else "dossiers"
        data_field = "data" if context == "aanvraag" else "invoer"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/{table}",
                headers=headers,
                params={"select": data_field, "id": f"eq.{aanvraag_id}"},
            )
            resp.raise_for_status()
            rows = resp.json()
            if rows:
                huidige_data = rows[0].get(data_field, {}) or {}

    # Haal dossier-analyse op voor samenvatting
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/dossier_analysis",
            headers=headers,
            params={
                "select": "samenvatting,compleetheid,inkomen_analyse,documenten_verwerkt,updated_at",
                "dossier_id": f"eq.{dossier_id}",
                "order": "updated_at.desc",
                "limit": "1",
            },
        )
        resp.raise_for_status()
        analysis = resp.json()

    # Bouw import-overzicht — alleen importeerbare velden
    imports = []
    seen_fields: set[str] = set()

    for ef in all_fields:
        sectie = ef.get("sectie", "")
        persoon = ef.get("persoon", "aanvrager")
        fields = ef.get("fields", {})
        confidences = ef.get("field_confidence", {})
        created = ef.get("created_at", "")

        for veld, waarde in fields.items():
            if waarde is None:
                continue

            mapping = _resolve_field(veld)
            if mapping is None:
                continue

            # Filter: veld moet een target hebben voor deze context
            target = mapping.get(target_key)
            if target is None:
                continue

            label = mapping["label"]
            category = mapping["categorie"]
            value_type = mapping["value_type"]

            # Resolve {P} placeholder
            if "{P}" in target:
                suffix = "Partner" if persoon == "partner" else "Aanvrager"
                target = target.replace("{P}", suffix)

            # Dedup: nieuwste wint, per (persoon, target)
            dedup_key = f"{persoon}.{target}"
            if dedup_key in seen_fields:
                continue
            seen_fields.add(dedup_key)

            # Vergelijk met huidige data
            if context == "aanvraag":
                waarde_huidig = _find_in_aanvraag(huidige_data, mapping["target_aanvraag"], persoon)
            else:
                waarde_huidig = _find_in_berekening(huidige_data, target, persoon)

            confidence = confidences.get(veld, 0.5)

            if waarde_huidig is None:
                status = "nieuw"
            elif _values_match(waarde, waarde_huidig):
                status = "bevestigd"
            else:
                status = "afwijkend"

            imports.append({
                "veld": veld,
                "label": label,
                "categorie": category,
                "sectie": sectie,
                "persoon": persoon,
                "target": target,
                "value_type": value_type,
                "waarde_extractie": waarde,
                "waarde_huidig": waarde_huidig,
                "status": status,
                "confidence": confidence if isinstance(confidence, (int, float)) else 0.5,
                "bron_datum": created,
            })

    # Sorteer: persoon → categorie → label
    category_order = [
        "Persoonsgegevens", "Adres", "Legitimatie", "Werkgever", "Inkomen",
        "Onderpand", "Hypotheek", "Pensioen", "Bankgegevens", "Echtscheiding",
    ]
    persoon_order = {"aanvrager": 0, "partner": 1, "gezamenlijk": 2}

    def sort_key(item):
        cat_idx = category_order.index(item["categorie"]) if item["categorie"] in category_order else 99
        pers_idx = persoon_order.get(item["persoon"], 9)
        return (pers_idx, cat_idx, item["label"])

    imports.sort(key=sort_key)

    nieuw = sum(1 for i in imports if i["status"] == "nieuw")
    bevestigd = sum(1 for i in imports if i["status"] == "bevestigd")
    afwijkend = sum(1 for i in imports if i["status"] == "afwijkend")

    analysis_data = analysis[0] if analysis else {}
    inkomen = analysis_data.get("inkomen_analyse", {})

    return {
        "dossier_id": dossier_id,
        "aanvraag_id": aanvraag_id,
        "context": context,
        "documenten_verwerkt": analysis_data.get("documenten_verwerkt", len(all_fields)),
        "laatste_verwerking": analysis_data.get("updated_at"),
        "dossier_samenvatting": analysis_data.get("samenvatting"),
        "inkomen_analyse": inkomen,
        "imports": imports,
        "samenvatting": {
            "nieuw": nieuw,
            "bevestigd": bevestigd,
            "afwijkend": afwijkend,
            "totaal": len(imports),
        },
    }


# ---------------------------------------------------------------------------
# Find in aanvraag (AanvraagData structuur)
# ---------------------------------------------------------------------------

def _find_in_aanvraag(data: dict, target: str, persoon: str):
    """Zoek een veld in de aanvraag data via target path."""
    if not data:
        return None

    prefix, _, field = target.partition(".")
    if not field:
        return None

    if prefix == "persoon":
        person_data = data.get(persoon if persoon != "gezamenlijk" else "aanvrager", {})
        sub = person_data.get("persoon", {})
        if isinstance(sub, dict) and field in sub:
            return sub[field]

    elif prefix == "identiteit":
        person_data = data.get(persoon if persoon != "gezamenlijk" else "aanvrager", {})
        sub = person_data.get("identiteit", {})
        if isinstance(sub, dict) and field in sub:
            return sub[field]

    elif prefix == "werkgever":
        inkomen_key = f"inkomen{persoon.capitalize()}" if persoon != "gezamenlijk" else "inkomenAanvrager"
        for item in data.get(inkomen_key, []):
            if isinstance(item, dict):
                werkgever = item.get("loondienst", {}).get("werkgever", {})
                if isinstance(werkgever, dict) and field in werkgever:
                    return werkgever[field]

    elif prefix == "dienstverband":
        inkomen_key = f"inkomen{persoon.capitalize()}" if persoon != "gezamenlijk" else "inkomenAanvrager"
        for item in data.get(inkomen_key, []):
            if isinstance(item, dict):
                dv = item.get("loondienst", {}).get("dienstverband", {})
                if isinstance(dv, dict) and field in dv:
                    return dv[field]

    elif prefix == "wgv":
        inkomen_key = f"inkomen{persoon.capitalize()}" if persoon != "gezamenlijk" else "inkomenAanvrager"
        for item in data.get(inkomen_key, []):
            if isinstance(item, dict):
                wgv = item.get("loondienst", {}).get("werkgeversverklaringCalc", {})
                if isinstance(wgv, dict) and field in wgv:
                    return wgv[field]

    elif prefix == "loondienst":
        inkomen_key = f"inkomen{persoon.capitalize()}" if persoon != "gezamenlijk" else "inkomenAanvrager"
        for item in data.get(inkomen_key, []):
            if isinstance(item, dict):
                ld = item.get("loondienst", {})
                if isinstance(ld, dict) and field in ld:
                    return ld[field]

    elif prefix == "onderpand":
        onderpand = data.get("onderpand", {})
        if isinstance(onderpand, dict) and field in onderpand:
            return onderpand[field]

    elif prefix == "financiering":
        fin = data.get("financieringsopzet", {})
        if isinstance(fin, dict) and field in fin:
            return fin[field]

    elif prefix == "vermogen":
        vs = data.get("vermogenSectie", {})
        if isinstance(vs, dict):
            if field == "iban":
                ibans = vs.get("iban", {})
                iban_key = f"iban{persoon.capitalize()}" if persoon != "gezamenlijk" else "ibanAanvrager"
                return ibans.get(iban_key)

    return None


# ---------------------------------------------------------------------------
# Find in berekening (invoer structuur)
# ---------------------------------------------------------------------------

def _find_in_berekening(data: dict, target: str, persoon: str):
    """Zoek een veld in de berekening invoer via target path.

    Target paden:
      klantGegevens.achternaamAanvrager
      inkomenGegevens.hoofdinkomenAanvrager
      onderpand.marktwaarde → haalbaarheidsBerekeningen[0].onderpand.X
      berekeningen.aankoopsomWoning → berekeningen[0].X
    """
    if not data:
        return None

    prefix, _, field = target.partition(".")
    if not field:
        return None

    if prefix == "klantGegevens":
        kg = data.get("klantGegevens", {})
        if isinstance(kg, dict) and field in kg:
            return kg[field]

    elif prefix == "inkomenGegevens":
        ig = data.get("inkomenGegevens", {})
        if isinstance(ig, dict) and field in ig:
            return ig[field]

    elif prefix == "onderpand":
        # haalbaarheidsBerekeningen[0].onderpand.X
        hb = data.get("haalbaarheidsBerekeningen", [])
        if hb and isinstance(hb[0], dict):
            onderpand = hb[0].get("onderpand", {})
            if isinstance(onderpand, dict) and field in onderpand:
                return onderpand[field]

    elif prefix == "berekeningen":
        # berekeningen[0].X
        ber = data.get("berekeningen", [])
        if ber and isinstance(ber[0], dict) and field in ber[0]:
            return ber[0][field]

    return None


def _values_match(val1, val2) -> bool:
    """Vergelijk twee waarden (flexibel: string vs number, hoofdletter-insensitief)."""
    if val1 == val2:
        return True

    s1 = str(val1).strip().lower()
    s2 = str(val2).strip().lower()
    if s1 == s2:
        return True

    try:
        n1 = float(str(val1).replace(",", ".").replace("\u20ac", "").replace(" ", ""))
        n2 = float(str(val2).replace(",", ".").replace("\u20ac", "").replace(" ", ""))
        if abs(n1 - n2) < 0.01:
            return True
    except (ValueError, TypeError):
        pass

    return False
