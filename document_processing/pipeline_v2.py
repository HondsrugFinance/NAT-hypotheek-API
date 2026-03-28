"""Document processing pipeline V2 — 3-stappen extractie.

Flow per document:
  0. Tekst-detectie (PyPDF2 → Vision → Azure DI)
  1. Vrije extractie: "vertel me alles" → document_extractions
  2. Structurering + vergelijking → extracted_fields
  3. Dossier-brede analyse → dossier_analysis

UWV documenten: stap 0 bepaalt pdf_text → IBL-tool direct.
"""

import logging
import os
import time

import httpx

from document_processing import ocr_client, ibl_runner
from document_processing.text_detector import determine_input_method
from document_processing.step1_extract_all import extract_all_vision, extract_all_text
from document_processing.step2_structure import structure_and_compare
from document_processing.step3_dossier_analysis import analyze_dossier
from document_processing.step_combined import process_combined_vision, process_combined_text, SIMPLE_DOCUMENTS
from document_processing.rename_move import build_filename, build_filename_v2, move_from_inbox
from sharepoint import client as sp_client

logger = logging.getLogger("nat-api.pipeline-v2")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")


def _sb_headers(prefer: str | None = None) -> dict:
    key = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
    h = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


async def _sb_get(table: str, params: dict) -> list:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=_sb_headers(), params=params)
        resp.raise_for_status()
        return resp.json()


async def _sb_insert(table: str, data: dict) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=_sb_headers("return=representation"), json=data)
        resp.raise_for_status()
        rows = resp.json()
        return rows[0] if rows else data


async def _sb_update(table: str, params: dict, data: dict) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.patch(f"{SUPABASE_URL}/rest/v1/{table}", headers=_sb_headers(), params=params, json=data)
        if resp.status_code >= 400:
            logger.error("_sb_update FOUT %s: %s %s (params=%s, data_keys=%s)",
                         table, resp.status_code, resp.text[:200], params, list(data.keys()))
        resp.raise_for_status()


async def _sb_upsert(table: str, data: dict) -> dict:
    headers = {**_sb_headers(), "Prefer": "return=representation,resolution=merge-duplicates"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=headers, json=data)
        resp.raise_for_status()
        rows = resp.json()
        return rows[0] if rows else data


def _build_dossier_context(dossier: dict) -> dict:
    contact = dossier.get("klant_contact_gegevens") or {}
    aanvrager = contact.get("aanvrager", {})
    partner = contact.get("partner", {})

    a_naam = f"{aanvrager.get('voornaam', '')} {aanvrager.get('tussenvoegsel', '')} {aanvrager.get('achternaam', '')}".strip()
    p_naam = f"{partner.get('voornaam', '')} {partner.get('tussenvoegsel', '')} {partner.get('achternaam', '')}".strip() if partner else ""

    if not a_naam:
        a_naam = dossier.get("klant_naam", "onbekend")

    return {
        "aanvrager_naam": a_naam,
        "partner_naam": p_naam,
        "aanvrager_achternaam": aanvrager.get("achternaam", ""),
        "partner_achternaam": partner.get("achternaam", "") if partner else "",
    }


def _db_persoon(persoon: str) -> str:
    """Map persoon naar geldige database-waarde (CHECK constraint)."""
    if persoon in ("aanvrager", "partner", "gezamenlijk"):
        return persoon
    if persoon == "ex-partner":
        return "gezamenlijk"  # Ex-partner opgeslagen als gezamenlijk in DB
    return "gezamenlijk"


