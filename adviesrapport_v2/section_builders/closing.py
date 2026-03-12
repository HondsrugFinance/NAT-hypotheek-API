"""Afsluiting sectie — aandachtspunten + disclaimer tekst."""

from adviesrapport_v2.texts import build_attention_points, build_disclaimer_narratives


def build_attention_points_section(
    *,
    has_rvp: bool = True,
    has_box3: bool = False,
    customer_rejected_orv: bool = False,
) -> dict:
    """Bouw de aandachtspunten sectie."""
    items = build_attention_points(
        has_rvp=has_rvp,
        has_box3=has_box3,
        customer_rejected_orv=customer_rejected_orv,
    )
    return {
        "id": "attention-points",
        "title": "Aandachtspunten",
        "visible": True,
        "bullets": items,
    }


def build_closing_section() -> dict:
    """Bouw de disclaimer/afsluiting sectie."""
    return {
        "id": "disclaimer",
        "title": "Disclaimer",
        "visible": True,
        "narratives": build_disclaimer_narratives(),
    }
