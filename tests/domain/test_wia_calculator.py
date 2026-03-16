"""
Test wia_calculator.py — WIA uitkering calculator.

Test scenario's:
1. Loondoorbetaling jaar 1 (100% doorbetaling)
2. Loondoorbetaling jaar 2 (70% doorbetaling)
3. Geen WIA (AO < 35%)
4. IVA (80% AO, duurzaam)
5. WGA 80-100% (80% AO, niet duurzaam)
6. WGA LGU zonder werken (maand 1-2: 75%, maand 3+: 70%)
7. WGA loonaanvulling variant 2 (benutting 50%)
8. WGA loonaanvulling variant 1 (benutting >= 100%)
9. WGA vervolguitkering (benutting < 50%)
10. Buitenlands/niet-werknemer → geen uitkering
11. LGU-duur berekening
12. Vereenvoudigde helper (bereken_wia_bruto_jaar)
"""

from datetime import date, timedelta
from wia_calculator import bereken_wia_uitkering, bereken_wia_bruto_jaar, _bereken_lgu_duur


# Standaard testdata
SV_LOON_JAAR = 50400  # 4200/mnd
# Dagloon = 50400 / 261 = 193.103...
# Maandloon = 193.103 * 21.75 = 4199.99 ≈ 4200
SICK_DAY = date(2024, 1, 15)
WACHTTIJD_EINDE = SICK_DAY + timedelta(weeks=104)  # 2026-01-12


def test_1_loondoorbetaling_jaar1():
    """Jaar 1 ziekte: 100% doorbetaling, minimaal minimumloon."""
    peil = SICK_DAY + timedelta(weeks=26)  # halverwege jaar 1

    result = bereken_wia_uitkering(
        peildatum=peil,
        first_sick_day=SICK_DAY,
        sv_loon_12m_total=SV_LOON_JAAR,
        pre_disability_gross_month=4200,
        ao_percentage=50,
        salary_continuation_pct_year1=1.0,
    )

    print("\n=== Test 1: Loondoorbetaling jaar 1 ===")
    _print_result(result)

    assert result['status'] == 'loondoorbetaling'
    # 100% van 4200 = 4200
    assert result['uwv_uitkering_bruto_per_maand'] == 4200
    assert result['loon_uit_arbeid_bruto_per_maand'] == 0
    print("[OK] Loondoorbetaling jaar 1: 100% = 4200/mnd")


def test_2_loondoorbetaling_jaar2():
    """Jaar 2 ziekte: 70% doorbetaling, geen minimumloon-vloer."""
    peil = SICK_DAY + timedelta(weeks=78)  # halverwege jaar 2

    result = bereken_wia_uitkering(
        peildatum=peil,
        first_sick_day=SICK_DAY,
        sv_loon_12m_total=SV_LOON_JAAR,
        pre_disability_gross_month=4200,
        ao_percentage=50,
        salary_continuation_pct_year2=0.70,
    )

    print("\n=== Test 2: Loondoorbetaling jaar 2 ===")
    _print_result(result)

    assert result['status'] == 'loondoorbetaling'
    # 70% van 4200 = 2940
    assert result['uwv_uitkering_bruto_per_maand'] == 2940
    print("[OK] Loondoorbetaling jaar 2: 70% = 2940/mnd")


def test_3_geen_wia():
    """AO < 35% → geen WIA-recht."""
    peil = WACHTTIJD_EINDE + timedelta(days=30)

    result = bereken_wia_uitkering(
        peildatum=peil,
        first_sick_day=SICK_DAY,
        sv_loon_12m_total=SV_LOON_JAAR,
        ao_percentage=30,
        current_actual_gross_wages_per_month=3000,
        uses_rvc_input_directly=False,
    )

    print("\n=== Test 3: Geen WIA (AO 30%) ===")
    _print_result(result)

    assert result['status'] == 'geen_wia'
    assert result['uwv_uitkering_bruto_per_maand'] == 0
    assert result['loon_uit_arbeid_bruto_per_maand'] == 3000
    print("[OK] Geen WIA: AO 30% < 35%")


