"""IBL-tool wrapper — berekent toetsinkomen uit UWV Verzekeringsbericht."""

import asyncio
import logging
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

logger = logging.getLogger("nat-api.ibl")

# Voeg IBL-tool toe aan sys.path (meerdere mogelijke locaties)
_possible_paths = [
    os.path.join(os.path.dirname(__file__), "..", "B1", "IBL-tool"),
    os.path.join(os.getcwd(), "B1", "IBL-tool"),
    "/opt/render/project/src/B1/IBL-tool",  # Render deploy pad
]
for _p in _possible_paths:
    _p = os.path.abspath(_p)
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)
        logger.info("IBL-tool pad gevonden: %s", _p)
        break
else:
    logger.warning("IBL-tool pad niet gevonden in: %s", _possible_paths)

_executor = ThreadPoolExecutor(max_workers=2)


def _sync_ibl(pdf_bytes: bytes, pensioen_maand: float) -> list[dict]:
    """Synchrone IBL-berekening (draait in thread pool)."""
    from ibl.pdf_parser import parse_uwv_pdf
    from ibl.beslisboom import voer_berekening_uit

    # Schrijf bytes naar temp bestand (PyPDF2 verwacht een bestandspad)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        # Parse UWV PDF
        naam, datum, blokken = parse_uwv_pdf(tmp_path)

        # Bereken toetsinkomen
        resultaten = voer_berekening_uit(
            blokken, naam, datum, Decimal(str(pensioen_maand))
        )

        # Converteer naar serialiseerbare dicts
        output = []
        for r in resultaten:
            output.append({
                "werkgever_naam": r.werkgever_naam,
                "berekening_type": r.berekening_type.value if hasattr(r.berekening_type, "value") else str(r.berekening_type),
                "toetsinkomen": float(r.toetsinkomen),
                "aanvrager_naam": r.aanvrager_naam,
                "waarschuwingen": r.waarschuwingen,
            })

        logger.info("IBL berekening: %d resultaten, totaal toetsinkomen %.2f",
                     len(output), sum(r["toetsinkomen"] for r in output))
        return output

    finally:
        os.unlink(tmp_path)


async def run_ibl(pdf_bytes: bytes, pensioen_maand: float = 0.0) -> list[dict]:
    """Bereken toetsinkomen uit UWV Verzekeringsbericht (async wrapper).

    Args:
        pdf_bytes: UWV PDF als bytes
        pensioen_maand: Eigen bijdrage pensioen per maand (van salarisstrook)

    Returns:
        Lijst van resultaten per werkgever/contract:
        [{"werkgever_naam": "...", "berekening_type": "A", "toetsinkomen": 47473.44, ...}]
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _sync_ibl, pdf_bytes, pensioen_maand)
