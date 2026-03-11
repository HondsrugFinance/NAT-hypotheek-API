"""
Genereer proef-HTML's van het adviesrapport met voorbeelddata.

Twee varianten:
1. Harry Slinger — alleenstaand, 1 leningdeel
2. Harry en Harriette Slinger — stel, 3 leningdelen, volledige risico-analyse

Per risicosectie een eigen SVG grafiek:
- Pensioen: verticale staven (max hypotheek per jaar) + restschuld-lijn
- Overlijden / AO / WW: horizontale staven

Rendert lokaal met Jinja2 — zelfde template als productie.
"""

import base64
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


# ═══════════════════════════════════════════════════════════════════════
# Helpers voor pensioen chart testdata
# ═══════════════════════════════════════════════════════════════════════

def _restschuld(hoofdsom, rente_jaar, lpt_mnd, elapsed_mnd, aflos_type="Annuïteit"):
    """Bereken restschuld na elapsed_mnd maanden (vereenvoudigd)."""
    if elapsed_mnd <= 0:
        return hoofdsom
    if aflos_type in ("Aflossingsvrij", "Aflosvrij"):
        return hoofdsom
    if aflos_type == "Lineair":
        if elapsed_mnd >= lpt_mnd:
            return 0
        return max(0, hoofdsom - (hoofdsom / lpt_mnd) * elapsed_mnd)
    # Annuïteit
    if elapsed_mnd >= lpt_mnd:
        return 0
    r = rente_jaar / 12
    if r == 0:
        return max(0, hoofdsom - (hoofdsom / lpt_mnd) * elapsed_mnd)
    fn = (1 + r) ** lpt_mnd
    pmt = hoofdsom * (r * fn) / (fn - 1)
    fe = (1 + r) ** elapsed_mnd
    return max(0, hoofdsom * fe - pmt * (fe - 1) / r)


def _pensioen_chart_data(start_jaar, n_jaren, delen, geadviseerd,
                         max_hyp_jaar_0, max_hyp_aow, aow_jaar):
    """
    Genereer synthetische pensioen chart data voor testdoeleinden.

    Args:
        delen: list van {"hs": float, "rente": float, "lpt": int, "type": str}
        max_hyp_jaar_0/max_hyp_aow: lineair geïnterpoleerd
    """
    jaren = []
    for y in range(n_jaren):
        jaar = start_jaar + y
        elapsed = y * 12

        restschuld = sum(
            _restschuld(d["hs"], d["rente"], d["lpt"], elapsed, d["type"])
            for d in delen
        )

        # Max hypotheek: lineair interpoleren tot AOW, daarna constant
        if jaar <= aow_jaar:
            t = y / max(1, aow_jaar - start_jaar)
            max_hyp = max_hyp_jaar_0 + (max_hyp_aow - max_hyp_jaar_0) * t
        else:
            max_hyp = max_hyp_aow

        jaren.append({
            "jaar": jaar,
            "max_hypotheek": round(max_hyp),
            "restschuld": round(restschuld),
        })

    return {"geadviseerd_hypotheekbedrag": geadviseerd, "jaren": jaren}


# --- Gedeelde bedrijfsgegevens ---
BEDRIJF = {
    "naam": "Hondsrug Finance B.V.",
    "adres": "Marktstraat 21, 9401 JG Assen",
    "email": "info@hondsrugfinance.nl",
    "telefoon": "088 400 2700",
    "kvk": "KVK 93276699",
}

# ═══════════════════════════════════════════════════════════════════════
# TESTSET 1: Harry Slinger — Alleenstaand
# ═══════════════════════════════════════════════════════════════════════

