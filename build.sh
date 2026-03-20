#!/usr/bin/env bash
# Render build script
set -e

pip install -r requirements.txt

# Installeer Playwright Chromium + systeem-dependencies
# Render draait op Debian/Ubuntu, dus --with-deps installeert libatk, libcups etc.
echo "==> Installing Playwright Chromium..."
npx playwright install --with-deps chromium || python -m playwright install --with-deps chromium || echo "WARN: Playwright Chromium install failed (optional)"
echo "==> Playwright install done"
