"""
WW Calculator — Werkloosheidswet

Berekent bruto WW-uitkering en totaal inkomen bij werkloosheid.

Statische berekening (geen indexaties), rule_version-based.
Alleen voor Nederlandse werknemerssituaties.

Drie lagen:
1. Recht op WW — toelatingscriteria (wekeneis, urenverlies)
2. Duur WW — op basis van arbeidsverleden (3-24 maanden)
3. Hoogte WW — percentage van maandloon + inkomstenverrekening

Tarieven uit config/ww.json.
"""

import os
import json
from datetime import date
from dateutil.relativedelta import relativedelta

# --- Config laden ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, 'config', 'ww.json'), 'r', encoding='utf-8') as f:
    WW_CONFIG = json.load(f)

DAGLOON_CFG = WW_CONFIG['dagloon']
UITKERING_CFG = WW_CONFIG['uitkering']
DUUR_CFG = WW_CONFIG['duur']
VERREKENING_CFG = WW_CONFIG['inkomstenverrekening']
WEKENEIS_CFG = WW_CONFIG['wekeneis']
URENVERLIES_CFG = WW_CONFIG['urenverlies']


def bereken_ww_uitkering(
    peildatum: date,
    first_unemployment_day: date,
    # Inkomen referentie
    sv_loon_12m_total: float = 0,
    ww_day_wage_override: float = None,
    ww_month_wage_override: float = None,
    # Urenverlies
    avg_hours_per_week_before_unemployment: float = 40.0,
    hours_lost_per_week: float = 40.0,
    hours_remaining_per_week: float = 0.0,
    lost_wages_for_lost_hours: bool = True,
    # Wekeneis
    weeks_worked_last_36: int = 36,
    # Arbeidsverleden
    employment_years_total_relevant: int = 0,
    employment_years_pre2016_above10: int = 0,
    employment_years_from2016_above10: int = 0,
    # Werken naast WW
    earnings_from_employment_month: float = 0,
    self_employed_hours_month: float = 0,
    other_non_insured_hours_month: float = 0,
    # Garantiedagloon
    use_guarantee_day_wage: bool = False,
    guarantee_day_wage_override: float = None,
    # Overrides
    manual_end_reason: str = None,
    manual_duration_months_override: int = None,
    # Stopregel: vorige maand ook boven 87.5%?
    previous_month_earnings_above_threshold: bool = False,
    # Type
    employment_type: str = "nl_employee",
    is_foreign_income_case: bool = False,
    insured_for_unemployment: bool = True,
    available_for_paid_work: bool = True,
) -> dict:
    """
    Bereken bruto WW-uitkering en totaal inkomen op peildatum.

    Args:
        peildatum: Datum waarop berekening plaatsvindt
        first_unemployment_day: Eerste werkloosheidsdag

        -- Inkomen referentie --
        sv_loon_12m_total: SV-loon over 12 maanden referteperiode
        ww_day_wage_override: Handmatige override WW-dagloon
        ww_month_wage_override: Handmatige override WW-maandloon

        -- Urenverlies --
        avg_hours_per_week_before_unemployment: Gemiddeld uren/week vóór werkloosheid
        hours_lost_per_week: Verloren uren per week
        hours_remaining_per_week: Resterende contracturen per week
        lost_wages_for_lost_hours: Loon over verloren uren valt ook weg

        -- Wekeneis --
        weeks_worked_last_36: Weken gewerkt in laatste 36 weken

        -- Arbeidsverleden --
        employment_years_total_relevant: Totaal relevante arbeidsjaren
        employment_years_pre2016_above10: Arbeidsjaren t/m 2015 boven de eerste 10
        employment_years_from2016_above10: Arbeidsjaren vanaf 2016 boven de eerste 10

        -- Werken naast WW --
        earnings_from_employment_month: Bruto loon uit loondienst naast WW per maand
        self_employed_hours_month: Uren als zelfstandige per maand
        other_non_insured_hours_month: Overige niet-verzekeringsplichtige uren per maand

        -- Garantiedagloon --
        use_guarantee_day_wage: Garantiedagloon toepassen
        guarantee_day_wage_override: Garantiedagloon bedrag

        -- Overrides --
        manual_end_reason: Handmatige beëindigingsreden
        manual_duration_months_override: Override WW-duur in maanden

        -- Stopregel --
        previous_month_earnings_above_threshold: Vorige maand boven 87.5%

        -- Type --
        employment_type: "nl_employee" of anders
        is_foreign_income_case: Buitenlands inkomen (geen WW)
        insured_for_unemployment: Verzekerd voor werkloosheid
        available_for_paid_work: Beschikbaar voor betaald werk

    Returns:
        dict met status, bedragen, toelichting en flags
    """
    flags = []
    toelichting = []

    # --- Stap 1: Buitenlands / niet-werknemer → geen WW ---
    if employment_type != "nl_employee" or is_foreign_income_case:
        flags.append("foreign_or_non_nl_employee_case_out_of_scope")
        return _maak_resultaat(
            status="geen_ww",
            ww_uitkering=0,
            employment_income=earnings_from_employment_month,
            grondslag_maandloon=0,
            ww_duur_maanden=0,
            ww_maand_nummer=0,
            flags=flags,
            toelichting=["Geen WW: buitenlands inkomen of geen Nederlandse werknemer."],
        )

    # --- Stap 2: Handmatig beëindigd ---
    if manual_end_reason:
        return _maak_resultaat(
            status=f"beeindigd_{manual_end_reason}",
            ww_uitkering=0,
            employment_income=earnings_from_employment_month,
            grondslag_maandloon=0,
            ww_duur_maanden=0,
            ww_maand_nummer=0,
            flags=flags,
            toelichting=[f"WW beëindigd: {manual_end_reason}."],
        )

    # --- Stap 3: Toelatingscriteria ---
    eligible, elig_flags, elig_toel = _check_toelating(
        insured_for_unemployment=insured_for_unemployment,
        weeks_worked_last_36=weeks_worked_last_36,
        avg_hours=avg_hours_per_week_before_unemployment,
        lost_hours=hours_lost_per_week,
        lost_wages=lost_wages_for_lost_hours,
        available=available_for_paid_work,
    )
    flags.extend(elig_flags)
    toelichting.extend(elig_toel)

    if not eligible:
        return _maak_resultaat(
            status="geen_ww",
            ww_uitkering=0,
            employment_income=earnings_from_employment_month,
            grondslag_maandloon=0,
            ww_duur_maanden=0,
            ww_maand_nummer=0,
            flags=flags,
            toelichting=toelichting,
        )

    # --- Stap 4: Dagloon en maandloon ---
    dagloon, maandloon, dl_flags, dl_toel = _bereken_dagloon_maandloon(
        sv_loon_12m_total=sv_loon_12m_total,
        ww_day_wage_override=ww_day_wage_override,
        ww_month_wage_override=ww_month_wage_override,
        use_guarantee_day_wage=use_guarantee_day_wage,
        guarantee_day_wage_override=guarantee_day_wage_override,
    )
    flags.extend(dl_flags)
    toelichting.extend(dl_toel)

    if maandloon <= 0:
        return _maak_resultaat(
            status="geen_ww",
            ww_uitkering=0,
            employment_income=earnings_from_employment_month,
            grondslag_maandloon=0,
            ww_duur_maanden=0,
            ww_maand_nummer=0,
            flags=flags,
            toelichting=toelichting,
        )

    # --- Stap 5: Duur ---
    if manual_duration_months_override is not None and manual_duration_months_override > 0:
        duur = manual_duration_months_override
        flags.append("manual_duration_override_used")
        toelichting.append(f"WW-duur handmatig ingesteld: {duur} maanden.")
    else:
        duur = bereken_ww_duur(
            employment_years_total_relevant=employment_years_total_relevant,
            employment_years_pre2016_above10=employment_years_pre2016_above10,
            employment_years_from2016_above10=employment_years_from2016_above10,
        )
        toelichting.append(f"WW-duur op basis van arbeidsverleden: {duur} maanden.")

    # --- Stap 6: Huidige WW-maand ---
    maand_nummer = _bepaal_ww_maand(first_unemployment_day, peildatum)

    # AOW-check
    # (niet geïmplementeerd hier — wordt in risk_scenarios afgehandeld)

    # --- Stap 7: Duur verstreken? ---
    if maand_nummer > duur:
        toelichting.append(
            f"WW-duur verstreken: maand {maand_nummer} > duur {duur} maanden."
        )
        return _maak_resultaat(
            status="beeindigd_duur",
            ww_uitkering=0,
            employment_income=earnings_from_employment_month,
            grondslag_maandloon=maandloon,
            ww_duur_maanden=duur,
            ww_maand_nummer=maand_nummer,
            flags=flags,
            toelichting=toelichting,
        )

    # --- Stap 8: WW-basis ---
    if maand_nummer <= 2:
        pct = UITKERING_CFG['percentage_maand_1_2']
        fase_label = "maand 1-2"
    else:
        pct = UITKERING_CFG['percentage_maand_3_plus']
        fase_label = "maand 3+"

    ww_basis = pct * maandloon
    toelichting.append(
        f"WW-basis ({fase_label}): {pct*100:.0f}% van WW-maandloon "
        f"({maandloon:,.2f}) = {ww_basis:,.2f}/mnd."
    )

    # --- Stap 9: Inkomsten verrekening ---
    counted_income = earnings_from_employment_month

    # Fictief inkomen voor zelfstandige werkzaamheden
    if self_employed_hours_month > 0 or other_non_insured_hours_month > 0:
        uur_ref = DAGLOON_CFG['uren_per_werkdag']
        hourly_rate = dagloon / uur_ref if uur_ref > 0 else 0
        total_zelfstandig_uren = self_employed_hours_month + other_non_insured_hours_month
        fictief_inkomen = hourly_rate * total_zelfstandig_uren
        counted_income += fictief_inkomen
        flags.append("fictitious_income_used")
        toelichting.append(
            f"Fictief inkomen: {total_zelfstandig_uren:.0f} uren x "
            f"€{hourly_rate:,.2f}/uur = €{fictief_inkomen:,.2f}/mnd "
            f"(dagloon / {uur_ref} uren/dag)."
        )

    # Verrekening
    if counted_income > 0:
        offset_pct = VERREKENING_CFG['income_offset_pct']
        income_deduction = offset_pct * counted_income
        ww_na_verrekening = max(0, ww_basis - income_deduction)
        toelichting.append(
            f"Inkomstenverrekening: {offset_pct*100:.0f}% van inkomsten "
            f"({counted_income:,.2f}) = {income_deduction:,.2f} aftrek. "
            f"WW na verrekening: {ww_na_verrekening:,.2f}/mnd."
        )
    else:
        ww_na_verrekening = ww_basis

    # --- Stap 10: Stopregel werkhervatting ---
    threshold = VERREKENING_CFG['work_stop_threshold_pct'] * maandloon

    if counted_income > threshold and previous_month_earnings_above_threshold:
        toelichting.append(
            f"WW gestopt: inkomsten ({counted_income:,.2f}) > 87,5% van WW-maandloon "
            f"({threshold:,.2f}) in 2 opeenvolgende maanden."
        )
        return _maak_resultaat(
            status="gestopt_door_werk",
            ww_uitkering=0,
            employment_income=earnings_from_employment_month,
            grondslag_maandloon=maandloon,
            ww_duur_maanden=duur,
            ww_maand_nummer=maand_nummer,
            flags=flags,
            toelichting=toelichting,
        )

    # Waarschuwing als boven threshold maar nog niet 2 maanden
    if counted_income > threshold:
        toelichting.append(
            f"Let op: inkomsten ({counted_income:,.2f}) > 87,5%-grens ({threshold:,.2f}). "
            f"Bij 2e opeenvolgende maand stopt de WW."
        )

    # --- Stap 11: Resultaat ---
    status = "ww_lopend"
    if counted_income > 0 and ww_na_verrekening > 0:
        status = "ww_aanvullend"

    return _maak_resultaat(
        status=status,
        ww_uitkering=ww_na_verrekening,
        employment_income=earnings_from_employment_month,
        grondslag_maandloon=maandloon,
        ww_duur_maanden=duur,
        ww_maand_nummer=maand_nummer,
        flags=flags,
        toelichting=toelichting,
        extra={
            "ww_basis_bruto_maand": round(ww_basis, 2),
            "counted_income_for_offset": round(counted_income, 2),
            "income_deduction": round(counted_income * VERREKENING_CFG['income_offset_pct'], 2) if counted_income > 0 else 0,
            "work_stop_threshold": round(threshold, 2),
            "above_threshold_this_month": counted_income > threshold,
        },
    )


