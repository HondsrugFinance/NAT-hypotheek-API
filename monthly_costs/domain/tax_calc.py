"""Tax calculation module - marginal rates and brackets."""

from decimal import Decimal

from monthly_costs.schemas.rules import TaxBracket


def calculate_marginal_rate(
    taxable_income: Decimal,
    brackets: list[TaxBracket],
    is_aow: bool = False,
) -> Decimal:
    """
    Determine the marginal tax rate based on taxable income.

    The marginal rate is the rate that applies to the last euro of income,
    which is used for calculating the benefit of deductions.
    """
    if not brackets:
        return Decimal("0")

    sorted_brackets = sorted(brackets, key=lambda b: b.lower, reverse=True)

    for bracket in sorted_brackets:
        if taxable_income > bracket.lower:
            return bracket.rate

    return sorted_brackets[-1].rate


def calculate_effective_deduction_rate(
    marginal_rate: Decimal,
    max_deduction_rate: Decimal,
) -> Decimal:
    """
    Determine the effective deduction rate for mortgage interest.

    Since 2014, the maximum deduction rate for mortgage interest has been
    gradually reduced. This function applies that limitation.
    """
    return min(marginal_rate, max_deduction_rate)


def calculate_tax_on_income(
    taxable_income: Decimal,
    brackets: list[TaxBracket],
) -> Decimal:
    """
    Calculate total income tax based on brackets.

    Useful for understanding overall tax position, though not directly
    used for monthly cost calculation.
    """
    if taxable_income <= 0:
        return Decimal("0")

    total_tax = Decimal("0")
    remaining_income = taxable_income

    sorted_brackets = sorted(brackets, key=lambda b: b.lower)

    for bracket in sorted_brackets:
        if remaining_income <= 0:
            break

        bracket_lower = bracket.lower
        bracket_upper = bracket.upper if bracket.upper is not None else Decimal("Infinity")

        if taxable_income <= bracket_lower:
            continue

        taxable_in_bracket = min(remaining_income, bracket_upper - bracket_lower)
        if bracket_lower < taxable_income:
            taxable_in_bracket = min(
                taxable_income - bracket_lower,
                bracket_upper - bracket_lower if bracket_upper != Decimal("Infinity") else remaining_income,
            )

        tax_in_bracket = taxable_in_bracket * bracket.rate
        total_tax += tax_in_bracket
        remaining_income -= taxable_in_bracket

    return total_tax
