"""
Calcasa API Discovery Script
=============================
Verkent de Calcasa API (api.calcasa.nl) met een Bearer token uit de browser.

Gebruik:
1. Log in op app.desktoptaxatie.nl
2. Open DevTools → Application → Local Storage (of Network tab)
3. Kopieer de Bearer token (begint meestal met "eyJ...")
4. Plak in .env als CALCASA_BEARER_TOKEN
5. Run: python discover_api.py
"""

import os
import sys
import json
import httpx
from pathlib import Path
from dotenv import load_dotenv

# Laad .env uit dezelfde map
load_dotenv(Path(__file__).parent / ".env")

API_BASE = "https://api.calcasa.nl"
TOKEN = os.getenv("CALCASA_BEARER_TOKEN", "")

if not TOKEN:
    print("❌ Geen CALCASA_BEARER_TOKEN gevonden in .env")
    print("   Kopieer je Bearer token uit de browser DevTools.")
    print("   Zie README voor instructies.")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}


def probe_endpoint(client: httpx.Client, method: str, path: str, body: dict | None = None) -> dict:
    """Test een endpoint en return status + response."""
    url = f"{API_BASE}{path}"
    try:
        if method == "GET":
            r = client.get(url)
        elif method == "POST":
            r = client.post(url, json=body or {})
        else:
            return {"path": path, "status": "skip", "method": method}

        result = {
            "path": path,
            "method": method,
            "status": r.status_code,
            "content_type": r.headers.get("content-type", ""),
        }

        # Probeer JSON response te parsen
        if "json" in result["content_type"]:
            try:
                data = r.json()
                # Beperk output voor grote responses
                result["response"] = _truncate(data)
            except Exception:
                result["response_text"] = r.text[:500]
        elif r.status_code == 200:
            result["response_text"] = r.text[:500]

        return result

    except Exception as e:
        return {"path": path, "method": method, "error": str(e)}


def _truncate(data, max_items: int = 3, max_depth: int = 2) -> any:
    """Beperk grote JSON responses voor leesbaarheid."""
    if max_depth <= 0:
        return "..." if isinstance(data, (dict, list)) else data
    if isinstance(data, list):
        truncated = [_truncate(item, max_items, max_depth - 1) for item in data[:max_items]]
        if len(data) > max_items:
            truncated.append(f"... (+{len(data) - max_items} meer)")
        return truncated
    if isinstance(data, dict):
        return {k: _truncate(v, max_items, max_depth - 1) for k, v in list(data.items())[:10]}
    return data


def main():
    print("=" * 60)
    print("Calcasa API Discovery")
    print(f"Base URL: {API_BASE}")
    print(f"Token: {TOKEN[:20]}...{TOKEN[-10:]}" if len(TOKEN) > 30 else f"Token: {TOKEN}")
    print("=" * 60)

    # Bekende en vermoedelijke endpoints om te testen
    endpoints = [
        # Health / info
        ("GET", "/health"),
        ("GET", "/api/v1"),
        ("GET", "/api/v1/me"),
        ("GET", "/api/v1/users/me"),
        ("GET", "/v1"),
        ("GET", "/v1/me"),

        # Adressen
        ("GET", "/api/v1/adressen"),
        ("POST", "/api/v1/adressen/zoeken"),
        ("GET", "/v1/adressen"),
        ("POST", "/v1/adressen/zoeken"),

        # Waarderingen (taxaties)
        ("GET", "/api/v1/waarderingen"),
        ("POST", "/api/v1/waarderingen/zoeken"),
        ("GET", "/v1/waarderingen"),
        ("POST", "/v1/waarderingen/zoeken"),

        # Geldverstrekkers
        ("GET", "/api/v1/geldverstrekkers"),
        ("GET", "/v1/geldverstrekkers"),
        ("GET", "/api/v1/geldverstrekkers/hypotheek"),
        ("GET", "/v1/geldverstrekkers/hypotheek"),

        # Rapporten
        ("GET", "/api/v1/rapporten"),
        ("GET", "/v1/rapporten"),

        # Bestemmingsplannen
        ("GET", "/api/v1/bestemmingsplandata"),
        ("GET", "/v1/bestemmingsplandata"),

        # Gebruiker / account
        ("GET", "/api/v1/account"),
        ("GET", "/v1/account"),
        ("GET", "/api/v1/tegoed"),
        ("GET", "/v1/tegoed"),

        # Facturen
        ("GET", "/api/v1/facturen"),
        ("GET", "/v1/facturen"),

        # Callbacks
        ("GET", "/api/v1/callbacks"),
        ("GET", "/v1/callbacks"),
    ]

    results = []
    with httpx.Client(headers=HEADERS, timeout=15.0, follow_redirects=True) as client:
        for method, path in endpoints:
            print(f"  {method:4s} {path} ...", end=" ", flush=True)
            result = probe_endpoint(client, method, path)
            status = result.get("status", result.get("error", "?"))

            # Kleur-indicatie
            if isinstance(status, int):
                if status == 200:
                    indicator = "✅"
                elif status == 401:
                    indicator = "🔒"
                elif status == 403:
                    indicator = "⛔"
                elif status == 404:
                    indicator = "❌"
                else:
                    indicator = f"⚠️ "
            else:
                indicator = "💥"

            print(f"{indicator} {status}")
            results.append(result)

    # Samenvatting: alleen werkende endpoints
    print("\n" + "=" * 60)
    print("WERKENDE ENDPOINTS (status 200):")
    print("=" * 60)
    working = [r for r in results if r.get("status") == 200]
    if working:
        for r in working:
            print(f"\n  {r['method']} {r['path']}")
            if "response" in r:
                print(f"  Response: {json.dumps(r['response'], indent=2, ensure_ascii=False)[:1000]}")
            elif "response_text" in r:
                print(f"  Response: {r['response_text'][:500]}")
    else:
        print("  Geen werkende endpoints gevonden.")
        print("  Mogelijk is de Bearer token verlopen of ongeldig.")

    # Auth-problemen
    auth_issues = [r for r in results if r.get("status") in (401, 403)]
    if auth_issues:
        print(f"\n⚠️  {len(auth_issues)} endpoints gaven 401/403 — token mogelijk verlopen of verkeerde scope.")

    # Exporteer resultaten
    output_file = Path(__file__).parent / "discovery_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResultaten opgeslagen in: {output_file}")


if __name__ == "__main__":
    main()
