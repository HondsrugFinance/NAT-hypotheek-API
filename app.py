"""
NAT Hypotheeknormen Calculator 2026 - FastAPI Service
API voor hypotheekberekeningen met beveiliging, logging en invoercontrole
"""

import os
import sys
import time
import json
import logging
import asyncio
from fastapi import FastAPI, HTTPException, Request, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import date
from decimal import Decimal
try:
    import sentry_sdk
    _SENTRY_DSN = os.environ.get("SENTRY_DSN")
    if _SENTRY_DSN:
        sentry_sdk.init(
            dsn=_SENTRY_DSN,
            traces_sample_rate=0.1,
            environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
            release=os.environ.get("RENDER_GIT_COMMIT", "unknown"),
        )
except ImportError:
    pass  # Sentry niet geïnstalleerd — geen monitoring

import calculator_final
import aow_calculator
import pdf_generator
import graph_client
import email_templates

# --- Fiscale defaults laden uit config (centraal beheer voor jaarwisseling) ---
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_BASE_DIR, 'config', 'fiscaal.json'), 'r', encoding='utf-8') as _f:
    _FISCAAL_CONFIG = json.load(_f)
_FISCAAL_DEFAULTS = _FISCAAL_CONFIG["defaults"]

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
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

logger.info(f"CORS allowed origins: {ALLOWED_ORIGINS} + *.lovable.app + *.lovableproject.com")

# --- Monthly costs calculator ---
from monthly_costs.routes.calculate import router as monthly_costs_router
from monthly_costs.exceptions.handlers import register_exception_handlers

app.include_router(monthly_costs_router)
register_exception_handlers(app)
logger.info("Monthly costs calculator endpoint registered: POST /calculate/monthly-costs")

# --- Adviesrapport V2 (backend-driven) ---
from adviesrapport_v2.route import router as adviesrapport_v2_router
app.include_router(adviesrapport_v2_router)
logger.info("Adviesrapport V2 endpoints registered: POST /adviesrapport-pdf-v2, POST /adviesrapport-preview-v2")

# --- Hypotheekrentes (Supabase lookup + CRUD) ---
from rentes.route import router as rentes_router
app.include_router(rentes_router)
logger.info("Rentes endpoints registered: GET /rentes/lookup, GET/POST /rentes/tarieven, GET/POST /rentes/kortingen")

# --- SharePoint klantmappen ---
from sharepoint.route import router as sharepoint_router, webhook_router
app.include_router(sharepoint_router)
app.include_router(webhook_router)
logger.info("SharePoint endpoints registered: POST /sharepoint/klantmap, GET /sharepoint/klantmap/{id}, POST /webhooks/dossier-created")

# --- Document API (upload, lijst, completheidscheck) ---
from document_api.route import router as document_router
app.include_router(document_router)
logger.info("Document API endpoints registered: POST /documents/upload, GET /documents/{id}, GET /documents/{id}/ontbrekend")

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
    org_lpt: int = Field(default=_FISCAAL_DEFAULTS.get("c_lpt", 360), ge=1, le=600)
    rest_lpt: int = Field(default=_FISCAAL_DEFAULTS.get("c_lpt", 360), ge=1, le=600)
    hoofdsom_box1: float = Field(default=0, ge=0)
    hoofdsom_box3: float = Field(default=0, ge=0)
    rvp: int = Field(default=_FISCAAL_DEFAULTS.get("c_rvp_toets_rente", 120), ge=0, le=600)
    inleg_overig: float = Field(default=0, ge=0)
    werkelijke_rente: float = Field(default=_FISCAAL_DEFAULTS.get("c_toets_rente", 0.05), ge=0, le=0.20)

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

    # Constanten (optioneel overschrijven — defaults uit config/fiscaal.json)
    c_toets_rente: float = Field(default=_FISCAAL_DEFAULTS.get("c_toets_rente", 0.05), ge=0, le=0.20)
    c_actuele_10jr_rente: float = Field(default=_FISCAAL_DEFAULTS.get("c_actuele_10jr_rente", 0.05), ge=0, le=0.20)
    c_rvp_toets_rente: int = Field(default=_FISCAAL_DEFAULTS.get("c_rvp_toets_rente", 120), ge=0, le=600)
    c_factor_2e_inkomen: float = Field(default=_FISCAAL_DEFAULTS.get("c_factor_2e_inkomen", 1.0), ge=0, le=2.0)
    c_lpt: int = Field(default=_FISCAAL_DEFAULTS.get("c_lpt", 360), ge=1, le=600)
    c_alleen_grens_o: float = Field(default=_FISCAAL_DEFAULTS.get("c_alleen_grens_o", 30000), ge=0)
    c_alleen_grens_b: float = Field(default=_FISCAAL_DEFAULTS.get("c_alleen_grens_b", 29000), ge=0)
    c_alleen_factor: float = Field(default=_FISCAAL_DEFAULTS.get("c_alleen_factor", 17000), ge=0)

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


# --- Aflosschema endpoint ---

class AflosschemaLoanPart(BaseModel):
    id: str = Field(..., description="Uniek ID van het leningdeel")
    principal: float = Field(..., gt=0, description="Hoofdsom in euro's")
    interest_rate: float = Field(..., ge=0, le=20, description="Jaarrente als percentage (bijv. 4.5)")
    term_years: int = Field(..., ge=1, le=50, description="Looptijd in jaren")
    loan_type: Literal["annuity", "linear", "interest_only"] = Field(..., description="Aflosvorm")


class AflosschemaRequest(BaseModel):
    loan_parts: List[AflosschemaLoanPart] = Field(..., min_length=1, max_length=10)


@app.post("/aflosschema")
async def aflosschema(request_body: AflosschemaRequest, request: Request):
    """
    Genereer een volledig aflosschema per leningdeel.

    Retourneert per leningdeel een maandelijks schema (rente, aflossing, restschuld)
    en totalen over de gehele looptijd.
    """
    from monthly_costs.domain.loan_calc import get_calculator

    result_parts = []

    for part in request_body.loan_parts:
        calc = get_calculator(part.loan_type)
        principal = Decimal(str(part.principal))
        annual_rate = Decimal(str(part.interest_rate)) / 100
        total_months = part.term_years * 12

        schedule = []
        total_interest = Decimal("0")
        total_principal_paid = Decimal("0")

        for month in range(1, total_months + 1):
            payment = calc.calculate_month(principal, annual_rate, part.term_years, month)
            schedule.append({
                "month": month,
                "interest": float(payment.interest_payment),
                "principal_payment": float(payment.principal_payment),
                "gross_payment": float(payment.gross_payment),
                "remaining_principal": float(payment.remaining_principal),
            })
            total_interest += payment.interest_payment
            total_principal_paid += payment.principal_payment

        result_parts.append({
            "id": part.id,
            "loan_type": part.loan_type,
            "principal": part.principal,
            "interest_rate": part.interest_rate,
            "term_years": part.term_years,
            "total_months": total_months,
            "schedule": schedule,
            "totals": {
                "total_interest": float(total_interest),
                "total_principal": float(total_principal_paid),
                "total_payments": float(total_interest + total_principal_paid),
            },
        })

    return {"loan_parts": result_parts}


