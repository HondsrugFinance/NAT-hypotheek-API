"""Unit tests for tax calculations."""

import pytest
from decimal import Decimal

from monthly_costs.domain.tax_calc import (
    calculate_marginal_rate,
    calculate_effective_deduction_rate,
)
from monthly_costs.schemas.rules import TaxBracket


class TestMarginalRate:
    """Tests for marginal rate calculation."""

    @pytest.fixture
    def brackets_2026(self) -> list[TaxBracket]:
        """Tax brackets for 2026."""
        return [
            TaxBracket(lower=Decimal("0"), upper=Decimal("38883"), rate=Decimal("0.3575")),
            TaxBracket(lower=Decimal("38883"), upper=Decimal("78426"), rate=Decimal("0.3756")),
            TaxBracket(lower=Decimal("78426"), upper=None, rate=Decimal("0.495")),
        ]

    def test_marginal_rate_first_bracket(self, brackets_2026):
        """Test income in first bracket."""
        result = calculate_marginal_rate(Decimal("30000"), brackets_2026)
        assert result == Decimal("0.3575")

    def test_marginal_rate_second_bracket(self, brackets_2026):
        """Test income in second bracket."""
        result = calculate_marginal_rate(Decimal("60000"), brackets_2026)
        assert result == Decimal("0.3756")

    def test_marginal_rate_third_bracket(self, brackets_2026):
        """Test income in third bracket."""
        result = calculate_marginal_rate(Decimal("100000"), brackets_2026)
        assert result == Decimal("0.495")

    def test_marginal_rate_exactly_on_boundary(self, brackets_2026):
        """Test income exactly on bracket boundary."""
        # Income of 38883 is still in first bracket
        result = calculate_marginal_rate(Decimal("38883"), brackets_2026)
        assert result == Decimal("0.3575")

        # Income of 38884 is in second bracket
        result = calculate_marginal_rate(Decimal("38884"), brackets_2026)
        assert result == Decimal("0.3756")

    def test_marginal_rate_zero_income(self, brackets_2026):
        """Test zero income."""
        result = calculate_marginal_rate(Decimal("0"), brackets_2026)
        assert result == Decimal("0.3575")  # Lowest bracket

    def test_marginal_rate_empty_brackets(self):
        """Test with empty brackets."""
        result = calculate_marginal_rate(Decimal("50000"), [])
        assert result == Decimal("0")


class TestEffectiveDeductionRate:
    """Tests for effective deduction rate calculation."""

    def test_rate_below_max(self):
        """Test when marginal rate is below max."""
        result = calculate_effective_deduction_rate(
            marginal_rate=Decimal("0.3575"),
            max_deduction_rate=Decimal("0.3756"),
        )
        assert result == Decimal("0.3575")

    def test_rate_equals_max(self):
        """Test when marginal rate equals max."""
        result = calculate_effective_deduction_rate(
            marginal_rate=Decimal("0.3756"),
            max_deduction_rate=Decimal("0.3756"),
        )
        assert result == Decimal("0.3756")

    def test_rate_above_max(self):
        """Test when marginal rate is above max (capped)."""
        result = calculate_effective_deduction_rate(
            marginal_rate=Decimal("0.495"),
            max_deduction_rate=Decimal("0.3756"),
        )
        assert result == Decimal("0.3756")
