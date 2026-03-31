"""Import service — vergelijk extracties met aanvraag/berekening en importeer velden.

Drie functies:
1. available_imports() — wat is er beschikbaar vs wat is er al ingevuld
2. import_fields() — importeer geselecteerde velden naar aanvraag
3. compare_field() — vergelijk een enkel veld

Alleen velden die daadwerkelijk in een hypotheekaanvraag ingevuld kunnen worden
zijn importeerbaar. De rest blijft in de extractie-verzamelbak.
"""

import logging
import os
from datetime import datetime

import httpx

logger = logging.getLogger("nat-api.import-service")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")


# ---------------------------------------------------------------------------
# Veld-mapping: alleen velden relevant voor een hypotheekaanvraag
# key = veldnaam zoals Claude het extraheert (camelCase)
# value = (label_NL, display_categorie, target_path)
#
# target_path notatie:
#   persoon.X        → {persoon}.persoon.X
#   identiteit.X     → {persoon}.identiteit.X
#   werkgever.X      → inkomen{Persoon}[0].loondienst.werkgever.X
#   dienstverband.X  → inkomen{Persoon}[0].loondienst.dienstverband.X
#   wgv.X            → inkomen{Persoon}[0].loondienst.werkgeversverklaringCalc.X
#   loondienst.X     → inkomen{Persoon}[0].loondienst.X
#   onderpand.X      → onderpand.X
#   financiering.X   → financieringsopzet.X
#   pensioen.X       → pensioen specifiek (frontend routing)
#   hypotheek.X      → hypotheek specifiek (frontend routing)
#   vermogen.X       → vermogenSectie specifiek
#   verplichtingen.X → verplichtingen specifiek
# ---------------------------------------------------------------------------
IMPORTABLE_FIELDS: dict[str, tuple[str, str, str]] = {
    # --- Persoonsgegevens ---
    "achternaam":       ("Achternaam", "Persoonsgegevens", "persoon.achternaam"),
    "voornamen":        ("Voornamen", "Persoonsgegevens", "persoon.voornamen"),
    "voorletters":      ("Voorletters", "Persoonsgegevens", "persoon.voorletters"),
    "roepnaam":         ("Roepnaam", "Persoonsgegevens", "persoon.roepnaam"),
    "geboortedatum":    ("Geboortedatum", "Persoonsgegevens", "persoon.geboortedatum"),
    "geboorteplaats":   ("Geboorteplaats", "Persoonsgegevens", "persoon.geboorteplaats"),
    "geboorteland":     ("Geboorteland", "Persoonsgegevens", "persoon.geboorteland"),
    "nationaliteit":    ("Nationaliteit", "Persoonsgegevens", "persoon.nationaliteit"),
    "geslacht":         ("Geslacht", "Persoonsgegevens", "persoon.geslacht"),
    "bsn":              ("BSN", "Persoonsgegevens", "persoon.bsn"),

    # --- Legitimatie ---
    "documentnummer":       ("Documentnummer", "Legitimatie", "identiteit.legitimatienummer"),
    "legitimatienummer":    ("Documentnummer", "Legitimatie", "identiteit.legitimatienummer"),
    "geldigTot":            ("Geldig tot", "Legitimatie", "identiteit.geldigTot"),
    "documentGeldigTot":    ("Geldig tot", "Legitimatie", "identiteit.geldigTot"),
    "verloopdatum":         ("Geldig tot", "Legitimatie", "identiteit.geldigTot"),
    "afgifteplaats":        ("Afgifteplaats", "Legitimatie", "identiteit.afgifteplaats"),
    "afgiftedatum":         ("Afgiftedatum", "Legitimatie", "identiteit.afgiftedatum"),

    # --- Werkgever ---
    "werkgeverNaam":        ("Werkgever", "Werkgever", "werkgever.naamWerkgever"),
    "naamWerkgever":        ("Werkgever", "Werkgever", "werkgever.naamWerkgever"),
    "functie":              ("Functie", "Werkgever", "dienstverband.functie"),
    "inDienstSinds":        ("In dienst sinds", "Werkgever", "dienstverband.inDienstSinds"),
    "datumInDienst":        ("In dienst sinds", "Werkgever", "dienstverband.inDienstSinds"),
    "kvkNummer":            ("KvK-nummer", "Werkgever", "werkgever.kvkNummer"),
    "adresWerkgever":       ("Adres werkgever", "Werkgever", "werkgever.adresWerkgever"),
    "adresWerknemer":       ("Adres werknemer", "Persoonsgegevens", "persoon.adres"),
    "vestigingsplaats":     ("Vestigingsplaats", "Werkgever", "werkgever.vestigingsplaats"),
    "dienstverbandType":    ("Soort dienstverband", "Werkgever", "dienstverband.soortDienstverband"),
    "soortDienstverband":   ("Soort dienstverband", "Werkgever", "dienstverband.soortDienstverband"),
    "proeftijd":            ("Proeftijd", "Werkgever", "dienstverband.proeftijd"),
    "loonbeslag":           ("Loonbeslag", "Werkgever", "dienstverband.loonbeslag"),

    # --- Inkomen (WGV) ---
    "brutoJaarsalaris":             ("Bruto jaarsalaris", "Inkomen", "wgv.brutoSalaris"),
    "brutoSalaris":                 ("Bruto jaarsalaris", "Inkomen", "wgv.brutoSalaris"),
    "vakantiegeld":                 ("Vakantiegeld", "Inkomen", "wgv.vakantiegeldBedrag"),
    "vakantiegeldBedrag":           ("Vakantiegeld", "Inkomen", "wgv.vakantiegeldBedrag"),
    "vakantiegeldPercentage":       ("Vakantiegeld %", "Inkomen", "wgv.vakantiegeldPercentage"),
    "eindejaarsuitkering":          ("Eindejaarsuitkering", "Inkomen", "wgv.eindejaarsuitkering"),
    "onregelmatigheidstoeslag":     ("Onregelmatigheidstoeslag", "Inkomen", "wgv.onregelmatigheidstoeslag"),
    "overwerk":                     ("Overwerk", "Inkomen", "wgv.overwerk"),
    "provisie":                     ("Provisie", "Inkomen", "wgv.provisie"),
    "dertiendeMaand":               ("13e maand", "Inkomen", "wgv.dertiendeMaand"),
    "compensatieUren":              ("Compensatie-uren", "Inkomen", "wgv.structureelFlexibelBudget"),
    "totaalWgvInkomen":             ("Totaal WGV inkomen", "Inkomen", "wgv.totaalWgvInkomen"),
    "structureelFlexibelBudget":    ("Structureel flexibel budget", "Inkomen", "wgv.structureelFlexibelBudget"),
    "variabelBrutoJaarinkomen":     ("Variabel bruto jaarinkomen", "Inkomen", "wgv.variabelBrutoJaarinkomen"),
    "vastToeslagOpHetInkomen":      ("Vaste toeslag", "Inkomen", "wgv.vastToeslagOpHetInkomen"),
    "vebAfgelopen12Maanden":        ("VEB afgelopen 12 mnd", "Inkomen", "wgv.vebAfgelopen12Maanden"),

    # --- Inkomen (IBL) ---
    "gemiddeldJaarToetsinkomen":    ("IBL toetsinkomen", "Inkomen", "loondienst.gemiddeldJaarToetsinkomen"),
    "toetsinkomen":                 ("IBL toetsinkomen", "Inkomen", "loondienst.gemiddeldJaarToetsinkomen"),
    "iblToetsinkomen":              ("IBL toetsinkomen", "Inkomen", "loondienst.gemiddeldJaarToetsinkomen"),

    # --- Pensioenbijdrage ---
    "maandelijksePensioenbijdrage": ("Pensioenbijdrage (mnd)", "Inkomen", "loondienst.maandelijksePensioenbijdrage"),
    "pensioenbijdrage":             ("Pensioenbijdrage (mnd)", "Inkomen", "loondienst.maandelijksePensioenbijdrage"),
    "pensioenbijdragePercentage":   ("Pensioenbijdrage %", "Inkomen", "loondienst.pensioenbijdragePercentage"),

    # --- Onderpand / Woning ---
    "koopprijs":            ("Koopsom", "Onderpand", "financiering.aankoopsomWoning"),
    "aankoopsom":           ("Koopsom", "Onderpand", "financiering.aankoopsomWoning"),
    "marktwaarde":          ("Marktwaarde", "Onderpand", "onderpand.marktwaarde"),
    "wozWaarde":            ("WOZ-waarde", "Onderpand", "onderpand.wozWaarde"),
    "energielabel":         ("Energielabel", "Onderpand", "onderpand.energielabel"),
    "bouwjaar":             ("Bouwjaar", "Onderpand", "onderpand.bouwjaar"),
    "woonoppervlakte":      ("Woonoppervlakte (m²)", "Onderpand", "onderpand.woonoppervlakte"),
    "leveringsdatum":       ("Leveringsdatum", "Onderpand", "onderpand.leveringsdatum"),
    "jaarlijkseErfpacht":   ("Erfpachtcanon (jaar)", "Onderpand", "onderpand.jaarlijkseErfpacht"),
    "erfpacht":             ("Erfpacht", "Onderpand", "onderpand.erfpacht"),
    "taxatiedatum":         ("Taxatiedatum", "Onderpand", "onderpand.taxatiedatum"),
    "waardeNaVerbouwing":   ("Waarde na verbouwing", "Onderpand", "onderpand.marktwaardeNaVerbouwing"),
    "totaalVerbouwingskosten": ("Verbouwingskosten", "Onderpand", "financiering.verbouwing"),
    "vraagprijs":           ("Vraagprijs", "Onderpand", "onderpand.vraagprijs"),

    # --- Pensioen (UPO) ---
    "ouderdomspensioenTotaalExclAow":  ("Ouderdomspensioen (excl AOW)", "Pensioen", "pensioen.ouderdomspensioen"),
    "nabestaandenpensioenPartner":     ("Nabestaandenpensioen partner", "Pensioen", "pensioen.partnerpensioen"),
    "nabestaandenpensioenKinderen":    ("Wezenpensioen", "Pensioen", "pensioen.wezenpensioen"),

    # --- Hypotheek (bestaand) ---
    "geldverstrekker":      ("Geldverstrekker", "Hypotheek", "hypotheek.geldverstrekker"),
    "restschuld":           ("Restschuld", "Hypotheek", "hypotheek.restschuld"),
    "oorspronkelijkBedrag": ("Oorspronkelijk bedrag", "Hypotheek", "hypotheek.oorspronkelijkBedrag"),
    "maandlast":            ("Maandlast", "Hypotheek", "hypotheek.maandlast"),
    "einddatumRentevast":   ("Einddatum rentevast", "Hypotheek", "hypotheek.einddatumRentevast"),
    "rentePercentage":      ("Rente %", "Hypotheek", "hypotheek.rentePercentage"),

    # --- Bankgegevens ---
    "iban":                 ("IBAN", "Bankgegevens", "vermogen.iban"),
    "rekeningnummer":       ("IBAN", "Bankgegevens", "vermogen.iban"),

    # --- Echtscheiding ---
    "partneralimentatieBedrag":  ("Partneralimentatie", "Echtscheiding", "verplichtingen.partneralimentatie"),
    "kinderalimentatieBedrag":   ("Kinderalimentatie", "Echtscheiding", "verplichtingen.kinderalimentatie"),
    "datumScheiding":            ("Datum scheiding", "Echtscheiding", "persoon.datumEchtscheiding"),
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
    "volledige naam": None,
    "overige inkomensbestandsdelen": None,
    "proeftijd verlopen": None,
    "periode": None,
    "bijzondere beloningen": None,
    "pensioenfonds": None,
    "bruto bedrag": None,
    "ingangsdatum": None,
    "adres": None,
    "datum bankgarantie": None,
    "ontbindende voorwaarden datum": None,
    "registratiedatum": None,
    "bank": None,
    "saldo": None,
    "datum": None,
    "totaal vermogen": None,
    "kredietverstrekker": None,
    "type lening": None,
    "einddatum": None,
    "verdeling vermogen": None,
    "datum afgifte": None,
    "resultaat": None,
    "toetsdatum": None,
    "hypotheekbedrag": None,
    "eigenaar": None,
    "aandeel": None,
    "kadastrale aanduiding": None,
    "inschrijving bedrag": None,
    "specificatie per post": None,
    "leningnummer": None,
    "bruto maandloon": None,
    "loonheffing": None,
    "jaar": None,
}


