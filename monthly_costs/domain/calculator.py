"""Main calculator orchestrator - combines all calculation modules."""

from decimal import ROUND_HALF_UP, Decimal

from monthly_costs.schemas.input import (
    Box,
    LoanType,
    MonthlyCostsRequest,
    PartnerDistributionMethod,
)
from monthly_costs.schemas.output import (
    LoanPartResult,
    MonthlyCostsResponse,
    PartnerResult,
    TaxBreakdown,
)
from monthly_costs.schemas.rules import FiscalRules
from monthly_costs.domain.ewf import calculate_ewf
from monthly_costs.domain.hillen import calculate_hillen_deduction, calculate_net_ewf_addition
from monthly_costs.domain.loan_calc import get_calculator
from monthly_costs.domain.partner import (
    DistributionMethod,
    PartnerTaxInfo,
    calculate_partner_tax_info,
    calculate_total_tax_benefit,
    distribute_interest,
)
from monthly_costs.domain.tax_calc import (
    calculate_effective_deduction_rate,
    calculate_marginal_rate,
)
from monthly_costs.rules.loader import load_rules


def _round_currency(value: Decimal) -> Decimal:
    """Round to 2 decimal places using HALF_UP."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class MortgageCalculator:
    """Main calculator that orchestrates all sub-calculations."""

    def __init__(self, fiscal_year: int):
        self.fiscal_year = fiscal_year
        self.rules = load_rules(fiscal_year)

    def calculate(self, request: MonthlyCostsRequest) -> MonthlyCostsResponse:
        """Perform full monthly costs calculation."""
        # 1. Calculate loan parts
        loan_results = self._calculate_loan_parts(request)

        # 2. Sum up totals
        totals = self._calculate_totals(loan_results)

        # 3. Calculate EWF
        ewf_annual = Decimal("0")
        if request.include_ewf:
            ewf_annual = calculate_ewf(
                request.woz_value, self.rules.ewf_table, self.fiscal_year
            )
        ewf_monthly = _round_currency(ewf_annual / 12)

        # 4. Calculate partner tax info and distribution
        partner_info = self._build_partner_info(request)
        distribution = self._calculate_distribution(
            request, partner_info, totals["interest_box1_annual"]
        )

        # 5. Calculate effective rate (weighted if multiple partners)
        effective_rate = self._calculate_weighted_effective_rate(distribution)

        # 6. Calculate interest deduction
        interest_deduction_annual = calculate_total_tax_benefit(
            distribution, totals["interest_box1_annual"]
        )
        interest_deduction_monthly = _round_currency(interest_deduction_annual / 12)

        # 7. Calculate marginal rate (needed for EWF and Hillen)
        marginal_rate = self._calculate_combined_marginal_rate(partner_info)

        # 8. Calculate Hillen
        hillen_applicable = False
        hillen_deduction_annual = Decimal("0")
        hillen_benefit_monthly = Decimal("0")

        if request.include_hillen and self.rules.hillen.enabled:
            hillen_deduction_annual = calculate_hillen_deduction(
                ewf_annual, totals["interest_box1_annual"], self.rules.hillen
            )
            hillen_applicable = hillen_deduction_annual > 0
            hillen_benefit_monthly = _round_currency(
                hillen_deduction_annual * marginal_rate / 12
            )

        # 9. Calculate net EWF addition (taxed at marginal rate)
        net_ewf_addition_annual = ewf_annual - hillen_deduction_annual
        ewf_tax_monthly = _round_currency(net_ewf_addition_annual * marginal_rate / 12)

        # 10. Build tax breakdown
        tax_breakdown = TaxBreakdown(
            ewf_annual=ewf_annual,
            ewf_monthly=ewf_monthly,
            total_interest_box1_annual=totals["interest_box1_annual"],
            total_interest_box1_monthly=totals["interest_box1_monthly"],
            marginal_rate=marginal_rate,
            effective_deduction_rate=effective_rate,
            interest_deduction_annual=interest_deduction_annual,
            interest_deduction_monthly=interest_deduction_monthly,
            hillen_applicable=hillen_applicable,
            hillen_deduction_annual=hillen_deduction_annual,
            hillen_benefit_monthly=hillen_benefit_monthly,
            net_ewf_addition_annual=net_ewf_addition_annual,
            ewf_tax_monthly=ewf_tax_monthly,
            total_tax_benefit_monthly=interest_deduction_monthly,
            total_tax_cost_monthly=ewf_tax_monthly,
            net_tax_effect_monthly=interest_deduction_monthly - ewf_tax_monthly,
        )

        # 11. Build partner results if applicable
        partner_results = None
        if len(request.partners) > 1:
            partner_results = self._build_partner_results(
                request, partner_info, distribution, ewf_annual
            )

        # 12. Calculate net monthly cost
        net_monthly = (
            totals["gross_monthly"]
            - interest_deduction_monthly
            + ewf_tax_monthly
        )

        return MonthlyCostsResponse(
            fiscal_year=self.fiscal_year,
            month_number=request.month_number,
            woz_value=request.woz_value,
            loan_parts=loan_results,
            total_gross_monthly=totals["gross_monthly"],
            total_interest_monthly=totals["interest_monthly"],
            total_principal_monthly=totals["principal_monthly"],
            total_interest_box1_monthly=totals["interest_box1_monthly"],
            total_interest_box3_monthly=totals["interest_box3_monthly"],
            tax_breakdown=tax_breakdown,
            partner_results=partner_results,
            net_monthly_cost=_round_currency(net_monthly),
        )

    def _calculate_loan_parts(
        self, request: MonthlyCostsRequest
    ) -> list[LoanPartResult]:
        """Calculate results for each loan part."""
        results = []

        for loan_part in request.loan_parts:
            calculator = get_calculator(loan_part.loan_type.value)
            payment = calculator.calculate_month(
                principal=loan_part.principal,
                annual_rate=loan_part.interest_rate,
                term_years=loan_part.term_years,
                month_number=request.month_number,
            )

            results.append(
                LoanPartResult(
                    loan_part_id=loan_part.id,
                    loan_type=loan_part.loan_type.value,
                    box=loan_part.box.value,
                    principal=loan_part.principal,
                    remaining_principal=payment.remaining_principal,
                    interest_payment=payment.interest_payment,
                    principal_payment=payment.principal_payment,
                    gross_payment=payment.gross_payment,
                )
            )

        return results

    def _calculate_totals(
        self, loan_results: list[LoanPartResult]
    ) -> dict[str, Decimal]:
        """Calculate totals from loan results."""
        gross = Decimal("0")
        interest = Decimal("0")
        principal = Decimal("0")
        interest_box1 = Decimal("0")
        interest_box3 = Decimal("0")

        for result in loan_results:
            gross += result.gross_payment
            interest += result.interest_payment
            principal += result.principal_payment

            if result.box == 1:
                interest_box1 += result.interest_payment
            else:
                interest_box3 += result.interest_payment

        return {
            "gross_monthly": _round_currency(gross),
            "interest_monthly": _round_currency(interest),
            "principal_monthly": _round_currency(principal),
            "interest_box1_monthly": _round_currency(interest_box1),
            "interest_box3_monthly": _round_currency(interest_box3),
            "interest_box1_annual": _round_currency(interest_box1 * 12),
            "interest_box3_annual": _round_currency(interest_box3 * 12),
        }

    def _build_partner_info(
        self, request: MonthlyCostsRequest
    ) -> list[PartnerTaxInfo]:
        """Build tax info for all partners."""
        partners = []
        for partner in request.partners:
            brackets = (
                self.rules.tax_brackets_box1_aow
                if partner.is_aow and self.rules.tax_brackets_box1_aow
                else self.rules.tax_brackets_box1
            )
            info = calculate_partner_tax_info(
                partner_id=partner.id,
                taxable_income=partner.taxable_income,
                age=partner.age,
                brackets=brackets,
            )
            partners.append(info)
        return partners

    def _calculate_distribution(
        self,
        request: MonthlyCostsRequest,
        partner_info: list[PartnerTaxInfo],
        total_interest_annual: Decimal,
    ):
        """Calculate interest distribution between partners."""
        partner1 = partner_info[0]
        partner2 = partner_info[1] if len(partner_info) > 1 else None

        method = DistributionMethod.FIXED_PERCENT
        parameter = Decimal("100") if partner2 is None else Decimal("50")

        if request.partner_distribution and partner2:
            method = DistributionMethod(request.partner_distribution.method.value)
            parameter = request.partner_distribution.parameter

        return distribute_interest(
            total_interest=total_interest_annual,
            partner1=partner1,
            partner2=partner2,
            method=method,
            max_deduction_rate=self.rules.max_mortgage_interest_deduction_rate,
            parameter=parameter,
        )

    def _calculate_weighted_effective_rate(self, distribution) -> Decimal:
        """Calculate weighted effective rate based on distribution."""
        if distribution.partner2_share == 0:
            return distribution.partner1_effective_rate

        total = distribution.partner1_share + distribution.partner2_share
        if total == 0:
            return distribution.partner1_effective_rate

        weighted = (
            distribution.partner1_share * distribution.partner1_effective_rate
            + distribution.partner2_share * distribution.partner2_effective_rate
        ) / total

        return _round_currency(weighted)

    def _calculate_combined_marginal_rate(
        self, partner_info: list[PartnerTaxInfo]
    ) -> Decimal:
        """Calculate combined marginal rate for display."""
        if len(partner_info) == 1:
            return partner_info[0].marginal_rate

        return max(p.marginal_rate for p in partner_info)

    def _build_partner_results(
        self,
        request: MonthlyCostsRequest,
        partner_info: list[PartnerTaxInfo],
        distribution,
        ewf_annual: Decimal,
    ) -> list[PartnerResult]:
        """Build detailed results per partner."""
        results = []

        p1 = partner_info[0]
        p1_ewf_share = ewf_annual / 2

        results.append(
            PartnerResult(
                partner_id=p1.partner_id,
                taxable_income=p1.taxable_income,
                marginal_rate=p1.marginal_rate,
                effective_rate=distribution.partner1_effective_rate,
                interest_share_annual=distribution.partner1_share,
                interest_deduction_annual=_round_currency(
                    distribution.partner1_share * distribution.partner1_effective_rate
                ),
                ewf_share_annual=p1_ewf_share,
            )
        )

        if len(partner_info) > 1:
            p2 = partner_info[1]
            p2_ewf_share = ewf_annual / 2

            results.append(
                PartnerResult(
                    partner_id=p2.partner_id,
                    taxable_income=p2.taxable_income,
                    marginal_rate=p2.marginal_rate,
                    effective_rate=distribution.partner2_effective_rate,
                    interest_share_annual=distribution.partner2_share,
                    interest_deduction_annual=_round_currency(
                        distribution.partner2_share * distribution.partner2_effective_rate
                    ),
                    ewf_share_annual=p2_ewf_share,
                )
            )

        return results
