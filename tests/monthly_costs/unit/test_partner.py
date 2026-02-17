"""Unit tests for partner distribution."""

import pytest
from decimal import Decimal

from monthly_costs.domain.partner import (
    DistributionMethod,
    PartnerTaxInfo,
    distribute_interest,
)


class TestDistributeInterest:
    """Tests for interest distribution between partners."""

    @pytest.fixture
    def partner1(self) -> PartnerTaxInfo:
        """Partner 1 with high income."""
        return PartnerTaxInfo(
            partner_id="partner1",
            taxable_income=Decimal("90000"),
            marginal_rate=Decimal("0.495"),
        )

    @pytest.fixture
    def partner2(self) -> PartnerTaxInfo:
        """Partner 2 with lower income."""
        return PartnerTaxInfo(
            partner_id="partner2",
            taxable_income=Decimal("45000"),
            marginal_rate=Decimal("0.3756"),
        )

    def test_single_partner(self, partner1):
        """Test distribution with single partner."""
        result = distribute_interest(
            total_interest=Decimal("12000"),
            partner1=partner1,
            partner2=None,
            method=DistributionMethod.FIXED_PERCENT,
            max_deduction_rate=Decimal("0.3756"),
            parameter=Decimal("100"),
        )

        assert result.partner1_share == Decimal("12000")
        assert result.partner2_share == Decimal("0")
        # Effective rate should be capped at max
        assert result.partner1_effective_rate == Decimal("0.3756")

    def test_fixed_percent_50_50(self, partner1, partner2):
        """Test 50/50 fixed percentage distribution."""
        result = distribute_interest(
            total_interest=Decimal("12000"),
            partner1=partner1,
            partner2=partner2,
            method=DistributionMethod.FIXED_PERCENT,
            max_deduction_rate=Decimal("0.3756"),
            parameter=Decimal("50"),
        )

        assert result.partner1_share == Decimal("6000.00")
        assert result.partner2_share == Decimal("6000.00")

    def test_fixed_percent_70_30(self, partner1, partner2):
        """Test 70/30 fixed percentage distribution."""
        result = distribute_interest(
            total_interest=Decimal("10000"),
            partner1=partner1,
            partner2=partner2,
            method=DistributionMethod.FIXED_PERCENT,
            max_deduction_rate=Decimal("0.3756"),
            parameter=Decimal("70"),
        )

        assert result.partner1_share == Decimal("7000.00")
        assert result.partner2_share == Decimal("3000.00")

    def test_fixed_amount(self, partner1, partner2):
        """Test fixed amount distribution."""
        result = distribute_interest(
            total_interest=Decimal("12000"),
            partner1=partner1,
            partner2=partner2,
            method=DistributionMethod.FIXED_AMOUNT,
            max_deduction_rate=Decimal("0.3756"),
            parameter=Decimal("8000"),
        )

        assert result.partner1_share == Decimal("8000.00")
        assert result.partner2_share == Decimal("4000.00")

    def test_fixed_amount_exceeds_total(self, partner1, partner2):
        """Test fixed amount exceeding total interest."""
        result = distribute_interest(
            total_interest=Decimal("5000"),
            partner1=partner1,
            partner2=partner2,
            method=DistributionMethod.FIXED_AMOUNT,
            max_deduction_rate=Decimal("0.3756"),
            parameter=Decimal("8000"),
        )

        # Should cap at total
        assert result.partner1_share == Decimal("5000.00")
        assert result.partner2_share == Decimal("0")

    def test_optimize_higher_rate_partner1(self, partner1, partner2):
        """Test optimize assigns all to higher rate partner."""
        result = distribute_interest(
            total_interest=Decimal("12000"),
            partner1=partner1,
            partner2=partner2,
            method=DistributionMethod.OPTIMIZE,
            max_deduction_rate=Decimal("0.3756"),
        )

        # Both partners are capped at 0.3756, so partner1 gets all
        # (when equal, first partner wins)
        assert result.partner1_share == Decimal("12000")
        assert result.partner2_share == Decimal("0")

    def test_optimize_higher_rate_partner2(self):
        """Test optimize when partner2 has higher effective rate."""
        partner1 = PartnerTaxInfo(
            partner_id="p1",
            taxable_income=Decimal("30000"),
            marginal_rate=Decimal("0.3575"),
        )
        partner2 = PartnerTaxInfo(
            partner_id="p2",
            taxable_income=Decimal("60000"),
            marginal_rate=Decimal("0.3756"),
        )

        result = distribute_interest(
            total_interest=Decimal("12000"),
            partner1=partner1,
            partner2=partner2,
            method=DistributionMethod.OPTIMIZE,
            max_deduction_rate=Decimal("0.3756"),
        )

        # Partner2 has higher rate (0.3756 > 0.3575)
        assert result.partner1_share == Decimal("0")
        assert result.partner2_share == Decimal("12000")

    def test_effective_rate_capped(self, partner1, partner2):
        """Test effective rate is capped at max deduction rate."""
        result = distribute_interest(
            total_interest=Decimal("12000"),
            partner1=partner1,
            partner2=partner2,
            method=DistributionMethod.FIXED_PERCENT,
            max_deduction_rate=Decimal("0.3756"),
            parameter=Decimal("50"),
        )

        # Partner1 has 0.495 marginal but capped at 0.3756
        assert result.partner1_effective_rate == Decimal("0.3756")
        # Partner2 has 0.3756 marginal, equal to max
        assert result.partner2_effective_rate == Decimal("0.3756")
