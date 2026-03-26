"""Document classificatie via Claude API — Vision (direct) of tekst-modus."""

import base64
import json
import logging
import os

import httpx

from document_processing.schemas import ClassificationResult

logger = logging.getLogger("nat-api.classifier")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

# Laad document types config
_doc_types_cache: dict | None = None


def _load_document_types() -> dict:
    global _doc_types_cache
    if _doc_types_cache is None:
        config_path = os.path.join(os.path.dirname(__file__), "..", "config", "document_types.json")
        with open(config_path, encoding="utf-8") as f:
            _doc_types_cache = json.load(f)
    return _doc_types_cache


def is_configured() -> bool:
    return bool(ANTHROPIC_API_KEY)


def _build_classification_prompt(ocr_text: str, bestandsnaam: str, dossier_context: dict) -> str:
    """Bouw de classificatie-prompt op basis van OCR tekst en dossiercontext."""
    doc_types = _load_document_types()

    # Bouw documenttype-lijst voor de prompt
    type_descriptions = []
    for key, info in doc_types.items():
        desc = info.get("description", key)
        keywords = ", ".join(info.get("keywords", []))
        category = info.get("category", "Overig")
        type_descriptions.append(f'- "{key}": {desc} (categorie: {category}, keywords: {keywords})')

    types_text = "\n".join(type_descriptions)

    aanvrager = dossier_context.get("aanvrager_naam", "onbekend")
    partner = dossier_context.get("partner_naam", "")
    klanttype = dossier_context.get("klanttype", "onbekend")

    partner_text = f"\nPartner: {partner}" if partner else "\nGeen partner bekend."

    return f"""Je bent een documentclassificatie-expert voor hypotheekadvies in Nederland.

Analyseer de volgende OCR-tekst uit een document en bepaal:
1. Wat voor type document dit is
2. Bij welke categorie het hoort
3. Of het bij de aanvrager, partner of gezamenlijk hoort

## Dossiercontext
Aanvrager: {aanvrager}{partner_text}
Klanttype: {klanttype}
Bestandsnaam: {bestandsnaam}

## Beschikbare documenttypen
{types_text}

## OCR-tekst (eerste 4000 tekens)
{ocr_text[:4000]}

## Instructies
- Kies het best passende documenttype uit de lijst hierboven
- Als het document niet matcht met een bekend type, gebruik "onbekend"
- Bepaal 'persoon' op basis van de naam in het document vs. de dossiercontext
  - Als de naam op het document matcht met de aanvrager → "aanvrager"
  - Als de naam matcht met de partner → "partner"
  - Als het een gezamenlijk document is (bijv. koopovereenkomst met beide namen) → "gezamenlijk"
  - Let op gehuwde namen: "Slinger-Aap" kan matchen op achternaam "Slinger" (aanvrager) of "Aap" (partner)
- Geef een confidence score (0.0 - 1.0)

Antwoord in exact dit JSON formaat:
{{"document_type": "...", "categorie": "...", "persoon": "...", "confidence": 0.95, "reasoning": "..."}}"""


async def classify_document(
    ocr_text: str,
    bestandsnaam: str,
    dossier_context: dict,
) -> ClassificationResult:
    """Classificeer een document via Claude API (tekst-modus).

    Gebruikt OCR-tekst als input. Zie classify_document_vision() voor directe PDF/afbeelding analyse.
    """
    if not is_configured():
        raise RuntimeError("Claude API niet geconfigureerd (ANTHROPIC_API_KEY)")

    prompt = _build_classification_prompt(ocr_text, bestandsnaam, dossier_context)

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 500,
        "temperature": 0.1,
        "messages": [{"role": "user", "content": prompt}],
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(ANTHROPIC_URL, headers=headers, json=payload)

        if resp.status_code != 200:
            logger.error("Claude classificatie mislukt: %s %s", resp.status_code, resp.text[:300])
            raise RuntimeError(f"Claude API fout: {resp.status_code}")

        data = resp.json()
        text = data["content"][0]["text"].strip()

        # Parse JSON uit response (soms zit er tekst omheen)
        try:
            # Zoek JSON object in de response
            start = text.index("{")
            end = text.rindex("}") + 1
            result = json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError) as e:
            logger.error("Claude classificatie: ongeldig JSON response: %s", text[:200])
            raise RuntimeError(f"Claude classificatie: kon JSON niet parsen: {e}")

        # Valideer tegen bekende types
        doc_types = _load_document_types()
        doc_type = result.get("document_type", "onbekend")
        if doc_type not in doc_types and doc_type != "onbekend":
            logger.warning("Claude classificatie: onbekend type '%s', fallback naar 'onbekend'", doc_type)
            doc_type = "onbekend"

        categorie = result.get("categorie", "Overig")
        if doc_type in doc_types:
            # Gebruik categorie uit config (betrouwbaarder dan Claude's keuze)
            categorie = doc_types[doc_type].get("category", categorie)

        classification = ClassificationResult(
            document_type=doc_type,
            categorie=categorie,
            persoon=result.get("persoon", "gezamenlijk"),
            confidence=float(result.get("confidence", 0.5)),
            reasoning=result.get("reasoning", ""),
        )

        logger.info("Geclassificeerd: %s (categorie=%s, persoon=%s, confidence=%.2f)",
                     classification.document_type, classification.categorie,
                     classification.persoon, classification.confidence)

        return classification


