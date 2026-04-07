"""Email intake endpoints — cron polling en status."""

import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from email_intake.monitor import poll_all_mailboxes, EMAIL_INTAKE_ENABLED

logger = logging.getLogger("nat-api.email-intake")

router = APIRouter(prefix="/email-intake", tags=["email-intake"])

CRON_SECRET = os.environ.get("CRON_SECRET", "")

# Laatste poll status (in-memory)
_last_poll: dict | None = None


@router.post("/poll")
async def poll_email_inbox(request: Request):
    """Cron endpoint: check alle mailboxen voor nieuwe documenten.

    Beveiligd met X-Cron-Secret header. Bedoeld als cron job (elke 2 min).
    """
    global _last_poll

    secret = request.headers.get("X-Cron-Secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        raise HTTPException(401, "Ongeldig cron secret")

    if not EMAIL_INTAKE_ENABLED:
        return {"status": "disabled", "message": "Email intake is uitgeschakeld (EMAIL_INTAKE_ENABLED=false)"}

    results = await poll_all_mailboxes()

    _last_poll = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }

    # Samenvatting
    total_processed = sum(r.get("processed", 0) for r in results if isinstance(r, dict))
    total_matched = sum(r.get("matched", 0) for r in results if isinstance(r, dict))
    total_uploaded = sum(r.get("uploaded", 0) for r in results if isinstance(r, dict))

    return {
        "status": "ok",
        "mailboxes_polled": len(results),
        "total_processed": total_processed,
        "total_matched": total_matched,
        "total_uploaded": total_uploaded,
        "details": results,
    }


@router.get("/status")
async def email_intake_status():
    """Status van email intake: enabled, laatste poll, configuratie."""
    return {
        "enabled": EMAIL_INTAKE_ENABLED,
        "last_poll": _last_poll,
    }
