"""
Test V2 adviesrapport: render naar HTML voor visuele inspectie.

Draait de volledige V2 orchestrator met mock data (Harry & Harriëtte Slinger)
en rendert het resultaat als HTML (geen WeasyPrint nodig).

Gebruik: python test_render_v2.py
Output:  Adviesrapporten/v2-preview-stel.html
"""

import json
import os
import sys
import base64

# --- Mock pdf_generator vóór import orchestrator (WeasyPrint werkt niet op Windows) ---
from unittest.mock import MagicMock

captured_rapport = {}

def _capture_rapport(data: dict) -> bytes:
    """Capture rapport dict in plaats van PDF generatie."""
    captured_rapport.update(data)
    return b"%PDF-mock"

mock_pdf_gen = MagicMock()
mock_pdf_gen.genereer_adviesrapport_pdf = _capture_rapport
sys.modules["pdf_generator"] = mock_pdf_gen

# --- Nu veilig importeren ---
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup
import chart_generator

from adviesrapport_v2.report_orchestrator import generate_report
from adviesrapport_v2.schemas import AdviesrapportOptions

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")


# ═══════════════════════════════════════════════════════════════════════
# Mock data — stel (Harry & Harriëtte Slinger)
# Moet matchen met het dossier uit 21.pdf
# ═══════════════════════════════════════════════════════════════════════

MOCK_DOSSIER_STEL = {
    "invoer": {
        "klantGegevens": {
            "voornaamAanvrager": "Harry",
            "tussenvoegselAanvrager": "",
            "achternaamAanvrager": "Slinger",
            "naamAanvrager": "Harry Slinger",
            "voornaamPartner": "Harriëtte",
            "tussenvoegselPartner": "",
            "achternaamPartner": "Slinger-Aap",
            "naamPartner": "Harriëtte Slinger-Aap",
            "alleenstaand": False,
            "geboortedatumAanvrager": "1980-01-01",
            "geboortedatumPartner": "1985-01-01",
        },
        "berekeningen": [
            {
                "aankoopsomWoning": 600000,
                "eigenGeld": 2600,
                "woningType": "bestaande_bouw",
                "wozWaarde": 468000,
            }
        ],
        "_dossierScenario1": {
            "leningDelen": [
                {
                    "bedrag": 200000,
                    "aflossingsvorm": "aflossingsvrij",
                    "rentepercentage": 4.0,
                    "origineleLooptijd": 298,
                    "restantLooptijd": 298,
                    "rentevastePeriode": 120,
                },
                {
                    "bedrag": 160000,
                    "aflossingsvorm": "annuiteit",
                    "rentepercentage": 5.0,
                    "origineleLooptijd": 360,
                    "restantLooptijd": 360,
                    "rentevastePeriode": 120,
                },
            ],
        },
        "klant_contact_gegevens": {
            "emailAanvrager": "harry@slinger.com",
            "telefoonAanvrager": "0611112222",
            "adresAanvrager": "Hofakkers 2",
            "postcodeAanvrager": "9471HA",
            "plaatsAanvrager": "Zuidlaren",
            "emailPartner": "harriëtte@slinger.com",
            "telefoonPartner": "0633334444",
            "adresPartner": "Hofakkers 2",
            "postcodePartner": "9471HA",
            "plaatsPartner": "Zuidlaren",
        },
    },
}

MOCK_AANVRAAG_STEL = {
    "id": "aanvraag-stel-test",
    "hypotheekverstrekker": "Allianz",
    "nhg": False,
    "data": {
        "heeftPartner": True,
        "aanvrager": {
            "persoon": {
                "initialen": "H.",
                "achternaam": "Slinger",
                "geboortedatum": "1980-01-01",
            },
        },
        "partner": {
            "persoon": {
                "initialen": "H.V.",
                "achternaam": "Slinger-Aap",
                "geboortedatum": "1985-01-01",
            },
        },
        "inkomenAanvrager": [
            {"type": "Loondienst", "jaarbedrag": 80000},
        ],
        "inkomenPartner": [
            {"type": "Loondienst", "jaarbedrag": 16000},
        ],
        "inkomenAOW": {
            "pensioenAanvrager": 20000,
            "pensioenPartner": 4000,
        },
        "onderpand": {
            "straat": "Archipel 21",
            "postcode": "9421JG",
            "plaats": "Lelystad",
            "marktwaarde": 600000,
            "wozWaarde": 468000,
            "energielabel": "B",
        },
        "financieringsopzet": {
            "aankoopsomWoning": 600000,
            "overdrachtsbelasting": 12000,
            "notariskosten": 1500,
            "verbouwing": 10000,
            "hypotheekadvies": 2900,
            "taxatiekosten": 800,
            "bankgarantie": 400,
        },
        "samenstellenHypotheek": {
            "geldverstrekker": "Allianz",
            "nhg": False,
            "leningdelen": [
                {
                    "bedrag": 200000,
                    "aflossingsvorm": "aflossingsvrij",
                    "rentepercentage": 4.0,
                    "origineleLooptijd": 298,
                    "restantLooptijd": 298,
                    "rentevastePeriode": 120,
                },
                {
                    "bedrag": 160000,
                    "aflossingsvorm": "annuiteit",
                    "rentepercentage": 5.0,
                    "origineleLooptijd": 360,
                    "restantLooptijd": 360,
                    "rentevastePeriode": 120,
                },
            ],
        },
        "huidigeWoning": {
            "adres": "Hofakkers 2",
            "postcode": "9471HA",
            "plaats": "Zuidlaren",
            "marktwaarde": 500000,
            "wozWaarde": 400000,
            "energielabel": "C",
            "status": "Verkopen",
            "hypotheekverstrekker": "Allianz",
            "nhg": False,
            "oorspronkelijkeHoofdsom": 200000,
            "leningdelen": [
                {
                    "bedrag": 200000,
                    "aflossingsvorm": "aflossingsvrij",
                    "rente": 4.0,
                    "looptijd": "30 jaar",
                    "rentevast": "10 jaar",
                    "ingangsdatum": "01-03-2021",
                },
            ],
        },
        "overbrugging": {
            "bedrag": 275000,
        },
        "vermogen": [
            {"omschrijving": "Spaargeld (ABN AMRO)", "bedrag": 50000},
        ],
        "verplichtingen": [
            {"omschrijving": "Studielening", "saldo": 1500, "maandlast": 100},
        ],
        "voorzieningen": {
            "verzekeringen": [
                {
                    "aanbieder": "ABN AMRO",
                    "type": "Overlijdensrisicoverzekering",
                    "verzekerde": "Harry Slinger",
                    "uitkering": 30000,
                },
                {
                    "aanbieder": "ABN AMRO",
                    "type": "Overlijdensrisicoverzekering",
                    "verzekerde": "Harriëtte Slinger-Aap",
                    "uitkering": 20000,
                },
            ],
        },
        "kinderen": [
            {"naam": "Timo Slinger", "geboortedatum": "2017-01-01"},
        ],
        "gezinssituatie": {
            "burgerlijkeStaat": "Gehuwd",
            "huwelijkseVoorwaarden": "Beperkte gemeenschap van goederen",
        },
        "nabestaandenpensioen": {
            "aanvrager": 18000,
            "partner": 2500,
        },
    },
}

