"""Smart mapper — vertaalt geëxtraheerde data naar formuliervelden.

Architectuur v2: AI analyseert (stap 3), Python vertaalt (dit bestand).
De Claude mapping-call is vervangen door een deterministische Python mapper.
Beslissingen (keuzemomenten) komen uit stap 3 dossier-analyse.

Flow:
1. Lees extracted_fields uit Supabase (resultaat van stap 1+2)
2. Lees beslissingen uit dossier_analysis (resultaat van stap 3)
3. Python field mapper vertaalt naar AanvraagData (instant, geen API call)
4. Resultaat in import_cache (voor instant prefill)
"""

import json
import logging
import os
from typing import Any

import httpx

from document_processing.field_mapper_v2 import map_extracted_to_form

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


async def _fetch_beslissingen(dossier_id: str) -> list[dict]:
    """Haal beslissingen op uit dossier_analysis (stap 3 output)."""
    headers = _sb_headers()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/dossier_analysis",
            headers=headers,
            params={
                "select": "beslissingen",
                "dossier_id": f"eq.{dossier_id}",
                "order": "updated_at.desc",
                "limit": "1",
            },
        )
        if resp.status_code == 200:
            rows = resp.json()
            if rows:
                return rows[0].get("beslissingen") or []
    return []


## _build_prompt en Claude mapping VERWIJDERD in v2 ##
# De Claude smart mapping call is vervangen door de deterministische Python
# field mapper (field_mapper_v2.py). Beslissingen komen uit stap 3 analyse.


async def generate_smart_import(
    dossier_id: str,
    target_id: str | None,
    context: str,
    force_refresh: bool = False,
) -> dict:
    """Genereer import-preview. Leest uit cache, tenzij force_refresh=True.

    Flow:
    1. Check cache (import_cache tabel)
    2. Als cache bestaat en niet force: vergelijk cached velden met huidige target data
    3. Als geen cache of force: draai Claude, sla op in cache

    Returns dict met merged_data, velden, imports, groups, samenvatting, toon_banner.
    """
    headers = _sb_headers()

    # --- Stap 1: check cache ---
    if not force_refresh:
        cached = await _read_cache(headers, dossier_id, context)
        if cached:
            # Vergelijk cached velden met huidige target data
            current_data = {}
            if target_id:
                current_data = await _fetch_target_data(context, target_id)

            return _build_response_from_cache(cached, current_data, dossier_id, target_id, context)

    # --- Stap 2: geen cache of force → Python field mapping ---
    result = await _run_field_mapping(dossier_id, context)

    if result is None:
        return _empty_response(dossier_id, target_id, context)

    merged_data, velden, check_vragen = result

    # --- Stap 3: sla op in cache ---
    groups = _build_groups(velden)
    await _write_cache(headers, dossier_id, context, merged_data, velden, groups, check_vragen)

    # --- Stap 4: vergelijk met huidige target data ---
    current_data = {}
    if target_id:
        current_data = await _fetch_target_data(context, target_id)

    return _build_response(merged_data, velden, current_data, dossier_id, target_id, context)


async def populate_cache(dossier_id: str):
    """Vul de cache voor beide contexten. Draai na documentverwerking."""
    for ctx in ("berekening", "aanvraag"):
        try:
            await generate_smart_import(dossier_id, None, ctx, force_refresh=True)
            logger.info("Cache gevuld voor %s context=%s", dossier_id, ctx)
        except Exception as ex:
            logger.error("Cache vullen mislukt voor %s context=%s: %s", dossier_id, ctx, ex)


