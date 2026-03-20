"""
Calcasa Modelwaarde Bepaling
=============================
Bepaal de Calcasa modelmatige woningwaarde via de desktoptaxatie API.
Gratis — er wordt geen taxatie uitgevoerd.

Gebruik:
    python waardebepaling.py
"""

import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from calcasa_client import CalcasaClient


def main():
    print("=" * 60)
    print("Calcasa Modelwaarde Bepaling")
    print("=" * 60)

    with CalcasaClient() as client:
        # Token
        print("\nInloggen...")
        try:
            client.refresh_access_token()
            print("  OK")
        except Exception as e:
            print(f"  FOUT: {e}")
            sys.exit(1)

        # Adres
        postcode = input("\nPostcode: ").strip()
        if not postcode:
            sys.exit(1)

        adressen = client.zoek_adressen(postcode)
        if not adressen:
            print("Geen adressen gevonden.")
            sys.exit(1)

        straten = set(a.get("straat", "?") for a in adressen)
        for straat in sorted(straten):
            nummers = sorted(a.get("huisnummer", 0) for a in adressen if a.get("straat") == straat)
            preview = ", ".join(str(n) for n in nummers[:15])
            more = f" ... (+{len(nummers) - 15})" if len(nummers) > 15 else ""
            print(f"  {straat}: {preview}{more}")

        huisnummer = input("Huisnummer: ").strip()
        adres = next((a for a in adressen if str(a.get("huisnummer")) == huisnummer
                       and not a.get("toevoeging")), None)
        if not adres:
            # Probeer met toevoeging
            adres = next((a for a in adressen if str(a.get("huisnummer")) == huisnummer.split()[0]), None)
        if not adres:
            print(f"Huisnummer {huisnummer} niet gevonden.")
            sys.exit(1)

        print(f"\n  {adres['straat']} {adres['huisnummer']}"
              f"{adres.get('toevoeging', '')}, "
              f"{adres['postcode']} {adres['plaats']}")

        # Modelwaarde bepalen
        print("\nModelwaarde bepalen...")
        result = client.bepaal_modelwaarde("ing", adres["id"])

        print("\n" + "=" * 60)
        if result.get("modelwaarde"):
            print(f"  Modelwaarde:  EUR {result['modelwaarde']:>10,}")
            print(f"  LTV test:     {result['ltv_percentage']:.2f}%")
            print(f"  Max LTV:      {result['max_ltv'] * 100:.0f}%")
            print(f"  Max hypotheek: EUR {round(result['modelwaarde'] * result['max_ltv']):>10,}")
        else:
            print(f"  FOUT: {result.get('error', 'Onbekend')}")
        print("=" * 60)


if __name__ == "__main__":
    main()
