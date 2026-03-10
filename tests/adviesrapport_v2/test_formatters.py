"""Tests voor adviesrapport_v2.formatters."""

import pytest
from adviesrapport_v2.formatters import (
    format_bedrag, format_percentage, format_datum,
    format_looptijd_jaren, format_rvp_jaren,
)


class TestFormatBedrag:
    def test_basic(self):
        assert format_bedrag(338173) == "€ 338.173"

    def test_zero(self):
        assert format_bedrag(0) == "€ 0"

    def test_none(self):
        assert format_bedrag(None) == "€ 0"

    def test_millions(self):
        assert format_bedrag(1234567) == "€ 1.234.567"

    def test_with_cents(self):
        assert format_bedrag(1267.48, show_cents=True) == "€ 1.267,48"

    def test_small(self):
        assert format_bedrag(100) == "€ 100"

    def test_negative(self):
        assert format_bedrag(-5000) == "€ -5.000"


class TestFormatPercentage:
    def test_decimal_to_percent(self):
        assert format_percentage(0.045) == "4,50%"

    def test_zero(self):
        assert format_percentage(0) == "0,00%"

    def test_three_decimals(self):
        assert format_percentage(0.04316, decimals=3) == "4,316%"

    def test_one_decimal(self):
        assert format_percentage(0.263, decimals=1) == "26,3%"


class TestFormatDatum:
    def test_iso_to_nl(self):
        assert format_datum("1968-02-01") == "01-02-1968"

    def test_already_nl(self):
        assert format_datum("01-02-1968") == "01-02-1968"

    def test_empty(self):
        assert format_datum("") == ""

    def test_none(self):
        assert format_datum(None) == ""

    def test_invalid(self):
        assert format_datum("invalid") == "invalid"


class TestFormatLooptijdJaren:
    def test_30_jaar(self):
        assert format_looptijd_jaren(360) == "30 jaar"

    def test_25_jaar(self):
        assert format_looptijd_jaren(300) == "25 jaar"

    def test_with_months(self):
        assert format_looptijd_jaren(269) == "22 jaar en 5 mnd"

    def test_zero(self):
        assert format_looptijd_jaren(0) == "0 jaar"


class TestFormatRvpJaren:
    def test_10_jaar(self):
        assert format_rvp_jaren(120) == "10 jaar"

    def test_20_jaar(self):
        assert format_rvp_jaren(240) == "20 jaar"