def _mime_to_media_type(mime_type: str) -> str:
    """Converteer MIME type naar Claude Vision media_type."""
    mapping = {
        "application/pdf": "application/pdf",
        "image/jpeg": "image/jpeg",
        "image/png": "image/png",
        "image/tiff": "image/tiff",
        "image/gif": "image/gif",
        "image/webp": "image/webp",
    }
    return mapping.get(mime_type, "application/pdf")


async def classify_document_vision(
    file_bytes: bytes,
    mime_type: str,
    bestandsnaam: str,
    dossier_context: dict,
) -> ClassificationResult:
    """Classificeer een document via Claude Vision (direct, zonder OCR).

    Stuurt het document als base64 naar Claude. Werkt voor PDF's en afbeeldingen.
    Sneller en goedkoper dan Azure DI + Claude tekst, maar minder goed bij
    slechte scans of handgeschreven tekst.

    Args:
        file_bytes: Document als bytes
        mime_type: MIME type (application/pdf, image/jpeg, etc.)
        bestandsnaam: Originele bestandsnaam
        dossier_context: {"aanvrager_naam": "...", "partner_naam": "...", "klanttype": "..."}

    Returns:
        ClassificationResult
    """
    if not is_configured():
        raise RuntimeError("Claude API niet geconfigureerd (ANTHROPIC_API_KEY)")

    doc_types = _load_document_types()
    type_descriptions = []
    for key, info in doc_types.items():
        desc = info.get("description", key)
        keywords = ", ".join(info.get("keywords", []))
        category = info.get("category", "Overig")
        type_descriptions.append(f'- "{key}": {desc} (categorie: {category})')
    types_text = "\n".join(type_descriptions)

    aanvrager = dossier_context.get("aanvrager_naam", "onbekend")
    partner = dossier_context.get("partner_naam", "")
    partner_text = f"\nPartner: {partner}" if partner else "\nGeen partner bekend."

    prompt = f"""Je bent een documentclassificatie-expert voor hypotheekadvies in Nederland.

Analyseer het bijgevoegde document en bepaal:
1. Wat voor type document dit is
2. Bij welke categorie het hoort
3. Of het bij de aanvrager, partner of gezamenlijk hoort

## Dossiercontext
Aanvrager: {aanvrager}{partner_text}
Bestandsnaam: {bestandsnaam}

## Beschikbare documenttypen
{types_text}

## Instructies
- Kies het best passende documenttype uit de lijst
- Als het document niet matcht, gebruik "onbekend"
- Bepaal 'persoon' op basis van namen in het document vs. dossiercontext
- Let op gehuwde namen: "Slinger-Aap" kan matchen op "Slinger" (aanvrager) of "Aap" (partner meisjesnaam)
- Geef een confidence score (0.0 - 1.0). Gebruik < 0.7 als je twijfelt.

Antwoord in exact dit JSON formaat:
{{"document_type": "...", "categorie": "...", "persoon": "...", "confidence": 0.95, "reasoning": "..."}}"""

    b64 = base64.standard_b64encode(file_bytes).decode("ascii")
    media_type = _mime_to_media_type(mime_type)

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 500,
        "temperature": 0.1,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {"type": "base64", "media_type": media_type, "data": b64},
                },
                {"type": "text", "text": prompt},
            ],
        }],
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(ANTHROPIC_URL, headers=headers, json=payload)

        if resp.status_code != 200:
            logger.error("Claude Vision classificatie mislukt: %s %s", resp.status_code, resp.text[:300])
            raise RuntimeError(f"Claude Vision API fout: {resp.status_code}")

        data = resp.json()
        text = data["content"][0]["text"].strip()

        try:
            start_idx = text.index("{")
            end_idx = text.rindex("}") + 1
            result = json.loads(text[start_idx:end_idx])
        except (ValueError, json.JSONDecodeError) as e:
            logger.error("Claude Vision: ongeldig JSON: %s", text[:200])
            raise RuntimeError(f"Claude Vision: kon JSON niet parsen: {e}")

        doc_type = result.get("document_type", "onbekend")
        if doc_type not in doc_types and doc_type != "onbekend":
            doc_type = "onbekend"

        categorie = result.get("categorie", "Overig")
        if doc_type in doc_types:
            categorie = doc_types[doc_type].get("category", categorie)

        classification = ClassificationResult(
            document_type=doc_type,
            categorie=categorie,
            persoon=result.get("persoon", "gezamenlijk"),
            confidence=float(result.get("confidence", 0.5)),
            reasoning=result.get("reasoning", ""),
        )

        logger.info("Vision classificatie: %s (confidence=%.2f)", classification.document_type, classification.confidence)
        return classification
