"""Document processing pipeline — orchestratie van OCR → classificatie → extractie."""

import logging
import os
import time

import httpx

from document_processing import ocr_client, classifier, extractor, ibl_runner
from document_processing.name_matcher import match_persoon
from document_processing.rename_move import build_filename, move_from_inbox, archive_existing
from document_processing.schemas import ProcessingResult, ExtractionResult
from sharepoint import client as sp_client

logger = logging.getLogger("nat-api.pipeline")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")


def _sb_headers(access_token: str | None = None) -> dict:
    """Bouw Supabase headers (hergebruik patroon uit supabase_client.py)."""
    key = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
    token = access_token or SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
    return {
        "apikey": key,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


async def _read_document(document_id: str) -> dict:
    """Lees document record uit Supabase."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/documents",
            headers=_sb_headers(),
            params={"select": "*", "id": f"eq.{document_id}"},
        )
        resp.raise_for_status()
        rows = resp.json()
    if not rows:
        raise ValueError(f"Document niet gevonden: {document_id}")
    return rows[0]


async def _read_dossier(dossier_id: str) -> dict:
    """Lees dossier record uit Supabase."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/dossiers",
            headers=_sb_headers(),
            params={
                "select": "id,dossiernummer,klant_naam,klant_contact_gegevens,sharepoint_url",
                "id": f"eq.{dossier_id}",
            },
        )
        resp.raise_for_status()
        rows = resp.json()
    if not rows:
        raise ValueError(f"Dossier niet gevonden: {dossier_id}")
    return rows[0]


async def _update_document(document_id: str, updates: dict) -> None:
    """Update document record in Supabase."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.patch(
            f"{SUPABASE_URL}/rest/v1/documents",
            headers=_sb_headers(),
            params={"id": f"eq.{document_id}"},
            json=updates,
        )
        resp.raise_for_status()


async def _insert_extracted_data(data: dict) -> dict:
    """Insert een rij in extracted_data."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/rest/v1/extracted_data",
            headers=_sb_headers(),
            json=data,
        )
        resp.raise_for_status()
        rows = resp.json()
        return rows[0] if rows else data


def _build_dossier_context(dossier: dict) -> dict:
    """Bouw dossier context voor classificatie/extractie prompts."""
    contact = dossier.get("klant_contact_gegevens") or {}
    aanvrager = contact.get("aanvrager", {})
    partner = contact.get("partner", {})

    aanvrager_naam = f"{aanvrager.get('voornaam', '')} {aanvrager.get('tussenvoegsel', '')} {aanvrager.get('achternaam', '')}".strip()
    partner_naam = f"{partner.get('voornaam', '')} {partner.get('tussenvoegsel', '')} {partner.get('achternaam', '')}".strip() if partner else ""

    if not aanvrager_naam:
        aanvrager_naam = dossier.get("klant_naam", "onbekend")

    return {
        "aanvrager_naam": aanvrager_naam,
        "partner_naam": partner_naam,
        "aanvrager_achternaam": aanvrager.get("achternaam", ""),
        "klanttype": "",  # TODO: uit aanvragen.data.doelstelling halen
    }


