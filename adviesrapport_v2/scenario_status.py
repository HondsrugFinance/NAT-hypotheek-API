"""Status-derivatie voor risicoscenario's.

Bepaalt per scenario de status (affordable/resolved/attention/shortfall)
en het bijbehorende adviestype.  Logica is overgenomen uit de Lovable
frontend (src/report/builders.ts).
"""

from __future__ import annotations

SHORTFALL_THRESHOLD_PCT = 5  # % van hypotheek → grens limited vs material


def derive_death_status(
    *,
    has_partner: bool,
    has_orv: bool = False,
    customer_rejected_orv: bool = False,
) -> dict:
    """Overlijden status-derivatie."""
    if not has_partner:
        return {"status": "affordable", "advice_type": "no_action"}

    if has_orv:
        return {"status": "resolved", "advice_type": "no_action"}

    if customer_rejected_orv:
        return {"status": "attention", "advice_type": "awareness_only"}

    return {"status": "attention", "advice_type": "consider_solution"}


def derive_retirement_status(
    *,
    aow_scenarios: list[dict],
    hypotheek: float,
) -> dict:
    """Pensioen status-derivatie op basis van AOW-scenario's.

    Gebruikt de 5%-drempel: tekort ≤ 5% = limited (attention),
    tekort > 5% = material (shortfall).
    """
    if not aow_scenarios:
        return {"status": "affordable", "advice_type": "no_action"}

    shortfalls = []
    for sc in aow_scenarios:
        max_hyp = sc.get("max_hypotheek_annuitair", 0)
        if hypotheek > max_hyp > 0:
            tekort = hypotheek - max_hyp
            tekort_pct = (tekort / hypotheek * 100) if hypotheek > 0 else 0
            shortfalls.append({
                "tekort": tekort,
                "tekort_pct": tekort_pct,
                "severity": "limited" if tekort_pct <= SHORTFALL_THRESHOLD_PCT else "material",
            })

    if not shortfalls:
        return {"status": "affordable", "advice_type": "no_action"}

    all_limited = all(s["severity"] == "limited" for s in shortfalls)
    if all_limited:
        return {"status": "attention", "advice_type": "awareness_only"}

    return {"status": "shortfall", "advice_type": "advise_extra_repayment"}


def derive_disability_status(*, has_aov: bool = False) -> dict:
    """Arbeidsongeschiktheid status-derivatie."""
    if has_aov:
        return {"status": "resolved", "advice_type": "no_action"}

    return {"status": "attention", "advice_type": "refer_to_specialist"}


def derive_unemployment_status(*, buffer_months: float | None = None) -> dict:
    """Werkloosheid status-derivatie op basis van financiële buffer.

    Buffer = spaargeld / netto maandlast.
    ≥ 6 maanden = affordable, ≥ 3 = attention, < 3 of onbekend = attention.
    """
    if buffer_months is not None and buffer_months >= 6:
        return {"status": "affordable", "advice_type": "no_action"}

    if buffer_months is not None and buffer_months >= 3:
        return {"status": "attention", "advice_type": "consider_solution"}

    # < 3 maanden of onbekend
    return {"status": "attention", "advice_type": "consider_solution"}


def derive_relationship_status(
    *,
    max_hyp_aanvrager: float,
    max_hyp_partner: float,
    hypotheek: float,
) -> dict:
    """Relatiebeëindiging status-derivatie.

    Returns dict met overall_status + per-persoon status.
    """
    aanvrager_ok = max_hyp_aanvrager >= hypotheek
    partner_ok = max_hyp_partner >= hypotheek

    def _person_status(can_afford: bool) -> str:
        if can_afford:
            return "affordable"
        return "shortfall"

    if aanvrager_ok and partner_ok:
        overall = "affordable_for_both"
    elif aanvrager_ok or partner_ok:
        overall = "affordable_for_one"
    else:
        overall = "affordable_for_none"

    return {
        "overall_status": overall,
        "applicant_status": _person_status(aanvrager_ok),
        "partner_status": _person_status(partner_ok),
    }