test_alleenstaand = {
    "meta": {
        "title": "Persoonlijk Hypotheekadvies",
        "date": "12-02-2026",
        "advisor": "Alex Kuijper CFP\u00ae",
        "customerName": "Harry Slinger",
        "propertyAddress": "Voorbeeldstraat 12, 1234 AB Emmen",
    },
    "bedrijf": BEDRIJF,
    "sections": [
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
                "De hypotheek wordt aangevraagd met Nationale Hypotheek Garantie.",
            ],
            "highlights": [
                {"label": "Hypotheek", "value": "\u20ac 338.173",
                 "note": "Verantwoord hypotheekbedrag: \u20ac 326.250",
                 "status": "warning"},
                {"label": "Hypotheekverstrekker", "value": "ING",
                 "note": "Met NHG",
                 "status": "ok"},
                {"label": "Maandlast", "value": "\u20ac 1.267 netto",
                 "note": "Bruto: \u20ac 1.855",
                 "status": "ok"},
                {"label": "Woningwaarde", "value": "\u20ac 350.000",
                 "note": "Schuld-marktwaardeverhouding 96,6%",
                 "status": "ok"},
            ],
            "mortgage_summary": [
                {"label": "Hypotheekvorm", "value": "Annu\u00efteitenhypotheek"},
                {"label": "Rentevastperiode", "value": "10 jaar"},
            ],
            "scenario_checks": [
                {"label": "Arbeidsongeschiktheid", "status": "warning"},
                {"label": "Pensionering", "status": "warning"},
                {"label": "Werkloosheid", "status": "warning"},
            ],
            "advice_text": [
                "Wij adviseren een hypotheek van \u20ac 338.173 bij ING, met een annu\u00eftaire "
                "aflossingsvorm en een rentevaste periode van 10 jaar. De hypotheek wordt "
                "aangevraagd met Nationale Hypotheek Garantie.",
                "De bruto maandlast bedraagt \u20ac 1.855, wat na belastingvoordeel neerkomt "
                "op een netto maandlast van \u20ac 1.267. Het geadviseerde hypotheekbedrag past "
                "binnen de maximaal toegestane hypotheek van \u20ac 326.250.",
                "Overlijden: niet van toepassing (alleenstaand). Arbeidsongeschiktheid: "
                "aandachtspunt, verwijzing naar specialist. Werkloosheid: aandachtspunt. "
                "Pensionering: afgedekt.",
                "Bij dit advies is rekening gehouden met uw prioriteit: stabiele maandlast.",
            ],
        },
        {
            "id": "client-profile",
            "title": "Klantprofiel",
            "visible": True,
            "narratives": [],
            "rows": [
                {"label": "Doel van de hypotheek", "value": "Aankoop bestaande woning"},
                {"label": "Ervaring met een hypotheek", "value": "Nee"},
                {"label": "Kennis van hypotheekvormen", "value": "Redelijk"},
                {"label": "Kennis van fiscale regels", "value": "Matig"},
            ],
            "tables": [{
                "headers": ["Financi\u00eble risico's", "Risicobereidheid"],
                "rows": [
                    ["Pensioen", "Risico een beetje beperken"],
                    ["Arbeidsongeschiktheid", "Risico een beetje beperken"],
                    ["Werkloosheid", "Risico aanvaarden"],
                    ["Waardedaling woning", "Risico een beetje beperken"],
                    ["Rentestijging", "Risico aanvaarden"],
                    ["Aflopen hypotheekrenteaftrek", "Risico aanvaarden"],
                ],
            }],
        },
        # ── Huidige situatie ──────────────────────────────────────────
        {
            "id": "current-situation",
            "title": "Huidige situatie",
            "visible": True,
            "subsections": [
                {
                    "subtitle": "Persoonsgegevens",
                    "rows": [
                        {"label": "Naam", "value": "H. Slinger"},
                        {"label": "Geboortedatum", "value": "15-01-1986"},
                        {"label": "Adres", "value": "Hoofdstraat 22"},
                        {"label": "Postcode en plaats", "value": "7811 EB Emmen"},
                        {"label": "Telefoon", "value": "06-12345678"},
                        {"label": "E-mail", "value": "harry@example.nl"},
                    ],
                },
                {
                    "subtitle": "Gezinssituatie",
                    "rows": [
                        {"label": "Burgerlijke staat", "value": "Alleenstaand"},
                    ],
                },
                {
                    "subtitle": "Huidige woonsituatie",
                    "rows": [
                        {"label": "Adres", "value": "Hoofdstraat 22, 7811 EB Emmen"},
                        {"label": "Type", "value": "Huurwoning"},
                    ],
                },
                {
                    "subtitle": "Inkomen",
                    "tables": [{
                        "headers": ["Type", "Bedrag"],
                        "rows": [
                            ["Loondienst", "\u20ac 80.000"],
                        ],
                        "totals": ["Totaal", "\u20ac 80.000"],
                    }],
                },
                {
                    "subtitle": "Inkomen na AOW",
                    "tables": [{
                        "headers": ["Type", "Bedrag"],
                        "rows": [
                            ["AOW-uitkering", "\u20ac 16.800"],
                            ["Pensioen", "\u20ac 28.200"],
                        ],
                        "totals": ["Totaal", "\u20ac 45.000"],
                    }],
                },
                {
                    "subtitle": "Vermogen",
                    "rows": [
                        {"label": "Spaargeld", "value": "\u20ac 25.000"},
                        {"label": "Totaal", "value": "\u20ac 25.000", "bold": True},
                    ],
                },
            ],
        },
        # ── Financiering ──────────────────────────────────────────────
        {
            "id": "financing",
            "title": "Financiering",
            "visible": True,
            "subsections": [
                {
                    "subtitle": "Onderpand",
                    "rows": [
                        {"label": "Adres", "value": "Voorbeeldstraat 12, 1234 AB Emmen"},
                        {"label": "Type woning", "value": "Bestaande bouw"},
                        {"label": "Marktwaarde", "value": "\u20ac 350.000"},
                        {"label": "Energielabel", "value": "A"},
                    ],
                },
                {
                    "subtitle": "Financieringsopzet",
                    "rows": [
                        {"label": "Koopsom", "value": "\u20ac 350.000"},
                        {"label": "Kosten koper", "value": "\u20ac 13.173"},
                        {"label": "Totale investering", "value": "\u20ac 363.173", "bold": True},
                        {"label": "", "value": ""},
                        {"label": "Eigen middelen", "value": "\u20ac 25.000"},
                        {"label": "Benodigd hypotheekbedrag", "value": "\u20ac 338.173", "bold": True},
                    ],
                },
                {
                    "subtitle": "Hypotheekconstructie",
                    "rows": [
                        {"label": "Hypotheekverstrekker", "value": "ING"},
                        {"label": "NHG", "value": "Ja"},
                    ],
                    "tables": [{
                        "headers": ["Leningdeel", "Bedrag", "Aflosvorm", "Looptijd",
                                    "Rentevast", "Rente %", "Aftrekbaar", "Bruto p/m"],
                        "rows": [
                            ["1", "\u20ac 338.173", "Annu\u00efteit", "30 jaar",
                             "10 jaar", "4,50%", "30 jaar", "\u20ac 1.855"],
                        ],
                        "totals": ["", "\u20ac 338.173", "", "", "", "", "", "\u20ac 1.855"],
                    }],
                },
            ],
        },
        # --- Risico-secties (volgorde: pensioen, overlijden, AO, WW) ---
        {
            "id": "retirement",
            "title": "Pensioen",
            "visible": True,
            "narratives": [
                "Wij hebben gekeken naar uw verwachte inkomenssituatie na "
                "pensionering op basis van de bij ons bekende pensioeninformatie.",
                "Na pensionering daalt de maximale hypotheek onder het geadviseerde "
                "hypotheekbedrag. Wij adviseren om de gevolgen hiervan bewust mee "
                "te nemen in uw financi\u00eble planning.",
            ],
            "rows": [
                {"label": "Inkomen na AOW Harry (2053)", "value": "\u20ac 45.000", "bold": True},
                {"label": "AOW Harry", "value": "\u20ac 16.800", "sub": True},
                {"label": "Pensioen Harry", "value": "\u20ac 28.200", "sub": True},
                {"label": "Maximale hypotheek na AOW (2053)", "value": "\u20ac 280.412"},
            ],
            "chart_data": _pensioen_chart_data(
                start_jaar=2026, n_jaren=30,
                delen=[{"hs": 338173, "rente": 0.045, "lpt": 360, "type": "Annuïteit"}],
                geadviseerd=338173,
                max_hyp_jaar_0=326250, max_hyp_aow=280412, aow_jaar=2053,
            ),
        },
        {
            "id": "risk-death",
            "title": "Overlijden",
            "visible": True,
            "narratives": [
                "Bij overlijden ontstaat geen financieel risico voor een partner.",
            ],
            "advisor_note": "U bent alleenstaand. Bij overlijden wordt de woning "
                            "onderdeel van de nalatenschap.",
        },
        {
            "id": "risk-disability",
            "title": "Arbeidsongeschiktheid",
            "visible": True,
            "narratives": [
                "Wij hebben beoordeeld wat de gevolgen zijn als u 50% "
                "arbeidsongeschikt raakt. Bij uw dienstverband (loondienst) "
                "gaan wij uit van 50% benutting van de restverdiencapaciteit.",
            ],
            "columns": [
                {
                    "title": "Harry Slinger",
                    "rows": [
                        {"label": "Inkomen bij WGA loongerelateerd", "value": "\u20ac 50.000", "bold": True},
                        {"label": "Restloon (50% benut)", "value": "\u20ac 20.000", "sub": True},
                        {"label": "WGA-uitkering", "value": "\u20ac 30.000", "sub": True},
                        {"label": "", "value": ""},
                        {"label": "Inkomen bij WGA loonaanvulling", "value": "\u20ac 42.000", "bold": True},
                        {"label": "Restloon (50% benut)", "value": "\u20ac 20.000", "sub": True},
                        {"label": "WGA-uitkering", "value": "\u20ac 22.000", "sub": True},
                    ],
                    "chart_data": {
                        "type": "vergelijk_fasen",
                        "fasen": [
                            {"label": "Huidig", "max_hypotheek": 326250},
                            {"label": "WGA loongerelateerd", "max_hypotheek": 225000},
                            {"label": "WGA loonaanvulling", "max_hypotheek": 198000},
                        ],
                        "geadviseerd_hypotheekbedrag": 338173,
                    },
                },
            ],
            "advisor_note": "Bij 50% AO daalt uw maximale hypotheek naar "
                            "\u20ac 198.000 in de WGA-loonaanvullingsfase. "
                            "Overweeg een AOV met een dekking van circa "
                            "\u20ac 30.000/jaar.",
        },
        {
            "id": "risk-unemployment",
            "title": "Werkloosheid",
            "visible": True,
            "narratives": [
                "U heeft recht op 13 maanden WW-uitkering. Na afloop van de WW "
                "valt uw inkomen uit loondienst volledig weg.",
            ],
            "columns": [
                {
                    "title": "Harry Slinger",
                    "rows": [
                        {"label": "Inkomen tijdens WW", "value": "\u20ac 55.587", "bold": True},
                        {"label": "WW-uitkering (13 mnd)", "value": "\u20ac 55.587", "sub": True},
                        {"label": "", "value": ""},
                        {"label": "Inkomen na WW", "value": "\u20ac 0", "bold": True},
                    ],
                    "chart_data": {
                        "type": "vergelijk_fasen",
                        "fasen": [
                            {"label": "Huidig", "max_hypotheek": 326250},
                            {"label": "Tijdens WW", "max_hypotheek": 295000},
                            {"label": "Na WW", "max_hypotheek": 125000},
                        ],
                        "geadviseerd_hypotheekbedrag": 338173,
                    },
                },
            ],
            "advisor_note": "Na afloop van de WW-periode daalt uw maximale hypotheek "
                            "fors. Wij adviseren een buffer van minimaal 6 maanden "
                            "netto lasten aan te houden.",
        },
        # --- Afsluiting ---
        {
            "id": "closing",
            "title": "Afsluiting",
            "visible": True,
            "narratives": [
                "Dit Persoonlijk Hypotheekadvies en de bijbehorende berekeningen "
                "zijn uitsluitend bedoeld als advies. Dit advies is geen aanbod "
                "voor het aangaan van een overeenkomst, u kunt hieraan geen rechten "
                "ontlenen. De berekeningen zijn gebaseerd op de persoonlijke en "
                "financi\u00eble gegevens die u ons heeft gegeven.",
                "Dit hypotheekadvies is gebaseerd op de gegevens die wij van u "
                "hebben ontvangen en op de relevante (fiscale) wet- en regelgeving "
                "die nu geldt. Van een totaal fiscaal advies is geen sprake. "
                "Daarvoor verwijzen wij u naar een fiscaal adviseur. Hondsrug "
                "Finance aanvaardt geen aansprakelijkheid voor eventuele toekomstige "
                "wijzigingen in de fiscale wet- en regelgeving.",
            ],
        },
    ],
}

