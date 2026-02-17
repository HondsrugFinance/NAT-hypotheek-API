"""Fiscal rules loader with caching."""

import json
from functools import lru_cache
from pathlib import Path

from monthly_costs.schemas.rules import FiscalRules
from monthly_costs.config import RULES_DIR
from monthly_costs.exceptions import FiscalRulesNotFoundError, InvalidFiscalRulesError


@lru_cache(maxsize=10)
def load_rules(fiscal_year: int) -> FiscalRules:
    """
    Load fiscal rules for a specific year.

    Rules are loaded from JSON files in the rules directory.
    Results are cached for performance.
    """
    rules_file = RULES_DIR / f"{fiscal_year}.json"

    if not rules_file.exists():
        raise FiscalRulesNotFoundError(fiscal_year)

    try:
        with open(rules_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        rules = FiscalRules.model_validate(data)
        return rules

    except json.JSONDecodeError as e:
        raise InvalidFiscalRulesError(
            message=f"Invalid JSON in rules file: {e}",
            year=fiscal_year,
        )
    except Exception as e:
        raise InvalidFiscalRulesError(
            message=f"Error loading rules: {e}",
            year=fiscal_year,
        )


def get_available_years() -> list[int]:
    """Get list of years for which rules are available."""
    if not RULES_DIR.exists():
        return []

    years = []
    for file in RULES_DIR.glob("*.json"):
        try:
            year = int(file.stem)
            years.append(year)
        except ValueError:
            continue

    return sorted(years)


def save_rules(rules: FiscalRules) -> Path:
    """Save fiscal rules to a JSON file."""
    RULES_DIR.mkdir(parents=True, exist_ok=True)

    rules_file = RULES_DIR / f"{rules.fiscal_year}.json"

    with open(rules_file, "w", encoding="utf-8") as f:
        json.dump(rules.model_dump(mode="json"), f, indent=2, ensure_ascii=False)

    load_rules.cache_clear()

    return rules_file


def clear_cache() -> None:
    """Clear the rules cache."""
    load_rules.cache_clear()