def _map_categorie(document_type: str) -> str:
    """Map documenttype naar geldige categorie (CHECK constraint)."""
    _type_to_cat = {
        "paspoort": "Identificatie", "id_kaart": "Identificatie",
        "salarisstrook": "Inkomen", "werkgeversverklaring": "Inkomen",
        "uwv_verzekeringsbericht": "Inkomen", "ibl_resultaat": "Inkomen",
        "ib_aangifte": "Inkomen", "jaarrapport": "Inkomen", "ib60": "Inkomen",
        "toekenningsbesluit_uitkering": "Inkomen", "betaalspecificatie_uitkering": "Inkomen",
        "pensioenspecificatie": "Inkomen", "arbeidsmarktscan": "Inkomen",
        "jaaropgave": "Inkomen",
        "kadaster_eigendom": "Woning", "kadaster_hypotheek": "Woning",
        "nhg_toets": "Overig", "toelichting": "Overig",
        "ontruimingsverklaring": "Overig", "rijbewijs": "Identificatie",
        "koopovereenkomst": "Woning", "concept_koopovereenkomst": "Woning",
        "verkoopovereenkomst": "Woning", "verkoopbrochure": "Woning",
        "taxatierapport": "Woning", "verbouwingsspecificatie": "Woning",
        "energielabel": "Woning", "koop_aanneemovereenkomst": "Woning",
        "meerwerkoverzicht": "Woning",
        "hypotheekoverzicht": "Financieel", "bankafschrift": "Financieel",
        "vermogensoverzicht": "Financieel", "leningoverzicht": "Financieel",
        "nota_van_afrekening": "Financieel",
        "echtscheidingsconvenant": "Overig", "beschikking_rechtbank": "Overig",
        "inschrijving_burgerlijke_stand": "Overig", "akte_van_verdeling": "Overig",
        "bkr": "Overig",
    }
    return _type_to_cat.get(document_type, "Overig")


