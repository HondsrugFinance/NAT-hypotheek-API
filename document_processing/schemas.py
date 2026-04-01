"""Pydantic modellen voor document processing pipeline."""

from pydantic import BaseModel


class ClassificationResult(BaseModel):
    document_type: str  # key uit document_types.json
    categorie: str  # Identificatie, Inkomen, Woning, Financieel, Overig
    persoon: str  # aanvrager, partner, gezamenlijk
    confidence: float  # 0.0 - 1.0
    reasoning: str  # waarom dit type


class ExtractionResult(BaseModel):
    raw_values: dict  # {"bruto_jaarsalaris": "55000", "werkgever": "Philips"}
    computed_values: dict  # {"bruto_jaarsalaris_euro": 55000.00}
    confidence: float
    warnings: list[str]  # ["Vakantiegeld niet vermeld op document"]


class ProcessingResult(BaseModel):
    document_id: str
    status: str  # classified, extracted, error
    classification: ClassificationResult | None = None
    extraction: ExtractionResult | None = None
    new_filename: str | None = None
    new_sharepoint_pad: str | None = None
    error: str | None = None
    duration_ms: int = 0


class ResolvedValue(BaseModel):
    field_name: str
    value: str | float | bool | None
    source_document_type: str
    source_document_id: str
    confidence: float
    conflicting_values: list[dict] | None = None  # andere bronnen met afwijkende waarde


class ProcessRequest(BaseModel):
    """Request voor POST /documents/{id}/process."""
    force: bool = False  # herverwerk ook als al processed


class MergePhotosRequest(BaseModel):
    """Request voor POST /documents/merge-photos."""
    dossier_id: str
    document_ids: list[str]


class ApplyToAanvraagRequest(BaseModel):
    """DEPRECATED — gebruik ApplyImportsRequest."""
    aanvraag_id: str
    extraction_ids: list[str]


class ApplyImportsRequest(BaseModel):
    """Request voor POST /doc-processing/{dossier_id}/apply-imports."""
    target_id: str  # aanvraag_id of dossier_id (berekening)
    context: str = "aanvraag"  # "aanvraag" of "berekening"
    selected_targets: list[str]  # lijst van target-paden om te importeren
