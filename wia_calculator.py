"""
WIA Calculator — Wet werk en inkomen naar arbeidsvermogen

Berekent bruto WIA-uitkering en totaal inkomen bij arbeidsongeschiktheid.
Ondersteunt alle WIA-fasen: loondoorbetaling, WGA (LGU, loonaanvulling,
vervolg), IVA, WGA 80-100%.

Statische berekening (geen indexaties), rule_version-based.
Alleen voor Nederlandse werknemerssituaties.

Drie lagen:
1. Rule engine — bepaal status op peildatum
2. Calculator — bereken maandbedragen
3. Explain layer — geef begrijpelijke toelichting

Tarieven en klassetabellen uit config/wia.json.
"""

import os
import json
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

# --- Config laden ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, 'config', 'wia.json'), 'r', encoding='utf-8') as f:
    WIA_CONFIG = json.load(f)

DAGLOON_CFG = WIA_CONFIG['dagloon']
MAX_DAGLOON = DAGLOON_CFG.get('maximum_dagloon', 0)
WGA_LGU_CFG = WIA_CONFIG['wga_lgu']
WGA_LA_CFG = WIA_CONFIG['wga_loonaanvulling']
WGA_VERVOLG_CFG = WIA_CONFIG['wga_vervolg']
IVA_CFG = WIA_CONFIG['iva']
WGA_80_100_CFG = WIA_CONFIG['wga_80_100']
WACHTTIJD_WEKEN = WIA_CONFIG['wachttijd_standaard_weken']
MIN_AO_PCT = WIA_CONFIG['minimum_ao_percentage_wia']

# AO-klassetabel: grenzen en percentages
AO_KLASSEN = [
    (35, 45, WGA_VERVOLG_CFG['ao_klassen']['35_45']),
    (45, 55, WGA_VERVOLG_CFG['ao_klassen']['45_55']),
    (55, 65, WGA_VERVOLG_CFG['ao_klassen']['55_65']),
    (65, 80, WGA_VERVOLG_CFG['ao_klassen']['65_80']),
]


