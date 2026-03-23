"""
Microsoft Graph API authenticatie — gedeelde token-logica.

Gebruikt client_credentials flow (application permissions, geen per-user OAuth).
Vereist Azure Entra ID app-registratie.

Wordt gedeeld door graph_client.py (e-mail) en sharepoint/client.py (bestanden).
"""

import os
import time
import logging

import httpx

logger = logging.getLogger("nat-api.graph-auth")

# --- Configuratie uit environment ---
AZURE_TENANT_ID = os.environ.get("AZURE_TENANT_ID")
AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID")
AZURE_CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET")

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
TOKEN_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"

# Module-level token cache
_token_cache: dict = {"access_token": None, "expires_at": 0}


class GraphAPIError(Exception):
    """Fout bij aanroep van Microsoft Graph API."""

    def __init__(self, message: str, status_code: int = 500, detail: str = ""):
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


def is_configured() -> bool:
    """Check of alle Azure credentials zijn ingesteld."""
    return all([AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET])


async def get_access_token() -> str:
    """
    Verkrijg een access token via client_credentials flow.
    Cached het token tot 5 minuten voor verloop.
    """
    if _token_cache["access_token"] and time.time() < _token_cache["expires_at"] - 300:
        return _token_cache["access_token"]

    url = TOKEN_URL_TEMPLATE.format(tenant=AZURE_TENANT_ID)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, data={
            "client_id": AZURE_CLIENT_ID,
            "client_secret": AZURE_CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        })
        resp.raise_for_status()

        data = resp.json()
        _token_cache["access_token"] = data["access_token"]
        _token_cache["expires_at"] = time.time() + data.get("expires_in", 3600)

        logger.info(
            "Graph API token verkregen (geldig voor %d seconden)",
            data.get("expires_in", 0),
        )
        return data["access_token"]
