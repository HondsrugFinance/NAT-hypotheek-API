"""Import service — vergelijk extracties met aanvraag/berekening en importeer velden.

Drie functies:
1. available_imports() — wat is er beschikbaar vs wat is er al ingevuld
2. import_fields() — importeer geselecteerde velden naar aanvraag
3. compare_field() — vergelijk een enkel veld
"""

import logging
import os
from datetime import datetime

import httpx

logger = logging.getLogger("nat-api.import-service")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")


def _sb_headers(access_token: str | None = None) -> dict:
    key = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
    token = access_token or key
    return {
        "apikey": key,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


async def get_available_imports(
    dossier_id: str,
    aanvraag_id: str | None = None,
    access_token: str | None = None,
) -> dict:
    """Vergelijk beschikbare extracties met huidige aanvraag/berekening data.

    Returns:
        {
            "dossier_id": "...",
            "aanvraag_id": "...",
            "documenten_verwerkt": 9,
            "laatste_verwerking": "2026-03-27T...",
            "imports": [
                {
                    "veld": "brutoJaarsalaris",
                    "sectie": "werkgeversverklaring",
                    "waarde_extractie": 58752,
                    "waarde_huidig": null,
                    "status": "nieuw",  // "nieuw", "bevestigd", "afwijkend", "niet_beschikbaar"
                    "bron_document": "WGV - Denise Uilenberg",
                    "confidence": 0.95,
                    "persoon": "aanvrager",
                },
                ...
            ],
            "samenvatting": {
                "nieuw": 23,
                "bevestigd": 12,
                "afwijkend": 3,
                "totaal": 38,
            }
        }
    """
    headers = _sb_headers(access_token)

    # Haal alle extracted_fields op voor dit dossier
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/extracted_fields",
            headers=headers,
            params={
                "select": "id,sectie,persoon,fields,field_confidence,status,created_at",
                "dossier_id": f"eq.{dossier_id}",
                "status": "in.(pending_review,accepted)",
                "order": "created_at.desc",
            },
        )
        resp.raise_for_status()
        all_fields = resp.json()

    # Haal IBL resultaten op
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/extracted_fields",
            headers=headers,
            params={
                "select": "id,sectie,persoon,fields,field_confidence,status,created_at",
                "dossier_id": f"eq.{dossier_id}",
                "sectie": "eq.inkomen_ibl",
                "order": "created_at.desc",
            },
        )
        resp.raise_for_status()
        ibl_fields = resp.json()
        all_fields.extend(ibl_fields)

    # Haal huidige aanvraag data op (als aanvraag_id gegeven)
    huidige_data = {}
    if aanvraag_id:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/aanvragen",
                headers=headers,
                params={"select": "data", "id": f"eq.{aanvraag_id}"},
            )
            resp.raise_for_status()
            rows = resp.json()
            if rows:
                huidige_data = rows[0].get("data", {}) or {}

    # Haal dossier-analyse op voor samenvatting
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/dossier_analysis",
            headers=headers,
            params={
                "select": "samenvatting,compleetheid,inkomen_analyse,documenten_verwerkt,updated_at",
                "dossier_id": f"eq.{dossier_id}",
                "order": "updated_at.desc",
                "limit": "1",
            },
        )
        resp.raise_for_status()
        analysis = resp.json()

    # Bouw import-overzicht per veld
    imports = []
    seen_fields = set()  # Voorkom dubbelen (nieuwste wint)

    for ef in all_fields:
        sectie = ef.get("sectie", "")
        persoon = ef.get("persoon", "aanvrager")
        fields = ef.get("fields", {})
        confidences = ef.get("field_confidence", {})
        created = ef.get("created_at", "")

        for veld, waarde in fields.items():
            if waarde is None:
                continue

            field_key = f"{sectie}.{persoon}.{veld}"
            if field_key in seen_fields:
                continue  # Al gezien (nieuwere versie)
            seen_fields.add(field_key)

            # Vergelijk met huidige aanvraag data
            waarde_huidig = _find_in_aanvraag(huidige_data, veld, persoon, sectie)
            confidence = confidences.get(veld, 0.5)

            if waarde_huidig is None:
                status = "nieuw"
            elif _values_match(waarde, waarde_huidig):
                status = "bevestigd"
            else:
                status = "afwijkend"

            imports.append({
                "veld": veld,
                "sectie": sectie,
                "persoon": persoon,
                "waarde_extractie": waarde,
                "waarde_huidig": waarde_huidig,
                "status": status,
                "confidence": confidence if isinstance(confidence, (int, float)) else 0.5,
                "bron_datum": created,
            })

    # Samenvatting
    nieuw = sum(1 for i in imports if i["status"] == "nieuw")
    bevestigd = sum(1 for i in imports if i["status"] == "bevestigd")
    afwijkend = sum(1 for i in imports if i["status"] == "afwijkend")

    # Dossier-analyse info
    analysis_data = analysis[0] if analysis else {}
    inkomen = analysis_data.get("inkomen_analyse", {})

    return {
        "dossier_id": dossier_id,
        "aanvraag_id": aanvraag_id,
        "documenten_verwerkt": analysis_data.get("documenten_verwerkt", len(all_fields)),
        "laatste_verwerking": analysis_data.get("updated_at"),
        "dossier_samenvatting": analysis_data.get("samenvatting"),
        "inkomen_analyse": inkomen,
        "imports": imports,
        "samenvatting": {
            "nieuw": nieuw,
            "bevestigd": bevestigd,
            "afwijkend": afwijkend,
            "totaal": len(imports),
        },
    }


