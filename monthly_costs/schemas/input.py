"""Pydantic schemas for API request input."""

from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class LoanType(str, Enum):
    """Type of loan repayment."""

    ANNUITY = "annuity"
    LINEAR = "linear"
    INTEREST_ONLY = "interest_only"


class Box(int, Enum):
    """Fiscal box for the loan."""

    BOX1 = 1
    BOX3 = 3


class PartnerDistributionMethod(str, Enum):
    """Method for distributing interest deduction between partners."""

    FIXED_PERCENT = "fixed_percent"
    FIXED_AMOUNT = "fixed_amount"
    OPTIMIZE = "optimize"


class LoanPart(BaseModel):
    """A single loan part within the mortgage."""

    model_config = {"frozen": True}

    id: str = Field(..., min_length=1, description="Unique identifier for this loan part")
    principal: Decimal = Field(..., gt=0, description="Principal amount in euros")
    interest_rate: Decimal = Field(
        ...,
        ge=0,
        le=20,
        description="Annual interest rate as percentage (e.g., 4.5 for 4.5%)",
    )
    term_years: int = Field(..., gt=0, le=50, description="Loan term in years")
    loan_type: LoanType = Field(..., description="Type of loan repayment")
    box: Box = Field(default=Box.BOX1, description="Fiscal box (1 or 3)")

    @field_validator("interest_rate")
    @classmethod
    def convert_percentage_to_decimal(cls, v: Decimal) -> Decimal:
        """Convert percentage to decimal if needed (4.5 -> 0.045)."""
        if v > 1:
            return v / 100
        return v


class Partner(BaseModel):
    """Partner fiscal information."""

    model_config = {"frozen": True}

    id: str = Field(..., min_length=1, description="Identifier (e.g., 'partner1')")
    taxable_income: Decimal = Field(
        ..., ge=0, description="Annual taxable income in box 1"
    )
    age: int = Field(..., ge=18, le=120, description="Age of the partner")
    is_aow: bool = Field(default=False, description="Has reached AOW age")


class PartnerDistribution(BaseModel):
    """Configuration for distributing interest deduction between partners."""

    model_config = {"frozen": True}

    method: PartnerDistributionMethod = Field(
        ..., description="Distribution method to use"
    )
    parameter: Optional[Decimal] = Field(
        default=None,
        description="Percentage (0-100) for fixed_percent, amount for fixed_amount",
    )

    @field_validator("parameter")
    @classmethod
    def validate_parameter(cls, v: Optional[Decimal], info) -> Optional[Decimal]:
        """Validate parameter based on method."""
        return v


class MonthlyCostsRequest(BaseModel):
    """Main request for monthly costs calculation."""

    model_config = {"frozen": True}

    fiscal_year: int = Field(
        ..., ge=2020, le=2050, description="Fiscal year for rules"
    )
    woz_value: Decimal = Field(..., gt=0, description="WOZ value of the property")
    loan_parts: list[LoanPart] = Field(
        ..., min_length=1, description="List of loan parts"
    )
    partners: list[Partner] = Field(
        ..., min_length=1, max_length=2, description="Partner(s) fiscal information"
    )
    partner_distribution: Optional[PartnerDistribution] = Field(
        default=None, description="Distribution config for 2 partners (optional)"
    )
    month_number: int = Field(
        default=1, ge=1, description="Month number for calculation (1 = first month)"
    )
    include_ewf: bool = Field(
        default=True, description="Include eigenwoningforfait in calculation"
    )
    include_hillen: bool = Field(
        default=True, description="Apply Wet Hillen if applicable"
    )

    @field_validator("partner_distribution")
    @classmethod
    def validate_distribution_for_partners(
        cls, v: Optional[PartnerDistribution], info
    ) -> Optional[PartnerDistribution]:
        """Validate distribution config is provided when needed."""
        return v
