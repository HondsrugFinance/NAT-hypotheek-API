"""
Test WW Calculator.

Testpersoon: SV-loon € 50.400/jaar (≈ € 4.200/mnd)
  dagloon = 50400 / 261 = 193.10
  maandloon = 193.10 × 21.75 = 4200.00

Arbeidsverleden: 15 jaar totaal, 1 jaar pre-2016 boven 10, 4 jaar vanaf 2016 boven 10
  → duur = 10 + 1 + 4×0.5 = 13 maanden

WW-uitkering:
  maand 1-2: 75% × 4200 = 3150/mnd
  maand 3+:  70% × 4200 = 2940/mnd
"""

from datetime import date
from ww_calculator import (
    bereken_ww_uitkering,
    bereken_ww_duur,
    bereken_ww_bruto_jaar,
)

SV_LOON = 50400.0
# 50400 / 261 = 193.103... × 21.75 = 4199.99 ≈ 4200
EXPECTED_MAANDLOON = round(50400 / 261 * 21.75, 2)  # 4199.99


# ============================================================
# Test 1: Volledig werkloos, maand 1-2 (75%)
# ============================================================
def test_1_volledig_werkloos_maand_1():
    result = bereken_ww_uitkering(
        peildatum=date(2026, 2, 1),
        first_unemployment_day=date(2026, 1, 15),
        sv_loon_12m_total=SV_LOON,
        employment_years_total_relevant=15,
        employment_years_pre2016_above10=1,
        employment_years_from2016_above10=4,
    )
    print(f"\nTest 1: Volledig werkloos maand 1")
    print(f"  Status: {result['ww_status']}")
    print(f"  WW-maandloon: {result['ww_month_wage']}")
    print(f"  WW-uitkering: {result['ww_benefit_gross_month']}")
    print(f"  Maand: {result['current_ww_month_number']}")

    assert result['ww_eligible'] is True
    assert result['ww_status'] == 'ww_lopend'
    assert result['current_ww_month_number'] == 1
    # 75% × ~4200 = ~3150
    assert abs(result['ww_benefit_gross_month'] - 0.75 * EXPECTED_MAANDLOON) < 1
    assert result['ww_duration_months'] == 13


# ============================================================
# Test 2: Volledig werkloos, maand 3+ (70%)
# ============================================================
def test_2_volledig_werkloos_maand_4():
    result = bereken_ww_uitkering(
        peildatum=date(2026, 5, 1),
        first_unemployment_day=date(2026, 1, 15),
        sv_loon_12m_total=SV_LOON,
        employment_years_total_relevant=15,
        employment_years_pre2016_above10=1,
        employment_years_from2016_above10=4,
    )
    print(f"\nTest 2: Volledig werkloos maand 4")
    print(f"  Status: {result['ww_status']}")
    print(f"  WW-uitkering: {result['ww_benefit_gross_month']}")
    print(f"  Maand: {result['current_ww_month_number']}")

    assert result['ww_status'] == 'ww_lopend'
    assert result['current_ww_month_number'] == 4
    # 70% × ~4200 = ~2940
    assert abs(result['ww_benefit_gross_month'] - 0.70 * EXPECTED_MAANDLOON) < 1


# ============================================================
# Test 3: Geen recht — wekeneis niet gehaald
# ============================================================
def test_3_geen_recht_wekeneis():
    result = bereken_ww_uitkering(
        peildatum=date(2026, 2, 1),
        first_unemployment_day=date(2026, 1, 15),
        sv_loon_12m_total=SV_LOON,
        weeks_worked_last_36=20,  # < 26
    )
    print(f"\nTest 3: Geen recht — wekeneis")
    print(f"  Status: {result['ww_status']}")

    assert result['ww_eligible'] is False
    assert result['ww_status'] == 'geen_ww'
    assert result['ww_benefit_gross_month'] == 0


# ============================================================
# Test 4: Geen recht — buitenlands inkomen
# ============================================================
def test_4_buitenlands():
    result = bereken_ww_uitkering(
        peildatum=date(2026, 2, 1),
        first_unemployment_day=date(2026, 1, 15),
        sv_loon_12m_total=SV_LOON,
        is_foreign_income_case=True,
    )
    print(f"\nTest 4: Buitenlands inkomen")
    print(f"  Status: {result['ww_status']}")

    assert result['ww_eligible'] is False
    assert 'foreign_or_non_nl_employee_case_out_of_scope' in result['manual_review_flags']


