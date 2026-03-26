"""Piekdetectie en aftopping conform §6 IBL Rekenregels v8.1.1."""

from decimal import Decimal

from .models import (
    LoonItem, BerekeningType, Betaaltermijn,
    jaar_perioden,
)

CENT = Decimal("0.01")
PIEK_RATIO = Decimal("1.30")
EIP_REF_FACTOR = Decimal("1.50")   # 150% referentie (GPI threshold)
EIP_CAP_FACTOR = Decimal("2.00")   # 200% GPI (EIP-A cap)
ENIP_MAAND = Decimal("4") / Decimal("12")   # 4/12e
ENIP_WEEK = Decimal("17") / Decimal("52")   # 17/52e


# ---------------------------------------------------------------------------
# §6.2  Vaststellen (Niet-)Incidentele Pieken
# ---------------------------------------------------------------------------

def bepaal_incidentele_pieken(
    items: list[LoonItem],
    berekening_type: BerekeningType,
    betaaltermijn: Betaaltermijn,
) -> set[int]:
    """Bepaal welke periodes incidentele pieken zijn.

    Per periode in jaar 1: vergelijk MAX/MIN over dezelfde periode in
    jaar 1, 2 en (indien beschikbaar) 3.
    MAX / MIN > 1,30  →  alle betrokken periodes = Incidentele Piek.

    A/D-berekening: niet van toepassing → leeg resultaat.
    """
    if berekening_type in (BerekeningType.A, BerekeningType.D):
        return set()

    jp = jaar_perioden(betaaltermijn)          # 12 of 13
    incidentele: set[int] = set()

    for i in range(min(jp, len(items))):
        waarden: list[Decimal] = []
        indices: list[int] = []

        for jaar in range(3):
            idx = i + jaar * jp
            if idx >= len(items):
                # Niet aanwezig
                if berekening_type == BerekeningType.C:
                    waarden.append(CENT)
                # B: niet meenemen (skip)
                continue

            sv = items[idx].sv_loon
            if sv <= Decimal("0"):
                waarden.append(CENT)
            else:
                waarden.append(sv)
            indices.append(idx)

        if len(waarden) < 2:
            continue

        min_v = min(waarden)
        max_v = max(waarden)
        if min_v <= Decimal("0"):
            min_v = CENT

        if max_v / min_v > PIEK_RATIO:
            for idx in indices:
                incidentele.add(idx)

    return incidentele


# ---------------------------------------------------------------------------
# §6.3  Gemiddeld Periode Inkomen (GPI)
# ---------------------------------------------------------------------------

def bereken_gpi(
    items: list[LoonItem],
    incidentele_pieken: set[int],
    scope: int,
) -> Decimal:
    """Bereken het Gemiddeld Periode Inkomen.

    Periodes die NIET meetellen:
    - Incidentele Piek EN > 150 % van ReferentiePeriode GPI
    - Niet aanwezig
    - SV Loon ≤ EUR 0,00

    ReferentiePeriode GPI = voorgaande periode met SV > 0 (mag buiten scope).
    """
    totaal = Decimal("0")
    count = 0

    for i in range(min(scope, len(items))):
        sv = items[i].sv_loon
        if sv <= Decimal("0"):
            continue

        # Incidentele piek EN > 150 % referentie?
        if i in incidentele_pieken:
            ref = _vind_referentie_voorgaand(items, i)
            if ref is not None and sv > ref * EIP_REF_FACTOR:
                continue        # Uitsluiten

        totaal += sv
        count += 1

    return totaal / count if count > 0 else Decimal("0")


def _vind_referentie_voorgaand(items: list[LoonItem], index: int) -> "Decimal | None":
    """Vind de voorgaande periode met SV > 0 (kan buiten scope liggen)."""
    for j in range(index + 1, len(items)):
        if items[j].sv_loon > Decimal("0"):
            return items[j].sv_loon
    return None


