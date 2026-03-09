"""
Hypotheekdelen Projectie Module

Berekent restant schuld en restant looptijd per hypotheekdeel
op een toekomstig moment. Input en output in NAT calculator formaat
zodat geprojecteerde delen direct herbruikt kunnen worden in calculate().

Regels:
- Annuïteit: standaard annuïtaire aflossing (closed-form)
- Lineair: gelijke maandelijkse aflossing (hoofdsom / looptijd)
- Aflossingsvrij: geen aflossing, bedrag blijft gelijk, ook na looptijd
- Spaar/Bankspaarhypotheek: geen aflossing tijdens looptijd, afgelost aan einde
- Geen rentewijzigingen aangenomen
- Geen extra vrijwillige aflossingen aangenomen
- Box1→Box3 transitie op basis van rente_aftrekbaar_tot datum
- rest_lpt: restant voor annuïteit/lineair, org_lpt voor aflossingsvrij/spaar
"""

from datetime import date


def projecteer_hypotheekdelen(delen: list[dict], elapsed_months: int,
                              peildatum: date = None) -> list[dict]:
    """
    Projecteer alle hypotheekdelen vooruit in de tijd.

    Args:
        delen: Hypotheekdelen in uitgebreid formaat:
               - aflos_type, org_lpt, rest_lpt, hoofdsom_box1, hoofdsom_box3,
                 rvp, werkelijke_rente, inleg_overig
               - rente_aftrekbaar_tot (optioneel, str "YYYY-MM-DD" of date):
                 als peildatum > deze datum, schuift box1 naar box3
        elapsed_months: Aantal maanden vooruit te projecteren
        peildatum: Doeldatum voor box1/box3 check (optioneel)

    Returns:
        Geprojecteerde hypotheekdelen in NAT calculator formaat.
        Volledig afgeloste delen (restant=0) worden uitgefilterd.
    """
    if elapsed_months <= 0:
        return [dict(d) for d in delen]

    result = []
    for deel in delen:
        projected = _projecteer_deel(deel, elapsed_months, peildatum)
        total = projected['hoofdsom_box1'] + projected['hoofdsom_box3']
        if total > 0:
            result.append(projected)
    return result


def _projecteer_deel(deel: dict, elapsed_months: int,
                     peildatum: date = None) -> dict:
    """Projecteer een enkel hypotheekdeel vooruit."""
    aflos_type = deel.get('aflos_type', '')
    hoofdsom_box1 = deel.get('hoofdsom_box1', 0)
    hoofdsom_box3 = deel.get('hoofdsom_box3', 0)
    hoofdsom = hoofdsom_box1 + hoofdsom_box3
    rente = deel.get('werkelijke_rente', 0)
    rest_lpt = deel.get('rest_lpt', deel.get('org_lpt', 360))
    org_lpt = deel.get('org_lpt', rest_lpt)

    is_annuitair_linear = aflos_type in ('Annuïteit', 'Lineair')

    if aflos_type in ('Aflosvrij', 'Aflossingsvrij'):
        # Geen aflossing, bedrag blijft gelijk, ook na afloop looptijd
        restant = hoofdsom
        # Aflossingsvrij/spaar: output rest_lpt = org_lpt
        new_rest_lpt = org_lpt

    elif aflos_type in ('Spaar', 'Spaarhypotheek'):
        # Geen aflossing tijdens looptijd, lump sum aan einde
        if elapsed_months >= rest_lpt:
            restant = 0.0
            new_rest_lpt = 0
        else:
            restant = hoofdsom
            # Spaar: output rest_lpt = org_lpt
            new_rest_lpt = org_lpt

    elif aflos_type == 'Annuïteit':
        if elapsed_months >= rest_lpt:
            restant = 0.0
            new_rest_lpt = 0
        else:
            restant = _annuitair_restant(hoofdsom, rente, rest_lpt, elapsed_months)
            new_rest_lpt = rest_lpt - elapsed_months

    elif aflos_type == 'Lineair':
        if elapsed_months >= rest_lpt:
            restant = 0.0
            new_rest_lpt = 0
        else:
            restant = _lineair_restant(hoofdsom, rest_lpt, elapsed_months)
            new_rest_lpt = rest_lpt - elapsed_months

    else:
        # Onbekend type → behandel als aflossingsvrij
        restant = hoofdsom
        new_rest_lpt = org_lpt

    # Box1/box3 verdeling: check rente_aftrekbaar_tot
    if hoofdsom > 0 and restant > 0:
        ratio = restant / hoofdsom
        box1 = round(hoofdsom_box1 * ratio, 2)
        box3 = round(hoofdsom_box3 * ratio, 2)

        # Als peildatum voorbij rente_aftrekbaar_tot → box1 wordt box3
        if peildatum and 'rente_aftrekbaar_tot' in deel and deel['rente_aftrekbaar_tot']:
            aftrekbaar_tot = deel['rente_aftrekbaar_tot']
            if isinstance(aftrekbaar_tot, str):
                aftrekbaar_tot = date.fromisoformat(aftrekbaar_tot)
            if peildatum > aftrekbaar_tot:
                box3 = round(box1 + box3, 2)
                box1 = 0.0
    else:
        box1 = 0.0
        box3 = 0.0

    return {
        'aflos_type': aflos_type,
        'org_lpt': org_lpt,
        'rest_lpt': new_rest_lpt,
        'hoofdsom_box1': box1,
        'hoofdsom_box3': box3,
        'rvp': max(0, deel.get('rvp', 120) - elapsed_months),
        'werkelijke_rente': rente,
        'inleg_overig': deel.get('inleg_overig', 0),
    }


def _annuitair_restant(hoofdsom: float, jaarrente: float,
                       rest_lpt: int, elapsed: int) -> float:
    """
    Bereken restant schuld na elapsed maanden voor annuïteit.

    Gebruikt closed-form formule (geen afrondingsfouten):
    B_n = P(1+r)^n - A * ((1+r)^n - 1) / r
    """
    if elapsed <= 0:
        return hoofdsom

    r = jaarrente / 12  # maandrente

    if r == 0:
        maandlast = hoofdsom / rest_lpt
        return round(max(0, hoofdsom - maandlast * elapsed), 2)

    # Maandlast (PMT formule)
    factor_n = (1 + r) ** rest_lpt
    maandlast = hoofdsom * (r * factor_n) / (factor_n - 1)

    # Closed-form restant na elapsed maanden
    factor_e = (1 + r) ** elapsed
    restant = hoofdsom * factor_e - maandlast * (factor_e - 1) / r

    return round(max(0, restant), 2)


def _lineair_restant(hoofdsom: float, rest_lpt: int, elapsed: int) -> float:
    """
    Bereken restant schuld na elapsed maanden voor lineair.

    Elke maand wordt hetzelfde bedrag afgelost: hoofdsom / looptijd.
    """
    if elapsed <= 0:
        return hoofdsom

    maandelijkse_aflossing = hoofdsom / rest_lpt
    restant = hoofdsom - maandelijkse_aflossing * elapsed
    return round(max(0, restant), 2)
