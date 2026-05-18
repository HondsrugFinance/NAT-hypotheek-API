"""Credentials store voor scraper-tokens (persistent in Supabase).

Voorkomt dat tokens verloren gaan bij Render redeploy of in-memory cache reset.
Bij token-expiry (403) wordt automatisch een refresh getriggerd via Playwright.

Volgorde van lookup:
1. Supabase tabel scraper_credentials (meest recente)
2. Env vars FASTLANE_AUTH_TOKEN + FASTLANE_USER_HASH (fallback)
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

import httpx

logger = logging.getLogger("nat-api.scraper.credentials")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")


def _headers() -> dict[str, str]:
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }


# In-memory cache om Supabase-calls te beperken (gerefresht bij elke scrape-run)
_cache: dict[str, tuple[str, str]] = {}  # bron → (auth_token, user_hash)


async def get_credentials(bron: str = "fastlane") -> tuple[str | None, str | None]:
    """Haal de meest recente credentials op voor een bron.

    Returns (auth_token, user_hash). None,None als niets gevonden.
    """
    # 1. In-memory cache
    if bron in _cache:
        return _cache[bron]

    # 2. Supabase
    if SUPABASE_URL and SUPABASE_SERVICE_KEY:
        try:
            url = f"{SUPABASE_URL}/rest/v1/scraper_credentials"
            params = {
                "select": "auth_token,user_hash",
                "bron": f"eq.{bron}",
                "limit": "1",
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=_headers(), params=params)
                resp.raise_for_status()
                rows = resp.json()
                if rows:
                    token = rows[0].get("auth_token")
                    uhash = rows[0].get("user_hash")
                    if token:
                        _cache[bron] = (token, uhash)
                        logger.info("[credentials] '%s' geladen uit Supabase", bron)
                        return token, uhash
        except Exception as e:
            logger.warning("[credentials] Kan Supabase niet lezen: %s", e)

    # 3. Fallback: env vars (alleen voor fastlane)
    if bron == "fastlane":
        token = os.environ.get("FASTLANE_AUTH_TOKEN")
        uhash = os.environ.get("FASTLANE_USER_HASH")
        if token and uhash:
            _cache[bron] = (token, uhash)
            logger.info("[credentials] '%s' geladen uit env vars (fallback)", bron)
            return token, uhash

    return None, None


async def save_credentials(
    bron: str,
    auth_token: str,
    user_hash: str | None = None,
    notes: str | None = None,
) -> bool:
    """Sla nieuwe credentials op in Supabase. Upsert op 'bron'."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.warning("[credentials] Geen Supabase config — kan niet opslaan")
        return False

    # Upsert
    url = f"{SUPABASE_URL}/rest/v1/scraper_credentials"
    headers = _headers()
    headers["Prefer"] = "resolution=merge-duplicates,return=representation"

    payload = [{
        "bron": bron,
        "auth_token": auth_token,
        "user_hash": user_hash or "",
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
    }]
    # Verhoog refresh_count alleen via RPC of in een tweede call — voor nu skip dat
    params = {"on_conflict": "bron"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=headers, params=params, json=payload)
            resp.raise_for_status()
        # Invalidate cache
        _cache.pop(bron, None)
        logger.info("[credentials] '%s' opgeslagen in Supabase", bron)
        return True
    except Exception as e:
        logger.error("[credentials] Opslaan mislukt voor '%s': %s", bron, e)
        return False


async def mark_403(bron: str = "fastlane") -> None:
    """Markeer dat een 403 is ontvangen — voor monitoring/diagnostiek."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return
    try:
        url = f"{SUPABASE_URL}/rest/v1/scraper_credentials"
        params = {"bron": f"eq.{bron}"}
        payload = {"last_403_at": datetime.now(timezone.utc).isoformat()}
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.patch(url, headers=_headers(), params=params, json=payload)
    except Exception:
        pass  # mag niet falen, alleen voor logging


def clear_cache(bron: str | None = None) -> None:
    """Leeg de in-memory cache. Forceert volgende lookup naar Supabase."""
    if bron is None:
        _cache.clear()
    else:
        _cache.pop(bron, None)