# ============================================================
# Laag 1: Toelating
# ============================================================

def _check_toelating(
    insured_for_unemployment: bool,
    weeks_worked_last_36: int,
    avg_hours: float,
    lost_hours: float,
    lost_wages: bool,
    available: bool,
) -> tuple[bool, list, list]:
    """Check WW-toelatingsvoorwaarden."""
    flags = []
    toelichting = []
    reasons = []

    if not insured_for_unemployment:
        reasons.append("niet verzekerd voor werkloosheid")

    weken_vereist = WEKENEIS_CFG['weken_vereist']
    if weeks_worked_last_36 < weken_vereist:
        reasons.append(
            f"wekeneis niet gehaald ({weeks_worked_last_36}/{weken_vereist} weken)"
        )
        flags.append("weeks_worked_last_36_uncertain")

    # Urenverlies
    drempel = URENVERLIES_CFG['drempel_uren_per_week_hoog']
    if avg_hours >= drempel:
        min_verlies = URENVERLIES_CFG['minimum_verlies_bij_hoog']
        if lost_hours < min_verlies:
            reasons.append(
                f"onvoldoende urenverlies ({lost_hours:.1f} < {min_verlies} uur/week)"
            )
            flags.append("hours_loss_uncertain")
    else:
        min_verlies = URENVERLIES_CFG['minimum_verlies_bij_laag_fractie'] * avg_hours
        if lost_hours < min_verlies:
            reasons.append(
                f"onvoldoende urenverlies ({lost_hours:.1f} < {min_verlies:.1f} uur/week, "
                f"helft van {avg_hours:.1f})"
            )
            flags.append("hours_loss_uncertain")

    if not lost_wages:
        reasons.append("loon over verloren uren valt niet weg")

    if not available:
        reasons.append("niet beschikbaar voor betaald werk")
        flags.append("availability_for_work_not_verified")

    if reasons:
        toelichting.append(f"Geen recht op WW: {'; '.join(reasons)}.")
        return False, flags, toelichting

    toelichting.append(
        f"Recht op WW: wekeneis gehaald ({weeks_worked_last_36}/{weken_vereist}), "
        f"voldoende urenverlies ({lost_hours:.0f} uur/week), "
        f"loonverlies en beschikbaar."
    )
    return True, flags, toelichting


