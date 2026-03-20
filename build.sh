#!/usr/bin/env bash
# Render build script
set -e

pip install -r requirements.txt

# Installeer Playwright Chromium (voor Calcasa login fallback)
# Faalt gracefully als het niet lukt (Playwright is optioneel)
python -m playwright install --with-deps chromium || echo "WARN: Playwright Chromium niet geïnstalleerd (optioneel)"
