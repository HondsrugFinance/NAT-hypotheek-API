"""Naamherkenning — koppel een naam uit een document aan aanvrager of partner."""

import re
import unicodedata


def _normalize(naam: str) -> set[str]:
    """Normaliseer een naam naar een set losse woorden (lowercase, zonder leestekens)."""
    if not naam:
        return set()
    # Verwijder accenten
    naam = unicodedata.normalize("NFD", naam)
    naam = "".join(c for c in naam if unicodedata.category(c) != "Mn")
    # Lowercase
    naam = naam.lower()
    # Verwijder leestekens behalve koppelteken
    naam = re.sub(r"[^a-z\s-]", "", naam)
    # Split op spaties en koppeltekens
    woorden = set()
    for w in naam.split():
        woorden.add(w)
        # Gehuwde naam: "slinger-aap" → voeg ook "slinger" en "aap" toe
        if "-" in w:
            woorden.update(w.split("-"))
    # Verwijder tussenvoegsels
    tussenvoegsels = {"van", "de", "het", "der", "den", "ten", "ter", "in", "op", "voor"}
    return woorden - tussenvoegsels


def _extract_achternaam(naam: str) -> str:
    """Probeer de achternaam te extraheren (alles na voorletters/voornaam)."""
    if not naam:
        return ""
    # Als er een komma in zit: "Slinger, Harry" → achternaam = "Slinger"
    if "," in naam:
        return naam.split(",")[0].strip()
    # Als eerste woord voorletters zijn (bijv. "A.M."): rest is achternaam
    parts = naam.split()
    if parts and re.match(r"^[A-Z]\.(?:[A-Z]\.)*$", parts[0]):
        return " ".join(parts[1:])
    return naam


def match_persoon(
    naam_uit_document: str,
    aanvrager_naam: str,
    partner_naam: str | None = None,
) -> str:
    """Koppel een naam uit een document aan aanvrager of partner.

    Houdt rekening met:
    - Gehuwde namen (Slinger-Aap matcht op zowel Slinger als Aap)
    - Voorletters vs volledige namen (A.M. de Boer matcht op Agnes de Boer)
    - Tussenvoegsels worden genegeerd

    Args:
        naam_uit_document: Naam zoals gevonden in het document
        aanvrager_naam: Volledige naam aanvrager uit dossier
        partner_naam: Volledige naam partner (of None)

    Returns:
        "aanvrager", "partner" of "gezamenlijk"
    """
    if not naam_uit_document:
        return "gezamenlijk"

    doc_woorden = _normalize(naam_uit_document)
    aanvrager_woorden = _normalize(aanvrager_naam)
    partner_woorden = _normalize(partner_naam) if partner_naam else set()

    if not doc_woorden:
        return "gezamenlijk"

    # Tel overlap
    overlap_aanvrager = len(doc_woorden & aanvrager_woorden)
    overlap_partner = len(doc_woorden & partner_woorden) if partner_woorden else 0

    # Minimaal 1 betekenisvol woord moet matchen (niet alleen "van" of "de")
    match_aanvrager = overlap_aanvrager >= 1
    match_partner = overlap_partner >= 1

    if match_aanvrager and match_partner:
        return "gezamenlijk"
    elif match_aanvrager:
        return "aanvrager"
    elif match_partner:
        return "partner"

    # Fallback: probeer achternaam-match
    doc_achternaam = _normalize(_extract_achternaam(naam_uit_document))
    aanvrager_achternaam = _normalize(_extract_achternaam(aanvrager_naam))
    partner_achternaam = _normalize(_extract_achternaam(partner_naam)) if partner_naam else set()

    if doc_achternaam & aanvrager_achternaam:
        return "aanvrager"
    if doc_achternaam & partner_achternaam:
        return "partner"

    return "gezamenlijk"
