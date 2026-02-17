"""Wet Hillen calculation module."""

from decimal import ROUND_HALF_UP, Decimal

from monthly_costs.schemas.rules import HillenConfig


def _round_currency(value: Decimal) -> Decimal:
    """Round to 2 decimal places using HALF_UP."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_hillen_deduction(
    ewf: Decimal,
    deductible_interest: Decimal,
    hillen_config: HillenConfig,
) -> Decimal:
    """
    Calculate the Hillen deduction (aftrek wegens geen of geringe eigenwoningschuld).

    The Hillen arrangement applies when the deductible mortgage interest is less
    than the eigenwoningforfait (EWF). Since 2019, the Hillen deduction is being
    phased out gradually.
    """
    if not hillen_config.enabled:
        return Decimal("0")

    if deductible_interest >= ewf:
        return Decimal("0")

    difference = ewf - deductible_interest
    hillen_deduction = difference * hillen_config.reduction_percentage

    return _round_currency(hillen_deduction)


def calculate_net_ewf_addition(
    ewf: Decimal,
    deductible_interest: Decimal,
    hillen_config: HillenConfig,
) -> Decimal:
    """
    Calculate the net EWF addition after Hillen deduction.

    This is the amount that will be added to taxable income.
    """
    hillen = calculate_hillen_deduction(ewf, deductible_interest, hillen_config)
    net_ewf = ewf - hillen
    return max(Decimal("0"), net_ewf)
