"""Afsluiting sectie — aandachtspunten + ondertekening."""

from adviesrapport_v2.texts import build_closing_bullets


def build_closing_section() -> dict:
    """Bouw de afsluiting sectie met aandachtspunten."""
    return {
        "id": "closing",
        "title": "Afsluiting",
        "visible": True,
        "bullets_heading": "Belangrijke aandachtspunten",
        "bullets": build_closing_bullets(),
    }
