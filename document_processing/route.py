"""Endpoints voor document processing pipeline."""

import logging
import os

import httpx
from fastapi import APIRouter, HTTPException, Request

from document_processing.pipeline_v2 import process_document_v2
from document_processing.smart_mapper import generate_smart_import, apply_smart_import, get_prefill_data
from document_processing.schemas import ProcessRequest, ApplyImportsRequest

logger = logging.getLogger("nat-api.doc-processing")

router = APIRouter(prefix="/doc-processing", tags=["document-processing"])

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
    result = await process_document_v2(document_id, force=body.force)

    if result.get("status") == "error":
        raise HTTPException(500, f"Verwerking mislukt: {result.get('error', 'onbekend')}")

    return result


@router.post("/{dossier_id}/process-all")
async def process_all_pending(dossier_id: str, request: Request):
    """Scan _inbox, registreer nieuwe bestanden, en verwerk alles."""
    token = _extract_token(request)
    headers = _sb_headers(token)

    # Stap 1: Haal dossier op voor SharePoint pad
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/dossiers",
            headers=headers,
            params={"select": "id,dossiernummer,klant_naam,sharepoint_url", "id": f"eq.{dossier_id}"},
        )
        resp.raise_for_status()
        dossiers = resp.json()

    if not dossiers:
        raise HTTPException(404, "Dossier niet gevonden")

    dossier = dossiers[0]
    dossiernummer = dossier.get("dossiernummer", "")

    # Stap 2: Scan _inbox op SharePoint
    from sharepoint import client as sp_client
    inbox_pad = None
    sharepoint_url = dossier.get("sharepoint_url", "")
    if sharepoint_url:
        # Haal mapnaam uit sharepoint_url: .../1.Klanten/{mapnaam}
        # URL decode en extract het pad
        import re
        from urllib.parse import unquote
        decoded = unquote(sharepoint_url)
        match = re.search(r"1\.Klanten/([^?]+)", decoded)
        if match:
            mapnaam = match.group(1).rstrip("/")
            inbox_pad = f"{sp_client.SHAREPOINT_KLANTEN_ROOT}/{mapnaam}/_inbox"
            logger.info("_inbox pad: %s", inbox_pad)

    inbox_bestanden = []
    if inbox_pad:
        try:
            items = await sp_client.list_folder(inbox_pad)
            inbox_bestanden = [
                item for item in items
                if item.get("file") and not item.get("folder")
            ]
            logger.info("_inbox scan: %d bestanden gevonden", len(inbox_bestanden))
        except Exception as e:
            logger.warning("_inbox scan mislukt (map bestaat mogelijk niet): %s", e)

    # Stap 3: Registreer nieuwe bestanden in documents tabel
    registered = 0
    for item in inbox_bestanden:
        bestandsnaam = item.get("name", "")
        sp_item_id = item.get("id", "")
        size = item.get("size", 0)
        mime = item.get("file", {}).get("mimeType", "application/octet-stream")
        web_url = item.get("webUrl", "")

        # Check of bestand al geregistreerd is
        async with httpx.AsyncClient(timeout=10) as client:
            check = await client.get(
                f"{SUPABASE_URL}/rest/v1/documents",
                headers=headers,
                params={
                    "select": "id",
                    "dossier_id": f"eq.{dossier_id}",
                    "bestandsnaam": f"eq.{bestandsnaam}",
                },
            )
            if check.json():
                continue  # Al geregistreerd

        # Registreer in Supabase
        doc_record = {
            "dossier_id": dossier_id,
            "bestandsnaam": bestandsnaam,
            "sharepoint_pad": f"{inbox_pad}/{bestandsnaam}",
            "bron": "upload",
            "status": "pending",
            "mime_type": mime,
            "bestandsgrootte": size,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            ins = await client.post(
                f"{SUPABASE_URL}/rest/v1/documents",
                headers={**headers, "Prefer": "return=representation"},
                json=doc_record,
            )
            if ins.status_code in (200, 201):
                registered += 1

    logger.info("_inbox: %d nieuwe bestanden geregistreerd", registered)

    # Stap 4: Haal alle pending documenten op
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/documents",
            headers=headers,
            params={
                "select": "id",
                "dossier_id": f"eq.{dossier_id}",
                "status": "eq.pending",
            },
        )
        resp.raise_for_status()
        docs = resp.json()

    if not docs:
        return {"message": "Geen documenten gevonden in _inbox", "registered": registered, "processed": 0}

    import asyncio
    from document_processing.pipeline_v2 import _run_dossier_analysis, _build_dossier_context

    # Parallelle verwerking: max 4 tegelijk, stap 3 alleen aan het einde
    semaphore = asyncio.Semaphore(4)

    async def process_with_limit(doc_id: str) -> dict:
        async with semaphore:
            return await process_document_v2(doc_id, skip_step3=True)

    tasks = [process_with_limit(doc["id"]) for doc in docs]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Converteer exceptions naar error dicts
    clean_results = []
    for r in results:
        if isinstance(r, Exception):
            clean_results.append({"status": "error", "error": str(r)})
        else:
            clean_results.append(r)

    succeeded = sum(1 for r in clean_results if r.get("status") == "extracted")
    failed = sum(1 for r in clean_results if r.get("status") == "error")

    # IBL herberekening: als UWV eerder dan loonstrook verwerkt is, was pensioenbijdrage 0
    ibl_rerun = None
    try:
        from document_processing.pipeline_v2 import _find_pensioen_bijdrage, _sb_headers as _pipe_headers
        from document_processing import ibl_runner

        SUPABASE_URL_PIPE = os.environ.get("SUPABASE_URL", "")
        pipe_h = {"apikey": SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY}", "Content-Type": "application/json"}

        # Zoek IBL resultaten met pensioenbijdrage=0
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{SUPABASE_URL_PIPE}/rest/v1/extracted_fields",
                headers=pipe_h,
                params={
                    "select": "id,persoon,fields",
                    "dossier_id": f"eq.{dossier_id}",
                    "sectie": "eq.inkomen_ibl",
                },
            )
            resp.raise_for_status()
            ibl_rows = resp.json()

        for ibl_row in ibl_rows:
            fields = ibl_row.get("fields", {})
            pensioen_used = fields.get("maandelijksePensioenbijdrage", 0)
            if pensioen_used == 0 or pensioen_used == 0.0:
                persoon = ibl_row.get("persoon", "aanvrager")
                # Check of er nu wél een pensioenbijdrage beschikbaar is
                pensioen = await _find_pensioen_bijdrage(dossier_id, persoon)
                if pensioen > 0:
                    logger.info("IBL herberekening: pensioenbijdrage %.2f gevonden voor %s (was 0)", pensioen, persoon)
                    # Zoek het UWV document
                    async with httpx.AsyncClient(timeout=10) as client:
                        resp = await client.get(
                            f"{SUPABASE_URL_PIPE}/rest/v1/documents",
                            headers=pipe_h,
                            params={
                                "select": "id",
                                "dossier_id": f"eq.{dossier_id}",
                                "document_type": "eq.uwv_verzekeringsbericht",
                                "persoon": f"eq.{persoon}",
                                "limit": "1",
                            },
                        )
                        resp.raise_for_status()
                        uwv_docs = resp.json()

                    if uwv_docs:
                        # Herverwerk UWV met force
                        rerun_result = await process_document_v2(uwv_docs[0]["id"], force=True, skip_step3=True)
                        ibl_rerun = f"herberekend voor {persoon} met pensioen {pensioen}"
                        logger.info("IBL herberekening voltooid: %s", ibl_rerun)
    except Exception as e:
        logger.warning("IBL herberekening check mislukt: %s", e)

    # Stap 3: dossier-analyse één keer aan het einde
    step3_result = None
    try:
        # Haal dossier op voor context
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/dossiers",
                headers=headers,
                params={"select": "id,dossiernummer,klant_naam,klant_contact_gegevens,sharepoint_url", "id": f"eq.{dossier_id}"},
            )
            resp.raise_for_status()
            dossier_rows = resp.json()

        if dossier_rows:
            context = _build_dossier_context(dossier_rows[0])
            await _run_dossier_analysis(dossier_id, context)
            step3_result = "completed"
    except Exception as e:
        logger.error("Stap 3 (einde) mislukt: %s", e)
        step3_result = f"error: {e}"

    # Stap 4: import cache vullen (op achtergrond, niet-blokkerend)
    cache_result = None
    try:
        from document_processing.smart_mapper import populate_cache
        await populate_cache(dossier_id)
        cache_result = "completed"
    except Exception as e:
        logger.warning("Import cache vullen mislukt: %s", e)
        cache_result = f"error: {e}"

    return {
        "processed": len(clean_results),
        "succeeded": succeeded,
        "failed": failed,
        "ibl_rerun": ibl_rerun,
        "step3": step3_result,
        "import_cache": cache_result,
        "results": clean_results,
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


@router.get("/{dossier_id}/available-imports")
async def available_imports(
    dossier_id: str,
    request: Request,
    target_id: str = None,
    context: str = "berekening",
    refresh: bool = False,
):
    """Haal beschikbare imports op. Leest uit cache (instant), tenzij refresh=true.

    Query params:
        dossier_id: UUID van het dossier (bron: extracted_fields)
        target_id: UUID van de berekening of aanvraag (vergelijk hiermee)
        context: "berekening" of "aanvraag"
        refresh: true = forceer nieuwe Claude mapping (langzaam, ~10s)
    """
    if context not in ("aanvraag", "berekening"):
        context = "berekening"
    try:
        result = await generate_smart_import(dossier_id, target_id, context, force_refresh=refresh)
        return result
    except Exception as _ex:
        import traceback
        logger.error("Smart import preview mislukt: %s\n%s", _ex, traceback.format_exc())
        raise HTTPException(500, f"Imports ophalen mislukt: {type(_ex).__name__}: {_ex}")


@router.post("/{dossier_id}/apply-imports")
async def apply_imports_endpoint(dossier_id: str, request: Request, body: ApplyImportsRequest = None):
    """Importeer geselecteerde velden naar een aanvraag of berekening.

    Body:
        target_id: UUID van de berekening of aanvraag (bestemming)
        context: "berekening" of "aanvraag"
        selected_targets: lijst van veld-paden (bijv. ["aanvrager.persoon.achternaam"])
    """
    if not body or (not body.selected_targets and not body.check_vragen_answers):
        raise HTTPException(400, "Geen velden of check_vragen antwoorden geselecteerd")
    if body.context not in ("aanvraag", "berekening"):
        raise HTTPException(400, "context moet 'aanvraag' of 'berekening' zijn")

    try:
        # Converteer CheckVraagAnswer objecten naar dicts
        answers = [{"pad": a.pad, "waarde": a.waarde} for a in body.check_vragen_answers]

        result = await apply_smart_import(
            dossier_id=dossier_id,
            target_id=body.target_id,
            context=body.context,
            selected_pads=body.selected_targets,
            check_vragen_answers=answers if answers else None,
        )
        return result
    except ValueError as _ex:
        raise HTTPException(404, str(_ex))
    except Exception as _ex:
        logger.error("Smart import apply mislukt: %s", _ex)
        raise HTTPException(500, f"Importeren mislukt: {_ex}")


@router.post("/{dossier_id}/rerun-analysis")
async def rerun_analysis(dossier_id: str, request: Request):
    """Draai stap 3 (dossier-analyse) opnieuw, zonder documenten te herverwerken.

    Handig als stap 3 prompt is bijgewerkt (bijv. beslissingen toegevoegd)
    maar documenten al verwerkt zijn.
    """
    from document_processing.pipeline_v2 import _run_dossier_analysis, _build_dossier_context

    token = _extract_token(request)
    headers = _sb_headers(token)

    # Haal dossier op
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/dossiers",
            headers=headers,
            params={"select": "id,dossiernummer,klant_naam,klant_contact_gegevens,sharepoint_url", "id": f"eq.{dossier_id}"},
        )
        resp.raise_for_status()
        dossiers = resp.json()

    if not dossiers:
        raise HTTPException(404, "Dossier niet gevonden")

    context = _build_dossier_context(dossiers[0])

    try:
        await _run_dossier_analysis(dossier_id, context)
    except Exception as _ex:
        raise HTTPException(500, f"Analyse mislukt: {_ex}")

    # Cache ook opnieuw vullen met Python mapper
    from document_processing.smart_mapper import populate_cache
    await populate_cache(dossier_id)

    return {"status": "completed", "dossier_id": dossier_id}


@router.delete("/{dossier_id}/clear-cache")
async def clear_cache(dossier_id: str, request: Request):
    """Verwijder alle import cache entries voor een dossier."""
    import httpx, os
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.delete(
            f"{url}/rest/v1/import_cache",
            headers=headers,
            params={"dossier_id": f"eq.{dossier_id}"},
        )
    return {"deleted": True, "status": resp.status_code}


@router.get("/{dossier_id}/prefill-aanvraag")
async def prefill_aanvraag(dossier_id: str, request: Request):
    """Haal vooringevulde aanvraag-data op uit de import cache.

    Retourneert merged_data die direct als startdata voor een nieuwe aanvraag
    gebruikt kan worden. Instant als cache gevuld is, anders ~15s (Claude call).

    Response:
        {
            "prefill_data": { ... AanvraagData ... },
            "velden_count": 50,
            "cached": true
        }
    """
    try:
        result = await get_prefill_data(dossier_id)
        return result
    except Exception as _ex:
        import traceback
        logger.error("Prefill aanvraag mislukt: %s\n%s", _ex, traceback.format_exc())
        raise HTTPException(500, f"Prefill ophalen mislukt: {type(_ex).__name__}: {_ex}")