# ============================================================
# Laag 2: Duur
# ============================================================

def bereken_ww_duur(
    employment_years_total_relevant: int = 0,
    employment_years_pre2016_above10: int = 0,
    employment_years_from2016_above10: int = 0,
) -> int:
    """
    Bereken WW-duur in maanden op basis van arbeidsverleden.

    Eerste 10 jaren: 1 maand per jaar
    Pre-2016 boven 10: 1 maand per jaar
    Vanaf 2016 boven 10: 0,5 maand per jaar
    Minimum 3, maximum 24 maanden.
    """
    first_10 = min(10, employment_years_total_relevant)

    months = (
        first_10 * 1.0
        + employment_years_pre2016_above10 * 1.0
        + employment_years_from2016_above10 * 0.5
    )

    months = max(DUUR_CFG['minimum_maanden'], min(DUUR_CFG['maximum_maanden'], int(months)))
    return months


# ============================================================
# Laag 3: Dagloon en maandloon
# ============================================================

def _bereken_dagloon_maandloon(
    sv_loon_12m_total: float,
    ww_day_wage_override: float,
    ww_month_wage_override: float,
    use_guarantee_day_wage: bool,
    guarantee_day_wage_override: float,
) -> tuple[float, float, list, list]:
    """Bereken WW-dagloon en maandloon."""
    flags = []
    toelichting = []

    # Override maandloon
    if ww_month_wage_override and ww_month_wage_override > 0:
        maandloon = ww_month_wage_override
        dagloon = maandloon / DAGLOON_CFG['maandloon_factor']
        toelichting.append(f"WW-maandloon (override): {maandloon:,.2f}")
        return dagloon, maandloon, flags, toelichting

    # Override dagloon of afgeleid van sv-loon
    if ww_day_wage_override and ww_day_wage_override > 0:
        dagloon = ww_day_wage_override
    elif sv_loon_12m_total > 0:
        dagloon = sv_loon_12m_total / DAGLOON_CFG['werkdagen_per_jaar']
        flags.append("possible_referrteperiod_special_case")
    else:
        flags.append("salary_history_incomplete")
        toelichting.append("Geen sv-loon of dagloon opgegeven — WW niet te berekenen.")
        return 0, 0, flags, toelichting

    # Maximum dagloon
    max_dagloon = DAGLOON_CFG['maximum_dagloon']
    if dagloon > max_dagloon:
        toelichting.append(
            f"Dagloon ({dagloon:,.2f}) afgetopt op maximum ({max_dagloon:,.2f})."
        )
        dagloon = max_dagloon

    # Garantiedagloon
    if use_guarantee_day_wage and guarantee_day_wage_override and guarantee_day_wage_override > 0:
        if guarantee_day_wage_override > dagloon:
            toelichting.append(
                f"Garantiedagloon ({guarantee_day_wage_override:,.2f}) hoger dan regulier "
                f"dagloon ({dagloon:,.2f}) — garantiedagloon toegepast."
            )
            dagloon = guarantee_day_wage_override
        flags.append("guarantee_day_wage_manual_override_used")

    maandloon = dagloon * DAGLOON_CFG['maandloon_factor']
    toelichting.append(
        f"WW-dagloon: {dagloon:,.2f} (sv-loon / {DAGLOON_CFG['werkdagen_per_jaar']}). "
        f"WW-maandloon: {maandloon:,.2f} (dagloon x {DAGLOON_CFG['maandloon_factor']})."
    )

    return dagloon, maandloon, flags, toelichting


