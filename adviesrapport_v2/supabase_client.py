"""Supabase REST API client — read-only, voor dossier/aanvraag data.

Gebruikt httpx (al een dependency) ipv supabase-py om dependencies minimaal te houden.

Auth strategie:
  - SUPABASE_URL: project URL (verplicht)
  - SUPABASE_ANON_KEY: public anon key voor `apikey` header (verplicht)
  - access_token: session JWT van de ingelogde Lovable-gebruiker (per request)

  Lovable stuurt de Supabase session token mee in de Authorization header.
  De backend forwardt die naar Supabase, zodat RLS gewoon werkt.
  Geen service_role key nodig (die is niet beschikbaar bij Lovable-managed projecten).
"""

import os
import logging

import httpx

logger = logging.getLogger("nat-api.adviesrapport_v2")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
# Backward compatibility: als SUPABASE_SERVICE_KEY gezet is, gebruik die als fallback
_FALLBACK_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")


def _get_api_key() -> str:
    """Return de API key voor de `apikey` header."""
    return SUPABASE_ANON_KEY or _FALLBACK_KEY


def _headers(access_token: str | None = None) -> dict[str, str]:
    """Bouw Supabase request headers.

    Args:
        access_token: Supabase session JWT van de ingelogde gebruiker.
                      Als None, fallback naar service_role key, dan anon key.
    """
    api_key = _get_api_key()
    auth_token = access_token or _FALLBACK_KEY or api_key

    if not auth_token:
        raise ValueError("Geen Supabase auth token beschikbaar (geen session, service key, of anon key)")

    return {
        "apikey": api_key,
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }


async def lees_dossier(dossier_id: str, access_token: str | None = None) -> dict:
    """Lees een dossier uit Supabase (tabel: dossiers).

    Args:
        dossier_id: UUID van het dossier
        access_token: Supabase session JWT (optioneel, voor RLS)

    Returns:
        dict met dossier data inclusief `invoer` JSONB kolom.

    Raises:
        ValueError: Als het dossier niet gevonden wordt.
        httpx.HTTPStatusError: Bij Supabase API fouten.
    """
    url = f"{SUPABASE_URL}/rest/v1/dossiers"
    params = {
        "select": "*",
        "id": f"eq.{dossier_id}",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=_headers(access_token), params=params)
        resp.raise_for_status()

    rows = resp.json()
    if not rows:
        raise ValueError(f"Dossier niet gevonden: {dossier_id}")

    logger.info("Dossier geladen: %s", dossier_id)
    return rows[0]


async def lees_aanvraag(aanvraag_id: str, access_token: str | None = None) -> dict:
    """Lees een aanvraag uit Supabase (tabel: aanvragen).

    Args:
        aanvraag_id: UUID van de aanvraag
        access_token: Supabase session JWT (optioneel, voor RLS)

    Returns:
        dict met aanvraag data.

    Raises:
        ValueError: Als de aanvraag niet gevonden wordt.
        httpx.HTTPStatusError: Bij Supabase API fouten.
    """
    url = f"{SUPABASE_URL}/rest/v1/aanvragen"
    params = {
        "select": "*",
        "id": f"eq.{aanvraag_id}",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=_headers(access_token), params=params)
        resp.raise_for_status()

    rows = resp.json()
    if not rows:
        raise ValueError(f"Aanvraag niet gevonden: {aanvraag_id}")

    logger.info("Aanvraag geladen: %s", aanvraag_id)
    return rows[0]


async def lees_berekeningen(dossier_id: str, access_token: str | None = None) -> list[dict]:
    """Lees alle berekeningen van een dossier (tabel: berekeningen).

    Returns:
        Lijst van berekening-dicts, gesorteerd op aanmaak_datum.
    """
    url = f"{SUPABASE_URL}/rest/v1/berekeningen"
    params = {
        "select": "*",
        "dossier_id": f"eq.{dossier_id}",
        "order": "aanmaak_datum.asc",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=_headers(access_token), params=params)
        resp.raise_for_status()

    rows = resp.json()
    logger.info("Berekeningen geladen voor dossier %s: %d stuks", dossier_id, len(rows))
    return rows


async def lees_berekening(berekening_id: str, access_token: str | None = None) -> dict:
    """Lees een enkele berekening (tabel: berekeningen).

    Raises:
        ValueError: Als de berekening niet gevonden wordt.
    """
    url = f"{SUPABASE_URL}/rest/v1/berekeningen"
    params = {
        "select": "*",
        "id": f"eq.{berekening_id}",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=_headers(access_token), params=params)
        resp.raise_for_status()

    rows = resp.json()
    if not rows:
        raise ValueError(f"Berekening niet gevonden: {berekening_id}")

    logger.info("Berekening geladen: %s", berekening_id)
    return rows[0]
