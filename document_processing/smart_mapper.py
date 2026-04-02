"""Smart mapper — Claude vult het doelschema in op basis van geëxtraheerde data.

In plaats van een handmatige veld-mapping laat Claude het formulier invullen.
Claude krijgt:
1. Alle geëxtraheerde data uit documenten (de vergaarbak)
2. Het doelschema (AanvraagData of berekening-invoer)
3. De huidige data (wat de adviseur al heeft ingevuld)

Claude retourneert een kant-en-klaar JSON object + veldenlijst voor de UI.
"""

import json
import logging
import os
from typing import Any

import httpx

from document_processing.schemas_target import AANVRAAG_SCHEMA, BEREKENING_SCHEMA

logger = logging.getLogger("nat-api.smart-mapper")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")


def _sb_headers() -> dict:
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }


async def _fetch_extracted_data(dossier_id: str) -> list[dict]:
    """Haal alle geëxtraheerde velden op voor een dossier."""
    headers = _sb_headers()
    all_data = []

    # extracted_fields (stap 2 output)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/extracted_fields",
            headers=headers,
            params={
                "select": "sectie,persoon,fields,field_confidence,status",
                "dossier_id": f"eq.{dossier_id}",
                "status": "in.(pending_review,accepted)",
                "order": "created_at.desc",
            },
        )
        if resp.status_code == 200:
            all_data.extend(resp.json())

    # IBL resultaten apart (sectie=inkomen_ibl)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/extracted_fields",
            headers=headers,
            params={
                "select": "sectie,persoon,fields,field_confidence,status",
                "dossier_id": f"eq.{dossier_id}",
                "sectie": "eq.inkomen_ibl",
                "order": "created_at.desc",
            },
        )
        if resp.status_code == 200:
            all_data.extend(resp.json())

    return all_data


async def _fetch_target_data(context: str, target_id: str) -> dict:
    """Haal huidige data op van het target (berekening of aanvraag)."""
    headers = _sb_headers()
    if context == "aanvraag":
        table, field = "aanvragen", "data"
    else:
        table, field = "berekeningen", "invoer"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=headers,
            params={"select": field, "id": f"eq.{target_id}"},
        )
        if resp.status_code == 200:
            rows = resp.json()
            if rows:
                return rows[0].get(field, {}) or {}
    return {}


def _format_extracted_for_prompt(extracted: list[dict]) -> str:
    """Formatteer geëxtraheerde data voor de Claude prompt."""
    sections = []
    seen = set()

    for ef in extracted:
        sectie = ef.get("sectie", "onbekend")
        persoon = ef.get("persoon", "onbekend")
        fields = ef.get("fields", {})

        if not fields:
            continue

        key = f"{sectie}_{persoon}"
        if key in seen:
            continue
        seen.add(key)

        lines = [f"\n--- {sectie} ({persoon}) ---"]
        for veld, waarde in fields.items():
            if waarde is not None:
                lines.append(f"  {veld}: {waarde}")

        sections.append("\n".join(lines))

    return "\n".join(sections) if sections else "(geen geëxtraheerde data)"


