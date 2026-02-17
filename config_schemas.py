"""
Pydantic validatie-modellen voor bewerkbare config-bestanden.
Gebruikt door PUT /config/{name} endpoint.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional


# --- fiscaal-frontend.json ---

class FiscaalFrontendParameters(BaseModel):
    nhgGrens: int = Field(ge=0, le=2_000_000)
    nhgProvisie: float = Field(ge=0, le=0.1)
    belastingtariefBox1: float = Field(ge=0, le=1)
    belastingtariefBox1Hoog: float = Field(ge=0, le=1)
    grensBox1Hoog: int = Field(ge=0)
    aowLeeftijdJaren: int = Field(ge=60, le=75)
    aowLeeftijdMaanden: int = Field(ge=0, le=11)
    overdrachtsbelastingWoning: float = Field(ge=0, le=0.5)
    overdrachtsbelastingOverig: float = Field(ge=0, le=0.5)
    startersVrijstellingGrens: int = Field(ge=0)
    startersMaxLeeftijd: int = Field(ge=0, le=100)
    standaardLooptijdJaren: int = Field(ge=1, le=50)
    standaardLooptijdMaanden: int = Field(ge=1, le=600)
    toetsrente: float = Field(ge=0, le=20)
    bkrForfait: int = Field(ge=0)
    taxatiekosten: int = Field(ge=0)
    hypotheekadvieskosten: int = Field(ge=0)
    jaar: int = Field(ge=2024, le=2030)
    datumIngang: str


class FiscaalFrontendAowBedragen(BaseModel):
    alleenstaand: int = Field(ge=0)
    samenwonend: int = Field(ge=0)
    toelichting: str


class WoonquoteStaffel(BaseModel):
    grens: int = Field(ge=0)
    quote: float = Field(ge=0, le=1)


class WoonquoteTabel(BaseModel):
    toelichting: str
    staffels: List[WoonquoteStaffel] = Field(min_length=1)
    rentecorrectie_basis: float = Field(ge=0, le=20)
    rentecorrectie_factor: float = Field(ge=0, le=1)
    box3_reductie: float = Field(ge=0, le=1)
    box3_minimum: float = Field(ge=0, le=1)
    box1_minimum: float = Field(ge=0, le=1)


class FiscaalFrontendConfig(BaseModel):
    versie: str
    laatst_bijgewerkt: str
    beschrijving: str
    parameters: FiscaalFrontendParameters
    aow_jaarbedragen: FiscaalFrontendAowBedragen
    woonquote_tabel: Optional[WoonquoteTabel] = None


# --- fiscaal.json ---

class FiscaalDefaults(BaseModel):
    c_toets_rente: float = Field(ge=0, le=0.20)
    c_actuele_10jr_rente: float = Field(ge=0, le=0.20)
    c_rvp_toets_rente: int = Field(ge=0, le=600)
    c_factor_2e_inkomen: float = Field(ge=0, le=2.0)
    c_lpt: int = Field(ge=1, le=600)
    c_alleen_grens_o: float = Field(ge=0)
    c_alleen_grens_b: float = Field(ge=0)
    c_alleen_factor: float = Field(ge=0)


class FiscaalConfig(BaseModel):
    versie: str
    laatst_bijgewerkt: str
    beschrijving: str
    defaults: FiscaalDefaults


# --- geldverstrekkers.json ---

class GeldverstrekkersConfig(BaseModel):
    versie: str
    laatst_bijgewerkt: str
    beschrijving: str
    geldverstrekkers: List[str] = Field(min_length=1)
    productlijnen: Dict[str, List[str]]


# Schema lookup per config-naam
CONFIG_SCHEMAS = {
    "fiscaal-frontend": FiscaalFrontendConfig,
    "fiscaal": FiscaalConfig,
    "geldverstrekkers": GeldverstrekkersConfig,
}
