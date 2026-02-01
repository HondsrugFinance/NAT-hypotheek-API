"""
NAT Hypotheeknormen Calculator 2026 - FastAPI Service
Minimal API voor hypotheekberekeningen
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import calculator_final

app = FastAPI(
    title="NAT Hypotheeknormen Calculator 2026",
    description="Bereken maximale hypotheek volgens NAT normen 2026",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



class HypotheekDeel(BaseModel):
    """Hypotheek deel input"""
    aflos_type: str = "Annuïteit"
    org_lpt: int = 360
    rest_lpt: int = 360
    hoofdsom_box1: float = 0
    hoofdsom_box3: float = 0
    rvp: int = 120
    inleg_overig: float = 0
    werkelijke_rente: float = 0.05


class CalculateRequest(BaseModel):
    """Calculate endpoint request body"""
    # Basis inkomen
    hoofd_inkomen_aanvrager: float = 0
    hoofd_inkomen_partner: float = 0
    
    # Inkomen aanvullingen
    inkomen_uit_lijfrente_aanvrager: float = 0
    inkomen_uit_lijfrente_partner: float = 0
    ontvangen_partneralimentatie_aanvrager: float = 0
    ontvangen_partneralimentatie_partner: float = 0
    inkomsten_uit_vermogen_aanvrager: float = 0
    huurinkomsten_aanvrager: float = 0
    te_betalen_partneralimentatie_aanvrager: float = 0
    te_betalen_partneralimentatie_partner: float = 0
    inkomen_overige_aanvragers: float = 0
    
    # Status
    alleenstaande: str = "JA"
    ontvangt_aow: str = "NEE"
    
    # Energielabel
    energielabel: Optional[str] = "Geen (geldig) Label"
    verduurzamings_maatregelen: float = 0
    
    # Schulden
    limieten_bkr_geregistreerd: float = 0
    limieten_niet_bkr_geregistreerd: float = 0
    studievoorschot_studielening: float = 0
    erfpachtcanon_per_jaar: float = 0
    jaarlast_overige_kredieten: float = 0
    
    # Hypotheekdelen (max 10)
    hypotheek_delen: List[HypotheekDeel] = Field(default_factory=list)
    
    # Scenario 2 (optioneel)
    gewijzigd_hoofd_inkomen_aanvrager2: Optional[float] = None
    gewijzigd_hoofd_inkomen_partner2: Optional[float] = None
    gewijzigd_hoofd_inkomen_aow2: Optional[str] = None
    inkomen_overige_aanvragers_min2: float = 0
    
    # Constanten (optioneel overschrijven)
    c_toets_rente: float = 0.05
    c_actuele_10jr_rente: float = 0.05
    c_rvp_toets_rente: int = 120
    c_factor_2e_inkomen: float = 1.0
    c_lpt: int = 360
    c_alleen_grens_o: float = 30000
    c_alleen_grens_b: float = 29000
    c_alleen_factor: float = 17000


@app.get("/")
def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "NAT Hypotheeknormen Calculator 2026",
        "version": "1.0.0"
    }


@app.post("/calculate")
def calculate(request: CalculateRequest) -> Dict[str, Any]:
    """
    Bereken maximale hypotheek
    
    Request body: CalculateRequest model (zie schema)
    Response: {"scenario1": {...}, "scenario2": {...} | null}
    
    Scenario2 wordt alleen berekend als gewijzigd_hoofd_inkomen_aanvrager2
    of gewijzigd_hoofd_inkomen_partner2 gevuld is (niet None, niet lege string).
    """
    
    # Validatie: max 10 hypotheekdelen (truncate)
    hypotheek_delen = request.hypotheek_delen[:10]
    
    # Convert Pydantic models to dict for calculator
    hypotheek_delen_dict = [deel.model_dump() for deel in hypotheek_delen]
    
    # Build inputs dict
    inputs = {
        'hoofd_inkomen_aanvrager': request.hoofd_inkomen_aanvrager,
        'hoofd_inkomen_partner': request.hoofd_inkomen_partner,
        'inkomen_uit_lijfrente_aanvrager': request.inkomen_uit_lijfrente_aanvrager,
        'inkomen_uit_lijfrente_partner': request.inkomen_uit_lijfrente_partner,
        'ontvangen_partneralimentatie_aanvrager': request.ontvangen_partneralimentatie_aanvrager,
        'ontvangen_partneralimentatie_partner': request.ontvangen_partneralimentatie_partner,
        'inkomsten_uit_vermogen_aanvrager': request.inkomsten_uit_vermogen_aanvrager,
        'huurinkomsten_aanvrager': request.huurinkomsten_aanvrager,
        'te_betalen_partneralimentatie_aanvrager': request.te_betalen_partneralimentatie_aanvrager,
        'te_betalen_partneralimentatie_partner': request.te_betalen_partneralimentatie_partner,
        'inkomen_overige_aanvragers': request.inkomen_overige_aanvragers,
        'alleenstaande': request.alleenstaande,
        'ontvangt_aow': request.ontvangt_aow,
        'energielabel': request.energielabel,
        'verduurzamings_maatregelen': request.verduurzamings_maatregelen,
        'limieten_bkr_geregistreerd': request.limieten_bkr_geregistreerd,
        'limieten_niet_bkr_geregistreerd': request.limieten_niet_bkr_geregistreerd,
        'studievoorschot_studielening': request.studievoorschot_studielening,
        'erfpachtcanon_per_jaar': request.erfpachtcanon_per_jaar,
        'jaarlast_overige_kredieten': request.jaarlast_overige_kredieten,
        'hypotheek_delen': hypotheek_delen_dict,
        'gewijzigd_hoofd_inkomen_aanvrager2': request.gewijzigd_hoofd_inkomen_aanvrager2,
        'gewijzigd_hoofd_inkomen_partner2': request.gewijzigd_hoofd_inkomen_partner2,
        'gewijzigd_hoofd_inkomen_aow2': request.gewijzigd_hoofd_inkomen_aow2,
        'inkomen_overige_aanvragers_min2': request.inkomen_overige_aanvragers_min2,
        'c_toets_rente': request.c_toets_rente,
        'c_actuele_10jr_rente': request.c_actuele_10jr_rente,
        'c_rvp_toets_rente': request.c_rvp_toets_rente,
        'c_factor_2e_inkomen': request.c_factor_2e_inkomen,
        'c_lpt': request.c_lpt,
        'c_alleen_grens_o': request.c_alleen_grens_o,
        'c_alleen_grens_b': request.c_alleen_grens_b,
        'c_alleen_factor': request.c_alleen_factor,
    }
    
    try:
        # Run calculation
        result = calculator_final.calculate(inputs)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Calculation error: {str(e)}"
        )


@app.get("/health")
def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "woonquote_tables_loaded": hasattr(calculator_final, 'WOONQUOTE_TABLES'),
        "calculator_version": "Excel-exact 2026"
    }
