"""Scraper API endpoints — cron trigger, status, logs."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from pydantic import BaseModel

from rentes.scraper.runner import ScrapeOrchestrator

logger = logging.getLogger("nat-api.scraper")

router = APIRouter(prefix="/rentes/scraper", tags=["rentes-scraper"])

CRON_SECRET = os.environ.get("CRON_SECRET", "")

# In-memory laatste run status
_last_run: dict | None = None
_is_running: bool = False


async def _run_scrape_async(dry_run: bool, source: Optional[str]):
    """Voer de scrape uit in de achtergrond en update _last_run."""
    global _last_run, _is_running
    _is_running = True
    try:
        orchestrator = ScrapeOrchestrator(dry_run=dry_run, single_source=source)
        result = await orchestrator.run()
        _last_run = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": result,
        }
        # Status 'error' / 'partial' ook naar Sentry — anders zien we alleen excepties
        status = result.get("status", "")
        if status in ("error", "partial"):
            try:
                import sentry_sdk
                sentry_sdk.capture_message(
                    f"Scraper run finished with status={status}",
                    level="warning" if status == "partial" else "error",
                    extras={"result": result},
                )
            except Exception:
                pass
    except Exception as e:
        logger.exception("[scraper] Background scrape gefaald: %s", e)
        _last_run = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": {"status": "error", "error": str(e)},
        }
        # Uncaught exception → Sentry
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(e)
        except Exception:
            pass
    finally:
        _is_running = False


@router.post("/run")
async def scraper_run(
    request: Request,
    dry_run: bool = Query(False, description="Alleen scrapen en valideren, niet opslaan"),
    source: Optional[str] = Query(None, description="Alleen deze bron draaien"),
):
    """Cron endpoint: start een scrape-run in de achtergrond.

    Beveiligd met X-Cron-Secret header. Retourneert direct (HTTP 202),
    de scrape draait door in de achtergrond. Vraag /status op voor het resultaat.

    Query params:
    - dry_run=true: scrape + valideer zonder opslag
    - source=fastlane: alleen deze bron draaien
    """
    global _is_running

    secret = request.headers.get("X-Cron-Secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        raise HTTPException(401, "Ongeldig cron secret")

    if _is_running:
        return {
            "status": "already_running",
            "message": "Er draait al een scrape. Wacht tot deze klaar is.",
        }

    # Start de scrape in de achtergrond met asyncio.create_task
    # (BackgroundTasks van FastAPI werkt niet altijd lekker bij langlopende taken)
    asyncio.create_task(_run_scrape_async(dry_run=dry_run, source=source))

    return {
        "status": "started",
        "message": "Scrape gestart in achtergrond. Vraag GET /rentes/scraper/status voor resultaat.",
        "dry_run": dry_run,
        "source": source,
    }


@router.get("/status")
async def scraper_status():
    """Laatste scrape-run status (in-memory)."""
    if not _last_run:
        msg = "Scrape draait nu (start net)" if _is_running else "Nog geen scrape-run uitgevoerd sinds server start"
        return {"status": "running" if _is_running else "no_runs", "message": msg}
    out = dict(_last_run)
    out["is_running"] = _is_running
    return out


@router.get("/status-health")
async def scraper_status_health(
    max_age_hours: int = Query(26, ge=1, le=168, description="Max ouderdom laatste run in uren"),
):
    """Health check voor monitoring/cron-job alerting.

    Returnt HTTP 500 als de laatste scrape:
    - Niet bestaat in scraper_logs tabel
    - Ouder is dan max_age_hours (default 26 — 1 dag + 2 uur buffer)
    - Geen success heeft
    - Te weinig rates heeft opgeslagen (< 100)

    HTTP 200 als alles in orde is.

    Use case: 2e cron-job.org job draait dit 15min na de scrape, met
    'notify on failure' aan → mail bij fout zonder dat de scrape-trigger zelf
    al een mail moest sturen (die retourneert nu altijd 200 met 'started').
    """
    import httpx

    supabase_url = os.environ.get("SUPABASE_URL", "")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")

    if not supabase_url or not service_key:
        raise HTTPException(500, "Supabase niet geconfigureerd — kan health niet bepalen")

    try:
        url = f"{supabase_url}/rest/v1/scraper_logs"
        params = {
            "select": "*",
            "bron": "eq.fastlane",
            "order": "created_at.desc",
            "limit": "1",
        }
        headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
        rows = resp.json()
    except Exception as e:
        raise HTTPException(500, f"Kan scraper_logs niet lezen: {e}")

    if not rows:
        raise HTTPException(500, "Geen scraper runs gevonden in scraper_logs tabel")

    last = rows[0]
    created_at = datetime.fromisoformat(last["created_at"].replace("Z", "+00:00"))
    age_hours = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600

    problems = []
    if age_hours > max_age_hours:
        problems.append(f"Laatste scrape is {age_hours:.1f}u oud (max {max_age_hours}u)")
    if not last.get("success"):
        problems.append(f"Laatste scrape was niet succesvol ({last.get('errors', 0)} errors)")
    if last.get("rates_stored", 0) < 100:
        problems.append(f"Laatste scrape stored slechts {last.get('rates_stored', 0)} rates (< 100)")

    summary = {
        "last_run_at": last["created_at"],
        "age_hours": round(age_hours, 1),
        "success": last.get("success"),
        "rates_scraped": last.get("rates_scraped"),
        "rates_stored": last.get("rates_stored"),
        "errors": last.get("errors"),
    }

    if problems:
        action = "Actie: POST /rentes/scraper/set-credentials met nieuwe token uit fastlane.fdta.nl DevTools"
        raise HTTPException(500, {
            "status": "unhealthy",
            "problems": problems,
            "last_run": summary,
            "action": action,
        })

    return {"status": "healthy", "last_run": summary}


class SetCredentialsRequest(BaseModel):
    auth_token: str
    user_hash: str
    notes: str | None = None


@router.post("/set-credentials")
async def scraper_set_credentials(body: SetCredentialsRequest, request: Request):
    """Handmatig nieuwe Fastlane credentials opslaan in Supabase.

    Veel betrouwbaarder dan auto-refresh via Playwright (Fastlane SSO is
    sessiegebonden en niet stabiel te scripten). Workflow:

    1. Open https://fastlane.fdta.nl/rente/rentevast-periode in browser (ingelogd)
    2. F12 → Network tab → klik 'ja' request
    3. Kopieer 'authorization' header value
    4. Kopieer 'x-user-hash' header value
    5. POST naar dit endpoint met die waarden

    Beveiligd met X-Cron-Secret header.
    """
    secret = request.headers.get("X-Cron-Secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        raise HTTPException(401, "Ongeldig cron secret")

    # Validatie: token moet 32 hex chars zijn, user_hash 36 chars (UUID)
    if len(body.auth_token) < 16:
        raise HTTPException(400, f"auth_token te kort ({len(body.auth_token)} chars, verwacht 32)")
    if len(body.user_hash) != 36:
        raise HTTPException(400, f"user_hash moet 36 chars zijn (UUID), kreeg {len(body.user_hash)}")

    # Eerst: test of de nieuwe credentials werken
    import httpx
    test_url = "https://fds2.fdta.nl/v1/filter/ltv/58/120/C/2/nee/1/ja"
    test_headers = {
        "authorization": body.auth_token,
        "x-user-hash": body.user_hash,
        "origin": "https://fastlane.fdta.nl",
        "referer": "https://fastlane.fdta.nl/",
        "user-agent": "Mozilla/5.0",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(test_url, headers=test_headers)
        if resp.status_code != 200:
            return {
                "status": "rejected",
                "message": f"Test-call mislukt met HTTP {resp.status_code}",
                "response_preview": resp.text[:200],
            }
    except Exception as e:
        return {"status": "rejected", "message": f"Test-call exception: {e}"}

    # Werkt → opslaan
    from rentes.scraper.credentials_store import save_credentials
    saved = await save_credentials(
        bron="fastlane",
        auth_token=body.auth_token,
        user_hash=body.user_hash,
        notes=body.notes or "Handmatig ingevoerd via /set-credentials",
    )

    return {
        "status": "ok" if saved else "warning",
        "saved_to_supabase": saved,
        "test_call_status": 200,
        "message": "Credentials geverifieerd en opgeslagen — scraper gebruikt deze bij volgende run",
    }


@router.get("/diagnostic")
async def scraper_diagnostic(request: Request):
    """Diagnostiek endpoint: test of Fastlane API bereikbaar is vanaf deze server.

    Beveiligd met X-Cron-Secret. Doet 1 simpele API-call naar Fastlane en
    retourneert HTTP status, response-grootte en eventuele errors. Handig
    om te zien of de credentials kloppen en of Render's IP toegang heeft.
    """
    secret = request.headers.get("X-Cron-Secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        raise HTTPException(401, "Ongeldig cron secret")

    import time
    import httpx
    from rentes.scraper.credentials_store import get_credentials, clear_cache

    # Lees uit Supabase (met env-var fallback) — zelfde flow als de scraper
    clear_cache("fastlane")  # geen stale cache
    auth_token, user_hash = await get_credentials("fastlane")
    auth_token = auth_token or ""
    user_hash = user_hash or ""

    result = {
        "auth_token_configured": bool(auth_token),
        "auth_token_length": len(auth_token),
        "auth_token_first8": auth_token[:8] if auth_token else "",
        "auth_token_last4": auth_token[-4:] if auth_token else "",
        "user_hash_configured": bool(user_hash),
        "user_hash_length": len(user_hash),
        "user_hash_first8": user_hash[:8] if user_hash else "",
        "test_url": "https://fds2.fdta.nl/v1/filter/ltv/58/120/C/2/nee/1/ja",
    }

    # Probeer ook outbound IP detecteren via een echo-service
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            ip_resp = await client.get("https://api.ipify.org?format=json")
            result["outbound_ip"] = ip_resp.json().get("ip")
    except Exception as e:
        result["outbound_ip_error"] = str(e)

    if not auth_token or not user_hash:
        result["error"] = "Credentials niet geconfigureerd"
        return result

    headers = {
        "authorization": auth_token,
        "x-user-hash": user_hash,
        "origin": "https://fastlane.fdta.nl",
        "referer": "https://fastlane.fdta.nl/",
        "user-agent": "Mozilla/5.0",
        "accept": "*/*",
    }

    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(result["test_url"], headers=headers)
        duration = time.time() - start
        result["duration_seconds"] = round(duration, 2)
        result["status_code"] = resp.status_code
        result["response_length"] = len(resp.content)
        if resp.status_code == 200:
            try:
                data = resp.json()
                result["labels_count"] = len(data.get("labels", []))
                result["risk_categories_count"] = len(data.get("riskCategories", []))
                result["success"] = True
            except Exception as e:
                result["parse_error"] = str(e)
                result["response_preview"] = resp.text[:300]
        else:
            result["response_preview"] = resp.text[:500]
            result["success"] = False
    except Exception as e:
        result["duration_seconds"] = round(time.time() - start, 2)
        result["exception_type"] = type(e).__name__
        result["exception_message"] = str(e)
        result["success"] = False

    return result


@router.post("/inactivity-trigger")
async def scraper_inactivity_trigger(request: Request):
    """Trigger _update_inactivity_tracking met live scrape-data (synchroon),
    om exception/error zichtbaar te maken in HTTP response."""
    secret = request.headers.get("X-Cron-Secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        raise HTTPException(401, "Ongeldig cron secret")

    from rentes.scraper.sources.fastlane import FastlaneScraper
    from rentes.scraper.runner import ScrapeOrchestrator

    # Pak alleen 1 periode voor snelle test
    from rentes.scraper.sources import fastlane as fl_module
    orig_periodes = fl_module.PERIODES_MAANDEN
    fl_module.PERIODES_MAANDEN = [120]  # alleen 10jr

    try:
        scraper_nieuw = FastlaneScraper(klanttype="nieuw", energielabels=["G"], with_nhg=False)
        scraper_bestaand = FastlaneScraper(klanttype="bestaand", energielabels=["G"], with_nhg=False)
        r_nieuw = await scraper_nieuw.scrape()
        r_bestaand = await scraper_bestaand.scrape()
    finally:
        fl_module.PERIODES_MAANDEN = orig_periodes

    out = {
        "nieuw_rates": len(r_nieuw.rates),
        "bestaand_rates": len(r_bestaand.rates),
        "nieuw_unique_products": len({(r.geldverstrekker, r.productlijn) for r in r_nieuw.rates}),
        "bestaand_unique_products": len({(r.geldverstrekker, r.productlijn) for r in r_bestaand.rates}),
    }

    # Roep _update_inactivity_tracking expliciet aan
    orch = ScrapeOrchestrator()
    try:
        result = await orch._update_inactivity_tracking(r_nieuw.rates, r_bestaand.rates)
        out["update_result"] = result
        out["success"] = True
    except Exception as e:
        import traceback
        out["exception"] = str(e)
        out["traceback"] = traceback.format_exc()[-1500:]
        out["success"] = False

    return out


@router.post("/inactivity-test")
async def scraper_inactivity_test(request: Request):
    """Test: probeer 1 rij in scraper_inactivity_tracking te schrijven, toon exacte error."""
    secret = request.headers.get("X-Cron-Secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        raise HTTPException(401, "Ongeldig cron secret")

    import httpx
    from datetime import datetime as _dt, timezone as _tz

    supabase_url = os.environ.get("SUPABASE_URL", "")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not supabase_url or not service_key:
        return {"error": "no supabase"}

    now = _dt.now(_tz.utc).isoformat()
    test_row = {
        "geldverstrekker": "_TEST_",
        "productlijn": "_TEST_PROD_",
        "status": "actief",
        "last_seen_active_at": now,
        "last_seen_bestaand_at": None,
        "last_updated_at": now,
    }

    url = f"{supabase_url}/rest/v1/scraper_inactivity_tracking"
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation",
    }
    params = {"on_conflict": "geldverstrekker,productlijn"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, params=params, json=[test_row])
        return {
            "status_code": resp.status_code,
            "response_body": resp.text[:1000],
            "request_body": test_row,
        }
    except Exception as e:
        return {"exception": str(e), "exception_type": type(e).__name__}


@router.get("/inactivity")
async def scraper_inactivity(
    status: Optional[str] = Query(None, description="Filter op status: actief, alleen_bestaand, nieuw_in_hb"),
    limit: int = Query(100, ge=1, le=500),
):
    """Toon inactivity tracking status: welke producten zijn alleen voor bestaande klanten beschikbaar?"""
    import httpx

    supabase_url = os.environ.get("SUPABASE_URL", "")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")

    if not supabase_url or not service_key:
        return {"items": [], "message": "Supabase niet geconfigureerd"}

    try:
        url = f"{supabase_url}/rest/v1/scraper_inactivity_tracking"
        params = {
            "select": "*",
            "order": "status,geldverstrekker,productlijn",
            "limit": str(limit),
        }
        if status:
            params["status"] = f"eq.{status}"
        headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()

        rows = resp.json()
        return {
            "total": len(rows),
            "by_status": {
                s: sum(1 for r in rows if r["status"] == s)
                for s in ("actief", "alleen_bestaand", "nieuw_in_hb", "verdwenen")
            },
            "items": rows,
        }
    except Exception as e:
        logger.error("[scraper] Kan inactivity niet ophalen: %s", e)
        raise HTTPException(500, f"Fout bij ophalen inactivity: {e}")


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