# ============================================================
# Test 5: Geen recht — onvoldoende urenverlies (hoog)
# ============================================================
def test_5_onvoldoende_urenverlies_hoog():
    result = bereken_ww_uitkering(
        peildatum=date(2026, 2, 1),
        first_unemployment_day=date(2026, 1, 15),
        sv_loon_12m_total=SV_LOON,
        avg_hours_per_week_before_unemployment=40,
        hours_lost_per_week=3,  # < 5
    )
    print(f"\nTest 5: Onvoldoende urenverlies (>= 10 uur)")
    print(f"  Status: {result['ww_status']}")

    assert result['ww_eligible'] is False


# ============================================================
# Test 6: Geen recht — onvoldoende urenverlies (laag)
# ============================================================
def test_6_onvoldoende_urenverlies_laag():
    result = bereken_ww_uitkering(
        peildatum=date(2026, 2, 1),
        first_unemployment_day=date(2026, 1, 15),
        sv_loon_12m_total=SV_LOON,
        avg_hours_per_week_before_unemployment=8,  # < 10 uur
        hours_lost_per_week=3,  # < 50% × 8 = 4
    )
    print(f"\nTest 6: Onvoldoende urenverlies (< 10 uur)")
    print(f"  Status: {result['ww_status']}")

    assert result['ww_eligible'] is False


# ============================================================
# Test 7: WW-duur berekening
# ============================================================
def test_7_ww_duur():
    # 15 jr totaal, 1 pre-2016 boven 10, 4 vanaf 2016 boven 10
    # = 10 + 1 + 4×0.5 = 13 maanden
    duur = bereken_ww_duur(
        employment_years_total_relevant=15,
        employment_years_pre2016_above10=1,
        employment_years_from2016_above10=4,
    )
    print(f"\nTest 7: WW-duur")
    print(f"  Duur: {duur} maanden")

    assert duur == 13

    # Minimum: alleen wekeneis (< 10 jr) → 3 maanden
    duur_min = bereken_ww_duur(employment_years_total_relevant=2)
    assert duur_min == 3

    # Maximum: veel jaren → 24 maanden cap
    duur_max = bereken_ww_duur(
        employment_years_total_relevant=40,
        employment_years_pre2016_above10=20,
        employment_years_from2016_above10=10,
    )
    assert duur_max == 24

    print(f"  Min: {duur_min}, Max: {duur_max}")


# ============================================================
# Test 8: Werken naast WW — aanvullende WW
# ============================================================
def test_8_werken_naast_ww():
    result = bereken_ww_uitkering(
        peildatum=date(2026, 5, 1),
        first_unemployment_day=date(2026, 1, 15),
        sv_loon_12m_total=SV_LOON,
        employment_years_total_relevant=15,
        employment_years_pre2016_above10=1,
        employment_years_from2016_above10=4,
        earnings_from_employment_month=1200,
    )
    print(f"\nTest 8: Werken naast WW")
    print(f"  Status: {result['ww_status']}")
    print(f"  WW-uitkering: {result['ww_benefit_gross_month']}")
    print(f"  Loon: {result['employment_income_gross_month']}")
    print(f"  Totaal: {result['total_gross_month']}")

    assert result['ww_status'] == 'ww_aanvullend'
    # WW basis = 70% × 4200 = 2940
    # Verrekening = 70% × 1200 = 840
    # WW na verrekening = 2940 - 840 = 2100
    ww_basis = 0.70 * EXPECTED_MAANDLOON
    verwacht_ww = ww_basis - 0.70 * 1200
    assert abs(result['ww_benefit_gross_month'] - verwacht_ww) < 1
    # Totaal = 1200 + 2100 = 3300
    assert abs(result['total_gross_month'] - (1200 + verwacht_ww)) < 1


