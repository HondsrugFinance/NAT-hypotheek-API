"""Slimme tekst-detectie: bepaal de optimale input-methode per document.

Volgorde (goedkoopst/snelst eerst):
1. PyPDF2 tekst-extractie (gratis, instant)
2. Claude Vision (base64, ~10 sec)
3. Azure DI OCR (fallback bij slechte scans, ~15 sec)
"""

import io
import logging
import os
import sys

logger = logging.getLogger("nat-api.text-detector")

# PyPDF2 pad
_ibl_path = os.path.join(os.path.dirname(__file__), "..", "B1", "IBL-tool")
_possible_paths = [
    _ibl_path,
    os.path.join(os.getcwd(), "B1", "IBL-tool"),
    "/opt/render/project/src/B1/IBL-tool",
]
for _p in _possible_paths:
    _p = os.path.abspath(_p)
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)
        break

MIN_TEXT_WORDS = 50  # Minimaal 50 woorden voor bruikbare tekst


def extract_pdf_text(file_bytes: bytes) -> str | None:
    """Probeer tekst te extraheren uit een PDF via PyPDF2.

    Returns:
        Tekst als string, of None als het geen PDF is of geen tekst bevat.
    """
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        pages_text = []
        for page in reader.pages:
            text = page.extract_text() or ""
            pages_text.append(text)
        full_text = "\n\n".join(pages_text).strip()

        word_count = len(full_text.split())
        logger.info("PyPDF2: %d pagina's, %d woorden", len(reader.pages), word_count)

        if word_count >= MIN_TEXT_WORDS:
            return full_text
        else:
            logger.info("PyPDF2: te weinig tekst (%d woorden < %d), fallback naar vision",
                        word_count, MIN_TEXT_WORDS)
            return None
    except Exception as e:
        logger.debug("PyPDF2 extractie mislukt: %s", e)
        return None


def determine_input_method(file_bytes: bytes, mime_type: str) -> tuple[str, str | None]:
    """Bepaal de beste input-methode voor een document.

    Returns:
        Tuple van (methode, tekst):
        - ("pdf_text", "volledige tekst...") — PyPDF2 geslaagd
        - ("vision", None) — gebruik Claude Vision (geen tekst beschikbaar)
        - ("vision", None) — geen PDF, gebruik Vision direct
    """
    # Alleen voor PDF's proberen we PyPDF2 eerst
    if mime_type == "application/pdf":
        text = extract_pdf_text(file_bytes)
        if text:
            return "pdf_text", text

    # Voor afbeeldingen of PDF's zonder tekst → Vision
    return "vision", None