def test_4_iva():
    """80% AO, duurzaam → IVA = 75% maandloon."""
    peil = WACHTTIJD_EINDE + timedelta(days=30)
    maandloon = SV_LOON_JAAR / 261 * 21.75

    result = bereken_wia_uitkering(
        peildatum=peil,
        first_sick_day=SICK_DAY,
        sv_loon_12m_total=SV_LOON_JAAR,
        ao_percentage=85,
        is_durable=True,
        uses_rvc_input_directly=False,
    )

    print("\n=== Test 4: IVA (85% AO, duurzaam) ===")
    _print_result(result)

    assert result['status'] == 'iva'
    expected = round(0.75 * maandloon, 2)
    assert abs(result['uwv_uitkering_bruto_per_maand'] - expected) < 0.02
    print(f"[OK] IVA: 75% x {maandloon:.2f} = {expected:.2f}/mnd")


def test_5_wga_80_100():
    """85% AO, niet duurzaam → WGA 80-100%."""
    peil = WACHTTIJD_EINDE + timedelta(days=90)  # maand 3+
    maandloon = SV_LOON_JAAR / 261 * 21.75

    result = bereken_wia_uitkering(
        peildatum=peil,
        first_sick_day=SICK_DAY,
        sv_loon_12m_total=SV_LOON_JAAR,
        ao_percentage=85,
        is_durable=False,
        uses_rvc_input_directly=False,
    )

    print("\n=== Test 5: WGA 80-100% (85% AO, niet duurzaam) ===")
    _print_result(result)

    assert result['status'] == 'wga_80_100'
    expected = round(0.70 * maandloon, 2)
    assert abs(result['uwv_uitkering_bruto_per_maand'] - expected) < 0.02
    print(f"[OK] WGA 80-100%: 70% x {maandloon:.2f} = {expected:.2f}/mnd")


def test_6_wga_lgu_zonder_werken():
    """WGA LGU zonder werken, maand 3+: 70% maandloon."""
    peil = WACHTTIJD_EINDE + timedelta(days=90)  # maand 3+
    maandloon = SV_LOON_JAAR / 261 * 21.75

    result = bereken_wia_uitkering(
        peildatum=peil,
        first_sick_day=SICK_DAY,
        sv_loon_12m_total=SV_LOON_JAAR,
        ao_percentage=50,
        current_actual_gross_wages_per_month=0,
        uses_rvc_input_directly=False,
        employment_history_years_to_2015=8,
        employment_history_years_from_2016=4,
    )

    print("\n=== Test 6: WGA LGU zonder werken (maand 3+) ===")
    _print_result(result)

    assert result['status'] == 'wga_loongerelateerd'
    expected = round(0.70 * maandloon, 2)
    assert abs(result['uwv_uitkering_bruto_per_maand'] - expected) < 0.02
    print(f"[OK] WGA LGU: 70% x {maandloon:.2f} = {expected:.2f}/mnd")


