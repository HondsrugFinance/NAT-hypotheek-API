"""Pytest fixtures for monthly costs tests."""

import pytest
from decimal import Decimal

from monthly_costs.schemas.rules import TaxBracket, EWFBand, HillenConfig, FiscalRules


@pytest.fixture
def tax_brackets_2026() -> list[TaxBracket]:
    """Tax brackets for 2026."""
    return [
        TaxBracket(lower=Decimal("0"), upper=Decimal("38883"), rate=Decimal("0.3575")),
        TaxBracket(lower=Decimal("38883"), upper=Decimal("78426"), rate=Decimal("0.3756")),
        TaxBracket(lower=Decimal("78426"), upper=None, rate=Decimal("0.495")),
    ]


@pytest.fixture
def ewf_table_2026() -> list[EWFBand]:
    """EWF table for 2026."""
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


@pytest.fixture
def hillen_config_2026() -> HillenConfig:
    """Hillen config for 2026."""
    return HillenConfig(enabled=True, reduction_percentage=Decimal("0.71867"))


@pytest.fixture
def fiscal_rules_2026(
    tax_brackets_2026, ewf_table_2026, hillen_config_2026
) -> FiscalRules:
    """Complete fiscal rules for 2026."""
    return FiscalRules(
        fiscal_year=2026,
        tax_brackets_box1=tax_brackets_2026,
        max_mortgage_interest_deduction_rate=Decimal("0.3756"),
        ewf_table=ewf_table_2026,
        hillen=hillen_config_2026,
    )