def _build_prompt(context: str, extracted_text: str, current_data: dict) -> str:
    """Bouw de Claude prompt."""
    schema = AANVRAAG_SCHEMA if context == "aanvraag" else BEREKENING_SCHEMA

    current_json = json.dumps(current_data, ensure_ascii=False, indent=2) if current_data else "{}"
    # Beperk huidige data tot 3000 chars om tokens te besparen
    if len(current_json) > 3000:
        current_json = current_json[:3000] + "\n... (ingekort)"

    return f"""Je bent een hypotheekadviseur-assistent. Je taak: vul het doelschema in met de beschikbare geëxtraheerde data uit documenten.

DOELSCHEMA:
{schema}

GEËXTRAHEERDE DATA UIT DOCUMENTEN:
{extracted_text}

HUIDIGE DATA (al ingevuld door adviseur):
{current_json}

INSTRUCTIES:
1. Vul het doelschema in met alle beschikbare data uit de documenten.
2. Behoud de huidige data van de adviseur — overschrijf NIET wat al ingevuld is (tenzij de huidige waarde 0, null, of een lege string is).
3. Bij meerdere inkomstenbronnen (WGV en IBL): maak APARTE entries. Één met soortBerekening="werkgeversverklaring" en één met soortBerekening="inkomensbepaling_loondienst".
4. Bij meerdere hypotheekdelen: maak aparte entries in de leningdelen array.
5. Zet GEEN waarden neer die niet in de brondata staan.
6. Datums in YYYY-MM-DD formaat.
7. Bedragen als getallen zonder € teken.
8. Rente als percentage (1.46 = 1,46%).
9. Looptijd in maanden (360 = 30 jaar).

RESPONSE FORMAT (strict JSON, geen markdown):
{{
  "merged_data": {{ ... het ingevulde schema ... }},
  "velden": [
    {{
      "pad": "aanvrager.persoon.achternaam",
      "label": "Achternaam",
      "waarde": "Brust",
      "waarde_display": "Brust",
      "bron": "paspoort",
      "status": "nieuw"
    }}
  ]
}}

Elke entry in "velden" representeert EEN veld dat je hebt ingevuld. Gebruik deze status:
- "nieuw": veld was leeg/0/null, nu ingevuld
- "bevestigd": veld was al ingevuld en matcht met document
- "afwijkend": veld was al ingevuld maar wijkt af van document (toon BEIDE waarden)

Voor "afwijkend" velden: zet de document-waarde in merged_data maar voeg "waarde_huidig" en "huidig_display" toe aan het veld-object.

Formatteer waarde_display als volgt:
- Bedragen: "€ 42.768" (met € en NL duizendtallen)
- Datums: "01-05-1983" (DD-MM-YYYY)
- Percentages: "1,46%"
- Booleans: "Ja" of "Nee"
- Getallen: "127" (geen € teken voor niet-bedragen zoals bouwjaar, m²)

Retourneer ALLEEN valid JSON, geen uitleg of markdown."""


async def generate_smart_import(
    dossier_id: str,
    target_id: str | None,
    context: str,
) -> dict:
    """Genereer import-preview via Claude.

    Returns:
        {
            "merged_data": { ... },
            "velden": [ { pad, label, waarde, waarde_display, bron, status } ],
            "groups": [ { title, items: [velden] } ],
            "samenvatting": { nieuw, bevestigd, afwijkend, totaal },
            "toon_banner": true,
            "dossier_id": "...",
            "context": "...",
        }
    """
    # 1. Haal geëxtraheerde data op
    extracted = await _fetch_extracted_data(dossier_id)

    if not extracted:
        return {
            "dossier_id": dossier_id,
            "target_id": target_id,
            "context": context,
            "merged_data": {},
            "velden": [],
            "imports": [],
            "groups": [],
            "toon_banner": False,
            "samenvatting": {"nieuw": 0, "bevestigd": 0, "afwijkend": 0, "totaal": 0},
        }

    # 2. Haal huidige target data op (als target bestaat)
    current_data = {}
    if target_id:
        current_data = await _fetch_target_data(context, target_id)

    # 3. Bouw prompt
    extracted_text = _format_extracted_for_prompt(extracted)
    prompt = _build_prompt(context, extracted_text, current_data)

    # 4. Claude API call
    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY niet geconfigureerd")
        return _fallback_response(dossier_id, target_id, context)

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 8000,
                "messages": [{"role": "user", "content": prompt}],
            },
        )

        if resp.status_code != 200:
            logger.error("Claude API error: %s %s", resp.status_code, resp.text[:500])
            return _fallback_response(dossier_id, target_id, context)

        result = resp.json()

    # 5. Parse Claude response
    content = result.get("content", [{}])[0].get("text", "")

    try:
        # Strip eventuele markdown code blocks
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            content = content.rsplit("```", 1)[0]
        parsed = json.loads(content)
    except json.JSONDecodeError:
        logger.error("Claude response is geen geldige JSON: %s", content[:500])
        return _fallback_response(dossier_id, target_id, context)

    merged_data = parsed.get("merged_data", {})
    velden = parsed.get("velden", [])

    # 6. Bouw groups (groepering voor UI)
    groups = _build_groups(velden)

    # 7. Samenvatting
    nieuw = sum(1 for v in velden if v.get("status") == "nieuw")
    bevestigd = sum(1 for v in velden if v.get("status") == "bevestigd")
    afwijkend = sum(1 for v in velden if v.get("status") == "afwijkend")

    return {
        "dossier_id": dossier_id,
        "target_id": target_id,
        "context": context,
        "merged_data": merged_data,
        "velden": velden,
        "imports": velden,  # alias — frontend verwacht "imports"
        "groups": groups,
        "toon_banner": len(velden) > 0,
        "samenvatting": {
            "nieuw": nieuw,
            "bevestigd": bevestigd,
            "afwijkend": afwijkend,
            "totaal": len(velden),
        },
    }


