"""Pydantic schemas for API response output."""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class LoanPartResult(BaseModel):
    """Result for a single loan part."""

    model_config = {"frozen": True}

    loan_part_id: str = Field(description="Identifier of the loan part")
    loan_type: str = Field(description="Type of loan (annuity/linear/interest_only)")
    box: int = Field(description="Fiscal box (1 or 3)")
    principal: Decimal = Field(description="Original principal amount")
    remaining_principal: Decimal = Field(description="Remaining principal after this month")
    interest_payment: Decimal = Field(description="Interest payment this month")
    principal_payment: Decimal = Field(description="Principal payment this month")
    gross_payment: Decimal = Field(description="Total gross payment this month")


class TaxBreakdown(BaseModel):
    """Detailed tax breakdown."""

    model_config = {"frozen": True}

    # EWF
    ewf_annual: Decimal = Field(description="Annual eigenwoningforfait")
    ewf_monthly: Decimal = Field(description="Monthly eigenwoningforfait")

    # Interest
    total_interest_box1_annual: Decimal = Field(
        description="Total annual interest from box 1 loans"
    )
    total_interest_box1_monthly: Decimal = Field(
        description="Monthly interest from box 1 loans"
    )

    # Rates
    marginal_rate: Decimal = Field(
        description="Marginal tax rate (weighted if 2 partners)"
    )
    effective_deduction_rate: Decimal = Field(
        description="Effective deduction rate after max limitation"
    )

    # Interest deduction
    interest_deduction_annual: Decimal = Field(
        description="Annual tax benefit from interest deduction"
    )
    interest_deduction_monthly: Decimal = Field(
        description="Monthly tax benefit from interest deduction"
    )

    # Hillen
    hillen_applicable: bool = Field(description="Whether Hillen applies")
    hillen_deduction_annual: Decimal = Field(
        description="Annual Hillen deduction"
    )
    hillen_benefit_monthly: Decimal = Field(
        description="Monthly tax benefit from Hillen"
    )

    # Net EWF
    net_ewf_addition_annual: Decimal = Field(
        description="Net annual EWF addition after Hillen"
    )
    ewf_tax_monthly: Decimal = Field(
        description="Monthly tax cost from EWF"
    )

    # Totals
    total_tax_benefit_monthly: Decimal = Field(
        description="Total monthly tax benefit (interest deduction + Hillen)"
    )
    total_tax_cost_monthly: Decimal = Field(
        description="Total monthly tax cost (EWF)"
    )
    net_tax_effect_monthly: Decimal = Field(
        description="Net monthly tax effect (benefit - cost)"
    )


class PartnerResult(BaseModel):
    """Result per partner when using partner distribution."""

    model_config = {"frozen": True}

    partner_id: str = Field(description="Partner identifier")
    taxable_income: Decimal = Field(description="Annual taxable income")
    marginal_rate: Decimal = Field(description="Marginal tax rate")
    effective_rate: Decimal = Field(
        description="Effective deduction rate (capped at max)"
    )
    interest_share_annual: Decimal = Field(
        description="Annual share of deductible interest"
    )
    interest_deduction_annual: Decimal = Field(
        description="Annual tax benefit from interest"
    )
    ewf_share_annual: Decimal = Field(
        description="Annual share of EWF addition"
    )


class MonthlyCostsResponse(BaseModel):
    """Complete response with all calculation details."""

    model_config = {"frozen": True}

    # Request context
    fiscal_year: int = Field(description="Fiscal year used")
    month_number: int = Field(description="Month number calculated")
    woz_value: Decimal = Field(description="WOZ value of property")

    # Per loan part results
    loan_parts: list[LoanPartResult] = Field(description="Results per loan part")

    # Totals
    total_gross_monthly: Decimal = Field(description="Total gross monthly payment")
    total_interest_monthly: Decimal = Field(description="Total monthly interest")
    total_principal_monthly: Decimal = Field(description="Total monthly principal")
    total_interest_box1_monthly: Decimal = Field(
        description="Monthly interest from box 1 loans only"
    )
    total_interest_box3_monthly: Decimal = Field(
        description="Monthly interest from box 3 loans (no deduction)"
    )

    # Tax breakdown
    tax_breakdown: TaxBreakdown = Field(description="Detailed tax calculations")

    # Partner distribution (if applicable)
    partner_results: Optional[list[PartnerResult]] = Field(
        default=None, description="Results per partner if distributed"
    )

    # Final results
    net_monthly_cost: Decimal = Field(
        description="Net monthly cost after tax effects"
    )

    # Disclaimer
    disclaimer: str = Field(
        default="Indicatief - geen aangifteadvies. Wijzigingen in wetgeving, inkomen of rente kunnen de uitkomst beïnvloeden.",
        description="Legal disclaimer",
    )
