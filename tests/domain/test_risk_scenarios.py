"""
Test risk_scenarios.py — AOW scenario's met Harry Slinger data.

Harry Slinger (geb. ~1980, AOW 01-04-2047):
  Huidig inkomen: E80.000
  Inkomen vanaf AOW: E34.342 (AOW E14.342 + pensioen E20.000)

Harriette Slinger-Aap (geb. ~1985, AOW 01-04-2052):
  Huidig inkomen: E40.000
  Inkomen vanaf AOW: E23.342 (AOW E14.342 + pensioen E9.000)

Hypotheek per 01-01-2026:
  Deel 1: E145.000 Aflossingsvrij, 4%, 240m, aftrekbaar tot 2046-01-01
  Deel 2: E120.000 Annuiteit, 5%, 360m, aftrekbaar tot 2056-01-01
  Deel 3: E85.000 Lineair, 3%, 300m, aftrekbaar tot 2051-01-01

Geadviseerd hypotheekbedrag: E350.000
Oorspronkelijke toetsrente: 4,664% (0.04664)
"""

from risk_scenarios import bereken_aow_scenarios


HARRY_SLINGER_DELEN = [
    {
        'aflos_type': 'Aflosvrij',
        'org_lpt': 240,
        'rest_lpt': 240,
        'hoofdsom_box1': 145000,
        'hoofdsom_box3': 0,
        'rvp': 120,
        'werkelijke_rente': 0.04,
        'inleg_overig': 0,
        'rente_aftrekbaar_tot': '2046-01-01',
    },
    {
        'aflos_type': 'Annuïteit',
        'org_lpt': 360,
        'rest_lpt': 360,
        'hoofdsom_box1': 120000,
        'hoofdsom_box3': 0,
        'rvp': 240,
        'werkelijke_rente': 0.05,
        'inleg_overig': 0,
        'rente_aftrekbaar_tot': '2056-01-01',
    },
    {
        'aflos_type': 'Lineair',
        'org_lpt': 300,
        'rest_lpt': 300,
        'hoofdsom_box1': 85000,
        'hoofdsom_box3': 0,
        'rvp': 60,
        'werkelijke_rente': 0.03,
        'inleg_overig': 0,
        'rente_aftrekbaar_tot': '2051-01-01',
    },
]