def test_7_wga_loonaanvulling_variant2():
    """
    50% AO, benutting 50% → loonaanvulling variant 2.
    = 70% × (maandloon - rvc)
    """
    maandloon = SV_LOON_JAAR / 261 * 21.75
    rvc = maandloon * 0.50  # 50% AO → rvc = 50% van maandloon
    actual = rvc * 0.50     # 50% benutting

    # Peildatum ruim na LGU
    peil = WACHTTIJD_EINDE + timedelta(weeks=130)

    result = bereken_wia_uitkering(
        peildatum=peil,
        first_sick_day=SICK_DAY,
        sv_loon_12m_total=SV_LOON_JAAR,
        ao_percentage=50,
        current_actual_gross_wages_per_month=actual,
        uses_rvc_input_directly=False,
        employment_history_years_to_2015=8,
        employment_history_years_from_2016=4,
    )

    print("\n=== Test 7: WGA loonaanvulling variant 2 (50% AO, 50% benutting) ===")
    _print_result(result)

    assert result['status'] == 'wga_loonaanvulling'
    expected_uwv = round(0.70 * (maandloon - rvc), 2)
    assert abs(result['uwv_uitkering_bruto_per_maand'] - expected_uwv) < 0.02
    expected_total = round(expected_uwv + actual, 2)
    assert abs(result['totaal_bruto_per_maand'] - expected_total) < 0.02
    print(f"[OK] Loonaanvulling v2: 70% x ({maandloon:.2f} - {rvc:.2f}) = {expected_uwv:.2f}/mnd")
    print(f"     Totaal: {expected_uwv:.2f} + {actual:.2f} = {expected_total:.2f}/mnd")


def test_8_wga_loonaanvulling_variant1():
    """
    50% AO, benutting >= 100% → loonaanvulling variant 1.
    = 70% × (maandloon - feitelijk loon)
    """
    maandloon = SV_LOON_JAAR / 261 * 21.75
    rvc = maandloon * 0.50
    actual = rvc * 1.20  # 120% benutting

    peil = WACHTTIJD_EINDE + timedelta(weeks=130)

    result = bereken_wia_uitkering(
        peildatum=peil,
        first_sick_day=SICK_DAY,
        sv_loon_12m_total=SV_LOON_JAAR,
        ao_percentage=50,
        current_actual_gross_wages_per_month=actual,
        uses_rvc_input_directly=False,
        employment_history_years_to_2015=8,
        employment_history_years_from_2016=4,
    )

    print("\n=== Test 8: WGA loonaanvulling variant 1 (50% AO, 120% benutting) ===")
    _print_result(result)

    assert result['status'] == 'wga_loonaanvulling'
    expected_uwv = round(0.70 * (maandloon - actual), 2)
    assert abs(result['uwv_uitkering_bruto_per_maand'] - expected_uwv) < 0.02
    print(f"[OK] Loonaanvulling v1: 70% x ({maandloon:.2f} - {actual:.2f}) = {expected_uwv:.2f}/mnd")


def test_9_wga_vervolg():
    """
    50% AO, benutting < 50% → vervolguitkering.
    AO-klasse 45-55% → 35% van minimumloon.
    """
    peil = WACHTTIJD_EINDE + timedelta(weeks=130)
    maandloon = SV_LOON_JAAR / 261 * 21.75
    rvc = maandloon * 0.50
    actual = rvc * 0.30  # 30% benutting → < 50%

    min_wage = 2177.40  # voorbeeld minimumloon

    result = bereken_wia_uitkering(
        peildatum=peil,
        first_sick_day=SICK_DAY,
        sv_loon_12m_total=SV_LOON_JAAR,
        ao_percentage=50,
        current_actual_gross_wages_per_month=actual,
        uses_rvc_input_directly=False,
        employment_history_years_to_2015=8,
        employment_history_years_from_2016=4,
        minimum_wage_month_reference=min_wage,
    )

    print("\n=== Test 9: WGA vervolguitkering (50% AO, 30% benutting) ===")
    _print_result(result)

    assert result['status'] == 'wga_vervolg'
    # AO-klasse 45-55% → 35%
    base = min(min_wage, maandloon)
    expected_uwv = round(0.35 * base, 2)
    assert abs(result['uwv_uitkering_bruto_per_maand'] - expected_uwv) < 0.02
    print(f"[OK] Vervolguitkering: 35% x {base:.2f} = {expected_uwv:.2f}/mnd")


