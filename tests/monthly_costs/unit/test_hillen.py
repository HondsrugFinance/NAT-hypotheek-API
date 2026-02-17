"""Unit tests for Wet Hillen calculation."""

import pytest
from decimal import Decimal

from monthly_costs.domain.hillen import calculate_hillen_deduction, calculate_net_ewf_addition
from monthly_costs.schemas.rules import HillenConfig


class TestHillenCalculation:
    """Tests for Hillen deduction calculation."""

    @pytest.fixture
    def hillen_config(self) -> HillenConfig:
        """Standard Hillen config for 2026."""
        return HillenConfig(enabled=True, reduction_percentage=Decimal("0.71867"))

    @pytest.fixture
    def hillen_disabled(self) -> HillenConfig:
        """Disabled Hillen config."""
        return HillenConfig(enabled=False, reduction_percentage=Decimal("0"))

    def test_hillen_no_benefit_high_interest(self, hillen_config):
        """Test no Hillen when interest > EWF."""
        result = calculate_hillen_deduction(
            ewf=Decimal("1400"),
            deductible_interest=Decimal("12000"),
            hillen_config=hillen_config,
        )
        assert result == Decimal("0")

    def test_hillen_no_benefit_equal(self, hillen_config):
        """Test no Hillen when interest == EWF."""
        result = calculate_hillen_deduction(
            ewf=Decimal("1400"),
            deductible_interest=Decimal("1400"),
            hillen_config=hillen_config,
        )
        assert result == Decimal("0")

    def test_hillen_full_benefit_no_mortgage(self, hillen_config):
        """Test maximum Hillen when no mortgage."""
        result = calculate_hillen_deduction(
            ewf=Decimal("1400"),
            deductible_interest=Decimal("0"),
            hillen_config=hillen_config,
        )
        # 1400 * 0.71867 = 1006.14
        assert result == Decimal("1006.14")

    def test_hillen_partial_benefit(self, hillen_config):
        """Test partial Hillen benefit."""
        result = calculate_hillen_deduction(
            ewf=Decimal("1200"),
            deductible_interest=Decimal("1000"),
            hillen_config=hillen_config,
        )
        # Difference = 200, aftrek = 200 * 0.71867 = 143.73
        assert result == Decimal("143.73")

    def test_hillen_disabled(self, hillen_disabled):
        """Test Hillen when disabled."""
        result = calculate_hillen_deduction(
            ewf=Decimal("1400"),
            deductible_interest=Decimal("0"),
            hillen_config=hillen_disabled,
        )
        assert result == Decimal("0")


class TestNetEWFAddition:
    """Tests for net EWF addition calculation."""

    @pytest.fixture
    def hillen_config(self) -> HillenConfig:
        """Standard Hillen config for 2026."""
        return HillenConfig(enabled=True, reduction_percentage=Decimal("0.71867"))

    def test_net_ewf_with_high_interest(self, hillen_config):
        """Test net EWF when interest > EWF (no Hillen)."""
        result = calculate_net_ewf_addition(
            ewf=Decimal("1400"),
            deductible_interest=Decimal("12000"),
            hillen_config=hillen_config,
        )
        # No Hillen, full EWF
        assert result == Decimal("1400")

    def test_net_ewf_with_no_mortgage(self, hillen_config):
        """Test net EWF when no mortgage (max Hillen)."""
        result = calculate_net_ewf_addition(
            ewf=Decimal("1400"),
            deductible_interest=Decimal("0"),
            hillen_config=hillen_config,
        )
        # 1400 - (1400 * 0.71867) = 1400 - 1006.14 = 393.86
        assert result == Decimal("393.86")

    def test_net_ewf_partial(self, hillen_config):
        """Test net EWF with partial Hillen."""
        result = calculate_net_ewf_addition(
            ewf=Decimal("1200"),
            deductible_interest=Decimal("1000"),
            hillen_config=hillen_config,
        )
        # EWF 1200 - Hillen 143.73 = 1056.27
        assert result == Decimal("1056.27")
