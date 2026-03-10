"""Formattering-helpers voor adviesrapport waarden.

Alle functies retourneren strings die direct in de PDF template worden geplaatst.
Nederlands format: punt als duizendtallen-scheidingsteken, komma als decimaal.
"""

from datetime import date


def format_bedrag(value: float, show_cents: bool = False) -> str:
    """Format bedrag als '€ 338.173' (zonder centen) of '€ 1.267,48' (met centen)."""
    if value is None:
        return "€ 0"
    if show_cents:
        formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"€ {formatted}"
    formatted = f"{value:,.0f}".replace(",", ".")
    return f"€ {formatted}"


def format_percentage(value: float, decimals: int = 2) -> str:
    """Format percentage als '4,50%'. Verwacht decimaal (0.045 → 4,50%)."""
    pct = value * 100
    formatted = f"{pct:.{decimals}f}".replace(".", ",")
    return f"{formatted}%"


def format_datum(value: str) -> str:
    """Converteer YYYY-MM-DD naar DD-MM-YYYY. Retourneert origineel als conversie faalt."""
    if not value:
        return ""
    try:
        d = date.fromisoformat(value)
        return d.strftime("%d-%m-%Y")
    except (ValueError, TypeError):
        return value


def format_looptijd_jaren(maanden: int) -> str:
    """Converteer maanden naar leesbare looptijd. 360 → '30 jaar', 300 → '25 jaar'."""
    jaren = maanden // 12
    rest = maanden % 12
    if rest == 0:
        return f"{jaren} jaar"
    return f"{jaren} jaar en {rest} mnd"


def format_rvp_jaren(maanden: int) -> str:
    """Converteer RVP maanden naar jaren. 120 → '10 jaar'."""
    return format_looptijd_jaren(maanden)