def test_10_buitenlands():
    """Buitenlands inkomen → geen uitkering."""
    result = bereken_wia_uitkering(
        peildatum=WACHTTIJD_EINDE + timedelta(days=30),
        first_sick_day=SICK_DAY,
        sv_loon_12m_total=SV_LOON_JAAR,
        ao_percentage=50,
        is_foreign_income_case=True,
        current_actual_gross_wages_per_month=2000,
    )

    print("\n=== Test 10: Buitenlands inkomen ===")
    _print_result(result)

    assert result['status'] == 'geen_wia'
    assert result['uwv_uitkering_bruto_per_maand'] == 0
    assert "foreign_or_non_nl_employee_case_out_of_scope" in result['manual_review_flags']
    print("[OK] Geen uitkering bij buitenlands inkomen")


def test_11_lgu_duur():
    """Test LGU-duur berekening."""
    print("\n=== Test 11: LGU-duur berekening ===")

    # 8 jaren t/m 2015 + 4 jaren vanaf 2016 = 12 totaal
    # Eerste 10: 8 pre + 2 post = 10 maanden
    # Resterend pre: 0, resterend post: 2 x 0.5 = 1
    # Totaal: 11 maanden
    duur = _bereken_lgu_duur(years_to_2015=8, years_from_2016=4)
    assert duur == 11
    print(f"  8+4 jaren = {duur} maanden LGU [OK]")

    # 5 jaren t/m 2015, 0 vanaf 2016 = 5
    # Eerste 5: 5 maanden, minimum 3
    duur = _bereken_lgu_duur(years_to_2015=5, years_from_2016=0)
    assert duur == 5
    print(f"  5+0 jaren = {duur} maanden LGU [OK]")

    # 2 jaren → minimum 3 maanden
    duur = _bereken_lgu_duur(years_to_2015=2, years_from_2016=0)
    assert duur == 3
    print(f"  2+0 jaren = {duur} maanden LGU (minimum 3) [OK]")

    # 20 + 10 = 30 → 10 + 10 + 5 = 25 → max 24
    duur = _bereken_lgu_duur(years_to_2015=20, years_from_2016=10)
    assert duur == 24
    print(f"  20+10 jaren = {duur} maanden LGU (maximum 24) [OK]")

    # Met WW-aftrek
    duur = _bereken_lgu_duur(years_to_2015=8, years_from_2016=4, ww_months_to_deduct=3)
    assert duur == 8  # 11 - 3 = 8
    print(f"  8+4-3ww = {duur} maanden LGU [OK]")


def test_12_helper_bruto_jaar():
    """Test vereenvoudigde helper."""
    print("\n=== Test 12: bereken_wia_bruto_jaar helper ===")

    # 50% AO, na LGU, geen werken
    result = bereken_wia_bruto_jaar(
        ao_percentage=50,
        sv_loon_jaar=SV_LOON_JAAR,
        feitelijk_loon_maand=0,
        fase="na_lgu",
        minimum_wage_month_reference=2177.40,
    )

    print(f"  Status: {result['status']}")
    print(f"  UWV: {result['uwv_uitkering_bruto_maand']}/mnd = {result['uwv_uitkering_bruto_jaar']}/jr")
    print(f"  Totaal: {result['totaal_bruto_maand']}/mnd = {result['totaal_bruto_jaar']}/jr")

    # 50% AO, geen werken (benutting 0% < 50%) → vervolguitkering
    assert result['status'] == 'wga_vervolg'
    # 45-55% klasse → 35% van minimumloon
    expected = round(0.35 * 2177.40, 2)
    assert abs(result['uwv_uitkering_bruto_maand'] - expected) < 0.02
    print(f"  [OK] Vervolg: 35% x 2177.40 = {expected}/mnd")

    # IVA
    result_iva = bereken_wia_bruto_jaar(
        ao_percentage=90,
        sv_loon_jaar=SV_LOON_JAAR,
        is_durable=True,
        fase="na_lgu",
    )
    assert result_iva['status'] == 'iva'
    print(f"  [OK] IVA: {result_iva['uwv_uitkering_bruto_maand']}/mnd")


