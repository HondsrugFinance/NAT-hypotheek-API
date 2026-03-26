"""Parser voor UWV Verzekeringsbericht PDF bestanden."""

import re
from decimal import Decimal
from datetime import date, datetime
from typing import Optional

import PyPDF2

from .models import LoonItem, ContractBlok


# --- Nederlandse maandnamen voor datum-parsing ---
MAANDEN_NL = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4,
    "mei": 5, "juni": 6, "juli": 7, "augustus": 8,
    "september": 9, "oktober": 10, "november": 11, "december": 12,
}


def parse_dutch_decimal(s: str) -> Decimal:
    """Converteer Nederlands getalformaat naar Decimal: '1.234,56' → Decimal('1234.56')."""
    s = s.strip().replace("\u20ac", "").replace("\xa4", "").strip()
    # Verwijder duizendtallen-punt, vervang decimale komma door punt
    s = s.replace(".", "").replace(",", ".")
    return Decimal(s)


def parse_dutch_date(s: str) -> date:
    """Converteer 'DD-MM-YYYY' naar date object."""
    return datetime.strptime(s.strip(), "%d-%m-%Y").date()


def _extract_all_text(pdf_path: str) -> tuple[list[str], str]:
    """Extraheer tekst per pagina uit een PDF.

    Returns:
        pages: lijst van tekst per pagina
        full_text: alle tekst samengevoegd
    """
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            pages.append(text)
    return pages, "\n".join(pages)


def _extract_aanvrager_naam(full_text: str) -> str:
    """Extraheer naam aanvrager uit footer: 'De heer X' of 'Mevrouw X'."""
    m = re.search(r"(De heer|Mevrouw)\s+(.+?)(?:\n|Geboortedatum)", full_text)
    if m:
        return m.group(2).strip()
    return "Onbekend"


def _extract_aanmaakdatum(full_text: str) -> date:
    """Extraheer aanmaakdatum uit 'Datum: DD maand YYYY'."""
    m = re.search(r"Datum:\s*(\d{1,2})\s+(\w+)\s+(\d{4})", full_text)
    if m:
        dag = int(m.group(1))
        maand_str = m.group(2).lower()
        jaar = int(m.group(3))
        maand = MAANDEN_NL.get(maand_str, 1)
        return date(jaar, maand, dag)
    return date.today()


def _split_into_contract_blocks(loon_text: str) -> list[str]:
    """Splits de loongegevens-tekst op in blokken per contract.

    Elk blok begint met 'Werkgever/Instantie'.
    """
    # Split op 'Werkgever/Instantie' maar behoud het als begin van elk blok
    parts = re.split(r"(?=Werkgever/Instantie\s)", loon_text)
    blocks = [p.strip() for p in parts if p.strip() and "Werkgever/Instantie" in p]
    return blocks


def _parse_contract_header(block_text: str) -> tuple[str, str, str, Optional[str]]:
    """Parse de header van een contractblok.

    Returns: (werkgever_naam, loonheffingennummer, verzekerde_wetten, contractvorm)
    """
    # Werkgever/Instantie: alles na het label tot Loonheffingennummer
    werkgever = ""
    m = re.search(
        r"Werkgever/Instantie\s+(.+?)(?=\nLoonheffingennummer\s)",
        block_text, re.DOTALL
    )
    if m:
        werkgever = re.sub(r"\s+", " ", m.group(1)).strip()

    # Loonheffingennummer
    lhn = ""
    m = re.search(r"Loonheffingennummer\s+(\S+)", block_text)
    if m:
        lhn = m.group(1).strip()

    # Verzekerde wetten
    vw = ""
    m = re.search(r"Verzekerde wetten\s+(.+?)(?=\nContractvorm|\nPeriode)", block_text)
    if m:
        vw = m.group(1).strip()

    # Contractvorm - kan leeg zijn of over meerdere regels lopen
    contractvorm = None
    m = re.search(r"Contractvorm\s+(.*?)(?=\nPeriode)", block_text, re.DOTALL)
    if m:
        cv = re.sub(r"\s+", " ", m.group(1)).strip()
        if cv:
            contractvorm = cv

    return werkgever, lhn, vw, contractvorm


