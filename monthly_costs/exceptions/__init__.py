"""Custom exceptions for the mortgage calculator."""

from typing import Any


class MortgageCalculatorError(Exception):
    """Base exception for all application errors."""

    def __init__(
        self,
        message: str,
        error_code: str,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class ValidationError(MortgageCalculatorError):
    """Input validation errors."""

    def __init__(self, message: str, field: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details={"field": field, **(details or {})},
        )


class FiscalRulesNotFoundError(MortgageCalculatorError):
    """Fiscal rules not found for the requested year."""

    def __init__(self, year: int):
        super().__init__(
            message=f"Geen fiscale regels beschikbaar voor jaar {year}",
            error_code="RULES_NOT_FOUND",
            details={"fiscal_year": year},
        )


class InvalidFiscalRulesError(MortgageCalculatorError):
    """Invalid fiscal rules configuration."""

    def __init__(self, message: str, year: int):
        super().__init__(
            message=message,
            error_code="INVALID_RULES",
            details={"fiscal_year": year},
        )


class CalculationError(MortgageCalculatorError):
    """Error during calculation."""

    def __init__(self, message: str, calculation_step: str):
        super().__init__(
            message=message,
            error_code="CALCULATION_ERROR",
            details={"step": calculation_step},
        )


class WOZValueOutOfRangeError(MortgageCalculatorError):
    """WOZ value outside configured range."""

    def __init__(self, woz_value: float, year: int):
        super().__init__(
            message=f"WOZ-waarde {woz_value} valt buiten configuratie voor {year}",
            error_code="WOZ_OUT_OF_RANGE",
            details={"woz_value": woz_value, "fiscal_year": year},
        )
