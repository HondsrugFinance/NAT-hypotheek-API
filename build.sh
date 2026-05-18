#!/usr/bin/env bash
# Render build script
set -e

pip install -r requirements.txt

# Installeer Playwright Chromium + headless shell (Playwright 1.52 splitst die op).
# Nodig voor de Fastlane scraper auto token-refresh via fastlane_auth.py.
echo "==> Installing Playwright Chromium..."
python -m playwright install chromium chromium-headless-shell || echo "WARN: Playwright Chromium install failed — auto token-refresh werkt niet"
echo "==> Playwright install done"