def bereken_wia_uitkering(
    peildatum: date,
    first_sick_day: date,
    # Inkomen referentie
    sv_loon_12m_total: float = 0,
    pre_disability_gross_month: float = 0,
    wia_dayloon_override: float = None,
    wia_monthloon_override: float = None,
    # Arbeidsongeschiktheid
    ao_percentage: float = 0,
    is_durable: bool = False,
    residual_earning_capacity_per_month: float = None,
    current_actual_gross_wages_per_month: float = 0,
    uses_rvc_input_directly: bool = True,
    # Werkgever fase
    salary_continuation_pct_year1: float = 1.0,
    salary_continuation_pct_year2: float = 0.70,
    waiting_days: int = 0,
    wage_sanction_extension_weeks: int = 0,
    voluntary_extension_weeks: int = 0,
    # Statische referenties
    minimum_wage_month_reference: float = 0,
    maximum_day_wage_reference: float = 0,
    # Arbeidsverleden (voor LGU-duur)
    employment_history_years_to_2015: int = 0,
    employment_history_years_from_2016: int = 0,
    ww_months_before_sickness_to_deduct: int = 0,
    # Type
    employment_type: str = "nl_employee",
    is_foreign_income_case: bool = False,
) -> dict:
    """
    Bereken bruto WIA-uitkering en totaal inkomen op peildatum.

    Args:
        peildatum: Datum waarop berekening plaatsvindt
        first_sick_day: Eerste ziektedag

        -- Inkomen referentie --
        sv_loon_12m_total: SV-loon over 12 maanden referteperiode
        pre_disability_gross_month: Bruto maandloon vóór ziekte (voor loondoorbetaling)
        wia_dayloon_override: Handmatige override WIA-dagloon
        wia_monthloon_override: Handmatige override WIA-maandloon

        -- Arbeidsongeschiktheid --
        ao_percentage: AO-percentage (0-100)
        is_durable: Duurzaam arbeidsongeschikt (voor IVA)
        residual_earning_capacity_per_month: Restverdiencapaciteit in euro/maand
        current_actual_gross_wages_per_month: Feitelijk verdiend loon per maand
        uses_rvc_input_directly: True = RVC in euro's (Route A), False = afgeleid van AO%

        -- Werkgever fase --
        salary_continuation_pct_year1: Doorbetaling % jaar 1 (1.0 = 100%)
        salary_continuation_pct_year2: Doorbetaling % jaar 2
        waiting_days: Wachtdagen (normaal 0-2)
        wage_sanction_extension_weeks: Loonsanctie verlenging (weken)
        voluntary_extension_weeks: Vrijwillige verlenging (weken)

        -- Statische referenties --
        minimum_wage_month_reference: Bruto minimumloon per maand (0 = niet opgegeven)
        maximum_day_wage_reference: Maximum dagloon (0 = niet opgegeven)

        -- Arbeidsverleden --
        employment_history_years_to_2015: Arbeidsjaren t/m 2015
        employment_history_years_from_2016: Arbeidsjaren vanaf 2016
        ww_months_before_sickness_to_deduct: WW-maanden af te trekken van LGU-duur

        -- Type --
        employment_type: "nl_employee" of anders
        is_foreign_income_case: Buitenlands inkomen (geen uitkering)

    Returns:
        dict met status, bedragen, toelichting en flags
    """
    flags = []
    toelichting = []

    # --- Buitenlands / niet-werknemer → geen uitkering ---
    if employment_type != "nl_employee" or is_foreign_income_case:
        flags.append("foreign_or_non_nl_employee_case_out_of_scope")
        return _maak_resultaat(
            status="geen_wia",
            uwv_uitkering=0,
            actual_wage=current_actual_gross_wages_per_month,
            grondslag_maandloon=0,
            rvc=0,
            benutting_pct=0,
            flags=flags,
            toelichting=["Geen WIA: buitenlands inkomen of geen Nederlandse werknemer."],
        )

    # --- Dagloon en maandloon ---
    dagloon, maandloon, dl_flags, dl_toel = _bereken_dagloon_maandloon(
        sv_loon_12m_total=sv_loon_12m_total,
        wia_dayloon_override=wia_dayloon_override,
        wia_monthloon_override=wia_monthloon_override,
        maximum_day_wage_reference=maximum_day_wage_reference,
    )
    flags.extend(dl_flags)
    toelichting.extend(dl_toel)

    # Pre-disability gross month (voor loondoorbetaling)
    if pre_disability_gross_month <= 0 and sv_loon_12m_total > 0:
        pre_disability_gross_month = sv_loon_12m_total / 12

    # --- Restverdiencapaciteit en AO ---
    rvc, ao_pct, benutting_pct, rvc_flags, rvc_toel = _bepaal_rvc_en_ao(
        maandloon=maandloon,
        ao_percentage=ao_percentage,
        residual_earning_capacity_per_month=residual_earning_capacity_per_month,
        current_actual_gross_wages_per_month=current_actual_gross_wages_per_month,
        uses_rvc_input_directly=uses_rvc_input_directly,
    )
    flags.extend(rvc_flags)
    toelichting.extend(rvc_toel)

    # --- Wachttijd / einde loondoorbetaling ---
    wachttijd_einde = _bereken_wachttijd_einde(
        first_sick_day=first_sick_day,
        wage_sanction_extension_weeks=wage_sanction_extension_weeks,
        voluntary_extension_weeks=voluntary_extension_weeks,
    )

    if wage_sanction_extension_weeks > 0:
        flags.append("wage_sanction_applied")
        toelichting.append(
            f"Loonsanctie: {wage_sanction_extension_weeks} weken verlenging wachttijd."
        )

    # --- Fase 1: Loondoorbetaling ---
    if peildatum < wachttijd_einde:
        uwv, ldb_toel = _bereken_loondoorbetaling(
            peildatum=peildatum,
            first_sick_day=first_sick_day,
            pre_disability_gross_month=pre_disability_gross_month,
            salary_continuation_pct_year1=salary_continuation_pct_year1,
            salary_continuation_pct_year2=salary_continuation_pct_year2,
            minimum_wage_month_reference=minimum_wage_month_reference,
            waiting_days=waiting_days,
        )
        toelichting.extend(ldb_toel)

        if waiting_days > 0:
            flags.append("waiting_period_override_used")

        return _maak_resultaat(
            status="loondoorbetaling",
            uwv_uitkering=uwv,
            actual_wage=0,  # Loondoorbetaling vervangt loon
            grondslag_maandloon=maandloon,
            rvc=rvc,
            benutting_pct=benutting_pct,
            flags=flags,
            toelichting=toelichting,
            extra={
                "wachttijd_einde": wachttijd_einde.isoformat(),
                "pre_disability_gross_month": round(pre_disability_gross_month, 2),
            },
        )

    # --- Fase 2: WIA-toegang ---
    # AO < 35% → geen WIA
    if ao_pct < MIN_AO_PCT:
        toelichting.append(
            f"Geen WIA: AO-percentage {ao_pct:.1f}% < drempel {MIN_AO_PCT}%."
        )
        return _maak_resultaat(
            status="geen_wia",
            uwv_uitkering=0,
            actual_wage=current_actual_gross_wages_per_month,
            grondslag_maandloon=maandloon,
            rvc=rvc,
            benutting_pct=benutting_pct,
            flags=flags,
            toelichting=toelichting,
        )

    # --- IVA: >= 80% AO en duurzaam ---
    earning_capacity_pct = 100 - ao_pct
    if earning_capacity_pct <= 20 and is_durable:
        uwv = IVA_CFG['percentage'] * maandloon
        toelichting.append(
            f"IVA-uitkering: {IVA_CFG['percentage']*100:.0f}% van WIA-maandloon "
            f"({maandloon:,.2f}) = {uwv:,.2f}/mnd."
        )
        return _maak_resultaat(
            status="iva",
            uwv_uitkering=uwv,
            actual_wage=current_actual_gross_wages_per_month,
            grondslag_maandloon=maandloon,
            rvc=rvc,
            benutting_pct=benutting_pct,
            flags=flags,
            toelichting=toelichting,
        )

    # --- WGA 80-100%: >= 80% AO maar niet duurzaam ---
    if earning_capacity_pct <= 20 and not is_durable:
        months_since_wia = _maanden_verschil(wachttijd_einde, peildatum)
        if months_since_wia < 2:
            pct = WGA_80_100_CFG['percentage_maand_1_2']
        else:
            pct = WGA_80_100_CFG['percentage_maand_3_plus']
        uwv = pct * maandloon
        toelichting.append(
            f"WGA 80-100% (niet duurzaam): {pct*100:.0f}% van WIA-maandloon "
            f"({maandloon:,.2f}) = {uwv:,.2f}/mnd."
        )
        return _maak_resultaat(
            status="wga_80_100",
            uwv_uitkering=uwv,
            actual_wage=current_actual_gross_wages_per_month,
            grondslag_maandloon=maandloon,
            rvc=rvc,
            benutting_pct=benutting_pct,
            flags=flags,
            toelichting=toelichting,
        )

    # --- WGA: 35-80% AO ---
    # Bepaal LGU-duur
    lgu_maanden = _bereken_lgu_duur(
        years_to_2015=employment_history_years_to_2015,
        years_from_2016=employment_history_years_from_2016,
        ww_months_to_deduct=ww_months_before_sickness_to_deduct,
    )

    lgu_einde = wachttijd_einde + relativedelta(months=lgu_maanden)
    months_since_wia = _maanden_verschil(wachttijd_einde, peildatum)

    toelichting.append(
        f"WGA: AO-percentage {ao_pct:.1f}%, verdiencapaciteit {earning_capacity_pct:.1f}%."
    )
    toelichting.append(
        f"LGU-duur: {lgu_maanden} maanden (t/m {lgu_einde.strftime('%d-%m-%Y')})."
    )

    # --- Fase 3: WGA loongerelateerde uitkering ---
    if peildatum < lgu_einde:
        uwv, lgu_toel = _bereken_wga_lgu(
            months_since_wia=months_since_wia,
            maandloon=maandloon,
            actual_wage=current_actual_gross_wages_per_month,
        )
        toelichting.extend(lgu_toel)

        return _maak_resultaat(
            status="wga_loongerelateerd",
            uwv_uitkering=uwv,
            actual_wage=current_actual_gross_wages_per_month,
            grondslag_maandloon=maandloon,
            rvc=rvc,
            benutting_pct=benutting_pct,
            flags=flags,
            toelichting=toelichting,
            extra={
                "lgu_maanden_totaal": lgu_maanden,
                "lgu_maand_nummer": months_since_wia + 1,
                "lgu_einde": lgu_einde.isoformat(),
            },
        )

    # --- Fase 4: WGA na loongerelateerde uitkering ---
    uwv, na_lgu_status, na_lgu_toel = _bereken_wga_na_lgu(
        maandloon=maandloon,
        rvc=rvc,
        actual_wage=current_actual_gross_wages_per_month,
        ao_pct=ao_pct,
        benutting_pct=benutting_pct,
        minimum_wage=minimum_wage_month_reference,
    )
    toelichting.extend(na_lgu_toel)

    if minimum_wage_month_reference > 0 and na_lgu_status == "wga_vervolg":
        flags.append("manual_minimum_wage_reference_used")

    return _maak_resultaat(
        status=na_lgu_status,
        uwv_uitkering=uwv,
        actual_wage=current_actual_gross_wages_per_month,
        grondslag_maandloon=maandloon,
        rvc=rvc,
        benutting_pct=benutting_pct,
        flags=flags,
        toelichting=toelichting,
    )


