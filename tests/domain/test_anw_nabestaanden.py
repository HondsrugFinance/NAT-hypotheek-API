"""
Test anw_nabestaanden.py — ANW nabestaanden calculator.

Test scenario's:
1. Harriette (35) met kind onder 18 → ANW, geen inkomen → volledig
2. Harriette (35) met kind onder 18, loondienst E2.200/mnd → ANW met korting
3. Harriette (35) met kind onder 18, loondienst E4.000/mnd → geen ANW (boven nihilgrens)
4. Harry (55) zonder kind, niet AO → geen ANW
5. Harry (55) met 50% AO → ANW
6. Nabestaande na AOW-leeftijd → geen ANW, wel AOW
7. Kostendeler situatie → lager ANW bedrag
8. Gezamenlijke huishouding → geen ANW
"""

from datetime import date
from anw_nabestaanden import bereken_nabestaanden_inkomen, bereken_nabestaanden_jaarbedrag


def test_1_volledig_anw_kind_onder_18():
    """Harriette 35j, kind 10j, geen eigen inkomen → volledig ANW."""
    result = bereken_nabestaanden_inkomen(
        geboortedatum_nabestaande=date(1991, 1, 1),
        peildatum=date(2026, 6, 1),
        heeft_kind_onder_18=True,
        geboortedatum_jongste_kind=date(2016, 3, 15),
        woonsituatie="alone",
    )

    print("=== Test 1: Volledig ANW, kind onder 18, geen inkomen ===")
    _print_result(result)

    assert result['anw_eligible'] is True
    assert "kind" in result['anw_eligible_reason'].lower()
    # Volledig ANW: 1668.49 + 128.18 = 1796.67
    assert result['anw_bruto_maand'] == 1796.67
    assert result['anw_bruto_jaar'] == round(1796.67 * 12, 2)
    print(f"[OK] ANW: E{result['anw_bruto_maand']}/mnd = E{result['anw_bruto_jaar']}/jr")

    # ANW stopt als kind 18 wordt (2034-03-15) of bij AOW
    assert result['anw_einddatum'] == '2034-03-15'
    print(f"[OK] ANW einddatum: {result['anw_einddatum']} (kind wordt 18)")


def test_2_anw_met_korting():
    """Harriette 35j, kind onder 18, loondienst E2.200/mnd → ANW met korting."""
    result = bereken_nabestaanden_inkomen(
        geboortedatum_nabestaande=date(1991, 1, 1),
        peildatum=date(2026, 6, 1),
        heeft_kind_onder_18=True,
        geboortedatum_jongste_kind=date(2016, 3, 15),
        woonsituatie="alone",
        inkomen_loondienst_maand=2200,
    )

    print("\n=== Test 2: ANW met korting, loondienst E2.200/mnd ===")
    _print_result(result)

    assert result['anw_eligible'] is True
    # Korting: (2200 - 1147.20) * 2/3 = 1052.80 * 0.6667 = 701.85
    # ANW: 1796.67 - 701.85 = 1094.82
    expected_excess = 2200 - 1147.20
    expected_deduction = round(0.6666667 * expected_excess, 2)
    expected_anw = round(1796.67 - expected_deduction, 2)
    print(f"  Verwacht: vrijlating E1147.20, excess E{expected_excess:.2f}, "
          f"korting E{expected_deduction:.2f}, ANW E{expected_anw:.2f}")
    assert abs(result['anw_bruto_maand'] - expected_anw) < 0.02
    print(f"[OK] ANW na korting: E{result['anw_bruto_maand']}/mnd")

    # Totaal: 2200 (loon) + ANW
    assert abs(result['totaal_bruto_maand'] - (2200 + result['anw_bruto_maand'])) < 0.01
    print(f"[OK] Totaal: E{result['totaal_bruto_maand']}/mnd")


