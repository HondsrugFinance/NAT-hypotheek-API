"""Unit tests for loan calculations."""

import pytest
from decimal import Decimal

from monthly_costs.domain.loan_calc import (
    AnnuityCalculator,
    LinearCalculator,
    InterestOnlyCalculator,
    get_calculator,
)


class TestAnnuityCalculator:
    """Tests for annuity loan calculator."""

    def test_standard_annuity_first_month(self):
        """Test standard annuity calculation for first month."""
        calc = AnnuityCalculator()
        result = calc.calculate_month(
            principal=Decimal("300000"),
            annual_rate=Decimal("0.04"),  # 4%
            term_years=30,
            month_number=1,
        )

        # Expected annuity is approximately 1432.25 per month
        assert Decimal("1430") < result.gross_payment < Decimal("1435")
        # First month interest = 300000 * 0.04 / 12 = 1000
        assert result.interest_payment == Decimal("1000.00")
        # Principal = annuity - interest
        assert result.principal_payment == result.gross_payment - result.interest_payment
        # Remaining principal should be less than original
        assert result.remaining_principal < Decimal("300000")

    def test_annuity_zero_interest(self):
        """Test annuity with 0% interest rate."""
        calc = AnnuityCalculator()
        result = calc.calculate_month(
            principal=Decimal("120000"),
            annual_rate=Decimal("0"),
            term_years=10,
            month_number=1,
        )

        # With 0% interest, payment = principal / months
        assert result.gross_payment == Decimal("1000.00")
        assert result.interest_payment == Decimal("0")
        assert result.principal_payment == Decimal("1000.00")

    def test_annuity_interest_decreases_over_time(self):
        """Test that interest component decreases over loan lifetime."""
        calc = AnnuityCalculator()

        result_month_1 = calc.calculate_month(
            principal=Decimal("200000"),
            annual_rate=Decimal("0.05"),
            term_years=20,
            month_number=1,
        )

        result_month_60 = calc.calculate_month(
            principal=Decimal("200000"),
            annual_rate=Decimal("0.05"),
            term_years=20,
            month_number=60,
        )

        # Interest should decrease over time
        assert result_month_60.interest_payment < result_month_1.interest_payment
        # Principal payment should increase
        assert result_month_60.principal_payment > result_month_1.principal_payment
        # Total payment stays constant (annuity)
        assert result_month_1.gross_payment == result_month_60.gross_payment


class TestLinearCalculator:
    """Tests for linear loan calculator."""

    def test_linear_first_month(self):
        """Test linear calculation for first month."""
        calc = LinearCalculator()
        result = calc.calculate_month(
            principal=Decimal("240000"),
            annual_rate=Decimal("0.04"),
            term_years=20,
            month_number=1,
        )

        # Principal payment = 240000 / 240 months = 1000
        assert result.principal_payment == Decimal("1000.00")
        # Interest = 240000 * 0.04 / 12 = 800
        assert result.interest_payment == Decimal("800.00")
        # Total = 1800
        assert result.gross_payment == Decimal("1800.00")

    def test_linear_payment_decreases(self):
        """Test that total payment decreases for linear loan."""
        calc = LinearCalculator()

        result_month_1 = calc.calculate_month(
            principal=Decimal("240000"),
            annual_rate=Decimal("0.04"),
            term_years=20,
            month_number=1,
        )

        result_month_120 = calc.calculate_month(
            principal=Decimal("240000"),
            annual_rate=Decimal("0.04"),
            term_years=20,
            month_number=120,
        )

        # Principal stays the same
        assert result_month_120.principal_payment == result_month_1.principal_payment
        # Interest decreases
        assert result_month_120.interest_payment < result_month_1.interest_payment
        # Total payment decreases
        assert result_month_120.gross_payment < result_month_1.gross_payment


class TestInterestOnlyCalculator:
    """Tests for interest-only loan calculator."""

    def test_interest_only_constant(self):
        """Test interest-only payment is constant."""
        calc = InterestOnlyCalculator()

        for month in [1, 60, 120, 180]:
            result = calc.calculate_month(
                principal=Decimal("150000"),
                annual_rate=Decimal("0.045"),
                term_years=30,
                month_number=month,
            )

            # No principal payment
            assert result.principal_payment == Decimal("0")
            # Interest = 150000 * 0.045 / 12 = 562.50
            assert result.interest_payment == Decimal("562.50")
            # Principal unchanged
            assert result.remaining_principal == Decimal("150000")


class TestGetCalculator:
    """Tests for calculator factory."""

    def test_get_annuity_calculator(self):
        """Test getting annuity calculator."""
        calc = get_calculator("annuity")
        assert isinstance(calc, AnnuityCalculator)

    def test_get_linear_calculator(self):
        """Test getting linear calculator."""
        calc = get_calculator("linear")
        assert isinstance(calc, LinearCalculator)

    def test_get_interest_only_calculator(self):
        """Test getting interest-only calculator."""
        calc = get_calculator("interest_only")
        assert isinstance(calc, InterestOnlyCalculator)

    def test_invalid_loan_type(self):
        """Test that invalid loan type raises error."""
        with pytest.raises(ValueError, match="Unknown loan type"):
            get_calculator("invalid")