async def process_document(document_id: str, force: bool = False) -> ProcessingResult:
    """Verwerk één document door de volledige pipeline.

    Stappen:
    1. Lees document + dossier uit Supabase
    2. Download bestand van SharePoint (_inbox)
    3. OCR via Azure Document Intelligence
    4. Classificatie via Claude API
    5. Extractie via Claude API
    6. Als UWV: draai IBL-tool
    7. Hernoem + verplaats naar hoofdmap
    8. Sla resultaten op in Supabase

    Args:
        document_id: UUID van het document in de documents tabel
        force: Herverwerk ook als status niet "pending" is

    Returns:
        ProcessingResult met alle resultaten
    """
    start = time.monotonic()

    try:
        # 1. Lees document en dossier
        doc = await _read_document(document_id)
        dossier_id = doc["dossier_id"]

        if doc["status"] not in ("pending", "processing") and not force:
            return ProcessingResult(
                document_id=document_id,
                status="skipped",
                error=f"Document heeft al status '{doc['status']}'. Gebruik force=true om te herverwerken.",
            )

        # Markeer als processing
        await _update_document(document_id, {"status": "processing"})

        dossier = await _read_dossier(dossier_id)
        context = _build_dossier_context(dossier)

        # 2. Download bestand van SharePoint
        sharepoint_pad = doc.get("sharepoint_pad", "")
        if not sharepoint_pad:
            raise ValueError("Document heeft geen sharepoint_pad")

        file_bytes = await sp_client.download_file(sharepoint_pad)
        mime_type = doc.get("mime_type", "application/pdf")

        # 3 + 4. Classificatie — Claude Vision direct (standaard)
        #         Azure DI OCR als fallback bij lage confidence
        classification = None
        ocr_text = ""
        used_azure_fallback = False

        if classifier.is_configured():
            # Stap 1: Probeer Claude Vision direct
            try:
                classification = await classifier.classify_document_vision(
                    file_bytes, mime_type, doc["bestandsnaam"], context
                )
                logger.info("Claude Vision classificatie: %s (confidence=%.2f)",
                            classification.document_type, classification.confidence)
            except Exception as e:
                logger.warning("Claude Vision mislukt: %s — probeer Azure DI fallback", e)

            # Stap 2: Fallback naar Azure DI als confidence laag of type onbekend
            needs_fallback = (
                classification is None
                or classification.confidence < 0.7
                or classification.document_type == "onbekend"
            )

            if needs_fallback and ocr_client.is_configured():
                logger.info("Fallback naar Azure DI OCR (confidence=%.2f, type=%s)",
                            classification.confidence if classification else 0,
                            classification.document_type if classification else "geen")
                used_azure_fallback = True

                try:
                    ocr_result = await ocr_client.analyze_document(file_bytes, mime_type)
                    ocr_text = ocr_result.get("content", "")

                    await _update_document(document_id, {
                        "ocr_text": ocr_text[:50000],
                        "ocr_page_count": ocr_result.get("page_count", 0),
                    })

                    # Herclassificeer met schone OCR-tekst
                    if ocr_text:
                        classification = await classifier.classify_document(
                            ocr_text, doc["bestandsnaam"], context
                        )
                        logger.info("Azure DI fallback classificatie: %s (confidence=%.2f)",
                                    classification.document_type, classification.confidence)
                except Exception as e:
                    logger.warning("Azure DI fallback ook mislukt: %s", e)

            # Sla classificatie op
            if classification:
                await _update_document(document_id, {
                    "document_type": classification.document_type,
                    "categorie": classification.categorie,
                    "persoon": classification.persoon,
                    "status": "classified",
                    "classification_confidence": classification.confidence,
                    "classification_reasoning": classification.reasoning,
                })
        else:
            logger.warning("Claude niet geconfigureerd — skip classificatie")

        # 5. Extractie — UWV Verzekeringsbericht: eigen parser (IBL-tool)
        #    Andere documenten: Claude API extractie
        extraction = None

        if classification and classification.document_type == "uwv_verzekeringsbericht":
            # UWV: gebruik IBL-tool direct (eigen PyPDF2 parser, leest alle pagina's)
            logger.info("UWV document → IBL-tool route (bypass Azure DI extractie)")
            try:
                pensioen = await _find_pensioen_bijdrage(dossier_id, classification.persoon)
                ibl_results = await ibl_runner.run_ibl(file_bytes, pensioen)

                # Sla IBL resultaten op
                for ibl_r in ibl_results:
                    await _insert_extracted_data({
                        "dossier_id": dossier_id,
                        "document_id": document_id,
                        "extract_type": "ibl_toetsinkomen",
                        "persoon": classification.persoon,
                        "raw_values": ibl_r,
                        "computed_values": {
                            "gemiddeldJaarToetsinkomen": ibl_r.get("toetsinkomen", 0),
                            "berekening_type": ibl_r.get("berekening_type", ""),
                            "werkgever_naam": ibl_r.get("werkgever_naam", ""),
                        },
                        "confidence": 1.0,  # IBL is een exacte berekening
                        "status": "pending_review",
                    })

                # Bouw extraction result voor response
                totaal = sum(r.get("toetsinkomen", 0) for r in ibl_results)
                extraction = ExtractionResult(
                    raw_values={r.get("werkgever_naam", f"werkgever_{i}"): r for i, r in enumerate(ibl_results)},
                    computed_values={
                        "gemiddeldJaarToetsinkomen": totaal,
                        "aantalWerkgevers": len(ibl_results),
                        "resultaten": ibl_results,
                    },
                    confidence=1.0,
                    warnings=[
                        f"IBL toetsinkomen: EUR {totaal:,.2f} ({len(ibl_results)} werkgever(s))",
                        f"Pensioenbijdrage gebruikt: EUR {pensioen:.2f}/mnd",
                    ] + [w for r in ibl_results for w in r.get("waarschuwingen", [])],
                )

                logger.info("IBL berekening succesvol: %d resultaten, totaal EUR %.2f", len(ibl_results), totaal)
            except Exception as e:
                logger.error("IBL berekening mislukt: %s", e)
                extraction = ExtractionResult(
                    raw_values={},
                    computed_values={},
                    confidence=0.0,
                    warnings=[f"IBL berekening mislukt: {e}"],
                )

        elif classifier.is_configured() and classification and classification.document_type != "onbekend":
            # Alle andere documenten: Claude API extractie
            if used_azure_fallback and ocr_text:
                # Azure DI was nodig → gebruik schone OCR-tekst
                extraction = await extractor.extract_fields(
                    ocr_text, classification.document_type, context
                )
            else:
                # Claude Vision direct → stuur document als base64
                extraction = await extractor.extract_fields_vision(
                    file_bytes, mime_type, classification.document_type, context
                )

            # Sla op in extracted_data
            await _insert_extracted_data({
                "dossier_id": dossier_id,
                "document_id": document_id,
                "extract_type": classification.document_type,
                "persoon": classification.persoon,
                "raw_values": extraction.raw_values,
                "computed_values": extraction.computed_values,
                "confidence": extraction.confidence,
                "notes": "; ".join(extraction.warnings) if extraction.warnings else None,
                "status": "pending_review",
            })

        # 7. Hernoem en verplaats
        new_filename = None
        new_pad = None

        if classification and classification.document_type != "onbekend":
            dossiernummer = dossier.get("dossiernummer", "0000-0000")
            achternaam = context.get("aanvrager_achternaam", "Onbekend")
            if classification.persoon == "partner" and context.get("partner_naam"):
                # Gebruik achternaam partner
                partner_contact = (dossier.get("klant_contact_gegevens") or {}).get("partner", {})
                achternaam = partner_contact.get("achternaam", achternaam)

            ext = os.path.splitext(doc["bestandsnaam"])[1] or ".pdf"
            new_filename = build_filename(dossiernummer, classification.document_type, achternaam, ext)

            # Bepaal hoofdpad
            sharepoint_url = dossier.get("sharepoint_url", "")
            if sharepoint_url:
                # Haal hoofdpad uit sharepoint_pad: alles voor /_inbox/
                if "/_inbox/" in sharepoint_pad:
                    hoofdpad = sharepoint_pad.split("/_inbox/")[0]
                else:
                    # Fallback: bouw pad op
                    hoofdpad = f"{sp_client.SHAREPOINT_KLANTEN_ROOT}/{dossiernummer}"

                try:
                    move_result = await move_from_inbox(
                        hoofdpad, doc["bestandsnaam"], new_filename
                    )
                    new_pad = move_result.get("sharepoint_pad", "")
                except Exception as e:
                    logger.warning("Verplaatsen mislukt: %s (document blijft in _inbox)", e)

        # 8. Update document status
        final_updates = {"status": "extracted"}
        if new_filename:
            final_updates["original_bestandsnaam"] = doc["bestandsnaam"]
        if new_pad:
            final_updates["sharepoint_pad"] = new_pad
            final_updates["bestandsnaam"] = new_filename

        duration_ms = int((time.monotonic() - start) * 1000)
        final_updates["processing_duration_ms"] = duration_ms

        await _update_document(document_id, final_updates)

        logger.info("Pipeline voltooid voor %s: %s → %s (%dms)",
                     document_id, doc["bestandsnaam"],
                     classification.document_type if classification else "onbekend",
                     duration_ms)

        return ProcessingResult(
            document_id=document_id,
            status="extracted",
            classification=classification,
            extraction=extraction,
            new_filename=new_filename,
            new_sharepoint_pad=new_pad,
            duration_ms=duration_ms,
        )

    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.error("Pipeline fout voor %s: %s", document_id, e)

        try:
            await _update_document(document_id, {
                "status": "error",
                "processing_error": str(e)[:500],
                "processing_duration_ms": duration_ms,
            })
        except Exception:
            pass

        return ProcessingResult(
            document_id=document_id,
            status="error",
            error=str(e),
            duration_ms=duration_ms,
        )


async def _find_pensioen_bijdrage(dossier_id: str, persoon: str) -> float:
    """Zoek eigen bijdrage pensioen uit eerder geëxtraheerde salarisstrook."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/extracted_data",
                headers=_sb_headers(),
                params={
                    "select": "computed_values",
                    "dossier_id": f"eq.{dossier_id}",
                    "extract_type": "eq.salarisstrook",
                    "persoon": f"eq.{persoon}",
                    "order": "created_at.desc",
                    "limit": "1",
                },
            )
            resp.raise_for_status()
            rows = resp.json()

        if rows:
            values = rows[0].get("computed_values", {})
            # Zoek naar pensioenbijdrage veld (verschillende mogelijke namen)
            for key in ["maandelijksePensioenbijdrage", "pensioenbijdrage", "eigen_bijdrage_pensioen"]:
                if key in values and values[key]:
                    return float(values[key])
    except Exception as e:
        logger.warning("Pensioenbijdrage ophalen mislukt: %s (default 0)", e)

    return 0.0