# ---------------------------------------------------------------------------
# §6.4  Aftopping Excessieve Incidentele Pieken (EIP)
# ---------------------------------------------------------------------------

def cap_eip(
    items: list[LoonItem],
    incidentele_pieken: set[int],
    gpi: Decimal,
    berekening_type: BerekeningType,
    betaaltermijn: Betaaltermijn,
) -> list[Decimal]:
    """Cap excessieve incidentele pieken.

    EIP criteria: Incidentele Piek EN > 150 % GPI.

    B: cap = min(bedrag, EIP-A, EIP-B)
       EIP-A = 200 % GPI
       EIP-B = min(gemiddelde 3 ref.perioden, meest recente ref)
    C: cap = min(bedrag, EIP-A)
    A/D: niet van toepassing.
    """
    sv = [item.sv_loon for item in items]

    if berekening_type in (BerekeningType.A, BerekeningType.D):
        return sv

    threshold = gpi * EIP_REF_FACTOR      # 150 % GPI
    cap_a = gpi * EIP_CAP_FACTOR           # 200 % GPI
    jp = jaar_perioden(betaaltermijn)

    for i in range(len(sv)):
        if i not in incidentele_pieken:
            continue
        if sv[i] <= threshold:
            continue

        # --- Excessieve Incidentele Piek ---
        cap = cap_a                        # EIP-A

        if berekening_type == BerekeningType.B:
            # EIP-B: referentieperioden = dezelfde slot in jaar 1, 2, 3
            slot = i % jp
            refs: list[Decimal] = []
            meest_recente_ref: Decimal | None = None

            for jaar in range(3):
                ri = slot + jaar * jp
                if ri < len(items) and items[ri].sv_loon >= Decimal("0"):
                    refs.append(items[ri].sv_loon)
                    if meest_recente_ref is None and items[ri].sv_loon > Decimal("0"):
                        meest_recente_ref = items[ri].sv_loon

            if refs and meest_recente_ref is not None:
                gem = sum(refs) / len(refs)
                eip_b = min(gem, meest_recente_ref)
                cap = min(cap, eip_b)

        sv[i] = min(sv[i], cap)

    return sv


# ---------------------------------------------------------------------------
# §6.5  Gemiddeld Jaarinkomen (GJI)
# ---------------------------------------------------------------------------

def _bereken_gji_scope(
    sv_values: list[Decimal],
    scope: int,
) -> Decimal:
    """Bereken gemiddeld periode-inkomen voor GJI over een scope.

    Per periode: ratio t.o.v. voorgaande periode met SV > 0.
    ratio ≤ 1,3 → meetellen; > 1,3 → uitsluiten.
    Geen referentie → vergelijk met zichzelf (ratio = 1).
    """
    meetellend: list[Decimal] = []

    for i in range(min(scope, len(sv_values))):
        sv = sv_values[i]
        if sv <= Decimal("0"):
            continue

        # Zoek referentie (mag buiten scope)
        ref = None
        for j in range(i + 1, len(sv_values)):
            if sv_values[j] > Decimal("0"):
                ref = sv_values[j]
                break

        if ref is None:
            # Vergelijk met zichzelf → ratio = 1 → meetellen
            meetellend.append(sv)
            continue

        ratio = sv / ref
        if ratio <= Decimal("1.3"):
            meetellend.append(sv)

    if not meetellend:
        return Decimal("0")
    return sum(meetellend) / len(meetellend)


def bereken_gji(
    sv_values: list[Decimal],
    betaaltermijn: Betaaltermijn,
) -> Decimal:
    """Bereken het Gemiddeld Jaarinkomen = min(GJI 3jr, GJI 1jr).

    Gebruikt post-EIP waarden als input.
    """
    jp = jaar_perioden(betaaltermijn)

    gpi_3jr = _bereken_gji_scope(sv_values, 3 * jp)
    gji_3yr = gpi_3jr * jp

    gpi_1jr = _bereken_gji_scope(sv_values, jp)
    gji_1yr = gpi_1jr * jp

    return min(gji_3yr, gji_1yr)