async def process_document_v2(document_id: str, force: bool = False, skip_step3: bool = False) -> dict:
    """Verwerk één document door de 3-stappen pipeline.

    Returns:
        dict met resultaten van alle stappen.
    """
    start = time.monotonic()
    result = {"document_id": document_id, "steps": {}}

    try:
        # Lees document en dossier
        docs = await _sb_get("documents", {"select": "*", "id": f"eq.{document_id}"})
        if not docs:
            raise ValueError(f"Document niet gevonden: {document_id}")
        doc = docs[0]
        dossier_id = doc["dossier_id"]

        if doc["status"] not in ("pending", "processing") and not force:
            return {"document_id": document_id, "status": "skipped", "reason": f"Status is '{doc['status']}'"}

        try:
            await _sb_update("documents", {"id": f"eq.{document_id}"}, {"status": "processing"})
        except Exception as _ex:
            logger.warning("Status update naar 'processing' mislukt: %s", _ex)

        dossiers = await _sb_get("dossiers", {
            "select": "id,dossiernummer,klant_naam,klant_contact_gegevens,sharepoint_url",
            "id": f"eq.{dossier_id}",
        })
        if not dossiers:
            raise ValueError(f"Dossier niet gevonden: {dossier_id}")
        dossier = dossiers[0]
        context = _build_dossier_context(dossier)

        # Download bestand
        sharepoint_pad = doc.get("sharepoint_pad", "")
        if not sharepoint_pad:
            raise ValueError("Document heeft geen sharepoint_pad")
        file_bytes = await sp_client.download_file(sharepoint_pad)
        mime_type = doc.get("mime_type", "application/pdf")

        # === STAP 0: Tekst-detectie ===
        input_method, pdf_text = determine_input_method(file_bytes, mime_type)
        logger.info("Stap 0: input_method=%s, tekst=%s", input_method, "ja" if pdf_text else "nee")

        # === UWV snelroute: detecteer op basis van PDF tekst ===
        # STRENG: alleen echte UWV verzekeringsbericht, niet documenten die "uwv" noemen
        is_uwv = False
        combined_result = None  # Wordt gezet bij gecombineerde stap 1+2
        if pdf_text:
            text_lower = pdf_text.lower()
            # Moet de specifieke UWV header bevatten EN loongegevens met SV-loon
            has_uwv_header = "printversie verzekeringsbericht" in text_lower
            has_loongegevens = "loongegevens" in text_lower and "sv-loon" in text_lower
            if has_uwv_header or has_loongegevens:
                is_uwv = True
                logger.info("UWV snelroute: document herkend via header/loongegevens")

        if is_uwv:
            # Skip stap 1 (Claude) — direct naar IBL-tool
            document_type = "uwv_verzekeringsbericht"
            persoon = "aanvrager"  # Default, wordt later gecorrigeerd
            confidence = 1.0
            classification = {
                "document_type": document_type,
                "categorie": "Inkomen",
                "persoon": _db_persoon(persoon),
                "confidence": confidence,
                "reasoning": "UWV Verzekeringsbericht herkend via PDF tekst (bevat 'uwv' + 'verzekeringsbericht/loongegevens')",
            }
            step1_result = {"classification": classification, "extracted_data": {}}
            input_method = "pdf_text"
            step1_ms = 0

            # Probeer persoon te bepalen uit PDF tekst
            if context.get("partner_naam"):
                partner_achternaam = context.get("partner_achternaam", "").lower()
                aanvrager_achternaam = context.get("aanvrager_achternaam", "").lower()
                if partner_achternaam and partner_achternaam in text_lower:
                    if not aanvrager_achternaam or aanvrager_achternaam not in text_lower:
                        persoon = "partner"
                        classification["persoon"] = persoon

            # Sla classificatie op in document_extractions
            extraction_record = await _sb_insert("document_extractions", {
                "dossier_id": dossier_id,
                "document_id": document_id,
                "document_type": document_type,
                "persoon": _db_persoon(persoon),
                "classification": classification,
                "raw_data": {"uwv_snelroute": True, "tekst_lengte": len(pdf_text)},
                "input_method": input_method,
                "confidence": confidence,
                "duration_ms": 0,
            })

            # Update document record
            categorie = _map_categorie(document_type)
            try:
                await _sb_update("documents", {"id": f"eq.{document_id}"}, {
                    "document_type": document_type,
                    "categorie": categorie,
                    "persoon": _db_persoon(persoon),
                    "status": "classified",
                    "classification_confidence": confidence,
                    "classification_reasoning": classification["reasoning"],
                })
            except Exception as _ex:
                logger.warning("Document status update mislukt: %s", _ex)

            result["steps"]["step1"] = {"classification": classification, "input_method": "uwv_snelroute", "duration_ms": 0}

        else:
            # === STAP 1 (+2): Extractie ===
            step1_start = time.monotonic()
            combined_result = None  # Als gezet: stap 2 kan overgeslagen worden

            # Probeer gecombineerde stap 1+2 (één call) voor alle documenten
            # Na classificatie bepalen we of het simpel genoeg was
            try:
                if input_method == "pdf_text" and pdf_text:
                    combined_result = await process_combined_text(pdf_text, doc["bestandsnaam"], context)
                else:
                    combined_result = await process_combined_vision(file_bytes, mime_type, context)
            except Exception as _ex:
                logger.warning("Gecombineerde stap mislukt: %s — fallback naar apart", _ex)

            if combined_result:
                step1_result = combined_result
                classification = combined_result.get("classification", {})
                document_type = classification.get("document_type", "onbekend")
            else:
                # Fallback: aparte stap 1
                if input_method == "pdf_text" and pdf_text:
                    step1_result = await extract_all_text(pdf_text, doc["bestandsnaam"], context)
                else:
                    step1_result = await extract_all_vision(file_bytes, mime_type, context)

                classification = step1_result.get("classification", {})
                document_type = classification.get("document_type", "onbekend")
            persoon = classification.get("persoon", "gezamenlijk")
            confidence = classification.get("confidence", 0.5)

            # Fallback naar Azure DI als confidence laag
            if confidence < 0.7 and ocr_client.is_configured():
                logger.info("Stap 1: confidence %.2f < 0.7, fallback naar Azure DI", confidence)
                try:
                    ocr_result = await ocr_client.analyze_document(file_bytes, mime_type)
                    ocr_text = ocr_result.get("content", "")
                    if ocr_text:
                        step1_result = await extract_all_text(ocr_text, doc["bestandsnaam"], context)
                        classification = step1_result.get("classification", {})
                        document_type = classification.get("document_type", "onbekend")
                        persoon = classification.get("persoon", "gezamenlijk")
                        confidence = classification.get("confidence", 0.5)
                        input_method = "azure_di"
                except Exception as _ex:
                    logger.warning("Azure DI fallback mislukt: %s", _ex)

            step1_ms = int((time.monotonic() - step1_start) * 1000)

            # Sla stap 1 op in document_extractions
            extraction_record = await _sb_insert("document_extractions", {
                "dossier_id": dossier_id,
                "document_id": document_id,
                "document_type": document_type,
                "persoon": _db_persoon(persoon),
                "classification": classification,
                "raw_data": step1_result.get("extracted_data", {}),
                "input_method": input_method,
                "confidence": confidence,
                "warnings": step1_result.get("extracted_data", {}).get("opvallend", []),
                "duration_ms": step1_ms,
            })

            # Update document record
            try:
                conf_float = float(confidence) if confidence is not None else None
            except (ValueError, TypeError):
                conf_float = None

            VALID_CATEGORIES = {"Identificatie", "Inkomen", "Woning", "Financieel", "Overig"}
            raw_categorie = classification.get("categorie", "Overig")
            categorie = raw_categorie if raw_categorie in VALID_CATEGORIES else _map_categorie(document_type)

            doc_update = {
                "document_type": document_type,
                "categorie": categorie,
                "persoon": _db_persoon(persoon),
                "status": "classified",
                "classification_reasoning": str(classification.get("reasoning", ""))[:500],
            }
            if conf_float is not None:
                doc_update["classification_confidence"] = conf_float

            try:
                await _sb_update("documents", {"id": f"eq.{document_id}"}, doc_update)
            except Exception as _ex:
                logger.error("Document status update mislukt (doorgaan): %s — data: %s", _ex, doc_update)

            result["steps"]["step1"] = {
                "classification": classification,
                "extracted_data": step1_result.get("extracted_data", {}),
                "input_method": input_method,
                "duration_ms": step1_ms,
            }

        # === UWV → IBL-tool route ===
        ibl_result = None
        if document_type == "uwv_verzekeringsbericht":
            logger.info("UWV document → IBL-tool route")
            try:
                pensioen = await _find_pensioen_bijdrage(dossier_id, persoon)
                ibl_results = await ibl_runner.run_ibl(file_bytes, pensioen)

                if ibl_results:
                    totaal = sum(r.get("toetsinkomen", 0) for r in ibl_results)
                    ibl_result = {
                        "toetsinkomen": totaal,
                        "werkgevers": len(ibl_results),
                        "resultaten": ibl_results,
                        "pensioenbijdrage_gebruikt": pensioen,
                    }

                    # Sla IBL op als extracted_fields
                    await _sb_insert("extracted_fields", {
                        "dossier_id": dossier_id,
                        "document_id": document_id,
                        "extraction_id": extraction_record.get("id"),
                        "persoon": _db_persoon(persoon),
                        "sectie": "inkomen_ibl",
                        "fields": {
                            "gemiddeldJaarToetsinkomen": totaal,
                            "berekeningType": ibl_results[0].get("berekening_type", ""),
                            "werkgeverNaam": ibl_results[0].get("werkgever_naam", ""),
                            "maandelijksePensioenbijdrage": pensioen,
                        },
                        "field_confidence": {"gemiddeldJaarToetsinkomen": 1.0, "berekeningType": 1.0},
                        "status": "pending_review",
                    })

                    result["steps"]["ibl"] = ibl_result
                    logger.info("IBL: toetsinkomen EUR %.2f (%d werkgevers)", totaal, len(ibl_results))
            except Exception as _ex:
                logger.error("IBL mislukt: %s", _ex)
                result["steps"]["ibl_error"] = str(_ex)

        # === STAP 2: Structurering (niet voor UWV, die gaat via IBL) ===
        if document_type != "uwv_verzekeringsbericht" and document_type != "onbekend":
            step2_start = time.monotonic()

            # Check of gecombineerde stap al structured_fields heeft
            has_combined_fields = (
                combined_result
                and combined_result.get("structured_fields")
                and document_type in SIMPLE_DOCUMENTS
            )

            try:
                if has_combined_fields:
                    # Simpel document: gebruik structured_fields uit gecombineerde stap
                    step2_result = {
                        "sectie": document_type,
                        "persoon": _db_persoon(persoon),
                        "fields": combined_result["structured_fields"],
                        "field_confidence": combined_result.get("field_confidence", {}),
                        "waarschuwingen": combined_result.get("waarschuwingen", []),
                        "inconsistenties": [],
                        "suggesties": [],
                    }
                    logger.info("Stap 2 overgeslagen: %s is simpel document (gecombineerd)", document_type)
                else:
                    # Complex document: aparte stap 2
                    existing = await _get_existing_fields(dossier_id, persoon)
                    step2_result = await structure_and_compare(
                        step1_result.get("extracted_data", {}),
                        document_type,
                        persoon,
                        existing,
                        context,
                    )

                step2_ms = int((time.monotonic() - step2_start) * 1000)

                # Sla op in extracted_fields
                await _sb_insert("extracted_fields", {
                    "dossier_id": dossier_id,
                    "document_id": document_id,
                    "extraction_id": extraction_record.get("id"),
                    "persoon": _db_persoon(persoon),
                    "sectie": step2_result.get("sectie", document_type),
                    "fields": step2_result.get("fields", {}),
                    "field_confidence": step2_result.get("field_confidence", {}),
                    "status": "pending_review",
                })

                result["steps"]["step2"] = {
                    "fields": step2_result.get("fields", {}),
                    "inconsistenties": step2_result.get("inconsistenties", []),
                    "waarschuwingen": step2_result.get("waarschuwingen", []),
                    "suggesties": step2_result.get("suggesties", []),
                    "duration_ms": step2_ms,
                }
            except Exception as _ex:
                logger.error("Stap 2 mislukt: %s", _ex)
                result["steps"]["step2_error"] = str(_ex)

        # === Hernoem en verplaats ===
        new_filename = None
        new_pad = None
        if document_type != "onbekend":
            heeft_partner = bool(context.get("partner_naam"))
            ext = os.path.splitext(doc["bestandsnaam"])[1] or ".pdf"

            # Verzamel extractie data voor bestandsnaam
            extraction_data = {}
            if step1_result and step1_result.get("extracted_data"):
                extraction_data = step1_result["extracted_data"]
            if combined_result and combined_result.get("structured_fields"):
                extraction_data.update(combined_result["structured_fields"])

            new_filename = build_filename_v2(
                document_type, persoon, heeft_partner,
                extraction_data, context, ext,
            )

            if "/_inbox/" in sharepoint_pad:
                hoofdpad = sharepoint_pad.split("/_inbox/")[0]
                try:
                    move_result = await move_from_inbox(hoofdpad, doc["bestandsnaam"], new_filename)
                    new_pad = move_result.get("sharepoint_pad", "")
                except Exception as _ex:
                    logger.warning("Verplaatsen mislukt: %s", _ex)

        # === Update document status ===
        final_updates = {"status": "extracted"}
        if new_filename:
            final_updates["original_bestandsnaam"] = doc["bestandsnaam"]
        if new_pad:
            final_updates["sharepoint_pad"] = new_pad
            final_updates["bestandsnaam"] = new_filename

        duration_ms = int((time.monotonic() - start) * 1000)
        final_updates["processing_duration_ms"] = duration_ms
        try:
            await _sb_update("documents", {"id": f"eq.{document_id}"}, final_updates)
        except Exception as _ex:
            logger.error("Final document update mislukt (doorgaan): %s", _ex)

        result["status"] = "extracted"
        result["document_type"] = document_type
        result["persoon"] = persoon
        result["new_filename"] = new_filename
        result["duration_ms"] = duration_ms

        # === STAP 3: Dossier-analyse (optioneel, skip bij batch) ===
        if not skip_step3:
            try:
                await _run_dossier_analysis(dossier_id, context)
                result["steps"]["step3"] = "completed"
            except Exception as _ex:
                logger.error("Stap 3 mislukt: %s", _ex)
        else:
            result["steps"]["step3"] = "skipped (batch)"

        logger.info("Pipeline V2 voltooid: %s → %s (%dms)", doc["bestandsnaam"], document_type, duration_ms)
        return result

    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        error_msg = str(exc)
        logger.error("Pipeline V2 fout: %s", error_msg)

        try:
            await _sb_update("documents", {"id": f"eq.{document_id}"}, {
                "status": "error",
                "processing_error": error_msg[:500],
                "processing_duration_ms": duration_ms,
            })
        except Exception:
            pass

        return {"document_id": document_id, "status": "error", "error": error_msg, "duration_ms": duration_ms}


