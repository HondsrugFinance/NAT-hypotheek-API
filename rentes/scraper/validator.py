"""Cross-validatie + trendcheck voor gescrapete rentes."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone

from rentes.scraper.models import RateChange, ScrapedRate, ScrapeResult, ValidationReport

logger = logging.getLogger("nat-api.scraper.validator")

# Drempels (in procentpunten)
WARN_THRESHOLD = 0.05      # bronnen wijken 0.05% af → waarschuwing
ERROR_THRESHOLD = 0.20     # bronnen wijken 0.20% af → quarantaine
TREND_WARN = 0.30          # sprong t.o.v. gisteren → flag
TREND_QUARANTINE = 1.00    # sprong t.o.v. gisteren → quarantaine


def _rate_key(r: ScrapedRate) -> tuple:
    """Unieke sleutel per tarief."""
    return (r.geldverstrekker, r.productlijn, r.aflosvorm, r.rentevaste_periode, r.ltv_categorie)


def cross_validate(results: list[ScrapeResult]) -> ValidationReport:
    """Vergelijk rentes van verschillende bronnen.

    Per tarief-key:
    - 1 bron: markeer als onbevestigd (niet per se fout)
    - 2+ bronnen: vergelijk waarden, markeer afwijkingen
    """
    report = ValidationReport()

    # Groepeer alle rates per key
    grouped: dict[tuple, list[ScrapedRate]] = defaultdict(list)
    for result in results:
        if not result.success:
            continue
        for rate in result.rates:
            grouped[_rate_key(rate)].append(rate)

    report.total_rates = len(grouped)

    for key, rates in grouped.items():
        if len(rates) == 1:
            # Eén bron — onbevestigd maar acceptabel
            continue

        # Meerdere bronnen: check afwijking
        values = [r.rente for r in rates]
        min_val = min(values)
        max_val = max(values)
        spread = max_val - min_val

        if spread > ERROR_THRESHOLD:
            report.quarantined.append({
                "key": key,
                "bronnen": [(r.bron, r.rente) for r in rates],
                "spread": round(spread, 4),
                "reden": f"Bron-conflict: spread {spread:.3f}% > {ERROR_THRESHOLD}%",
            })
        elif spread > WARN_THRESHOLD:
            report.warnings.append({
                "key": key,
                "bronnen": [(r.bron, r.rente) for r in rates],
                "spread": round(spread, 4),
            })

    return report


def trend_check(
    new_rates: list[ScrapedRate],
    previous_rates: dict[tuple, float],
) -> tuple[list[RateChange], list[dict]]:
    """Vergelijk nieuwe rentes met de vorige (uit database).

    Returns:
        changes: lijst van alle wijzigingen
        quarantined: verdachte sprongen (>TREND_QUARANTINE)
    """
    changes: list[RateChange] = []
    quarantined: list[dict] = []

    for rate in new_rates:
        key = _rate_key(rate)
        if key not in previous_rates:
            continue

        old_value = previous_rates[key]
        diff = rate.rente - old_value
        if abs(diff) < 0.001:
            continue  # geen wijziging

        change = RateChange(
            geldverstrekker=rate.geldverstrekker,
            productlijn=rate.productlijn,
            aflosvorm=rate.aflosvorm,
            rentevaste_periode=rate.rentevaste_periode,
            ltv_categorie=rate.ltv_categorie,
            oude_rente=old_value,
            nieuwe_rente=rate.rente,
            verschil=round(diff, 4),
        )
        changes.append(change)

        if abs(diff) >= TREND_QUARANTINE:
            quarantined.append({
                "key": key,
                "oud": old_value,
                "nieuw": rate.rente,
                "verschil": round(diff, 4),
                "reden": f"Sprong {abs(diff):.3f}% > {TREND_QUARANTINE}% — vermoedelijk parsefout",
            })
        elif abs(diff) >= TREND_WARN:
            logger.warning(
                "[validator] Grote rentewijziging: %s %s %s %djr %s: %.2f%% → %.2f%% (%+.3f%%)",
                *key, old_value, rate.rente, diff,
            )

    return changes, quarantined