def _resolve_field(name: str) -> tuple[str, str, str] | None:
    """Resolve veldnaam naar (label, category, target) of None als niet importeerbaar."""
    # Directe match (camelCase)
    if name in IMPORTABLE_FIELDS:
        return IMPORTABLE_FIELDS[name]

    # Nederlandse alias (lowercase)
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
    access_token: str | None = None,
) -> dict:
    """Vergelijk beschikbare extracties met huidige aanvraag/berekening data.

    Retourneert alleen velden die daadwerkelijk in een hypotheekaanvraag
    ingevuld kunnen worden (gefilterd via IMPORTABLE_FIELDS mapping).
    """
    headers = _sb_headers(access_token)

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

    # Haal huidige aanvraag data op (als aanvraag_id gegeven)
    huidige_data = {}
    if aanvraag_id:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/aanvragen",
                headers=headers,
                params={"select": "data", "id": f"eq.{aanvraag_id}"},
            )
            resp.raise_for_status()
            rows = resp.json()
            if rows:
                huidige_data = rows[0].get("data", {}) or {}

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
    seen_fields: set[str] = set()  # Voorkom dubbelen (nieuwste wint)

    for ef in all_fields:
        sectie = ef.get("sectie", "")
        persoon = ef.get("persoon", "aanvrager")
        fields = ef.get("fields", {})
        confidences = ef.get("field_confidence", {})
        created = ef.get("created_at", "")

        for veld, waarde in fields.items():
            if waarde is None:
                continue

            # Filter: alleen importeerbare velden
            mapping = _resolve_field(veld)
            if mapping is None:
                continue

            label, category, target = mapping

            # Dedup: nieuwste wint, per (persoon, target)
            dedup_key = f"{persoon}.{target}"
            if dedup_key in seen_fields:
                continue
            seen_fields.add(dedup_key)

            # Vergelijk met huidige aanvraag data
            waarde_huidig = _find_in_aanvraag(huidige_data, target, persoon)
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
                "waarde_extractie": waarde,
                "waarde_huidig": waarde_huidig,
                "status": status,
                "confidence": confidence if isinstance(confidence, (int, float)) else 0.5,
                "bron_datum": created,
            })

    # Sorteer: categorie → persoon → label
    category_order = [
        "Persoonsgegevens", "Legitimatie", "Werkgever", "Inkomen",
        "Onderpand", "Pensioen", "Hypotheek", "Bankgegevens", "Echtscheiding",
    ]

    def sort_key(item):
        cat_idx = category_order.index(item["categorie"]) if item["categorie"] in category_order else 99
        return (cat_idx, item["persoon"], item["label"])

    imports.sort(key=sort_key)

    # Samenvatting
    nieuw = sum(1 for i in imports if i["status"] == "nieuw")
    bevestigd = sum(1 for i in imports if i["status"] == "bevestigd")
    afwijkend = sum(1 for i in imports if i["status"] == "afwijkend")

    # Dossier-analyse info
    analysis_data = analysis[0] if analysis else {}
    inkomen = analysis_data.get("inkomen_analyse", {})

    return {
        "dossier_id": dossier_id,
        "aanvraag_id": aanvraag_id,
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


def _find_in_aanvraag(data: dict, target: str, persoon: str):
    """Zoek een veld in de aanvraag data via target path."""
    if not data:
        return None

    prefix, _, field = target.partition(".")
    if not field:
        return None

    # --- persoon.X → {persoon}.persoon.X ---
    if prefix == "persoon":
        person_data = data.get(persoon if persoon != "gezamenlijk" else "aanvrager", {})
        sub = person_data.get("persoon", {})
        if isinstance(sub, dict) and field in sub:
            return sub[field]

    # --- identiteit.X → {persoon}.identiteit.X ---
    elif prefix == "identiteit":
        person_data = data.get(persoon if persoon != "gezamenlijk" else "aanvrager", {})
        sub = person_data.get("identiteit", {})
        if isinstance(sub, dict) and field in sub:
            return sub[field]

    # --- werkgever.X → inkomen{Persoon}[0].loondienst.werkgever.X ---
    elif prefix == "werkgever":
        inkomen_key = f"inkomen{persoon.capitalize()}" if persoon != "gezamenlijk" else "inkomenAanvrager"
        for item in data.get(inkomen_key, []):
            if isinstance(item, dict):
                werkgever = item.get("loondienst", {}).get("werkgever", {})
                if isinstance(werkgever, dict) and field in werkgever:
                    return werkgever[field]

    # --- dienstverband.X → inkomen{Persoon}[0].loondienst.dienstverband.X ---
    elif prefix == "dienstverband":
        inkomen_key = f"inkomen{persoon.capitalize()}" if persoon != "gezamenlijk" else "inkomenAanvrager"
        for item in data.get(inkomen_key, []):
            if isinstance(item, dict):
                dv = item.get("loondienst", {}).get("dienstverband", {})
                if isinstance(dv, dict) and field in dv:
                    return dv[field]

    # --- wgv.X → inkomen{Persoon}[0].loondienst.werkgeversverklaringCalc.X ---
    elif prefix == "wgv":
        inkomen_key = f"inkomen{persoon.capitalize()}" if persoon != "gezamenlijk" else "inkomenAanvrager"
        for item in data.get(inkomen_key, []):
            if isinstance(item, dict):
                wgv = item.get("loondienst", {}).get("werkgeversverklaringCalc", {})
                if isinstance(wgv, dict) and field in wgv:
                    return wgv[field]

    # --- loondienst.X → inkomen{Persoon}[0].loondienst.X ---
    elif prefix == "loondienst":
        inkomen_key = f"inkomen{persoon.capitalize()}" if persoon != "gezamenlijk" else "inkomenAanvrager"
        for item in data.get(inkomen_key, []):
            if isinstance(item, dict):
                ld = item.get("loondienst", {})
                if isinstance(ld, dict) and field in ld:
                    return ld[field]

    # --- onderpand.X ---
    elif prefix == "onderpand":
        onderpand = data.get("onderpand", {})
        if isinstance(onderpand, dict) and field in onderpand:
            return onderpand[field]

    # --- financiering.X → financieringsopzet.X ---
    elif prefix == "financiering":
        fin = data.get("financieringsopzet", {})
        if isinstance(fin, dict) and field in fin:
            return fin[field]

    # --- vermogen.X ---
    elif prefix == "vermogen":
        vs = data.get("vermogenSectie", {})
        if isinstance(vs, dict):
            if field == "iban":
                ibans = vs.get("iban", {})
                iban_key = f"iban{persoon.capitalize()}" if persoon != "gezamenlijk" else "ibanAanvrager"
                return ibans.get(iban_key)

    return None


def _values_match(val1, val2) -> bool:
    """Vergelijk twee waarden (flexibel: string vs number, hoofdletter-insensitief)."""
    if val1 == val2:
        return True

    # String vergelijking
    s1 = str(val1).strip().lower()
    s2 = str(val2).strip().lower()
    if s1 == s2:
        return True

    # Numerieke vergelijking (tolerantie 0.01)
    try:
        n1 = float(str(val1).replace(",", ".").replace("€", "").replace(" ", ""))
        n2 = float(str(val2).replace(",", ".").replace("€", "").replace(" ", ""))
        if abs(n1 - n2) < 0.01:
            return True
    except (ValueError, TypeError):
        pass

    return False
