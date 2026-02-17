"""Exception handlers for FastAPI."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from monthly_costs.exceptions import (
    CalculationError,
    FiscalRulesNotFoundError,
    MortgageCalculatorError,
    ValidationError,
)


async def mortgage_calculator_exception_handler(
    request: Request,
    exc: MortgageCalculatorError,
) -> JSONResponse:
    """Handle custom mortgage calculator exceptions."""
    status_code = status.HTTP_400_BAD_REQUEST

    if isinstance(exc, FiscalRulesNotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, ValidationError):
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    elif isinstance(exc, CalculationError):
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    return JSONResponse(
        status_code=status_code,
        content={
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register monthly costs exception handlers with the FastAPI app."""
    app.add_exception_handler(MortgageCalculatorError, mortgage_calculator_exception_handler)