# ============================================================
# Interne functies
# ============================================================

def _bereken_dagloon_maandloon(
    sv_loon_12m_total: float,
    wia_dayloon_override: float,
    wia_monthloon_override: float,
    maximum_day_wage_reference: float,
) -> tuple[float, float, list, list]:
    """Bereken WIA-dagloon en maandloon."""
    flags = []
    toelichting = []

    if wia_monthloon_override and wia_monthloon_override > 0:
        maandloon = wia_monthloon_override
        dagloon = maandloon / DAGLOON_CFG['maandloon_factor']
        toelichting.append(
            f"WIA-maandloon (override): {maandloon:,.2f}"
        )
        return dagloon, maandloon, flags, toelichting

    if wia_dayloon_override and wia_dayloon_override > 0:
        dagloon = wia_dayloon_override
    elif sv_loon_12m_total > 0:
        dagloon = sv_loon_12m_total / DAGLOON_CFG['werkdagen_per_jaar']
    else:
        flags.append("salary_history_incomplete")
        toelichting.append("Geen sv-loon of dagloon opgegeven — berekening onbetrouwbaar.")
        return 0, 0, flags, toelichting

    # Maximum dagloon toepassen
    if maximum_day_wage_reference > 0 and dagloon > maximum_day_wage_reference:
        toelichting.append(
            f"Dagloon ({dagloon:,.2f}) afgetopt op maximum ({maximum_day_wage_reference:,.2f})."
        )
        dagloon = maximum_day_wage_reference
        flags.append("manual_maximum_day_wage_reference_used")

    maandloon = dagloon * DAGLOON_CFG['maandloon_factor']
    toelichting.append(
        f"WIA-dagloon: {dagloon:,.2f} (sv-loon / {DAGLOON_CFG['werkdagen_per_jaar']}). "
        f"WIA-maandloon: {maandloon:,.2f} (dagloon x {DAGLOON_CFG['maandloon_factor']})."
    )

    return dagloon, maandloon, flags, toelichting