def test_3_geen_anw_boven_nihilgrens():
    """Harriette, loondienst E4.000/mnd → boven nihilgrens, geen ANW."""
    result = bereken_nabestaanden_inkomen(
        geboortedatum_nabestaande=date(1991, 1, 1),
        peildatum=date(2026, 6, 1),
        heeft_kind_onder_18=True,
        geboortedatum_jongste_kind=date(2016, 3, 15),
        woonsituatie="alone",
        inkomen_loondienst_maand=4000,
    )

    print("\n=== Test 3: Geen ANW, loondienst boven nihilgrens ===")
    _print_result(result)

    assert result['anw_eligible'] is True  # Wel recht, maar bedrag = 0
    assert result['anw_bruto_maand'] == 0  # Boven nihilgrens E3617.28
    print(f"[OK] ANW = E0 (inkomen E4000 > nihilgrens E3617.28)")


def test_4_geen_anw_geen_kind_geen_ao():
    """Harry 55j, geen kind onder 18, niet AO → geen ANW-recht."""
    result = bereken_nabestaanden_inkomen(
        geboortedatum_nabestaande=date(1971, 1, 1),
        peildatum=date(2026, 6, 1),
        heeft_kind_onder_18=False,
        woonsituatie="alone",
        inkomen_loondienst_maand=3000,
    )

    print("\n=== Test 4: Geen ANW, geen kind, niet AO ===")
    _print_result(result)

    assert result['anw_eligible'] is False
    assert "45%" in result['anw_eligible_reason'] or "kind" in result['anw_eligible_reason'].lower()
    assert result['anw_bruto_maand'] == 0
    print(f"[OK] Geen ANW: {result['anw_eligible_reason']}")


def test_5_anw_door_ao():
    """Harry 55j, 50% AO → ANW-recht op grond van arbeidsongeschiktheid."""
    result = bereken_nabestaanden_inkomen(
        geboortedatum_nabestaande=date(1971, 1, 1),
        peildatum=date(2026, 6, 1),
        heeft_kind_onder_18=False,
        ao_percentage=50,
        woonsituatie="alone",
    )

    print("\n=== Test 5: ANW door AO >= 45% ===")
    _print_result(result)

    assert result['anw_eligible'] is True
    assert "arbeidsongeschikt" in result['anw_eligible_reason'].lower()
    assert result['anw_bruto_maand'] == 1796.67
    print(f"[OK] ANW: E{result['anw_bruto_maand']}/mnd (AO {50}%)")


def test_6_na_aow_leeftijd():
    """Nabestaande 68j → geen ANW, wel AOW alleenstaand."""
    result = bereken_nabestaanden_inkomen(
        geboortedatum_nabestaande=date(1955, 1, 1),
        peildatum=date(2026, 6, 1),
        heeft_kind_onder_18=False,
        woonsituatie="alone",
    )

    print("\n=== Test 6: Na AOW-leeftijd → AOW, geen ANW ===")
    _print_result(result)

    assert result['heeft_aow_bereikt'] is True
    assert result['anw_eligible'] is False
    assert result['anw_bruto_maand'] == 0
    # AOW alleenstaand: 1637.57 + 106.55 = 1744.12
    assert result['aow_bruto_maand'] == 1744.12
    print(f"[OK] AOW: E{result['aow_bruto_maand']}/mnd, ANW: E0")


def test_7_kostendeler():
    """Kostendeler → lager ANW bedrag."""
    result = bereken_nabestaanden_inkomen(
        geboortedatum_nabestaande=date(1991, 1, 1),
        peildatum=date(2026, 6, 1),
        heeft_kind_onder_18=True,
        geboortedatum_jongste_kind=date(2016, 3, 15),
        woonsituatie="cost_sharer",
    )

    print("\n=== Test 7: Kostendeler → lager ANW ===")
    _print_result(result)

    assert result['anw_eligible'] is True
    # Kostendeler: 1112.33 + 85.46 = 1197.79
    assert result['anw_bruto_maand'] == 1197.79
    print(f"[OK] ANW kostendeler: E{result['anw_bruto_maand']}/mnd")


