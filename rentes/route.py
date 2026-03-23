"""Hypotheekrentes endpoints — lookup + CRUD via Supabase.

Endpoints:
  GET  /rentes/lookup       — Zoek rente op basis van geldverstrekker, product, aflosvorm, etc.
  GET  /rentes/tarieven     — Alle tarieven voor een geldverstrekker+productlijn (voor matrix-editor)
  GET  /rentes/kortingen    — Alle kortingen voor een geldverstrekker+productlijn
  POST /rentes/tarieven     — Tarieven opslaan (bulk upsert, voor admin matrix-editor)
  POST /rentes/kortingen    — Kortingen opslaan (bulk upsert)
"""

import os
import logging
from typing import Optional
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, Request, Depends, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

import httpx

logger = logging.getLogger("nat-api.rentes")

router = APIRouter(prefix="/rentes", tags=["rentes"])

# --- Supabase config (hergebruikt zelfde env vars als adviesrapport_v2) ---
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
_FALLBACK_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")


def _get_api_key() -> str:
    return SUPABASE_ANON_KEY or _FALLBACK_KEY


def _headers(access_token: str | None = None) -> dict[str, str]:
    api_key = _get_api_key()
    auth_token = access_token or _FALLBACK_KEY or api_key
    if not auth_token:
        raise ValueError("Geen Supabase auth token beschikbaar")
    return {
        "apikey": api_key,
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _extract_access_token(request: Request) -> str | None:
    """Haal Supabase session token uit Authorization header."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


# ──────────────────────────────────────────────
# GET /rentes/lookup — auto-fill voor formulier
# ──────────────────────────────────────────────

@router.get("/lookup")
async def rente_lookup(
    request: Request,
    geldverstrekker: str = Query(..., description="Naam geldverstrekker"),
    productlijn: str = Query(..., description="Productlijn"),
    aflosvorm: str = Query(..., description="annuitair, lineair of aflossingsvrij"),
    rentevaste_periode: int = Query(..., description="Jaren (0 = variabel)"),
    ltv: Optional[float] = Query(None, description="LTV percentage, bijv. 80"),
    energielabel: Optional[str] = Query(None, description="Energielabel, bijv. A, B, C"),
):
    """Zoek de actuele rente op voor een specifieke combinatie.

    Retourneert het basistarief uit de LTV-staffel + eventuele kortingen (energielabel etc.).
    Als geen ltv opgegeven: retourneert de hele LTV-staffel.
    """
    access_token = _extract_access_token(request)

    # 1. Haal het meest recente tarief op
    url = f"{SUPABASE_URL}/rest/v1/hypotheekrentes"
    params = {
        "select": "ltv_staffel,peildatum",
        "geldverstrekker": f"eq.{geldverstrekker}",
        "productlijn": f"eq.{productlijn}",
        "aflosvorm": f"eq.{aflosvorm}",
        "rentevaste_periode": f"eq.{rentevaste_periode}",
        "order": "peildatum.desc",
        "limit": "1",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=_headers(access_token), params=params)
        resp.raise_for_status()

    rows = resp.json()
    if not rows:
        raise HTTPException(status_code=404, detail="Geen tarief gevonden voor deze combinatie")

    tarief = rows[0]
    ltv_staffel = tarief["ltv_staffel"]
    peildatum = tarief["peildatum"]

    # 2. Bepaal basistarief uit LTV-staffel
    basis_rente = None
    if ltv is not None:
        basis_rente = _zoek_ltv_tarief(ltv_staffel, ltv)

    # 3. Haal kortingen op
    kortingen_url = f"{SUPABASE_URL}/rest/v1/rente_kortingen"
    kortingen_params = {
        "select": "korting_type,staffel,omschrijving",
        "geldverstrekker": f"eq.{geldverstrekker}",
        "productlijn": f"eq.{productlijn}",
        "order": "peildatum.desc",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            kortingen_url, headers=_headers(access_token), params=kortingen_params
        )
        resp.raise_for_status()

    # Neem per korting_type alleen de meest recente
    kortingen_raw = resp.json()
    kortingen = {}
    for k in kortingen_raw:
        if k["korting_type"] not in kortingen:
            kortingen[k["korting_type"]] = {
                "staffel": k["staffel"],
                "omschrijving": k.get("omschrijving"),
            }

    # 4. Bereken totale korting als energielabel opgegeven
    totale_korting = 0.0
    korting_details = []
    if energielabel and "energielabel" in kortingen:
        el_staffel = kortingen["energielabel"]["staffel"]
        el_korting = el_staffel.get(energielabel, 0)
        totale_korting += el_korting
        korting_details.append({
            "type": "energielabel",
            "label": energielabel,
            "korting": el_korting,
        })

    result = {
        "geldverstrekker": geldverstrekker,
        "productlijn": productlijn,
        "aflosvorm": aflosvorm,
        "rentevaste_periode": rentevaste_periode,
        "peildatum": peildatum,
        "ltv_staffel": ltv_staffel,
        "kortingen": kortingen,
    }

    if basis_rente is not None:
        result["basis_rente"] = basis_rente
        result["totale_korting"] = totale_korting
        result["netto_rente"] = round(basis_rente + totale_korting, 3)
        result["korting_details"] = korting_details

    return result


def _zoek_ltv_tarief(staffel: dict, ltv: float) -> float | None:
    """Zoek het juiste tarief in een LTV-staffel.

    De staffel heeft keys als "NHG", "55", "65", "80", "106plus".
    We zoeken de kleinste drempel die >= ltv is.
    """
    if not staffel:
        return None

    # NHG apart behandelen
    if ltv <= 0:
        return staffel.get("NHG")

    # Sorteer numerieke drempels
    numerieke = {}
    overig = {}
    for key, val in staffel.items():
        if key == "NHG":
            continue
        try:
            numerieke[int(key)] = val
        except ValueError:
            overig[key] = val  # bijv. "106plus"

    if not numerieke:
        return None

    # Zoek de kleinste drempel >= ltv
    for drempel in sorted(numerieke.keys()):
        if ltv <= drempel:
            return numerieke[drempel]

    # LTV hoger dan alle drempels → check "106plus" of hoogste
    if overig:
        return next(iter(overig.values()))
    return numerieke[max(numerieke.keys())]


# ──────────────────────────────────────────────
# GET /rentes/tarieven — voor matrix-editor
# ──────────────────────────────────────────────

@router.get("/tarieven")
async def rente_tarieven(
    request: Request,
    geldverstrekker: str = Query(...),
    productlijn: str = Query(...),
    aflosvorm: Optional[str] = Query(None, description="Filter op aflosvorm"),
):
    """Alle tarieven voor een geldverstrekker+productlijn (meest recente peildatum).

    Retourneert een lijst rijen, gesorteerd op rentevaste_periode.
    Gebruikt door de admin matrix-editor.
    """
    access_token = _extract_access_token(request)

    url = f"{SUPABASE_URL}/rest/v1/hypotheekrentes"
    params = {
        "select": "id,aflosvorm,rentevaste_periode,ltv_staffel,peildatum,bron",
        "geldverstrekker": f"eq.{geldverstrekker}",
        "productlijn": f"eq.{productlijn}",
        "order": "aflosvorm,rentevaste_periode",
    }
    if aflosvorm:
        params["aflosvorm"] = f"eq.{aflosvorm}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=_headers(access_token), params=params)
        resp.raise_for_status()

    rows = resp.json()

    # Groepeer per aflosvorm, neem per rentevaste_periode alleen meest recente peildatum
    result = {}
    for row in rows:
        av = row["aflosvorm"]
        rvp = row["rentevaste_periode"]
        if av not in result:
            result[av] = {}
        # Eerste entry per rvp is meest recente (door order)
        if rvp not in result[av]:
            result[av][rvp] = row

    # Flatten naar lijst per aflosvorm
    return {
        "geldverstrekker": geldverstrekker,
        "productlijn": productlijn,
        "aflosvormen": {
            av: sorted(tarieven.values(), key=lambda r: r["rentevaste_periode"])
            for av, tarieven in result.items()
        },
    }


# ──────────────────────────────────────────────
# GET /rentes/kortingen — voor admin
# ──────────────────────────────────────────────

@router.get("/kortingen")
async def rente_kortingen(
    request: Request,
    geldverstrekker: str = Query(...),
    productlijn: str = Query(...),
):
    """Alle kortingen voor een geldverstrekker+productlijn."""
    access_token = _extract_access_token(request)

    url = f"{SUPABASE_URL}/rest/v1/rente_kortingen"
    params = {
        "select": "id,korting_type,staffel,omschrijving,peildatum",
        "geldverstrekker": f"eq.{geldverstrekker}",
        "productlijn": f"eq.{productlijn}",
        "order": "korting_type,peildatum.desc",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=_headers(access_token), params=params)
        resp.raise_for_status()

    # Per korting_type alleen meest recente
    rows = resp.json()
    result = {}
    for row in rows:
        kt = row["korting_type"]
        if kt not in result:
            result[kt] = row

    return {
        "geldverstrekker": geldverstrekker,
        "productlijn": productlijn,
        "kortingen": list(result.values()),
    }


# ──────────────────────────────────────────────
# POST /rentes/tarieven — bulk upsert
# ──────────────────────────────────────────────

class TariefRij(BaseModel):
    aflosvorm: str = Field(..., pattern="^(annuitair|lineair|aflossingsvrij)$")
    rentevaste_periode: int = Field(..., ge=0, le=30)
    ltv_staffel: dict

class TarievenRequest(BaseModel):
    geldverstrekker: str
    productlijn: str
    peildatum: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    tarieven: list[TariefRij]


@router.post("/tarieven")
async def rente_tarieven_opslaan(
    body: TarievenRequest,
    request: Request,
):
    """Sla tarieven op (bulk upsert). Gebruikt door admin matrix-editor.

    Upsert op basis van (geldverstrekker, productlijn, aflosvorm, rentevaste_periode, peildatum).
    """
    access_token = _extract_access_token(request)

    url = f"{SUPABASE_URL}/rest/v1/hypotheekrentes"
    headers = _headers(access_token)
    headers["Prefer"] = "resolution=merge-duplicates,return=representation"

    rows = [
        {
            "geldverstrekker": body.geldverstrekker,
            "productlijn": body.productlijn,
            "aflosvorm": t.aflosvorm,
            "rentevaste_periode": t.rentevaste_periode,
            "ltv_staffel": t.ltv_staffel,
            "peildatum": body.peildatum,
            "bron": "handmatig",
        }
        for t in body.tarieven
    ]

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, headers=headers, json=rows)
        resp.raise_for_status()

    logger.info(
        "Tarieven opgeslagen: %s / %s — %d rijen",
        body.geldverstrekker, body.productlijn, len(rows),
    )
    return {"status": "ok", "rijen": len(rows)}


# ──────────────────────────────────────────────
# POST /rentes/kortingen — bulk upsert
# ──────────────────────────────────────────────

class KortingRij(BaseModel):
    korting_type: str
    staffel: dict
    omschrijving: Optional[str] = None

class KortingenRequest(BaseModel):
    geldverstrekker: str
    productlijn: str
    peildatum: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    kortingen: list[KortingRij]


@router.post("/kortingen")
async def rente_kortingen_opslaan(
    body: KortingenRequest,
    request: Request,
):
    """Sla kortingen op (bulk upsert). Gebruikt door admin."""
    access_token = _extract_access_token(request)

    url = f"{SUPABASE_URL}/rest/v1/rente_kortingen"
    headers = _headers(access_token)
    headers["Prefer"] = "resolution=merge-duplicates,return=representation"

    rows = [
        {
            "geldverstrekker": body.geldverstrekker,
            "productlijn": body.productlijn,
            "korting_type": k.korting_type,
            "staffel": k.staffel,
            "omschrijving": k.omschrijving,
            "peildatum": body.peildatum,
        }
        for k in body.kortingen
    ]

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, headers=headers, json=rows)
        resp.raise_for_status()

    logger.info(
        "Kortingen opgeslagen: %s / %s — %d rijen",
        body.geldverstrekker, body.productlijn, len(rows),
    )
    return {"status": "ok", "rijen": len(rows)}
