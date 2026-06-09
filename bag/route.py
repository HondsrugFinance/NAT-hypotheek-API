"""FastAPI route voor BAG-objectdata op adres."""

import logging
from typing import Optional, Dict, Any

import httpx
from fastapi import APIRouter, HTTPException, Request

from bag.client import BAGClient

logger = logging.getLogger(__name__)

router = APIRouter(tags=["bag"])


@router.get("/bag")
async def bag(
    postcode: str,
    huisnummer: int,
    toevoeging: Optional[str] = None,
    request: Request = None,
) -> Dict[str, Any]:
    """
    BAG-objectdata op een adres — GRATIS.

    Retourneert: gevonden, bouwjaar, oppervlakte (m²), gebruiksdoel,
    objecttype, status.
    """
    origin = request.headers.get("origin", "onbekend") if request else "onbekend"
    schoon_postcode = postcode.replace(" ", "").upper()
    logger.info("BAG: origin=%s, postcode=%s, huisnummer=%s", origin, schoon_postcode, huisnummer)

    client = BAGClient()
    if not client.is_configured:
        raise HTTPException(
            status_code=503,
            detail="BAG niet beschikbaar (BAG_API_KEY ontbreekt).",
        )

    try:
        return client.adres_uitgebreid(schoon_postcode, huisnummer, toevoeging)
    except httpx.HTTPStatusError as e:
        logger.warning("BAG API fout: %s — %s", e.response.status_code, e.response.text[:300])
        return {"gevonden": False, "error": f"BAG-API fout ({e.response.status_code})"}
    except Exception as e:
        logger.warning("BAG opvragen mislukt: %s", e)
        return {"gevonden": False, "error": "Opvragen mislukt"}
