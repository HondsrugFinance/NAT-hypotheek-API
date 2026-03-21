"""Status-derivatie voor risicoscenario's.

Bepaalt per scenario de status (affordable/resolved/attention/shortfall)
en het bijbehorende adviestype.  Logica is overgenomen uit de Lovable
frontend (src/report/builders.ts).

Buffer-logica: als de klant voldoende beschikbaar vermogen (spaargeld +
beleggingen - inbreng) heeft om een tekort op te vangen, wordt de status
'resolved' — vergelijkbaar met een bestaande ORV bij overlijden.
"""

from __future__ import annotations

SHORTFALL_THRESHOLD_PCT = 5  # % van hypotheek → grens limited vs material


def derive_death_status(
    *,
    has_partner: bool,
    has_orv: bool = False,
    customer_rejected_orv: bool = False,
    per_partner_shortfall: list[bool] | None = None,
    buffer: float = 0,
    shortfall_amounts: list[float] | None = None,
) -> dict:
    """Overlijden status-derivatie.

    Args:
        buffer: Beschikbaar vermogen (spaargeld + beleggingen - inbreng)
        shortfall_amounts: Tekort per partner in EUR (parallel aan per_partner_shortfall)
    """
    if not has_partner:
        return {"status": "affordable", "advice_type": "no_action"}

    # Datagedreven: als geen enkel scenario een tekort oplevert
    if per_partner_shortfall is not None and not any(per_partner_shortfall):
        return {"status": "affordable", "advice_type": "no_action"}

    # Buffer dekt alle tekorten → resolved
    if buffer > 0 and shortfall_amounts:
        max_tekort = max((a for a in shortfall_amounts if a > 0), default=0)
        if max_tekort > 0 and buffer >= max_tekort:
            return {"status": "resolved", "advice_type": "no_action"}

    if has_orv:
        if per_partner_shortfall is not None:
            # ORV niet toereikend — adviseer aanvullende
            return {"status": "attention", "advice_type": "consider_solution_existing"}
        return {"status": "resolved", "advice_type": "no_action"}

    if customer_rejected_orv:
        return {"status": "attention", "advice_type": "awareness_only"}

    return {"status": "attention", "advice_type": "consider_solution"}


def derive_retirement_status(
    *,
    aow_scenarios: list[dict],
    hypotheek: float,
    buffer: float = 0,
) -> dict:
    """Pensioen status-derivatie op basis van AOW-scenario's.

    Vergelijkt de RESTSCHULD op AOW-moment (niet het originele hypotheekbedrag)
    met de maximale hypotheek. Bij aflossende hypotheken is de restschuld op
    AOW-leeftijd lager dan het originele bedrag.

    buffer: beschikbaar vermogen dat ingezet kan worden om tekort op te vangen.
    """
    if not aow_scenarios:
        return {"status": "affordable", "advice_type": "no_action"}

    shortfalls = []
    for sc in aow_scenarios:
        max_hyp = max(
            sc.get("max_hypotheek_annuitair", 0),
            sc.get("max_hypotheek_niet_annuitair", 0),
        )
        # Vergelijk met restschuld op AOW-moment, niet het originele bedrag
        schuld = sc.get("restschuld_op_peildatum", hypotheek)
        max_hyp = max(0, max_hyp)
        if schuld > 0 and schuld > max_hyp:
            tekort = schuld - max_hyp
            # Buffer kan tekort opvangen
            if buffer >= tekort:
                continue  # Dit scenario is gedekt door buffer
            tekort_pct = (tekort / schuld * 100) if schuld > 0 else 0
            shortfalls.append({
                "tekort": tekort,
                "tekort_pct": tekort_pct,
                "severity": "limited" if tekort_pct <= SHORTFALL_THRESHOLD_PCT else "material",
            })

    if not shortfalls:
        # Alle tekorten gedekt (door buffer of gewoon geen tekort)
        if buffer > 0 and aow_scenarios:
            # Check of er überhaupt tekorten WAREN die door buffer gedekt zijn
            any_covered = any(
                sc.get("restschuld_op_peildatum", hypotheek) >
                max(sc.get("max_hypotheek_annuitair", 0),
                    sc.get("max_hypotheek_niet_annuitair", 0))
                for sc in aow_scenarios
            )
            if any_covered:
                return {"status": "resolved", "advice_type": "no_action"}
        return {"status": "affordable", "advice_type": "no_action"}

    all_limited = all(s["severity"] == "limited" for s in shortfalls)
    if all_limited:
        return {"status": "attention", "advice_type": "awareness_only"}

    return {"status": "shortfall", "advice_type": "advise_extra_repayment"}


