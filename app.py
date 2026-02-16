"""
NAT Hypotheeknormen Calculator 2026 - FastAPI Service
API voor hypotheekberekeningen met beveiliging, logging en invoercontrole
"""

import os
import sys
import time
import json
import logging
from fastapi import FastAPI, HTTPException, Request, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import date
import calculator_final
import aow_calculator

# --- Logging ---
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("nat-api")

# --- Startup time (voor uptime in health check) ---
START_TIME = time.time()

# --- Rate limiting ---
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    limiter = Limiter(key_func=get_remote_address)
    RATE_LIMITING_ENABLED = True
    logger.info("Rate limiting enabled")
except ImportError:
    limiter = None
    RATE_LIMITING_ENABLED = False
    logger.warning("slowapi not installed - rate limiting disabled")

# --- App ---
app = FastAPI(
    title="NAT Hypotheeknormen Calculator 2026",
    description="Bereken maximale hypotheek volgens NAT normen 2026",
    version="1.1.0",
)

# Rate limiting setup
if RATE_LIMITING_ENABLED:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- CORS ---
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "").split(",")
ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS if origin.strip()]

# Defaults als er geen env var is ingesteld
if not ALLOWED_ORIGINS:
    ALLOWED_ORIGINS = [
        "https://hondsrug-insight.lovable.app",
        "http://localhost:5173",
        "http://localhost:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.lovable\.app|https://.*\.lovableproject\.com",
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

logger.info(f"CORS allowed origins: {ALLOWED_ORIGINS} + *.lovable.app + *.lovableproject.com")

# --- API Key authenticatie ---
API_KEY = os.environ.get("NAT_API_KEY")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: Optional[str] = Security(api_key_header)):
    """Controleer API-sleutel. Slaat over als er geen sleutel is geconfigureerd."""
    if API_KEY is None:
        logger.debug("Geen API-sleutel geconfigureerd op server, alles doorlaten")
        return None
    if not api_key:
        logger.warning("API-sleutel ontbreekt in request (header X-API-Key niet meegestuurd)")
        raise HTTPException(status_code=403, detail="API-sleutel ontbreekt. Stuur header: X-API-Key")
    if api_key != API_KEY:
        logger.warning("Ongeldige API-sleutel ontvangen (lengte: %d)", len(api_key))
        raise HTTPException(status_code=403, detail="Ongeldige API-sleutel")
    return api_key


# --- Global exception handler ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Vang onverwachte fouten op en geef een nette foutmelding."""
    logger.error(f"Onverwachte fout op {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Interne rekenfout", "detail": str(exc)},
    )


# --- Constanten voor validatie (energielabels uit config) ---
VALID_ENERGIELABELS = list(calculator_final.ENERGIELABEL_CONFIG["base_bonus"].keys())

VALID_AFLOS_TYPES = ["Annuïteit", "Lineair", "Aflosvrij", "Spaarhypotheek"]


# --- Pydantic modellen met validatie ---
class HypotheekDeel(BaseModel):
    """Hypotheek deel input met invoercontrole"""
    aflos_type: str = "Annuïteit"
    org_lpt: int = Field(default=360, ge=1, le=600)
    rest_lpt: int = Field(default=360, ge=1, le=600)
    hoofdsom_box1: float = Field(default=0, ge=0)
    hoofdsom_box3: float = Field(default=0, ge=0)
    rvp: int = Field(default=120, ge=0, le=600)
    inleg_overig: float = Field(default=0, ge=0)
    werkelijke_rente: float = Field(default=0.05, ge=0, le=0.20)

    @field_validator("aflos_type")
    @classmethod
    def validate_aflos_type(cls, v: str) -> str:
        if v not in VALID_AFLOS_TYPES:
            raise ValueError(
                f"Ongeldig aflostype '{v}'. Toegestaan: {', '.join(VALID_AFLOS_TYPES)}"
            )
        return v