async def get_prefill_data(dossier_id: str) -> dict:
    """Haal vooringevulde aanvraag-data op uit de cache. NOOIT een Claude call.

    Gelaagd systeem:
    - prefill_data: alleen zekerheden (naam, BSN, adres, etc.) — direct invullen
    - alle_data: volledige data (voor na beantwoording checkvragen)
    - check_vragen: onzekerheden als keuzevragen voor de adviseur

    Als cache gevuld → retourneer instant.
    Als cache leeg → retourneer leeg object + foutmelding.
    De cache wordt gevuld door process-all (documentverwerking), niet hier.
    """
    headers = _sb_headers()

    cached = await _read_cache(headers, dossier_id, "aanvraag")
    if cached and cached.get("merged_data"):
        velden = cached.get("velden", [])
        merged_data = cached["merged_data"]
        check_vragen = cached.get("check_vragen") or []

        return {
            "prefill_data": merged_data,
            "alle_data": merged_data,
            "check_vragen": check_vragen,
            "velden_count": len(velden),
            "check_vragen_count": len(check_vragen),
            "cached": True,
            "dossier_id": dossier_id,
        }

    # Geen cache → retourneer leeg
    return {
        "prefill_data": {},
        "alle_data": {},
        "check_vragen": [],
        "velden_count": 0,
        "check_vragen_count": 0,
        "cached": False,
        "dossier_id": dossier_id,
        "error": "Verwerk eerst documenten om gegevens automatisch in te vullen",
    }


# ---------------------------------------------------------------------------
# Cache lezen/schrijven
# ---------------------------------------------------------------------------

async def _read_cache(headers: dict, dossier_id: str, context: str) -> dict | None:
    """Lees cache uit Supabase. Returns None als niet gevonden."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/import_cache",
            headers=headers,
            params={
                "select": "merged_data,velden,groups,samenvatting,check_vragen,updated_at",
                "dossier_id": f"eq.{dossier_id}",
                "context": f"eq.{context}",
            },
        )
        if resp.status_code == 200:
            rows = resp.json()
            if rows:
                return rows[0]
    return None


async def _write_cache(
    headers: dict, dossier_id: str, context: str,
    merged_data: dict, velden: list, groups: list,
    check_vragen: list | None = None,
):
    """Schrijf cache: DELETE bestaande + INSERT nieuwe (simpel en betrouwbaar)."""
    nieuw = sum(1 for v in velden if v.get("status") == "nieuw")
    bevestigd = sum(1 for v in velden if v.get("status") == "bevestigd")
    afwijkend = sum(1 for v in velden if v.get("status") == "afwijkend")

    row = {
        "dossier_id": dossier_id,
        "context": context,
        "merged_data": merged_data,
        "velden": velden,
        "groups": groups,
        "check_vragen": check_vragen or [],
        "samenvatting": {
            "nieuw": nieuw, "bevestigd": bevestigd,
            "afwijkend": afwijkend, "totaal": len(velden),
            "check_vragen": len(check_vragen or []),
        },
    }

    async with httpx.AsyncClient(timeout=10) as client:
        # DELETE alle bestaande rows voor dit dossier+context
        await client.delete(
            f"{SUPABASE_URL}/rest/v1/import_cache",
            headers=headers,
            params={"dossier_id": f"eq.{dossier_id}", "context": f"eq.{context}"},
        )

        # INSERT nieuwe row
        resp = await client.post(
            f"{SUPABASE_URL}/rest/v1/import_cache",
            headers={**headers, "Prefer": "return=minimal"},
            json=row,
        )
        if resp.status_code >= 400:
            logger.error("Cache write failed: %s %s", resp.status_code, resp.text[:300])
        else:
            logger.info("Cache geschreven voor %s context=%s (%d velden)", dossier_id, context, len(velden))


# ---------------------------------------------------------------------------
# Python field mapping (vervangt Claude smart mapping call)
# ---------------------------------------------------------------------------

async def _run_field_mapping(dossier_id: str, context: str) -> tuple[dict, list, list] | None:
    """Deterministische field mapping. Returns (merged_data, velden, check_vragen) of None.

    Geen Claude API call — instant, deterministisch, testbaar.
    """
    extracted = await _fetch_extracted_data(dossier_id)
    if not extracted:
        return None

    # Haal beslissingen op uit stap 3 analyse
    beslissingen = await _fetch_beslissingen(dossier_id)

    # Python mapper: extracted_fields + beslissingen → formuliervelden
    merged_data, velden, check_vragen = map_extracted_to_form(extracted, beslissingen)

    if not merged_data:
        return None

    return merged_data, velden, check_vragen


# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------

def _compare_velden_with_target(velden: list[dict], current_data: dict) -> list[dict]:
    """Vergelijk cached velden met huidige target data. Update status per veld."""
    if not current_data:
        # Geen target → alles is "nieuw"
        for v in velden:
            v["status"] = "nieuw"
        return velden

    result = []
    for v in velden:
        v = {**v}  # kopie
        pad = v.get("pad", "")
        cached_value = v.get("waarde")

        # Zoek huidige waarde via pad in current_data
        current_value = _get_nested(current_data, pad)

        if current_value is None or current_value == "" or current_value == 0:
            v["status"] = "nieuw"
        elif _values_equal(cached_value, current_value):
            v["status"] = "bevestigd"
        else:
            v["status"] = "afwijkend"
            v["waarde_huidig"] = current_value
            v["huidig_display"] = _format_for_display(current_value)

        result.append(v)
    return result


def _get_nested(data: dict, pad: str):
    """Haal een waarde op uit een genest dict via dot-notatie met array-support."""
    if not data or not pad:
        return None

    parts = pad.replace("]", "").split("[")
    # "haalbaarheidsBerekeningen[0].inkomenGegevens.hoofdinkomenAanvrager"
    # → ["haalbaarheidsBerekeningen", "0", ".inkomenGegevens.hoofdinkomenAanvrager"]

    current = data
    for segment in pad.split("."):
        if not current:
            return None
        # Array index: "leningdelen[0]"
        if "[" in segment:
            key, idx = segment.split("[")
            idx = int(idx.rstrip("]"))
            current = current.get(key) if isinstance(current, dict) else None
            if isinstance(current, list) and idx < len(current):
                current = current[idx]
            else:
                return None
        elif isinstance(current, dict):
            current = current.get(segment)
        else:
            return None

    return current


def _values_equal(v1, v2) -> bool:
    """Flexibele vergelijking."""
    if v1 == v2:
        return True
    s1, s2 = str(v1).strip().lower(), str(v2).strip().lower()
    if s1 == s2:
        return True
    try:
        n1 = float(str(v1).replace(",", ".").replace("€", "").replace(" ", ""))
        n2 = float(str(v2).replace(",", ".").replace("€", "").replace(" ", ""))
        if abs(n1 - n2) < 0.01:
            return True
    except (ValueError, TypeError):
        pass
    return False


def _format_for_display(value) -> str:
    """Simpele display-formatting voor huidige waarden."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Ja" if value else "Nee"
    if isinstance(value, (int, float)) and abs(value) >= 100:
        return f"€ {value:,.0f}".replace(",", ".")
    return str(value)