def _bepaal_rvc_en_ao(
    maandloon: float,
    ao_percentage: float,
    residual_earning_capacity_per_month: float,
    current_actual_gross_wages_per_month: float,
    uses_rvc_input_directly: bool,
) -> tuple[float, float, float, list, list]:
    """
    Bepaal restverdiencapaciteit, AO-percentage en benuttingspercentage.

    Route A (uses_rvc_input_directly=True): RVC in euro's, leidt AO% af
    Route B: AO% gegeven, leidt RVC af
    """
    flags = []
    toelichting = []
    actual = current_actual_gross_wages_per_month

    if maandloon <= 0:
        return 0, ao_percentage, 0, flags, toelichting

    if uses_rvc_input_directly and residual_earning_capacity_per_month is not None:
        rvc = residual_earning_capacity_per_month
        ao_pct = (maandloon - rvc) / maandloon * 100 if maandloon > 0 else 0
        ao_pct = max(0, min(100, ao_pct))

        # Check consistentie met opgegeven AO%
        if ao_percentage > 0 and abs(ao_pct - ao_percentage) > 2:
            flags.append("ao_pct_and_rvc_conflict")
            toelichting.append(
                f"Let op: afgeleid AO ({ao_pct:.1f}%) wijkt af van opgegeven AO ({ao_percentage:.1f}%). "
                f"RVC-invoer ({rvc:,.2f}) gevolgd (Route A)."
            )

        toelichting.append(
            f"RVC: {rvc:,.2f}/mnd (invoer). "
            f"AO: {ao_pct:.1f}% = (maandloon {maandloon:,.2f} - rvc {rvc:,.2f}) / maandloon."
        )
    else:
        # Route B: afgeleid van AO%
        ao_pct = ao_percentage
        rvc = maandloon * (1 - ao_pct / 100)
        toelichting.append(
            f"AO: {ao_pct:.1f}% (invoer). "
            f"RVC: {rvc:,.2f}/mnd = maandloon {maandloon:,.2f} x {(1 - ao_pct/100):.2f}."
        )

    # Benuttingspercentage
    if rvc > 0:
        benutting_pct = actual / rvc * 100
    else:
        benutting_pct = 0

    toelichting.append(
        f"Benutting RVC: {benutting_pct:.1f}% "
        f"(feitelijk loon {actual:,.2f} / rvc {rvc:,.2f})."
    )

    return rvc, ao_pct, benutting_pct, flags, toelichting