# ============================================================
# Helpers
# ============================================================

def _bepaal_ww_maand(first_unemployment_day: date, peildatum: date) -> int:
    """Bepaal het huidige WW-maandnummer (1-based)."""
    rd = relativedelta(peildatum, first_unemployment_day)
    months = rd.years * 12 + rd.months
    return max(1, months + 1)  # 1-based


def _maak_resultaat(
    status: str,
    ww_uitkering: float,
    employment_income: float,
    grondslag_maandloon: float,
    ww_duur_maanden: int,
    ww_maand_nummer: int,
    flags: list,
    toelichting: list,
    extra: dict = None,
) -> dict:
    """Bouw het resultaat-dict."""
    ww = round(ww_uitkering, 2)
    emp = round(employment_income, 2)
    totaal = round(ww + emp, 2)

    result = {
        "ww_eligible": status not in ("geen_ww",),
        "ww_status": status,
        "ww_day_wage": round(grondslag_maandloon / DAGLOON_CFG['maandloon_factor'], 2) if grondslag_maandloon > 0 else 0,
        "ww_month_wage": round(grondslag_maandloon, 2),
        "ww_duration_months": ww_duur_maanden,
        "current_ww_month_number": ww_maand_nummer,
        "ww_benefit_gross_month": ww,
        "employment_income_gross_month": emp,
        "total_gross_month": totaal,
        "total_gross_year": round(totaal * 12, 2),
        "manual_review_flags": flags,
        "toelichting": toelichting,
    }
    if extra:
        result.update(extra)
    return result


