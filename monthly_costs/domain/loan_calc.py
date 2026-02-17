"""Loan calculation module - annuity, linear, interest-only."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol


@dataclass(frozen=True)
class MonthlyPayment:
    """Result of a monthly payment calculation."""

    interest_payment: Decimal
    principal_payment: Decimal
    gross_payment: Decimal
    remaining_principal: Decimal


class LoanCalculator(Protocol):
    """Protocol for loan calculators."""

    def calculate_month(
        self,
        principal: Decimal,
        annual_rate: Decimal,
        term_years: int,
        month_number: int,
    ) -> MonthlyPayment:
        """Calculate payment for a specific month."""
        ...


def _round_currency(value: Decimal) -> Decimal:
    """Round to 2 decimal places using HALF_UP."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class AnnuityCalculator:
    """Annuity loan calculator - fixed monthly payment."""

    def calculate_month(
        self,
        principal: Decimal,
        annual_rate: Decimal,
        term_years: int,
        month_number: int,
    ) -> MonthlyPayment:
        """Calculate annuity payment for a specific month."""
        n = term_years * 12
        r = annual_rate / 12

        # Calculate annuity (fixed monthly payment)
        if r == 0:
            annuity = principal / n
        else:
            # A = P * (r * (1+r)^n) / ((1+r)^n - 1)
            factor = (1 + r) ** n
            annuity = principal * (r * factor) / (factor - 1)

        # Calculate remaining principal at start of this month
        if month_number == 1:
            remaining_start = principal
        else:
            remaining_start = self._calculate_remaining(principal, r, annuity, month_number - 1)

        # Ensure we don't go negative
        remaining_start = max(Decimal("0"), remaining_start)

        interest = _round_currency(remaining_start * r)
        principal_payment = _round_currency(annuity - interest)
        remaining_end = remaining_start - principal_payment

        return MonthlyPayment(
            interest_payment=interest,
            principal_payment=principal_payment,
            gross_payment=_round_currency(annuity),
            remaining_principal=max(Decimal("0"), remaining_end),
        )

    def _calculate_remaining(
        self,
        principal: Decimal,
        monthly_rate: Decimal,
        annuity: Decimal,
        after_months: int,
    ) -> Decimal:
        """Calculate remaining principal after X months using closed-form formula."""
        if monthly_rate == 0:
            return principal - (annuity * after_months)

        # Closed-form: B_n = P(1+r)^n - A*((1+r)^n - 1)/r
        factor = (1 + monthly_rate) ** after_months
        return principal * factor - annuity * (factor - 1) / monthly_rate


class LinearCalculator:
    """Linear loan calculator - fixed principal payment, decreasing total."""

    def calculate_month(
        self,
        principal: Decimal,
        annual_rate: Decimal,
        term_years: int,
        month_number: int,
    ) -> MonthlyPayment:
        """Calculate linear payment for a specific month."""
        n = term_years * 12
        monthly_principal = _round_currency(principal / n)

        # Remaining principal at start of this month
        remaining_start = principal - (monthly_principal * (month_number - 1))
        remaining_start = max(Decimal("0"), remaining_start)

        interest = _round_currency(remaining_start * annual_rate / 12)
        remaining_end = remaining_start - monthly_principal

        return MonthlyPayment(
            interest_payment=interest,
            principal_payment=monthly_principal,
            gross_payment=interest + monthly_principal,
            remaining_principal=max(Decimal("0"), remaining_end),
        )


class InterestOnlyCalculator:
    """Interest-only loan calculator - no principal repayment."""

    def calculate_month(
        self,
        principal: Decimal,
        annual_rate: Decimal,
        term_years: int,
        month_number: int,
    ) -> MonthlyPayment:
        """Calculate interest-only payment."""
        interest = _round_currency(principal * annual_rate / 12)

        return MonthlyPayment(
            interest_payment=interest,
            principal_payment=Decimal("0"),
            gross_payment=interest,
            remaining_principal=principal,
        )


def get_calculator(loan_type: str) -> LoanCalculator:
    """Factory function to get the appropriate calculator."""
    calculators: dict[str, LoanCalculator] = {
        "annuity": AnnuityCalculator(),
        "linear": LinearCalculator(),
        "interest_only": InterestOnlyCalculator(),
    }
    if loan_type not in calculators:
        raise ValueError(f"Unknown loan type: {loan_type}. Valid types: {list(calculators.keys())}")
    return calculators[loan_type]