def _parse_loon_items(block_text: str) -> list[LoonItem]:
    """Parse alle loonregels uit een contractblok.

    Twee formaten:
    1. Zonder auto: DD-MM-YYYY t/m DD-MM-YYYY  NNN  € N.NNN,NN
    2. Met auto: periode+uur op eerste regel, dan eigen bijdrage/sv-loon/waarde privégebruik
    """
    items = []

    # Verwijder footer (VZB-xxx en alles erna op elke pagina)
    block_text = re.sub(r"VZB-\d+.*?(?=Werkgever/Instantie|$)", "", block_text, flags=re.DOTALL)

    # Verwijder herhaalde headers bij paginaovergangen
    block_text = re.sub(r"Periode\s+Aantal uur\s+Sv-loon\s*", "", block_text)

    # Zoek alle perioderegels (datum t/m datum + uur)
    # Patroon: DD-MM-YYYY t/m DD-MM-YYYY  NNN
    periode_pattern = re.compile(
        r"(\d{2}-\d{2}-\d{4})\s+t/m\s+(\d{2}-\d{2}-\d{4})\s+(\d+)"
    )

    # Splits tekst in regels
    lines = block_text.split("\n")

    i = 0
    while i < len(lines):
        line = lines[i]
        m = periode_pattern.search(line)
        if not m:
            i += 1
            continue

        periode_start = parse_dutch_date(m.group(1))
        periode_eind = parse_dutch_date(m.group(2))
        aantal_uur = Decimal(m.group(3))

        # Rest van de regel na het uren-getal
        rest = line[m.end():].strip()

        # Check of er een sv-loon op dezelfde regel staat (formaat zonder auto)
        sv_loon = None
        eigen_bijdrage_auto = None
        waarde_privegebruik_auto = None

        # Probeer sv-loon te vinden op dezelfde regel
        # Het euro-teken kan € of \xa4 zijn in de extractie
        sv_match = re.search(r"[\u20ac\xa4]\s*([-\d.,]+)", rest)
        if sv_match:
            sv_loon = parse_dutch_decimal(sv_match.group(1))
        else:
            # Auto-formaat: sv-loon staat op de volgende regels
            # Kijk vooruit naar "Eigen bijdrage auto" patroon
            j = i + 1
            while j < len(lines) and j <= i + 5:
                combined = lines[j] if j < len(lines) else ""
                if "Eigen bijdrage auto" in combined:
                    # Volgende regel bevat eigen bijdrage + sv-loon: "€ 149,01€ 6.597,34"
                    j += 1
                    if j < len(lines):
                        euro_vals = re.findall(
                            r"[\u20ac\xa4]\s*([-\d.,]+)", lines[j]
                        )
                        if len(euro_vals) >= 2:
                            eigen_bijdrage_auto = parse_dutch_decimal(euro_vals[0])
                            sv_loon = parse_dutch_decimal(euro_vals[1])
                        elif len(euro_vals) == 1:
                            sv_loon = parse_dutch_decimal(euro_vals[0])
                elif "Waarde priv" in combined:
                    # Volgende regel bevat waarde privégebruik
                    j += 1
                    if j < len(lines):
                        euro_vals = re.findall(
                            r"[\u20ac\xa4]\s*([-\d.,]+)", lines[j]
                        )
                        if euro_vals:
                            waarde_privegebruik_auto = parse_dutch_decimal(euro_vals[0])
                    break  # Na waarde privégebruik is dit loonitem compleet
                elif periode_pattern.search(combined):
                    # Volgende periode gevonden, stop
                    break
                j += 1

        if sv_loon is not None:
            items.append(LoonItem(
                periode_start=periode_start,
                periode_eind=periode_eind,
                aantal_uur=aantal_uur,
                sv_loon=sv_loon,
                eigen_bijdrage_auto=eigen_bijdrage_auto,
                waarde_privegebruik_auto=waarde_privegebruik_auto,
            ))

        i += 1

    return items


class PDFParseError(Exception):
    """Fout bij het parsen van een UWV Verzekeringsbericht PDF."""
    pass


def parse_uwv_pdf(pdf_path: str) -> tuple[str, date, list[ContractBlok]]:
    """Parse een UWV Verzekeringsbericht PDF.

    Args:
        pdf_path: Pad naar het PDF bestand.

    Returns:
        aanvrager_naam: Naam van de aanvrager
        aanmaakdatum: Datum van het verzekeringsbericht
        contract_blokken: Lijst van ContractBlok objecten

    Raises:
        PDFParseError: Bij onverwacht PDF-formaat of leesfouten.
    """
    try:
        pages, full_text = _extract_all_text(pdf_path)
    except FileNotFoundError:
        raise PDFParseError(f"PDF bestand niet gevonden: {pdf_path}")
    except Exception as e:
        raise PDFParseError(f"Kan PDF niet lezen: {e}")

    if not full_text.strip():
        raise PDFParseError("PDF bevat geen leesbare tekst.")

    aanvrager_naam = _extract_aanvrager_naam(full_text)
    aanmaakdatum = _extract_aanmaakdatum(full_text)

    # Vind start van loongegevens sectie
    loon_start = full_text.find("Loongegevens")
    if loon_start == -1:
        raise PDFParseError(
            "Geen 'Loongegevens' sectie gevonden. "
            "Is dit een UWV Verzekeringsbericht?"
        )

    loon_text = full_text[loon_start:]

    # Split in contractblokken
    raw_blocks = _split_into_contract_blocks(loon_text)

    if not raw_blocks:
        raise PDFParseError(
            "Geen contractblokken gevonden in de loongegevens. "
            "Controleer of het PDF-formaat correct is."
        )

    contract_blokken = []
    for raw_block in raw_blocks:
        try:
            werkgever, lhn, vw, contractvorm = _parse_contract_header(raw_block)
            loon_items = _parse_loon_items(raw_block)
        except Exception as e:
            raise PDFParseError(
                f"Fout bij parsen contractblok: {e}"
            )

        if loon_items:  # Alleen blokken met daadwerkelijke loongegevens
            contract_blokken.append(ContractBlok(
                werkgever_naam=werkgever,
                loonheffingennummer=lhn,
                verzekerde_wetten=vw,
                contractvorm=contractvorm,
                loon_items=loon_items,
            ))

    return aanvrager_naam, aanmaakdatum, contract_blokken
