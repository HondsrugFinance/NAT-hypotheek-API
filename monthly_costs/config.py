"""Configuration for monthly costs calculator."""

import json
from pathlib import Path

RULES_DIR = Path(__file__).parent / "rules"

# Fiscal year uit centraal config (config/fiscaal.json)
_CONFIG_DIR = Path(__file__).parent.parent / "config"
with open(_CONFIG_DIR / "fiscaal.json", "r", encoding="utf-8") as _f:
    DEFAULT_FISCAL_YEAR = int(json.load(_f)["versie"])
