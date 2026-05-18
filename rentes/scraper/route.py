"""Scraper API endpoints — cron trigger, status, logs."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request

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
    except Exception as e:
        logger.exception("[scraper] Background scrape gefaald: %s", e)
        _last_run = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": {"status": "error", "error": str(e)},
        }
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


@router.post("/test-mini")
async def scraper_test_mini(request: Request):
    """Mini-scrape: 1 Fastlane call + parsing test (zonder Supabase, zonder loop).

    Doet exact wat 1 stap van de scraper doet: fetch + parse + naam-normalisatie.
    Snel (~2s) en toont of er onderweg iets fout gaat.
    """
    secret = request.headers.get("X-Cron-Secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        raise HTTPException(401, "Ongeldig cron secret")

    import time
    from rentes.scraper.sources.fastlane import FastlaneScraper

    start = time.time()
    scraper = FastlaneScraper()

    out = {
        "auth_configured": bool(scraper.auth_token and scraper.user_hash),
    }

    try:
        import httpx
        url = scraper._build_ltv_url(58, 120, "C", False)
        out["url"] = url

        async with httpx.AsyncClient(timeout=10.0, headers=scraper._headers()) as client:
            resp = await scraper._fetch(client, url)
        out["http_status"] = resp.status_code

        rates = scraper._parse_ltv_response(
            resp.json(), aflosvorm="annuitair", rentevaste_periode=10,
            energielabel="C", nhg=False,
        )
        out["rates_parsed"] = len(rates)
        out["unique_banks"] = len(set(r.geldverstrekker for r in rates))
        if rates:
            sample = rates[0]
            out["sample_rate"] = {
                "geldverstrekker": sample.geldverstrekker,
                "productlijn": sample.productlijn,
                "ltv": sample.ltv_categorie,
                "rente": sample.rente,
            }
        out["success"] = True
    except Exception as e:
        out["exception_type"] = type(e).__name__
        out["exception_message"] = str(e)[:500]
        out["success"] = False

    out["duration_seconds"] = round(time.time() - start, 2)
    return out


@router.post("/refresh-token-debug")
async def scraper_refresh_token_debug(request: Request):
    """Token refresh met uitgebreide stap-voor-stap diagnostiek."""
    secret = request.headers.get("X-Cron-Secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        raise HTTPException(401, "Ongeldig cron secret")

    import time
    from playwright.async_api import async_playwright

    email = os.environ.get("HYPOTHEEKBOND_EMAIL", "")
    password = os.environ.get("HYPOTHEEKBOND_PASSWORD", "")

    steps = []
    captured_calls = []
    out = {
        "email_set": bool(email),
        "password_set": bool(password),
        "password_length": len(password),
    }

    if not email or not password:
        out["error"] = "Missing credentials env vars"
        return out

    start = time.time()
    try:
        async with async_playwright() as p:
            steps.append({"step": "playwright_started", "t": round(time.time() - start, 2)})
            browser = await p.chromium.launch(headless=True)
            steps.append({"step": "browser_launched", "t": round(time.time() - start, 2)})
            context = await browser.new_context()
            page = await context.new_page()

            def on_req(req):
                if "fdta" in req.url or "fastlane" in req.url:
                    captured_calls.append({
                        "method": req.method,
                        "url": req.url[:150],
                        "auth": req.headers.get("authorization", "")[:16],
                        "hash": req.headers.get("x-user-hash", "")[:16],
                    })

            page.on("request", on_req)

            await page.goto("https://www.hypotheekbond.nl/inloggen", timeout=30000)
            await page.wait_for_load_state("networkidle")
            steps.append({"step": "login_page_loaded", "t": round(time.time() - start, 2), "url": page.url})

            await page.fill('input[name="email"]', email)
            await page.fill('input[name="password"]', password)
            await page.click('button[type="submit"], input[type="submit"]')
            await page.wait_for_timeout(3000)
            steps.append({"step": "login_submitted", "t": round(time.time() - start, 2), "url": page.url, "title": await page.title()})

            await page.goto("https://fastlane.fdta.nl/rente/rentevast-periode", timeout=30000)
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(7000)
            steps.append({"step": "fastlane_loaded", "t": round(time.time() - start, 2), "url": page.url, "title": await page.title()})

            body_text = await page.inner_text("body")
            out["fastlane_body_preview"] = body_text[:300]

            await browser.close()

        out["captured_calls"] = captured_calls[:10]
        out["captured_calls_count"] = len(captured_calls)
        out["steps"] = steps
        out["total_duration"] = round(time.time() - start, 2)
    except Exception as e:
        out["exception"] = str(e)[:500]
        out["exception_type"] = type(e).__name__
        out["steps"] = steps

    return out


@router.get("/playwright-status")
async def playwright_status(request: Request):
    """Toon wat er in de Playwright cache zit + voer install opnieuw uit."""
    secret = request.headers.get("X-Cron-Secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        raise HTTPException(401, "Ongeldig cron secret")

    import asyncio as _asyncio
    out = {}

    # 1. Welke cache dir gebruikt Playwright?
    for env_var in ["PLAYWRIGHT_BROWSERS_PATH", "HOME"]:
        out[f"env_{env_var}"] = os.environ.get(env_var, "")

    # 2. Wat staat er in de cache?
    for path in ["/opt/render/.cache/ms-playwright", "/root/.cache/ms-playwright", "~/.cache/ms-playwright"]:
        expanded = os.path.expanduser(path)
        try:
            if os.path.isdir(expanded):
                out[f"contents_{path}"] = sorted(os.listdir(expanded))
            else:
                out[f"contents_{path}"] = "DOES_NOT_EXIST"
        except Exception as e:
            out[f"contents_{path}"] = f"ERROR: {e}"

    # 3. Playwright version
    try:
        proc = await _asyncio.create_subprocess_exec(
            "python", "-c", "import playwright; print(playwright.__version__)",
            stdout=_asyncio.subprocess.PIPE, stderr=_asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        out["playwright_version"] = stdout.decode().strip()
    except Exception as e:
        out["playwright_version_error"] = str(e)

    # 4. Run --force install met full stderr
    try:
        proc = await _asyncio.create_subprocess_exec(
            "python", "-m", "playwright", "install", "--force", "chromium",
            stdout=_asyncio.subprocess.PIPE,
            stderr=_asyncio.subprocess.STDOUT,
        )
        stdout, _ = await _asyncio.wait_for(proc.communicate(), timeout=180)
        out["force_install_returncode"] = proc.returncode
        out["force_install_output"] = stdout.decode("utf-8", errors="replace")[-3000:]
    except _asyncio.TimeoutError:
        out["force_install"] = "TIMEOUT after 180s"
    except Exception as e:
        out["force_install_exception"] = str(e)

    # 5. Check opnieuw na install
    for path in ["/opt/render/.cache/ms-playwright"]:
        expanded = os.path.expanduser(path)
        try:
            if os.path.isdir(expanded):
                out[f"contents_after_{path}"] = sorted(os.listdir(expanded))
        except Exception as e:
            out[f"contents_after_{path}"] = f"ERROR: {e}"

    return out


@router.post("/install-playwright")
async def scraper_install_playwright(request: Request):
    """Installeer Playwright Chromium browsers op runtime.

    Handig als build-time install faalt of als Playwright wordt geupgrade.
    Beveiligd met X-Cron-Secret. Duurt 30-60 seconden.
    """
    secret = request.headers.get("X-Cron-Secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        raise HTTPException(401, "Ongeldig cron secret")

    import asyncio as _asyncio
    import time
    start = time.time()
    try:
        proc = await _asyncio.create_subprocess_exec(
            "python", "-m", "playwright", "install", "chromium", "chromium-headless-shell",
            stdout=_asyncio.subprocess.PIPE,
            stderr=_asyncio.subprocess.STDOUT,
        )
        stdout, _ = await _asyncio.wait_for(proc.communicate(), timeout=180)
        duration = round(time.time() - start, 2)
        return {
            "status": "ok" if proc.returncode == 0 else "error",
            "returncode": proc.returncode,
            "duration_seconds": duration,
            "output": stdout.decode("utf-8", errors="replace")[-2000:],
        }
    except _asyncio.TimeoutError:
        return {"status": "timeout", "duration_seconds": round(time.time() - start, 2)}
    except Exception as e:
        return {"status": "exception", "exception_type": type(e).__name__, "exception_message": str(e)}


@router.post("/refresh-token")
async def scraper_refresh_token(request: Request):
    """Trigger Playwright login + sla nieuwe Fastlane token op in Supabase.

    Handmatig aan te roepen als de auto-refresh om wat voor reden niet werkt,
    of om initiële credentials op te slaan in de store.
    """
    secret = request.headers.get("X-Cron-Secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        raise HTTPException(401, "Ongeldig cron secret")

    import time
    from rentes.scraper.fastlane_auth import refresh_and_store_fastlane_credentials

    start = time.time()
    try:
        token, user_hash = await refresh_and_store_fastlane_credentials()
        duration = round(time.time() - start, 2)
        if token and user_hash:
            return {
                "status": "ok",
                "duration_seconds": duration,
                "auth_token_first8": token[:8],
                "auth_token_last4": token[-4:],
                "user_hash_first8": user_hash[:8],
                "message": "Token opgeslagen in scraper_credentials tabel",
            }
        return {
            "status": "error",
            "duration_seconds": duration,
            "message": "Playwright login mislukt of geen token onderschept",
        }
    except Exception as e:
        return {
            "status": "exception",
            "duration_seconds": round(time.time() - start, 2),
            "exception_type": type(e).__name__,
            "exception_message": str(e)[:500],
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

    auth_token = os.environ.get("FASTLANE_AUTH_TOKEN", "")
    user_hash = os.environ.get("FASTLANE_USER_HASH", "")

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