def test_13_route_a_rvc_direct():
    """Test Route A: RVC in euro's direct invoer."""
    peil = WACHTTIJD_EINDE + timedelta(weeks=130)

    # RVC = 2100, actual = 1050 → benutting 50%
    # Maandloon = 4200 (approx)
    # Lookaanvulling v2: 70% x (4200 - 2100) = 1470
    result = bereken_wia_uitkering(
        peildatum=peil,
        first_sick_day=SICK_DAY,
        sv_loon_12m_total=SV_LOON_JAAR,
        ao_percentage=50,  # wordt overschreven door RVC
        residual_earning_capacity_per_month=2100,
        current_actual_gross_wages_per_month=1050,
        uses_rvc_input_directly=True,
        employment_history_years_to_2015=8,
        employment_history_years_from_2016=4,
    )

    print("\n=== Test 13: Route A (RVC direct) ===")
    _print_result(result)

    assert result['status'] == 'wga_loonaanvulling'
    maandloon = result['grondslag_maandloon']
    expected = round(0.70 * (maandloon - 2100), 2)
    assert abs(result['uwv_uitkering_bruto_per_maand'] - expected) < 1
    print(f"[OK] Route A: LA v2 = {result['uwv_uitkering_bruto_per_maand']}/mnd")


def test_14_loonsanctie():
    """Loonsanctie verlengt wachttijd."""
    # Normaal wachttijd: 104 weken → 2026-01-12
    # Met 26 weken sanctie → 130 weken → 2026-07-13 (approx)
    peil = WACHTTIJD_EINDE + timedelta(weeks=10)  # Zou normaal WIA zijn

    result = bereken_wia_uitkering(
        peildatum=peil,
        first_sick_day=SICK_DAY,
        sv_loon_12m_total=SV_LOON_JAAR,
        pre_disability_gross_month=4200,
        ao_percentage=50,
        salary_continuation_pct_year2=0.70,
        wage_sanction_extension_weeks=26,
    )

    print("\n=== Test 14: Loonsanctie verlengt wachttijd ===")
    _print_result(result)

    # Nog steeds in loondoorbetaling door verlenging
    assert result['status'] == 'loondoorbetaling'
    assert "wage_sanction_applied" in result['manual_review_flags']
    print("[OK] Loonsanctie: nog in loondoorbetaling")


def _print_result(result: dict):
    """Print resultaat compact."""
    print(f"  Status: {result['status']}")
    print(f"  UWV uitkering: {result['uwv_uitkering_bruto_per_maand']:,.2f}/mnd")
    print(f"  Loon uit arbeid: {result['loon_uit_arbeid_bruto_per_maand']:,.2f}/mnd")
    print(f"  Totaal bruto: {result['totaal_bruto_per_maand']:,.2f}/mnd "
          f"= {result['totaal_bruto_per_jaar']:,.2f}/jr")
    print(f"  Grondslag maandloon: {result['grondslag_maandloon']:,.2f}")
    print(f"  RVC: {result['restverdiencapaciteit_euro_per_maand']:,.2f}/mnd "
          f"(benutting: {result['benuttingspercentage_restverdiencapaciteit']:.1f}%)")
    if result['manual_review_flags']:
        print(f"  Flags: {result['manual_review_flags']}")
    for t in result['toelichting']:
        print(f"    > {t}")


if __name__ == '__main__':
    test_1_loondoorbetaling_jaar1()
    test_2_loondoorbetaling_jaar2()
    test_3_geen_wia()
    test_4_iva()
    test_5_wga_80_100()
    test_6_wga_lgu_zonder_werken()
    test_7_wga_loonaanvulling_variant2()
    test_8_wga_loonaanvulling_variant1()
    test_9_wga_vervolg()
    test_10_buitenlands()
    test_11_lgu_duur()
    test_12_helper_bruto_jaar()
    test_13_route_a_rvc_direct()
    test_14_loonsanctie()
    print("\n" + "=" * 60)
    print("Alle WIA tests geslaagd!")