def _build_groups(velden: list[dict]) -> list[dict]:
    """Groepeer velden op basis van pad-prefix."""
    # Bepaal categorie uit pad
    category_map = {
        "aanvrager.persoon": "Aanvrager — Persoonsgegevens",
        "aanvrager.adresContact": "Aanvrager — Adres",
        "aanvrager.identiteit": "Aanvrager — Legitimatie",
        "aanvrager.werkgever": "Aanvrager — Werkgever",
        "partner.persoon": "Partner — Persoonsgegevens",
        "partner.adresContact": "Partner — Adres",
        "partner.identiteit": "Partner — Legitimatie",
        "partner.werkgever": "Partner — Werkgever",
        "inkomenAanvrager": "Aanvrager — Inkomen",
        "inkomenPartner": "Partner — Inkomen",
        "woningen": "Woning",
        "hypotheken": "Hypotheek",
        "hypotheekInschrijvingen": "Hypotheek",
        "verplichtingen": "Verplichtingen",
        "vermogenSectie": "Bankgegevens",
        "onderpand": "Onderpand",
        "klantGegevens": "Klantgegevens",
        "haalbaarheidsBerekeningen": "Berekening",
        "berekeningen": "Financieringsopzet",
    }

    groups_dict: dict[str, list[dict]] = {}
    for veld in velden:
        pad = veld.get("pad", "")
        # Zoek langste matchende prefix
        group_title = "Overig"
        best_len = 0
        for prefix, title in category_map.items():
            if pad.startswith(prefix) and len(prefix) > best_len:
                group_title = title
                best_len = len(prefix)

        if group_title not in groups_dict:
            groups_dict[group_title] = []
        groups_dict[group_title].append(veld)

    return [{"title": title, "items": items} for title, items in groups_dict.items()]


def _fallback_response(dossier_id: str, target_id: str | None, context: str) -> dict:
    """Fallback als Claude API niet beschikbaar is."""
    return {
        "dossier_id": dossier_id,
        "target_id": target_id,
        "context": context,
        "merged_data": {},
        "velden": [],
        "imports": [],
        "groups": [],
        "toon_banner": False,
        "samenvatting": {"nieuw": 0, "bevestigd": 0, "afwijkend": 0, "totaal": 0},
        "error": "Smart mapping niet beschikbaar (Claude API fout)",
    }


async def apply_smart_import(
    dossier_id: str,
    target_id: str,
    context: str,
    selected_pads: list[str],
) -> dict:
    """Pas geselecteerde velden toe op het target.

    1. Genereer de volledige smart import (met merged_data)
    2. Schrijf merged_data naar Supabase (alleen geselecteerde paden)
    """
    # Genereer de volledige mapping
    full = await generate_smart_import(dossier_id, target_id, context)
    merged_data = full.get("merged_data", {})
    all_velden = full.get("velden", [])

    if not merged_data:
        return {"imported": 0, "target_id": target_id, "context": context}

    # Filter: alleen geselecteerde paden
    selected_set = set(selected_pads)
    selected_velden = [v for v in all_velden if v.get("pad") in selected_set]

    if not selected_velden:
        return {"imported": 0, "target_id": target_id, "context": context}

    # Schrijf de volledige merged_data naar Supabase
    # Claude heeft al de huidige data meegenomen, dus merged_data is compleet
    headers = _sb_headers()
    if context == "aanvraag":
        table, field = "aanvragen", "data"
    else:
        table, field = "berekeningen", "invoer"

    patch_headers = {**headers, "Prefer": "return=minimal"}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.patch(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=patch_headers,
            params={"id": f"eq.{target_id}"},
            json={field: merged_data},
        )
        if resp.status_code >= 400:
            logger.error("Write %s/%s failed: %s %s", table, target_id, resp.status_code, resp.text)
            raise ValueError(f"Opslaan mislukt: {resp.text}")

    logger.info("Smart import: %d velden naar %s %s", len(selected_velden), table, target_id)

    return {
        "imported": len(selected_velden),
        "target_id": target_id,
        "context": context,
        "velden": [{"label": v["label"], "pad": v["pad"]} for v in selected_velden],
    }
