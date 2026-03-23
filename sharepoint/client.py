"""SharePoint client — bestanden en mappen beheren via Microsoft Graph API.

Gebruikt dezelfde Azure app-registratie als graph_client.py (Mail).
Vereist extra permissions: Files.ReadWrite.All, Sites.ReadWrite.All.
"""

import os
import logging
from typing import Optional

import httpx

from graph_auth import GRAPH_BASE_URL, GraphAPIError, get_access_token

logger = logging.getLogger("nat-api.sharepoint")

# --- Configuratie uit environment ---
SHAREPOINT_DRIVE_ID = os.environ.get("SHAREPOINT_DRIVE_ID", "")
SHAREPOINT_KLANTEN_ROOT = os.environ.get("SHAREPOINT_KLANTEN_ROOT", "1.Klanten")

# Submappen per klantmap (matcht n8n SharePoint structuur)
KLANTMAP_SUBMAPPEN = [
    "Identificatie",
    "Inkomen",
    "Woning",
    "Financieel",
    "Overig",
    "Communicatie",
]


def is_configured() -> bool:
    """Check of SharePoint configuratie beschikbaar is."""
    from graph_auth import is_configured as auth_configured
    return auth_configured() and bool(SHAREPOINT_DRIVE_ID)


async def _graph_headers() -> dict[str, str]:
    """Bouw Graph API headers met Bearer token."""
    token = await get_access_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


async def create_folder(pad: str) -> dict:
    """Maak een map aan op SharePoint.

    Args:
        pad: Relatief pad binnen de drive (bijv. "1.Klanten/2026-0001 Jansen, Jan")

    Returns:
        dict met folder metadata (id, name, webUrl)

    Raises:
        GraphAPIError: bij API fout (behalve 409 Conflict = map bestaat al)
    """
    headers = await _graph_headers()

    # Split pad in parent en nieuwe mapnaam
    parts = pad.rsplit("/", 1)
    if len(parts) == 2:
        parent_path, folder_name = parts
        url = f"{GRAPH_BASE_URL}/drives/{SHAREPOINT_DRIVE_ID}/root:/{parent_path}:/children"
    else:
        folder_name = parts[0]
        url = f"{GRAPH_BASE_URL}/drives/{SHAREPOINT_DRIVE_ID}/root/children"

    payload = {
        "name": folder_name,
        "folder": {},
        "@microsoft.graph.conflictBehavior": "fail",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=headers, json=payload)

        if resp.status_code == 409:
            # Map bestaat al — ophalen in plaats van fout
            logger.info("Map bestaat al: %s", pad)
            return await get_folder(pad)

        if resp.status_code not in (200, 201):
            logger.error("Map aanmaken mislukt: %s %s", resp.status_code, resp.text[:300])
            raise GraphAPIError(
                f"Map aanmaken mislukt: {resp.status_code}",
                status_code=resp.status_code,
                detail=resp.text[:300],
            )

        result = resp.json()
        logger.info("Map aangemaakt: %s (id=%s)", pad, result.get("id", "")[:12])
        return result


async def get_folder(pad: str) -> dict:
    """Haal folder metadata op.

    Args:
        pad: Relatief pad binnen de drive

    Returns:
        dict met folder metadata
    """
    headers = await _graph_headers()
    url = f"{GRAPH_BASE_URL}/drives/{SHAREPOINT_DRIVE_ID}/root:/{pad}"

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers=headers)

        if resp.status_code == 404:
            raise GraphAPIError(f"Map niet gevonden: {pad}", status_code=404)

        if resp.status_code != 200:
            raise GraphAPIError(
                f"Map ophalen mislukt: {resp.status_code}",
                status_code=resp.status_code,
                detail=resp.text[:300],
            )

        return resp.json()


async def list_folder(pad: str) -> list[dict]:
    """Lijst de inhoud van een map.

    Args:
        pad: Relatief pad binnen de drive

    Returns:
        Lijst van items (bestanden en mappen) met name, id, size, webUrl, etc.
    """
    headers = await _graph_headers()
    url = f"{GRAPH_BASE_URL}/drives/{SHAREPOINT_DRIVE_ID}/root:/{pad}:/children"

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers=headers)

        if resp.status_code == 404:
            return []

        if resp.status_code != 200:
            raise GraphAPIError(
                f"Map inhoud ophalen mislukt: {resp.status_code}",
                status_code=resp.status_code,
                detail=resp.text[:300],
            )

        return resp.json().get("value", [])


async def upload_file(
    pad: str,
    filename: str,
    content: bytes,
    content_type: str = "application/octet-stream",
) -> dict:
    """Upload een bestand naar SharePoint.

    Args:
        pad: Map-pad waarin het bestand moet komen
        filename: Bestandsnaam
        content: Bestandsinhoud als bytes
        content_type: MIME type

    Returns:
        dict met bestand metadata (id, name, webUrl, size)
    """
    token = await get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": content_type,
    }

    url = (
        f"{GRAPH_BASE_URL}/drives/{SHAREPOINT_DRIVE_ID}"
        f"/root:/{pad}/{filename}:/content"
    )

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.put(url, headers=headers, content=content)

        if resp.status_code not in (200, 201):
            logger.error("Upload mislukt: %s %s", resp.status_code, resp.text[:300])
            raise GraphAPIError(
                f"Upload mislukt: {resp.status_code}",
                status_code=resp.status_code,
                detail=resp.text[:300],
            )

        result = resp.json()
        logger.info("Bestand geüpload: %s/%s (%d bytes)", pad, filename, len(content))
        return result


async def create_klantmap(dossiernummer: str, naam_deel: str) -> dict:
    """Maak een klantmap aan op SharePoint.

    Args:
        dossiernummer: bijv. "2026-0001"
        naam_deel: bijv. "Marum, Walter van en Marum-Koning, Nynke van"

    Returns:
        dict met "mapnaam", "sharepoint_url", "mappen_aangemaakt"
    """
    import re
    # Sanitize: SharePoint staat geen mapnamen toe die eindigen op punt/spatie
    # of die ongeldige tekens bevatten (" * : < > ? / \ |)
    clean_naam = re.sub(r'["*:<>?/\\|]', '', naam_deel).rstrip('. ')
    mapnaam = f"{dossiernummer} {clean_naam}"
    hoofdpad = f"{SHAREPOINT_KLANTEN_ROOT}/{mapnaam}"

    # Hoofdmap aanmaken (geen submappen — categorisering zit in de database)
    result = await create_folder(hoofdpad)
    sharepoint_url = result.get("webUrl", "")

    logger.info("Klantmap aangemaakt: %s", mapnaam)

    return {
        "mapnaam": mapnaam,
        "sharepoint_url": sharepoint_url,
        "hoofdpad": hoofdpad,
        "mappen_aangemaakt": [mapnaam],
    }
