"""SharePoint API endpoints — klantmappen aanmaken en beheren."""

import os
import logging
import re

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

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

    # Mapnaam opbouwen uit contactgegevens
    naam_deel = _build_mapnaam(dossier)

    # 2. Klantmap aanmaken op SharePoint
    try:
        result = await sp_client.create_klantmap(dossiernummer, naam_deel)
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
    naam_deel = _build_mapnaam(dossier)
    import re
    clean_naam = re.sub(r'["*:<>?/\\|]', '', naam_deel).rstrip('. ')
    mapnaam = f"{dossiernummer} {clean_naam}"
    hoofdpad = f"{sp_client.SHAREPOINT_KLANTEN_ROOT}/{mapnaam}"

    try:
        items_raw = await sp_client.list_folder(hoofdpad)
    except GraphAPIError as e:
        if e.status_code == 404:
            raise HTTPException(404, "Klantmap niet gevonden op SharePoint")
        raise HTTPException(e.status_code, f"SharePoint fout: {e.message}")

    items = []
    for item in items_raw:
        # Gewijzigd door: haal naam uit lastModifiedBy.user.displayName
        modified_by = ""
        lmb = item.get("lastModifiedBy", {})
        if isinstance(lmb, dict):
            user = lmb.get("user", {})
            if isinstance(user, dict):
                modified_by = user.get("displayName", "")

        items.append(FolderItem(
            name=item["name"],
            id=item["id"],
            type="folder" if "folder" in item else "file",
            size=item.get("size"),
            web_url=item.get("webUrl"),
            last_modified=item.get("lastModifiedDateTime"),
            last_modified_by=modified_by,
        ))

    return KlantmapInhoudResponse(
        sharepoint_url=dossier.get("sharepoint_url"),
        items=items,
    )


@router.post("/klantmap/{dossier_id}/upload")
async def upload_naar_klantmap(
    dossier_id: str,
    request: Request,
    file: UploadFile = File(...),
):
    """Upload een bestand naar de klantmap op SharePoint."""
    if not sp_client.is_configured():
        raise HTTPException(503, "SharePoint niet geconfigureerd")

    access_token = _extract_access_token(request)

    # Validatie: bestandsgrootte (max 25MB)
    content = await file.read()
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(400, "Bestand te groot (max 25 MB)")
    if len(content) < 1024:
        raise HTTPException(400, "Bestand te klein (min 1 KB)")

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

    naam_deel = _build_mapnaam(dossier)
    clean_naam = re.sub(r'["*:<>?/\\|]', '', naam_deel).rstrip('. ')
    hoofdpad = f"{sp_client.SHAREPOINT_KLANTEN_ROOT}/{dossiernummer} {clean_naam}"

    try:
        result = await sp_client.upload_file(
            hoofdpad,
            file.filename or "document",
            content,
            file.content_type or "application/octet-stream",
        )
    except GraphAPIError as e:
        raise HTTPException(e.status_code, f"Upload mislukt: {e.message}")

    return {
        "name": result.get("name"),
        "id": result.get("id"),
        "size": result.get("size"),
        "web_url": result.get("webUrl"),
    }


@router.delete("/klantmap/item/{item_id}")
async def verwijder_bestand(item_id: str, request: Request):
    """Verwijder een bestand uit een klantmap op SharePoint."""
    if not sp_client.is_configured():
        raise HTTPException(503, "SharePoint niet geconfigureerd")

    try:
        await sp_client.delete_item(item_id)
    except GraphAPIError as e:
        raise HTTPException(e.status_code, f"Verwijderen mislukt: {e.message}")

    return {"status": "ok", "deleted": item_id}


# =============================================================================
# Webhook: automatisch klantmap aanmaken bij nieuw dossier
# =============================================================================

def _format_persoon(persoon: dict) -> str:
    """Formatteer een persoon als 'Achternaam, Voornaam tussenvoegsel'.

    Voorbeeld: {"achternaam": "Marum", "voornaam": "Walter", "tussenvoegsel": "van"}
    → "Marum, Walter van"
    """
    achternaam = persoon.get("achternaam", "").strip()
    voornaam = persoon.get("voornaam", "").strip()
    tussenvoegsel = persoon.get("tussenvoegsel", "").strip()

    if not achternaam:
        return ""

    delen = [f"{achternaam}, {voornaam}" if voornaam else achternaam]
    if tussenvoegsel:
        delen.append(tussenvoegsel)

    return " ".join(delen)


def _build_mapnaam(dossier: dict) -> str:
    """Bouw de mapnaam voor SharePoint.

    Formaat: "{dossiernummer} {Achternaam, Voornaam tussenvoegsel}"
    Bij stel: "{dossiernummer} {Aanvrager} en {Partner}"

    Voorbeelden:
      "2026-0050 Marum, Walter van en Marum-Koning, Nynke van"
      "2026-0007 Alawi, Javad"
    """
    contact = dossier.get("klant_contact_gegevens") or {}
    aanvrager = contact.get("aanvrager", {})
    partner = contact.get("partner", {})

    aanvrager_str = _format_persoon(aanvrager)
    partner_str = _format_persoon(partner)

    # Fallback: als geen contact gegevens, gebruik klant_naam
    if not aanvrager_str:
        klant_naam = dossier.get("klant_naam", "Onbekend")
        return klant_naam

    if partner_str:
        return f"{aanvrager_str} en {partner_str}"

    return aanvrager_str


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

    # Mapnaam opbouwen
    naam_deel = _build_mapnaam(record)

    # Klantmap aanmaken
    try:
        result = await sp_client.create_klantmap(dossiernummer, naam_deel)
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
