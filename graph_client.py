"""
Microsoft Graph API client — maak concept e-mails aan in Outlook met bijlagen.

Gebruikt client_credentials flow (application permissions, geen per-user OAuth).
Vereist Azure Entra ID app-registratie met Mail.ReadWrite toestemming.
"""

import base64
import logging
from typing import Optional

import httpx

from graph_auth import (
    GRAPH_BASE_URL,
    GraphAPIError,
    get_access_token,
    is_configured,
)

logger = logging.getLogger("nat-api.graph")

# Re-export voor backward compatibility
__all__ = ["GraphAPIError", "is_configured", "create_draft_with_attachment"]


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
    token = await get_access_token()
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