# ============================================================
# Test 9: WW stopt door werkhervatting (87.5% regel)
# ============================================================
def test_9_stopregel_werk():
    maandloon = EXPECTED_MAANDLOON
    hoog_loon = 0.90 * maandloon  # > 87.5%

    result = bereken_ww_uitkering(
        peildatum=date(2026, 5, 1),
        first_unemployment_day=date(2026, 1, 15),
        sv_loon_12m_total=SV_LOON,
        employment_years_total_relevant=15,
        employment_years_pre2016_above10=1,
        employment_years_from2016_above10=4,
        earnings_from_employment_month=hoog_loon,
        previous_month_earnings_above_threshold=True,  # 2e maand boven grens
    )
    print(f"\nTest 9: Stopregel werkhervatting")
    print(f"  Status: {result['ww_status']}")
    print(f"  Loon: {hoog_loon:,.2f} (> 87.5% van {maandloon:,.2f})")

    assert result['ww_status'] == 'gestopt_door_werk'
    assert result['ww_benefit_gross_month'] == 0


# ============================================================
# Test 10: WW-duur verstreken
# ============================================================
def test_10_duur_verstreken():
    result = bereken_ww_uitkering(
        peildatum=date(2027, 4, 1),  # 14+ maanden na start
        first_unemployment_day=date(2026, 1, 15),
        sv_loon_12m_total=SV_LOON,
        employment_years_total_relevant=15,
        employment_years_pre2016_above10=1,
        employment_years_from2016_above10=4,
    )
    print(f"\nTest 10: Duur verstreken")
    print(f"  Status: {result['ww_status']}")
    print(f"  Maand: {result['current_ww_month_number']} (duur: {result['ww_duration_months']})")

    assert result['ww_status'] == 'beeindigd_duur'
    assert result['ww_benefit_gross_month'] == 0
    assert result['current_ww_month_number'] > result['ww_duration_months']


# ============================================================
# Test 11: Maximum dagloon aftopping
# ============================================================
def test_11_maximum_dagloon():
    hoog_loon = 120000  # dagloon = 120000/261 = 459.77 > max 304.25
    result = bereken_ww_uitkering(
        peildatum=date(2026, 5, 1),
        first_unemployment_day=date(2026, 1, 15),
        sv_loon_12m_total=hoog_loon,
        employment_years_total_relevant=15,
        employment_years_pre2016_above10=1,
        employment_years_from2016_above10=4,
    )
    max_maandloon = 304.25 * 21.75  # 6617.44

    print(f"\nTest 11: Maximum dagloon")
    print(f"  WW-maandloon: {result['ww_month_wage']} (max: {max_maandloon:,.2f})")
    print(f"  WW-uitkering: {result['ww_benefit_gross_month']}")

    assert result['ww_month_wage'] == round(max_maandloon, 2)
    # 70% × 6617.44 = 4632.21
    assert abs(result['ww_benefit_gross_month'] - 0.70 * max_maandloon) < 1


# ============================================================
# Test 12: Garantiedagloon
# ============================================================
def test_12_garantiedagloon():
    result = bereken_ww_uitkering(
        peildatum=date(2026, 5, 1),
        first_unemployment_day=date(2026, 1, 15),
        sv_loon_12m_total=SV_LOON,  # dagloon ~193
        use_guarantee_day_wage=True,
        guarantee_day_wage_override=250.0,  # hoger dan regulier
        employment_years_total_relevant=15,
        employment_years_pre2016_above10=1,
        employment_years_from2016_above10=4,
    )
    garantie_maandloon = 250.0 * 21.75  # 5437.50

    print(f"\nTest 12: Garantiedagloon")
    print(f"  WW-maandloon: {result['ww_month_wage']} (garantie: {garantie_maandloon:,.2f})")

    assert result['ww_month_wage'] == round(garantie_maandloon, 2)
    assert 'guarantee_day_wage_manual_override_used' in result['manual_review_flags']


