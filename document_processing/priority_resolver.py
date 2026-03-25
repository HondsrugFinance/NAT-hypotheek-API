"""Bronvolgorde resolver — bepaalt welke waarde wint per veld."""

import json
import logging
import os

from document_processing.schemas import ResolvedValue

logger = logging.getLogger("nat-api.priority")

_mapping_cache: dict | None = None


def _load_mapping() -> dict:
    """Laad de extractie-mapping config (bronvolgorde per veld).

    Dit is een vereenvoudigde versie. De volledige mapping uit de Excel
    wordt later omgezet naar JSON. Voor nu gebruiken we een hardcoded mapping.
    """
    global _mapping_cache
    if _mapping_cache is not None:
        return _mapping_cache

    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "extraction_priority.json")
    if os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as f:
            _mapping_cache = json.load(f)
    else:
        # Default mapping (de meest kritieke velden)
        _mapping_cache = {
            # Persoonsgegevens
            "voornamen": ["paspoort", "id_kaart"],
            "achternaam": ["paspoort", "id_kaart", "uwv_verzekeringsbericht"],
            "tussenvoegsel": ["paspoort", "id_kaart", "uwv_verzekeringsbericht"],
            "geboortedatum": ["paspoort", "id_kaart", "uwv_verzekeringsbericht"],
            "geboorteplaats": ["paspoort", "id_kaart"],
            "nationaliteit": ["paspoort", "id_kaart"],
            "geslacht": ["paspoort", "id_kaart", "uwv_verzekeringsbericht"],
            "legitimatienummer": ["paspoort", "id_kaart"],
            # Inkomen — loondienst
            "bruto_jaarsalaris": ["werkgeversverklaring", "salarisstrook"],
            "naamWerkgever": ["werkgeversverklaring", "uwv_verzekeringsbericht", "salarisstrook"],
            "functie": ["werkgeversverklaring", "salarisstrook"],
            "soortDienstverband": ["werkgeversverklaring", "salarisstrook", "uwv_verzekeringsbericht"],
            "inDienstSinds": ["werkgeversverklaring", "salarisstrook", "uwv_verzekeringsbericht"],
            "gemiddeldUrenPerWeek": ["werkgeversverklaring", "salarisstrook", "uwv_verzekeringsbericht"],
            "vakantiegeldPercentage": ["werkgeversverklaring", "salarisstrook"],
            "gemiddeldJaarToetsinkomen": ["ibl_toetsinkomen"],
            "maandelijksePensioenbijdrage": ["salarisstrook"],
            # Inkomen — onderneming
            "nettoWinstJaar1": ["jaarrapport", "ib_aangifte"],
            "nettoWinstJaar2": ["jaarrapport", "ib_aangifte"],
            "nettoWinstJaar3": ["jaarrapport", "ib_aangifte"],
            # Onderpand
            "aankoopsomWoning": ["koopovereenkomst"],
            "marktwaarde": ["taxatierapport"],
            "energielabel": ["energielabel"],
            "leveringsdatum": ["koopovereenkomst"],
            # Hypotheek
            "restschuld": ["hypotheekoverzicht"],
            "rentePercentage": ["hypotheekoverzicht"],
            "aflosvorm": ["hypotheekoverzicht"],
        }
        logger.info("Geen extraction_priority.json gevonden, default mapping geladen (%d velden)", len(_mapping_cache))

    return _mapping_cache


def resolve_field(
    field_name: str,
    extractions: list[dict],
) -> ResolvedValue | None:
    """Bepaal de winnende waarde voor een veld op basis van bronvolgorde.

    Args:
        field_name: Veldnaam (bijv. "bruto_jaarsalaris")
        extractions: Lijst van extracted_data rijen voor dit dossier
            Elke rij: {"extract_type": "werkgeversverklaring", "computed_values": {...}, "confidence": 0.9, "id": "..."}

    Returns:
        ResolvedValue met de winnende waarde, of None als geen bron het veld heeft.
    """
    mapping = _load_mapping()
    priority_order = mapping.get(field_name, [])

    # Verzamel alle waarden voor dit veld, per bron
    candidates = []
    for ext in extractions:
        extract_type = ext.get("extract_type", "")
        values = ext.get("computed_values", {})
        raw = ext.get("raw_values", {})

        # Check of dit veld aanwezig is
        value = values.get(field_name) or raw.get(field_name)
        if value is not None:
            candidates.append({
                "value": value,
                "source_type": extract_type,
                "source_id": ext.get("id", ""),
                "confidence": ext.get("confidence", 0.5),
            })

    if not candidates:
        return None

    # Sorteer op prioriteit
    def sort_key(c):
        try:
            idx = priority_order.index(c["source_type"])
        except ValueError:
            idx = 999  # onbekend type → laagste prioriteit
        return (idx, -c["confidence"])

    candidates.sort(key=sort_key)
    winner = candidates[0]

    # Detecteer tegenstrijdigheden
    conflicting = []
    for c in candidates[1:]:
        if str(c["value"]) != str(winner["value"]):
            conflicting.append({
                "value": c["value"],
                "source_type": c["source_type"],
                "source_id": c["source_id"],
            })

    return ResolvedValue(
        field_name=field_name,
        value=winner["value"],
        source_document_type=winner["source_type"],
        source_document_id=winner["source_id"],
        confidence=winner["confidence"],
        conflicting_values=conflicting if conflicting else None,
    )


def resolve_all_fields(extractions: list[dict]) -> list[ResolvedValue]:
    """Resolve alle velden voor een dossier.

    Args:
        extractions: Alle extracted_data rijen voor dit dossier

    Returns:
        Lijst van ResolvedValue per veld (alleen velden die in minstens 1 extractie voorkomen)
    """
    # Verzamel alle unieke veldnamen
    all_fields = set()
    for ext in extractions:
        all_fields.update(ext.get("computed_values", {}).keys())
        all_fields.update(ext.get("raw_values", {}).keys())

    results = []
    for field in sorted(all_fields):
        resolved = resolve_field(field, extractions)
        if resolved:
            results.append(resolved)

    return results
