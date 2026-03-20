"""
WOZ-waarde Opvragen (CLI)
=========================
Interactieve tool om WOZ-waarden op te vragen via het WOZ Waardeloket.

Gebruik:
    python opvragen.py
    python opvragen.py 9472VM 33
    python opvragen.py 1017CT 263 H
"""

import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from woz_client import WOZClient


def main():
    print("=" * 60)
    print("WOZ-waarde Opvragen (Kadaster WOZ Waardeloket)")
    print("=" * 60)

    client = WOZClient()

    # CLI argumenten of interactief
    if len(sys.argv) >= 3:
        postcode = sys.argv[1]
        huisnummer_str = sys.argv[2]
        toevoeging = sys.argv[3] if len(sys.argv) > 3 else None
    else:
        postcode = input("\nPostcode: ").strip()
        if not postcode:
            sys.exit(1)

        huisnummer_str = input("Huisnummer: ").strip()
        if not huisnummer_str:
            sys.exit(1)

        toevoeging = input("Toevoeging (optioneel): ").strip() or None

    # Parse huisnummer
    try:
        huisnummer = int(huisnummer_str)
    except ValueError:
        print(f"Ongeldig huisnummer: {huisnummer_str}")
        sys.exit(1)

    adres_str = f"{postcode} {huisnummer}"
    if toevoeging:
        adres_str += f" {toevoeging}"
    print(f"\nOpvragen: {adres_str}...")

    try:
        result = client.opvragen(postcode, huisnummer, toevoeging)
    except Exception as e:
        print(f"\nFOUT: {e}")
        sys.exit(1)

    if "error" in result:
        print(f"\n⚠  {result['error']}")
        sys.exit(1)

    adres = result["adres"]
    toev_str = ""
    if adres.get("huisletter"):
        toev_str += adres["huisletter"]
    if adres.get("toevoeging"):
        toev_str += adres["toevoeging"]

    print(f"\n  {adres['straat']} {adres['huisnummer']}{toev_str}, "
          f"{adres['postcode']} {adres['woonplaats']}")

    if adres.get("grondoppervlakte"):
        print(f"  Grondoppervlakte: {adres['grondoppervlakte']} m²")

    print("\n" + "=" * 60)
    print("  WOZ-waarden:")
    print("  " + "-" * 40)

    for i, w in enumerate(result["woz_waarden"]):
        peildatum = w["peildatum"]
        waarde = w["waarde"]
        # Peildatum 2024-01-01 → belastingjaar 2025
        jaar = int(peildatum[:4]) + 1 if peildatum else "?"
        marker = "  ◄ meest recent" if i == 0 else ""
        print(f"  {peildatum}  (jaar {jaar}):  € {waarde:>10,}{marker}")

    print("  " + "-" * 40)
    meest_recent = result["meest_recente_waarde"]
    if meest_recent:
        print(f"\n  Meest recente WOZ-waarde:  € {meest_recent:>10,}")
    print("=" * 60)


if __name__ == "__main__":
    main()
