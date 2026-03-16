"""
Test AO-scenario's met Harry Slinger data.

Harry Slinger (geb. 1980-04-01), loondienst 80.000
Harriette Slinger-Aap (geb. 1985-06-15), loondienst 40.000
Geadviseerd hypotheekbedrag: 338.173

Loondoorbetaling Harry: jaar1=100%, jaar2=70%
Loondoorbetaling Harriette: jaar1=100%, jaar2=70% (standaard)

AO: 50%, benutting RVC: 50%

Hypotheek: ingangsdatum 2026-03-01
- Aflossingsvrij: 145.000, 5%, box1
- Annuiteit: 120.000, 5%, 360 mnd, box1
- Lineair: 85.000, 3%, 300 mnd, box1

Per persoon 3 fasen:
1. Loondoorbetaling (jaar 2)
2. WGA loongerelateerd
3. WGA loonaanvulling
"""

from risk_scenarios import bereken_ao_scenarios


def test_ao_scenarios_harry_slinger():
    """Test AO-scenario's voor Harry Slinger stel."""

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

    result = bereken_ao_scenarios(
        hypotheek_delen=hypotheek_delen,
        ingangsdatum_hypotheek="2026-03-01",
        geboortedatum_aanvrager="1980-04-01",
        alleenstaande="NEE",
        geboortedatum_partner="1985-06-15",
        # Inkomensverdeling
        inkomen_loondienst_aanvrager=80000,
        inkomen_loondienst_partner=40000,
        # AO
        ao_percentage=50,
        benutting_rvc_percentage=50,
        # Loondoorbetaling
        loondoorbetaling_pct_jaar2_aanvrager=0.70,
        loondoorbetaling_pct_jaar2_partner=0.70,
        # Toetsrente
        toetsrente=0.04664,
        geadviseerd_hypotheekbedrag=338173,
    )

    scenarios = result['scenarios']
    # 2 personen x 3 fasen = 6 scenario's
    assert len(scenarios) == 6

    # === AO aanvrager (Harry) — 3 fasen ===
    s_a_ldb = scenarios[0]
    s_a_lgu = scenarios[1]
    s_a_la = scenarios[2]

    print("\n=== AO aanvrager (Harry wordt AO) ===")

    # Fase 1: Loondoorbetaling jaar 2
    print(f"\n  Fase 1: {s_a_ldb['naam']}")
    print(f"    Loondienst: {s_a_ldb['ao_details']['loondienst_component']}")
    print(f"    Totaal getroffen: {s_a_ldb['ao_details']['totaal_getroffen_persoon']}")
    print(f"    Inkomen aanvrager: {s_a_ldb['inkomen_aanvrager']}")
    print(f"    Inkomen partner: {s_a_ldb['inkomen_partner']}")
    print(f"    Max hypotheek: {s_a_ldb['max_hypotheek_annuitair']:,.2f}")
    print(f"    Tekort: {s_a_ldb['tekort']:,.2f}")

    assert s_a_ldb['ao_details']['fase'] == 'loondoorbetaling'
    # 70% x 80k = 56k
    assert s_a_ldb['ao_details']['loondienst_component'] == 56000
    assert s_a_ldb['ao_details']['totaal_getroffen_persoon'] == 56000
    # Partner ongewijzigd: 40k
    assert s_a_ldb['inkomen_partner'] == 40000
    print(f"    [OK] Loondoorbetaling: 70% x 80k = 56k")

    # Fase 2: WGA LGU
    print(f"\n  Fase 2: {s_a_lgu['naam']}")
    print(f"    WIA status: {s_a_lgu['ao_details']['wia_status']}")
    print(f"    WIA uitkering/jaar: {s_a_lgu['ao_details']['wia_uitkering_jaar']}")
    print(f"    Loon uit arbeid/jaar: {s_a_lgu['ao_details']['loon_uit_arbeid_jaar']}")
    print(f"    Totaal getroffen: {s_a_lgu['ao_details']['totaal_getroffen_persoon']}")
    print(f"    Max hypotheek: {s_a_lgu['max_hypotheek_annuitair']:,.2f}")
    print(f"    Tekort: {s_a_lgu['tekort']:,.2f}")

    assert s_a_lgu['ao_details']['fase'] == 'wga_loongerelateerd'
    assert s_a_lgu['ao_details']['wia_uitkering_jaar'] > 0
    # RVC = 80k/12 * 50% = 3333.33, actual = 3333.33 * 50% = 1666.67/mnd = 20k/jr
    assert abs(s_a_lgu['ao_details']['loon_uit_arbeid_jaar'] - 20000) < 1
    print(f"    [OK] WGA LGU met inkomsten")

    # Fase 3: WGA loonaanvulling
    print(f"\n  Fase 3: {s_a_la['naam']}")
    print(f"    WIA status: {s_a_la['ao_details']['wia_status']}")
    print(f"    WIA uitkering/jaar: {s_a_la['ao_details']['wia_uitkering_jaar']}")
    print(f"    Loon uit arbeid/jaar: {s_a_la['ao_details']['loon_uit_arbeid_jaar']}")
    print(f"    Totaal getroffen: {s_a_la['ao_details']['totaal_getroffen_persoon']}")
    print(f"    Max hypotheek: {s_a_la['max_hypotheek_annuitair']:,.2f}")
    print(f"    Tekort: {s_a_la['tekort']:,.2f}")

    assert s_a_la['ao_details']['wia_status'] == 'wga_loonaanvulling'
    # Lookaanvulling v2: 70% x (maandloon - rvc) = 70% x (6666.67 - 3333.33) = 2333.33/mnd
    # = 28000/jaar
    assert abs(s_a_la['ao_details']['wia_uitkering_jaar'] - 28000) < 5
    # Actual wage: 20k/jaar
    assert abs(s_a_la['ao_details']['loon_uit_arbeid_jaar'] - 20000) < 1
    # Totaal: 28k + 20k = 48k
    assert abs(s_a_la['ao_details']['totaal_getroffen_persoon'] - 48000) < 5
    print(f"    [OK] WGA loonaanvulling: UWV 28k + loon 20k = 48k")

    # Inkomen daalt per fase: LDB > LGU > LA (of LGU hoger door onvolledige verrekening)
    # Loonaanvulling is de structurele situatie
    print(f"\n  Inkomen per fase: LDB={s_a_ldb['ao_details']['totaal_getroffen_persoon']}"
          f" → LGU={s_a_lgu['ao_details']['totaal_getroffen_persoon']}"
          f" → LA={s_a_la['ao_details']['totaal_getroffen_persoon']}")

    # === AO partner (Harriette) — 3 fasen ===
    s_p_ldb = scenarios[3]
    s_p_lgu = scenarios[4]
    s_p_la = scenarios[5]

    print(f"\n=== AO partner (Harriette wordt AO) ===")

    # Fase 1: Loondoorbetaling
    print(f"\n  Fase 1: {s_p_ldb['naam']}")
    print(f"    Loondienst: {s_p_ldb['ao_details']['loondienst_component']}")
    print(f"    Max hypotheek: {s_p_ldb['max_hypotheek_annuitair']:,.2f}")
    print(f"    Tekort: {s_p_ldb['tekort']:,.2f}")

    # 70% x 40k = 28k
    assert s_p_ldb['ao_details']['loondienst_component'] == 28000
    # Aanvrager ongewijzigd: 80k
    assert s_p_ldb['inkomen_aanvrager'] == 80000
    print(f"    [OK] Loondoorbetaling partner: 70% x 40k = 28k")

    # Fase 3: WGA loonaanvulling
    print(f"\n  Fase 3: {s_p_la['naam']}")
    print(f"    WIA uitkering/jaar: {s_p_la['ao_details']['wia_uitkering_jaar']}")
    print(f"    Totaal getroffen: {s_p_la['ao_details']['totaal_getroffen_persoon']}")
    print(f"    Max hypotheek: {s_p_la['max_hypotheek_annuitair']:,.2f}")
    print(f"    Tekort: {s_p_la['tekort']:,.2f}")

    assert s_p_la['ao_details']['wia_status'] == 'wga_loonaanvulling'
    # Harriette: maandloon 40k/12=3333.33, rvc=1666.67, actual=833.33
    # LA v2: 70% x (3333.33 - 1666.67) = 1166.67/mnd = 14000/jr
    assert abs(s_p_la['ao_details']['wia_uitkering_jaar'] - 14000) < 5
    print(f"    [OK] WGA loonaanvulling partner")

    # AO aanvrager heeft meer impact (hogere verdiener), dus lagere max hypotheek
    assert s_a_la['max_hypotheek_annuitair'] < s_p_la['max_hypotheek_annuitair']
    print(f"\n  [OK] Max hyp AO aanvrager ({s_a_la['max_hypotheek_annuitair']:,.0f}) < "
          f"max hyp AO partner ({s_p_la['max_hypotheek_annuitair']:,.0f})")

    # Alleenstaande wijzigt NIET bij AO
    for s in scenarios:
        assert s.get('inkomen_partner', 0) >= 0  # partner leeft nog

    print("\n" + "=" * 60)
    print("Alle AO-scenario tests geslaagd!")


if __name__ == '__main__':
    test_ao_scenarios_harry_slinger()
