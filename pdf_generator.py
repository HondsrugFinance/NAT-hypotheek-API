"""
PDF generator voor hypotheekrapporten.
Rendert Jinja2 HTML-templates en converteert naar PDF via WeasyPrint.

Ondersteunt:
- Samenvatting Hypotheekberekening (samenvatting.html)
- Adviesrapport Hypotheek (adviesrapport.html)
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


def _fix_toelichting_paragrafen(data: dict) -> None:
    """Fix toelichting paragrafen: zorg dat de onderdelen-lijst als HTML bullets wordt gerenderd."""
    toelichting = data.get("toelichting")
    if not toelichting or not toelichting.get("paragrafen"):
        return

    onderdelen = [
        ("Maximaal haalbare hypotheek", "een indicatie van het maximale hypotheekbedrag op basis van inkomen en financiële verplichtingen."),
        ("Financieringsopzet", "een overzicht van de totale financieringsbehoefte en de opbouw van de hypotheek, inclusief kosten en eventuele eigen middelen."),
        ("Maandlasten", "een indicatie van de verwachte bruto en netto maandlasten."),
    ]

    nieuwe_paragrafen = []
    for p in toelichting["paragrafen"]:
        # Skip paragrafen die al HTML-lijsten bevatten
        if "<ul" in p:
            nieuwe_paragrafen.append(p)
            continue

        # Detecteer de paragraaf met de drie onderdelen als platte tekst
        if "Maximaal haalbare hypotheek" in p and "Financieringsopzet" in p and "Maandlasten" in p:
            # Vervang door HTML-lijst (intro-zin staat al in vorige paragraaf)
            items = "".join(
                f'<li><strong>{naam}</strong> — {beschrijving}</li>'
                for naam, beschrijving in onderdelen
            )
            nieuwe_paragrafen.append(f'<ul style="margin: 4px 0; padding-left: 20px;">{items}</ul>')
            continue

        # Ongewijzigd doorlaten
        nieuwe_paragrafen.append(p)

    toelichting["paragrafen"] = nieuwe_paragrafen


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
    _fix_toelichting_paragrafen(data)

    # Render HTML
    template = jinja_env.get_template("samenvatting.html")
    html_string = template.render(**data)

    # Converteer naar PDF (base_url zodat relatieve paden zoals assets/logo.png werken)
    pdf_bytes = HTML(string=html_string, base_url=TEMPLATES_DIR).write_pdf()

    logger.info(
        "PDF gegenereerd: %d bytes, klant=%s",
        len(pdf_bytes),
        data.get("klant_naam", "(onbekend)"),
    )
    return pdf_bytes


def genereer_adviesrapport_pdf(data: dict) -> bytes:
    """
    Genereer een adviesrapport PDF.

    Args:
        data: Dict met meta, bedrijf, sections[] (PdfReport structuur).
              Alle bedragen zijn al geformateerd als strings door de frontend.

    Returns:
        PDF als bytes.
    """
    # Vul defaults aan
    meta = data.get("meta", {})
    if not meta.get("date"):
        meta["date"] = date.today().strftime("%d-%m-%Y")
        data["meta"] = meta

    # Render HTML
    template = jinja_env.get_template("adviesrapport.html")
    html_string = template.render(**data)

    # Converteer naar PDF
    pdf_bytes = HTML(string=html_string, base_url=TEMPLATES_DIR).write_pdf()

    logger.info(
        "Adviesrapport PDF gegenereerd: %d bytes, klant=%s",
        len(pdf_bytes),
        meta.get("customerName", "(onbekend)"),
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
