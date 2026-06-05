"""Unit tests for input schema validation (LoanPart)."""

from decimal import Decimal

import pytest

from monthly_costs.schemas.input import LoanPart


def _loan_part(rate) -> LoanPart:
    return LoanPart(
        id="deel_1",
        principal=Decimal("100000"),
        interest_rate=rate,
        term_years=Decimal("30"),
        loan_type="annuity",
    )


class TestInterestRateConversion:
    """Het contract is een percentage (4.5 = 4,5%): altijd delen door 100."""

    def test_standard_rate(self):
        assert _loan_part(Decimal("4.5")).interest_rate == Decimal("0.045")

    def test_high_rate(self):
        assert _loan_part(Decimal("3.7")).interest_rate == Decimal("0.037")

    def test_rate_exactly_one_percent(self):
        assert _loan_part(Decimal("1")).interest_rate == Decimal("0.01")

    @pytest.mark.parametrize(
        "percentage,expected",
        [
            (Decimal("0.9"), Decimal("0.009")),
            (Decimal("0.5"), Decimal("0.005")),
            (Decimal("0.1"), Decimal("0.001")),
            (Decimal("0.001"), Decimal("0.00001")),
        ],
    )
    def test_sub_one_percent_rate(self, percentage, expected):
        """Regressie: rentes onder 1% mogen NIET als heel getal blijven staan.

        Voorheen liet `if v > 1` deze ongemoeid, waardoor 0,9% als 90% werd
        gerekend en het bruto-maandlasttotaal explodeerde.
        """
        assert _loan_part(percentage).interest_rate == expected

    def test_zero_rate(self):
        assert _loan_part(Decimal("0")).interest_rate == Decimal("0")

    def test_max_rate_within_bounds(self):
        assert _loan_part(Decimal("20")).interest_rate == Decimal("0.2")
