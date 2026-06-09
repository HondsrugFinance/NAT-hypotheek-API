"""FastAPI routes voor de Kadaster KIK Inzage koppeling."""

import logging

from fastapi import APIRouter, HTTPException

from kadaster import keys

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kadaster", tags=["kadaster"])


@router.get("/jwks.json")
def jwks_endpoint() -> dict:
    """
    Publieke JWKS (JSON Web Key Set) voor de KIK Inzage OAuth-koppeling.

    Het Kadaster haalt deze URL op om de signed JWT's van onze tool te
    valideren. Bevat ALLEEN de publieke sleutel — nooit de privésleutel.

    Vul deze URL in als 'JWKS URI' bij de KIK Inzage-aanvraag:
        https://nat-hypotheek-api.onrender.com/kadaster/jwks.json
    """
    if not keys.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Kadaster-sleutel niet geconfigureerd (KADASTER_JWT_PRIVATE_KEY ontbreekt in env).",
        )
    try:
        return keys.jwks()
    except Exception as exc:  # ongeldige PEM o.i.d.
        logger.error("JWKS genereren mislukt: %s", exc)
        raise HTTPException(status_code=500, detail=f"JWKS genereren mislukt: {exc}")
