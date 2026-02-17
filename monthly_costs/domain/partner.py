"""Partner distribution module for mortgage interest deduction."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from monthly_costs.schemas.rules import TaxBracket
from monthly_costs.domain.tax_calc import calculate_marginal_rate


class DistributionMethod(str, Enum):
    """Methods for distributing mortgage interest between partners."""

    FIXED_PERCENT = "fixed_percent"
    FIXED_AMOUNT = "fixed_amount"
    OPTIMIZE = "optimize"


@dataclass(frozen=True)
class PartnerTaxInfo:
    """Tax information for a partner."""

    partner_id: str
    taxable_income: Decimal
    marginal_rate: Decimal
    is_aow: bool = False


@dataclass(frozen=True)
class DistributionResult:
    """Result of interest distribution between partners."""

    partner1_share: Decimal
    partner2_share: Decimal
    partner1_effective_rate: Decimal
    partner2_effective_rate: Decimal


def _round_currency(value: Decimal) -> Decimal:
    """Round to 2 decimal places using HALF_UP."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def distribute_interest(
    total_interest: Decimal,
    partner1: PartnerTaxInfo,
    partner2: PartnerTaxInfo | None,
    method: DistributionMethod,
    max_deduction_rate: Decimal,
    parameter: Decimal | None = None,
) -> DistributionResult:
    """
    Distribute mortgage interest between partners.
    """
    # Single applicant case
    if partner2 is None:
        effective_rate = min(partner1.marginal_rate, max_deduction_rate)
        return DistributionResult(
            partner1_share=total_interest,
            partner2_share=Decimal("0"),
            partner1_effective_rate=effective_rate,
            partner2_effective_rate=Decimal("0"),
        )

    # Calculate effective rates for both partners
    p1_effective = min(partner1.marginal_rate, max_deduction_rate)
    p2_effective = min(partner2.marginal_rate, max_deduction_rate)

    if method == DistributionMethod.FIXED_PERCENT:
        if parameter is None:
            raise ValueError("fixed_percent requires a parameter (percentage 0-100)")
        percentage = parameter / 100
        p1_share = _round_currency(total_interest * percentage)
        p2_share = total_interest - p1_share

    elif method == DistributionMethod.FIXED_AMOUNT:
        if parameter is None:
            raise ValueError("fixed_amount requires a parameter (amount)")
        p1_share = min(parameter, total_interest)
        p1_share = _round_currency(p1_share)
        p2_share = total_interest - p1_share

    elif method == DistributionMethod.OPTIMIZE:
        if p1_effective >= p2_effective:
            p1_share = total_interest
            p2_share = Decimal("0")
        else:
            p1_share = Decimal("0")
            p2_share = total_interest

    else:
        raise ValueError(f"Unknown distribution method: {method}")

    return DistributionResult(
        partner1_share=p1_share,
        partner2_share=p2_share,
        partner1_effective_rate=p1_effective,
        partner2_effective_rate=p2_effective,
    )


def calculate_partner_tax_info(
    partner_id: str,
    taxable_income: Decimal,
    age: int,
    brackets: list[TaxBracket],
    aow_age: int = 67,
) -> PartnerTaxInfo:
    """Calculate tax information for a partner."""
    is_aow = age >= aow_age
    marginal_rate = calculate_marginal_rate(taxable_income, brackets, is_aow)

    return PartnerTaxInfo(
        partner_id=partner_id,
        taxable_income=taxable_income,
        marginal_rate=marginal_rate,
        is_aow=is_aow,
    )


def calculate_total_tax_benefit(
    distribution: DistributionResult,
    total_interest: Decimal,
) -> Decimal:
    """Calculate total tax benefit from interest deduction."""
    p1_benefit = distribution.partner1_share * distribution.partner1_effective_rate
    p2_benefit = distribution.partner2_share * distribution.partner2_effective_rate

    return _round_currency(p1_benefit + p2_benefit)