MOCK_OPTIONS = AdviesrapportOptions(
    doel_hypotheek="Aankoop bestaande woning",
    ervaring_hypotheek="Nee",
    kennis_hypotheekvormen="Redelijk",
    kennis_fiscale_regels="Matig",
    risicobereidheid={
        "pensioen": "Risico een beetje beperken",
        "overlijden": "Risico zoveel mogelijk beperken",
        "arbeidsongeschiktheid": "Risico een beetje beperken",
        "werkloosheid": "Risico aanvaarden",
        "relatiebeeindiging": "Risico aanvaarden",
        "waardedaling": "Risico een beetje beperken",
        "rentestijging": "Risico aanvaarden",
        "hypotheekrenteaftrek": "Risico aanvaarden",
    },
    advisor_name="Alex Kuijper",
    report_date="11-03-2026",
    ao_percentage=50,
    benutting_rvc_percentage=50,
)


def _inject_charts(data: dict) -> None:
    """Injecteer SVG grafieken in het rapport dict (kopie van pdf_generator logica)."""
    for section in data.get("sections", []):
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


def main():
    print("V2 Adviesrapport — HTML preview genereren...")
    print("=" * 60)

    # Draai de volledige V2 orchestrator
    generate_report(
        dossier=MOCK_DOSSIER_STEL,
        aanvraag=MOCK_AANVRAAG_STEL,
        options=MOCK_OPTIONS,
    )

    rapport = captured_rapport
    print(f"Secties: {len(rapport.get('sections', []))}")
    for s in rapport.get("sections", []):
        has_conclusion = "conclusion" in s and s["conclusion"]
        has_narratives = "narratives" in s and s["narratives"]
        has_bullets = "bullets" in s and s["bullets"] if "bullets" in s else False
        extras = []
        if has_conclusion:
            extras.append(f"conclusion({len(s['conclusion'])})")
        if has_narratives:
            extras.append(f"narratives({len(s['narratives'])})")
        if has_bullets:
            extras.append(f"bullets({len(s['bullets'])})")
        if s.get("columns"):
            extras.append(f"columns({len(s['columns'])})")
        if s.get("scenario_checks"):
            extras.append(f"checks({len(s['scenario_checks'])})")
        print(f"  [{s['id']}] {s['title']}  {' | '.join(extras)}")

    # Scenario checks detail
    for s in rapport.get("sections", []):
        if s.get("scenario_checks"):
            print("\nScenario checks:")
            for c in s["scenario_checks"]:
                print(f"  {c['label']}: {c['status']} (class={c.get('status_class', '?')})")

    # Injecteer afbeeldingen
    logo_path = os.path.join(TEMPLATES_DIR, "assets", "HF - liggend.png")
    illus_path = os.path.join(TEMPLATES_DIR, "assets", "voorpagina-illustratie.jpg")
    try:
        with open(logo_path, "rb") as f:
            rapport["logo_liggend_base64"] = base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        rapport["logo_liggend_base64"] = ""
    try:
        with open(illus_path, "rb") as f:
            rapport["illustratie_base64"] = base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        rapport["illustratie_base64"] = ""

    # Injecteer SVG grafieken
    _inject_charts(rapport)

    # Render template
    jinja_env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=True,
    )
    template = jinja_env.get_template("adviesrapport.html")
    html = template.render(**rapport)

    # Schrijf output
    out_dir = os.path.join(BASE_DIR, "Adviesrapporten")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "v2-preview-stel.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nHTML preview geschreven naar: {out_path}")

    # Dump secties als JSON (voor debugging)
    json_path = os.path.join(out_dir, "v2-preview-stel.json")
    # Strip chart_svg (te groot voor JSON)
    clean = {
        "meta": rapport.get("meta"),
        "bedrijf": rapport.get("bedrijf"),
        "sections": [],
    }
    for s in rapport.get("sections", []):
        cs = {k: v for k, v in s.items() if k not in ("chart_svg",)}
        for col in cs.get("columns", []):
            col.pop("chart_svg", None)
        clean["sections"].append(cs)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False, default=str)
    print(f"JSON dump geschreven naar: {json_path}")


if __name__ == "__main__":
    main()
