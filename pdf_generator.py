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
LOGO_LIGGEND_PATH = os.path.join(TEMPLATES_DIR, "assets", "HF - liggend.png")
ILLUSTRATIE_PATH = os.path.join(TEMPLATES_DIR, "assets", "voorpagina-illustratie.jpg")

# --- Afbeeldingen als base64 laden (eenmalig bij import) ---
LOGO_BASE64 = ""
try:
    with open(LOGO_PATH, "rb") as f:
        LOGO_BASE64 = base64.b64encode(f.read()).decode("utf-8")
    logger.info("Logo geladen: %s", LOGO_PATH)
except FileNotFoundError:
    logger.warning("Logo niet gevonden: %s", LOGO_PATH)

LOGO_LIGGEND_BASE64 = ""
try:
    with open(LOGO_LIGGEND_PATH, "rb") as f:
        LOGO_LIGGEND_BASE64 = base64.b64encode(f.read()).decode("utf-8")
    logger.info("Logo liggend geladen: %s", LOGO_LIGGEND_PATH)
except FileNotFoundError:
    logger.warning("Logo liggend niet gevonden: %s", LOGO_LIGGEND_PATH)

ILLUSTRATIE_BASE64 = ""
try:
    with open(ILLUSTRATIE_PATH, "rb") as f:
        ILLUSTRATIE_BASE64 = base64.b64encode(f.read()).decode("utf-8")
    logger.info("Illustratie geladen: %s", ILLUSTRATIE_PATH)
except FileNotFoundError:
    logger.warning("Illustratie niet gevonden: %s", ILLUSTRATIE_PATH)

# --- Jinja2 environment ---
jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=True,
)


def _fix_toelichting_paragrafen(data: dict) -> None:
    """Fix toelichting paragrafen: zorg dat de onderdelen-lijst als HTML bullets wordt gerenderd.

    Ondersteunt een variabel aantal onderdelen — als de frontend alleen
    'Financieringsopzet' en 'Maandlasten' stuurt (haalbaarheid verborgen),
    wordt de lijst correct opgebouwd met alleen die items.
    """
    toelichting = data.get("toelichting")
    if not toelichting or not toelichting.get("paragrafen"):
        return

    # Bekende onderdelen die als bullet-lijst moeten worden gerenderd
    onderdelen_beschrijvingen = {
        "Maximaal haalbare hypotheek": "een indicatie van het maximale hypotheekbedrag op basis van inkomen en financiële verplichtingen.",
        "Financieringsopzet": "een overzicht van de totale financieringsbehoefte en de opbouw van de hypotheek, inclusief kosten en eventuele eigen middelen.",
        "Maandlasten": "een indicatie van de verwachte bruto en netto maandlasten.",
    }

    nieuwe_paragrafen = []
    for p in toelichting["paragrafen"]:
        # Skip paragrafen die al HTML-lijsten bevatten
        if "<ul" in p:
            nieuwe_paragrafen.append(p)
            continue

        # Detecteer de onderdelen-paragraaf: bevat " — " en minstens één
        # bekend onderdeel-label. Dit onderscheidt het van de intro-zin
        # (die geen " — " bevat).
        if "\u2014" in p or " — " in p:
            gevonden = [
                (naam, beschrijving)
                for naam, beschrijving in onderdelen_beschrijvingen.items()
                if naam in p
            ]
            if gevonden:
                items = "".join(
                    f'<li><strong>{naam}</strong> \u2014 {beschrijving}</li>'
                    for naam, beschrijving in gevonden
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

    # Afbeeldingen als base64 injecteren
    data["logo_liggend_base64"] = LOGO_LIGGEND_BASE64
    data["illustratie_base64"] = ILLUSTRATIE_BASE64

    # Genereer SVG grafieken voor secties met chart_data
    from markupsafe import Markup
    import chart_generator
    for section in data.get("sections", []):
        # Top-level chart_data
        cd = section.get("chart_data")
        if cd:
            sid = section.get("id", "")
            if sid == "retirement":
                section["chart_svg"] = Markup(chart_generator.genereer_pensioen_chart_svg(
                    jaren=cd.get("jaren", []),
                    geadviseerd_hypotheekbedrag=cd.get("geadviseerd_hypotheekbedrag", 0),
                    aow_markers=cd.get("aow_markers"),
                ))
            elif cd.get("type") == "overlijden_vergelijk":
                section["chart_svg"] = Markup(chart_generator.genereer_overlijden_vergelijk_svg(
                    huidig_max_hypotheek=cd.get("huidig_max_hypotheek", 0),
                    max_hypotheek_na_overlijden=cd.get("max_hypotheek_na_overlijden", 0),
                    geadviseerd_hypotheekbedrag=cd.get("geadviseerd_hypotheekbedrag", 0),
                    label_bar1=cd.get("label_bar1", "Huidig"),
                    label_bar2=cd.get("label_bar2", "Na overlijden"),
                ))
            elif cd.get("type") == "vergelijk_fasen":
                section["chart_svg"] = Markup(chart_generator.genereer_vergelijk_chart_svg(
                    fasen=cd.get("fasen", []),
                    geadviseerd_hypotheekbedrag=cd.get("geadviseerd_hypotheekbedrag", 0),
                ))
            else:
                section["chart_svg"] = Markup(chart_generator.genereer_risico_chart_svg(
                    scenarios=cd.get("scenarios", []),
                    geadviseerd_hypotheekbedrag=cd.get("geadviseerd_hypotheekbedrag", 0),
                ))

        # Column chart_data (overlijden/AO side-by-side)
        for col in section.get("columns", []):
            col_cd = col.get("chart_data")
            if not col_cd:
                continue
            if col_cd.get("type") == "overlijden_vergelijk":
                col["chart_svg"] = Markup(chart_generator.genereer_overlijden_vergelijk_svg(
                    huidig_max_hypotheek=col_cd.get("huidig_max_hypotheek", 0),
                    max_hypotheek_na_overlijden=col_cd.get("max_hypotheek_na_overlijden", 0),
                    geadviseerd_hypotheekbedrag=col_cd.get("geadviseerd_hypotheekbedrag", 0),
                    label_bar1=col_cd.get("label_bar1", "Huidig"),
                    label_bar2=col_cd.get("label_bar2", "Na overlijden"),
                ))
            elif col_cd.get("type") == "vergelijk_fasen":
                col["chart_svg"] = Markup(chart_generator.genereer_vergelijk_chart_svg(
                    fasen=col_cd.get("fasen", []),
                    geadviseerd_hypotheekbedrag=col_cd.get("geadviseerd_hypotheekbedrag", 0),
                ))

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
