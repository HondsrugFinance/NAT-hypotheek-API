"""
Test overlijdensscenario's met Harry Slinger data.

Harry Slinger (geb. 1980-04-01), inkomen 80.000
Harriette Slinger-Aap (geb. 1985-06-15), inkomen 40.000
Geadviseerd hypotheekbedrag: 338.173

Pensioenregeling Harry (als Harry overlijdt):
  Partnerpensioen voor Harriette: 18.000/jaar (voor AOW), 15.000 (na AOW)
  Wezenpensioen: 2.000/jaar

Pensioenregeling Harriette (als Harriette overlijdt):
  Partnerpensioen voor Harry: 7.500/jaar (voor AOW), 7.500 (na AOW)
  Wezenpensioen: 1.000/jaar

Kind: ja, jongste kind geb. 2018-03-20 (onder 18 => ANW-recht)

Hypotheekdelen op startdatum (origineel, geen projectie):
- Aflossingsvrij: 145.000, 5% rente, box1
- Annuiteit: 120.000, 5% rente, 360 maanden, box1
- Lineair: 85.000, 3% rente, 300 maanden, box1
"""

from risk_scenarios import bereken_overlijdens_scenarios


def test_overlijdens_scenarios_harry_slinger():
    """Test met Harry Slinger stel."""

    hypotheek_delen = [
        {
            "aflos_type": "Aflosvrij",
            "org_lpt": 360,
            "rest_lpt": 360,
            "hoofdsom_box1": 145000,
            "hoofdsom_box3": 0,
            "rvp": 120,
            "inleg_overig": 0,
            "werkelijke_rente": 0.05,
        },
        {
            "aflos_type": "Annuiteit",
            "org_lpt": 360,
            "rest_lpt": 360,
            "hoofdsom_box1": 120000,
            "hoofdsom_box3": 0,
            "rvp": 120,
            "inleg_overig": 0,
            "werkelijke_rente": 0.05,
        },
        {
            "aflos_type": "Lineair",
            "org_lpt": 300,
            "rest_lpt": 300,
            "hoofdsom_box1": 85000,
            "hoofdsom_box3": 0,
            "rvp": 120,
            "inleg_overig": 0,
            "werkelijke_rente": 0.03,
        },
    ]

    result = bereken_overlijdens_scenarios(
        hypotheek_delen=hypotheek_delen,
        geboortedatum_aanvrager="1980-04-01",
        inkomen_aanvrager_huidig=80000,
        geboortedatum_partner="1985-06-15",
        inkomen_partner_huidig=40000,
        nabestaandenpensioen_bij_overlijden_aanvrager=18000,  # Harry overlijdt
        nabestaandenpensioen_bij_overlijden_partner=7500,     # Harriette overlijdt
        heeft_kind_onder_18=True,
        geboortedatum_jongste_kind="2018-03-20",
        toetsrente=0.04664,
        geadviseerd_hypotheekbedrag=338173,
    )

    scenarios = result['scenarios']
    assert len(scenarios) == 2

    # --- Scenario 1: Harry overlijdt, Harriette is nabestaande ---
    s1 = scenarios[0]
    print("\n=== Scenario 1: Overlijden aanvrager (Harry overlijdt) ===")
    print(f"  Nabestaande: Harriette")
    print(f"  Eigen inkomen: {s1['anw_details']['eigen_inkomen_jaar']}")
    print(f"  Nabestaandenpensioen: {s1['anw_details']['nabestaandenpensioen_jaar']}")
    print(f"  ANW eligible: {s1['anw_details']['anw_eligible']} ({s1['anw_details']['anw_reason']})")
    print(f"  ANW bruto/jaar: {s1['anw_details']['anw_bruto_jaar']}")
    print(f"  ANW einddatum: {s1['anw_details']['anw_einddatum']}")
    print(f"  Totaal inkomen: {s1['anw_details']['totaal_inkomen_jaar']}")
    print(f"  Max hypotheek (annuitair): {s1['max_hypotheek_annuitair']:,.2f}")
    print(f"  Tekort: {s1['tekort']:,.2f}")
    print(f"  Percentage: {s1['percentage_van_geadviseerd']}%")

    assert s1['categorie'] == 'overlijden'
    assert s1['van_toepassing_op'] == 'aanvrager'

    # Harriette eigen inkomen 40.000
    assert s1['anw_details']['eigen_inkomen_jaar'] == 40000
    # Nabestaandenpensioen: 18.000
    assert s1['anw_details']['nabestaandenpensioen_jaar'] == 18000
    # ANW: Harriette heeft kind onder 18 => recht op ANW
    assert s1['anw_details']['anw_eligible'] is True

    # ANW met korting: Harriette verdient 40.000/12 = 3.333,33/mnd
    # Dat is < nihilgrens 3.617,28 maar > vrijlating 1.147,20
    # Excess: 3333.33 - 1147.20 = 2186.13
    # Korting: 2186.13 * 2/3 = 1457.42
    # ANW basis: 1796.67 (incl vakantiegeld)
    # ANW na korting: 1796.67 - 1457.42 = 339.25/mnd = 4071.00/jaar (afgerond)
    # Nabestaandenpensioen kort ANW NIET
    print(f"  ANW berekening: basis 1796.67 - korting (inkomen {40000/12:.2f}/mnd)")
    assert s1['anw_details']['anw_bruto_jaar'] > 0

    # Totaal: 40.000 + 18.000 + ANW
    expected_total = 40000 + 18000 + s1['anw_details']['anw_bruto_jaar']
    assert abs(s1['anw_details']['totaal_inkomen_jaar'] - expected_total) < 1

    # Max hypotheek > 0 (er is inkomen)
    assert s1['max_hypotheek_annuitair'] > 0
    # Maar er is een tekort (minder dan 338.173)
    assert s1['tekort'] > 0
    print(f"  [OK] Scenario 1 correct")

    # --- Scenario 2: Harriette overlijdt, Harry is nabestaande ---
    s2 = scenarios[1]
    print(f"\n=== Scenario 2: Overlijden partner (Harriette overlijdt) ===")
    print(f"  Nabestaande: Harry")
    print(f"  Eigen inkomen: {s2['anw_details']['eigen_inkomen_jaar']}")
    print(f"  Nabestaandenpensioen: {s2['anw_details']['nabestaandenpensioen_jaar']}")
    print(f"  ANW eligible: {s2['anw_details']['anw_eligible']} ({s2['anw_details']['anw_reason']})")
    print(f"  ANW bruto/jaar: {s2['anw_details']['anw_bruto_jaar']}")
    print(f"  ANW einddatum: {s2['anw_details']['anw_einddatum']}")
    print(f"  Totaal inkomen: {s2['anw_details']['totaal_inkomen_jaar']}")
    print(f"  Max hypotheek (annuitair): {s2['max_hypotheek_annuitair']:,.2f}")
    print(f"  Tekort: {s2['tekort']:,.2f}")
    print(f"  Percentage: {s2['percentage_van_geadviseerd']}%")

    assert s2['categorie'] == 'overlijden'
    assert s2['van_toepassing_op'] == 'partner'

    # Harry eigen inkomen 80.000
    assert s2['anw_details']['eigen_inkomen_jaar'] == 80000
    # Nabestaandenpensioen: 7.500
    assert s2['anw_details']['nabestaandenpensioen_jaar'] == 7500
    # ANW: Harry heeft kind onder 18 => recht op ANW
    assert s2['anw_details']['anw_eligible'] is True

    # ANW met korting: Harry verdient 80.000/12 = 6.666,67/mnd
    # Dat is BOVEN nihilgrens 3.617,28 => ANW = 0
    assert s2['anw_details']['anw_bruto_jaar'] == 0
    print(f"  [OK] ANW = 0 (inkomen {80000/12:.2f}/mnd > nihilgrens 3617.28)")

    # Totaal: 80.000 + 7.500 + 0 (ANW) = 87.500
    assert s2['anw_details']['totaal_inkomen_jaar'] == 87500

    # Harry met 87.500 als alleenstaande: moet nog steeds veel kunnen lenen
    assert s2['max_hypotheek_annuitair'] > 200000
    print(f"  [OK] Scenario 2 correct")

    # Harry heeft hoger inkomen, dus tekort bij overlijden partner is kleiner
    assert s2['tekort'] < s1['tekort']
    print(f"\n[OK] Tekort scenario 1 ({s1['tekort']:,.2f}) > tekort scenario 2 ({s2['tekort']:,.2f})")

    print("\n" + "=" * 60)
    print("Alle overlijdensscenario tests geslaagd!")


if __name__ == '__main__':
    test_overlijdens_scenarios_harry_slinger()
