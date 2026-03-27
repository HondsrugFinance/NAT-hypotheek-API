"""Hernoem en verplaats documenten op SharePoint — van _inbox naar hoofdmap."""

import logging
import re

from sharepoint import client as sp_client

logger = logging.getLogger("nat-api.rename-move")

# Afkortingen voor documenttypen
TYPE_LABELS = {
    "paspoort": "Paspoort",
    "id_kaart": "ID-kaart",
    "salarisstrook": "Loonstrook",
    "werkgeversverklaring": "WGV",
    "uwv_verzekeringsbericht": "UWV",
    "ibl_resultaat": "IBL",
    "ibl_toetsinkomen": "IBL",
    "ib_aangifte": "IB",
    "jaarrapport": "JR",
    "ib60": "IB60",
    "pensioenspecificatie": "UPO",
    "koopovereenkomst": "Koopovereenkomst",
    "concept_koopovereenkomst": "Concept koopovereenkomst",
    "verkoopovereenkomst": "Verkoopovereenkomst",
    "verkoopbrochure": "Verkoopbrochure",
    "taxatierapport": "Taxatierapport",
    "verbouwingsspecificatie": "Verbouwingsspecificatie",
    "energielabel": "Energielabel",
    "koop_aanneemovereenkomst": "Koop-aanneemovereenkomst",
    "meerwerkoverzicht": "Meerwerkoverzicht",
    "hypotheekoverzicht": "Hypotheekoverzicht",
    "bankafschrift": "Bankafschrift",
    "vermogensoverzicht": "Vermogensoverzicht",
    "leningoverzicht": "Leningoverzicht",
    "nota_van_afrekening": "Nota van afrekening",
    "echtscheidingsconvenant": "Echtscheiding - Convenant",
    "beschikking_rechtbank": "Echtscheiding - Beschikking rechtbank",
    "inschrijving_burgerlijke_stand": "Echtscheiding - Inschrijving burgerlijke stand",
    "akte_van_verdeling": "Echtscheiding - Akte van verdeling",
    "bkr": "BKR",
    "toekenningsbesluit_uitkering": "Toekenningsbesluit",
    "betaalspecificatie_uitkering": "Betaalspecificatie",
    "arbeidsmarktscan": "Arbeidsmarktscan",
}

# Documenten waar het jaar achteraan komt (meerdere jaren per persoon)
YEAR_SUFFIX_TYPES = {"ib_aangifte", "jaarrapport", "ib60"}

# Documenten met periode (maand)
PERIOD_PREFIX_TYPES = {"salarisstrook", "betaalspecificatie_uitkering"}

# Woningdocumenten (adres i.p.v. persoonsnaam)
WONING_TYPES = {
    "koopovereenkomst", "concept_koopovereenkomst", "verkoopovereenkomst",
    "verkoopbrochure", "taxatierapport", "verbouwingsspecificatie",
    "energielabel", "koop_aanneemovereenkomst", "meerwerkoverzicht",
}


def _sanitize(text: str) -> str:
    """Verwijder ongeldige tekens voor SharePoint bestandsnamen."""
    # Verwijder: " * : < > ? / \ |
    clean = re.sub(r'["*:<>?/\\|]', '', text)
    # Vervang meerdere spaties door één
    clean = re.sub(r'\s+', ' ', clean).strip()
    # Verwijder punt aan einde (SharePoint beperking)
    clean = clean.rstrip('.')
    return clean


