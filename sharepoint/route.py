"""SharePoint API endpoints — klantmappen aanmaken en beheren."""

import logging

from fastapi import APIRouter, HTTPException, Request

from adviesrapport_v2.supabase_client import _headers as supabase_headers, SUPABASE_URL
from graph_auth import GraphAPIError
from sharepoint import client as sp_client
from sharepoint.schemas import (
    FolderItem,
    KlantmapInhoudResponse,
    KlantmapRequest,
    KlantmapResponse,
)

import httpx

logger = logging.getLogger("nat-api.sharepoint")

router = APIRouter(prefix="/sharepoint", tags=["sharepoint"])


def _extract_access_token(request: Request) -> str | None:
    """Haal Supabase session token uit Authorization header."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


@router.post("/klantmap", response_model=KlantmapResponse)
async def maak_klantmap(body: KlantmapRequest, request: Request):
    """Maak een klantmap aan op SharePoint voor een dossier.

    Haalt dossiernummer en klantnaam op uit Supabase,
    maakt de mapstructuur aan op SharePoint,
    en slaat de SharePoint URL op in het dossier.
    """
    if not sp_client.is_configured():
        raise HTTPException(503, "SharePoint niet geconfigureerd (Azure credentials of SHAREPOINT_DRIVE_ID ontbreekt)")

    access_token = _extract_access_token(request)

    # 1. Dossier ophalen uit Supabase
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/dossiers",
                headers=supabase_headers(access_token),
                params={"select": "id,dossiernummer,klant_naam,klant_contact_gegevens,sharepoint_url", "id": f"eq.{body.dossier_id}"},
            )
            resp.raise_for_status()
            rows = resp.json()
    except Exception as e:
        logger.error("Dossier ophalen mislukt: %s", e)
        raise HTTPException(500, f"Dossier ophalen mislukt: {e}")

    if not rows:
        raise HTTPException(404, f"Dossier niet gevonden: {body.dossier_id}")

    dossier = rows[0]

    # Check of klantmap al bestaat
    if dossier.get("sharepoint_url"):
        raise HTTPException(409, "Klantmap bestaat al voor dit dossier")

    dossiernummer = dossier.get("dossiernummer")
    if not dossiernummer:
        raise HTTPException(400, "Dossier heeft geen dossiernummer — maak eerst een dossiernummer aan")

    # Klantnaam splitsen in achternaam + voornaam
    klant_naam = dossier.get("klant_naam", "Onbekend")
    contact = dossier.get("klant_contact_gegevens") or {}
    aanvrager = contact.get("aanvrager", {})
    voornaam = aanvrager.get("voornaam", "")
    achternaam = aanvrager.get("achternaam", klant_naam)

    # Fallback: als geen contact gegevens, probeer klantnaam te splitsen
    if not voornaam and " " in klant_naam:
        parts = klant_naam.split(" ", 1)
        voornaam = parts[0]
        achternaam = parts[1] if len(parts) > 1 else klant_naam

    # 2. Klantmap aanmaken op SharePoint
    try:
        result = await sp_client.create_klantmap(dossiernummer, achternaam, voornaam)
    except GraphAPIError as e:
        logger.error("Klantmap aanmaken mislukt: %s", e.message)
        raise HTTPException(e.status_code, f"SharePoint fout: {e.message}")

    # 3. SharePoint URL opslaan in dossier
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.patch(
                f"{SUPABASE_URL}/rest/v1/dossiers",
                headers=supabase_headers(access_token),
                params={"id": f"eq.{body.dossier_id}"},
                json={"sharepoint_url": result["sharepoint_url"]},
            )
            resp.raise_for_status()
    except Exception as e:
        logger.warning("SharePoint URL opslaan in dossier mislukt: %s (map is wel aangemaakt)", e)

    return KlantmapResponse(
        dossiernummer=dossiernummer,
        mapnaam=result["mapnaam"],
        sharepoint_url=result["sharepoint_url"],
        mappen_aangemaakt=result["mappen_aangemaakt"],
    )


@router.get("/klantmap/{dossier_id}", response_model=KlantmapInhoudResponse)
async def lees_klantmap(dossier_id: str, request: Request):
    """Haal de inhoud van een klantmap op."""
    if not sp_client.is_configured():
        raise HTTPException(503, "SharePoint niet geconfigureerd")

    access_token = _extract_access_token(request)

    # Dossier ophalen voor SharePoint pad
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/dossiers",
                headers=supabase_headers(access_token),
                params={"select": "dossiernummer,klant_naam,klant_contact_gegevens,sharepoint_url", "id": f"eq.{dossier_id}"},
            )
            resp.raise_for_status()
            rows = resp.json()
    except Exception as e:
        raise HTTPException(500, f"Dossier ophalen mislukt: {e}")

    if not rows:
        raise HTTPException(404, f"Dossier niet gevonden: {dossier_id}")

    dossier = rows[0]
    dossiernummer = dossier.get("dossiernummer")

    if not dossiernummer:
        raise HTTPException(400, "Dossier heeft geen dossiernummer")

    # Mapnaam reconstrueren
    klant_naam = dossier.get("klant_naam", "Onbekend")
    contact = dossier.get("klant_contact_gegevens") or {}
    aanvrager = contact.get("aanvrager", {})
    voornaam = aanvrager.get("voornaam", "")
    achternaam = aanvrager.get("achternaam", klant_naam)
    if not voornaam and " " in klant_naam:
        parts = klant_naam.split(" ", 1)
        voornaam = parts[0]
        achternaam = parts[1] if len(parts) > 1 else klant_naam

    mapnaam = f"{dossiernummer} {achternaam}, {voornaam}"
    hoofdpad = f"{sp_client.SHAREPOINT_KLANTEN_ROOT}/{mapnaam}"

    try:
        items_raw = await sp_client.list_folder(hoofdpad)
    except GraphAPIError as e:
        if e.status_code == 404:
            raise HTTPException(404, "Klantmap niet gevonden op SharePoint")
        raise HTTPException(e.status_code, f"SharePoint fout: {e.message}")

    items = [
        FolderItem(
            name=item["name"],
            id=item["id"],
            type="folder" if "folder" in item else "file",
            size=item.get("size"),
            web_url=item.get("webUrl"),
        )
        for item in items_raw
    ]

    return KlantmapInhoudResponse(
        sharepoint_url=dossier.get("sharepoint_url"),
        items=items,
    )