def _bereken_wachttijd_einde(
    first_sick_day: date,
    wage_sanction_extension_weeks: int = 0,
    voluntary_extension_weeks: int = 0,
) -> date:
    """Bereken einde wachttijd (= start WIA)."""
    total_weeks = WACHTTIJD_WEKEN + wage_sanction_extension_weeks + voluntary_extension_weeks
    return first_sick_day + timedelta(weeks=total_weeks)


def _bereken_loondoorbetaling(
    peildatum: date,
    first_sick_day: date,
    pre_disability_gross_month: float,
    salary_continuation_pct_year1: float,
    salary_continuation_pct_year2: float,
    minimum_wage_month_reference: float,
    waiting_days: int,
) -> tuple[float, list]:
    """Bereken loondoorbetaling bij ziekte."""
    toelichting = []

    # Wachtdagen: eerste N dagen geen loon
    if waiting_days > 0:
        wachtdag_einde = first_sick_day + timedelta(days=waiting_days)
        if peildatum < wachtdag_einde:
            toelichting.append(
                f"Wachtdag {(peildatum - first_sick_day).days + 1} van {waiting_days}: geen loon."
            )
            return 0, toelichting

    # Jaar 1 of jaar 2?
    jaar1_einde = first_sick_day + timedelta(weeks=52)

    if peildatum < jaar1_einde:
        # Jaar 1: pct × loon, minimaal minimumloon
        bruto = salary_continuation_pct_year1 * pre_disability_gross_month
        if minimum_wage_month_reference > 0:
            bruto = max(bruto, minimum_wage_month_reference)
        toelichting.append(
            f"Loondoorbetaling jaar 1: {salary_continuation_pct_year1*100:.0f}% van "
            f"{pre_disability_gross_month:,.2f} = {bruto:,.2f}/mnd"
            + (f" (min. minimumloon {minimum_wage_month_reference:,.2f})"
               if minimum_wage_month_reference > 0 else "")
            + "."
        )
    else:
        # Jaar 2: pct × loon, geen verplichte minimumloon-vloer
        bruto = salary_continuation_pct_year2 * pre_disability_gross_month
        toelichting.append(
            f"Loondoorbetaling jaar 2: {salary_continuation_pct_year2*100:.0f}% van "
            f"{pre_disability_gross_month:,.2f} = {bruto:,.2f}/mnd (geen minimumloon-vloer)."
        )

    return round(bruto, 2), toelichting


