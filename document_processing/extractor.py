"""Document extractie via Claude API — haalt specifieke velden uit documenten."""

import base64
import json
import logging
import os

import httpx

from document_processing.schemas import ExtractionResult

logger = logging.getLogger("nat-api.extractor")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

_doc_types_cache: dict | None = None


def _load_document_types() -> dict:
    global _doc_types_cache
    if _doc_types_cache is None:
        config_path = os.path.join(os.path.dirname(__file__), "..", "config", "document_types.json")
        with open(config_path, encoding="utf-8") as f:
            _doc_types_cache = json.load(f)
    return _doc_types_cache


def _build_extraction_prompt(ocr_text: str, document_type: str, dossier_context: dict) -> str:
    """Bouw de extractie-prompt op basis van documenttype."""
    doc_types = _load_document_types()
    doc_info = doc_types.get(document_type, {})
    extract_fields = doc_info.get("extract_fields", [])

    aanvrager = dossier_context.get("aanvrager_naam", "onbekend")
    partner = dossier_context.get("partner_naam", "")

    fields_text = "\n".join(f"- {f}" for f in extract_fields)

    return f"""Je bent een specialist in het extraheren van gegevens uit Nederlandse hypotheekdocumenten.

## Document
Type: {document_type}
Beschrijving: {doc_info.get('description', document_type)}

## Dossiercontext
Aanvrager: {aanvrager}
Partner: {partner or 'geen'}

## Gewenste velden
Extraheer de volgende gegevens uit de tekst:
{fields_text}

## Formateerinstructies
- Bedragen als getal ZONDER valutasymbool (bijv. 55000, niet €55.000)
- Percentages als getal (bijv. 8, niet 8%)
- Datums in formaat YYYY-MM-DD (bijv. 2026-01-15)
- Lege/ontbrekende velden als null
- Namen voluit, correct gespeld
- Voorletters met punten (bijv. "A.M.")

## Extra instructies per documenttype
{"- Bij werkgeversverklaring: let op of proeftijd is verstreken, of er loonbeslag is, of er een onderhandse lening is" if document_type == "werkgeversverklaring" else ""}
{"- Bij salarisstrook: zoek naar de eigen bijdrage pensioen (nodig voor IBL-berekening)" if document_type == "salarisstrook" else ""}
{"- Bij UWV verzekeringsbericht: extraheer alle werkgevers/dienstverbanden apart" if document_type == "uwv_verzekeringsbericht" else ""}
{"- Bij koopovereenkomst: let op erfpacht, ontbindende voorwaarden datum, bankgarantie datum" if document_type == "koopovereenkomst" else ""}
{"- Bij paspoort/ID: voorletters afleiden uit voornamen (eerste letters + punten)" if document_type in ("paspoort", "id_kaart") else ""}

## OCR-tekst
{ocr_text[:8000]}

Antwoord in exact dit JSON formaat:
{{
  "extracted_fields": {{
    "veldnaam": "waarde",
    ...
  }},
  "confidence": 0.92,
  "warnings": ["waarschuwing 1", ...]
}}

Geef ALLEEN de velden die je daadwerkelijk kunt vinden in de tekst. Gok niet."""


