"""
Test werkloosheidsscenario's met Harry Slinger data.

Harry Slinger (geb. 1980-04-01), loondienst 80.000
Harriette Slinger-Aap (geb. 1985-06-15), loondienst 40.000
Geadviseerd hypotheekbedrag: 338.173

Arbeidsverleden Harry: 15 jaar totaal, 1 pre-2016 boven 10, 4 vanaf 2016 boven 10
  → WW-duur = 10 + 1 + 4×0.5 = 13 maanden → 2 WW-jaren

Arbeidsverleden Harriette: 8 jaar totaal, 0 boven 10
  → WW-duur = min(8, 10) = 8 maanden → 1 WW-jaar

Harry WW-uitkering:
  dagloon = 80000/261 = 306.51 → afgetopt op max 304.25
  maandloon = 304.25 × 21.75 = 6617.44
  WW = 70% × 6617.44 = 4632.21/mnd = 55586.48/jaar

Harriette WW-uitkering:
  dagloon = 40000/261 = 153.26 (onder max)
  maandloon = 153.26 × 21.75 = 3333.33
  WW = 70% × 3333.33 = 2333.33/mnd = 27999.99/jaar

Hypotheek: ingangsdatum 2026-03-01
- Aflossingsvrij: 145.000, 5%, box1
- Annuiteit: 120.000, 5%, 360 mnd, box1
- Lineair: 85.000, 3%, 300 mnd, box1
"""

from risk_scenarios import bereken_werkloosheid_scenarios


def test_werkloosheid_scenarios_harry_slinger():
    """Test werkloosheidsscenario's voor Harry Slinger stel."""

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

    result = bereken_werkloosheid_scenarios(
        hypotheek_delen=hypotheek_delen,
        ingangsdatum_hypotheek="2026-03-01",
        geboortedatum_aanvrager="1980-04-01",
        alleenstaande="NEE",
        geboortedatum_partner="1985-06-15",
        # Inkomen
        inkomen_loondienst_aanvrager=80000,
        inkomen_loondienst_partner=40000,
        # Arbeidsverleden Harry: 15 jaar, 1 pre-2016 boven 10, 4 vanaf 2016 boven 10
        arbeidsverleden_jaren_totaal_aanvrager=15,
        arbeidsverleden_pre2016_boven10_aanvrager=1,
        arbeidsverleden_vanaf2016_boven10_aanvrager=4,
        # Arbeidsverleden Harriette: 8 jaar
        arbeidsverleden_jaren_totaal_partner=8,
        arbeidsverleden_pre2016_boven10_partner=0,
        arbeidsverleden_vanaf2016_boven10_partner=0,
        # Toetsrente
        toetsrente=0.04664,
        geadviseerd_hypotheekbedrag=338173,
    )

    scenarios = result['scenarios']

    print("\n=== Werkloosheidsscenario's Harry Slinger ===")
    for s in scenarios:
        print(f"\n  {s['naam']}")
        print(f"    Inkomen aanvrager: {s['inkomen_aanvrager']:,.2f}")
        print(f"    Inkomen partner: {s['inkomen_partner']:,.2f}")
        print(f"    Max hypotheek: {s['max_hypotheek_annuitair']:,.2f}")
        print(f"    Tekort: {s['tekort']:,.2f}")
        if 'ww_details' in s:
            d = s['ww_details']
            print(f"    WW details: {d}")

    # Harry: 13 mnd WW → 2 jaren → 2 WW-scenario's + 1 na-WW = 3
    # Harriette: 8 mnd WW → 1 jaar → 1 WW-scenario + 1 na-WW = 2
    # Totaal: 5 scenario's
    assert len(scenarios) == 5, f"Verwacht 5 scenario's, kreeg {len(scenarios)}"

    # === Harry's scenario's ===
    s_h_ww1 = scenarios[0]
    s_h_ww2 = scenarios[1]
    s_h_na = scenarios[2]

    # Harry WW jaar 1
    assert s_h_ww1['ww_details']['ww_duur_maanden'] == 13
    assert s_h_ww1['ww_details']['ww_jaar'] == 1
    # Harry WW: dagloon afgetopt op 304.25 → maandloon 6617.44 → 70% = 4632.21/mnd
    max_dagloon_maandloon = 304.25 * 21.75
    verwacht_ww_harry = 0.70 * max_dagloon_maandloon * 12  # 55586.48/jaar
    assert abs(s_h_ww1['ww_details']['ww_uitkering_jaar'] - verwacht_ww_harry) < 5
    print(f"\n  [OK] Harry WW jaar 1: {s_h_ww1['ww_details']['ww_uitkering_jaar']:,.2f}/jaar "
          f"(afgetopt dagloon)")

    # Harry WW jaar 2
    assert s_h_ww2['ww_details']['ww_jaar'] == 2

    # Harry na WW: alleen onderneming+roz+overig = 0 (alleen loondienst)
    assert s_h_na['ww_details']['fase'] == 'na_ww'
    assert s_h_na['ww_details']['totaal_getroffen_persoon'] == 0
    print(f"  [OK] Harry na WW: inkomen getroffen = 0 (alleen loondienst)")

    # === Harriette's scenario's ===
    s_p_ww = scenarios[3]
    s_p_na = scenarios[4]

    # Harriette WW: 8 maanden duur → 1 jaar
    assert s_p_ww['ww_details']['ww_duur_maanden'] == 8
    # Harriette: dagloon = 40000/261 = 153.26 → maandloon = 3333.33
    verwacht_maandloon = round(40000 / 261 * 21.75, 2)
    verwacht_ww_harriette = 0.70 * verwacht_maandloon * 12
    assert abs(s_p_ww['ww_details']['ww_uitkering_jaar'] - verwacht_ww_harriette) < 5
    print(f"  [OK] Harriette WW: {s_p_ww['ww_details']['ww_uitkering_jaar']:,.2f}/jaar")

    # Harriette na WW
    assert s_p_na['ww_details']['fase'] == 'na_ww'

    # Werkloosheid aanvrager heeft meer impact dan partner
    assert s_h_ww1['max_hypotheek_annuitair'] < s_p_ww['max_hypotheek_annuitair']
    print(f"\n  [OK] Max hyp WW Harry ({s_h_ww1['max_hypotheek_annuitair']:,.0f}) < "
          f"WW Harriette ({s_p_ww['max_hypotheek_annuitair']:,.0f})")

    # Na-WW is erger dan WW (want geen uitkering meer)
    assert s_h_na['max_hypotheek_annuitair'] < s_h_ww1['max_hypotheek_annuitair']
    print(f"  [OK] Max hyp Na-WW Harry ({s_h_na['max_hypotheek_annuitair']:,.0f}) < "
          f"WW Harry ({s_h_ww1['max_hypotheek_annuitair']:,.0f})")

    print("\n" + "=" * 60)
    print("Alle werkloosheid-scenario tests geslaagd!")


if __name__ == '__main__':
    test_werkloosheid_scenarios_harry_slinger()
