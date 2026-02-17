"""Eigenwoningforfait (EWF) calculation module."""

from decimal import ROUND_HALF_UP, Decimal

from monthly_costs.schemas.rules import EWFBand
from monthly_costs.exceptions import WOZValueOutOfRangeError


def _round_currency(value: Decimal) -> Decimal:
    """Round to 2 decimal places using HALF_UP."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_ewf(
    woz_value: Decimal,
    ewf_table: list[EWFBand],
    fiscal_year: int,
) -> Decimal:
    """
    Calculate the eigenwoningforfait (deemed rental income) based on WOZ value.

    The EWF is a percentage of the WOZ value that is added to taxable income.
    For high-value properties (> 1.35M in 2026), there's a "villa tax" with
    a fixed amount plus a percentage on the excess.
    """
    if woz_value < 0:
        raise WOZValueOutOfRangeError(woz_value=float(woz_value), year=fiscal_year)

    if not ewf_table:
        raise WOZValueOutOfRangeError(woz_value=float(woz_value), year=fiscal_year)

    sorted_bands = sorted(ewf_table, key=lambda b: b.lower)

    for band in sorted_bands:
        upper = band.upper if band.upper is not None else Decimal("Infinity")

        if band.lower <= woz_value <= upper:
            # Villa tax band (fixed amount + excess percentage)
            if band.fixed_amount is not None and band.excess_percentage is not None:
                threshold = band.threshold if band.threshold is not None else band.lower
                excess = max(Decimal("0"), woz_value - threshold)
                ewf = band.fixed_amount + (excess * band.excess_percentage)
                return _round_currency(ewf)

            # Standard percentage band
            if band.percentage is not None:
                ewf = woz_value * band.percentage
                return _round_currency(ewf)

            # Zero percentage (exempt band)
            return Decimal("0")

    raise WOZValueOutOfRangeError(woz_value=float(woz_value), year=fiscal_year)