def _build_response_from_cache(
    cached: dict, current_data: dict,
    dossier_id: str, target_id: str | None, context: str,
) -> dict:
    """Bouw response uit cache + vergelijking met huidige target data."""
    velden = cached.get("velden", [])
    merged_data = cached.get("merged_data", {})

    # Vergelijk met huidige data per veld
    compared = _compare_velden_with_target(velden, current_data)

    groups = _build_groups(compared)
    nieuw = sum(1 for v in compared if v.get("status") == "nieuw")
    bevestigd = sum(1 for v in compared if v.get("status") == "bevestigd")
    afwijkend = sum(1 for v in compared if v.get("status") == "afwijkend")

    return {
        "dossier_id": dossier_id,
        "target_id": target_id,
        "context": context,
        "merged_data": merged_data,
        "velden": compared,
        "imports": compared,
        "groups": groups,
        "toon_banner": len(compared) > 0,
        "cached": True,
        "cache_updated_at": cached.get("updated_at"),
        "samenvatting": {
            "nieuw": nieuw, "bevestigd": bevestigd,
            "afwijkend": afwijkend, "totaal": len(compared),
        },
    }


def _build_response(
    merged_data: dict, velden: list, current_data: dict,
    dossier_id: str, target_id: str | None, context: str,
) -> dict:
    """Bouw response van verse Claude call + vergelijking."""
    compared = _compare_velden_with_target(velden, current_data)
    groups = _build_groups(compared)
    nieuw = sum(1 for v in compared if v.get("status") == "nieuw")
    bevestigd = sum(1 for v in compared if v.get("status") == "bevestigd")
    afwijkend = sum(1 for v in compared if v.get("status") == "afwijkend")

    return {
        "dossier_id": dossier_id,
        "target_id": target_id,
        "context": context,
        "merged_data": merged_data,
        "velden": compared,
        "imports": compared,
        "groups": groups,
        "toon_banner": len(compared) > 0,
        "cached": False,
        "samenvatting": {
            "nieuw": nieuw, "bevestigd": bevestigd,
            "afwijkend": afwijkend, "totaal": len(compared),
        },
    }


