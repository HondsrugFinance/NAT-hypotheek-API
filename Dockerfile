FROM python:3.13-slim

# WeasyPrint systeemafhankelijkheden
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright is NIET geïnstalleerd op runtime — Fastlane SSO is sessiegebonden
# en Playwright auto-refresh werkt niet betrouwbaar. Token-refresh gebeurt
# handmatig via POST /rentes/scraper/set-credentials.

COPY . .

# Render zet PORT env var, default 10000
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}
