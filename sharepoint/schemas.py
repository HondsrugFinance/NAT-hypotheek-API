"""Pydantic modellen voor SharePoint endpoints."""

from pydantic import BaseModel


class KlantmapRequest(BaseModel):
    dossier_id: str


class KlantmapResponse(BaseModel):
    dossiernummer: str
    mapnaam: str
    sharepoint_url: str
    mappen_aangemaakt: list[str]


class FolderItem(BaseModel):
    name: str
    id: str
    type: str  # "folder" of "file"
    size: int | None = None
    web_url: str | None = None
    last_modified: str | None = None
    last_modified_by: str | None = None


class KlantmapInhoudResponse(BaseModel):
    sharepoint_url: str | None
    items: list[FolderItem]


class KlantmapRenameRequest(BaseModel):
    dossier_id: str
    nieuwe_naam: str  # Naamdeel na dossiernummer, bijv. "Hall, Peter van en Hall-van der Lee, Arabella"
