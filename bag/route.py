"""FastAPI route voor BAG-objectdata + luchtfoto op adres."""

import logging
from typing import Optional, Dict, Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from bag.client import BAGClient
from bag import luchtfoto as lf

logger = logging.getLogger(__name__)

router = APIRouter(tags=["bag"])


def _adres_punt(postcode: str, huisnummer: int, toevoeging: Optional[str]) -> Dict[str, Any]:
    """Gedeelde helper: BAG-call → RD-coördinaat + adresdata (of foutmelding)."""
    client = BAGClient()
    if not client.is_configured:
        raise HTTPException(status_code=503, detail="BAG niet beschikbaar (BAG_API_KEY ontbreekt).")

    schoon_postcode = postcode.replace(" ", "").upper()
    try:
        data = client.adres_uitgebreid(schoon_postcode, huisnummer, toevoeging)
    except httpx.HTTPStatusError as e:
        logger.warning("BAG API fout: %s — %s", e.response.status_code, e.response.text[:300])
        return {"gevonden": False, "error": f"BAG-API fout ({e.response.status_code})"}
    except Exception as e:
        logger.warning("BAG opvragen mislukt: %s", e)
        return {"gevonden": False, "error": "Opvragen mislukt"}

    if data.get("gevonden") and data.get("rd_x") is None:
        return {"gevonden": False, "error": "Geen coördinaat beschikbaar voor dit adres"}
    return data


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


@router.get("/luchtfoto")
async def luchtfoto(
    postcode: str,
    huisnummer: int,
    toevoeging: Optional[str] = None,
    grootte: Optional[float] = None,
    breedte: Optional[int] = None,
    hoogte: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Luchtfoto-URL voor een adres — GRATIS (PDOK Beeldmateriaal NL).

    Geeft een kant-en-klare PDOK WMS-URL terug die de frontend direct als
    afbeelding kan laden. `grootte` = breedte van de uitsnede in meters
    (20–1000, default 80). `breedte`/`hoogte` = pixels (64–2048, default 600).
    """
    data = _adres_punt(postcode, huisnummer, toevoeging)
    if not data.get("gevonden"):
        return {"gevonden": False, "error": data.get("error", "Adres niet gevonden")}

    grootte_m = lf.clamp_grootte(grootte)
    px_w = lf.clamp_pixels(breedte)
    px_h = lf.clamp_pixels(hoogte)
    url = lf.wms_url(data["rd_x"], data["rd_y"], grootte_m, px_w, px_h)

    return {
        "gevonden": True,
        "url": url,
        "rd_x": data["rd_x"],
        "rd_y": data["rd_y"],
        "grootte_m": grootte_m,
        "breedte": px_w,
        "hoogte": px_h,
        "bron": lf.BRON,
    }


@router.get("/luchtfoto/image")
async def luchtfoto_image(
    postcode: str,
    huisnummer: int,
    toevoeging: Optional[str] = None,
    grootte: Optional[float] = None,
    breedte: Optional[int] = None,
    hoogte: Optional[int] = None,
):
    """
    Luchtfoto als PNG — server-side proxy (voor insluiten in PDF/adviesrapport).

    Zelfde parameters als /luchtfoto, maar retourneert de afbeelding zelf.
    """
    data = _adres_punt(postcode, huisnummer, toevoeging)
    if not data.get("gevonden"):
        raise HTTPException(status_code=404, detail=data.get("error", "Adres niet gevonden"))

    url = lf.wms_url(
        data["rd_x"], data["rd_y"],
        lf.clamp_grootte(grootte), lf.clamp_pixels(breedte), lf.clamp_pixels(hoogte),
    )

    try:
        async with httpx.AsyncClient(timeout=20.0) as http:
            resp = await http.get(url, headers={"User-Agent": "HondsrugFinance-Rekentool/1.0"})
        resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning("Luchtfoto ophalen mislukt: %s", e)
        raise HTTPException(status_code=502, detail="Luchtfoto kon niet worden opgehaald")

    content_type = resp.headers.get("content-type", "image/png")
    if "image" not in content_type:
        # PDOK geeft bij een fout een XML ServiceException terug i.p.v. een plaatje.
        logger.warning("Luchtfoto: onverwacht content-type %s — %s", content_type, resp.text[:300])
        raise HTTPException(status_code=502, detail="Luchtfoto-service gaf geen afbeelding terug")

    return Response(
        content=resp.content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
