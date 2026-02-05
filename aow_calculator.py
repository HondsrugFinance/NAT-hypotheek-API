"""
AOW-leeftijd Calculator
Bepaalt AOW-categorie voor hypotheekberekeningen

Categorieën:
- AOW_BEREIKT: Klant heeft AOW-leeftijd al bereikt
- BINNEN_10_JAAR: Klant bereikt AOW binnen 10 jaar
- MEER_DAN_10_JAAR: Klant bereikt AOW over meer dan 10 jaar

Bron AOW-leeftijd: https://www.rijksoverheid.nl/onderwerpen/algemene-ouderdomswet-aow/aow-leeftijd
Bron AOW-bedragen: https://www.svb.nl/nl/aow/bedragen-aow/aow-bedragen
Laatst bijgewerkt: 2026-02-05
"""

from datetime import date
from dateutil.relativedelta import relativedelta

# AOW-leeftijd tabel (officieel vastgesteld t/m 2031)
# Jaarlijks updaten in november wanneer nieuwe jaren worden aangekondigd
AOW_TABEL = [
    {"geboren_tot": date(1960, 12, 31), "jaren": 67, "maanden": 0},
    {"geboren_tot": date(1964, 9, 30), "jaren": 67, "maanden": 3},
    # Fallback voor jongeren (geschat, nog niet officieel vastgesteld)
    {"geboren_tot": None, "jaren": 67, "maanden": 3},
]

# AOW-inkomen bij volledige opbouw (50 jaar), bruto per jaar incl. vakantiegeld
# Bron: SVB, per 1 januari 2026
# Jaarlijks updaten in december/januari wanneer nieuwe bedragen bekend zijn
AOW_INKOMEN = {
    "alleenstaand_bruto_jaar": 20929.44,   # (1637.57 + 106.55) * 12
    "samenwonend_bruto_jaar": 14378.64,    # (1122.12 + 76.10) * 12
}


def bereken_aow_datum(geboortedatum: date) -> date:
    for regel in AOW_TABEL:
        if regel["geboren_tot"] is None or geboortedatum <= regel["geboren_tot"]:
            aow_leeftijd = relativedelta(years=regel["jaren"], months=regel["maanden"])
            return geboortedatum + aow_leeftijd
    return geboortedatum + relativedelta(years=67, months=3)


def bepaal_aow_categorie(geboortedatum: date, peildatum: date = None) -> dict:
    if peildatum is None:
        peildatum = date.today()

    aow_datum = bereken_aow_datum(geboortedatum)
    verschil = relativedelta(aow_datum, peildatum)
    jaren_tot_aow = verschil.years + verschil.months / 12

    if aow_datum <= peildatum:
        categorie = "AOW_BEREIKT"
        jaren_tot_aow = 0
    elif jaren_tot_aow <= 10:
        categorie = "BINNEN_10_JAAR"
    else:
        categorie = "MEER_DAN_10_JAAR"

    return {
        "categorie": categorie,
        "aow_datum": aow_datum.isoformat(),
        "jaren_tot_aow": round(jaren_tot_aow, 1),
        "aow_inkomen": AOW_INKOMEN,
    }