async def _find_pensioen_bijdrage(dossier_id: str, persoon: str) -> float:
    """Zoek pensioenbijdrage uit eerder geëxtraheerde salarisstrook."""
    try:
        rows = await _sb_get("extracted_fields", {
            "select": "fields",
            "dossier_id": f"eq.{dossier_id}",
            "persoon": f"eq.{persoon}",
            "sectie": "eq.salarisstrook",
            "order": "created_at.desc",
            "limit": "1",
        })
        if rows:
            fields = rows[0].get("fields", {})
            pensioen_keys = [
                "maandelijksePensioenbijdrage", "pensioenbijdrage",
                "eigen_bijdrage_pensioen", "eigen_bijdrage_pensioen_bedrag",
                "pensioen_eigen_bijdrage_bedrag", "pensioenpremie",
            ]
            for key in pensioen_keys:
                if key in fields and fields[key]:
                    try:
                        val = float(fields[key])
                        if val > 0:
                            logger.info("Pensioenbijdrage gevonden: %s = %.2f", key, val)
                            return val
                    except (ValueError, TypeError):
                        continue

        # Fallback: zoek in document_extractions raw_data
        rows2 = await _sb_get("document_extractions", {
            "select": "raw_data",
            "dossier_id": f"eq.{dossier_id}",
            "persoon": f"eq.{persoon}",
            "document_type": "eq.salarisstrook",
            "order": "created_at.desc",
            "limit": "1",
        })
        if rows2:
            raw = rows2[0].get("raw_data", {})
            financieel = raw.get("financieel", {})
            for key in ["eigen_bijdrage_pensioen", "pensioenpremie", "premie_pensioen", "pensioen"]:
                if key in financieel:
                    try:
                        val = float(str(financieel[key]).replace(",", "."))
                        if val > 0:
                            return val
                    except (ValueError, TypeError):
                        continue
    except Exception as _ex:
        logger.warning("Pensioenbijdrage ophalen mislukt: %s", _ex)

    return 0.0