def _find_in_aanvraag(data: dict, veld: str, persoon: str, sectie: str):
    """Zoek een veld in de aanvraag data structuur."""
    if not data:
        return None

    # Directe match
    if veld in data:
        return data[veld]

    # Zoek in persoon-specifieke secties
    if persoon == "aanvrager":
        aanvrager = data.get("aanvrager", {})
        for sub in [aanvrager, aanvrager.get("persoon", {}), aanvrager.get("werkgever", {}),
                     aanvrager.get("adresContact", {})]:
            if isinstance(sub, dict) and veld in sub:
                return sub[veld]

        # Zoek in inkomenAanvrager
        for item in data.get("inkomenAanvrager", []):
            if isinstance(item, dict):
                if veld in item:
                    return item[veld]
                for sub_key in ["loondienst", "werkgeversverklaringCalc", "ondernemingData"]:
                    sub = item.get(sub_key, {})
                    if isinstance(sub, dict) and veld in sub:
                        return sub[veld]

    elif persoon == "partner":
        partner = data.get("partner", {})
        for sub in [partner, partner.get("persoon", {}), partner.get("werkgever", {}),
                     partner.get("adresContact", {})]:
            if isinstance(sub, dict) and veld in sub:
                return sub[veld]

    # Zoek in onderpand
    onderpand = data.get("onderpand", {})
    if isinstance(onderpand, dict) and veld in onderpand:
        return onderpand[veld]

    # Zoek in financieringsopzet
    fin = data.get("financieringsopzet", {})
    if isinstance(fin, dict) and veld in fin:
        return fin[veld]

    return None


def _values_match(val1, val2) -> bool:
    """Vergelijk twee waarden (flexibel: string vs number, hoofdletter-insensitief)."""
    if val1 == val2:
        return True

    # String vergelijking
    s1 = str(val1).strip().lower()
    s2 = str(val2).strip().lower()
    if s1 == s2:
        return True

    # Numerieke vergelijking (tolerantie 0.01)
    try:
        n1 = float(str(val1).replace(",", ".").replace("€", "").replace(" ", ""))
        n2 = float(str(val2).replace(",", ".").replace("€", "").replace(" ", ""))
        if abs(n1 - n2) < 0.01:
            return True
    except (ValueError, TypeError):
        pass

    return False
