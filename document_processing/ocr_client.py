"""Azure Document Intelligence client — OCR via pure httpx."""

import asyncio
import base64
import logging
import os
import time

import httpx

logger = logging.getLogger("nat-api.ocr")

AZURE_DI_ENDPOINT = os.environ.get("AZURE_DI_ENDPOINT", "")
AZURE_DI_KEY = os.environ.get("AZURE_DI_KEY", "")

# prebuilt-read: general OCR, goed voor alle documenttypen
MODEL_ID = "prebuilt-read"
API_VERSION = "2024-11-30"

MAX_POLL_SECONDS = 90
POLL_INTERVAL = 2


def is_configured() -> bool:
    return bool(AZURE_DI_ENDPOINT and AZURE_DI_KEY)


async def analyze_document(content: bytes, mime_type: str = "application/pdf") -> dict:
    """Analyseer een document via Azure Document Intelligence.

    Args:
        content: Document bytes (PDF, JPG, PNG, TIFF)
        mime_type: MIME type van het document

    Returns:
        dict met:
            - content: str (volledige OCR tekst)
            - pages: list (pagina-informatie)
            - tables: list (gedetecteerde tabellen)
            - page_count: int

    Raises:
        RuntimeError bij fouten of timeout.
    """
    if not is_configured():
        raise RuntimeError("Azure Document Intelligence niet geconfigureerd (AZURE_DI_ENDPOINT / AZURE_DI_KEY)")

    endpoint = AZURE_DI_ENDPOINT.rstrip("/")
    url = f"{endpoint}/documentintelligence/documentModels/{MODEL_ID}:analyze?api-version={API_VERSION}"

    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_DI_KEY,
        "Content-Type": "application/json",
    }

    # Base64-encode het document
    payload = {
        "base64Source": base64.b64encode(content).decode("ascii"),
    }

    start = time.monotonic()

    async with httpx.AsyncClient(timeout=30) as client:
        # Start analyse
        resp = await client.post(url, headers=headers, json=payload)

        if resp.status_code not in (200, 202):
            logger.error("Azure DI analyse start mislukt: %s %s", resp.status_code, resp.text[:300])
            raise RuntimeError(f"Azure DI fout: {resp.status_code} — {resp.text[:200]}")

        # 202 = accepted, poll voor resultaat
        operation_url = resp.headers.get("Operation-Location") or resp.headers.get("operation-location")

        if not operation_url:
            # 200 = direct resultaat (soms bij kleine documenten)
            result = resp.json()
            return _parse_result(result, start)

        # Poll totdat klaar
        poll_headers = {"Ocp-Apim-Subscription-Key": AZURE_DI_KEY}
        elapsed = 0

        while elapsed < MAX_POLL_SECONDS:
            await asyncio.sleep(POLL_INTERVAL)
            elapsed = time.monotonic() - start

            poll_resp = await client.get(operation_url, headers=poll_headers)
            if poll_resp.status_code != 200:
                logger.warning("Azure DI poll fout: %s", poll_resp.status_code)
                continue

            poll_data = poll_resp.json()
            status = poll_data.get("status", "")

            if status == "succeeded":
                result = poll_data.get("analyzeResult", {})
                return _parse_result(result, start)
            elif status == "failed":
                error = poll_data.get("error", {})
                raise RuntimeError(f"Azure DI analyse mislukt: {error.get('message', 'onbekend')}")
            # status == "running" → doorpollen

        raise RuntimeError(f"Azure DI timeout na {MAX_POLL_SECONDS}s")


def _parse_result(result: dict, start: float) -> dict:
    """Parse het Azure DI analyse-resultaat naar een schoon formaat."""
    content = result.get("content", "")
    pages = result.get("pages", [])
    tables = result.get("tables", [])

    duration_ms = int((time.monotonic() - start) * 1000)
    page_count = len(pages)

    logger.info("OCR voltooid: %d pagina's, %d tekens, %d tabellen (%dms)",
                page_count, len(content), len(tables), duration_ms)

    return {
        "content": content,
        "pages": pages,
        "tables": tables,
        "page_count": page_count,
        "duration_ms": duration_ms,
    }