def build_filename_v2(
    document_type: str,
    persoon: str,
    heeft_partner: bool,
    extraction_data: dict,
    dossier_context: dict,
    original_ext: str = ".pdf",
) -> str:
    """Bouw een leesbare bestandsnaam op basis van documenttype en extractie.

    Schema:
      Eén persoon: Type.ext of Type YYYY-MM.ext
      Stel: Type - Voornaam Achternaam.ext
      Meerdere jaren: Type Naam - YYYY.ext
      Woning: Type - Adres.ext

    Args:
        document_type: bijv. "werkgeversverklaring"
        persoon: "aanvrager", "partner", "gezamenlijk"
        heeft_partner: True als het dossier een partner heeft
        extraction_data: dict met geëxtraheerde velden (stap 1 of stap 2)
        dossier_context: {"aanvrager_naam": "...", "partner_naam": "...", ...}
        original_ext: bijv. ".pdf" of ".jpg"

    Returns:
        Leesbare bestandsnaam
    """
    label = TYPE_LABELS.get(document_type, document_type.replace("_", " ").title())
    ext = original_ext.lower() if original_ext.startswith(".") else f".{original_ext.lower()}"

    # Bepaal persoonsnaam
    naam = ""
    if persoon == "aanvrager":
        naam = dossier_context.get("aanvrager_naam", "").strip()
    elif persoon == "partner":
        naam = dossier_context.get("partner_naam", "").strip()

    if not naam and persoon == "aanvrager":
        naam = "Aanvrager"
    elif not naam and persoon == "partner":
        naam = "Partner"

    # Haal jaar/periode uit extractie
    jaar = _extract_jaar(extraction_data)
    periode = _extract_periode(extraction_data)
    bedrijfsnaam = _extract_bedrijfsnaam(extraction_data)
    adres = _extract_adres(extraction_data)
    geldverstrekker = _extract_geldverstrekker(extraction_data)

    # === Woningdocumenten: Type - Adres ===
    if document_type in WONING_TYPES:
        if adres:
            filename = f"{label} - {adres}"
        else:
            filename = label
        return _sanitize(filename) + ext

    # === Hypotheekoverzicht: Type - Geldverstrekker ===
    if document_type == "hypotheekoverzicht" and geldverstrekker:
        return _sanitize(f"{label} - {geldverstrekker}") + ext

    # === Documenten met meerdere jaren: Type Naam - YYYY ===
    if document_type in YEAR_SUFFIX_TYPES:
        if document_type == "jaarrapport" and bedrijfsnaam:
            # JR Bedrijfsnaam - 2023
            naam_deel = bedrijfsnaam
        else:
            # IB Voornaam Achternaam - 2023
            naam_deel = naam

        if jaar:
            filename = f"{label} {naam_deel} - {jaar}"
        else:
            filename = f"{label} {naam_deel}"
        return _sanitize(filename) + ext

    # === Documenten met periode: Type YYYY-MM - Naam ===
    if document_type in PERIOD_PREFIX_TYPES:
        if periode:
            if heeft_partner and naam and naam not in ("Aanvrager", "Partner", ""):
                filename = f"{label} {periode} - {naam}"
            elif heeft_partner:
                filename = f"{label} {periode} - {naam}"
            else:
                filename = f"{label} {periode}"
        else:
            if heeft_partner:
                filename = f"{label} - {naam}"
            else:
                filename = label
        return _sanitize(filename) + ext

    # === Standaard: Type - Naam (of alleen Type bij alleenstaand) ===
    if heeft_partner:
        filename = f"{label} - {naam}"
    else:
        filename = label

    return _sanitize(filename) + ext


def _extract_jaar(data: dict) -> str | None:
    """Extraheer boekjaar/belastingjaar uit extractie data."""
    # Zoek in structured_fields (stap 1+2 gecombineerd)
    for key in ["belastingjaar", "boekjaar", "jaar", "belastingJaar"]:
        val = data.get(key)
        if val:
            # Kan een int of string zijn
            s = str(val).strip()
            if re.match(r"^\d{4}$", s):
                return s

    # Zoek in extracted_data (stap 1 ruwe data)
    for section in ["datums", "financieel", "document_specifiek"]:
        section_data = data.get(section, {})
        if isinstance(section_data, dict):
            for key in ["boekjaar", "belastingjaar", "jaar"]:
                val = section_data.get(key)
                if val:
                    s = str(val).strip()
                    if re.match(r"^\d{4}$", s):
                        return s
    return None


def _extract_periode(data: dict) -> str | None:
    """Extraheer periode (YYYY-MM) uit extractie data."""
    for key in ["salarisperiode", "periode", "salarisPerdiode"]:
        val = data.get(key)
        if val:
            s = str(val).strip()
            # Formaat: "2026-03" of "03/2026" of "2026-03-01"
            m = re.search(r"(\d{4})-(\d{2})", s)
            if m:
                return f"{m.group(1)}-{m.group(2)}"
            m = re.search(r"(\d{2})/(\d{4})", s)
            if m:
                return f"{m.group(2)}-{m.group(1)}"

    # Zoek in datums sectie
    datums = data.get("datums", {})
    if isinstance(datums, dict):
        for key in ["salarisperiode", "periode"]:
            val = datums.get(key)
            if val:
                s = str(val).strip()
                m = re.search(r"(\d{4})-(\d{2})", s)
                if m:
                    return f"{m.group(1)}-{m.group(2)}"
    return None


def _extract_bedrijfsnaam(data: dict) -> str | None:
    """Extraheer bedrijfsnaam uit extractie data (voor jaarrekeningen)."""
    for key in ["bedrijfsnaam", "bedrijfsNaam", "naam_bedrijf"]:
        val = data.get(key)
        if val and isinstance(val, str):
            return val.strip()

    # Zoek in persoonsgegevens of document_specifiek
    for section in ["persoonsgegevens", "document_specifiek"]:
        section_data = data.get(section, {})
        if isinstance(section_data, dict):
            for key in ["bedrijfsnaam", "naam_bedrijf"]:
                val = section_data.get(key)
                if val and isinstance(val, str):
                    return val.strip()
    return None


def _extract_adres(data: dict) -> str | None:
    """Extraheer kort adres (straat + huisnummer + plaats) uit extractie data."""
    # Zoek in adressen sectie
    adressen = data.get("adressen", {})
    if isinstance(adressen, dict):
        for key in ["verkoop_object", "woning_adres", "object_adres", "adres"]:
            val = adressen.get(key)
            if val:
                if isinstance(val, dict):
                    straat = val.get("straat", "")
                    woonplaats = val.get("woonplaats", "")
                    if straat and woonplaats:
                        return f"{straat} {woonplaats}"
                elif isinstance(val, str):
                    # Kort maken: alleen straat + huisnr + plaats
                    # "Mr. P.J. Troelstralaan 223, 9402 BH Assen" → "Troelstralaan 223 Assen"
                    return _shorten_address(val)

    # Zoek in structured fields
    for key in ["adresStraat", "woningAdres", "Adres"]:
        val = data.get(key)
        if val and isinstance(val, str):
            return _shorten_address(val)

    return None


