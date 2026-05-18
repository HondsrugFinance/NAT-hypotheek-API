#!/usr/bin/env bash
# Render build script
set -e

pip install -r requirements.txt

# Installeer Playwright Chromium (zonder --with-deps want geen root op Render).
# Nodig voor de Fastlane scraper auto token-refresh via fastlane_auth.py.
echo "==> Installing Playwright Chromium..."
python -m playwright install chromium || echo "WARN: Playwright Chromium install failed — auto token-refresh werkt niet"
echo "==> Playwright install done"
