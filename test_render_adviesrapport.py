"""
Genereer een proef-PDF van het adviesrapport met voorbeelddata (Harry Slinger).

Rendert lokaal met Jinja2 + WeasyPrint — zelfde engine als productie.
"""

import os
import sys

# --- Dependencies check ---
try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    print("Installeer eerst: pip install jinja2")
    sys.exit(1)

try:
    from weasyprint import HTML
    HAS_WEASYPRINT = True
except (ImportError, OSError):
    HAS_WEASYPRINT = False

# --- Paden ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# --- Voorbeelddata (PdfReport structuur, zoals de TypeScript pdf-mapper oplevert) ---

test_data = {
    "meta": {
        "title": "Adviesrapport Hypotheek",
        "date": "12-02-2026",
        "dossierNumber": "HF-2026-001",
        "advisor": "Alex Kuijper CFP\u00ae",
        "customerName": "Harry Slinger",
        "propertyAddress": "Voorbeeldstraat 12, 1234 AB Emmen",
    },
    "bedrijf": {
        "naam": "Hondsrug Finance",
        "email": "Info@hondsrugfinance.nl",
        "telefoon": "+31 88 400 2700",
        "kvk": "KVK 93276699",
    },
    "sections": [
        # ── Samenvatting advies ──────────────────────────────────────
        {
            "id": "summary",
            "title": "Samenvatting advies",
            "visible": True,
            "narratives": [
                "U wilt een hypotheek afsluiten voor aankoop bestaande woning "
                "aan Voorbeeldstraat 12, 1234 AB Emmen.",
                "Op basis van uw financi\u00eble situatie, uw wensen en de geldende "
                "leennormen hebben wij beoordeeld dat de geadviseerde financiering "
                "passend is binnen uw situatie.",
                "Bij het advies hebben wij nadrukkelijk rekening gehouden met uw "
                "prioriteit: stabiele maandlast.",
                "De hypotheek wordt aangevraagd met Nationale Hypotheek Garantie.",
            ],
            "highlights": [
                {
                    "label": "Hypotheekbedrag",
                    "value": "\u20ac 338.173",
                    "note": "ING \u2014 Annu\u00eftair Hypotheek",
                },
                {
                    "label": "Netto maandlast",
                    "value": "\u20ac 1.267",
                },
            ],
            "rows": [
                {"label": "Bruto maandlast", "value": "\u20ac 1.855"},
                {"label": "Netto maandlast", "value": "\u20ac 1.267", "bold": True},
                {"label": "Eigen inbreng", "value": "\u20ac 25.000"},
            ],
        },
        # ── Klantprofiel ─────────────────────────────────────────────
        {
            "id": "client-profile",
            "title": "Klantprofiel",
            "visible": True,
            "narratives": ["Aanvraag zonder partner."],
            "rows": [
                {"label": "Aanvrager \u2014 Naam", "value": "Harry Slinger"},
                {"label": "Aanvrager \u2014 Geboortedatum", "value": "15-01-1986"},
                {"label": "Aanvrager \u2014 Adres", "value": "Kerkstraat 12, 9471 AB Zuidlaren"},
                {"label": "Aanvrager \u2014 Telefoon", "value": "06-12345678"},
                {"label": "Aanvrager \u2014 E-mail", "value": "harry@example.nl"},
                {"label": "", "value": ""},
                {"label": "Bruto jaarinkomen aanvrager", "value": "\u20ac 80.000"},
                {"label": "Totaal huishoudinkomen", "value": "\u20ac 80.000", "bold": True},
                {"label": "", "value": ""},
                {"label": "Spaargeld", "value": "\u20ac 25.000"},
                {"label": "Totaal vermogen", "value": "\u20ac 25.000", "bold": True},
            ],
        },
        # ── Onderpand ────────────────────────────────────────────────
        {
            "id": "property",
            "title": "Onderpand",
            "visible": True,
            "narratives": [],
            "rows": [
                {"label": "Adres", "value": "Voorbeeldstraat 12, 1234 AB Emmen"},
                {"label": "Woningtype", "value": "Woning"},
                {"label": "Marktwaarde", "value": "\u20ac 350.000"},
                {"label": "Bouwjaar", "value": "1998"},
                {"label": "Energielabel", "value": "A"},
                {"label": "Loan-to-Value", "value": "96,6%"},
            ],
        },
        # ── Betaalbaarheid ───────────────────────────────────────────
        {
            "id": "affordability",
            "title": "Betaalbaarheid",
            "visible": True,
            "narratives": [
                "De maximale hypotheek is beoordeeld op basis van de geldende "
                "leennormen, het toetsinkomen en uw financi\u00eble verplichtingen.",
                "De geadviseerde maandlasten zijn getoetst aan uw situatie en "
                "passen binnen de gehanteerde normen.",
            ],
            "rows": [
                {"label": "Toetsinkomen", "value": "\u20ac 80.000"},
                {"label": "Maximale hypotheek (huidige situatie)", "value": "\u20ac 326.250"},
                {"label": "Geadviseerd hypotheekbedrag", "value": "\u20ac 338.173", "bold": True},
                {"label": "Bruto maandlast", "value": "\u20ac 1.855"},
                {"label": "Fiscaal voordeel", "value": "\u20ac 588"},
                {"label": "Netto maandlast", "value": "\u20ac 1.267", "bold": True},
            ],
        },
        # ── Financieringsopzet ───────────────────────────────────────
        {
            "id": "financing",
            "title": "Financieringsopzet",
            "visible": True,
            "narratives": [],
            "rows": [
                {"label": "Koopsom", "value": "\u20ac 350.000"},
                {"label": "Overdrachtsbelasting", "value": "\u20ac 7.000"},
                {"label": "Taxatiekosten", "value": "\u20ac 750"},
                {"label": "Advies- en bemiddelingskosten", "value": "\u20ac 2.500"},
                {"label": "Notariskosten", "value": "\u20ac 1.500"},
                {"label": "NHG-borgtochtprovisie", "value": "\u20ac 1.423"},
                {"label": "Totale investering", "value": "\u20ac 363.173", "bold": True},
                {"label": "", "value": ""},
                {"label": "Eigen spaargeld", "value": "\u20ac 25.000"},
                {"label": "Totaal eigen middelen", "value": "\u20ac 25.000", "bold": True},
                {"label": "", "value": ""},
                {"label": "Benodigd hypotheekbedrag", "value": "\u20ac 338.173", "bold": True},
            ],
        },
        # ── Hypotheekonderdelen ──────────────────────────────────────
        {
            "id": "loan-parts",
            "title": "Hypotheekonderdelen",
            "visible": True,
            "narratives": [
                "Een annu\u00eftaire hypotheek kent een maandlast die bestaat uit rente "
                "en aflossing. Binnen de looptijd wordt de lening volledig afgelost.",
            ],
            "rows": [
                {"label": "Geldverstrekker", "value": "ING"},
                {"label": "Productlijn", "value": "Annu\u00eftair Hypotheek"},
            ],
            "tables": [
                {
                    "headers": ["Leningdeel", "Bedrag", "Aflosvorm", "Rente", "RVP", "Looptijd", "Box"],
                    "rows": [
                        ["Deel 1", "\u20ac 338.173", "Annu\u00efteit", "4,50%", "10 jaar", "30 jaar", "box 1"],
                    ],
                }
            ],
        },
        # ── Fiscale aspecten ─────────────────────────────────────────
        {
            "id": "tax",
            "title": "Fiscale aspecten",
            "visible": True,
            "narratives": [
                "De leningdelen die kwalificeren als eigenwoningschuld vallen in box 1. "
                "De betaalde hypotheekrente kan fiscaal aftrekbaar zijn, voor zover "
                "aan de wettelijke voorwaarden wordt voldaan.",
                "Op basis van het bekende eigenwoningverleden loopt de renteaftrek "
                "tot en met 2056.",
            ],
            "rows": [
                {
                    "label": "Fiscale kwalificatie",
                    "value": "Eigenwoningschuld (box 1)",
                },
                {"label": "Renteaftrek tot en met", "value": "2056"},
            ],
        },
        # ── Risico bij overlijden ────────────────────────────────────
        {
            "id": "risk-death",
            "title": "Risico bij overlijden",
            "visible": True,
            "narratives": [
                "Bij overlijden ontstaat geen financieel risico voor een partner, "
                "maar het blijft van belang dat eventuele nabestaanden of erfgenamen "
                "zich bewust zijn van de gevolgen voor de woningfinanciering.",
            ],
        },
        # ── Risico bij arbeidsongeschiktheid ─────────────────────────
        {
            "id": "risk-disability",
            "title": "Risico bij arbeidsongeschiktheid",
            "visible": True,
            "narratives": [
                "Wanneer u arbeidsongeschikt raakt, kan uw inkomen dalen. "
                "Hierdoor kan het lastiger worden om de hypotheeklasten te "
                "blijven betalen.",
                "In dit rapport is geen afzonderlijke productoplossing voor "
                "arbeidsongeschiktheid opgenomen. Het doel van dit onderdeel is "
                "bewustwording van dit risico.",
            ],
        },
        # ── Risico bij werkloosheid ──────────────────────────────────
        {
            "id": "risk-unemployment",
            "title": "Risico bij werkloosheid",
            "visible": True,
            "narratives": [
                "Bij werkloosheid kan uw inkomen tijdelijk lager zijn. "
                "Hierdoor kunnen de maandlasten moeilijker betaalbaar worden.",
                "Het is daarom belangrijk om voldoende financi\u00eble reserves "
                "aan te houden om een periode van inkomensdaling op te kunnen vangen.",
            ],
            "rows": [
                {"label": "Beschikbare buffer (spaargeld)", "value": "\u20ac 25.000"},
            ],
        },
        # ── Pensionering (niet zichtbaar in dit voorbeeld) ───────────
        {
            "id": "retirement",
            "title": "Pensionering",
            "visible": False,
            "narratives": [
                "Wij hebben gekeken naar uw verwachte inkomenssituatie na "
                "pensionering op basis van de bij ons bekende pensioeninformatie.",
            ],
        },
        # ── Aandachtspunten ──────────────────────────────────────────
        {
            "id": "attention-points",
            "title": "Aandachtspunten",
            "visible": True,
            "narratives": [
                "Na afloop van de rentevaste periode kan de rente wijzigen, "
                "waardoor de maandlasten kunnen stijgen of dalen.",
                "Veranderingen in uw persoonlijke of financi\u00eble situatie "
                "kunnen invloed hebben op de betaalbaarheid van de hypotheek.",
            ],
        },
        # ── Disclaimer ───────────────────────────────────────────────
        {
            "id": "disclaimer",
            "title": "Disclaimer",
            "visible": True,
            "narratives": [
                "Dit adviesrapport is opgesteld op basis van de door u verstrekte "
                "informatie. Wij gaan ervan uit dat deze gegevens juist en volledig zijn.",
                "Het advies is een momentopname en gebaseerd op de huidige wet- en "
                "regelgeving en de op het moment van opstellen bekende uitgangspunten.",
                "De definitieve acceptatie van de hypotheek is afhankelijk van de "
                "beoordeling door de geldverstrekker.",
            ],
        },
    ],
}


