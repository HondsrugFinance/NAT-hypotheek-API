#!/usr/bin/env bash
# Render build script
set -e

pip install -r requirements.txt

# Playwright Chromium NIET geïnstalleerd — Fastlane SSO is sessiegebonden,
# auto-refresh werkt niet betrouwbaar. Manuele token refresh via:
#   POST /rentes/scraper/set-credentials
echo "==> Build done"
