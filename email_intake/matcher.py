"""Match email-afzender aan een actief dossier in Supabase."""

import logging
import os

import httpx

logger = logging.getLogger("nat-api.email-intake.matcher")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")


def _sb_headers() -> dict:
    key = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


async def match_sender_to_dossier(sender_email: str) -> dict | None:
    """Match een email-afzender aan een actief dossier.

    Matching strategie (volgorde):
    1. Exact match op klant_email
    2. JSONB match op klant_contact_gegevens->aanvrager/partner->email

    Alleen actieve dossiers (niet afgerond/nazorg).
    Bij geen match → None (email wordt genegeerd, niet gelogd).

    Returns:
        Dossier record dict of None bij geen match.
    """
    headers = _sb_headers()
    sender_lower = sender_email.lower().strip()
    select_fields = "id,dossiernummer,klant_naam,klant_email,klant_contact_gegevens,sharepoint_url"

    # Strategie 1: exact match op klant_email
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/dossiers",
                headers=headers,
                params={
                    "select": select_fields,
                    "klant_email": f"eq.{sender_lower}",
                    "status": "neq.afgerond",
                    "order": "created_at.desc",
                    "limit": "1",
                },
            )
            resp.raise_for_status()
            rows = resp.json()
            if rows:
                logger.info("Match op klant_email: %s → dossier %s", sender_lower, rows[0]["dossiernummer"])
                return rows[0]
    except Exception as e:
        logger.debug("Strategie 1 (klant_email) mislukt: %s", e)

    # Strategie 2: JSONB match op contact gegevens (aanvrager + partner email)
    for persoon in ("aanvrager", "partner"):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{SUPABASE_URL}/rest/v1/dossiers",
                    headers=headers,
                    params={
                        "select": select_fields,
                        f"klant_contact_gegevens->{persoon}->>email": f"eq.{sender_lower}",
                        "status": "neq.afgerond",
                        "order": "created_at.desc",
                        "limit": "1",
                    },
                )
                resp.raise_for_status()
                rows = resp.json()
                if rows:
                    logger.info(
                        "Match op contact %s email: %s → dossier %s",
                        persoon, sender_lower, rows[0]["dossiernummer"],
                    )
                    return rows[0]
        except Exception as e:
            logger.debug("Strategie 2 (%s email) mislukt: %s", persoon, e)

    return None