async def _get_existing_fields(dossier_id: str, persoon: str) -> dict:
    """Haal alle bestaande gestructureerde velden op voor een dossier/persoon."""
    try:
        rows = await _sb_get("extracted_fields", {
            "select": "sectie,fields",
            "dossier_id": f"eq.{dossier_id}",
            "persoon": f"eq.{persoon}",
            "status": "in.(pending_review,accepted,imported)",
        })
        combined = {}
        for row in rows:
            sectie = row.get("sectie", "")
            fields = row.get("fields", {})
            if sectie not in combined:
                combined[sectie] = {}
            combined[sectie].update(fields)
        return combined
    except Exception:
        return {}


async def _run_dossier_analysis(dossier_id: str, context: dict) -> None:
    """Draai stap 3: dossier-brede analyse."""
    # Haal alle extracties op
    all_extractions = await _sb_get("document_extractions", {
        "select": "document_type,persoon,raw_data",
        "dossier_id": f"eq.{dossier_id}",
    })

    # Haal alle gestructureerde velden op
    all_fields = await _sb_get("extracted_fields", {
        "select": "sectie,persoon,fields",
        "dossier_id": f"eq.{dossier_id}",
    })

    step3_start = time.monotonic()
    analysis = await analyze_dossier(all_extractions, all_fields, context)
    step3_ms = int((time.monotonic() - step3_start) * 1000)

    # Upsert in dossier_analysis (één rij per dossier, wordt overschreven)
    existing = await _sb_get("dossier_analysis", {
        "select": "id",
        "dossier_id": f"eq.{dossier_id}",
    })

    record = {
        "dossier_id": dossier_id,
        "compleetheid": analysis.get("compleetheid", {}),
        "inconsistenties": analysis.get("inconsistenties", []),
        "suggesties": analysis.get("suggesties", []),
        "ontbrekende_documenten": analysis.get("compleetheid", {}).get("ontbrekend", []),
        "samenvatting": analysis.get("samenvatting", ""),
        "inkomen_analyse": analysis.get("inkomen_analyse", {}),
        "documenten_verwerkt": len(all_extractions),
        "confidence": analysis.get("confidence", 0),
        "duration_ms": step3_ms,
    }

    if existing:
        await _sb_update("dossier_analysis", {"id": f"eq.{existing[0]['id']}"}, record)
    else:
        await _sb_insert("dossier_analysis", record)

    logger.info("Stap 3: dossier-analyse voltooid (%dms, %d docs)", step3_ms, len(all_extractions))