def test_aow_scenarios():
    """Test AOW scenario's voor Harry Slinger stel."""
    result = bereken_aow_scenarios(
        hypotheek_delen=HARRY_SLINGER_DELEN,
        ingangsdatum_hypotheek="2026-01-01",
        # Harry: geboren ~1980, AOW op 01-04-2047 (67j+3m)
        # Terugrekenen: 2047-04-01 minus 67j3m = 1980-01-01
        geboortedatum_aanvrager="1980-01-01",
        inkomen_aanvrager_huidig=80000,
        inkomen_aanvrager_aow=34342,
        alleenstaande="NEE",
        # Harriette: geboren ~1985, AOW op 01-04-2052 (67j+3m)
        # 2052-04-01 minus 67j3m = 1985-01-01
        geboortedatum_partner="1985-01-01",
        inkomen_partner_huidig=40000,
        inkomen_partner_aow=23342,
        toetsrente=0.04664,
        energielabel="Geen (geldig) Label",
        geadviseerd_hypotheekbedrag=350000,
    )

    scenarios = result['scenarios']
    print(f"Aantal scenario's: {len(scenarios)}")
    print()

    for s in scenarios:
        print(f"--- {s['naam']} ---")
        print(f"  Peildatum: {s['peildatum']}")
        print(f"  Inkomen aanvrager: E{s['inkomen_aanvrager']:,.0f}")
        print(f"  Inkomen partner: E{s['inkomen_partner']:,.0f}")
        print(f"  Ontvangt AOW: {s['ontvangt_aow']}")
        print(f"  Toetsinkomen: E{s['toets_inkomen']:,.0f}")
        print(f"  Toetsrente: {s['toets_rente']*100:.3f}%")
        print(f"  Woonquote: {s['woonquote']*100:.1f}%")
        print(f"  Max hypotheek (annuitair): E{s['max_hypotheek_annuitair']:,.0f}")
        print(f"  Max hypotheek (niet-annuitair): E{s['max_hypotheek_niet_annuitair']:,.0f}")
        print(f"  Tekort t.o.v. E{result['geadviseerd_hypotheekbedrag']:,.0f}: E{s['tekort']:,.0f}")
        print(f"  Percentage: {s['percentage_van_geadviseerd']}%")
        print()
        print(f"  Geprojecteerde hypotheekdelen:")
        for j, d in enumerate(s['hypotheek_delen_geprojecteerd']):
            total = d['hoofdsom_box1'] + d['hoofdsom_box3']
            box = "box1" if d['hoofdsom_box1'] > 0 else "box3"
            print(f"    Deel {j+1}: {d['aflos_type']} E{total:,.0f} ({box}), rest_lpt={d['rest_lpt']}")
        print()

    # Validaties
    assert len(scenarios) == 2, "Verwacht 2 AOW scenario's (aanvrager + partner)"

    # Scenario 1: AOW aanvrager (01-04-2047)
    s1 = scenarios[0]
    assert s1['categorie'] == 'aow'
    assert s1['van_toepassing_op'] == 'aanvrager'
    assert s1['peildatum'] == '2047-04-01'
    assert s1['inkomen_aanvrager'] == 34342
    assert s1['inkomen_partner'] == 40000  # partner werkt nog
    assert s1['ontvangt_aow'] == 'NEE'  # hoogste verdiener (partner E40k) is NIET AOW
    assert s1['max_hypotheek_annuitair'] > 0
    print(f"[OK] Scenario 1: AOW aanvrager, ontvangt_aow=NEE (partner verdient meer)")

    # Scenario 2: AOW partner (01-04-2052)
    s2 = scenarios[1]
    assert s2['categorie'] == 'aow'
    assert s2['van_toepassing_op'] == 'partner'
    assert s2['peildatum'] == '2052-04-01'
    assert s2['inkomen_aanvrager'] == 34342  # aanvrager ook al AOW
    assert s2['inkomen_partner'] == 23342
    assert s2['ontvangt_aow'] == 'JA'  # beide AOW, hoogste (E34k) is AOW
    assert s2['max_hypotheek_annuitair'] > 0
    print(f"[OK] Scenario 2: AOW partner, ontvangt_aow=JA (beide AOW)")

    # Tekort moet er zijn (AOW-inkomen << huidig)
    assert s1['tekort'] > 0, "Verwacht tekort bij AOW aanvrager"
    assert s2['tekort'] > 0, "Verwacht tekort bij AOW partner"
    print(f"[OK] Tekorten: AOW aanvrager E{s1['tekort']:,.0f}, AOW partner E{s2['tekort']:,.0f}")


def test_alleenstaande():
    """Alleenstaande: alleen AOW aanvrager scenario."""
    result = bereken_aow_scenarios(
        hypotheek_delen=HARRY_SLINGER_DELEN,
        ingangsdatum_hypotheek="2026-01-01",
        geboortedatum_aanvrager="1980-01-01",
        inkomen_aanvrager_huidig=80000,
        inkomen_aanvrager_aow=34342,
        alleenstaande="JA",
        toetsrente=0.04664,
        geadviseerd_hypotheekbedrag=350000,
    )

    assert len(result['scenarios']) == 1
    s = result['scenarios'][0]
    assert s['van_toepassing_op'] == 'aanvrager'
    assert s['ontvangt_aow'] == 'JA'  # alleenstaande en AOW
    print(f"[OK] Alleenstaande: 1 scenario, ontvangt_aow=JA")
    print(f"  Max hypotheek: E{s['max_hypotheek_annuitair']:,.0f}")


if __name__ == '__main__':
    test_aow_scenarios()
    print()
    print("=" * 60)
    test_alleenstaande()
