"""Scraper API endpoints — cron trigger, status, logs."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from rentes.scraper.runner import ScrapeOrchestrator

logger = logging.getLogger("nat-api.scraper")

router = APIRouter(prefix="/rentes/scraper", tags=["rentes-scraper"])

CRON_SECRET = os.environ.get("CRON_SECRET", "")

# In-memory laatste run status
_last_run: dict | None = None


@router.post("/run")
async def scraper_run(
    request: Request,
    dry_run: bool = Query(False, description="Alleen scrapen en valideren, niet opslaan"),
    source: Optional[str] = Query(None, description="Alleen deze bron draaien"),
):
    """Cron endpoint: start een scrape-run.

    Beveiligd met X-Cron-Secret header. Kan ook handmatig getriggerd worden.

    Query params:
    - dry_run=true: scrape + valideer zonder opslag
    - source=easymortgage: alleen deze bron draaien
    """
    global _last_run

    secret = request.headers.get("X-Cron-Secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        raise HTTPException(401, "Ongeldig cron secret")

    orchestrator = ScrapeOrchestrator(dry_run=dry_run, single_source=source)
    result = await orchestrator.run()

    _last_run = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "result": result,
    }

    return result


@router.get("/status")
async def scraper_status():
    """Laatste scrape-run status (in-memory)."""
    if not _last_run:
        return {"status": "no_runs", "message": "Nog geen scrape-run uitgevoerd sinds server start"}
    return _last_run


@router.get("/logs")
async def scraper_logs(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
):
    """Historische scraper logs uit Supabase."""
    import httpx

    supabase_url = os.environ.get("SUPABASE_URL", "")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")

    if not supabase_url or not service_key:
        return {"logs": [], "message": "Supabase niet geconfigureerd"}

    try:
        url = f"{supabase_url}/rest/v1/scraper_logs"
        params = {
            "select": "*",
            "order": "created_at.desc",
            "limit": str(limit),
        }
        headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()

        return {"logs": resp.json()}
    except Exception as e:
        logger.error("[scraper] Kan logs niet ophalen: %s", e)
        raise HTTPException(500, f"Fout bij ophalen logs: {e}")