# ============================================================
# Test 13: Fictief inkomen (zelfstandige uren)
# ============================================================
def test_13_fictief_inkomen():
    result = bereken_ww_uitkering(
        peildatum=date(2026, 5, 1),
        first_unemployment_day=date(2026, 1, 15),
        sv_loon_12m_total=SV_LOON,
        employment_years_total_relevant=15,
        employment_years_pre2016_above10=1,
        employment_years_from2016_above10=4,
        self_employed_hours_month=20,
    )
    dagloon = min(SV_LOON / 261, 304.25)
    hourly = dagloon / 8  # 24.14
    fictief = hourly * 20  # 482.76

    print(f"\nTest 13: Fictief inkomen")
    print(f"  Status: {result['ww_status']}")
    print(f"  Counted income: {result.get('counted_income_for_offset', 0)}")
    print(f"  Verwacht fictief: {fictief:,.2f}")

    assert 'fictitious_income_used' in result['manual_review_flags']
    assert abs(result['counted_income_for_offset'] - fictief) < 1


# ============================================================
# Test 14: Helper bereken_ww_bruto_jaar
# ============================================================
def test_14_helper_bruto_jaar():
    result = bereken_ww_bruto_jaar(
        sv_loon_jaar=SV_LOON,
        employment_years_total_relevant=15,
        employment_years_pre2016_above10=1,
        employment_years_from2016_above10=4,
        ww_maand_nummer=4,
    )
    print(f"\nTest 14: Helper bruto jaar")
    print(f"  Status: {result['ww_status']}")
    print(f"  WW/mnd: {result['ww_benefit_gross_month']}")
    print(f"  WW/jaar: {result['ww_benefit_gross_year']}")
    print(f"  Duur: {result['ww_duration_months']} mnd")

    assert result['ww_status'] in ('ww_lopend', 'ww_aanvullend')
    # 70% × ~4200 = ~2940/mnd → ~35280/jaar
    assert abs(result['ww_benefit_gross_month'] - 0.70 * EXPECTED_MAANDLOON) < 1
    assert abs(result['ww_benefit_gross_year'] - 0.70 * EXPECTED_MAANDLOON * 12) < 10
    assert result['ww_duration_months'] == 13


# ============================================================
# Test 15: Gedeeltelijke werkloosheid
# ============================================================
def test_15_gedeeltelijke_werkloosheid():
    # 40 uur → 16 uur verloren, 24 uur resterend
    result = bereken_ww_uitkering(
        peildatum=date(2026, 5, 1),
        first_unemployment_day=date(2026, 1, 15),
        sv_loon_12m_total=SV_LOON,
        avg_hours_per_week_before_unemployment=40,
        hours_lost_per_week=16,
        hours_remaining_per_week=24,
        employment_years_total_relevant=15,
        employment_years_pre2016_above10=1,
        employment_years_from2016_above10=4,
        earnings_from_employment_month=2520,  # 24/40 × 4200
    )
    print(f"\nTest 15: Gedeeltelijke werkloosheid")
    print(f"  Status: {result['ww_status']}")
    print(f"  WW-uitkering: {result['ww_benefit_gross_month']}")
    print(f"  Loon: {result['employment_income_gross_month']}")
    print(f"  Totaal: {result['total_gross_month']}")

    assert result['ww_eligible'] is True
    assert result['ww_status'] == 'ww_aanvullend'
    # WW basis = 70% × 4200 ≈ 2940
    # Verrekening = 70% × 2520 = 1764
    # WW na verrekening = 2940 - 1764 = 1176
    ww_basis = 0.70 * EXPECTED_MAANDLOON
    verwacht_ww = ww_basis - 0.70 * 2520
    assert abs(result['ww_benefit_gross_month'] - verwacht_ww) < 1


if __name__ == '__main__':
    test_1_volledig_werkloos_maand_1()
    test_2_volledig_werkloos_maand_4()
    test_3_geen_recht_wekeneis()
    test_4_buitenlands()
    test_5_onvoldoende_urenverlies_hoog()
    test_6_onvoldoende_urenverlies_laag()
    test_7_ww_duur()
    test_8_werken_naast_ww()
    test_9_stopregel_werk()
    test_10_duur_verstreken()
    test_11_maximum_dagloon()
    test_12_garantiedagloon()
    test_13_fictief_inkomen()
    test_14_helper_bruto_jaar()
    test_15_gedeeltelijke_werkloosheid()
    print("\n" + "=" * 50)
    print("Alle WW-calculator tests geslaagd!")
