"""
Test loan_projection.py tegen Harry Slinger voorbeeld.

Hypotheek per 01-01-2026:
  Deel 1: E145.000 Aflossingsvrij, 4%, 240m, rente aftrekbaar tot 01-01-2046
  Deel 2: E120.000 Annuiteit, 5%, 360m, rente aftrekbaar tot 01-01-2056
  Deel 3: E85.000 Lineair, 3%, 300m, rente aftrekbaar tot 01-01-2051

Per 01-04-2047 (255 maanden, AOW aanvrager):
  Deel 1: E145.000 Aflossingsvrij, rest_lpt=240 (org), BOX3 (aftrekbaar verlopen)
  Deel 2: E54.693,95 Annuiteit, rest_lpt=105, box1
  Deel 3: E12.750 Lineair, rest_lpt=45, box1

Per 01-04-2052 (318 maanden, AOW partner):
  Deel 1: E145.000 Aflossingsvrij, rest_lpt=240 (org), box3
  Deel 2: E19.171 Annuiteit, rest_lpt=42, box1
  Deel 3: afgelost (300m looptijd verlopen)
"""

from datetime import date
from loan_projection import projecteer_hypotheekdelen, _annuitair_restant, _lineair_restant


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


def test_aow_aanvrager():
    """Per 01-04-2047: AOW-datum aanvrager, 255 maanden na 01-01-2026."""
    peildatum = date(2047, 4, 1)
    elapsed = 255  # (2047-2026)*12 + 3 = 255

    result = projecteer_hypotheekdelen(HARRY_SLINGER_DELEN, elapsed, peildatum)

    print("=== AOW aanvrager (01-04-2047, 255 maanden) ===")
    print()
    for i, d in enumerate(result):
        total = d['hoofdsom_box1'] + d['hoofdsom_box3']
        print(f"Deel {i+1}: {d['aflos_type']}")
        print(f"  Box1: E{d['hoofdsom_box1']:,.2f}  Box3: E{d['hoofdsom_box3']:,.2f}")
        print(f"  rest_lpt: {d['rest_lpt']}  org_lpt: {d['org_lpt']}")
        print()

    assert len(result) == 3

    # Deel 1: Aflossingsvrij — E145k, box3 (rente aftrekbaar tot 2046-01-01 verlopen)
    d1 = result[0]
    assert d1['hoofdsom_box1'] == 0, f"Deel 1 moet box3 zijn, maar box1={d1['hoofdsom_box1']}"
    assert d1['hoofdsom_box3'] == 145000
    assert d1['rest_lpt'] == 240  # org_lpt voor aflossingsvrij
    print("[OK] Deel 1: E145k box3 (aftrekbaar verlopen), rest_lpt=240")

    # Deel 2: Annuiteit — ~E54.694, nog steeds box1
    d2 = result[1]
    restant = d2['hoofdsom_box1'] + d2['hoofdsom_box3']
    assert d2['hoofdsom_box3'] == 0, "Deel 2 moet box1 zijn"
    assert abs(restant - 54693.95) < 5
    assert d2['rest_lpt'] == 105
    print(f"[OK] Deel 2: E{restant:,.2f} box1, rest_lpt=105")

    # Deel 3: Lineair — E12.750, nog steeds box1
    d3 = result[2]
    restant3 = d3['hoofdsom_box1'] + d3['hoofdsom_box3']
    assert d3['hoofdsom_box3'] == 0, "Deel 3 moet box1 zijn"
    assert abs(restant3 - 12750) < 1
    assert d3['rest_lpt'] == 45
    print(f"[OK] Deel 3: E{restant3:,.2f} box1, rest_lpt=45")