# ---------------------------------------------------------------------------
# §6.6  Aftopping Excessieve Niet-Incidentele Pieken (ENIP)
# ---------------------------------------------------------------------------

def cap_enip(
    sv_values: list[Decimal],
    incidentele_pieken: set[int],
    gji: Decimal,
    betaaltermijn: Betaaltermijn,
) -> list[Decimal]:
    """Cap excessieve niet-incidentele pieken.

    ENIP criteria: Niet-Incidentele Piek EN > 4/12 GJI (of 17/52).
    ENIP-A = 4/12 GJI (of 17/52)
    ENIP-B = min(gemiddelde ref.perioden, meest recente ref)

    NB: ook bij A-berekening toegepast (met 3 jaar data).
    """
    jp = jaar_perioden(betaaltermijn)
    result = list(sv_values)

    if gji <= Decimal("0"):
        return result

    grens = gji * (ENIP_MAAND if betaaltermijn == Betaaltermijn.MAANDELIJKS else ENIP_WEEK)

    for i in range(len(result)):
        # Alleen niet-incidentele pieken
        if i in incidentele_pieken:
            continue
        if result[i] <= grens:
            continue

        # --- Excessieve Niet-Incidentele Piek ---
        cap = grens                        # ENIP-A

        # ENIP-B: referentieperioden (zelfde slot in jaar 1, 2, 3)
        slot = i % jp
        refs: list[Decimal] = []
        meest_recente_ref: Decimal | None = None

        for jaar in range(3):
            ri = slot + jaar * jp
            if ri < len(sv_values) and sv_values[ri] > Decimal("0"):
                refs.append(sv_values[ri])
                if meest_recente_ref is None:
                    meest_recente_ref = sv_values[ri]

        if refs and meest_recente_ref is not None:
            gem = sum(refs) / len(refs)
            enip_b = min(gem, meest_recente_ref)
            cap = min(cap, enip_b)

        result[i] = min(result[i], cap)

    return result


# ---------------------------------------------------------------------------
# Hoofdfunctie: volledige piek-pipeline
# ---------------------------------------------------------------------------

def analyseer_pieken(
    items: list[LoonItem],
    berekening_type: BerekeningType,
    betaaltermijn: Betaaltermijn,
) -> tuple[list[Decimal], dict]:
    """Voer de volledige piekanalyse uit (§6.2 t/m §6.6).

    Args:
        items: Loon items gesorteerd meest recent → oudst.
        berekening_type: A, B, C of D.
        betaaltermijn: Maandelijks of vierwekelijks.

    Returns:
        sv_gecorrigeerd: Lijst van (eventueel afgetopte) SV-loon waarden.
        info: Dict met tussenresultaten (incidentele_pieken, gpi, gji).
    """
    if berekening_type == BerekeningType.D:
        return [item.sv_loon for item in items], {}

    jp = jaar_perioden(betaaltermijn)
    scope = min(3 * jp, len(items))

    if berekening_type == BerekeningType.A:
        # Geen §6.2, geen GPI, geen EIP
        inc_pieken: set[int] = set()
        sv_values = [item.sv_loon for item in items]
        gpi_val = None
    else:
        # B of C: §6.2 → §6.3 → §6.4
        inc_pieken = bepaal_incidentele_pieken(items, berekening_type, betaaltermijn)
        gpi_val = bereken_gpi(items, inc_pieken, scope)
        sv_values = cap_eip(items, inc_pieken, gpi_val, berekening_type, betaaltermijn)

    # §6.5 → §6.6 (voor A, B én C)
    gji_val = bereken_gji(sv_values, betaaltermijn)
    sv_final = cap_enip(sv_values, inc_pieken, gji_val, betaaltermijn)

    return sv_final, {
        "incidentele_pieken": inc_pieken,
        "gpi": gpi_val,
        "gji": gji_val,
    }
