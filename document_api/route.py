"""Document API endpoints — upload, lijst, en completheidscheck."""

import logging

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from document_api import service
from document_api.schemas import (
    DocumentLijstResponse,
    DocumentRecord,
    DocumentUploadResponse,
    OntbrekendDocument,
    OntbrekendResponse,
)

logger = logging.getLogger("nat-api.document-api")

router = APIRouter(prefix="/documents", tags=["documents"])


def _extract_access_token(request: Request) -> str | None:
    """Haal Supabase session token uit Authorization header."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    dossier_id: str = Form(...),
    categorie: str | None = Form(None),
    persoon: str = Form("gezamenlijk"),
    document_type: str | None = Form(None),
):
    """Upload een document naar SharePoint en registreer in de database.

    Het bestand wordt geüpload naar de juiste submap in de klantmap op SharePoint
    en geregistreerd in de `documents` tabel in Supabase.
    """
    access_token = _extract_access_token(request)

    # Validatie: bestandsgrootte
    content = await file.read()
    if len(content) < service.MIN_FILE_SIZE:
        raise HTTPException(400, f"Bestand te klein (min {service.MIN_FILE_SIZE // 1024} KB)")
    if len(content) > service.MAX_FILE_SIZE:
        raise HTTPException(400, f"Bestand te groot (max {service.MAX_FILE_SIZE // (1024*1024)} MB)")

    # Validatie: bestandstype
    content_type = file.content_type or "application/octet-stream"
    if content_type not in service.ALLOWED_MIME_TYPES:
        raise HTTPException(
            400,
            f"Ongeldig bestandstype: {content_type}. "
            f"Toegestaan: PDF, JPG, PNG, TIFF, DOCX, XLSX, DOC, XLS",
        )

    # Validatie: persoon
    if persoon not in ("aanvrager", "partner", "gezamenlijk"):
        raise HTTPException(400, f"Ongeldige persoon: {persoon}")

    try:
        result = await service.upload_document(
            dossier_id=dossier_id,
            bestandsnaam=file.filename or "document",
            content=content,
            content_type=content_type,
            access_token=access_token,
            categorie=categorie,
            persoon=persoon,
            document_type=document_type,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.error("Document upload mislukt: %s", e)
        raise HTTPException(500, f"Upload mislukt: {e}")

    return DocumentUploadResponse(
        id=result.get("id", ""),
        bestandsnaam=result.get("bestandsnaam", ""),
        sharepoint_pad=result.get("sharepoint_pad"),
        categorie=result.get("categorie", "Overig"),
        status=result.get("status", "pending"),
    )


@router.get("/{dossier_id}", response_model=DocumentLijstResponse)
async def lijst_documenten(dossier_id: str, request: Request):
    """Haal alle documenten op voor een dossier."""
    access_token = _extract_access_token(request)

    try:
        docs = await service.lijst_documenten(dossier_id, access_token)
    except Exception as e:
        logger.error("Documenten ophalen mislukt: %s", e)
        raise HTTPException(500, f"Documenten ophalen mislukt: {e}")

    records = [
        DocumentRecord(
            id=d.get("id", ""),
            dossier_id=d.get("dossier_id", ""),
            bestandsnaam=d.get("bestandsnaam", ""),
            document_type=d.get("document_type"),
            categorie=d.get("categorie", "Overig"),
            sharepoint_pad=d.get("sharepoint_pad"),
            bron=d.get("bron", "upload"),
            status=d.get("status", "pending"),
            persoon=d.get("persoon", "gezamenlijk"),
            geldigheid_maanden=d.get("geldigheid_maanden"),
            mime_type=d.get("mime_type"),
            bestandsgrootte=d.get("bestandsgrootte"),
            uploaded_at=d.get("uploaded_at"),
        )
        for d in docs
    ]

    return DocumentLijstResponse(
        dossier_id=dossier_id,
        documenten=records,
        totaal=len(records),
    )


@router.get("/{dossier_id}/ontbrekend", response_model=OntbrekendResponse)
async def ontbrekende_documenten(
    dossier_id: str,
    request: Request,
    klanttype: str = "starter",
    inkomen_type_aanvrager: str | None = None,
    inkomen_type_partner: str | None = None,
    heeft_partner: bool = False,
):
    """Check welke documenten nog ontbreken voor een dossier.

    Vergelijkt aanwezige documenten met de requirements matrix
    op basis van klanttype en inkomenstype.
    """
    access_token = _extract_access_token(request)

    # Huidige documenten ophalen
    try:
        docs = await service.lijst_documenten(dossier_id, access_token)
    except Exception as e:
        raise HTTPException(500, f"Documenten ophalen mislukt: {e}")

    # Set van aanwezige document types
    aanwezige_types = {d.get("document_type") for d in docs if d.get("document_type")}

    # Ontbrekende berekenen
    aanwezig, ontbrekend = service.bereken_ontbrekende_documenten(
        aanwezige_types=aanwezige_types,
        klanttype=klanttype,
        inkomen_type_aanvrager=inkomen_type_aanvrager,
        inkomen_type_partner=inkomen_type_partner,
        heeft_partner=heeft_partner,
    )

    totaal = len(aanwezig) + len(ontbrekend)
    percentage = round(len(aanwezig) / totaal * 100) if totaal > 0 else 0

    return OntbrekendResponse(
        dossier_id=dossier_id,
        aanwezig=aanwezig,
        ontbrekend=[OntbrekendDocument(**o) for o in ontbrekend],
        compleet_percentage=percentage,
    )