async def extract_fields(
    ocr_text: str,
    document_type: str,
    dossier_context: dict,
) -> ExtractionResult:
    """Extraheer velden uit een document via Claude API.

    Args:
        ocr_text: OCR-tekst uit Azure Document Intelligence
        document_type: Geclassificeerd documenttype (key uit document_types.json)
        dossier_context: {"aanvrager_naam": "...", "partner_naam": "..."}

    Returns:
        ExtractionResult met raw_values, computed_values, confidence, warnings
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("Claude API niet geconfigureerd (ANTHROPIC_API_KEY)")

    prompt = _build_extraction_prompt(ocr_text, document_type, dossier_context)

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 2000,
        "temperature": 0.0,
        "messages": [{"role": "user", "content": prompt}],
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(ANTHROPIC_URL, headers=headers, json=payload)

        if resp.status_code != 200:
            logger.error("Claude extractie mislukt: %s %s", resp.status_code, resp.text[:300])
            raise RuntimeError(f"Claude API fout: {resp.status_code}")

        data = resp.json()
        text = data["content"][0]["text"].strip()

        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            result = json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError) as e:
            logger.error("Claude extractie: ongeldig JSON: %s", text[:200])
            raise RuntimeError(f"Claude extractie: kon JSON niet parsen: {e}")

    raw_values = result.get("extracted_fields", {})
    warnings = result.get("warnings", [])
    confidence = float(result.get("confidence", 0.5))

    # Computed values: converteer strings naar getallen waar mogelijk
    computed_values = {}
    for key, val in raw_values.items():
        if val is None:
            continue
        # Probeer getal-conversie
        if isinstance(val, str):
            clean = val.replace(".", "").replace(",", ".").replace("€", "").replace(" ", "").strip()
            try:
                computed_values[key] = float(clean)
            except ValueError:
                computed_values[key] = val
        else:
            computed_values[key] = val

    logger.info("Geëxtraheerd: %s — %d velden, confidence=%.2f, %d waarschuwingen",
                document_type, len(raw_values), confidence, len(warnings))

    return ExtractionResult(
        raw_values=raw_values,
        computed_values=computed_values,
        confidence=confidence,
        warnings=warnings,
    )


def _build_extraction_prompt_base(document_type: str, dossier_context: dict) -> str:
    """Bouw de extractie-prompt zonder OCR tekst (voor Vision modus)."""
    doc_types = _load_document_types()
    doc_info = doc_types.get(document_type, {})
    extract_fields = doc_info.get("extract_fields", [])

    aanvrager = dossier_context.get("aanvrager_naam", "onbekend")
    partner = dossier_context.get("partner_naam", "")
    fields_text = "\n".join(f"- {f}" for f in extract_fields)

    extra = ""
    if document_type == "werkgeversverklaring":
        extra = "- Let op proeftijd, loonbeslag, onderhandse lening, loondoorbetaling bij ziekte"
    elif document_type == "salarisstrook":
        extra = "- Zoek de eigen bijdrage pensioen (bedrag + percentage) — nodig voor IBL-berekening"
    elif document_type == "koopovereenkomst":
        extra = "- Let op erfpacht, ontbindende voorwaarden datum, bankgarantie datum"
    elif document_type in ("paspoort", "id_kaart"):
        extra = "- Voorletters afleiden uit voornamen (eerste letters + punten)"
    elif document_type == "hypotheekoverzicht":
        extra = "- Extraheer ALLE leningdelen apart (aflosvorm, bedrag, rente, looptijd per deel)"

    return f"""Je bent een specialist in het extraheren van gegevens uit Nederlandse hypotheekdocumenten.

## Document
Type: {document_type}
Beschrijving: {doc_info.get('description', document_type)}

## Dossiercontext
Aanvrager: {aanvrager}
Partner: {partner or 'geen'}

## Gewenste velden
Extraheer de volgende gegevens uit het bijgevoegde document:
{fields_text}

## Extra instructies
{extra}

## Formateerinstructies
- Bedragen als getal ZONDER valutasymbool (bijv. 55000, niet €55.000)
- Percentages als getal (bijv. 8, niet 8%)
- Datums in formaat YYYY-MM-DD
- Lege/ontbrekende velden als null
- Namen voluit, correct gespeld

Antwoord in exact dit JSON formaat:
{{
  "extracted_fields": {{
    "veldnaam": "waarde",
    ...
  }},
  "confidence": 0.92,
  "warnings": ["waarschuwing 1", ...]
}}

Geef ALLEEN de velden die je daadwerkelijk kunt vinden. Gok niet."""


async def extract_fields_vision(
    file_bytes: bytes,
    mime_type: str,
    document_type: str,
    dossier_context: dict,
) -> ExtractionResult:
    """Extraheer velden via Claude Vision (direct, zonder OCR).

    Stuurt het document als base64 naar Claude. Standaardroute voor digitale PDF's.
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("Claude API niet geconfigureerd (ANTHROPIC_API_KEY)")

    prompt = _build_extraction_prompt_base(document_type, dossier_context)

    b64 = base64.standard_b64encode(file_bytes).decode("ascii")
    media_type = {
        "application/pdf": "application/pdf",
        "image/jpeg": "image/jpeg",
        "image/png": "image/png",
        "image/tiff": "image/tiff",
    }.get(mime_type, "application/pdf")

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 2000,
        "temperature": 0.0,
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

    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(ANTHROPIC_URL, headers=headers, json=payload)

        if resp.status_code != 200:
            logger.error("Claude Vision extractie mislukt: %s %s", resp.status_code, resp.text[:300])
            raise RuntimeError(f"Claude Vision API fout: {resp.status_code}")

        data = resp.json()
        text = data["content"][0]["text"].strip()

        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            result = json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError) as e:
            logger.error("Claude Vision extractie: ongeldig JSON: %s", text[:200])
            raise RuntimeError(f"Claude Vision extractie: kon JSON niet parsen: {e}")

    raw_values = result.get("extracted_fields", {})
    warnings = result.get("warnings", [])
    confidence = float(result.get("confidence", 0.5))

    computed_values = {}
    for key, val in raw_values.items():
        if val is None:
            continue
        if isinstance(val, str):
            clean = val.replace(".", "").replace(",", ".").replace("\u20ac", "").replace(" ", "").strip()
            try:
                computed_values[key] = float(clean)
            except ValueError:
                computed_values[key] = val
        else:
            computed_values[key] = val

    logger.info("Vision extractie: %s — %d velden, confidence=%.2f",
                document_type, len(raw_values), confidence)

    return ExtractionResult(
        raw_values=raw_values,
        computed_values=computed_values,
        confidence=confidence,
        warnings=warnings,
    )