def derive_betaalbaarheid_status(
    *,
    chart_jaren: list[dict],
    buffer: float = 0,
) -> dict:
    """Betaalbaarheid status op basis van 30-jaar tijdlijn.

    Check: is max_hypotheek >= restschuld in alle jaren?
    Buffer: als het maximale tekort gedekt wordt door spaargeld (extra aflossing) → afgedekt.
    """
    if not chart_jaren:
        return {"status": "affordable", "advice_type": "no_action"}

    max_tekort = 0
    for jr in chart_jaren:
        restschuld = jr.get("restschuld", 0)
        max_hyp = jr.get("max_hypotheek", 0)
        if restschuld > max_hyp:
            tekort = restschuld - max_hyp
            max_tekort = max(max_tekort, tekort)

    if max_tekort == 0:
        return {"status": "affordable", "advice_type": "no_action"}

    # Buffer kan het maximale tekort dekken → extra aflossing lost het op
    if buffer >= max_tekort:
        return {"status": "resolved", "advice_type": "no_action"}

    return {"status": "attention", "advice_type": "consider_solution"}


def derive_disability_status(
    *,
    has_aov: bool = False,
    per_partner_shortfall: list[bool] | None = None,
    buffer: float = 0,
    shortfall_amounts: list[float] | None = None,
) -> dict:
    """Arbeidsongeschiktheid status-derivatie.

    Args:
        buffer: Beschikbaar vermogen (spaargeld + beleggingen - inbreng)
        shortfall_amounts: Tekort per partner in EUR
    """
    # Datagedreven: als geen enkel scenario een tekort oplevert
    if per_partner_shortfall is not None and not any(per_partner_shortfall):
        return {"status": "affordable", "advice_type": "no_action"}

    # Buffer dekt alle tekorten → resolved
    if buffer > 0 and shortfall_amounts:
        max_tekort = max((a for a in shortfall_amounts if a > 0), default=0)
        if max_tekort > 0 and buffer >= max_tekort:
            return {"status": "resolved", "advice_type": "no_action"}

    if has_aov:
        if per_partner_shortfall is not None:
            # AOV niet toereikend — adviseer aanvullende
            return {"status": "attention", "advice_type": "refer_to_specialist_existing"}
        return {"status": "resolved", "advice_type": "no_action"}

    return {"status": "attention", "advice_type": "refer_to_specialist"}


def derive_unemployment_status(
    *,
    buffer_months: float | None = None,
    per_partner_shortfall: list[bool] | None = None,
    buffer: float = 0,
    shortfall_amounts: list[float] | None = None,
) -> dict:
    """Werkloosheid status-derivatie op basis van financiële buffer.

    Buffer = spaargeld / netto maandlast.
    ≥ 6 maanden = affordable, ≥ 3 = attention, < 3 of onbekend = attention.
    """
    # Datagedreven: als geen enkel scenario een tekort oplevert
    if per_partner_shortfall is not None and not any(per_partner_shortfall):
        return {"status": "affordable", "advice_type": "no_action"}

    # Buffer dekt alle tekorten → resolved
    if buffer > 0 and shortfall_amounts:
        max_tekort = max((a for a in shortfall_amounts if a > 0), default=0)
        if max_tekort > 0 and buffer >= max_tekort:
            return {"status": "resolved", "advice_type": "no_action"}

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
    buffer: float = 0,
) -> dict:
    """Relatiebeëindiging status-derivatie.

    Returns dict met overall_status + per-persoon status.
    Buffer kan ingezet worden om tekort per persoon te dekken.
    """
    aanvrager_ok = (max_hyp_aanvrager + buffer) >= hypotheek
    partner_ok = (max_hyp_partner + buffer) >= hypotheek

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