def test_aow_partner():
    """Per 01-04-2052: AOW-datum partner, 318 maanden na 01-01-2026."""
    peildatum = date(2052, 4, 1)
    elapsed = 318  # (2052-2026)*12 + 3 = 315... nee: 26*12+3=315

    # Correctie: 2052-2026 = 26 jaar, + 3 maanden = 26*12+3 = 315
    elapsed = (2052 - 2026) * 12 + 3  # = 315
    result = projecteer_hypotheekdelen(HARRY_SLINGER_DELEN, elapsed, peildatum)

    print()
    print("=== AOW partner (01-04-2052, 315 maanden) ===")
    print()
    for i, d in enumerate(result):
        total = d['hoofdsom_box1'] + d['hoofdsom_box3']
        print(f"Deel {i+1}: {d['aflos_type']}")
        print(f"  Box1: E{d['hoofdsom_box1']:,.2f}  Box3: E{d['hoofdsom_box3']:,.2f}")
        print(f"  rest_lpt: {d['rest_lpt']}  org_lpt: {d['org_lpt']}")
        print()

    # Deel 3 (lineair, 300m) is afgelost na 315 maanden -> uitgefilterd
    # Verwacht: 2 delen (aflossingsvrij + annuitair)
    assert len(result) == 2, f"Verwacht 2 delen (lineair afgelost), kreeg {len(result)}"

    # Deel 1: Aflossingsvrij — E145k, box3
    d1 = result[0]
    assert d1['hoofdsom_box1'] == 0
    assert d1['hoofdsom_box3'] == 145000
    assert d1['rest_lpt'] == 240
    print("[OK] Deel 1: E145k box3, rest_lpt=240")

    # Deel 2: Annuiteit — rest na 315 maanden, box1 (aftrekbaar tot 2056)
    d2 = result[1]
    restant = d2['hoofdsom_box1'] + d2['hoofdsom_box3']
    assert d2['hoofdsom_box3'] == 0, "Deel 2 moet box1 zijn (aftrekbaar tot 2056)"
    assert d2['rest_lpt'] == 360 - 315  # = 45
    print(f"[OK] Deel 2: E{restant:,.2f} box1, rest_lpt={d2['rest_lpt']}")

    # Deel 3 lineair: afgelost (300m < 315m)
    print("[OK] Deel 3: lineair afgelost (uitgefilterd)")


def test_lineair_exact():
    """Lineair is exact: 85000 / 300 * 255 = 72250 afgelost."""
    restant = _lineair_restant(85000, 300, 255)
    assert restant == 12750.0, f"Verwacht 12750.0, kreeg {restant}"
    print(f"[OK] Lineair exact: E{restant:,.2f}")


def test_annuitair_detail():
    """Toon annuitair resultaat in detail."""
    restant = _annuitair_restant(120000, 0.05, 360, 255)
    print(f"Annuitair restant na 255 maanden: E{restant:,.2f}")
    print(f"Verwacht: E54.693,95 | Verschil: E{abs(restant - 54693.95):.2f}")


def test_aflossingsvrij_rest_lpt_org():
    """Aflossingsvrij: rest_lpt = org_lpt (niet aflopend)."""
    delen = [{
        'aflos_type': 'Aflosvrij',
        'org_lpt': 240,
        'rest_lpt': 240,
        'hoofdsom_box1': 100000,
        'hoofdsom_box3': 0,
        'rvp': 60,
        'werkelijke_rente': 0.04,
        'inleg_overig': 0,
    }]
    result = projecteer_hypotheekdelen(delen, 180)
    assert result[0]['rest_lpt'] == 240  # org_lpt
    assert result[0]['hoofdsom_box1'] == 100000
    print("[OK] Aflossingsvrij: rest_lpt=org_lpt, bedrag ongewijzigd")


def test_spaar_rest_lpt_org():
    """Spaarhypotheek: rest_lpt = org_lpt (niet aflopend) tijdens looptijd."""
    delen = [{
        'aflos_type': 'Spaar',
        'org_lpt': 360,
        'rest_lpt': 360,
        'hoofdsom_box1': 200000,
        'hoofdsom_box3': 0,
        'rvp': 120,
        'werkelijke_rente': 0.04,
        'inleg_overig': 0,
    }]
    result = projecteer_hypotheekdelen(delen, 180)
    assert result[0]['rest_lpt'] == 360  # org_lpt
    assert result[0]['hoofdsom_box1'] == 200000
    print("[OK] Spaar: rest_lpt=org_lpt, bedrag ongewijzigd")