def _bereken_lgu_duur(
    years_to_2015: int,
    years_from_2016: int,
    ww_months_to_deduct: int = 0,
) -> int:
    """
    Bereken duur WGA loongerelateerde uitkering in maanden.

    Eerste 10 jaren arbeidsverleden: 1 maand per jaar.
    Daarboven t/m 2015: 1 maand per jaar.
    Daarboven vanaf 2016: 0,5 maand per jaar.
    Min 3, max 24 maanden.
    WW-maanden worden afgetrokken.
    """
    total = years_to_2015 + years_from_2016

    # Eerste 10 jaren vullen (chronologisch: pre-2016 eerst)
    first_10_pre2016 = min(years_to_2015, 10)
    first_10_post2016 = min(years_from_2016, max(0, 10 - first_10_pre2016))
    months = first_10_pre2016 + first_10_post2016  # elk 1 maand

    # Resterende jaren boven de 10
    remaining_pre2016 = years_to_2015 - first_10_pre2016
    remaining_post2016 = years_from_2016 - first_10_post2016
    months += remaining_pre2016 * 1  # t/m 2015: 1 maand
    months += remaining_post2016 * 0.5  # vanaf 2016: 0,5 maand

    # WW aftrekken
    months -= ww_months_to_deduct

    # Grenzen
    months = max(WGA_LGU_CFG['minimum_duur_maanden'],
                 min(WGA_LGU_CFG['maximum_duur_maanden'], int(months)))

    return months


def _bereken_wga_lgu(
    months_since_wia: int,
    maandloon: float,
    actual_wage: float,
) -> tuple[float, list]:
    """
    Bereken WGA loongerelateerde uitkering.

    Zonder werken:
    - Maand 1-2: 75% van WIA-maandloon
    - Maand 3+: 70% van WIA-maandloon

    Met werken: verrekening (manual review flag).
    """
    toelichting = []

    if actual_wage > 0:
        # Met inkomsten: benadering, maar flag voor handmatige controle
        if months_since_wia < 2:
            pct = WGA_LGU_CFG['percentage_maand_1_2']
        else:
            pct = WGA_LGU_CFG['percentage_maand_3_plus']
        uwv = pct * maandloon
        # Bij inkomsten verrekent UWV gedeeltelijk
        # Exacte formule niet volledig publiek → flag
        toelichting.append(
            f"WGA LGU met inkomsten: {pct*100:.0f}% van {maandloon:,.2f} = {uwv:,.2f}/mnd "
            f"(vóór verrekening met feitelijk loon {actual_wage:,.2f})."
        )
        toelichting.append(
            "Let op: verrekening inkomsten tijdens LGU vereist handmatige controle."
        )
        return round(uwv, 2), toelichting

    # Zonder werken
    if months_since_wia < 2:
        pct = WGA_LGU_CFG['percentage_maand_1_2']
        label = "maand 1-2"
    else:
        pct = WGA_LGU_CFG['percentage_maand_3_plus']
        label = "maand 3+"

    uwv = pct * maandloon
    toelichting.append(
        f"WGA LGU ({label}): {pct*100:.0f}% van WIA-maandloon "
        f"({maandloon:,.2f}) = {uwv:,.2f}/mnd."
    )

    return round(uwv, 2), toelichting


