"""Config loader voor smart mapper — laadt toegestane waarden uit config/*.json.

Leest geldverstrekkers, dropdown-opties en energielabels, en bouwt een
prompt-sectie die Claude vertelt welke waarden geldig zijn voor dropdown-velden.
"""

import json
import os
from functools import lru_cache

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")


@lru_cache(maxsize=1)
def _load_json(filename: str) -> dict:
    path = os.path.join(CONFIG_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_geldverstrekkers() -> list[str]:
    """Laad de lijst van bekende geldverstrekkers."""
    data = _load_json("geldverstrekkers.json")
    return data.get("geldverstrekkers", [])


def load_dropdowns() -> dict:
    """Laad alle dropdown-opties."""
    return _load_json("dropdowns.json")


def build_allowed_values_prompt() -> str:
    """Bouw een prompt-sectie met alle toegestane dropdown-waarden.

    Bevat compacte lijsten: geldverstrekkers, energielabel, aflosvorm,
    soort_berekening, soort_dienstverband, woningtoepassing, soort_onderpand.

    NIET: financiele_instellingen (300+), beroepstype (80+) — te groot.
    """
    geldverstrekkers = load_geldverstrekkers()
    dd = load_dropdowns()

    # Haal value-lijsten uit dropdown config
    energielabel = [opt["value"] for opt in dd.get("woning", {}).get("energielabel", [])]
    woningtoepassing = [opt["value"] for opt in dd.get("woning", {}).get("woningtoepassing", [])]
    soort_onderpand = [opt["value"] for opt in dd.get("woning", {}).get("soort_onderpand", [])]
    waarde_vastgesteld = [opt["value"] for opt in dd.get("woning", {}).get("waarde_vastgesteld_met", [])]
    woningstatus = [opt["value"] for opt in dd.get("woning", {}).get("woningstatus", [])]

    soort_berekening = [opt["value"] for opt in dd.get("inkomen", {}).get("soort_berekening", [])]
    soort_dienstverband = dd.get("inkomen", {}).get("soort_dienstverband", [])

    lines = [
        "TOEGESTANE WAARDEN (gebruik ALLEEN deze waarden voor dropdown-velden):",
        "",
        f"Geldverstrekkers: {json.dumps(geldverstrekkers, ensure_ascii=False)}",
        "",
        f"Energielabel (woning): {json.dumps(energielabel, ensure_ascii=False)}",
        f"Woningtoepassing: {json.dumps(woningtoepassing, ensure_ascii=False)}",
        f"Soort onderpand: {json.dumps(soort_onderpand, ensure_ascii=False)}",
        f"Waarde vastgesteld met: {json.dumps(waarde_vastgesteld, ensure_ascii=False)}",
        f"Woningstatus: {json.dumps(woningstatus, ensure_ascii=False)}",
        "",
        f"Soort berekening (inkomen): {json.dumps(soort_berekening, ensure_ascii=False)}",
        f"Soort dienstverband: {json.dumps(soort_dienstverband, ensure_ascii=False)}",
        "",
        'Aflosvorm (hypotheek): ["annuitair", "lineair", "aflossingsvrij", "bankspaarhypotheek", "spaarhypotheek"]',
        'Fiscaal regime: ["box1_na_2013", "box1_voor_2013", "box3"]',
        'Legitimatiesoort: ["paspoort", "europese_id"]',
        'Geslacht: ["man", "vrouw"]',
        "",
        "Als een waarde op het document niet EXACT overeenkomt met een toegestane waarde,",
        "kies dan de dichtstbijzijnde match. Als er GEEN match is: laat het veld LEEG",
        "en vermeld dit in het alternatieven/evidence veld.",
    ]

    return "\n".join(lines)
