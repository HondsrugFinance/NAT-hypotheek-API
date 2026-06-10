"""
KVK details-cache (Supabase)
============================
Slaat opgehaalde KVK-inschrijvingdetails op in Supabase (tabel: kvk_cache),
zodat een eerder (door wie dan ook) opgevraagde onderneming niet opnieuw
EUR 0,04 kost.

Sleutel: (kvk_nummer, vestigingsnummer). Bij ontbrekend vestigingsnummer
wordt een lege string opgeslagen, zodat de UNIQUE-constraint betrouwbaar werkt
(Postgres behandelt NULLs als onderling verschillend).

Schrijven gebeurt met de SERVICE_KEY (RLS-bypass) — de woningcheck stuurt geen
sessie-token mee. Als Supabase niet geconfigureerd is, is de cache een no-op:
de endpoint valt dan gewoon terug op een live KVK-call.

Env vars: SUPABASE_URL, SUPABASE_SERVICE_KEY (of SUPABASE_ANON_KEY als fallback).
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

logger = logging.getLogger("nat-api.kvk.cache")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

_TABEL = "kvk_cache"

# Cache-records ouder dan dit gelden als verlopen → verse KVK-ophaal (EUR 0,04).
# KVK-gegevens (rechtsvorm, werkzame personen, faillissement, handelsnamen) kunnen
# wijzigen; 6 maanden is een redelijke balans tussen kosten en actualiteit.
TTL_DAGEN = 180


def _verloop_grens_iso() -> str:
    """ISO-timestamp: records ouder dan dit zijn verlopen."""
    return (datetime.now(timezone.utc) - timedelta(days=TTL_DAGEN)).isoformat()


def is_configured() -> bool:
    """True als Supabase beschikbaar is voor caching."""
    return bool(SUPABASE_URL and (SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY))


def _headers(prefer: Optional[str] = None) -> dict:
    key = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
    h = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


def _norm_vest(vestigingsnummer: Optional[str]) -> str:
    return (vestigingsnummer or "").strip()


async def lees_cache(kvk_nummer: str, vestigingsnummer: Optional[str]) -> Optional[dict]:
    """
    Zoek een eerder opgeslagen detail-record.

    Retourneert dict met {details, opgehaald_op} of None als niet gevonden /
    verlopen (ouder dan TTL_DAGEN) / cache niet beschikbaar.
    """
    if not is_configured():
        return None

    params = {
        "select": "details,opgehaald_op",
        "kvk_nummer": f"eq.{kvk_nummer.strip()}",
        "vestigingsnummer": f"eq.{_norm_vest(vestigingsnummer)}",
        "opgehaald_op": f"gte.{_verloop_grens_iso()}",  # verlopen records overslaan
        "limit": "1",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/{_TABEL}",
                headers=_headers(),
                params=params,
            )
            resp.raise_for_status()
            rows = resp.json()
    except Exception as exc:  # cache mag nooit de hoofd-flow breken
        logger.warning("KVK cache-lees mislukt (val terug op live): %s", exc)
        return None

    return rows[0] if rows else None


async def welke_in_cache(kvk_nummers: list[str]) -> set[tuple[str, str]]:
    """
    Batch-check: welke (kvk_nummer, vestigingsnummer)-combinaties zitten al in de cache?

    Retourneert een set van (kvk_nummer, vestigingsnummer)-tuples (vestigingsnummer
    genormaliseerd naar "" indien leeg). Lege set als niets gevonden / niet beschikbaar.
    """
    schoon = sorted({n.strip() for n in kvk_nummers if n and n.strip()})
    if not schoon or not is_configured():
        return set()

    params = {
        "select": "kvk_nummer,vestigingsnummer",
        "kvk_nummer": f"in.({','.join(schoon)})",
        "opgehaald_op": f"gte.{_verloop_grens_iso()}",  # verlopen records tellen als niet-gecachet
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/{_TABEL}",
                headers=_headers(),
                params=params,
            )
            resp.raise_for_status()
            rows = resp.json()
    except Exception as exc:
        logger.warning("KVK cache batch-check mislukt: %s", exc)
        return set()

    return {(r.get("kvk_nummer"), r.get("vestigingsnummer") or "") for r in rows}


async def schrijf_cache(
    kvk_nummer: str,
    vestigingsnummer: Optional[str],
    details: dict,
    opgehaald_door: Optional[str] = None,
) -> None:
    """
    Sla detail-record op (upsert op kvk_nummer + vestigingsnummer).
    Fouten worden gelogd maar nooit doorgegooid — caching is best-effort.
    """
    if not is_configured():
        return

    payload = {
        "kvk_nummer": kvk_nummer.strip(),
        "vestigingsnummer": _norm_vest(vestigingsnummer),
        "naam": details.get("naam"),
        "details": details,
        "opgehaald_door": opgehaald_door,
        # opgehaald_op wordt door een DB-trigger op now() gezet (ook bij upsert).
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/{_TABEL}",
                headers=_headers("resolution=merge-duplicates,return=minimal"),
                json=payload,
            )
            resp.raise_for_status()
    except Exception as exc:
        logger.warning("KVK cache-schrijf mislukt: %s", exc)
