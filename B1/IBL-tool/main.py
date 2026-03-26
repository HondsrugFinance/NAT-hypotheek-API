"""IBL Toetsinkomen Calculator - CLI entry point."""

import sys
import argparse
from decimal import Decimal

from ibl.pdf_parser import parse_uwv_pdf, PDFParseError
from ibl.beslisboom import voer_berekening_uit
from ibl.output import formatteer_resultaat


def main():
    parser = argparse.ArgumentParser(
        description="IBL Toetsinkomen Calculator v8.1.1"
    )
    parser.add_argument("pdf", help="Pad naar UWV Verzekeringsbericht PDF")
    parser.add_argument(
        "--pensioen", type=str, required=True,
        help="Eigen bijdrage pensioen per maand (bijv. 48.64)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Toon tussenberekeningen"
    )

    args = parser.parse_args()

    # Parse pensioen bedrag
    pensioen_str = args.pensioen.replace(",", ".")
    pensioen_maand = Decimal(pensioen_str)

    # Parse PDF
    print(f"Verwerken: {args.pdf}")
    try:
        aanvrager_naam, aanmaakdatum, contract_blokken = parse_uwv_pdf(args.pdf)
    except PDFParseError as e:
        print(f"FOUT: {e}")
        sys.exit(1)

    print(f"Aanvrager: {aanvrager_naam}")
    print(f"Aanmaakdatum: {aanmaakdatum}")
    print(f"Contractblokken gevonden: {len(contract_blokken)}")
    print()

    # Voer berekening uit
    resultaten = voer_berekening_uit(
        contract_blokken,
        aanvrager_naam,
        aanmaakdatum,
        pensioen_maand,
    )

    if not resultaten:
        print("Geen actieve contracten gevonden voor berekening.")
        sys.exit(1)

    # Toon resultaten
    for resultaat in resultaten:
        print(formatteer_resultaat(resultaat, verbose=args.verbose))
        print()

    # Totaal toetsinkomen (som van alle berekeningen)
    if len(resultaten) > 1:
        totaal = sum(r.toetsinkomen for r in resultaten)
        print(f"TOTAAL TOETSINKOMEN: EUR {totaal:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))


if __name__ == "__main__":
    main()
