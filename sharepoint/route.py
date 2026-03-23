"""SharePoint API endpoints — klantmappen aanmaken en beheren."""

import os
import logging
import re

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

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

router = APIRouter(prefix="/sharepoint", tags=["sharepoint"])
webhook_router = APIRouter(tags=["webhooks"])


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


# =============================================================================
# Webhook: automatisch klantmap aanmaken bij nieuw dossier
# =============================================================================

def _extract_naam_delen(dossier: dict) -> tuple[str, str]:
    """Haal achternaam en voornaam uit een dossier record."""
    klant_naam = dossier.get("klant_naam", "Onbekend")
    contact = dossier.get("klant_contact_gegevens") or {}
    aanvrager = contact.get("aanvrager", {})
    voornaam = aanvrager.get("voornaam", "")
    achternaam = aanvrager.get("achternaam", klant_naam)

    if not voornaam and " " in klant_naam:
        parts = klant_naam.split(" ", 1)
        voornaam = parts[0]
        achternaam = parts[1] if len(parts) > 1 else klant_naam

    return achternaam, voornaam


@webhook_router.post("/webhooks/dossier-created")
async def webhook_dossier_created(request: Request):
    """Supabase Database Webhook — maakt automatisch een klantmap aan bij nieuw dossier.

    Supabase stuurt een POST met het nieuwe record in de body.
    Beveiligd met X-Webhook-Secret header.
    """
    # Auth check
    secret = request.headers.get("X-Webhook-Secret", "")
    if not WEBHOOK_SECRET or secret != WEBHOOK_SECRET:
        raise HTTPException(401, "Ongeldig webhook secret")

    if not sp_client.is_configured():
        logger.warning("Webhook ontvangen maar SharePoint niet geconfigureerd — skip")
        return {"status": "skipped", "reason": "sharepoint_not_configured"}

    # Parse Supabase webhook payload
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Ongeldige JSON payload")

    # Supabase webhook format: { "type": "INSERT", "table": "dossiers", "record": {...} }
    record = payload.get("record", {})
    dossier_id = record.get("id")
    dossiernummer = record.get("dossiernummer")
    klant_naam = record.get("klant_naam")

    if not dossier_id:
        logger.warning("Webhook: geen dossier_id in payload")
        return {"status": "skipped", "reason": "no_dossier_id"}

    if not dossiernummer or not klant_naam:
        logger.info("Webhook: dossier %s heeft nog geen dossiernummer of klantnaam — skip", dossier_id)
        return {"status": "skipped", "reason": "incomplete_data"}

    # Check of klantmap al bestaat
    if record.get("sharepoint_url"):
        return {"status": "skipped", "reason": "already_has_sharepoint_url"}

    # Naam splitsen
    achternaam, voornaam = _extract_naam_delen(record)

    # Klantmap aanmaken
    try:
        result = await sp_client.create_klantmap(dossiernummer, achternaam, voornaam)
    except GraphAPIError as e:
        logger.error("Webhook: klantmap aanmaken mislukt voor %s: %s", dossier_id, e.message)
        return {"status": "error", "reason": str(e.message)}

    # SharePoint URL opslaan (met service key, geen user session)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.patch(
                f"{SUPABASE_URL}/rest/v1/dossiers",
                headers=supabase_headers(None),  # Gebruikt service key
                params={"id": f"eq.{dossier_id}"},
                json={"sharepoint_url": result["sharepoint_url"]},
            )
            resp.raise_for_status()
    except Exception as e:
        logger.warning("Webhook: sharepoint_url opslaan mislukt: %s", e)

    logger.info("Webhook: klantmap aangemaakt voor dossier %s (%s)", dossier_id, result["mapnaam"])
    return {"status": "ok", "mapnaam": result["mapnaam"], "sharepoint_url": result["sharepoint_url"]}


# =============================================================================
# Admin: bestaande dossiers koppelen aan SharePoint mappen
# =============================================================================

def _normalize_naam(naam: str) -> str:
    """Normaliseer een naam voor matching (lowercase, geen spaties/leestekens)."""
    return re.sub(r'[^a-z0-9]', '', naam.lower())


