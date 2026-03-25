"""Endpoints voor document processing pipeline."""

import logging
import os

import httpx
from fastapi import APIRouter, HTTPException, Request

from document_processing.pipeline import process_document
from document_processing.priority_resolver import resolve_all_fields
from document_processing.schemas import ProcessRequest, ApplyToAanvraagRequest

logger = logging.getLogger("nat-api.doc-processing")

router = APIRouter(prefix="/documents", tags=["document-processing"])

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")


def _sb_headers(access_token: str | None = None) -> dict:
    key = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
    token = access_token or SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
    return {
        "apikey": key,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    return auth.replace("Bearer ", "") if auth.startswith("Bearer ") else None


@router.post("/{document_id}/process")
async def process_single(document_id: str, request: Request, body: ProcessRequest = ProcessRequest()):
    """Verwerk één document: OCR → classificatie → extractie.

    Wordt aangeroepen na upload of handmatig voor herverwerking.
    """
    result = await process_document(document_id, force=body.force)

    if result.status == "error":
        raise HTTPException(500, f"Verwerking mislukt: {result.error}")

    return result.model_dump()


@router.post("/{dossier_id}/process-all")
async def process_all_pending(dossier_id: str, request: Request):
    """Verwerk alle pending documenten voor een dossier."""
    token = _extract_token(request)

    # Haal pending documenten op
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/documents",
            headers=_sb_headers(token),
            params={
                "select": "id",
                "dossier_id": f"eq.{dossier_id}",
                "status": "eq.pending",
            },
        )
        resp.raise_for_status()
        docs = resp.json()

    if not docs:
        return {"message": "Geen pending documenten", "processed": 0}

    results = []
    for doc in docs:
        result = await process_document(doc["id"])
        results.append(result.model_dump())

    succeeded = sum(1 for r in results if r["status"] == "extracted")
    failed = sum(1 for r in results if r["status"] == "error")

    return {
        "processed": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }


@router.get("/{dossier_id}/extracted")
async def get_extracted_data(dossier_id: str, request: Request):
    """Haal alle extracties op voor een dossier, met bronvolgorde-resolutie.

    Returns:
        - extractions: alle ruwe extracties per document
        - resolved: de 'winnende' waarde per veld op basis van bronvolgorde
        - conflicts: velden met tegenstrijdige waarden
    """
    token = _extract_token(request)

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/extracted_data",
            headers=_sb_headers(token),
            params={
                "select": "*",
                "dossier_id": f"eq.{dossier_id}",
                "order": "created_at.desc",
            },
        )
        resp.raise_for_status()
        extractions = resp.json()

    # Pas bronvolgorde toe
    resolved = resolve_all_fields(extractions)

    # Splits op: resolved values en conflicts
    conflicts = [r for r in resolved if r.conflicting_values]

    return {
        "extractions": extractions,
        "resolved": [r.model_dump() for r in resolved],
        "conflicts": [r.model_dump() for r in conflicts],
        "total_extractions": len(extractions),
        "total_resolved": len(resolved),
        "total_conflicts": len(conflicts),
    }


@router.post("/{dossier_id}/extracted/{extraction_id}/accept")
async def accept_extraction(dossier_id: str, extraction_id: str, request: Request):
    """Adviseur accepteert een extractie-waarde."""
    token = _extract_token(request)

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.patch(
            f"{SUPABASE_URL}/rest/v1/extracted_data",
            headers={**_sb_headers(token), "Prefer": "return=representation"},
            params={"id": f"eq.{extraction_id}", "dossier_id": f"eq.{dossier_id}"},
            json={"status": "accepted", "reviewed_at": "now()"},
        )
        resp.raise_for_status()
        rows = resp.json()

    if not rows:
        raise HTTPException(404, "Extractie niet gevonden")

    return {"status": "accepted", "extraction_id": extraction_id}


@router.post("/{dossier_id}/extracted/{extraction_id}/reject")
async def reject_extraction(dossier_id: str, extraction_id: str, request: Request):
    """Adviseur verwerpt een extractie-waarde."""
    token = _extract_token(request)

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.patch(
            f"{SUPABASE_URL}/rest/v1/extracted_data",
            headers={**_sb_headers(token), "Prefer": "return=representation"},
            params={"id": f"eq.{extraction_id}", "dossier_id": f"eq.{dossier_id}"},
            json={"status": "rejected", "reviewed_at": "now()"},
        )
        resp.raise_for_status()
        rows = resp.json()

    if not rows:
        raise HTTPException(404, "Extractie niet gevonden")

    return {"status": "rejected", "extraction_id": extraction_id}


@router.post("/{dossier_id}/apply-to-aanvraag")
async def apply_to_aanvraag(dossier_id: str, request: Request, body: ApplyToAanvraagRequest = None):
    """Pas geaccepteerde extracties toe op aanvragen.data JSONB.

    Dit is de stap waarbij extracted_data daadwerkelijk naar de aanvraag gaat.
    Alleen accepted extracties worden toegepast.
    """
    # TODO: Implementeer de mapping van extracted_data velden naar aanvragen.data JSONB
    # Dit vereist de volledige veld-mapping uit document-extractie-mapping.xlsx
    raise HTTPException(501, "Apply-to-aanvraag wordt in een volgende fase gebouwd")
