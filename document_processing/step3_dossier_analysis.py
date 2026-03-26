"""Stap 3: Dossier-brede analyse.

Kijkt naar ALLE geëxtraheerde data van ALLE documenten samen:
- Inconsistenties tussen documenten
- Ontbrekende documenten
- Inkomensvergelijking (WGV vs IBL)
- Compleetheidspercentage
- Suggesties aan adviseur
"""

import json
import logging
import os

import httpx

logger = logging.getLogger("nat-api.step3")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def _build_prompt(
    all_extractions: list[dict],
    all_fields: list[dict],
    dossier_context: dict,
) -> str:
    aanvrager = dossier_context.get("aanvrager_naam", "onbekend")
    partner = dossier_context.get("partner_naam", "")

    # Bouw overzicht van alle documenten
    docs_overview = []
    for ext in all_extractions:
        docs_overview.append({
            "type": ext.get("document_type", "onbekend"),
            "persoon": ext.get("persoon", "onbekend"),
            "data": ext.get("raw_data", {}),
        })

    # Bouw overzicht van alle gestructureerde velden
    fields_overview = []
    for f in all_fields:
        fields_overview.append({
            "sectie": f.get("sectie", ""),
            "persoon": f.get("persoon", ""),
            "fields": f.get("fields", {}),
        })

    return f"""Je bent een senior hypotheekadviseur die een dossier analyseert.

## Dossiercontext
Aanvrager: {aanvrager}
Partner: {partner or 'geen'}

## Alle verwerkte documenten ({len(all_extractions)})
{json.dumps(docs_overview, indent=2, ensure_ascii=False)[:10000]}

## Alle gestructureerde velden
{json.dumps(fields_overview, indent=2, ensure_ascii=False)[:6000]}

## Opdracht
Analyseer het complete dossier en geef:

1. **Compleetheid**: Welke documenttypen zijn aanwezig? Welke ontbreken nog?
   Basisdocumenten (altijd nodig): paspoort/ID, loonstrook/WGV/UWV, bankafschrift
   Bij aankoop: koopovereenkomst, taxatierapport
   Bij loondienst: werkgeversverklaring EN/OF UWV
   Bij ondernemer: jaarrekening, IB-aangifte, IB60

2. **Inconsistenties**: Vergelijk dezelfde gegevens over documenten heen.
   - Geboortedatum identiek op alle docs?
   - Naam consistent?
   - Werkgever op WGV = werkgever op loonstrook = werkgever op UWV?
   - Adres consistent?
   - Inkomensbedragen logisch t.o.v. elkaar?

3. **Inkomensvergelijking** (als van toepassing):
   - WGV inkomen vs IBL toetsinkomen vs loonstrook-schatting
   - Welke is het hoogst? Suggestie welke te gebruiken.
   - Als WGV ontbreekt maar loonstrook suggereert hoger inkomen dan IBL → suggestie WGV opvragen.

4. **Waarschuwingen**:
   - Verlopen documenten
   - Toekomstige datums die niet kloppen
   - Ontbrekende handtekeningen
   - Proeftijd niet verstreken
   - Loonbeslag
   - Document betreft een andere woning/partner dan verwacht

5. **Samenvatting**: Korte status van het dossier in 2-3 zinnen.

Antwoord in exact dit JSON formaat:
{{
  "samenvatting": "Het dossier bevat ...",
  "compleetheid": {{
    "aanwezig": ["paspoort", "salarisstrook", ...],
    "ontbrekend": ["werkgeversverklaring", ...],
    "percentage": 65
  }},
  "inconsistenties": [
    {{"veld": "geboortedatum", "documenten": ["paspoort", "uwv"], "waarden": ["1995-08-23", "1995-08-23"], "status": "consistent"}},
    ...
  ],
  "inkomen_analyse": {{
    "aanvrager": {{
      "wgv_inkomen": null,
      "ibl_inkomen": 29715.31,
      "loonstrook_schatting": 58752,
      "suggestie": "WGV inkomen (EUR 58.752) is significant hoger dan IBL (EUR 29.715). Aanbeveling: gebruik WGV."
    }},
    "partner": {{ ... }}
  }},
  "suggesties": [
    "WGV opvragen — potentieel hoger inkomen",
    ...
  ],
  "waarschuwingen": [
    "Nota van afrekening betreft eerdere woning De Lange Garde 10 met J. Derks (2020)",
    ...
  ],
  "confidence": 0.9
}}"""


async def analyze_dossier(
    all_extractions: list[dict],
    all_fields: list[dict],
    dossier_context: dict,
) -> dict:
    """Voer dossier-brede analyse uit op alle geëxtraheerde data."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("Claude API niet geconfigureerd")

    if not all_extractions:
        return {
            "samenvatting": "Geen documenten verwerkt.",
            "compleetheid": {"aanwezig": [], "ontbrekend": [], "percentage": 0},
            "inconsistenties": [],
            "inkomen_analyse": {},
            "suggesties": [],
            "waarschuwingen": [],
            "confidence": 0,
        }

    prompt = _build_prompt(all_extractions, all_fields, dossier_context)

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
            logger.error("Claude stap 3 mislukt: %s %s", resp.status_code, resp.text[:300])
            raise RuntimeError(f"Claude API fout: {resp.status_code}")

        data = resp.json()
        text = data["content"][0]["text"].strip()

        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError) as e:
            logger.error("Claude stap 3: ongeldig JSON: %s", text[:300])
            raise RuntimeError(f"Claude stap 3: kon JSON niet parsen: {e}")