# ============================================================
# Vereenvoudigde helper voor risk_scenarios.py
# ============================================================

def bereken_ww_bruto_jaar(
    sv_loon_jaar: float,
    earnings_from_employment_month: float = 0,
    employment_years_total_relevant: int = 0,
    employment_years_pre2016_above10: int = 0,
    employment_years_from2016_above10: int = 0,
    ww_maand_nummer: int = 3,
) -> dict:
    """
    Vereenvoudigde WW-berekening voor risicoscenario's.

    Neemt aan: volledig werkloos, nl_employee, voldoet aan wekeneis.
    Gebruikt standaard peildatum zodat gevraagde maand actief is.

    Args:
        sv_loon_jaar: SV-loon per jaar (voor dagloon)
        earnings_from_employment_month: Eventueel loon naast WW
        employment_years_total_relevant: Totaal relevante arbeidsjaren
        employment_years_pre2016_above10: Arbeidsjaren t/m 2015 boven 10
        employment_years_from2016_above10: Arbeidsjaren vanaf 2016 boven 10
        ww_maand_nummer: In welke WW-maand berekenen (1-based)

    Returns:
        dict met status, ww per maand/jaar, duur, totaal
    """
    fake_start = date(2020, 1, 1)
    # Peildatum zo instellen dat we in de gewenste maand zitten
    peil = fake_start + relativedelta(months=ww_maand_nummer - 1, days=15)

    result = bereken_ww_uitkering(
        peildatum=peil,
        first_unemployment_day=fake_start,
        sv_loon_12m_total=sv_loon_jaar,
        avg_hours_per_week_before_unemployment=40.0,
        hours_lost_per_week=40.0,
        lost_wages_for_lost_hours=True,
        weeks_worked_last_36=36,
        employment_years_total_relevant=employment_years_total_relevant,
        employment_years_pre2016_above10=employment_years_pre2016_above10,
        employment_years_from2016_above10=employment_years_from2016_above10,
        earnings_from_employment_month=earnings_from_employment_month,
    )

    return {
        "ww_status": result['ww_status'],
        "ww_month_wage": result['ww_month_wage'],
        "ww_benefit_gross_month": result['ww_benefit_gross_month'],
        "ww_benefit_gross_year": round(result['ww_benefit_gross_month'] * 12, 2),
        "employment_income_gross_month": result['employment_income_gross_month'],
        "total_gross_month": result['total_gross_month'],
        "total_gross_year": result['total_gross_year'],
        "ww_duration_months": result['ww_duration_months'],
        "toelichting": result['toelichting'],
    }