# ═══════════════════════════════════════════════════════════════════════
# TESTSET 2: Harry en Harriette Slinger — Stel, 3 leningdelen
# ═══════════════════════════════════════════════════════════════════════

test_stel = {
    "meta": {
        "title": "Persoonlijk Hypotheekadvies",
        "date": "09-03-2026",
        "advisor": "Alex Kuijper CFP\u00ae",
        "customerName": "Harry en Harriette Slinger",
        "propertyAddress": "Kerkstraat 45, 9471 AB Zuidlaren",
    },
    "bedrijf": BEDRIJF,
    "sections": [
        # ── Samenvatting ───────────────────────────────────────────────
        {
            "id": "summary",
            "title": "Samenvatting advies",
            "visible": True,
            "narratives": [
                "U wilt samen een hypotheek afsluiten voor de aankoop van een "
                "bestaande woning aan Kerkstraat 45, 9471 AB Zuidlaren.",
                "Op basis van uw gezamenlijke financi\u00eble situatie is de "
                "geadviseerde financiering passend.",
            ],
            "highlights": [
                {"label": "Hypotheek", "value": "\u20ac 450.000",
                 "note": "Verantwoord hypotheekbedrag: \u20ac 520.000",
                 "status": "ok"},
                {"label": "Hypotheekverstrekker", "value": "ING",
                 "note": "Met NHG",
                 "status": "ok"},
                {"label": "Maandlast", "value": "\u20ac 1.890 netto",
                 "note": "Bruto: \u20ac 2.410",
                 "status": "ok"},
                {"label": "Woningwaarde", "value": "\u20ac 475.000",
                 "note": "Schuld-marktwaardeverhouding 94,7%",
                 "status": "ok"},
            ],
            "scenario_checks": [
                {"label": "Arbeidsongeschiktheid", "status": "warning"},
                {"label": "Relatiebeëindiging", "status": "warning"},
                {"label": "Werkloosheid", "status": "ok"},
                {"label": "Pensionering", "status": "ok"},
                {"label": "Overlijden", "status": "warning"},
            ],
            "advice_text": [
                "Wij adviseren een hypotheek van \u20ac 450.000 bij ING, met een combinatie "
                "van annu\u00eftair, lineair en aflossingsvrij als aflossingsvorm en een rentevaste "
                "periode van 20 jaar. De hypotheek wordt aangevraagd met Nationale Hypotheek Garantie.",
                "De bruto maandlast bedraagt \u20ac 2.410, wat na belastingvoordeel neerkomt "
                "op een netto maandlast van \u20ac 1.890. Het geadviseerde hypotheekbedrag past "
                "ruim binnen de maximaal toegestane hypotheek van \u20ac 520.000.",
                "Overlijden: aandachtspunt. Arbeidsongeschiktheid: aandachtspunt, verwijzing "
                "naar specialist. Werkloosheid: voldoende buffer. Pensionering: afgedekt.",
                "Bij dit advies is rekening gehouden met uw prioriteit: zo laag mogelijke maandlast.",
            ],
            "mortgage_summary": [
                {"label": "Hypotheekvorm", "value": "Combinatie van annuïtair, lineair en aflossingsvrij"},
                {"label": "Rentevastperiode", "value": "10 jaar"},
            ],
        },
        # ── Klantprofiel ───────────────────────────────────────────────
        {
            "id": "client-profile",
            "title": "Klantprofiel",
            "visible": True,
            "narratives": [],
            "rows": [
                {"label": "Doel van de hypotheek", "value": "Aankoop bestaande woning"},
                {"label": "Ervaring met een hypotheek", "value": "Ja"},
                {"label": "Kennis van hypotheekvormen", "value": "Goed"},
                {"label": "Kennis van fiscale regels", "value": "Redelijk"},
            ],
            "tables": [{
                "headers": ["Financi\u00eble risico's", "Risicobereidheid"],
                "rows": [
                    ["Pensioen", "Risico een beetje beperken"],
                    ["Overlijden", "Risico zoveel mogelijk beperken"],
                    ["Arbeidsongeschiktheid", "Risico een beetje beperken"],
                    ["Werkloosheid", "Risico aanvaarden"],
                    ["Relatiebeëindiging", "Risico aanvaarden"],
                    ["Waardedaling woning", "Risico een beetje beperken"],
                    ["Rentestijging", "Risico een beetje beperken"],
                    ["Aflopen hypotheekrenteaftrek", "Risico aanvaarden"],
                ],
            }],
        },
        # ── Huidige situatie ──────────────────────────────────────────
        {
            "id": "current-situation",
            "title": "Huidige situatie",
            "visible": True,
            "subsections": [
                {
                    "subtitle": "Persoonsgegevens",
                    "columns": [
                        {
                            "title": "Harry Slinger",
                            "rows": [
                                {"label": "Naam", "value": "H. Slinger"},
                                {"label": "Geboortedatum", "value": "01-04-1980"},
                                {"label": "Adres", "value": "Dorpsstraat 8"},
                                {"label": "Postcode en plaats", "value": "9471 AB Zuidlaren"},
                                {"label": "Telefoon", "value": "06-12345678"},
                                {"label": "E-mail", "value": "harry@example.nl"},
                            ],
                        },
                        {
                            "title": "Harriette Slinger",
                            "rows": [
                                {"label": "Naam", "value": "H. Slinger-Aap"},
                                {"label": "Geboortedatum", "value": "15-06-1985"},
                                {"label": "Adres", "value": "Dorpsstraat 8"},
                                {"label": "Postcode en plaats", "value": "9471 AB Zuidlaren"},
                                {"label": "Telefoon", "value": "06-87654321"},
                                {"label": "E-mail", "value": "harriette@example.nl"},
                            ],
                        },
                    ],
                },
                {
                    "subtitle": "Gezinssituatie",
                    "rows": [
                        {"label": "Burgerlijke staat", "value": "Gehuwd"},
                        {"label": "Huwelijkse voorwaarden", "value": "Koude uitsluiting"},
                    ],
                    "list_items": [
                        "Tim Slinger \u2013 12-05-2015",
                        "Lisa Slinger \u2013 03-09-2018",
                    ],
                    "list_label": "Kinderen",
                },
                {
                    "subtitle": "Bestaande woning",
                    "rows": [
                        {"label": "Adres", "value": "Dorpsstraat 8, 9471 AB Zuidlaren"},
                        {"label": "Type", "value": "Koopwoning"},
                        {"label": "Marktwaarde", "value": "\u20ac 320.000"},
                        {"label": "WOZ-waarde", "value": "\u20ac 295.000"},
                        {"label": "Status", "value": "Verkopen"},
                        {"label": "Erfpacht", "value": "\u20ac 125 per maand"},
                    ],
                },
                {
                    "subtitle": "Bestaande hypotheek",
                    "rows": [
                        {"label": "Hypotheekverstrekker", "value": "Rabobank"},
                        {"label": "NHG", "value": "Ja"},
                    ],
                    "tables": [{
                        "headers": ["Leningdeel", "Bedrag", "Aflosvorm", "Rente",
                                    "Looptijd", "Rentevast", "Ingangsdatum"],
                        "rows": [
                            ["1", "\u20ac 190.071", "Annu\u00efteit", "2,35%",
                             "22 jaar en 5 mnd", "12 jaar en 4 mnd", "01-08-2016"],
                            ["2", "\u20ac 304.929", "Annu\u00efteit", "3,82%",
                             "30 jaar", "10 jaar", "01-08-2016"],
                        ],
                        "totals": ["", "\u20ac 495.000", "", "", "", "", ""],
                    }],
                },
                {
                    "subtitle": "Inkomen",
                    "columns": [
                        {
                            "title": "Harry Slinger",
                            "tables": [{
                                "headers": ["Type", "Bedrag"],
                                "rows": [
                                    ["Loondienst", "\u20ac 80.000"],
                                ],
                                "totals": ["Totaal", "\u20ac 80.000"],
                            }],
                        },
                        {
                            "title": "Harriette Slinger",
                            "tables": [{
                                "headers": ["Type", "Bedrag"],
                                "rows": [
                                    ["Loondienst", "\u20ac 40.000"],
                                ],
                                "totals": ["Totaal", "\u20ac 40.000"],
                            }],
                        },
                    ],
                },
                {
                    "subtitle": "Inkomen na AOW",
                    "columns": [
                        {
                            "title": "Harry Slinger (2047)",
                            "tables": [{
                                "headers": ["Type", "Bedrag"],
                                "rows": [
                                    ["AOW-uitkering", "\u20ac 14.500"],
                                    ["Pensioen", "\u20ac 30.500"],
                                ],
                                "totals": ["Totaal", "\u20ac 45.000"],
                            }],
                        },
                        {
                            "title": "Harriette Slinger (2052)",
                            "tables": [{
                                "headers": ["Type", "Bedrag"],
                                "rows": [
                                    ["AOW-uitkering", "\u20ac 14.500"],
                                    ["Pensioen", "\u20ac 12.500"],
                                ],
                                "totals": ["Totaal", "\u20ac 27.000"],
                            }],
                        },
                    ],
                },
                {
                    "subtitle": "Vermogen",
                    "rows": [
                        {"label": "Spaargeld", "value": "\u20ac 35.000"},
                        {"label": "Schenking", "value": "\u20ac 5.000"},
                        {"label": "Totaal", "value": "\u20ac 40.000", "bold": True},
                    ],
                },
                {
                    "subtitle": "Verplichtingen",
                    "rows": [
                        {"label": "Doorlopend krediet (limiet \u20ac 5.000)",
                         "value": "\u20ac 100 p/m"},
                        {"label": "Totaal", "value": "\u20ac 100 p/m", "bold": True},
                    ],
                },
                {
                    "subtitle": "Voorzieningen",
                    "tables": [{
                        "headers": ["Aanbieder", "Type", "Verzekerde", "Uitkering"],
                        "rows": [
                            ["Aegon", "Overlijdensrisicoverzekering",
                             "Harry Slinger", "\u20ac 80.000"],
                            ["Aegon", "Overlijdensrisicoverzekering",
                             "Harriette Slinger", "\u20ac 80.000"],
                            ["Nationale-Nederlanden", "AOV",
                             "Harry Slinger", "\u20ac 25.000 p/j"],
                        ],
                    }],
                },
            ],
        },
        # ── Financiering ──────────────────────────────────────────────
        {
            "id": "financing",
            "title": "Financiering",
            "visible": True,
            "subsections": [
                {
                    "subtitle": "Onderpand",
                    "rows": [
                        {"label": "Adres", "value": "Kerkstraat 45, 9471 AB Zuidlaren"},
                        {"label": "Type woning", "value": "Bestaande bouw"},
                        {"label": "Marktwaarde", "value": "\u20ac 475.000"},
                        {"label": "Energielabel", "value": "B"},
                    ],
                },
                {
                    "subtitle": "Financieringsopzet",
                    "rows": [
                        {"label": "Koopsom", "value": "\u20ac 475.000"},
                        {"label": "Kosten koper", "value": "\u20ac 15.000"},
                        {"label": "Totale investering", "value": "\u20ac 490.000", "bold": True},
                        {"label": "", "value": ""},
                        {"label": "Eigen middelen", "value": "\u20ac 40.000"},
                        {"label": "Benodigd hypotheekbedrag", "value": "\u20ac 450.000", "bold": True},
                    ],
                },
                {
                    "subtitle": "Hypotheekconstructie",
                    "rows": [
                        {"label": "Hypotheekverstrekker", "value": "ING"},
                        {"label": "NHG", "value": "Ja"},
                    ],
                    "tables": [{
                        "headers": ["Leningdeel", "Bedrag", "Aflosvorm", "Looptijd",
                                    "Rentevast", "Rente %", "Aftrekbaar", "Bruto p/m"],
                        "rows": [
                            ["1", "\u20ac 150.000", "Aflossingsvrij", "30 jaar",
                             "10 jaar", "5,00%", "30 jaar", "\u20ac 625"],
                            ["2", "\u20ac 200.000", "Annu\u00efteit", "30 jaar",
                             "10 jaar", "5,00%", "30 jaar", "\u20ac 1.074"],
                            ["3", "\u20ac 100.000", "Lineair", "25 jaar",
                             "10 jaar", "3,00%", "25 jaar", "\u20ac 583"],
                        ],
                        "totals": ["", "\u20ac 450.000", "", "", "", "", "", "\u20ac 2.282"],
                    }],
                },
            ],
        },
        # ── Risico-secties (volgorde: pensioen, overlijden, AO, WW) ───
        {
            "id": "retirement",
            "title": "Pensioen",
            "visible": True,
            "narratives": [
                "Wij hebben gekeken naar uw verwachte inkomenssituatie na "
                "pensionering op basis van de bij ons bekende pensioeninformatie.",
                "Bij pensionering van Harry daalt de maximale hypotheek onder "
                "het geadviseerde hypotheekbedrag. Bij pensionering van "
                "Harriette neemt dit tekort verder toe. Wij adviseren om de "
                "gevolgen hiervan bewust mee te nemen in uw financi\u00eble planning.",
            ],
            "columns": [
                {
                    "title": "Inkomen na AOW Harry (2047)",
                    "rows": [
                        {"label": "AOW Harry", "value": "\u20ac 14.500", "sub": True},
                        {"label": "Pensioen Harry", "value": "\u20ac 30.500", "sub": True},
                        {"label": "Loondienst Harriette", "value": "\u20ac 40.000", "sub": True},
                        {"label": "Totaal inkomen", "value": "\u20ac 85.000", "bold": True},
                        {"label": "", "value": ""},
                        {"label": "Maximale hypotheek", "sub": True, "value": "\u20ac 410.000"},
                    ],
                },
                {
                    "title": "Inkomen na AOW Harriette (2052)",
                    "rows": [
                        {"label": "AOW Harry", "value": "\u20ac 14.500", "sub": True},
                        {"label": "Pensioen Harry", "value": "\u20ac 30.500", "sub": True},
                        {"label": "AOW Harriette", "value": "\u20ac 14.500", "sub": True},
                        {"label": "Pensioen Harriette", "value": "\u20ac 12.500", "sub": True},
                        {"label": "Totaal inkomen", "value": "\u20ac 72.000", "bold": True},
                        {"label": "", "value": ""},
                        {"label": "Maximale hypotheek", "sub": True, "value": "\u20ac 340.000"},
                    ],
                },
            ],
            "chart_data": _pensioen_chart_data(
                start_jaar=2026, n_jaren=30,
                delen=[
                    {"hs": 150000, "rente": 0.05, "lpt": 360, "type": "Aflossingsvrij"},
                    {"hs": 200000, "rente": 0.05, "lpt": 360, "type": "Annuïteit"},
                    {"hs": 100000, "rente": 0.03, "lpt": 300, "type": "Lineair"},
                ],
                geadviseerd=450000,
                max_hyp_jaar_0=520000, max_hyp_aow=340000, aow_jaar=2052,
            ),
            "advisor_note": "Na pensionering van beiden daalt de maximale hypotheek "
                            "onder het geadviseerde bedrag. Wij adviseren om extra "
                            "aflossingen of aanvullende pensioenopbouw te overwegen.",
        },
        {
            "id": "risk-death",
            "title": "Overlijden",
            "visible": True,
            "narratives": [
                "Bij overlijden van \u00e9\u00e9n van de partners daalt het "
                "huishoudinkomen. Hieronder de gevolgen per scenario.",
            ],
            "columns": [
                {
                    "title": "Overlijden - Harry",
                    "rows": [
                        {"label": "Resterend inkomen", "value": "\u20ac 52.000", "bold": True},
                        {"label": "Loondienst Harriette", "value": "\u20ac 40.000", "sub": True},
                        {"label": "Nabestaandenpensioen", "value": "\u20ac 12.000", "sub": True},
                        {"label": "Maximale hypotheek", "sub": True, "value": "\u20ac 195.000"},
                    ],
                    "chart_data": {
                        "type": "overlijden_vergelijk",
                        "huidig_max_hypotheek": 520000,
                        "max_hypotheek_na_overlijden": 195000,
                        "geadviseerd_hypotheekbedrag": 450000,
                    },
                },
                {
                    "title": "Overlijden - Harriette",
                    "rows": [
                        {"label": "Resterend inkomen", "value": "\u20ac 88.000", "bold": True},
                        {"label": "Loondienst Harry", "value": "\u20ac 80.000", "sub": True},
                        {"label": "Nabestaandenpensioen", "value": "\u20ac 8.000", "sub": True},
                        {"label": "Maximale hypotheek", "sub": True, "value": "\u20ac 362.000"},
                    ],
                    "chart_data": {
                        "type": "overlijden_vergelijk",
                        "huidig_max_hypotheek": 520000,
                        "max_hypotheek_na_overlijden": 362000,
                        "geadviseerd_hypotheekbedrag": 450000,
                    },
                },
            ],
            "advisor_note": "Bij overlijden van Harry ontstaat een aanzienlijk tekort. "
                            "Wij adviseren een overlijdensrisicoverzekering (ORV) van "
                            "minimaal \u20ac 255.000 op het leven van Harry.",
        },
        {
            "id": "risk-disability",
            "title": "Arbeidsongeschiktheid",
            "visible": True,
            "narratives": [
                "Wij hebben beoordeeld wat de gevolgen zijn als \u00e9\u00e9n van u "
                "50% arbeidsongeschikt raakt. Bij loondienst gaan wij uit van "
                "50% benutting van de restverdiencapaciteit.",
            ],
            "columns": [
                {
                    "title": "Arbeidsongeschiktheid - Harry",
                    "rows": [
                        {"label": "WGA loongerelateerd", "value": "\u20ac 90.000", "bold": True},
                        {"label": "Restloon Harry (50% benut)", "value": "\u20ac 20.000", "sub": True},
                        {"label": "WGA-uitkering Harry", "value": "\u20ac 30.000", "sub": True},
                        {"label": "Loondienst Harriette", "value": "\u20ac 40.000", "sub": True},
                        {"label": "", "value": ""},
                        {"label": "WGA loonaanvulling", "value": "\u20ac 82.000", "bold": True},
                        {"label": "Restloon Harry (50% benut)", "value": "\u20ac 20.000", "sub": True},
                        {"label": "WGA-uitkering Harry", "value": "\u20ac 22.000", "sub": True},
                        {"label": "Loondienst Harriette", "value": "\u20ac 40.000", "sub": True},
                    ],
                    "chart_data": {
                        "type": "vergelijk_fasen",
                        "fasen": [
                            {"label": "Huidig", "max_hypotheek": 520000},
                            {"label": "WGA loongerelateerd", "max_hypotheek": 395000},
                            {"label": "WGA loonaanvulling", "max_hypotheek": 350000},
                        ],
                        "geadviseerd_hypotheekbedrag": 450000,
                    },
                },
                {
                    "title": "Arbeidsongeschiktheid - Harriette",
                    "rows": [
                        {"label": "WGA loongerelateerd", "value": "\u20ac 106.000", "bold": True},
                        {"label": "Loondienst Harry", "value": "\u20ac 80.000", "sub": True},
                        {"label": "Restloon Harriette (50% benut)", "value": "\u20ac 10.000", "sub": True},
                        {"label": "WGA-uitkering Harriette", "value": "\u20ac 16.000", "sub": True},
                        {"label": "", "value": ""},
                        {"label": "WGA loonaanvulling", "value": "\u20ac 101.000", "bold": True},
                        {"label": "Loondienst Harry", "value": "\u20ac 80.000", "sub": True},
                        {"label": "Restloon Harriette (50% benut)", "value": "\u20ac 10.000", "sub": True},
                        {"label": "WGA-uitkering Harriette", "value": "\u20ac 11.000", "sub": True},
                    ],
                    "chart_data": {
                        "type": "vergelijk_fasen",
                        "fasen": [
                            {"label": "Huidig", "max_hypotheek": 520000},
                            {"label": "WGA loongerelateerd", "max_hypotheek": 475000},
                            {"label": "WGA loonaanvulling", "max_hypotheek": 455000},
                        ],
                        "geadviseerd_hypotheekbedrag": 450000,
                    },
                },
            ],
            "advisor_note": "Bij 50% AO van Harry daalt de maximale hypotheek met "
                            "\u20ac 125.000. Een AOV-verzekering verdient overweging.",
        },
        {
            "id": "risk-unemployment",
            "title": "Werkloosheid",
            "visible": True,
            "narratives": [
                "Harry heeft recht op 13 maanden WW-uitkering. "
                "Harriette heeft recht op 8 maanden WW-uitkering.",
            ],
            "columns": [
                {
                    "title": "Werkloosheid - Harry",
                    "rows": [
                        {"label": "Tijdens WW", "value": "\u20ac 95.587", "bold": True},
                        {"label": "WW-uitkering Harry", "value": "\u20ac 55.587", "sub": True},
                        {"label": "Loondienst Harriette", "value": "\u20ac 40.000", "sub": True},
                        {"label": "", "value": ""},
                        {"label": "Na WW Harry", "value": "\u20ac 40.000", "bold": True},
                        {"label": "Loondienst Harriette", "value": "\u20ac 40.000", "sub": True},
                    ],
                    "chart_data": {
                        "type": "vergelijk_fasen",
                        "fasen": [
                            {"label": "Huidig", "max_hypotheek": 520000},
                            {"label": "Tijdens WW", "max_hypotheek": 426030},
                            {"label": "Na WW", "max_hypotheek": 153325},
                        ],
                        "geadviseerd_hypotheekbedrag": 450000,
                    },
                },
                {
                    "title": "Werkloosheid - Harriette",
                    "rows": [
                        {"label": "Tijdens WW", "value": "\u20ac 108.000", "bold": True},
                        {"label": "Loondienst Harry", "value": "\u20ac 80.000", "sub": True},
                        {"label": "WW-uitkering Harriette", "value": "\u20ac 28.000", "sub": True},
                        {"label": "", "value": ""},
                        {"label": "Na WW Harriette", "value": "\u20ac 80.000", "bold": True},
                        {"label": "Loondienst Harry", "value": "\u20ac 80.000", "sub": True},
                    ],
                    "chart_data": {
                        "type": "vergelijk_fasen",
                        "fasen": [
                            {"label": "Huidig", "max_hypotheek": 520000},
                            {"label": "Tijdens WW", "max_hypotheek": 491072},
                            {"label": "Na WW", "max_hypotheek": 347590},
                        ],
                        "geadviseerd_hypotheekbedrag": 450000,
                    },
                },
            ],
            "advisor_note": "Bij werkloosheid van Harry daalt de maximale hypotheek "
                            "fors na afloop van de WW-periode. Wij adviseren een "
                            "financi\u00eble buffer van minimaal 6 maanden netto lasten.",
        },
        {
            "id": "risk-relationship",
            "title": "Relatiebeëindiging",
            "visible": True,
            "narratives": [
                "Bij relatiebeëindiging valt het inkomen van de partner weg. "
                "Er is geen recht op nabestaandenpensioen.",
            ],
            "columns": [
                {
                    "title": "Harry alleen",
                    "rows": [
                        {"label": "Resterend inkomen", "value": "\u20ac 80.000", "bold": True},
                        {"label": "Loondienst Harry", "value": "\u20ac 80.000", "sub": True},
                        {"label": "Maximale hypotheek", "sub": True, "value": "\u20ac 326.250"},
                    ],
                    "chart_data": {
                        "type": "overlijden_vergelijk",
                        "huidig_max_hypotheek": 520000,
                        "max_hypotheek_na_overlijden": 326250,
                        "geadviseerd_hypotheekbedrag": 450000,
                        "label_bar1": "Huidig",
                        "label_bar2": "Na scheiding",
                    },
                },
                {
                    "title": "Harriette alleen",
                    "rows": [
                        {"label": "Resterend inkomen", "value": "\u20ac 40.000", "bold": True},
                        {"label": "Loondienst Harriette", "value": "\u20ac 40.000", "sub": True},
                        {"label": "Maximale hypotheek", "sub": True, "value": "\u20ac 153.325"},
                    ],
                    "chart_data": {
                        "type": "overlijden_vergelijk",
                        "huidig_max_hypotheek": 520000,
                        "max_hypotheek_na_overlijden": 153325,
                        "geadviseerd_hypotheekbedrag": 450000,
                        "label_bar1": "Huidig",
                        "label_bar2": "Na scheiding",
                    },
                },
            ],
            "advisor_note": "Bij relatiebeëindiging moet de hypotheek door één inkomen "
                            "gedragen worden. Partneralimentatie kan het inkomen "
                            "aanvullen maar is niet gegarandeerd op lange termijn.",
        },
        {
            "id": "closing",
            "title": "Afsluiting",
            "visible": True,
            "narratives": [
                "Dit Persoonlijk Hypotheekadvies en de bijbehorende berekeningen "
                "zijn uitsluitend bedoeld als advies. Dit advies is geen aanbod "
                "voor het aangaan van een overeenkomst, u kunt hieraan geen rechten "
                "ontlenen. De berekeningen zijn gebaseerd op de persoonlijke en "
                "financi\u00eble gegevens die u ons heeft gegeven.",
                "Dit hypotheekadvies is gebaseerd op de gegevens die wij van u "
                "hebben ontvangen en op de relevante (fiscale) wet- en regelgeving "
                "die nu geldt. Van een totaal fiscaal advies is geen sprake. "
                "Daarvoor verwijzen wij u naar een fiscaal adviseur. Hondsrug "
                "Finance aanvaardt geen aansprakelijkheid voor eventuele toekomstige "
                "wijzigingen in de fiscale wet- en regelgeving.",
            ],
        },
    ],
}


