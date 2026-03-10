"""Supabase REST API client — read-only, voor dossier/aanvraag data.

Gebruikt httpx (al een dependency) ipv supabase-py om dependencies minimaal te houden.
"""

import os
import logging

import httpx

logger = logging.getLogger("nat-api.adviesrapport_v2")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")


def _headers() -> dict[str, str]:
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }


async def lees_dossier(dossier_id: str) -> dict:
    """Lees een dossier uit Supabase (tabel: dossiers).

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
        resp = await client.get(url, headers=_headers(), params=params)
        resp.raise_for_status()

    rows = resp.json()
    if not rows:
        raise ValueError(f"Dossier niet gevonden: {dossier_id}")

    logger.info("Dossier geladen: %s", dossier_id)
    return rows[0]


async def lees_aanvraag(aanvraag_id: str) -> dict:
    """Lees een aanvraag uit Supabase (tabel: aanvragen).

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
        resp = await client.get(url, headers=_headers(), params=params)
        resp.raise_for_status()

    rows = resp.json()
    if not rows:
        raise ValueError(f"Aanvraag niet gevonden: {aanvraag_id}")

    logger.info("Aanvraag geladen: %s", aanvraag_id)
    return rows[0]