def render_html_preview():
    """Genereer HTML preview (werkt altijd, ook zonder WeasyPrint)."""
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)
    template = env.get_template("adviesrapport.html")
    html_string = template.render(**test_data)

    html_path = os.path.join(BASE_DIR, "test-adviesrapport-preview.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_string)
    print(f"HTML preview: {html_path}")

    try:
        os.startfile(html_path)
    except AttributeError:
        print(f"Open handmatig: {html_path}")


def render_via_api():
    """Genereer PDF via de Render API (POST /adviesrapport-pdf)."""
    try:
        import httpx
    except ImportError:
        print("httpx niet geinstalleerd. Installeer met: pip install httpx")
        return

    API_URL = "https://nat-hypotheek-api.onrender.com/adviesrapport-pdf"
    API_KEY = os.environ.get("NAT_API_KEY", "")

    headers = {}
    if API_KEY:
        headers["X-API-Key"] = API_KEY

    print(f"POST {API_URL} ...")
    resp = httpx.post(API_URL, json=test_data, headers=headers, timeout=60)

    if resp.status_code == 200:
        output_path = os.path.join(BASE_DIR, "test-adviesrapport.pdf")
        with open(output_path, "wb") as f:
            f.write(resp.content)
        print(f"PDF opgeslagen: {output_path} ({len(resp.content):,} bytes)")
        try:
            os.startfile(output_path)
        except AttributeError:
            print(f"Open handmatig: {output_path}")
    else:
        print(f"FOUT {resp.status_code}: {resp.text[:500]}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "html"

    if mode == "api":
        render_via_api()
    else:
        render_html_preview()
        print("\nTip: gebruik 'python test_render_adviesrapport.py api' om via Render een echte PDF te genereren.")
