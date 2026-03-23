"""Pydantic modellen voor Document API endpoints."""

from pydantic import BaseModel


class DocumentRecord(BaseModel):
    id: str
    dossier_id: str
    bestandsnaam: str
    document_type: str | None = None
    categorie: str
    sharepoint_pad: str | None = None
    bron: str
    status: str
    persoon: str
    geldigheid_maanden: int | None = None
    mime_type: str | None = None
    bestandsgrootte: int | None = None
    uploaded_at: str | None = None


class DocumentUploadResponse(BaseModel):
    id: str
    bestandsnaam: str
    sharepoint_pad: str | None = None
    categorie: str
    status: str


class DocumentLijstResponse(BaseModel):
    dossier_id: str
    documenten: list[DocumentRecord]
    totaal: int


class OntbrekendDocument(BaseModel):
    document_type: str
    beschrijving: str
    categorie: str
    persoon: str  # "aanvrager", "partner", "gezamenlijk"


class OntbrekendResponse(BaseModel):
    dossier_id: str
    aanwezig: list[str]
    ontbrekend: list[OntbrekendDocument]
    compleet_percentage: int
