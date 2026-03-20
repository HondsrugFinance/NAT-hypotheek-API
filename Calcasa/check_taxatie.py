"""
Calcasa Desktop Taxatie Check
==============================
Check of een desktoptaxatie mogelijk is voor een adres bij een geldverstrekker.

Gebruik:
    python check_taxatie.py

Vereist .env met CALCASA_REFRESH_TOKEN.
"""

import sys
import io

# Fix Windows encoding voor console output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from calcasa_client import CalcasaClient


def main():
    print("=" * 60)
    print("Calcasa Desktop Taxatie - Check")
    print("=" * 60)

    with CalcasaClient() as client:
        # --- Token ---
        print("\n[1/5] Token vernieuwen...")
        try:
            if client.refresh_token:
                client.refresh_access_token()
                print("  OK - Access token vernieuwd")
            elif client.access_token:
                print("  OK - Bestaande bearer token gebruikt")
            else:
                print("  FOUT - Geen token beschikbaar. Vul .env in.")
                sys.exit(1)
        except Exception as e:
            print(f"  FOUT - Token refresh mislukt: {e}")
            if client.access_token:
                print("  Probeer met bestaande bearer token...")
            else:
                sys.exit(1)

        # --- Wallet ---
        print("\n[2/5] Wallet/saldo ophalen...")
        try:
            wallet = client.get_wallet_info()
            saldo = wallet.get("saldo", "?")
            limiet = wallet.get("limiet", "?")
            print(f"  Saldo: {saldo} / Limiet: {limiet}")
        except Exception as e:
            print(f"  Wallet info niet beschikbaar: {e}")

        # --- Banken ---
        print("\n[3/5] Beschikbare geldverstrekkers ophalen...")
        try:
            banken = client.get_banks()
            print(f"  {len(banken)} geldverstrekkers gevonden")
            for b in banken[:10]:
                print(f"     - {b.get('name', '?')} (slug: {b.get('slug', '?')})")
            if len(banken) > 10:
                print(f"     ... en {len(banken) - 10} meer")
        except Exception as e:
            print(f"  FOUT - Banken ophalen mislukt: {e}")
            sys.exit(1)

        # --- Adres zoeken ---
        postcode = input("\nPostcode (bijv. 9471HA): ").strip()
        if not postcode:
            print("Geen postcode opgegeven.")
            sys.exit(1)

        print(f"\n[4/5] Adressen zoeken voor {postcode}...")
        try:
            adressen = client.zoek_adressen(postcode)
            if not adressen:
                print("  Geen adressen gevonden voor deze postcode")
                sys.exit(1)

            print(f"  {len(adressen)} adressen gevonden")

            # Toon unieke straatnamen + huisnummers
            straten = set()
            for a in adressen:
                straten.add(a.get("straat", "?"))
            for straat in sorted(straten):
                nummers = sorted([
                    a.get("huisnummer", "?")
                    for a in adressen if a.get("straat") == straat
                ])
                preview = ", ".join(str(n) for n in nummers[:10])
                more = f", ... (+{len(nummers) - 10})" if len(nummers) > 10 else ""
                print(f"     {straat}: {preview}{more}")

        except Exception as e:
            print(f"  FOUT - Adres zoeken mislukt: {e}")
            sys.exit(1)

        # Huisnummer kiezen
        huisnummer = input("Huisnummer: ").strip()
        if not huisnummer:
            print("Geen huisnummer opgegeven.")
            sys.exit(1)

        # Zoek adres-ID
        adres_match = None
        for a in adressen:
            hn = str(a.get("huisnummer", ""))
            if hn == huisnummer:
                adres_match = a
                break

        if not adres_match:
            print(f"  Huisnummer {huisnummer} niet gevonden op {postcode}")
            sys.exit(1)

        adres_id = adres_match["id"]
        print(f"  Gevonden: {adres_match.get('straat', '?')} {huisnummer}, "
              f"{adres_match.get('plaats', '?')}")

        # Bank kiezen
        slug_list = ", ".join(b.get("slug", "?") for b in banken[:5])
        bank_slug = input(f"Geldverstrekker slug ({slug_list}): ").strip().lower()
        if not bank_slug:
            bank_slug = "ing"
            print(f"  Default: {bank_slug}")

        # Bedragen
        try:
            hypotheekbedrag = float(input("Verwacht hypotheekbedrag (EUR): ").strip() or "300000")
        except ValueError:
            hypotheekbedrag = 300000.0

        try:
            geschatte_waarde = float(input("Geschatte woningwaarde (EUR): ").strip() or "350000")
        except ValueError:
            geschatte_waarde = 350000.0

        # --- Check ---
        print(f"\n[5/5] Check desktoptaxatie bij {bank_slug}...")
        print(f"  Adres: {adres_match.get('straat')} {huisnummer}, {adres_match.get('plaats')}")
        print(f"  Hypotheek: EUR {hypotheekbedrag:,.0f}")
        print(f"  Geschatte waarde: EUR {geschatte_waarde:,.0f}")

        try:
            resultaat = client.check_taxatie_mogelijk(
                bank_slug=bank_slug,
                adres_id=adres_id,
                hypotheekbedrag=hypotheekbedrag,
                geschatte_waarde=geschatte_waarde,
                bestaande_bouw=True,
                eigen_bewoning=True,
            )

            print("\n" + "=" * 60)
            if resultaat["mogelijk"]:
                print(">>> DESKTOPTAXATIE IS MOGELIJK!")
                print(f"    Wizard doorlopen in {resultaat['stappen']} stappen")
                print(f"    Let op: kosten EUR 110 per taxatie")
            else:
                print(">>> DESKTOPTAXATIE NIET MOGELIJK")
                print(f"    Reden: {resultaat['blokkering']}")
                print(f"    Gestopt na stap {resultaat['stappen']}")
            print("=" * 60)

        except Exception as e:
            print(f"  Check mislukt: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