def _empty_response(dossier_id: str, target_id: str | None, context: str) -> dict:
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
    check_vragen_answers: list[dict] | None = None,
) -> dict:
    """Pas ALLEEN geselecteerde velden toe op het target.

    1. Haal cached velden op (met waarden)
    2. Lees huidige data van het target
    3. Merge alleen geselecteerde velden pad-voor-pad
    4. Merge check_vragen antwoorden (pad + waarde direct van adviseur)
    5. Schrijf geüpdatete data terug
    """
    import copy

    # Stap 1: haal cached mapping op
    headers = _sb_headers()
    cached = await _read_cache(headers, dossier_id, context)
    if not cached:
        # Geen cache → genereer on-the-fly
        result = await _run_field_mapping(dossier_id, context)
        if not result:
            return {"imported": 0, "target_id": target_id, "context": context}
        _, velden, _ = result
    else:
        velden = cached.get("velden", [])

    # Filter: alleen geselecteerde paden
    selected_set = set(selected_pads)
    selected_velden = [v for v in velden if v.get("pad") in selected_set]

    if not selected_velden and not check_vragen_answers:
        return {"imported": 0, "target_id": target_id, "context": context}

    # Stap 2: lees huidige data
    current_data = await _fetch_target_data(context, target_id)
    updated = copy.deepcopy(current_data) if current_data else {}

    # Stap 3: merge alleen geselecteerde velden, pad-voor-pad
    for veld in selected_velden:
        pad = veld.get("pad", "")
        waarde = veld.get("waarde")
        if pad and waarde is not None:
            _set_nested(updated, pad, waarde)

    # Stap 4: merge check_vragen antwoorden (adviseur-keuzes)
    answers_count = 0
    if check_vragen_answers:
        for answer in check_vragen_answers:
            pad = answer.get("pad", "")
            waarde = answer.get("waarde")
            if pad and waarde is not None:
                _set_nested(updated, pad, waarde)
                answers_count += 1

    # Stap 5: schrijf terug
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
            json={field: updated},
        )
        if resp.status_code >= 400:
            logger.error("Write %s/%s failed: %s %s", table, target_id, resp.status_code, resp.text)
            raise ValueError(f"Opslaan mislukt: {resp.text}")

    total_imported = len(selected_velden) + answers_count
    logger.info("Smart import: %d velden + %d check_vragen naar %s %s",
                len(selected_velden), answers_count, table, target_id)

    return {
        "imported": total_imported,
        "target_id": target_id,
        "context": context,
        "velden": [{"label": v["label"], "pad": v["pad"]} for v in selected_velden],
        "check_vragen_applied": answers_count,
    }


def _set_nested(data: dict, pad: str, value):
    """Zet een waarde in een genest dict via dot-notatie met array-support.

    Voorbeeld: _set_nested(data, "aanvrager.persoon.achternaam", "Brust")
    Voorbeeld: _set_nested(data, "hypotheken[0].leningdelen[1].bedrag", 90390)
    """
    segments = []
    for part in pad.split("."):
        if "[" in part:
            key, rest = part.split("[", 1)
            segments.append(key)
            segments.append(int(rest.rstrip("]")))
        else:
            segments.append(part)

    current = data
    for i, segment in enumerate(segments[:-1]):
        next_segment = segments[i + 1]

        if isinstance(segment, int):
            # Array index navigatie
            while len(current) <= segment:
                current.append({})
            if i + 1 < len(segments) - 1:
                current = current[segment]
            else:
                current = current[segment]
        elif isinstance(next_segment, int):
            # Volgende is een array index → zorg dat het een list is
            if segment not in current or not isinstance(current.get(segment), list):
                current[segment] = []
            current = current[segment]
        else:
            # Volgende is een dict key
            if segment not in current or not isinstance(current.get(segment), dict):
                current[segment] = {}
            current = current[segment]

    # Zet de waarde
    last = segments[-1]
    if isinstance(last, int):
        while len(current) <= last:
            current.append({})
        current[last] = value
    else:
        current[last] = value
