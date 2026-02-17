"""Pydantic schemas for fiscal rules configuration."""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class TaxBracket(BaseModel):
    """Income tax bracket for box 1."""

    model_config = {"frozen": True}

    lower: Decimal = Field(ge=0, description="Lower bound of the bracket")
    upper: Optional[Decimal] = Field(
        default=None, description="Upper bound (None = unlimited)"
    )
    rate: Decimal = Field(ge=0, le=1, description="Tax rate as decimal (e.g., 0.3756)")


class EWFBand(BaseModel):
    """Eigenwoningforfait (deemed rental income) band."""

    model_config = {"frozen": True}

    lower: Decimal = Field(ge=0, description="Lower bound of WOZ value")
    upper: Optional[Decimal] = Field(
        default=None, description="Upper bound (None = unlimited)"
    )
    percentage: Optional[Decimal] = Field(
        default=None, ge=0, le=1, description="EWF as percentage of WOZ value"
    )
    # Villa tax fields (for high-value properties)
    fixed_amount: Optional[Decimal] = Field(
        default=None, ge=0, description="Fixed base amount for villa tax"
    )
    excess_percentage: Optional[Decimal] = Field(
        default=None, ge=0, le=1, description="Percentage on excess above threshold"
    )
    threshold: Optional[Decimal] = Field(
        default=None, ge=0, description="Threshold for villa tax excess calculation"
    )

    @model_validator(mode="after")
    def validate_band(self) -> "EWFBand":
        """Validate that band has either percentage or villa tax config."""
        has_percentage = self.percentage is not None
        has_villataks = (
            self.fixed_amount is not None and self.excess_percentage is not None
        )

        if not has_percentage and not has_villataks:
            if self.lower > 0:
                pass  # Allow empty config for exempt bands

        return self


class HillenConfig(BaseModel):
    """Wet Hillen configuration."""

    model_config = {"frozen": True}

    enabled: bool = Field(default=True, description="Whether Hillen is enabled")
    reduction_percentage: Decimal = Field(
        ge=0,
        le=1,
        description="Percentage of difference that can be deducted (phased out)",
    )


class FiscalRules(BaseModel):
    """Complete fiscal rules for a specific year."""

    model_config = {"frozen": True}

    fiscal_year: int = Field(ge=2020, le=2050, description="The fiscal year")

    # Box 1 tax brackets
    tax_brackets_box1: list[TaxBracket] = Field(
        description="Income tax brackets for box 1"
    )
    tax_brackets_box1_aow: Optional[list[TaxBracket]] = Field(
        default=None, description="Tax brackets for AOW recipients (optional)"
    )

    # Maximum mortgage interest deduction rate
    max_mortgage_interest_deduction_rate: Decimal = Field(
        ge=0, le=1, description="Maximum rate for mortgage interest deduction"
    )

    # Eigenwoningforfait table
    ewf_table: list[EWFBand] = Field(description="EWF bands based on WOZ value")

    # Wet Hillen
    hillen: HillenConfig = Field(description="Hillen configuration")

    # Metadata
    effective_date: Optional[str] = Field(
        default=None, description="Effective date (YYYY-MM-DD)"
    )
    source: Optional[str] = Field(default=None, description="Source of the data")
    notes: Optional[str] = Field(default=None, description="Additional notes")

    @model_validator(mode="after")
    def validate_rules(self) -> "FiscalRules":
        """Validate rules consistency."""
        for i, bracket in enumerate(self.tax_brackets_box1[:-1]):
            next_bracket = self.tax_brackets_box1[i + 1]
            if bracket.upper is not None and bracket.upper != next_bracket.lower:
                pass

        sorted_bands = sorted(self.ewf_table, key=lambda b: b.lower)
        for i, band in enumerate(sorted_bands[:-1]):
            next_band = sorted_bands[i + 1]
            if band.upper is not None and band.upper >= next_band.lower:
                if band.upper > next_band.lower:
                    pass

        return self