def _match_mapnaam_aan_dossier(mapnaam: str, dossiers: list[dict]) -> dict | None:
    """Probeer een SharePoint mapnaam te matchen aan een dossier.

    Mapnaam formaat: "2026-0023 Mulder, Kirsten - Hakkers, Glenn"
    Dossier klant_naam: "Glenn Hakkers en Kirsten Mulder"
    """
    # Haal namen uit mapnaam (alles na het dossiernummer)
    match = re.match(r'\d{4}-\d{4}\s+(.*)', mapnaam)
    if not match:
        return None
    map_namen = _normalize_naam(match.group(1))

    best_match = None
    best_score = 0

    for dossier in dossiers:
        klant_naam = dossier.get("klant_naam", "")
        dossier_namen = _normalize_naam(klant_naam)

        # Check of alle woorden uit de dossier-naam in de mapnaam voorkomen (of vice versa)
        woorden_dossier = set(re.findall(r'[a-z]+', dossier_namen))
        woorden_map = set(re.findall(r'[a-z]+', map_namen))

        # Verwijder stopwoorden
        stopwoorden = {'en', 'van', 'de', 'het', 'der'}
        woorden_dossier -= stopwoorden
        woorden_map -= stopwoorden

        if not woorden_dossier or not woorden_map:
            continue

        # Score: overlap / max(len)
        overlap = len(woorden_dossier & woorden_map)
        score = overlap / max(len(woorden_dossier), len(woorden_map))

        if score > best_score and score >= 0.5:
            best_score = score
            best_match = dossier

    return best_match


@router.post("/koppel-bestaande")
async def koppel_bestaande_mappen(request: Request):
    """Koppel bestaande SharePoint klantmappen aan Supabase dossiers.

    Eenmalig admin-endpoint. Matcht op klantnaam (fuzzy).
    Vereist API key via X-API-Key header.
    """
    # Auth: check API key
    api_key = os.environ.get("NAT_API_KEY")
    provided_key = request.headers.get("X-API-Key", "")
    if api_key and provided_key != api_key:
        raise HTTPException(401, "Ongeldige API key")

    if not sp_client.is_configured():
        raise HTTPException(503, "SharePoint niet geconfigureerd")

    # 1. Alle dossiers zonder sharepoint_url ophalen
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/dossiers",
                headers=supabase_headers(None),
                params={
                    "select": "id,dossiernummer,klant_naam,klant_contact_gegevens,sharepoint_url",
                    "sharepoint_url": "is.null",
                },
            )
            resp.raise_for_status()
            dossiers = resp.json()
    except Exception as e:
        raise HTTPException(500, f"Dossiers ophalen mislukt: {e}")

    if not dossiers:
        return {"gekoppeld": 0, "niet_gekoppeld": 0, "details": [], "message": "Alle dossiers zijn al gekoppeld"}

    # 2. Alle klantmappen ophalen van SharePoint
    try:
        mappen = await sp_client.list_folder(sp_client.SHAREPOINT_KLANTEN_ROOT)
    except GraphAPIError as e:
        raise HTTPException(500, f"SharePoint mappen ophalen mislukt: {e.message}")

    # Filter alleen mappen (geen bestanden)
    klantmappen = [m for m in mappen if "folder" in m]

    # 3. Matchen
    gekoppeld = []
    niet_gekoppeld = []

    for map_item in klantmappen:
        mapnaam = map_item["name"]
        web_url = map_item.get("webUrl", "")

        matched_dossier = _match_mapnaam_aan_dossier(mapnaam, dossiers)

        if matched_dossier:
            dossier_id = matched_dossier["id"]

            # Dossiernummer uit mapnaam halen
            nr_match = re.match(r'(\d{4}-\d{4})', mapnaam)
            dossiernummer = nr_match.group(1) if nr_match else None

            # Update dossier
            update_data = {"sharepoint_url": web_url}
            if dossiernummer and not matched_dossier.get("dossiernummer"):
                update_data["dossiernummer"] = dossiernummer

            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.patch(
                        f"{SUPABASE_URL}/rest/v1/dossiers",
                        headers=supabase_headers(None),
                        params={"id": f"eq.{dossier_id}"},
                        json=update_data,
                    )
                    resp.raise_for_status()
            except Exception as e:
                logger.warning("Koppelen mislukt voor %s: %s", dossier_id, e)
                continue

            gekoppeld.append({
                "dossier_id": dossier_id,
                "klant_naam": matched_dossier.get("klant_naam"),
                "mapnaam": mapnaam,
                "sharepoint_url": web_url,
            })

            # Verwijder uit beschikbare dossiers (voorkom dubbele match)
            dossiers = [d for d in dossiers if d["id"] != dossier_id]
        else:
            niet_gekoppeld.append({"mapnaam": mapnaam, "sharepoint_url": web_url})

    logger.info("Koppeling: %d gekoppeld, %d niet gekoppeld", len(gekoppeld), len(niet_gekoppeld))

    return {
        "gekoppeld": len(gekoppeld),
        "niet_gekoppeld": len(niet_gekoppeld),
        "details_gekoppeld": gekoppeld,
        "details_niet_gekoppeld": niet_gekoppeld,
    }