def test_8_gezamenlijke_huishouding():
    """Gezamenlijke huishouding → geen ANW."""
    result = bereken_nabestaanden_inkomen(
        geboortedatum_nabestaande=date(1991, 1, 1),
        peildatum=date(2026, 6, 1),
        heeft_kind_onder_18=True,
        geboortedatum_jongste_kind=date(2016, 3, 15),
        woonsituatie="joint_household",
    )

    print("\n=== Test 8: Gezamenlijke huishouding → geen ANW ===")
    _print_result(result)

    assert result['anw_eligible'] is False
    assert "huishouding" in result['anw_eligible_reason'].lower()
    assert result['anw_bruto_maand'] == 0
    print(f"[OK] Geen ANW: {result['anw_eligible_reason']}")


def test_9_nabestaandenpensioen_kort_anw_niet():
    """Nabestaandenpensioen E850/mnd kort ANW NIET, telt wel mee in totaal."""
    result = bereken_nabestaanden_inkomen(
        geboortedatum_nabestaande=date(1991, 1, 1),
        peildatum=date(2026, 6, 1),
        heeft_kind_onder_18=True,
        geboortedatum_jongste_kind=date(2016, 3, 15),
        woonsituatie="alone",
        nabestaandenpensioen_maand=850,
    )

    print("\n=== Test 9: Nabestaandenpensioen kort ANW niet ===")
    _print_result(result)

    # ANW ongewijzigd (pensioen kort niet)
    assert result['anw_bruto_maand'] == 1796.67
    # Totaal = ANW + pensioen
    assert abs(result['totaal_bruto_maand'] - (1796.67 + 850)) < 0.01
    print(f"[OK] ANW ongewijzigd: E{result['anw_bruto_maand']}, totaal: E{result['totaal_bruto_maand']}")


def test_10_jaarbedrag_simpel():
    """Test vereenvoudigde jaarbedrag functie."""
    jaar = bereken_nabestaanden_jaarbedrag(
        geboortedatum_nabestaande=date(1991, 1, 1),
        peildatum=date(2026, 6, 1),
        heeft_kind_onder_18=True,
        geboortedatum_jongste_kind=date(2016, 3, 15),
        woonsituatie="alone",
        inkomen_loondienst_maand=2200,
        nabestaandenpensioen_maand=850,
    )

    print(f"\n=== Test 10: Jaarbedrag simpel ===")
    print(f"  Totaal bruto jaar: E{jaar:,.2f}")
    assert jaar > 0
    print(f"[OK] Jaarbedrag: E{jaar:,.2f}")


def _print_result(result: dict):
    """Print resultaat compact."""
    print(f"  ANW recht: {result['anw_eligible']} ({result['anw_eligible_reason']})")
    print(f"  ANW bruto: E{result['anw_bruto_maand']}/mnd = E{result['anw_bruto_jaar']}/jr")
    if result['anw_einddatum']:
        print(f"  ANW einddatum: {result['anw_einddatum']}")
    print(f"  AOW bereikt: {result['heeft_aow_bereikt']}")
    print(f"  AOW bruto: E{result['aow_bruto_maand']}/mnd = E{result['aow_bruto_jaar']}/jr")
    print(f"  Totaal bruto: E{result['totaal_bruto_maand']}/mnd = E{result['totaal_bruto_jaar']}/jr")
    if result['review_flags']:
        print(f"  Review flags: {result['review_flags']}")


if __name__ == '__main__':
    test_1_volledig_anw_kind_onder_18()
    test_2_anw_met_korting()
    test_3_geen_anw_boven_nihilgrens()
    test_4_geen_anw_geen_kind_geen_ao()
    test_5_anw_door_ao()
    test_6_na_aow_leeftijd()
    test_7_kostendeler()
    test_8_gezamenlijke_huishouding()
    test_9_nabestaandenpensioen_kort_anw_niet()
    test_10_jaarbedrag_simpel()
    print("\n" + "=" * 60)
    print("Alle tests geslaagd!")