def _shorten_address(address: str) -> str:
    """Kort een adres in voor bestandsnaam."""
    # Verwijder postcode (4 cijfers + 2 letters)
    short = re.sub(r'\d{4}\s*[A-Z]{2}\s*', '', address)
    # Verwijder komma's
    short = short.replace(",", "")
    # Verwijder dubbele spaties
    short = re.sub(r'\s+', ' ', short).strip()
    return short


def _extract_geldverstrekker(data: dict) -> str | None:
    """Extraheer geldverstrekker uit extractie data."""
    for key in ["geldverstrekker", "geldverstrekkerNaam", "hypotheekverstrekker"]:
        val = data.get(key)
        if val and isinstance(val, str):
            return val.strip()

    financieel = data.get("financieel", {})
    if isinstance(financieel, dict):
        for key in ["hypotheekverstrekker", "geldverstrekker"]:
            val = financieel.get(key)
            if val and isinstance(val, str):
                return val.strip()
    return None


# === Oude functie behouden voor backward compatibility ===
def build_filename(
    dossiernummer: str,
    document_type: str,
    achternaam: str,
    original_ext: str = ".pdf",
) -> str:
    """Legacy bestandsnaam builder. Gebruik build_filename_v2 voor nieuwe code."""
    clean_type = re.sub(r'[^a-z0-9_]', '_', document_type.lower())
    clean_naam = re.sub(r'[^a-zA-Z0-9]', '', achternaam)
    ext = original_ext.lower() if original_ext.startswith(".") else f".{original_ext.lower()}"
    return f"{dossiernummer}_{clean_type}_{clean_naam}{ext}"


async def _unique_filename(hoofdpad: str, filename: str) -> str:
    """Zorg dat de bestandsnaam uniek is in de map. Voeg (1), (2) etc. toe als nodig."""
    try:
        items = await sp_client.list_folder(hoofdpad)
        existing_names = {item.get("name", "") for item in items}
    except Exception:
        return filename  # Map bestaat niet of is leeg, naam is uniek

    if filename not in existing_names:
        return filename

    # Splits naam en extensie
    if "." in filename:
        base, ext = filename.rsplit(".", 1)
        ext = f".{ext}"
    else:
        base = filename
        ext = ""

    counter = 1
    while True:
        candidate = f"{base} ({counter}){ext}"
        if candidate not in existing_names:
            return candidate
        counter += 1


async def move_from_inbox(
    hoofdpad: str,
    inbox_filename: str,
    new_filename: str,
) -> dict:
    """Verplaats een bestand van _inbox naar de hoofdmap met nieuwe naam."""
    inbox_pad = f"{hoofdpad}/_inbox"

    # Zorg dat bestandsnaam uniek is (nooit overschrijven)
    new_filename = await _unique_filename(hoofdpad, new_filename)

    content = await sp_client.download_file(f"{inbox_pad}/{inbox_filename}")

    ext = new_filename.rsplit(".", 1)[-1].lower() if "." in new_filename else "pdf"
    mime_map = {
        "pdf": "application/pdf",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "tiff": "image/tiff",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    mime_type = mime_map.get(ext, "application/octet-stream")

    result = await sp_client.upload_file(hoofdpad, new_filename, content, mime_type)

    try:
        inbox_items = await sp_client.list_folder(inbox_pad)
        for item in inbox_items:
            if item.get("name") == inbox_filename:
                await sp_client.delete_item(item["id"])
                break
    except Exception as e:
        logger.warning("Kon origineel niet verwijderen uit _inbox: %s", e)

    new_pad = f"{hoofdpad}/{new_filename}"
    logger.info("Verplaatst: %s/_inbox/%s → %s", hoofdpad, inbox_filename, new_pad)

    return {
        "sharepoint_pad": new_pad,
        "web_url": result.get("webUrl", ""),
        "filename": new_filename,
    }


async def archive_existing(
    hoofdpad: str,
    filename: str,
) -> None:
    """Verplaats een bestaand bestand naar _archief (bij vernieuwing)."""
    try:
        content = await sp_client.download_file(f"{hoofdpad}/{filename}")
        archief_pad = f"{hoofdpad}/_archief"
        await sp_client.upload_file(archief_pad, filename, content)

        items = await sp_client.list_folder(hoofdpad)
        for item in items:
            if item.get("name") == filename and "folder" not in item:
                await sp_client.delete_item(item["id"])
                break

        logger.info("Gearchiveerd: %s → %s/_archief/", filename, hoofdpad)
    except Exception as e:
        logger.warning("Archivering mislukt voor %s: %s", filename, e)