if RATE_LIMITING_ENABLED:
    aflosschema = limiter.limit("30/minute")(aflosschema)


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


@app.get("/config/fiscaal-frontend")
def config_fiscaal_frontend():
    """Fiscale parameters voor de Lovable frontend UI (NHG, belasting, AOW-bedragen)."""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config', 'fiscaal-frontend.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


@app.get("/config/geldverstrekkers")
def config_geldverstrekkers():
    """Lijst van hypotheekverstrekkers en productlijnen."""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config', 'geldverstrekkers.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


@app.get("/config/dropdowns")
def config_dropdowns():
    """Alle dropdown-opties voor de Lovable frontend (beroepen, woning, instellingen)."""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config', 'dropdowns.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


@app.get("/config/versie")
def config_versie():
    """Versie-overzicht van API en configuratiebestanden."""
    # Laad versies uit frontend config-bestanden
    base_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_configs = {}
    for naam in ("fiscaal-frontend", "geldverstrekkers", "dropdowns"):
        try:
            with open(os.path.join(base_dir, 'config', f'{naam}.json'), 'r', encoding='utf-8') as f:
                frontend_configs[naam] = json.load(f).get("versie")
        except FileNotFoundError:
            frontend_configs[naam] = None

    return {
        "api_versie": "1.1.0",
        "calculator_versie": "Excel-exact 2026",
        "config_versies": {
            "energielabel": calculator_final.ENERGIELABEL_CONFIG.get("versie"),
            "studielening": calculator_final.STUDIELENING_CONFIG.get("versie"),
            "aow": aow_calculator.AOW_CONFIG.get("versie"),
            "fiscaal_frontend": frontend_configs.get("fiscaal-frontend"),
            "geldverstrekkers": frontend_configs.get("geldverstrekkers"),
            "dropdowns": frontend_configs.get("dropdowns"),
        },
    }


# --- Config PUT endpoint (admin, API-key vereist) ---

from config_schemas import CONFIG_SCHEMAS
import github_sync

EDITABLE_CONFIGS = {"fiscaal-frontend", "fiscaal", "geldverstrekkers"}


