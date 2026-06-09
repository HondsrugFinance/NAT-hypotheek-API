"""FastAPI route voor bestemming op adres (Ruimtelijke Plannen API)."""

import logging
from typing import Optional, Dict, Any

import httpx
from fastapi import APIRouter, HTTPException, Request

from bestemming.client import BestemmingClient

logger = logging.getLogger(__name__)

router = APIRouter(tags=["bestemming"])


@router.get("/bestemming")
async def bestemming(
    postcode: str,
    huisnummer: int,
    toevoeging: Optional[str] = None,
    request: Request = None,
) -> Dict[str, Any]:
    """
    Bestemming(en) op een adres volgens de geldende ruimtelijke plannen — GRATIS.

    Retourneert:
      - gevonden: bool
      - primair: str | None (bv. "Wonen")
      - bestemmingen: [{naam, hoofdgroep, type, plan_naam}]
      - plannen: [{id, naam, type}]
      - adres: {straat, huisnummer, postcode, plaats}
    """
    origin = request.headers.get("origin", "onbekend") if request else "onbekend"
    schoon_postcode = postcode.replace(" ", "").upper()
    logger.info("Bestemming: origin=%s, postcode=%s, huisnummer=%s", origin, schoon_postcode, huisnummer)

    client = BestemmingClient()
    if not client.is_configured:
        raise HTTPException(
            status_code=503,
            detail="Bestemming niet beschikbaar (RUIMTELIJKE_PLANNEN_API_KEY ontbreekt).",
        )

    try:
        return client.bestemming_op_adres(schoon_postcode, huisnummer, toevoeging)
    except httpx.HTTPStatusError as e:
        # API-fout (bv. 401 ongeldige key) → nette boodschap i.p.v. 500.
        logger.warning("Ruimtelijke Plannen API fout: %s — %s", e.response.status_code, e.response.text[:300])
        msg = "Ongeldige API-key" if e.response.status_code == 401 else f"Plannen-API fout ({e.response.status_code})"
        return {"gevonden": False, "error": msg, "primair": None, "bestemmingen": [], "plannen": [], "adres": None}
    except Exception as e:
        logger.warning("Bestemming opvragen mislukt: %s", e)
        return {"gevonden": False, "error": "Opvragen mislukt", "primair": None, "bestemmingen": [], "plannen": [], "adres": None}
