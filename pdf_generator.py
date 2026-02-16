"""
PDF generator voor Samenvatting Hypotheekberekening.
Rendert een Jinja2 HTML-template en converteert naar PDF via WeasyPrint.
"""

import os
import base64
import logging
from datetime import date

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

logger = logging.getLogger("nat-api.pdf")

# --- Pad-constanten ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
LOGO_PATH = os.path.join(TEMPLATES_DIR, "assets", "hondsrug-logo.png")

# --- Logo als base64 laden (eenmalig bij import) ---
LOGO_BASE64 = ""
try:
    with open(LOGO_PATH, "rb") as f:
        LOGO_BASE64 = base64.b64encode(f.read()).decode("utf-8")
    logger.info("Logo geladen: %s", LOGO_PATH)
except FileNotFoundError:
    logger.warning("Logo niet gevonden: %s", LOGO_PATH)

# --- Jinja2 environment ---
jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=True,
)


def genereer_samenvatting_pdf(data: dict) -> bytes:
    """
    Genereer een PDF samenvatting van de hypotheekberekening.

    Args:
        data: Dict met klant_naam, datum, haalbaarheid[], financiering[], maandlasten[]
              Alle bedragen zijn al geformateerd als strings door de frontend.

    Returns:
        PDF als bytes.
    """
    # Vul defaults aan
    if not data.get("datum"):
        data["datum"] = date.today().strftime("%d-%m-%Y")
    data["jaar"] = date.today().year
    data["logo_base64"] = LOGO_BASE64

    # Render HTML
    template = jinja_env.get_template("samenvatting.html")
    html_string = template.render(**data)

    # Converteer naar PDF
    pdf_bytes = HTML(string=html_string).write_pdf()

    logger.info(
        "PDF gegenereerd: %d bytes, klant=%s",
        len(pdf_bytes),
        data.get("klant_naam", "(onbekend)"),
    )
    return pdf_bytes


def genereer_samenvatting_html(data: dict) -> str:
    """
    Genereer alleen de HTML (voor testen zonder WeasyPrint).

    Args:
        data: Zelfde als genereer_samenvatting_pdf.

    Returns:
        HTML string.
    """
    if not data.get("datum"):
        data["datum"] = date.today().strftime("%d-%m-%Y")
    data["jaar"] = date.today().year
    data["logo_base64"] = LOGO_BASE64

    template = jinja_env.get_template("samenvatting.html")
    return template.render(**data)
