"""Hernoem en verplaats documenten op SharePoint — van _inbox naar hoofdmap."""

import logging
import re

from sharepoint import client as sp_client

logger = logging.getLogger("nat-api.rename-move")


def build_filename(
    dossiernummer: str,
    document_type: str,
    achternaam: str,
    original_ext: str = ".pdf",
) -> str:
    """Bouw een gestandaardiseerde bestandsnaam.

    Format: {dossiernummer}_{documenttype}_{achternaam}.{ext}
    Voorbeeld: 2026-0023_werkgeversverklaring_Slinger.pdf

    Args:
        dossiernummer: bijv. "2026-0023"
        document_type: bijv. "werkgeversverklaring"
        achternaam: bijv. "Slinger"
        original_ext: bijv. ".pdf"

    Returns:
        Gestandaardiseerde bestandsnaam
    """
    # Sanitize alle delen
    clean_type = re.sub(r'[^a-z0-9_]', '_', document_type.lower())
    clean_naam = re.sub(r'[^a-zA-Z0-9]', '', achternaam)
    ext = original_ext.lower() if original_ext.startswith(".") else f".{original_ext.lower()}"

    return f"{dossiernummer}_{clean_type}_{clean_naam}{ext}"


async def move_from_inbox(
    hoofdpad: str,
    inbox_filename: str,
    new_filename: str,
) -> dict:
    """Verplaats een bestand van _inbox naar de hoofdmap met nieuwe naam.

    Stappen:
    1. Download van _inbox
    2. Upload naar hoofdmap met nieuwe naam
    3. Verwijder uit _inbox

    Args:
        hoofdpad: SharePoint pad van de klantmap (bijv. "1.Klanten/2026-0023 Slinger, Harry")
        inbox_filename: Huidige bestandsnaam in _inbox
        new_filename: Nieuwe bestandsnaam

    Returns:
        dict met nieuwe SharePoint pad en webUrl
    """
    inbox_pad = f"{hoofdpad}/_inbox"

    # Download content van _inbox
    content = await sp_client.download_file(f"{inbox_pad}/{inbox_filename}")

    # Bepaal MIME type op basis van extensie
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

    # Upload naar hoofdmap
    result = await sp_client.upload_file(hoofdpad, new_filename, content, mime_type)

    # Verwijder uit _inbox
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
    """Verplaats een bestaand bestand naar _archief (bij vernieuwing).

    Args:
        hoofdpad: SharePoint pad van de klantmap
        filename: Bestandsnaam om te archiveren
    """
    try:
        # Download
        content = await sp_client.download_file(f"{hoofdpad}/{filename}")

        # Upload naar _archief
        archief_pad = f"{hoofdpad}/_archief"
        await sp_client.upload_file(archief_pad, filename, content)

        # Verwijder uit hoofdmap
        items = await sp_client.list_folder(hoofdpad)
        for item in items:
            if item.get("name") == filename and "folder" not in item:
                await sp_client.delete_item(item["id"])
                break

        logger.info("Gearchiveerd: %s → %s/_archief/", filename, hoofdpad)
    except Exception as e:
        logger.warning("Archivering mislukt voor %s: %s", filename, e)