def test_spaar_na_looptijd():
    """Spaarhypotheek: afgelost aan einde looptijd."""
    delen = [{
        'aflos_type': 'Spaar',
        'org_lpt': 360,
        'rest_lpt': 360,
        'hoofdsom_box1': 200000,
        'hoofdsom_box3': 0,
        'rvp': 120,
        'werkelijke_rente': 0.04,
        'inleg_overig': 0,
    }]
    result = projecteer_hypotheekdelen(delen, 360)
    assert len(result) == 0
    print("[OK] Spaar na looptijd: volledig afgelost")


def test_box1_naar_box3():
    """Box1 schuift naar box3 als rente_aftrekbaar_tot verlopen is."""
    delen = [{
        'aflos_type': 'Aflosvrij',
        'org_lpt': 240,
        'rest_lpt': 240,
        'hoofdsom_box1': 145000,
        'hoofdsom_box3': 0,
        'rvp': 120,
        'werkelijke_rente': 0.04,
        'inleg_overig': 0,
        'rente_aftrekbaar_tot': '2046-01-01',
    }]

    # Voor aftrekbaar_tot: nog box1
    result_voor = projecteer_hypotheekdelen(delen, 200, date(2042, 9, 1))
    assert result_voor[0]['hoofdsom_box1'] == 145000
    assert result_voor[0]['hoofdsom_box3'] == 0
    print("[OK] Voor aftrekbaar_tot: box1")

    # Na aftrekbaar_tot: box3
    result_na = projecteer_hypotheekdelen(delen, 255, date(2047, 4, 1))
    assert result_na[0]['hoofdsom_box1'] == 0
    assert result_na[0]['hoofdsom_box3'] == 145000
    print("[OK] Na aftrekbaar_tot: box3")


def test_box1_box3_proportioneel():
    """Gemengde box1/box3 bij lineair: proportioneel aflossen."""
    delen = [{
        'aflos_type': 'Lineair',
        'org_lpt': 300,
        'rest_lpt': 300,
        'hoofdsom_box1': 60000,
        'hoofdsom_box3': 25000,
        'rvp': 120,
        'werkelijke_rente': 0.03,
        'inleg_overig': 0,
    }]
    result = projecteer_hypotheekdelen(delen, 150)
    d = result[0]
    total = d['hoofdsom_box1'] + d['hoofdsom_box3']
    ratio = total / 85000
    assert d['hoofdsom_box1'] == round(60000 * ratio, 2)
    assert d['hoofdsom_box3'] == round(25000 * ratio, 2)
    print(f"[OK] Proportioneel: box1=E{d['hoofdsom_box1']:,.2f}, box3=E{d['hoofdsom_box3']:,.2f}")


def test_elapsed_nul():
    """Bij 0 maanden elapsed: ongewijzigd."""
    delen = [{
        'aflos_type': 'Annuïteit',
        'org_lpt': 360,
        'rest_lpt': 360,
        'hoofdsom_box1': 120000,
        'hoofdsom_box3': 0,
        'rvp': 120,
        'werkelijke_rente': 0.05,
        'inleg_overig': 0,
    }]
    result = projecteer_hypotheekdelen(delen, 0)
    assert result[0]['hoofdsom_box1'] == 120000
    assert result[0]['rest_lpt'] == 360
    print("[OK] Elapsed 0: ongewijzigd")


if __name__ == '__main__':
    test_lineair_exact()
    test_annuitair_detail()
    test_aflossingsvrij_rest_lpt_org()
    test_spaar_rest_lpt_org()
    test_spaar_na_looptijd()
    test_box1_naar_box3()
    test_box1_box3_proportioneel()
    test_elapsed_nul()

    print()
    print("=" * 60)
    print("HARRY SLINGER — AOW aanvrager (01-04-2047)")
    print("=" * 60)
    test_aow_aanvrager()

    print()
    print("=" * 60)
    print("HARRY SLINGER — AOW partner (01-04-2052)")
    print("=" * 60)
    test_aow_partner()
