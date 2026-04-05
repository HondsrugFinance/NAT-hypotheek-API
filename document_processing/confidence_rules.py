"""Confidence classificatie en checkvraag-bouwer voor gelaagd import systeem.

Bepaalt per veld of het 'zeker' (direct prefilen) of 'onzeker' (checkvraag aan
adviseur) is. Bouwt checkvragen uit onzekere velden met alternatieven.

Prioriteit: ONZEKER_PREFIXES > ZEKER_PREFIXES > Claude's eigen oordeel.
"""

from document_processing.smart_mapper import _get_nested, _set_nested

# ---------------------------------------------------------------------------
# Classificatieregels — welke paden zijn altijd zeker/onzeker?
# ---------------------------------------------------------------------------

# Velden die altijd zeker zijn als ze uit een document komen
ZEKER_PREFIXES: set[str] = {
    # Persoonsgegevens
    "aanvrager.persoon",
    "partner.persoon",
    # Legitimatie
    "aanvrager.identiteit",
    "partner.identiteit",
    # Adres
    "aanvrager.adresContact",
    "partner.adresContact",
    # Bankrekening
    "vermogenSectie.iban",
    # Woning adresgegevens
    "woningen[0].straat",
    "woningen[0].huisnummer",
    "woningen[0].toevoeging",
    "woningen[0].postcode",
    "woningen[0].woonplaats",
    # Werkgever naam (uit WGV)
    "aanvrager.werkgever.naam",
    "partner.werkgever.naam",
    # Kinderen
    "kinderen",
    # Hypotheek leningdelen (feiten uit hypotheekoverzicht)
    "hypotheken",
}

# Velden die altijd onzeker zijn (adviseur moet kiezen)
ONZEKER_PREFIXES: set[str] = {
    # Doelstelling is een adviseur-keuze
    "doelstelling",
    # Inkomen: WGV vs IBL keuze
    "inkomenAanvrager",
    "inkomenPartner",
    # Geldverstrekker: naam-mapping kan afwijken
    "hypotheekInschrijvingen",
    # Burgerlijke staat: soms onduidelijk uit documenten
    "burgerlijkeStaat",
}

# Binnen onzekere prefixes: sub-paden die wél zeker zijn
# (bijv. werkgever-details binnen inkomen)
ZEKER_SUBPADEN_BINNEN_ONZEKER: set[str] = {
    "inkomenAanvrager[0].loondienst.werkgever",
    "inkomenPartner[0].loondienst.werkgever",
    "inkomenAanvrager[0].loondienst.dienstverband.functie",
    "inkomenPartner[0].loondienst.dienstverband.functie",
    "inkomenAanvrager[0].loondienst.dienstverband.inDienstSinds",
    "inkomenPartner[0].loondienst.dienstverband.inDienstSinds",
    "inkomenAanvrager[0].loondienst.dienstverband.soortDienstverband",
    "inkomenPartner[0].loondienst.dienstverband.soortDienstverband",
    "inkomenAanvrager[0].inkomstenbron",
    "inkomenPartner[0].inkomstenbron",
    "inkomenAanvrager[0].ingangsdatum",
    "inkomenPartner[0].ingangsdatum",
}


def classify_veld(pad: str, claude_source: str) -> str:
    """Classificeer een veld als 'zeker' of 'onzeker'.

    Args:
        pad: Het veldpad (bijv. "aanvrager.persoon.achternaam")
        claude_source: Claude's eigen oordeel ("extracted" of "inferred")

    Returns:
        "zeker" of "onzeker"
    """
    # Check eerst zekere sub-paden binnen onzekere prefixes
    for subpad in ZEKER_SUBPADEN_BINNEN_ONZEKER:
        if pad.startswith(subpad):
            return "zeker"

    # ONZEKER_PREFIXES hebben voorrang
    for prefix in ONZEKER_PREFIXES:
        if pad.startswith(prefix):
            return "onzeker"

    # ZEKER_PREFIXES
    for prefix in ZEKER_PREFIXES:
        if pad.startswith(prefix):
            return "zeker"

    # Fallback: Claude's oordeel
    if claude_source == "inferred":
        return "onzeker"

    return "zeker"


# ---------------------------------------------------------------------------
# Checkvragen bouwen uit onzekere velden
# ---------------------------------------------------------------------------

# Categorie-mapping voor groepering van checkvragen
_VRAAG_CATEGORIE_MAP = {
    "inkomenAanvrager": "inkomen",
    "inkomenPartner": "inkomen",
    "hypotheekInschrijvingen": "hypotheek",
    "doelstelling": "algemeen",
    "burgerlijkeStaat": "algemeen",
}


def _pad_to_categorie(pad: str) -> str:
    """Bepaal de categorie van een checkvraag op basis van het pad."""
    for prefix, cat in _VRAAG_CATEGORIE_MAP.items():
        if pad.startswith(prefix):
            return cat
    return "overig"


def _generate_vraag_tekst(veld: dict) -> str:
    """Genereer een leesbare vraagtekst voor een onzeker veld."""
    label = veld.get("label", veld.get("pad", ""))
    evidence = veld.get("evidence", "")
    alternatieven = veld.get("alternatieven", [])

    if alternatieven:
        return f"{label}: welke waarde hanteren?"
    if evidence:
        return f"{label}: {evidence}"
    return f"Bevestig: {label}"


def build_check_vragen(velden: list[dict]) -> list[dict]:
    """Bouw checkvragen uit onzekere velden.

    Alleen velden met layer='onzeker' worden meegenomen.
    Velden met alternatieven worden keuzevragen,
    velden zonder alternatieven worden bevestigingsvragen.

    Returns:
        Lijst van check_vragen dicts.
    """
    vragen = []
    seen_pads = set()

    for veld in velden:
        if veld.get("layer") != "onzeker":
            continue

        pad = veld.get("pad", "")
        if pad in seen_pads:
            continue
        seen_pads.add(pad)

        waarde = veld.get("waarde")
        alternatieven = veld.get("alternatieven", [])

        # Bouw opties: huidige waarde + alternatieven
        opties = []
        if waarde is not None:
            opties.append({
                "label": veld.get("waarde_display", str(waarde)),
                "pad": pad,
                "waarde": waarde,
            })
        for alt in alternatieven:
            if alt.get("waarde") != waarde:  # geen duplicaten
                opties.append({
                    "label": alt.get("label", str(alt.get("waarde", ""))),
                    "pad": pad,
                    "waarde": alt.get("waarde"),
                })

        vraag = {
            "id": pad.replace(".", "_").replace("[", "_").replace("]", ""),
            "vraag": _generate_vraag_tekst(veld),
            "opties": opties,
            "bron": veld.get("bron", ""),
            "evidence": veld.get("evidence", ""),
            "categorie": _pad_to_categorie(pad),
            "pad": pad,
        }
        vragen.append(vraag)

    return vragen


def build_zeker_prefill(merged_data: dict, velden: list[dict]) -> dict:
    """Bouw een gefilterd data-object met alleen zekere velden.

    Kopieert waarden uit merged_data voor alle paden waar layer='zeker'.
    """
    result = {}
    for veld in velden:
        if veld.get("layer") != "zeker":
            continue
        pad = veld.get("pad", "")
        waarde = _get_nested(merged_data, pad)
        if waarde is not None:
            _set_nested(result, pad, waarde)
    return result
