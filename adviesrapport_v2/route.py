"""FastAPI route voor adviesrapport V2 endpoint."""

import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from adviesrapport_v2.schemas import AdviesrapportV2Request
from adviesrapport_v2.supabase_client import lees_dossier, lees_aanvraag
from adviesrapport_v2.report_orchestrator import generate_report

logger = logging.getLogger("nat-api.adviesrapport_v2.route")

router = APIRouter()


def _extract_supabase_token(request: Request) -> str | None:
    """Haal Supabase session token uit de Authorization header.

    Lovable stuurt: Authorization: Bearer <supabase_session_jwt>
    """
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


@router.post("/adviesrapport-pdf-v2")
async def adviesrapport_pdf_v2(
    request_body: AdviesrapportV2Request,
    request: Request,
):
    """
    Genereer een adviesrapport PDF — backend-driven (V2).

    Lovable stuurt alleen dossier_id + aanvraag_id + opties + Authorization header.
    De backend leest Supabase (met de user token), doet alle berekeningen,
    en retourneert de PDF.
    """
    origin = request.headers.get("origin", "onbekend")
    access_token = _extract_supabase_token(request)

    logger.info(
        "Adviesrapport V2 gestart: origin=%s, dossier=%s, aanvraag=%s, has_token=%s",
        origin,
        request_body.dossier_id,
        request_body.aanvraag_id,
        bool(access_token),
    )

    try:
        # 1. Lees data uit Supabase (met user token voor RLS)
        dossier = await lees_dossier(request_body.dossier_id, access_token)
        aanvraag = await lees_aanvraag(request_body.aanvraag_id, access_token)

        # 2. Genereer rapport (sync — alle berekeningen + PDF)
        pdf_bytes = generate_report(
            dossier=dossier,
            aanvraag=aanvraag,
            options=request_body.options,
        )

        # 3. Return PDF
        filename = f"adviesrapport-v2-{request_body.dossier_id[:8]}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    except ValueError as e:
        logger.warning("Adviesrapport V2 data niet gevonden: %s", e)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Adviesrapport V2 mislukt: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Adviesrapport V2 generatie mislukt: {str(e)}",
        )