def _bereken_wga_na_lgu(
    maandloon: float,
    rvc: float,
    actual_wage: float,
    ao_pct: float,
    benutting_pct: float,
    minimum_wage: float,
) -> tuple[float, str, list]:
    """
    Bereken WGA na loongerelateerde fase.

    Benutting >= 100%: loonaanvulling variant 1
        = 70% × (maandloon - feitelijk loon)
    Benutting >= 50%: loonaanvulling variant 2
        = 70% × (maandloon - rvc)
    Benutting < 50%: vervolguitkering
        = AO-klasse % × min(minimumloon, maandloon)
    """
    toelichting = []
    la_pct = WGA_LA_CFG['percentage']

    if benutting_pct >= 100:
        # Variant 1: verdient rvc of meer
        uwv = la_pct * (maandloon - actual_wage)
        uwv = max(0, uwv)
        toelichting.append(
            f"WGA loonaanvulling variant 1 (benutting {benutting_pct:.0f}% >= 100%): "
            f"{la_pct*100:.0f}% x (maandloon {maandloon:,.2f} - feitelijk loon {actual_wage:,.2f}) "
            f"= {uwv:,.2f}/mnd."
        )
        return round(uwv, 2), "wga_loonaanvulling", toelichting

    if benutting_pct >= 50:
        # Variant 2: verdient 50-99% van rvc
        uwv = la_pct * (maandloon - rvc)
        uwv = max(0, uwv)
        toelichting.append(
            f"WGA loonaanvulling variant 2 (benutting {benutting_pct:.0f}% >= 50%): "
            f"{la_pct*100:.0f}% x (maandloon {maandloon:,.2f} - rvc {rvc:,.2f}) "
            f"= {uwv:,.2f}/mnd."
        )
        return round(uwv, 2), "wga_loonaanvulling", toelichting

    # Benutting < 50%: vervolguitkering
    ao_klasse_pct = _bepaal_ao_klasse_pct(ao_pct)

    if minimum_wage <= 0:
        # Geen minimumloon opgegeven → flag, gebruik maandloon als basis
        toelichting.append(
            "Minimumloon niet opgegeven — vervolguitkering berekend op basis van WIA-maandloon."
        )
        base = maandloon
    else:
        base = min(minimum_wage, maandloon)

    uwv = ao_klasse_pct * base
    toelichting.append(
        f"WGA vervolguitkering (benutting {benutting_pct:.0f}% < 50%): "
        f"AO-klasse {ao_pct:.0f}% → {ao_klasse_pct*100:.2f}% x {base:,.2f} "
        f"= {uwv:,.2f}/mnd."
    )

    return round(uwv, 2), "wga_vervolg", toelichting


def _bepaal_ao_klasse_pct(ao_pct: float) -> float:
    """Bepaal vervolguitkering-percentage op basis van AO-klasse."""
    for lower, upper, pct in AO_KLASSEN:
        if lower <= ao_pct < upper:
            return pct
    # 65-80%: bovengrens is inclusief voor de hoogste klasse
    if ao_pct >= 65:
        return AO_KLASSEN[-1][2]
    return 0


def _maanden_verschil(van: date, tot: date) -> int:
    """Bereken aantal maanden tussen twee datums."""
    rd = relativedelta(tot, van)
    return rd.years * 12 + rd.months


