FROM python:3.13-slim

# WeasyPrint systeemafhankelijkheden + Playwright Chromium dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Installeer Playwright Chromium + headless shell (Playwright 1.52 splitst die op)
# Nodig voor Fastlane auto token-refresh via fastlane_auth.py
RUN python -m playwright install chromium chromium-headless-shell

COPY . .

# Render zet PORT env var, default 10000
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}
