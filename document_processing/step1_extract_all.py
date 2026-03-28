"""Stap 1: Vrije extractie — 'Vertel me alles wat je ziet'.

Classificeert het document en extraheert ALLE informatie zonder beperkingen.
Output wordt opgeslagen in document_extractions tabel (doorzoekbaar, chatbot).
"""

import base64
import json
import logging
import os

import httpx

logger = logging.getLogger("nat-api.step1")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

# Documenttypes laden voor classificatie-context
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

Analyseer het bijgevoegde document VOLLEDIG. Extraheer ALLE informatie die erop staat.
Elk veld, elk bedrag, elke datum, elke naam, elk adres, elk percentage, elk telefoonnummer.
Mis niets — details maken het verschil.

## Dossiercontext
Aanvrager: {aanvrager}{partner_text}

## Stap 1: Classificatie
Bepaal wat voor document dit is. Kies uit deze lijst:
{types_list}
- "jaaropgave": loonopgave van werkgever voor de belastingdienst (NIET hetzelfde als jaarrekening)
- "onbekend": als het niet matcht

KRITIEKE CLASSIFICATIEREGELS:
- De TITEL of KOPTEKST bepaalt het type. "Ontruimingsverklaring" = ontruimingsverklaring, niet paspoort.
- SALARISSTROOK = één maand/periode. JAAROPGAVE = heel jaar overzicht. JAARREKENING = bedrijfsverslag.
  Als het EEN loonperiode betreft → salarisstrook. Als het een JAAROVERZICHT is → jaaropgave.
- VERKOOPBROCHURE (foto's, vraagprijs) ≠ verkoopovereenkomst.
- RIJBEWIJS ≠ ID-kaart ≠ paspoort. Classificeer als "rijbewijs".
- NHG BEHEERTOETS ≠ IBL-resultaat ≠ UWV. Classificeer als "nhg_toets".
- E-mail/brief met toelichting = "toelichting", niet "email_correspondentie".
- KADASTER: "kadaster_eigendom" (eigenaar) vs "kadaster_hypotheek" (hypotheken).
- UWV: ALLEEN echt verzekeringsbericht met loongegevens. Geen IBL, NHG of aanvraagformulier.
- GETEKEND vs BLANCO: meld handtekening_aanwezig in document_specifiek.
- Bij paspoort/ID/rijbewijs/ontruimingsverklaring van iemand die niet aanvrager of partner is → persoon="ex-partner".
  UPO, loonstrook, WGV, jaaropgave, UWV zijn ALTIJD van de genoemde persoon — nooit "ex-partner".

Bepaal ook of het bij de aanvrager, partner, gezamenlijk of ex-partner hoort.
Let op gehuwde namen: "Slinger-Aap" kan matchen op "Slinger" (aanvrager) of "Aap" (partner meisjesnaam).
Let op: "Burg. van [stad]" op een paspoort betekent Burgemeester van [stad] → afgifteplaats = [stad].

## Stap 2: Volledige extractie
Geef ALLE informatie uit het document, gestructureerd in categorieën:

### Persoonsgegevens
Namen, voorletters, tussenvoegsel, achternaam, geboortedatum, geboorteplaats, geslacht, nationaliteit, etc.

### Adressen
Alle adressen die op het document staan (van personen, werkgevers, instanties).

### Financieel
Alle bedragen, percentages, rentes, looptijden, etc.

### Datums en termijnen
Alle datums (afgifte, geldigheid, indiensttreding, leveringsdatum, etc.)

### Document-specifiek
Alle overige informatie die relevant is (documentnummers, KvK, polisnummers, etc.)

### Opvallend / Waarschuwingen
Alles wat opvalt: inconsistenties, ontbrekende vinkjes, toekomstige datums, etc.

## Speciale instructies
- Bij salarisstroken: zoek de EIGEN BIJDRAGE PENSIOEN. Dit kan staan als:
  "Premie pensioen", "Premie OP", "Ouderdomspensioen", "Pensioenpremie WN",
  "Premie ABP Pensioen/NP", "Bijdrage Pensioenfonds", "PENSION PR.", etc.
  Tel alle pensioen-inhoudingen op. NIET meetellen: WGA-Hiaat, WIA, PAWW.
- Bij werkgeversverklaringen: noteer expliciet als velden "Nee" of "€0" zijn (loonbeslag: Nee, 13e maand: €0).
- Bij een nota van afrekening: dit is GEEN hypotheekoverzicht. Classificeer correct.
- Bij paspoort: MRZ-regels bevatten geboorteland en extra info.

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
  }}
}}"""


async def extract_all_vision(
    file_bytes: bytes,
    mime_type: str,
    dossier_context: dict,
) -> dict:
    """Stap 1 via Claude Vision: classificatie + volledige extractie."""
    b64 = base64.standard_b64encode(file_bytes).decode("ascii")
    media_type = {
        "application/pdf": "application/pdf",
        "image/jpeg": "image/jpeg",
        "image/png": "image/png",
        "image/tiff": "image/tiff",
        "image/gif": "image/gif",
        "image/webp": "image/webp",
    }.get(mime_type, "application/pdf")

    is_image = media_type.startswith("image/")
    content_type = "image" if is_image else "document"

    prompt = _build_prompt(dossier_context)

    resp = await _call_claude([
        {"type": content_type, "source": {"type": "base64", "media_type": media_type, "data": b64}},
        {"type": "text", "text": prompt},
    ])
    return resp


async def extract_all_text(
    text: str,
    bestandsnaam: str,
    dossier_context: dict,
) -> dict:
    """Stap 1 via tekst (PyPDF2 of Azure DI OCR): classificatie + volledige extractie."""
    prompt = _build_prompt(dossier_context)
    prompt += f"\n\n## Document tekst\nBestandsnaam: {bestandsnaam}\n\n{text[:30000]}"

    resp = await _call_claude([
        {"type": "text", "text": prompt},
    ])
    return resp


async def _call_claude(content: list) -> dict:
    """Generieke Claude API call, parse JSON response."""
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 4000,
        "temperature": 0.0,
        "messages": [{"role": "user", "content": content}],
    }

    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(ANTHROPIC_URL, headers=headers, json=payload)

        if resp.status_code != 200:
            logger.error("Claude stap 1 mislukt: %s %s", resp.status_code, resp.text[:300])
            raise RuntimeError(f"Claude API fout: {resp.status_code}")

        data = resp.json()
        text = data["content"][0]["text"].strip()

        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError) as e:
            logger.error("Claude stap 1: ongeldig JSON: %s", text[:300])
            raise RuntimeError(f"Claude stap 1: kon JSON niet parsen: {e}")
