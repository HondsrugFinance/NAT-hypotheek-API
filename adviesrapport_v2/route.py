"""FastAPI route voor adviesrapport V2 endpoint."""

import logging
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from adviesrapport_v2.schemas import AdviesrapportV2Request
from adviesrapport_v2.supabase_client import lees_dossier, lees_aanvraag
from adviesrapport_v2.report_orchestrator import generate_report
from adviesrapport_v2.field_mapper import extract_dossier_data

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


@router.get("/debug/dossier-data/{dossier_id}")
async def debug_dossier_data(
    dossier_id: str,
    request: Request,
    aanvraag_id: str = "",
):
    """Debug endpoint: toon raw Supabase data + genormaliseerde extractie.

    Beveiligd via API-key. Retourneert:
    - raw_dossier_keys: top-level keys van dossier
    - raw_invoer_keys: keys van invoer JSONB
    - raw_klant: klantGegevens dict
    - raw_berekeningen_keys: keys van berekeningen[0]
    - raw_scenario1_keys: keys van scenario1 kolom
    - normalized: wat field_mapper eruit haalt
    """
    # API-key check
    api_key = request.headers.get("x-api-key", "")
    expected = os.environ.get("NAT_API_KEY", "")
    if not expected or api_key != expected:
        raise HTTPException(status_code=401, detail="API key vereist")

    access_token = _extract_supabase_token(request)

    try:
        dossier = await lees_dossier(dossier_id, access_token)

        aanvraag = {}
        if aanvraag_id:
            aanvraag = await lees_aanvraag(aanvraag_id, access_token)

        invoer = dossier.get("invoer") or dossier
        klant = invoer.get("klantGegevens") or invoer.get("klant") or {}
        ber_list = invoer.get("berekeningen") or []
        ber = ber_list[0] if ber_list else {}
        scenario1 = dossier.get("scenario1") or {}

        # Normaliseer met field_mapper
        data = extract_dossier_data(dossier, aanvraag)

        return JSONResponse({
            "raw_dossier_keys": list(dossier.keys()) if isinstance(dossier, dict) else str(type(dossier)),
            "raw_invoer_keys": list(invoer.keys()) if isinstance(invoer, dict) else str(type(invoer)),
            "raw_klant": klant,
            "raw_berekeningen_keys": list(ber.keys()) if ber else [],
            "raw_berekeningen_0": ber,
            "raw_scenario1_keys": list(scenario1.keys()) if isinstance(scenario1, dict) else str(type(scenario1)),
            "raw_scenario1": scenario1,
            "raw_aanvraag": aanvraag,
            "normalized": {
                "aanvrager": {
                    "naam": data.aanvrager.naam,
                    "geboortedatum": data.aanvrager.geboortedatum,
                    "adres": data.aanvrager.adres,
                    "email": data.aanvrager.email,
                    "telefoon": data.aanvrager.telefoon,
                    "inkomen_loondienst": data.aanvrager.inkomen.loondienst,
                    "inkomen_aow": data.aanvrager.inkomen.aow_uitkering,
                    "inkomen_pensioen": data.aanvrager.inkomen.pensioen,
                },
                "partner": {
                    "naam": data.partner.naam if data.partner else None,
                    "geboortedatum": data.partner.geboortedatum if data.partner else None,
                    "inkomen_loondienst": data.partner.inkomen.loondienst if data.partner else None,
                    "inkomen_aow": data.partner.inkomen.aow_uitkering if data.partner else None,
                    "inkomen_pensioen": data.partner.inkomen.pensioen if data.partner else None,
                } if data.partner else None,
                "financiering": {
                    "koopsom": data.financiering.koopsom,
                    "woningwaarde": data.financiering.woningwaarde,
                    "eigen_middelen": data.financiering.eigen_middelen,
                    "kosten_koper": data.financiering.kosten_koper,
                    "energielabel": data.financiering.energielabel,
                    "type_woning": data.financiering.type_woning,
                    "adres": data.financiering.adres,
                },
                "hypotheek_bedrag": data.hypotheek_bedrag,
                "leningdelen_count": len(data.leningdelen),
                "leningdelen": [
                    {
                        "bedrag": ld.bedrag_box1 + ld.bedrag_box3,
                        "aflosvorm": ld.aflosvorm_display,
                        "rente": ld.werkelijke_rente,
                        "looptijd_mnd": ld.org_lpt,
                    }
                    for ld in data.leningdelen
                ],
            },
        })
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Debug endpoint mislukt: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
