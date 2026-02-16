"""
AOW-leeftijd Calculator
Bepaalt AOW-categorie voor hypotheekberekeningen

Categorieën:
- AOW_BEREIKT: Klant heeft AOW-leeftijd al bereikt
- BINNEN_10_JAAR: Klant bereikt AOW binnen 10 jaar
- MEER_DAN_10_JAAR: Klant bereikt AOW over meer dan 10 jaar

AOW-tabel wordt geladen uit config/aow.json
Jaarlijks updaten in november wanneer nieuwe jaren worden aangekondigd
"""

import os
import json
from datetime import date
from dateutil.relativedelta import relativedelta

# AOW-config laden uit JSON
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, 'config', 'aow.json'), 'r', encoding='utf-8') as f:
    AOW_CONFIG = json.load(f)

# Converteer JSON naar intern formaat
AOW_TABEL = []
for regel in AOW_CONFIG["tabel"]:
    AOW_TABEL.append({
        "geboren_tot": date.fromisoformat(regel["geboren_tot"]),
        "jaren": regel["jaren"],
        "maanden": regel["maanden"],
    })
AOW_TABEL.append({
    "geboren_tot": None,
    "jaren": AOW_CONFIG["fallback"]["jaren"],
    "maanden": AOW_CONFIG["fallback"]["maanden"],
})


def bereken_aow_datum(geboortedatum: date) -> date:
    """
    Bereken de AOW-ingangsdatum op basis van geboortedatum.

    Args:
        geboortedatum: Geboortedatum van de klant

    Returns:
        Datum waarop de klant AOW-gerechtigd wordt
    """
    for regel in AOW_TABEL:
        if regel["geboren_tot"] is None or geboortedatum <= regel["geboren_tot"]:
            aow_leeftijd = relativedelta(years=regel["jaren"], months=regel["maanden"])
            return geboortedatum + aow_leeftijd

    # Fallback (zou niet bereikt moeten worden)
    return geboortedatum + relativedelta(years=67, months=3)


def bepaal_aow_categorie(geboortedatum: date, peildatum: date = None) -> dict:
    """
    Bepaal AOW-categorie voor hypotheekberekening.

    Args:
        geboortedatum: Geboortedatum van de klant
        peildatum: Datum waarop de berekening wordt gemaakt (default: vandaag)

    Returns:
        Dict met:
        - categorie: "AOW_BEREIKT", "BINNEN_10_JAAR", of "MEER_DAN_10_JAAR"
        - aow_datum: ISO-formaat datum van AOW-ingang
        - jaren_tot_aow: Aantal jaren tot AOW (afgerond op 1 decimaal)
    """
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
        "jaren_tot_aow": round(jaren_tot_aow, 1)
    }
