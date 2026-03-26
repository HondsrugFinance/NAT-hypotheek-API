"""Stap 2: Structurering + dossiervergelijking.

Neemt de ruwe extractie uit stap 1 en:
- Mapt naar gestandaardiseerde veldnamen
- Vergelijkt met bestaande dossierdata
- Detecteert inconsistenties per document
"""

import json
import logging
import os

import httpx

logger = logging.getLogger("nat-api.step2")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def _build_prompt(
    raw_extraction: dict,
    document_type: str,
    persoon: str,
    existing_fields: dict,
    dossier_context: dict,
) -> str:
    aanvrager = dossier_context.get("aanvrager_naam", "onbekend")
    partner = dossier_context.get("partner_naam", "")

    existing_text = ""
    if existing_fields:
        existing_text = f"""
## Bestaande dossierdata (eerder geëxtraheerd of handmatig ingevuld)
{json.dumps(existing_fields, indent=2, ensure_ascii=False)[:4000]}

Vergelijk de nieuwe extractie met bovenstaande data. Meld inconsistenties.
"""

    return f"""Je bent een hypotheekadvies-specialist. Je krijgt een ruwe document-extractie en moet deze structureren.

## Document
Type: {document_type}
Persoon: {persoon}
Aanvrager: {aanvrager}
Partner: {partner or 'geen'}

## Ruwe extractie (uit stap 1)
{json.dumps(raw_extraction, indent=2, ensure_ascii=False)[:8000]}
{existing_text}
## Opdracht
1. Map de geëxtraheerde data naar gestandaardiseerde velden.
2. Groepeer per sectie (persoonsgegevens, inkomen, onderpand, etc.)
3. Gebruik deze veldnamen en formaten:
   - Datums: YYYY-MM-DD
   - Bedragen: getal zonder valutasymbool (55000, niet €55.000)
   - Percentages: getal (8.13, niet 8,13%)
   - Boolean: true/false
   - Namen: voluit, correct gespeld
   - Voorletters: met punten (A.M.)
   - Achternaam apart, tussenvoegsel apart
4. Geef per veld een confidence (0.0-1.0)
5. Meld inconsistenties met bestaande dossierdata
6. Meld waarschuwingen (verlopen document, toekomstige datums, ontbrekende info)

## Speciale veldnamen
- Pensioenbijdrage: altijd "maandelijksePensioenbijdrage" (bedrag) en "pensioenbijdragePercentage" (%)
- Bruto salaris: "brutoJaarsalaris" (jaar) of "brutoMaandloon" (maand)
- Vakantiegeld: "vakantiegeldBedrag" (bedrag) en "vakantiegeldPercentage" (%)

Antwoord in exact dit JSON formaat:
{{
  "sectie": "{document_type}",
  "persoon": "{persoon}",
  "fields": {{
    "veldnaam": waarde,
    ...
  }},
  "field_confidence": {{
    "veldnaam": 0.95,
    ...
  }},
  "inconsistenties": [
    {{"veld": "...", "huidig": "...", "nieuw": "...", "bron": "..."}}
  ],
  "waarschuwingen": ["...", "..."],
  "suggesties": ["...", "..."]
}}"""


async def structure_and_compare(
    raw_extraction: dict,
    document_type: str,
    persoon: str,
    existing_fields: dict,
    dossier_context: dict,
) -> dict:
    """Structureer ruwe extractie en vergelijk met bestaande dossierdata."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("Claude API niet geconfigureerd")

    prompt = _build_prompt(raw_extraction, document_type, persoon, existing_fields, dossier_context)

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 3000,
        "temperature": 0.0,
        "messages": [{"role": "user", "content": prompt}],
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(ANTHROPIC_URL, headers=headers, json=payload)

        if resp.status_code != 200:
            logger.error("Claude stap 2 mislukt: %s %s", resp.status_code, resp.text[:300])
            raise RuntimeError(f"Claude API fout: {resp.status_code}")

        data = resp.json()
        text = data["content"][0]["text"].strip()

        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError) as e:
            logger.error("Claude stap 2: ongeldig JSON: %s", text[:300])
            raise RuntimeError(f"Claude stap 2: kon JSON niet parsen: {e}")
