"""Document service — upload, registratie, en completheidscheck."""

import json
import logging
import os
from pathlib import Path

import httpx

from adviesrapport_v2.supabase_client import _headers as supabase_headers, SUPABASE_URL
from graph_auth import GraphAPIError
from sharepoint import client as sp_client

logger = logging.getLogger("nat-api.document-api")

# --- Config laden ---
_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

_doc_types: dict | None = None
_doc_requirements: dict | None = None


def _load_document_types() -> dict:
    global _doc_types
    if _doc_types is None:
        path = _CONFIG_DIR / "document_types.json"
        with open(path, encoding="utf-8") as f:
            _doc_types = json.load(f)
    return _doc_types


def _load_document_requirements() -> dict:
    global _doc_requirements
    if _doc_requirements is None:
        path = _CONFIG_DIR / "document_requirements.json"
        with open(path, encoding="utf-8") as f:
            _doc_requirements = json.load(f)
    return _doc_requirements


# --- Constanten ---
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
    "application/msword",  # doc
    "application/vnd.ms-excel",  # xls
}

MIN_FILE_SIZE = 10 * 1024        # 10 KB
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB

# Categorie mapping op basis van document_type
def _categorie_voor_type(document_type: str | None) -> str:
    """Bepaal categorie op basis van document_type uit config."""
    if not document_type:
        return "Overig"
    types = _load_document_types()
    info = types.get(document_type, {})
    return info.get("submap", "Overig")


async def upload_document(
    dossier_id: str,
    bestandsnaam: str,
    content: bytes,
    content_type: str,
    access_token: str | None = None,
    categorie: str | None = None,
    persoon: str = "gezamenlijk",
    document_type: str | None = None,
) -> dict:
    """Upload een document naar SharePoint en registreer in Supabase.

    Returns:
        dict met document record velden
    """
    # Categorie bepalen
    if not categorie:
        categorie = _categorie_voor_type(document_type)

    # Dossier ophalen voor SharePoint pad
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/dossiers",
            headers=supabase_headers(access_token),
            params={
                "select": "id,dossiernummer,klant_naam,klant_contact_gegevens",
                "id": f"eq.{dossier_id}",
            },
        )
        resp.raise_for_status()
        rows = resp.json()

    if not rows:
        raise ValueError(f"Dossier niet gevonden: {dossier_id}")

    dossier = rows[0]
    dossiernummer = dossier.get("dossiernummer")

    # SharePoint upload (als geconfigureerd en dossiernummer beschikbaar)
    sharepoint_pad = None
    if sp_client.is_configured() and dossiernummer:
        klant_naam = dossier.get("klant_naam", "Onbekend")
        contact = dossier.get("klant_contact_gegevens") or {}
        aanvrager = contact.get("aanvrager", {})
        voornaam = aanvrager.get("voornaam", "")
        achternaam = aanvrager.get("achternaam", klant_naam)
        if not voornaam and " " in klant_naam:
            parts = klant_naam.split(" ", 1)
            voornaam = parts[0]
            achternaam = parts[1] if len(parts) > 1 else klant_naam

        mapnaam = f"{dossiernummer} {achternaam}, {voornaam}"
        upload_pad = f"{sp_client.SHAREPOINT_KLANTEN_ROOT}/{mapnaam}/{categorie}"

        try:
            await sp_client.upload_file(upload_pad, bestandsnaam, content, content_type)
            sharepoint_pad = f"{upload_pad}/{bestandsnaam}"
            logger.info("Document geüpload naar SharePoint: %s", sharepoint_pad)
        except GraphAPIError as e:
            logger.warning("SharePoint upload mislukt (document wordt wel geregistreerd): %s", e.message)

    # Registreer in Supabase documents tabel
    doc_record = {
        "dossier_id": dossier_id,
        "bestandsnaam": bestandsnaam,
        "document_type": document_type,
        "categorie": categorie,
        "sharepoint_pad": sharepoint_pad,
        "bron": "upload",
        "status": "pending",
        "persoon": persoon,
        "mime_type": content_type,
        "bestandsgrootte": len(content),
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/rest/v1/documents",
            headers={
                **supabase_headers(access_token),
                "Prefer": "return=representation",
            },
            json=doc_record,
        )
        resp.raise_for_status()
        created = resp.json()

    if isinstance(created, list) and created:
        created = created[0]

    logger.info("Document geregistreerd: %s (id=%s)", bestandsnaam, created.get("id", "")[:12])
    return created


async def lijst_documenten(dossier_id: str, access_token: str | None = None) -> list[dict]:
    """Haal alle documenten op voor een dossier."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/documents",
            headers=supabase_headers(access_token),
            params={
                "select": "*",
                "dossier_id": f"eq.{dossier_id}",
                "order": "uploaded_at.desc",
            },
        )
        resp.raise_for_status()
        return resp.json()


def bereken_ontbrekende_documenten(
    aanwezige_types: set[str],
    klanttype: str,
    inkomen_type_aanvrager: str | None = None,
    inkomen_type_partner: str | None = None,
    heeft_partner: bool = False,
) -> tuple[list[str], list[dict]]:
    """Bereken welke documenten ontbreken op basis van de requirements matrix.

    Returns:
        (aanwezig_lijst, ontbrekend_lijst)
    """
    requirements = _load_document_requirements()
    doc_types = _load_document_types()

    benodigde: list[dict] = []  # {"type": str, "persoon": str}

    # Basis: identificatie (per persoon)
    benodigde.append({"type": "paspoort", "persoon": "aanvrager", "of": "id_kaart"})
    if heeft_partner:
        benodigde.append({"type": "paspoort", "persoon": "partner", "of": "id_kaart"})

    # Inkomen documenten (per persoon)
    for inkomen_type, persoon_label in [
        (inkomen_type_aanvrager, "aanvrager"),
        (inkomen_type_partner, "partner"),
    ]:
        if not inkomen_type:
            continue
        inkomen_docs = requirements.get("inkomen_documents", {}).get(inkomen_type, {})
        for doc_type in inkomen_docs.get("per_persoon", []):
            benodigde.append({"type": doc_type, "persoon": persoon_label})

    # Klanttype documenten (gezamenlijk)
    klanttype_docs = requirements.get("klanttype_documents", {}).get(klanttype.lower(), {})
    for categorie_docs in klanttype_docs.values():
        if isinstance(categorie_docs, list):
            for doc_type in categorie_docs:
                benodigde.append({"type": doc_type, "persoon": "gezamenlijk"})

    # Vergelijk met aanwezige documenten
    aanwezig = []
    ontbrekend = []

    for item in benodigde:
        doc_type = item["type"]
        alternatief = item.get("of")

        if doc_type in aanwezige_types or (alternatief and alternatief in aanwezige_types):
            aanwezig.append(doc_type)
        else:
            info = doc_types.get(doc_type, {})
            ontbrekend.append({
                "document_type": doc_type,
                "beschrijving": info.get("description", doc_type),
                "categorie": info.get("submap", "Overig"),
                "persoon": item["persoon"],
            })

    return aanwezig, ontbrekend