def _maak_resultaat(
    status: str,
    uwv_uitkering: float,
    actual_wage: float,
    grondslag_maandloon: float,
    rvc: float,
    benutting_pct: float,
    flags: list,
    toelichting: list,
    extra: dict = None,
) -> dict:
    """Bouw het resultaat-dict."""
    uwv = round(uwv_uitkering, 2)
    actual = round(actual_wage, 2)
    totaal = round(uwv + actual, 2)

    result = {
        "status": status,
        "uwv_uitkering_bruto_per_maand": uwv,
        "loon_uit_arbeid_bruto_per_maand": actual,
        "totaal_bruto_per_maand": totaal,
        "totaal_bruto_per_jaar": round(totaal * 12, 2),
        "grondslag_maandloon": round(grondslag_maandloon, 2),
        "restverdiencapaciteit_euro_per_maand": round(rvc, 2),
        "benuttingspercentage_restverdiencapaciteit": round(benutting_pct, 1),
        "manual_review_flags": flags,
        "toelichting": toelichting,
    }
    if extra:
        result.update(extra)
    return result


# ============================================================
# Vereenvoudigde helper voor risk_scenarios.py
# ============================================================

def bereken_wia_bruto_jaar(
    ao_percentage: float,
    sv_loon_jaar: float,
    feitelijk_loon_maand: float = 0,
    is_durable: bool = False,
    employment_history_years_to_2015: int = 10,
    employment_history_years_from_2016: int = 5,
    minimum_wage_month_reference: float = 0,
    fase: str = "na_lgu",
) -> dict:
    """
    Vereenvoudigde WIA-berekening voor risicoscenario's.

    Geeft bruto jaarbedrag terug voor een specifieke WIA-fase.
    Gebruikt standaard peildatum zodat de gevraagde fase actief is.

    Args:
        ao_percentage: AO-percentage (0-100)
        sv_loon_jaar: SV-loon per jaar (voor dagloon)
        feitelijk_loon_maand: Wat de persoon nu verdient per maand
        is_durable: Duurzaam AO (voor IVA)
        employment_history_years_to_2015: Arbeidsjaren t/m 2015
        employment_history_years_from_2016: Arbeidsjaren vanaf 2016
        minimum_wage_month_reference: Minimumloon (voor vervolg)
        fase: "loondoorbetaling_y1", "loondoorbetaling_y2", "lgu", "na_lgu"

    Returns:
        dict met status, uwv per maand/jaar, totaal per maand/jaar
    """
    # Stel peildatum zo in dat de gewenste fase actief is
    fake_sick = date(2020, 1, 1)

    if fase == "loondoorbetaling_y1":
        peil = fake_sick + timedelta(weeks=26)  # halverwege jaar 1
    elif fase == "loondoorbetaling_y2":
        peil = fake_sick + timedelta(weeks=78)  # halverwege jaar 2
    elif fase == "lgu":
        peil = fake_sick + timedelta(weeks=115)  # ~11 weken in LGU → maand 3+ (70%)
    else:  # na_lgu
        peil = fake_sick + timedelta(weeks=104 + 130)  # ruim na LGU

    result = bereken_wia_uitkering(
        peildatum=peil,
        first_sick_day=fake_sick,
        sv_loon_12m_total=sv_loon_jaar,
        ao_percentage=ao_percentage,
        is_durable=is_durable,
        current_actual_gross_wages_per_month=feitelijk_loon_maand,
        uses_rvc_input_directly=False,
        employment_history_years_to_2015=employment_history_years_to_2015,
        employment_history_years_from_2016=employment_history_years_from_2016,
        minimum_wage_month_reference=minimum_wage_month_reference,
        maximum_day_wage_reference=MAX_DAGLOON,
    )

    return {
        "status": result['status'],
        "uwv_uitkering_bruto_maand": result['uwv_uitkering_bruto_per_maand'],
        "uwv_uitkering_bruto_jaar": round(result['uwv_uitkering_bruto_per_maand'] * 12, 2),
        "loon_uit_arbeid_bruto_maand": result['loon_uit_arbeid_bruto_per_maand'],
        "totaal_bruto_maand": result['totaal_bruto_per_maand'],
        "totaal_bruto_jaar": result['totaal_bruto_per_jaar'],
        "toelichting": result['toelichting'],
    }
