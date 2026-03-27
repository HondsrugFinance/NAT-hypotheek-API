"""Gecombineerde stap 1+2 voor simpele documenten — één Claude call.

"Vertel me alles EN structureer het direct."
Gebruikt voor: paspoort, ID-kaart, bankafschrift, salarisstrook, BKR, energielabel.
"""

import base64
import json
import logging
import os

import httpx

logger = logging.getLogger("nat-api.step-combined")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

# Documenten die in één call verwerkt kunnen worden
SIMPLE_DOCUMENTS = {
    "paspoort", "id_kaart", "bankafschrift", "salarisstrook",
    "bkr", "energielabel", "leningoverzicht", "vermogensoverzicht",
    "betaalspecificatie_uitkering", "pensioenspecificatie",
}

_doc_types_cache: dict | None = None


def _load_document_types() -> dict:
    global _doc_types_cache
    if _doc_types_cache is None:
        config_path = os.path.join(os.path.dirname(__file__), "..", "config", "document_types.json")
        with open(config_path, encoding="utf-8") as f:
            _doc_types_cache = json.load(f)
    return _doc_types_cache


def _build_prompt(dossier_context: dict) -> str:
    doc_types = _load_document_types()
    types_list = "\n".join(f'- "{k}": {v.get("description", k)}' for k, v in doc_types.items())

    aanvrager = dossier_context.get("aanvrager_naam", "onbekend")
    partner = dossier_context.get("partner_naam", "")
    partner_text = f"\nPartner: {partner}" if partner else "\nGeen partner bekend."

    return f"""Je bent een documentanalyse-expert voor hypotheekadvies in Nederland.

Analyseer het bijgevoegde document in ÉÉN keer: classificeer het, extraheer ALLE informatie,
en structureer de belangrijkste velden direct.

## Dossiercontext
Aanvrager: {aanvrager}{partner_text}

## Beschikbare documenttypen
{types_list}

## Opdracht (3-in-1)

### A. Classificatie
Bepaal het documenttype, categorie, persoon (aanvrager/partner/gezamenlijk), confidence.

### B. Volledige extractie
Extraheer ALLE informatie: elk veld, bedrag, datum, naam, adres, percentage.
Structureer in categorieën: persoonsgegevens, adressen, financieel, datums, document_specifiek, opvallend.

### C. Gestructureerde velden
Map de belangrijkste velden naar gestandaardiseerde namen:
- Datums: YYYY-MM-DD
- Bedragen: getal zonder valutasymbool
- Percentages: getal (8.13, niet 8,13%)
- Boolean: true/false
- Namen: voluit, voorletters met punten

Speciale instructies:
- Bij salarisstrook: zoek EIGEN BIJDRAGE PENSIOEN (kan heten: "Premie pensioen", "Premie OP",
  "Ouderdomspensioen", "Pensioenpremie WN", "Premie ABP Pensioen/NP", etc.)
  Tel ALLE pensioen-inhoudingen op. Sla op als "maandelijksePensioenbijdrage".
  NIET meetellen: WGA-Hiaat, WIA-excedent, PAWW.
- Bij paspoort: "Burg. van [stad]" = afgifteplaats [stad]. Geslacht uit V/F of M/F.
- Bij pensioenspecificatie: bereken "ouderdomspensioenTotaalExclAow" (alle fondsen behalve SVB),
  "aowBedrag" apart. Nabestaandenpensioen: bepaal scenario (voor/na pensionering) op basis van AOW-datum.

Antwoord in exact dit JSON formaat:
{{
  "classification": {{
    "document_type": "...",
    "categorie": "...",
    "persoon": "aanvrager|partner|gezamenlijk",
    "confidence": 0.95,
    "reasoning": "korte uitleg"
  }},
  "extracted_data": {{
    "persoonsgegevens": {{ ... }},
    "adressen": {{ ... }},
    "financieel": {{ ... }},
    "datums": {{ ... }},
    "document_specifiek": {{ ... }},
    "opvallend": ["...", "..."]
  }},
  "structured_fields": {{
    "veldnaam": waarde,
    ...
  }},
  "field_confidence": {{
    "veldnaam": 0.95,
    ...
  }},
  "waarschuwingen": ["...", "..."]
}}"""


async def process_combined_vision(
    file_bytes: bytes,
    mime_type: str,
    dossier_context: dict,
) -> dict:
    """Gecombineerde stap 1+2 via Claude Vision."""
    b64 = base64.standard_b64encode(file_bytes).decode("ascii")
    media_type = {
        "application/pdf": "application/pdf",
        "image/jpeg": "image/jpeg",
        "image/png": "image/png",
        "image/tiff": "image/tiff",
    }.get(mime_type, "application/pdf")

    prompt = _build_prompt(dossier_context)

    return await _call_claude([
        {"type": "document", "source": {"type": "base64", "media_type": media_type, "data": b64}},
        {"type": "text", "text": prompt},
    ])


async def process_combined_text(
    text: str,
    bestandsnaam: str,
    dossier_context: dict,
) -> dict:
    """Gecombineerde stap 1+2 via tekst (PyPDF2)."""
    prompt = _build_prompt(dossier_context)
    prompt += f"\n\n## Document tekst\nBestandsnaam: {bestandsnaam}\n\n{text[:30000]}"

    return await _call_claude([
        {"type": "text", "text": prompt},
    ])


async def _call_claude(content: list) -> dict:
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 6000,
        "temperature": 0.0,
        "messages": [{"role": "user", "content": content}],
    }

    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(ANTHROPIC_URL, headers=headers, json=payload)

        if resp.status_code != 200:
            logger.error("Claude combined mislukt: %s %s", resp.status_code, resp.text[:300])
            raise RuntimeError(f"Claude API fout: {resp.status_code}")

        data = resp.json()
        text = data["content"][0]["text"].strip()

        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError) as e:
            logger.error("Claude combined: ongeldig JSON: %s", text[:300])
            raise RuntimeError(f"Claude combined: kon JSON niet parsen: {e}")