@app.put("/config/{config_name}")
async def update_config(
    config_name: str,
    body: Dict[str, Any],
    request: Request,
    api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Werk een config-bestand bij. Beveiligd met API-key.
    Schrijft naar lokaal filesystem + commit naar GitHub voor persistentie.
    """
    if config_name not in EDITABLE_CONFIGS:
        raise HTTPException(
            status_code=400,
            detail=f"Config '{config_name}' is niet bewerkbaar. "
            f"Toegestaan: {', '.join(sorted(EDITABLE_CONFIGS))}",
        )

    # Auto-set laatst_bijgewerkt (vóór validatie, zodat het veld altijd aanwezig is)
    body["laatst_bijgewerkt"] = date.today().isoformat()

    # Valideer tegen Pydantic schema
    schema = CONFIG_SCHEMAS.get(config_name)
    if schema:
        try:
            schema(**body)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Validatiefout: {str(e)}")

    # Schrijf naar lokaal filesystem
    config_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "config", f"{config_name}.json"
    )
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(body, f, indent=2, ensure_ascii=False)
        f.write("\n")

    origin = request.headers.get("origin", "onbekend")
    logger.info("Config '%s' bijgewerkt via %s", config_name, origin)

    # Commit naar GitHub (async)
    commit_msg = f"Config update: {config_name} (via admin UI)"
    github_ok = await github_sync.commit_config_to_github(
        config_name, body, commit_msg
    )

    return {
        "status": "ok",
        "config": config_name,
        "github_committed": github_ok,
        "message": f"Config '{config_name}' bijgewerkt",
    }


# Rate limit op config PUT (max 5 per minuut)
if RATE_LIMITING_ENABLED:
    update_config = limiter.limit("5/minute")(update_config)

# --- Samenvatting PDF modellen ---

class KlantGegevens(BaseModel):
    naam: str = ""
    geboortedatum: str = ""
    straat: str = ""
    postcode: str = ""
    woonplaats: str = ""
    telefoon: str = ""
    email: str = ""

class PartnerGegevens(BaseModel):
    naam: str = ""
    geboortedatum: str = ""
    straat: str = ""
    postcode: str = ""
    woonplaats: str = ""
    telefoon: str = ""
    email: str = ""

class KlantGegevensSectie(BaseModel):
    aanvrager: KlantGegevens = KlantGegevens()
    partner: Optional[PartnerGegevens] = None

class OnderpandSectie(BaseModel):
    naam: str = ""  # Scenario naam (bijv. "Huidige situatie")
    adres: str = ""
    marktwaarde: str = ""
    woz_waarde: str = ""
    woningtype: str = ""
    energielabel: str = ""
    ebv_ebb_bedrag: str = ""

class BedrijfsGegevens(BaseModel):
    naam: str = "Hondsrug Finance"
    email: str = "Info@hondsrugfinance.nl"
    telefoon: str = "+31 88 400 2700"
    kvk: str = "KVK 93276699"

class HighlightBox(BaseModel):
    label: str
    waarde: str
    toelichting: str = ""
    uitgangspunt: str = ""  # "Huidige situatie", "Toekomstige situatie", etc.

class ToelichtingSectie(BaseModel):
    paragrafen: List[str] = []

class SectieIntroTekst(BaseModel):
    paragrafen: List[str] = []
    highlight: Optional[HighlightBox] = None

class HaalbaarheidItem(BaseModel):
    label: str
    waarde: str
    is_totaal: bool = False

class HaalbaarheidSectie(BaseModel):
    naam: str
    inkomen_items: List[HaalbaarheidItem] = []
    verplichtingen_items: List[HaalbaarheidItem] = []
    max_annuitair: str = ""
    max_werkelijk: str = ""

class FinancieringItem(BaseModel):
    label: str
    waarde: str

class FinancieringSectie(BaseModel):
    naam: str
    type_label: str
    posten: List[FinancieringItem]
    totaal: str
    eigen_middelen: List[FinancieringItem] = []
    hypotheek: str

class LeningDeelPdf(BaseModel):
    naam: str
    aflosvorm: str
    looptijd: str
    rente: str
    rvp: str
    bedrag: str

class MaandlastenSectie(BaseModel):
    naam: str
    lening_delen: List[LeningDeelPdf]
    totaal_lening: str
    rente: str
    aflossing: str
    bruto: str
    renteaftrek: str
    netto: str

class SamenvattingPdfRequest(BaseModel):
    # Bestaand
    klant_naam: str = ""
    datum: str = ""
    klant_gegevens: Optional[KlantGegevensSectie] = None
    onderpand: Optional[OnderpandSectie] = None  # Backward-compatible: enkel onderpand
    onderpanden: List[OnderpandSectie] = []  # Nieuw: meerdere onderpanden (1 per berekening)
    haalbaarheid: List[HaalbaarheidSectie] = []
    financiering: List[FinancieringSectie] = []
    maandlasten: List[MaandlastenSectie] = []
    # Nieuw — alle tekst komt vanuit de frontend
    dossier_type: str = ""
    bedrijf: Optional[BedrijfsGegevens] = BedrijfsGegevens()
    toelichting: Optional[ToelichtingSectie] = None
    haalbaarheid_tekst: Optional[SectieIntroTekst] = None
    financiering_tekst: Optional[SectieIntroTekst] = None
    maandlasten_tekst: Optional[SectieIntroTekst] = None
    haalbaarheid_voetnoten: List[str] = []  # Voetnoten onder haalbaarheid cards (* / **)
    disclaimer: List[str] = []


# --- Samenvatting PDF endpoint ---

@app.post("/samenvatting-pdf")
async def samenvatting_pdf(
    request_body: SamenvattingPdfRequest,
    request: Request,
):
    """
    Genereer een PDF samenvatting van de hypotheekberekening.

    De frontend stuurt alle display-ready data (bedragen al geformateerd).
    Retourneert een PDF bestand.
    """
    origin = request.headers.get("origin", "onbekend")
    logger.info(
        "PDF generatie gestart: origin=%s, klant=%s, onderpanden=%d, onderpand=%s",
        origin,
        request_body.klant_naam or "(onbekend)",
        len(request_body.onderpanden),
        request_body.onderpand.model_dump() if request_body.onderpand else None,
    )

    try:
        data = request_body.model_dump()
        pdf_bytes = pdf_generator.genereer_samenvatting_pdf(data)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="Samenvatting hypotheekberekening - {request_body.klant_naam or "Klant"}.pdf"',
            },
        )
    except Exception as e:
        logger.error("PDF generatie mislukt: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"PDF generatie mislukt: {str(e)}",
        )


# Rate limit op PDF endpoint (zwaarder dan berekening)
if RATE_LIMITING_ENABLED:
    samenvatting_pdf = limiter.limit("30/minute")(samenvatting_pdf)


# --- Adviesrapport PDF modellen ---

class AdviesrapportMeta(BaseModel):
    title: str = "Adviesrapport Hypotheek"
    date: str = ""
    dossierNumber: str = ""
    advisor: str = ""
    customerName: str = ""
    propertyAddress: str = ""


class AdviesrapportRow(BaseModel):
    label: str = ""
    value: str = ""
    bold: bool = False
    sub: bool = False


class AdviesrapportTable(BaseModel):
    headers: List[str] = []
    rows: List[List[str]] = []
    totals: Optional[List[str]] = None


class AdviesrapportHighlight(BaseModel):
    label: str
    value: str
    note: str = ""
    status: str = "ok"


class AdviesrapportSection(BaseModel):
    id: str
    title: str
    visible: bool = True
    narratives: List[str] = []
    rows: Optional[List[AdviesrapportRow]] = None
    tables: Optional[List[AdviesrapportTable]] = None
    highlights: Optional[List[AdviesrapportHighlight]] = None
    advisor_note: Optional[str] = None
    chart_data: Optional[Dict[str, Any]] = None
    advice_text: Optional[List[str]] = None
    subsections: Optional[List[Dict[str, Any]]] = None
    columns: Optional[List[Dict[str, Any]]] = None
    scenario_checks: Optional[List[Dict[str, Any]]] = None
    mortgage_summary: Optional[List[AdviesrapportRow]] = None


class AdviesrapportPdfRequest(BaseModel):
    meta: AdviesrapportMeta = AdviesrapportMeta()
    bedrijf: Optional[BedrijfsGegevens] = BedrijfsGegevens()
    sections: List[AdviesrapportSection] = []


# --- Adviesrapport PDF endpoint ---

@app.post("/adviesrapport-pdf")
async def adviesrapport_pdf(
    request_body: AdviesrapportPdfRequest,
    request: Request,
):
    """
    Genereer een adviesrapport PDF.

    De frontend stuurt alle display-ready data (bedragen al geformateerd).
    Secties zijn generiek: id, title, narratives, rows, tables, highlights.
    Retourneert een PDF bestand.
    """
    origin = request.headers.get("origin", "onbekend")
    logger.info(
        "Adviesrapport PDF gestart: origin=%s, klant=%s, secties=%d",
        origin,
        request_body.meta.customerName or "(onbekend)",
        len(request_body.sections),
    )

    try:
        data = request_body.model_dump(exclude_none=True)
        pdf_bytes = pdf_generator.genereer_adviesrapport_pdf(data)
        klant_naam = request_body.meta.customerName or "klant"
        filename = f"Adviesrapport hypotheek - {klant_naam}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except Exception as e:
        logger.error("Adviesrapport PDF mislukt: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Adviesrapport PDF generatie mislukt: {str(e)}",
        )


# Rate limit op adviesrapport PDF endpoint
if RATE_LIMITING_ENABLED:
    adviesrapport_pdf = limiter.limit("10/minute")(adviesrapport_pdf)


# --- Risk Scenarios endpoint ---

import risk_scenarios


class RiskHypotheekDeel(BaseModel):
    """Hypotheekdeel met rente_aftrekbaar_tot voor risk scenarios."""
    aflos_type: str = "Annuïteit"
    org_lpt: int = Field(default=_FISCAAL_DEFAULTS.get("c_lpt", 360), ge=1, le=600)
    rest_lpt: int = Field(default=_FISCAAL_DEFAULTS.get("c_lpt", 360), ge=1, le=600)
    hoofdsom_box1: float = Field(default=0, ge=0)
    hoofdsom_box3: float = Field(default=0, ge=0)
    rvp: int = Field(default=_FISCAAL_DEFAULTS.get("c_rvp_toets_rente", 120), ge=0, le=600)
    inleg_overig: float = Field(default=0, ge=0)
    werkelijke_rente: float = Field(default=_FISCAAL_DEFAULTS.get("c_toets_rente", 0.05), ge=0, le=0.20)
    rente_aftrekbaar_tot: Optional[str] = None  # YYYY-MM-DD

    @field_validator("aflos_type")
    @classmethod
    def validate_aflos_type(cls, v: str) -> str:
        if v not in VALID_AFLOS_TYPES:
            raise ValueError(
                f"Ongeldig aflostype '{v}'. Toegestaan: {', '.join(VALID_AFLOS_TYPES)}"
            )
        return v


class RiskScenariosRequest(BaseModel):
    """Request voor risico-scenario berekeningen (AOW + overlijden + AO)."""
    # Hypotheekdelen met aftrekbaar-tot datum
    hypotheek_delen: List[RiskHypotheekDeel] = Field(default_factory=list, max_length=10)
    ingangsdatum_hypotheek: str  # YYYY-MM-DD

    # Persoonsgegevens
    geboortedatum_aanvrager: str  # YYYY-MM-DD
    inkomen_aanvrager_huidig: float = Field(ge=0, le=10_000_000)
    inkomen_aanvrager_aow: float = Field(ge=0, le=10_000_000)
    alleenstaande: str = "JA"

    # Partner (optioneel)
    geboortedatum_partner: Optional[str] = None
    inkomen_partner_huidig: float = Field(default=0, ge=0, le=10_000_000)
    inkomen_partner_aow: float = Field(default=0, ge=0, le=10_000_000)

    # Overlijdensscenario (alleen bij stel)
    nabestaandenpensioen_bij_overlijden_aanvrager: float = Field(
        default=0, ge=0, le=10_000_000,
        description="Jaarbedrag partnerpensioen dat partner ontvangt bij overlijden aanvrager"
    )
    nabestaandenpensioen_bij_overlijden_partner: float = Field(
        default=0, ge=0, le=10_000_000,
        description="Jaarbedrag partnerpensioen dat aanvrager ontvangt bij overlijden partner"
    )
    heeft_kind_onder_18: bool = Field(
        default=False,
        description="Thuiswonend kind onder 18 (voor ANW-recht)"
    )
    geboortedatum_jongste_kind: Optional[str] = Field(
        default=None,
        description="YYYY-MM-DD, voor ANW einddatum berekening"
    )

    # AO-scenario — inkomensverdeling (bruto jaarbedragen)
    inkomen_loondienst_aanvrager: float = Field(default=0, ge=0, le=10_000_000)
    inkomen_onderneming_aanvrager: float = Field(default=0, ge=0, le=10_000_000)
    inkomen_roz_aanvrager: float = Field(default=0, ge=0, le=10_000_000)
    inkomen_overig_aanvrager: float = Field(
        default=0, ge=0, le=10_000_000,
        description="Niet door AO beïnvloed (lijfrente, huur, etc.)"
    )
    inkomen_loondienst_partner: float = Field(default=0, ge=0, le=10_000_000)
    inkomen_onderneming_partner: float = Field(default=0, ge=0, le=10_000_000)
    inkomen_roz_partner: float = Field(default=0, ge=0, le=10_000_000)
    inkomen_overig_partner: float = Field(default=0, ge=0, le=10_000_000)

    # AO-scenario — parameters
    ao_percentage: float = Field(default=50, ge=0, le=100)
    benutting_rvc_percentage: float = Field(default=50, ge=0, le=100)
    loondoorbetaling_pct_jaar1_aanvrager: float = Field(default=1.0, ge=0, le=2.0)
    loondoorbetaling_pct_jaar2_aanvrager: float = Field(default=0.70, ge=0, le=2.0)
    loondoorbetaling_pct_jaar1_partner: float = Field(default=1.0, ge=0, le=2.0)
    loondoorbetaling_pct_jaar2_partner: float = Field(default=0.70, ge=0, le=2.0)

    # AO-scenario — verzekeringen (bruto jaarbedragen)
    aov_dekking_bruto_jaar_aanvrager: float = Field(default=0, ge=0, le=10_000_000)
    aov_dekking_bruto_jaar_partner: float = Field(default=0, ge=0, le=10_000_000)
    woonlastenverzekering_ao_bruto_jaar: float = Field(default=0, ge=0, le=10_000_000)

    # WW-scenario — verzekeringen (bruto jaarbedragen)
    woonlastenverzekering_ww_bruto_jaar: float = Field(default=0, ge=0, le=10_000_000)

    # AO-scenario — arbeidsverleden (voor LGU-duur)
    arbeidsverleden_jaren_tm_2015: int = Field(default=10, ge=0, le=50)
    arbeidsverleden_jaren_vanaf_2016: int = Field(default=5, ge=0, le=20)

    # Werkloosheid — arbeidsverleden (voor WW-duur)
    arbeidsverleden_jaren_totaal_aanvrager: int = Field(default=0, ge=0, le=50)
    arbeidsverleden_pre2016_boven10_aanvrager: int = Field(default=0, ge=0, le=40)
    arbeidsverleden_vanaf2016_boven10_aanvrager: int = Field(default=0, ge=0, le=20)
    arbeidsverleden_jaren_totaal_partner: int = Field(default=0, ge=0, le=50)
    arbeidsverleden_pre2016_boven10_partner: int = Field(default=0, ge=0, le=40)
    arbeidsverleden_vanaf2016_boven10_partner: int = Field(default=0, ge=0, le=20)

    # Berekening parameters
    toetsrente: float = Field(default=_FISCAAL_DEFAULTS.get("c_toets_rente", 0.05), ge=0, le=0.20)
    geadviseerd_hypotheekbedrag: float = Field(default=0, ge=0)

    # Woning / verplichtingen
    energielabel: Optional[str] = "Geen (geldig) Label"
    verduurzamings_maatregelen: float = Field(default=0, ge=0, le=1_000_000)
    limieten_bkr_geregistreerd: float = Field(default=0, ge=0, le=10_000_000)
    studievoorschot_studielening: float = Field(default=0, ge=0, le=100_000)
    erfpachtcanon_per_jaar: float = Field(default=0, ge=0, le=100_000)
    jaarlast_overige_kredieten: float = Field(default=0, ge=0, le=100_000)

    @field_validator("alleenstaande")
    @classmethod
    def validate_alleenstaande(cls, v: str) -> str:
        if v not in ("JA", "NEE"):
            raise ValueError("alleenstaande moet 'JA' of 'NEE' zijn")
        return v


@app.post("/calculate/risk-scenarios")
async def calculate_risk_scenarios(
    request_body: RiskScenariosRequest,
    request: Request,
):
    """
    Bereken maximale hypotheek bij risico-scenario's.

    Retourneert AOW-scenario's (geprojecteerde hypotheek op AOW-datum)
    en overlijdensscenario's (bij stellen, hypotheek op startdatum).
    """
    origin = request.headers.get("origin", "onbekend")
    logger.info(
        "Risk scenarios gestart: origin=%s, aanvrager_geb=%s, alleenstaande=%s",
        origin,
        request_body.geboortedatum_aanvrager,
        request_body.alleenstaande,
    )

    try:
        # Hypotheekdelen naar dict formaat
        delen = [d.model_dump() for d in request_body.hypotheek_delen]

        all_scenarios = []

        # --- AOW scenario's ---
        aow_result = risk_scenarios.bereken_aow_scenarios(
            hypotheek_delen=delen,
            ingangsdatum_hypotheek=request_body.ingangsdatum_hypotheek,
            geboortedatum_aanvrager=request_body.geboortedatum_aanvrager,
            inkomen_aanvrager_huidig=request_body.inkomen_aanvrager_huidig,
            inkomen_aanvrager_aow=request_body.inkomen_aanvrager_aow,
            alleenstaande=request_body.alleenstaande,
            geboortedatum_partner=request_body.geboortedatum_partner,
            inkomen_partner_huidig=request_body.inkomen_partner_huidig,
            inkomen_partner_aow=request_body.inkomen_partner_aow,
            toetsrente=request_body.toetsrente,
            energielabel=request_body.energielabel,
            verduurzamings_maatregelen=request_body.verduurzamings_maatregelen,
            limieten_bkr_geregistreerd=request_body.limieten_bkr_geregistreerd,
            studievoorschot_studielening=request_body.studievoorschot_studielening,
            erfpachtcanon_per_jaar=request_body.erfpachtcanon_per_jaar,
            jaarlast_overige_kredieten=request_body.jaarlast_overige_kredieten,
            geadviseerd_hypotheekbedrag=request_body.geadviseerd_hypotheekbedrag,
        )
        all_scenarios.extend(aow_result.get('scenarios', []))

        # --- Overlijdensscenario's (alleen bij stel) ---
        if (request_body.alleenstaande == "NEE"
                and request_body.geboortedatum_partner):
            overlijden_result = risk_scenarios.bereken_overlijdens_scenarios(
                hypotheek_delen=delen,
                geboortedatum_aanvrager=request_body.geboortedatum_aanvrager,
                inkomen_aanvrager_huidig=request_body.inkomen_aanvrager_huidig,
                geboortedatum_partner=request_body.geboortedatum_partner,
                inkomen_partner_huidig=request_body.inkomen_partner_huidig,
                nabestaandenpensioen_bij_overlijden_aanvrager=request_body.nabestaandenpensioen_bij_overlijden_aanvrager,
                nabestaandenpensioen_bij_overlijden_partner=request_body.nabestaandenpensioen_bij_overlijden_partner,
                heeft_kind_onder_18=request_body.heeft_kind_onder_18,
                geboortedatum_jongste_kind=request_body.geboortedatum_jongste_kind,
                toetsrente=request_body.toetsrente,
                energielabel=request_body.energielabel,
                verduurzamings_maatregelen=request_body.verduurzamings_maatregelen,
                limieten_bkr_geregistreerd=request_body.limieten_bkr_geregistreerd,
                studievoorschot_studielening=request_body.studievoorschot_studielening,
                erfpachtcanon_per_jaar=request_body.erfpachtcanon_per_jaar,
                jaarlast_overige_kredieten=request_body.jaarlast_overige_kredieten,
                geadviseerd_hypotheekbedrag=request_body.geadviseerd_hypotheekbedrag,
            )
            all_scenarios.extend(overlijden_result.get('scenarios', []))

        # --- AO-scenario's ---
        # Alleen als er inkomensverdeling is opgegeven (loondienst/onderneming/roz)
        has_ao_income = (
            request_body.inkomen_loondienst_aanvrager > 0
            or request_body.inkomen_onderneming_aanvrager > 0
            or request_body.inkomen_roz_aanvrager > 0
            or request_body.inkomen_loondienst_partner > 0
            or request_body.inkomen_onderneming_partner > 0
            or request_body.inkomen_roz_partner > 0
        )
        if has_ao_income:
            ao_result = risk_scenarios.bereken_ao_scenarios(
                hypotheek_delen=delen,
                ingangsdatum_hypotheek=request_body.ingangsdatum_hypotheek,
                geboortedatum_aanvrager=request_body.geboortedatum_aanvrager,
                alleenstaande=request_body.alleenstaande,
                geboortedatum_partner=request_body.geboortedatum_partner,
                inkomen_loondienst_aanvrager=request_body.inkomen_loondienst_aanvrager,
                inkomen_onderneming_aanvrager=request_body.inkomen_onderneming_aanvrager,
                inkomen_roz_aanvrager=request_body.inkomen_roz_aanvrager,
                inkomen_overig_aanvrager=request_body.inkomen_overig_aanvrager,
                inkomen_loondienst_partner=request_body.inkomen_loondienst_partner,
                inkomen_onderneming_partner=request_body.inkomen_onderneming_partner,
                inkomen_roz_partner=request_body.inkomen_roz_partner,
                inkomen_overig_partner=request_body.inkomen_overig_partner,
                ao_percentage=request_body.ao_percentage,
                benutting_rvc_percentage=request_body.benutting_rvc_percentage,
                loondoorbetaling_pct_jaar1_aanvrager=request_body.loondoorbetaling_pct_jaar1_aanvrager,
                loondoorbetaling_pct_jaar2_aanvrager=request_body.loondoorbetaling_pct_jaar2_aanvrager,
                loondoorbetaling_pct_jaar1_partner=request_body.loondoorbetaling_pct_jaar1_partner,
                loondoorbetaling_pct_jaar2_partner=request_body.loondoorbetaling_pct_jaar2_partner,
                aov_dekking_bruto_jaar_aanvrager=request_body.aov_dekking_bruto_jaar_aanvrager,
                aov_dekking_bruto_jaar_partner=request_body.aov_dekking_bruto_jaar_partner,
                woonlastenverzekering_ao_bruto_jaar=request_body.woonlastenverzekering_ao_bruto_jaar,
                arbeidsverleden_jaren_tm_2015=request_body.arbeidsverleden_jaren_tm_2015,
                arbeidsverleden_jaren_vanaf_2016=request_body.arbeidsverleden_jaren_vanaf_2016,
                toetsrente=request_body.toetsrente,
                energielabel=request_body.energielabel,
                verduurzamings_maatregelen=request_body.verduurzamings_maatregelen,
                limieten_bkr_geregistreerd=request_body.limieten_bkr_geregistreerd,
                studievoorschot_studielening=request_body.studievoorschot_studielening,
                erfpachtcanon_per_jaar=request_body.erfpachtcanon_per_jaar,
                jaarlast_overige_kredieten=request_body.jaarlast_overige_kredieten,
                geadviseerd_hypotheekbedrag=request_body.geadviseerd_hypotheekbedrag,
            )
            all_scenarios.extend(ao_result.get('scenarios', []))

        # --- Werkloosheidsscenario's ---
        if has_ao_income:
            ww_result = risk_scenarios.bereken_werkloosheid_scenarios(
                hypotheek_delen=delen,
                ingangsdatum_hypotheek=request_body.ingangsdatum_hypotheek,
                geboortedatum_aanvrager=request_body.geboortedatum_aanvrager,
                alleenstaande=request_body.alleenstaande,
                geboortedatum_partner=request_body.geboortedatum_partner,
                inkomen_loondienst_aanvrager=request_body.inkomen_loondienst_aanvrager,
                inkomen_onderneming_aanvrager=request_body.inkomen_onderneming_aanvrager,
                inkomen_roz_aanvrager=request_body.inkomen_roz_aanvrager,
                inkomen_overig_aanvrager=request_body.inkomen_overig_aanvrager,
                inkomen_loondienst_partner=request_body.inkomen_loondienst_partner,
                inkomen_onderneming_partner=request_body.inkomen_onderneming_partner,
                inkomen_roz_partner=request_body.inkomen_roz_partner,
                inkomen_overig_partner=request_body.inkomen_overig_partner,
                arbeidsverleden_jaren_totaal_aanvrager=request_body.arbeidsverleden_jaren_totaal_aanvrager,
                arbeidsverleden_pre2016_boven10_aanvrager=request_body.arbeidsverleden_pre2016_boven10_aanvrager,
                arbeidsverleden_vanaf2016_boven10_aanvrager=request_body.arbeidsverleden_vanaf2016_boven10_aanvrager,
                arbeidsverleden_jaren_totaal_partner=request_body.arbeidsverleden_jaren_totaal_partner,
                arbeidsverleden_pre2016_boven10_partner=request_body.arbeidsverleden_pre2016_boven10_partner,
                arbeidsverleden_vanaf2016_boven10_partner=request_body.arbeidsverleden_vanaf2016_boven10_partner,
                woonlastenverzekering_ww_bruto_jaar=request_body.woonlastenverzekering_ww_bruto_jaar,
                toetsrente=request_body.toetsrente,
                energielabel=request_body.energielabel,
                verduurzamings_maatregelen=request_body.verduurzamings_maatregelen,
                limieten_bkr_geregistreerd=request_body.limieten_bkr_geregistreerd,
                studievoorschot_studielening=request_body.studievoorschot_studielening,
                erfpachtcanon_per_jaar=request_body.erfpachtcanon_per_jaar,
                jaarlast_overige_kredieten=request_body.jaarlast_overige_kredieten,
                geadviseerd_hypotheekbedrag=request_body.geadviseerd_hypotheekbedrag,
            )
            all_scenarios.extend(ww_result.get('scenarios', []))

        logger.info(
            "Risk scenarios klaar: %d scenario's",
            len(all_scenarios),
        )
        return {
            "scenarios": all_scenarios,
            "geadviseerd_hypotheekbedrag": request_body.geadviseerd_hypotheekbedrag,
        }

    except Exception as e:
        logger.error("Risk scenarios mislukt: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Risk scenario berekening mislukt: {str(e)}",
        )


# Rate limit op risk scenarios endpoint
if RATE_LIMITING_ENABLED:
    calculate_risk_scenarios = limiter.limit("10/minute")(calculate_risk_scenarios)


# --- E-mail draft endpoint ---

class DraftEmailRequest(BaseModel):
    """Request om een concept e-mail aan te maken met de samenvatting PDF."""
    sender_email: str  # M365 e-mail van de ingelogde adviseur
    email_subject: Optional[str] = None  # Override onderwerp (anders automatisch)
    pdf_data: SamenvattingPdfRequest  # Alle data voor PDF generatie


@app.post("/email/draft-samenvatting")
async def email_draft_samenvatting(
    request_body: DraftEmailRequest,
    request: Request,
    api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Genereer de samenvatting PDF en maak een concept e-mail aan in Outlook.

    Vereist:
    - Azure Graph API credentials geconfigureerd op de server
    - API key (X-API-Key header)
    - sender_email moet een geldig M365 postvak zijn in de tenant
    """
    # Check of Graph API geconfigureerd is
    if not graph_client.is_configured():
        raise HTTPException(
            status_code=503,
            detail="E-mail integratie is niet geconfigureerd (Azure credentials ontbreken)",
        )

    origin = request.headers.get("origin", "onbekend")
    logger.info(
        "E-mail draft gestart: origin=%s, sender=%s, klant=%s",
        origin,
        request_body.sender_email,
        request_body.pdf_data.klant_naam or "(onbekend)",
    )

    # Stap 1: Genereer PDF (hergebruik bestaande code)
    try:
        pdf_data = request_body.pdf_data.model_dump()
        pdf_bytes = pdf_generator.genereer_samenvatting_pdf(pdf_data)
    except Exception as e:
        logger.error("PDF generatie mislukt voor e-mail draft: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"PDF generatie mislukt: {str(e)}")

    # Stap 2: Ontvangers ophalen
    recipients = []
    if request_body.pdf_data.klant_gegevens:
        aanvrager = request_body.pdf_data.klant_gegevens.aanvrager
        if aanvrager and aanvrager.email:
            recipients.append(aanvrager.email)
        partner = request_body.pdf_data.klant_gegevens.partner
        if partner and partner.email and partner.email not in recipients:
            recipients.append(partner.email)

    if not recipients:
        raise HTTPException(
            status_code=422,
            detail="Geen ontvanger e-mailadres gevonden (klant_gegevens.aanvrager.email is leeg)",
        )

    # Stap 3: E-mail opbouwen
    klant_naam = request_body.pdf_data.klant_naam or (
        request_body.pdf_data.klant_gegevens.aanvrager.naam
        if request_body.pdf_data.klant_gegevens
        else "klant"
    )
    subject = request_body.email_subject or f"Samenvatting hypotheekberekening - {klant_naam}"
    body_html = email_templates.samenvatting_email_body(
        klant_naam=klant_naam,
        sender_email=request_body.sender_email,
    )

    # Stap 4: Concept e-mail aanmaken in Outlook via Graph API
    try:
        result = await graph_client.create_draft_with_attachment(
            sender_email=request_body.sender_email,
            to_recipients=recipients,
            subject=subject,
            body_html=body_html,
            attachment_name=f"Samenvatting hypotheekberekening - {klant_naam}.pdf",
            attachment_bytes=pdf_bytes,
        )
    except graph_client.GraphAPIError as e:
        logger.error("Graph API fout: %s (status=%s)", e.message, e.status_code)
        raise HTTPException(
            status_code=502,
            detail=f"Outlook draft aanmaken mislukt: {e.message}",
        )

    logger.info(
        "E-mail draft aangemaakt: message_id=%s, recipients=%s",
        result.get("message_id", "?")[:30],
        recipients,
    )

    return {
        "status": "ok",
        "message": "Concept e-mail aangemaakt in Outlook",
        "message_id": result["message_id"],
        "web_link": result.get("web_link", ""),
        "recipients": recipients,
        "attachment_size_bytes": len(pdf_bytes),
    }


# Rate limit op email draft endpoint
if RATE_LIMITING_ENABLED:
    email_draft_samenvatting = limiter.limit("10/minute")(email_draft_samenvatting)


# ───────────────────────────────────────────────────────────────
# Calcasa Desktop Taxatie — Modelwaarde endpoint
# ───────────────────────────────────────────────────────────────

class TaxatieModelwaardeRequest(BaseModel):
    """Request voor Calcasa modelwaarde bepaling."""
    postcode: str = Field(..., min_length=6, max_length=7, description="Postcode (bijv. 9472VM)")
    huisnummer: int = Field(..., ge=1, le=99999, description="Huisnummer")
    toevoeging: Optional[str] = Field(default=None, description="Huisnummer toevoeging (bijv. A)")


_calcasa_client = None


def _get_calcasa_client():
    """Lazy-load Calcasa client (singleton). Herautht automatisch bij verlopen token."""
    global _calcasa_client
    if _calcasa_client is None:
        try:
            from Calcasa.calcasa_client import CalcasaClient
            _calcasa_client = CalcasaClient()
            _calcasa_client.refresh_access_token()
            logger.info("Calcasa client geinitialiseerd en token vernieuwd")
        except Exception as e:
            logger.error("Calcasa client init mislukt: %s", e)
            _calcasa_client = None
    return _calcasa_client


@app.post("/taxatie/modelwaarde")
async def taxatie_modelwaarde(
    request_body: TaxatieModelwaardeRequest,
    request: Request,
) -> Dict[str, Any]:
    """
    Bepaal de Calcasa modelmatige woningwaarde voor een adres.

    Gebruikt de Calcasa Desktop Taxatie API om de modelwaarde te achterhalen.
    Gratis — er wordt geen taxatie uitgevoerd.
    """
    origin = request.headers.get("origin", "onbekend")
    logger.info(
        "Modelwaarde gestart: origin=%s, postcode=%s, huisnummer=%s",
        origin, request_body.postcode, request_body.huisnummer,
    )

    client = _get_calcasa_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Calcasa service niet beschikbaar. Controleer CALCASA_REFRESH_TOKEN.",
        )

    try:
        # Adres zoeken
        postcode = request_body.postcode.upper().replace(" ", "")
        adressen = client.zoek_adressen(postcode)
        if not adressen:
            raise HTTPException(status_code=404, detail=f"Geen adressen gevonden voor postcode {postcode}")

        # Huisnummer matchen
        adres = None
        for a in adressen:
            if a.get("huisnummer") == request_body.huisnummer:
                if request_body.toevoeging:
                    if a.get("toevoeging", "").upper() == request_body.toevoeging.upper():
                        adres = a
                        break
                elif not a.get("toevoeging"):
                    adres = a
                    break

        if not adres:
            beschikbaar = sorted(set(
                f"{a.get('huisnummer', '?')}{a.get('toevoeging', '')}"
                for a in adressen
            ))
            raise HTTPException(
                status_code=404,
                detail=f"Huisnummer {request_body.huisnummer}{request_body.toevoeging or ''} niet gevonden. "
                       f"Beschikbaar: {', '.join(beschikbaar[:20])}",
            )

        # Modelwaarde bepalen
        result = client.bepaal_modelwaarde("ing", adres["id"])

        response = {
            "adres": {
                "straat": adres.get("straat"),
                "huisnummer": adres.get("huisnummer"),
                "toevoeging": adres.get("toevoeging"),
                "postcode": adres.get("postcode"),
                "plaats": adres.get("plaats"),
            },
        }

        if result.get("modelwaarde"):
            response["modelwaarde"] = result["modelwaarde"]
            response["max_hypotheek_90"] = round(result["modelwaarde"] * result.get("max_ltv", 0.9))
            response["ltv_percentage"] = result.get("ltv_percentage")
            response["max_ltv"] = result.get("max_ltv")
            logger.info(
                "Modelwaarde geslaagd: %s %s = EUR %s",
                adres.get("straat"), adres.get("huisnummer"), result["modelwaarde"],
            )
        else:
            response["modelwaarde"] = None
            response["error"] = result.get("error", "Modelwaarde kon niet worden bepaald")
            logger.warning(
                "Modelwaarde niet beschikbaar: %s %s - %s",
                adres.get("straat"), adres.get("huisnummer"), result.get("error"),
            )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Modelwaarde mislukt: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Modelwaarde bepaling mislukt: {str(e)}")


# Adres zoeken endpoint (voor autocomplete)
@app.get("/taxatie/adressen")
async def taxatie_adressen(
    postcode: str,
    request: Request,
) -> Dict[str, Any]:
    """Zoek adressen op postcode voor de taxatie module."""
    client = _get_calcasa_client()
    if client is None:
        raise HTTPException(status_code=503, detail="Calcasa service niet beschikbaar")

    try:
        adressen = client.zoek_adressen(postcode.upper().replace(" ", ""))
        return {
            "postcode": postcode.upper().replace(" ", ""),
            "adressen": [
                {
                    "straat": a.get("straat"),
                    "huisnummer": a.get("huisnummer"),
                    "toevoeging": a.get("toevoeging"),
                    "postcode": a.get("postcode"),
                    "plaats": a.get("plaats"),
                }
                for a in adressen
            ],
        }
    except Exception as e:
        logger.error("Adressen zoeken mislukt: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Adressen zoeken mislukt: {str(e)}")


# ── WOZ Waardeloket ───────────────────────────────────────

from WOZ.woz_client import WOZClient as _WOZClient


class WOZRequest(BaseModel):
    """Request voor WOZ-waarde opvragen."""
    postcode: str = Field(..., min_length=6, max_length=7, description="Postcode (bijv. 9472VM)")
    huisnummer: int = Field(..., ge=1, le=99999, description="Huisnummer")
    toevoeging: Optional[str] = Field(default=None, description="Huisnummer toevoeging (bijv. A)")


@app.post("/woz/waarde")
async def woz_waarde(
    request_body: WOZRequest,
    request: Request,
) -> Dict[str, Any]:
    """
    Haal WOZ-waarden op voor een adres via het WOZ Waardeloket (Kadaster).

    Gratis, geen API key nodig. Retourneert alle beschikbare WOZ-waarden
    (peildatum 2014 t/m heden).
    """
    origin = request.headers.get("origin", "onbekend")
    logger.info(
        "WOZ opvragen: origin=%s, postcode=%s, huisnummer=%s, toevoeging=%s",
        origin, request_body.postcode, request_body.huisnummer, request_body.toevoeging,
    )

    try:
        client = _WOZClient()
        result = client.opvragen(
            request_body.postcode,
            request_body.huisnummer,
            request_body.toevoeging,
        )

        if "error" in result:
            logger.warning("WOZ niet gevonden: %s", result["error"])
            raise HTTPException(status_code=404, detail=result["error"])

        logger.info(
            "WOZ geslaagd: %s %s, %s = EUR %s (peildatum %s)",
            result["adres"].get("straat"),
            result["adres"].get("huisnummer"),
            result["adres"].get("woonplaats"),
            result.get("meest_recente_waarde"),
            result.get("meest_recente_peildatum"),
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("WOZ opvragen mislukt: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"WOZ opvragen mislukt: {str(e)}")


# ── EP-Online Energielabel ────────────────────────────────

from energielabel.ep_online_client import EPOnlineClient as _EPOnlineClient


class EnergielabelRequest(BaseModel):
    """Request voor energielabel opvragen via EP-Online."""
    postcode: str = Field(..., min_length=6, max_length=7, description="Postcode (bijv. 9472VM)")
    huisnummer: int = Field(..., ge=1, le=99999, description="Huisnummer")
    huisletter: Optional[str] = Field(default=None, description="Huisletter (bijv. A)")
    toevoeging: Optional[str] = Field(default=None, description="Huisnummer toevoeging (bijv. 02)")


@app.get("/energielabel")
async def energielabel_opvragen(
    postcode: str,
    huisnummer: int,
    huisletter: Optional[str] = None,
    toevoeging: Optional[str] = None,
    request: Request = None,
) -> Dict[str, Any]:
    """
    Haal het energielabel op voor een adres via EP-Online (RVO).

    Gratis API — vereist EP_ONLINE_API_KEY env var.
    Retourneert labelklasse (A t/m G) + mapping naar config-waarde.
    """
    origin = request.headers.get("origin", "onbekend") if request else "onbekend"
    logger.info(
        "Energielabel opvragen: origin=%s, postcode=%s, huisnummer=%s",
        origin, postcode, huisnummer,
    )

    client = _EPOnlineClient()
    if not client.is_configured:
        raise HTTPException(
            status_code=503,
            detail="EP-Online service niet beschikbaar. Controleer EP_ONLINE_API_KEY.",
        )

    try:
        result = client.opvragen(postcode, huisnummer, huisletter, toevoeging)

        if "error" in result:
            logger.warning("Energielabel niet gevonden: %s", result["error"])
            raise HTTPException(status_code=404, detail=result["error"])

        logger.info(
            "Energielabel geslaagd: %s %s, %s = %s (config: %s)",
            result["adres"].get("straat"),
            result["adres"].get("huisnummer"),
            result["adres"].get("plaats"),
            result.get("labelklasse"),
            result.get("labelklasse_config"),
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Energielabel opvragen mislukt: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Energielabel opvragen mislukt: {str(e)}")


if RATE_LIMITING_ENABLED:
    taxatie_modelwaarde = limiter.limit("30/minute")(taxatie_modelwaarde)
    taxatie_adressen = limiter.limit("30/minute")(taxatie_adressen)
    woz_waarde = limiter.limit("30/minute")(woz_waarde)
    energielabel_opvragen = limiter.limit("30/minute")(energielabel_opvragen)


# ── Onderpand Lookup (gecombineerd) ──────────────────────


class OnderpandLookupRequest(BaseModel):
    """Request voor gecombineerde onderpand-lookup (Calcasa + WOZ + Energielabel)."""
    postcode: str = Field(..., min_length=6, max_length=7, description="Postcode (bijv. 9472VM)")
    huisnummer: int = Field(..., ge=1, le=99999, description="Huisnummer")
    toevoeging: Optional[str] = Field(default=None, description="Huisnummer toevoeging (bijv. A of 02)")


async def _lookup_calcasa(postcode: str, huisnummer: int, toevoeging: Optional[str]) -> Dict[str, Any]:
    """Calcasa modelwaarde opvragen. Retourneert dict met resultaat of error."""
    try:
        client = _get_calcasa_client()
        if client is None:
            return {"modelwaarde": None, "error": "Calcasa service niet beschikbaar"}

        adressen = client.zoek_adressen(postcode)
        if not adressen:
            return {"modelwaarde": None, "error": f"Geen adressen gevonden voor {postcode}"}

        adres = None
        for a in adressen:
            if a.get("huisnummer") == huisnummer:
                if toevoeging:
                    if (a.get("toevoeging") or "").upper() == toevoeging.upper():
                        adres = a
                        break
                elif not a.get("toevoeging"):
                    adres = a
                    break

        if not adres:
            return {"modelwaarde": None, "error": f"Huisnummer {huisnummer}{toevoeging or ''} niet gevonden"}

        result = client.bepaal_modelwaarde("ing", adres["id"])

        if result.get("modelwaarde"):
            return {
                "modelwaarde": result["modelwaarde"],
                "adres": {
                    "straat": adres.get("straat"),
                    "huisnummer": adres.get("huisnummer"),
                    "toevoeging": adres.get("toevoeging"),
                    "postcode": adres.get("postcode"),
                    "plaats": adres.get("plaats"),
                },
            }
        else:
            return {"modelwaarde": None, "error": result.get("error", "Modelwaarde niet bepaald")}
    except Exception as e:
        logger.warning("Onderpand lookup — Calcasa mislukt: %s", e)
        return {"modelwaarde": None, "error": str(e)}


async def _lookup_woz(postcode: str, huisnummer: int, toevoeging: Optional[str]) -> Dict[str, Any]:
    """WOZ-waarde opvragen. Retourneert dict met resultaat of error."""
    try:
        client = _WOZClient()
        result = client.opvragen(postcode, huisnummer, toevoeging)

        if "error" in result:
            return {"woz_waarde": None, "error": result["error"]}

        return {
            "woz_waarde": result.get("meest_recente_waarde"),
            "woz_peildatum": result.get("meest_recente_peildatum"),
            "adres": result.get("adres"),
        }
    except Exception as e:
        logger.warning("Onderpand lookup — WOZ mislukt: %s", e)
        return {"woz_waarde": None, "error": str(e)}


async def _lookup_energielabel(
    postcode: str, huisnummer: int, toevoeging: Optional[str],
) -> Dict[str, Any]:
    """Energielabel opvragen. Retourneert dict met resultaat of error."""
    try:
        client = _EPOnlineClient()
        if not client.is_configured:
            return {"labelklasse": None, "error": "EP-Online niet geconfigureerd"}

        result = client.opvragen(postcode, huisnummer, huisletter=None, toevoeging=toevoeging)

        if "error" in result:
            # Geen label gevonden → "geen_label" zodat frontend dropdown juiste waarde toont
            return {
                "labelklasse": "geen_label",
                "labelklasse_config": "Geen (geldig) Label",
                "error": result["error"],
            }

        return {
            "labelklasse": result.get("labelklasse"),
            "labelklasse_config": result.get("labelklasse_config"),
            "registratiedatum": result.get("registratiedatum"),
            "geldig_tot": result.get("geldig_tot"),
            "bouwjaar": result.get("bouwjaar"),
        }
    except Exception as e:
        logger.warning("Onderpand lookup — Energielabel mislukt: %s", e)
        return {"labelklasse": None, "error": str(e)}


@app.post("/onderpand/lookup")
async def onderpand_lookup(
    request_body: OnderpandLookupRequest,
    request: Request,
) -> Dict[str, Any]:
    """
    Gecombineerde onderpand-lookup: haalt Calcasa modelwaarde, WOZ-waarde
    en energielabel parallel op voor één adres.

    Elke bron die faalt retourneert null + error — de andere bronnen
    worden gewoon geleverd.
    """
    origin = request.headers.get("origin", "onbekend")
    postcode = request_body.postcode.upper().replace(" ", "")
    huisnummer = request_body.huisnummer
    toevoeging = request_body.toevoeging

    logger.info(
        "Onderpand lookup: origin=%s, postcode=%s, huisnummer=%s, toevoeging=%s",
        origin, postcode, huisnummer, toevoeging,
    )

    # Alle drie parallel ophalen
    calcasa_result, woz_result, energie_result = await asyncio.gather(
        _lookup_calcasa(postcode, huisnummer, toevoeging),
        _lookup_woz(postcode, huisnummer, toevoeging),
        _lookup_energielabel(postcode, huisnummer, toevoeging),
    )

    # Adres samenstellen uit eerste beschikbare bron
    adres = (
        calcasa_result.get("adres")
        or woz_result.get("adres")
        or {"postcode": postcode, "huisnummer": huisnummer, "toevoeging": toevoeging}
    )

    response = {
        "adres": adres,
        "calcasa": {
            "modelwaarde": calcasa_result.get("modelwaarde"),
            "error": calcasa_result.get("error"),
        },
        "woz": {
            "waarde": woz_result.get("woz_waarde"),
            "peildatum": woz_result.get("woz_peildatum"),
            "error": woz_result.get("error"),
        },
        "energielabel": {
            "labelklasse": energie_result.get("labelklasse"),
            "labelklasse_config": energie_result.get("labelklasse_config"),
            "registratiedatum": energie_result.get("registratiedatum"),
            "geldig_tot": energie_result.get("geldig_tot"),
            "bouwjaar": energie_result.get("bouwjaar"),
            "error": energie_result.get("error"),
        },
    }

    logger.info(
        "Onderpand lookup klaar: %s %s %s — calcasa=%s, woz=%s, label=%s",
        adres.get("straat", "?"), huisnummer, adres.get("plaats", "?"),
        calcasa_result.get("modelwaarde", "FOUT"),
        woz_result.get("woz_waarde", "FOUT"),
        energie_result.get("labelklasse", "FOUT"),
    )

    return response


if RATE_LIMITING_ENABLED:
    onderpand_lookup = limiter.limit("30/minute")(onderpand_lookup)