class CalculateRequest(BaseModel):
    """Calculate endpoint request body met invoercontrole"""
    # Basis inkomen
    hoofd_inkomen_aanvrager: float = Field(default=0, ge=0, le=10_000_000)
    hoofd_inkomen_partner: float = Field(default=0, ge=0, le=10_000_000)

    # Inkomen aanvullingen
    inkomen_uit_lijfrente_aanvrager: float = Field(default=0, ge=0, le=10_000_000)
    inkomen_uit_lijfrente_partner: float = Field(default=0, ge=0, le=10_000_000)
    ontvangen_partneralimentatie_aanvrager: float = Field(default=0, ge=0, le=10_000_000)
    ontvangen_partneralimentatie_partner: float = Field(default=0, ge=0, le=10_000_000)
    inkomsten_uit_vermogen_aanvrager: float = Field(default=0, ge=0, le=10_000_000)
    huurinkomsten_aanvrager: float = Field(default=0, ge=0, le=10_000_000)
    te_betalen_partneralimentatie_aanvrager: float = Field(default=0, ge=0, le=10_000_000)
    te_betalen_partneralimentatie_partner: float = Field(default=0, ge=0, le=10_000_000)
    inkomen_overige_aanvragers: float = Field(default=0, ge=0, le=10_000_000)

    # Status
    alleenstaande: str = "JA"
    ontvangt_aow: str = "NEE"

    # Energielabel
    energielabel: Optional[str] = "Geen (geldig) Label"
    verduurzamings_maatregelen: float = Field(default=0, ge=0, le=1_000_000)

    # Schulden
    limieten_bkr_geregistreerd: float = Field(default=0, ge=0, le=10_000_000)
    limieten_niet_bkr_geregistreerd: float = Field(default=0, ge=0, le=10_000_000)
    studievoorschot_studielening: float = Field(default=0, ge=0, le=100_000)
    erfpachtcanon_per_jaar: float = Field(default=0, ge=0, le=100_000)
    jaarlast_overige_kredieten: float = Field(default=0, ge=0, le=100_000)

    # Hypotheekdelen (max 10)
    hypotheek_delen: List[HypotheekDeel] = Field(default_factory=list, max_length=10)

    # Scenario 2 (optioneel)
    gewijzigd_hoofd_inkomen_aanvrager2: Optional[float] = None
    gewijzigd_hoofd_inkomen_partner2: Optional[float] = None
    gewijzigd_hoofd_inkomen_aow2: Optional[str] = None
    inkomen_overige_aanvragers_min2: float = Field(default=0, ge=0, le=10_000_000)

    # Constanten (optioneel overschrijven)
    c_toets_rente: float = Field(default=0.05, ge=0, le=0.20)
    c_actuele_10jr_rente: float = Field(default=0.05, ge=0, le=0.20)
    c_rvp_toets_rente: int = Field(default=120, ge=0, le=600)
    c_factor_2e_inkomen: float = Field(default=1.0, ge=0, le=2.0)
    c_lpt: int = Field(default=360, ge=1, le=600)
    c_alleen_grens_o: float = Field(default=30000, ge=0)
    c_alleen_grens_b: float = Field(default=29000, ge=0)
    c_alleen_factor: float = Field(default=17000, ge=0)

    @field_validator("alleenstaande")
    @classmethod
    def validate_alleenstaande(cls, v: str) -> str:
        if v not in ("JA", "NEE"):
            raise ValueError("alleenstaande moet 'JA' of 'NEE' zijn")
        return v

    @field_validator("ontvangt_aow")
    @classmethod
    def validate_ontvangt_aow(cls, v: str) -> str:
        if v not in ("JA", "NEE"):
            raise ValueError("ontvangt_aow moet 'JA' of 'NEE' zijn")
        return v

    @field_validator("energielabel")
    @classmethod
    def validate_energielabel(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_ENERGIELABELS:
            raise ValueError(
                f"Ongeldig energielabel '{v}'. Toegestaan: {', '.join(VALID_ENERGIELABELS)}"
            )
        return v

    @field_validator("gewijzigd_hoofd_inkomen_aow2")
    @classmethod
    def validate_aow2(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("JA", "NEE"):
            raise ValueError("gewijzigd_hoofd_inkomen_aow2 moet 'JA', 'NEE' of null zijn")
        return v


# --- Endpoints ---

@app.get("/")
def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "NAT Hypotheeknormen Calculator 2026",
        "version": "1.1.0",
    }


@app.post("/calculate")
async def calculate(
    request_body: CalculateRequest,
    request: Request,
    api_key: Optional[str] = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    Bereken maximale hypotheek

    Request body: CalculateRequest model (zie schema)
    Response: {"scenario1": {...}, "scenario2": {...} | null, "debug": {...}}

    Vereist X-API-Key header als NAT_API_KEY is geconfigureerd op de server.
    """
    origin = request.headers.get("origin", "onbekend")
    logger.info(
        "Berekening gestart: origin=%s, alleenstaande=%s, ontvangt_aow=%s, delen=%d",
        origin,
        request_body.alleenstaande,
        request_body.ontvangt_aow,
        len(request_body.hypotheek_delen),
    )

    # Convert Pydantic models to dict for calculator
    hypotheek_delen_dict = [deel.model_dump() for deel in request_body.hypotheek_delen]

    # Build inputs dict
    inputs = {
        "hoofd_inkomen_aanvrager": request_body.hoofd_inkomen_aanvrager,
        "hoofd_inkomen_partner": request_body.hoofd_inkomen_partner,
        "inkomen_uit_lijfrente_aanvrager": request_body.inkomen_uit_lijfrente_aanvrager,
        "inkomen_uit_lijfrente_partner": request_body.inkomen_uit_lijfrente_partner,
        "ontvangen_partneralimentatie_aanvrager": request_body.ontvangen_partneralimentatie_aanvrager,
        "ontvangen_partneralimentatie_partner": request_body.ontvangen_partneralimentatie_partner,
        "inkomsten_uit_vermogen_aanvrager": request_body.inkomsten_uit_vermogen_aanvrager,
        "huurinkomsten_aanvrager": request_body.huurinkomsten_aanvrager,
        "te_betalen_partneralimentatie_aanvrager": request_body.te_betalen_partneralimentatie_aanvrager,
        "te_betalen_partneralimentatie_partner": request_body.te_betalen_partneralimentatie_partner,
        "inkomen_overige_aanvragers": request_body.inkomen_overige_aanvragers,
        "alleenstaande": request_body.alleenstaande,
        "ontvangt_aow": request_body.ontvangt_aow,
        "energielabel": request_body.energielabel,
        "verduurzamings_maatregelen": request_body.verduurzamings_maatregelen,
        "limieten_bkr_geregistreerd": request_body.limieten_bkr_geregistreerd,
        "limieten_niet_bkr_geregistreerd": request_body.limieten_niet_bkr_geregistreerd,
        "studievoorschot_studielening": request_body.studievoorschot_studielening,
        "erfpachtcanon_per_jaar": request_body.erfpachtcanon_per_jaar,
        "jaarlast_overige_kredieten": request_body.jaarlast_overige_kredieten,
        "hypotheek_delen": hypotheek_delen_dict,
        "gewijzigd_hoofd_inkomen_aanvrager2": request_body.gewijzigd_hoofd_inkomen_aanvrager2,
        "gewijzigd_hoofd_inkomen_partner2": request_body.gewijzigd_hoofd_inkomen_partner2,
        "gewijzigd_hoofd_inkomen_aow2": request_body.gewijzigd_hoofd_inkomen_aow2,
        "inkomen_overige_aanvragers_min2": request_body.inkomen_overige_aanvragers_min2,
        "c_toets_rente": request_body.c_toets_rente,
        "c_actuele_10jr_rente": request_body.c_actuele_10jr_rente,
        "c_rvp_toets_rente": request_body.c_rvp_toets_rente,
        "c_factor_2e_inkomen": request_body.c_factor_2e_inkomen,
        "c_lpt": request_body.c_lpt,
        "c_alleen_grens_o": request_body.c_alleen_grens_o,
        "c_alleen_grens_b": request_body.c_alleen_grens_b,
        "c_alleen_factor": request_body.c_alleen_factor,
    }

    try:
        result = calculator_final.calculate(inputs)
        logger.info("Berekening geslaagd")
        return result
    except Exception as e:
        logger.error(f"Rekenfout: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Rekenfout: {str(e)}",
        )


# Rate limit decorator alleen als slowapi beschikbaar is
if RATE_LIMITING_ENABLED:
    calculate = limiter.limit("30/minute")(calculate)


@app.get("/health")
def health():
    """Uitgebreide health check"""
    return {
        "status": "healthy",
        "version": "1.1.0",
        "woonquote_tables_loaded": hasattr(calculator_final, "WOONQUOTE_TABLES"),
        "table_count": (
            len(calculator_final.WOONQUOTE_TABLES)
            if hasattr(calculator_final, "WOONQUOTE_TABLES")
            else 0
        ),
        "calculator_version": "Excel-exact 2026",
        "python_version": sys.version,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "rate_limiting": RATE_LIMITING_ENABLED,
        "api_key_configured": API_KEY is not None,
        "cors_origins": ALLOWED_ORIGINS,
    }


@app.get("/health/deep")
def health_deep():
    """Diepe health check — voert een proefberekening uit."""
    try:
        result = calculator_final.calculate(
            {
                "hoofd_inkomen_aanvrager": 50000,
                "alleenstaande": "JA",
                "ontvangt_aow": "NEE",
                "hypotheek_delen": [
                    {
                        "aflos_type": "Annuïteit",
                        "org_lpt": 360,
                        "rest_lpt": 360,
                        "hoofdsom_box1": 100000,
                        "hoofdsom_box3": 0,
                        "rvp": 120,
                        "inleg_overig": 0,
                        "werkelijke_rente": 0.03,
                    }
                ],
            }
        )
        # Controleer dat het resultaat er goed uitziet
        s1 = result.get("scenario1", {})
        if not s1 or "annuitair" not in s1:
            return {"status": "unhealthy", "reason": "Onvolledig resultaat"}
        return {"status": "healthy", "smoke_test": "passed"}
    except Exception as e:
        logger.error(f"Deep health check gefaald: {e}", exc_info=True)
        return {"status": "unhealthy", "reason": str(e)}


@app.get("/aow-categorie")
def aow_categorie(geboortedatum: str):
    """
    Bepaal AOW-categorie voor hypotheekberekening.

    Args:
        geboortedatum: Geboortedatum in ISO formaat (YYYY-MM-DD)

    Returns:
        {
            "categorie": "AOW_BEREIKT" | "BINNEN_10_JAAR" | "MEER_DAN_10_JAAR",
            "aow_datum": "YYYY-MM-DD",
            "jaren_tot_aow": float
        }
    """
    try:
        geboorte = date.fromisoformat(geboortedatum)
        return aow_calculator.bepaal_aow_categorie(geboorte)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Ongeldige geboortedatum. Gebruik formaat YYYY-MM-DD. Error: {str(e)}",
        )


# --- Config endpoints (publieke data, geen API-key vereist) ---

@app.get("/config/energielabel")
def config_energielabel():
    """Huidige energielabel bonussen en verduurzaming-caps."""
    return calculator_final.ENERGIELABEL_CONFIG


@app.get("/config/studielening")
def config_studielening():
    """Huidige studielening correctiefactoren per toetsrente-bracket."""
    return calculator_final.STUDIELENING_CONFIG


@app.get("/config/aow")
def config_aow():
    """Huidige AOW-leeftijden tabel."""
    return aow_calculator.AOW_CONFIG


@app.get("/config/fiscaal")
def config_fiscaal():
    """Huidige fiscale standaardwaarden voor hypotheekberekening."""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config', 'fiscaal.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


@app.get("/config/versie")
def config_versie():
    """Versie-overzicht van API en configuratiebestanden."""
    return {
        "api_versie": "1.1.0",
        "calculator_versie": "Excel-exact 2026",
        "config_versies": {
            "energielabel": calculator_final.ENERGIELABEL_CONFIG.get("versie"),
            "studielening": calculator_final.STUDIELENING_CONFIG.get("versie"),
            "aow": aow_calculator.AOW_CONFIG.get("versie"),
        },
    }
