"""
Microsoft Graph API client — maak concept e-mails aan in Outlook met bijlagen.

Gebruikt client_credentials flow (application permissions, geen per-user OAuth).
Vereist Azure Entra ID app-registratie met Mail.ReadWrite toestemming.
"""

import os
import time
import base64
import logging
from typing import Optional

import httpx

logger = logging.getLogger("nat-api.graph")

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


async def _get_access_token() -> str:
    """
    Verkrijg een access token via client_credentials flow.
    Cached het token tot 5 minuten voor verloop.
    """
    # Return cached token als nog geldig (met 5 min buffer)
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


async def create_draft_with_attachment(
    sender_email: str,
    to_recipients: list[str],
    subject: str,
    body_html: str,
    attachment_name: str,
    attachment_bytes: bytes,
    cc_recipients: Optional[list[str]] = None,
) -> dict:
    """
    Maak een concept e-mail met PDF-bijlage in het postvak van de afzender.

    Twee Graph API calls:
    1. POST /users/{email}/messages  → concept aanmaken
    2. POST /users/{email}/messages/{id}/attachments  → PDF toevoegen

    Returns:
        dict met "message_id" en "web_link" (link om draft te openen in Outlook)

    Raises:
        GraphAPIError: bij een Graph API fout
    """
    token = await _get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Ontvangers opbouwen
    to_list = [{"emailAddress": {"address": email}} for email in to_recipients]
    cc_list = [{"emailAddress": {"address": email}} for email in (cc_recipients or [])]

    # Stap 1: Concept e-mail aanmaken
    message_payload = {
        "subject": subject,
        "body": {
            "contentType": "HTML",
            "content": body_html,
        },
        "toRecipients": to_list,
    }
    if cc_list:
        message_payload["ccRecipients"] = cc_list

    async with httpx.AsyncClient(timeout=30) as client:
        # Draft aanmaken
        create_url = f"{GRAPH_BASE_URL}/users/{sender_email}/messages"
        resp = await client.post(create_url, headers=headers, json=message_payload)

        if resp.status_code not in (200, 201):
            logger.error("Graph draft aanmaken mislukt: %s %s", resp.status_code, resp.text[:300])
            raise GraphAPIError(
                f"Draft aanmaken mislukt: {resp.status_code}",
                status_code=resp.status_code,
                detail=resp.text[:300],
            )

        message = resp.json()
        message_id = message["id"]
        web_link = message.get("webLink", "")

        logger.info("Draft aangemaakt: message_id=%s", message_id[:30])

        # Stap 2: PDF-bijlage toevoegen
        attachment_url = f"{GRAPH_BASE_URL}/users/{sender_email}/messages/{message_id}/attachments"
        attachment_payload = {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": attachment_name,
            "contentType": "application/pdf",
            "contentBytes": base64.b64encode(attachment_bytes).decode("ascii"),
        }

        att_resp = await client.post(attachment_url, headers=headers, json=attachment_payload)

        if att_resp.status_code not in (200, 201):
            logger.error("Graph bijlage mislukt: %s %s", att_resp.status_code, att_resp.text[:300])
            raise GraphAPIError(
                f"Bijlage toevoegen mislukt: {att_resp.status_code}",
                status_code=att_resp.status_code,
                detail=att_resp.text[:300],
            )

        logger.info("PDF bijlage toegevoegd aan draft (%d bytes)", len(attachment_bytes))

        return {
            "message_id": message_id,
            "web_link": web_link,
        }