# ═══════════════════════════════════════════════════════════════════════
# Render functies
# ═══════════════════════════════════════════════════════════════════════

def _inject_chart_svg(data: dict):
    """Genereer SVG grafieken voor secties met chart_data."""
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


def _load_base64(path: str) -> str:
    """Laad bestand als base64 string."""
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except FileNotFoundError:
        return ""


def render_html_preview(data: dict, filename: str):
    """Genereer HTML preview en open in browser."""
    _inject_chart_svg(data)

    # Afbeeldingen als base64 injecteren
    assets_dir = os.path.join(TEMPLATES_DIR, "assets")
    data["logo_liggend_base64"] = _load_base64(os.path.join(assets_dir, "HF - liggend.png"))
    data["illustratie_base64"] = _load_base64(os.path.join(assets_dir, "voorpagina-illustratie.jpg"))

    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)
    template = env.get_template("adviesrapport.html")
    html_string = template.render(**data)

    html_path = os.path.join(BASE_DIR, filename)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_string)
    print(f"HTML preview: {html_path}")

    try:
        os.startfile(html_path)
    except AttributeError:
        print(f"Open handmatig: {html_path}")


def render_via_api(data: dict, filename: str):
    """Genereer PDF via de Render API."""
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

    print(f"POST {API_URL} ({data['meta']['customerName']}) ...")
    resp = httpx.post(API_URL, json=data, headers=headers, timeout=60)

    if resp.status_code == 200:
        output_path = os.path.join(BASE_DIR, filename)
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

    datasets = [
        (test_alleenstaand, "test-adviesrapport-alleenstaand", "Harry Slinger (alleenstaand)"),
        (test_stel, "test-adviesrapport-stel", "Harry en Harriette Slinger (stel)"),
    ]

    for data, base_name, label in datasets:
        print(f"\n--- {label} ---")
        if mode == "api":
            render_via_api(data, f"{base_name}.pdf")
        else:
            render_html_preview(data, f"{base_name}.html")

    if mode != "api":
        print("\nTip: gebruik 'python test_render_adviesrapport.py api' voor echte PDF's via Render.")
