"""Unit tests for eigenwoningforfait (EWF) calculation."""

import pytest
from decimal import Decimal

from monthly_costs.domain.ewf import calculate_ewf
from monthly_costs.schemas.rules import EWFBand
from monthly_costs.exceptions import WOZValueOutOfRangeError


class TestEWFCalculation:
    """Tests for EWF calculation."""

    @pytest.fixture
    def ewf_table(self) -> list[EWFBand]:
        """Standard EWF table for testing."""
        return [
            EWFBand(lower=Decimal("0"), upper=Decimal("75000"), percentage=Decimal("0")),
            EWFBand(
                lower=Decimal("75001"),
                upper=Decimal("1350000"),
                percentage=Decimal("0.0035"),
            ),
            EWFBand(
                lower=Decimal("1350001"),
                upper=None,
                fixed_amount=Decimal("4725"),
                excess_percentage=Decimal("0.0235"),
                threshold=Decimal("1350000"),
            ),
        ]

    def test_ewf_low_value_exempt(self, ewf_table):
        """Test WOZ under 75.000 is exempt (0%)."""
        result = calculate_ewf(Decimal("74000"), ewf_table, 2026)
        assert result == Decimal("0")

    def test_ewf_exactly_75000(self, ewf_table):
        """Test WOZ exactly at 75.000 is exempt."""
        result = calculate_ewf(Decimal("75000"), ewf_table, 2026)
        assert result == Decimal("0")

    def test_ewf_standard_band(self, ewf_table):
        """Test WOZ in standard band (0.35%)."""
        result = calculate_ewf(Decimal("400000"), ewf_table, 2026)
        # 400000 * 0.0035 = 1400
        assert result == Decimal("1400.00")

    def test_ewf_standard_band_500k(self, ewf_table):
        """Test WOZ of 500.000."""
        result = calculate_ewf(Decimal("500000"), ewf_table, 2026)
        # 500000 * 0.0035 = 1750
        assert result == Decimal("1750.00")

    def test_ewf_at_upper_boundary(self, ewf_table):
        """Test WOZ at upper boundary of standard band."""
        result = calculate_ewf(Decimal("1350000"), ewf_table, 2026)
        # 1350000 * 0.0035 = 4725
        assert result == Decimal("4725.00")

    def test_ewf_villataks(self, ewf_table):
        """Test villa tax for high-value properties."""
        result = calculate_ewf(Decimal("1500000"), ewf_table, 2026)
        # 4725 + (1500000 - 1350000) * 0.0235 = 4725 + 3525 = 8250
        assert result == Decimal("8250.00")

    def test_ewf_villataks_2m(self, ewf_table):
        """Test villa tax for 2M property."""
        result = calculate_ewf(Decimal("2000000"), ewf_table, 2026)
        # 4725 + (2000000 - 1350000) * 0.0235 = 4725 + 15275 = 20000
        assert result == Decimal("20000.00")

    def test_ewf_negative_woz_raises_error(self, ewf_table):
        """Test negative WOZ value raises error."""
        with pytest.raises(WOZValueOutOfRangeError):
            calculate_ewf(Decimal("-100000"), ewf_table, 2026)

    def test_ewf_empty_table_raises_error(self):
        """Test empty EWF table raises error."""
        with pytest.raises(WOZValueOutOfRangeError):
            calculate_ewf(Decimal("400000"), [], 2026)
