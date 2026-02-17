"""Main calculation endpoint."""

from fastapi import APIRouter

from monthly_costs.schemas.input import MonthlyCostsRequest
from monthly_costs.schemas.output import MonthlyCostsResponse
from monthly_costs.domain.calculator import MortgageCalculator

router = APIRouter(prefix="/calculate", tags=["monthly-costs"])


@router.post(
    "/monthly-costs",
    response_model=MonthlyCostsResponse,
    summary="Calculate monthly mortgage costs",
    description="""
    Calculate gross and net monthly costs for a Dutch mortgage.

    This endpoint calculates:
    - **Gross monthly payments** per loan part (interest + principal)
    - **Net monthly costs** after tax effects:
      - Mortgage interest deduction (box 1)
      - Eigenwoningforfait (EWF) addition
      - Wet Hillen correction (if applicable)

    **Features:**
    - Supports annuity, linear, and interest-only loans
    - Handles multiple loan parts with different types
    - Partner distribution: fixed percentage, fixed amount, or optimized
    - Box 1 vs Box 3 distinction (only box 1 interest is deductible)
    """,
    responses={
        200: {"description": "Successful calculation"},
        404: {"description": "Fiscal rules not found for the requested year"},
        422: {"description": "Validation error in request"},
    },
)
async def calculate_monthly_costs(
    request: MonthlyCostsRequest,
) -> MonthlyCostsResponse:
    """Calculate monthly mortgage costs."""
    calculator = MortgageCalculator(request.fiscal_year)
    return calculator.calculate(request)
