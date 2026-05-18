"""Fastlane token-refresh via Playwright login.

De Fastlane API gebruikt een statische Bearer-token + user-hash die we
moeten ophalen door in te loggen via hypotheekbond.nl. Het token blijft
geldig zolang de sessie actief is — typisch enkele weken tot maanden.

Workflow:
1. Login op hypotheekbond.nl met email/wachtwoord
2. Navigeer naar de Fastlane rente-pagina (via iframe)
3. Onderschep een API-call naar fds2.fdta.nl en lees `authorization` + `x-user-hash` headers
4. Sla op in Supabase (table `scraper_credentials`) of return als dict

Wanneer gebruiken:
- Bij eerste deploy: handmatig draaien om initial credentials te krijgen
- In scraper-orchestrator: als API een 401/403 geeft, refresh credentials
- Periodiek (maandelijks): refresh om verlopen tokens voor te zijn
"""

from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger("nat-api.scraper.fastlane-auth")

HYPOTHEEKBOND_LOGIN = "https://www.hypotheekbond.nl/inloggen"
FASTLANE_RENTE_PAGE = "https://fastlane.fdta.nl/rente/rentevast-periode"


async def refresh_fastlane_credentials(
    email: str | None = None,
    password: str | None = None,
    headless: bool = True,
    timeout: float = 60.0,
) -> dict[str, str] | None:
    """Login op hypotheekbond.nl en haal Fastlane API-credentials op.

    Returns:
        Dict met 'auth_token' en 'user_hash', of None bij fout.

    Args:
        email: HB login e-mail (default: env HYPOTHEEKBOND_EMAIL)
        password: HB wachtwoord (default: env HYPOTHEEKBOND_PASSWORD)
        headless: Of Playwright zonder UI moet draaien
        timeout: Max seconden voor de hele login-flow
    """
    email = email or os.environ.get("HYPOTHEEKBOND_EMAIL")
    password = password or os.environ.get("HYPOTHEEKBOND_PASSWORD")

    if not email or not password:
        logger.error("[fastlane-auth] Geen HYPOTHEEKBOND_EMAIL/PASSWORD ingesteld")
        return None

    try:
        # Playwright moet async geïnstalleerd zijn — staat al in requirements.txt
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("[fastlane-auth] playwright niet geïnstalleerd. `pip install playwright`")
        return None

    credentials: dict[str, str] = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()

        # Vang fds2.fdta.nl requests om auth headers te onderscheppen
        captured = {"auth": None, "user_hash": None}

        async def on_request(request):
            if "fds2.fdta.nl/v1/" in request.url and "filter" in request.url:
                headers = request.headers
                if not captured["auth"]:
                    captured["auth"] = headers.get("authorization")
                if not captured["user_hash"]:
                    captured["user_hash"] = headers.get("x-user-hash")

        page.on("request", on_request)

        try:
            # 1. Login
            logger.info("[fastlane-auth] Login op hypotheekbond.nl...")
            await page.goto(HYPOTHEEKBOND_LOGIN, timeout=int(timeout * 1000))
            await page.wait_for_load_state("networkidle")
            await page.fill('input[name="email"]', email)
            await page.fill('input[name="password"]', password)
            await page.click('button[type="submit"], input[type="submit"]')
            await page.wait_for_timeout(3000)

            # 2. Navigeer naar Fastlane rente-pagina
            logger.info("[fastlane-auth] Naar Fastlane rente-pagina...")
            await page.goto(FASTLANE_RENTE_PAGE, timeout=int(timeout * 1000))
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(5000)  # wacht op API call

            # 3. Check of credentials zijn opgevangen
            if captured["auth"] and captured["user_hash"]:
                credentials["auth_token"] = captured["auth"]
                credentials["user_hash"] = captured["user_hash"]
                logger.info("[fastlane-auth] Credentials succesvol opgehaald")
            else:
                logger.error(
                    "[fastlane-auth] Geen credentials onderschept. Auth=%s, UserHash=%s",
                    bool(captured["auth"]), bool(captured["user_hash"]),
                )
        except Exception as e:
            logger.exception("[fastlane-auth] Fout tijdens login: %s", e)
        finally:
            await browser.close()

    return credentials if credentials else None


async def verify_fastlane_credentials(auth_token: str, user_hash: str) -> bool:
    """Test of een Fastlane token nog geldig is met een simpele API-call."""
    import httpx

    try:
        url = "https://fds2.fdta.nl/v1/filter/ltv/58/120/C/2/nee/1/ja"
        headers = {
            "authorization": auth_token,
            "x-user-hash": user_hash,
            "origin": "https://fastlane.fdta.nl",
            "referer": "https://fastlane.fdta.nl/",
            "user-agent": "Mozilla/5.0",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            return resp.status_code == 200 and "labels" in resp.text
    except Exception as e:
        logger.warning("[fastlane-auth] Verificatie mislukt: %s", e)
        return False


# CLI-helper: handmatig credentials refreshen
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    async def main():
        creds = await refresh_fastlane_credentials(headless="--headed" not in sys.argv)
        if creds:
            print("\n=== Nieuwe credentials ===")
            print(f"FASTLANE_AUTH_TOKEN={creds['auth_token']}")
            print(f"FASTLANE_USER_HASH={creds['user_hash']}")
            print()
            print("Sla deze op als environment variables op Render.")
        else:
            print("\nLogin mislukt. Check credentials en logs.")
            sys.exit(1)

    asyncio.run(main())
