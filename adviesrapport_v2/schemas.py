"""Pydantic modellen voor adviesrapport V2 endpoint."""

from pydantic import BaseModel, Field
from typing import Optional


class AdviesrapportOptions(BaseModel):
    """Opties die de adviseur instelt in het Lovable dialog."""

    # Klantprofiel
    doel_hypotheek: str = "Aankoop bestaande woning"
    ervaring_hypotheek: str = "Nee"
    kennis_hypotheekvormen: str = "Redelijk"
    kennis_fiscale_regels: str = "Matig"

    # Risicobereidheid tabel
    risicobereidheid: dict[str, str] = Field(
        default_factory=lambda: {
            "pensioen": "Risico een beetje beperken",
            "overlijden": "Risico zoveel mogelijk beperken",
            "arbeidsongeschiktheid": "Risico een beetje beperken",
            "werkloosheid": "Risico aanvaarden",
            "relatiebeeindiging": "Risico aanvaarden",
            "waardedaling_woning": "Risico een beetje beperken",
            "rentestijging": "Risico aanvaarden",
            "aflopen_hypotheekrenteaftrek": "Risico aanvaarden",
        }
    )

    # AO parameters
    ao_percentage: float = Field(default=50, ge=0, le=100)
    benutting_rvc_percentage: float = Field(default=50, ge=0, le=100)

    # Loondoorbetaling percentages
    loondoorbetaling_pct_jaar1_aanvrager: float = Field(default=1.0, ge=0, le=2.0)
    loondoorbetaling_pct_jaar2_aanvrager: float = Field(default=0.70, ge=0, le=2.0)
    loondoorbetaling_pct_jaar1_partner: float = Field(default=1.0, ge=0, le=2.0)
    loondoorbetaling_pct_jaar2_partner: float = Field(default=0.70, ge=0, le=2.0)

    # Arbeidsverleden
    arbeidsverleden_jaren_tm_2015: int = Field(default=10, ge=0, le=50)
    arbeidsverleden_jaren_vanaf_2016: int = Field(default=5, ge=0, le=20)
    arbeidsverleden_jaren_totaal_aanvrager: int = Field(default=0, ge=0, le=50)
    arbeidsverleden_pre2016_boven10_aanvrager: int = Field(default=0, ge=0, le=40)
    arbeidsverleden_vanaf2016_boven10_aanvrager: int = Field(default=0, ge=0, le=20)
    arbeidsverleden_jaren_totaal_partner: int = Field(default=0, ge=0, le=50)
    arbeidsverleden_pre2016_boven10_partner: int = Field(default=0, ge=0, le=40)
    arbeidsverleden_vanaf2016_boven10_partner: int = Field(default=0, ge=0, le=20)

    # Nabestaanden
    nabestaandenpensioen_bij_overlijden_aanvrager: float = Field(default=0, ge=0)
    nabestaandenpensioen_bij_overlijden_partner: float = Field(default=0, ge=0)
    heeft_kind_onder_18: bool = False
    geboortedatum_jongste_kind: Optional[str] = None

    # Verzekeringen (bruto jaarbedragen)
    aov_dekking_bruto_jaar_aanvrager: float = Field(default=0, ge=0)
    aov_dekking_bruto_jaar_partner: float = Field(default=0, ge=0)
    woonlastenverzekering_ao_bruto_jaar: float = Field(default=0, ge=0)
    woonlastenverzekering_ww_bruto_jaar: float = Field(default=0, ge=0)

    # Hypotheekverstrekker
    hypotheekverstrekker: str = "ING"
    nhg: bool = True

    # Prioriteit
    prioriteit: str = "stabiele maandlast"

    # Rapport meta (uit dialog)
    advisor_name: str = "Alex Kuijper CFP®"
    report_date: Optional[str] = None  # DD-MM-YYYY, default = vandaag
    dossier_nummer: Optional[str] = None


class AdviesrapportV2Request(BaseModel):
    """Request voor backend-driven adviesrapport generatie."""

    dossier_id: str = Field(..., description="UUID van het dossier")
    aanvraag_id: str = Field(..., description="UUID van de aanvraag")
    options: AdviesrapportOptions = Field(default_factory=AdviesrapportOptions)
