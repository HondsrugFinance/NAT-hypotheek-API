"""Email intake monitor — poll mailboxen via Graph API, upload bijlagen naar _inbox.

Checkt alle geconfigureerde mailboxen op recente emails met bijlagen.
Alleen emails van bekende klanten (match op emailadres in dossier) worden verwerkt.
Emails van banken, verzekeraars, notarissen, etc. worden genegeerd.
"""

import base64
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

import httpx

from graph_auth import GRAPH_BASE_URL, GraphAPIError, get_access_token, is_configured
from email_intake.matcher import match_sender_to_dossier
from sharepoint import client as sp_client

logger = logging.getLogger("nat-api.email-intake")

# Configuratie
EMAIL_INTAKE_MAILBOXES = os.environ.get(
    "EMAIL_INTAKE_MAILBOXES",
    "alex@hondsrugfinance.nl,quido@hondsrugfinance.nl,stephan@hondsrugfinance.nl,info@hondsrugfinance.nl",
)
EMAIL_INTAKE_ENABLED = os.environ.get("EMAIL_INTAKE_ENABLED", "false").lower() == "true"

# Hoe ver terug kijken bij elke poll (minuten). Ruime marge zodat we niets missen
# bij korte downtime of trage poll. Deduplicatie via email_intake_log voorkomt
# dubbele verwerking.
LOOKBACK_MINUTES = int(os.environ.get("EMAIL_INTAKE_LOOKBACK_MINUTES", "10"))

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

# Bestandsvalidatie (zelfde als document_api/service.py)
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/msword",
    "application/vnd.ms-excel",
}

MIN_FILE_SIZE = 10 * 1024        # 10 KB
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB


def _sb_headers() -> dict:
    key = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


async def _log_email(
    message_id: str,
    sender_email: str,
    subject: str,
    dossier_id: str | None,
    status: str,
    attachments_count: int = 0,
    error_message: str | None = None,
):
    """Log email verwerking in email_intake_log tabel."""
    record = {
        "message_id": message_id,
        "sender_email": sender_email,
        "subject": subject[:500] if subject else None,
        "dossier_id": dossier_id,
        "status": status,
        "attachments_count": attachments_count,
    }
    if error_message:
        record["error_message"] = error_message[:1000]

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/email_intake_log",
                headers={**_sb_headers(), "Prefer": "return=minimal"},
                json=record,
            )
            resp.raise_for_status()
    except Exception as e:
        logger.warning("Email intake log schrijven mislukt: %s", e)


def _is_internal_sender(sender_email: str) -> bool:
    """Check of afzender een intern @hondsrugfinance.nl adres is."""
    return sender_email.lower().strip().endswith("@hondsrugfinance.nl")


def _get_inbox_pad(dossier: dict) -> str | None:
    """Extract het _inbox pad uit de SharePoint URL van een dossier."""
    sharepoint_url = dossier.get("sharepoint_url", "")
    if not sharepoint_url or sharepoint_url == "pending":
        return None
    decoded = unquote(sharepoint_url)
    match = re.search(r"1\.Klanten/([^?]+)", decoded)
    if not match:
        return None
    mapnaam = match.group(1).rstrip("/")
    return f"{sp_client.SHAREPOINT_KLANTEN_ROOT}/{mapnaam}/_inbox"


async def poll_mailbox(mailbox: str) -> dict:
    """Poll één mailbox voor recente emails met bijlagen van bekende klanten.

    Filtert op ontvangstdatum (laatste LOOKBACK_MINUTES minuten) in plaats van
    gelezen/ongelezen, zodat ook al geopende emails worden opgepakt.
    Deduplicatie via email_intake_log voorkomt dubbele verwerking.

    Alleen emails van afzenders die matchen met een actief dossier worden
    verwerkt. Alle andere emails (banken, notarissen, etc.) worden genegeerd.

    Returns:
        dict met statistieken.
    """
    stats = {"mailbox": mailbox, "checked": 0, "matched": 0, "uploaded": 0, "skipped": 0, "errors": 0}

    token = await get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Filter: emails ontvangen in de laatste LOOKBACK_MINUTES, met bijlagen
    since = (datetime.now(timezone.utc) - timedelta(minutes=LOOKBACK_MINUTES)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = (
        f"{GRAPH_BASE_URL}/users/{mailbox}/messages"
        f"?$filter=receivedDateTime ge {since} and hasAttachments eq true"
        "&$select=id,from,subject,receivedDateTime,hasAttachments"
        "&$orderby=receivedDateTime desc"
        "&$top=50"
    )

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            logger.warning("Mailbox %s ophalen mislukt: %s", mailbox, resp.status_code)
            stats["errors"] += 1
            return stats
        messages = resp.json().get("value", [])

    for msg in messages:
        message_id = msg["id"]
        sender_email = msg.get("from", {}).get("emailAddress", {}).get("address", "")
        subject = msg.get("subject", "")

        stats["checked"] += 1

        # Skip interne afzenders
        if _is_internal_sender(sender_email):
            stats["skipped"] += 1
            continue

        # Deduplicatie: al eerder verwerkt?
        if await _is_already_processed(message_id):
            stats["skipped"] += 1
            continue

        # Kernfilter: alleen verwerken als afzender een bekende klant is.
        # Emails van banken, notarissen, verzekeraars etc. worden genegeerd.
        dossier = await match_sender_to_dossier(sender_email)

        if not dossier:
            # Geen match = niet onze klant = negeren (niet loggen)
            stats["skipped"] += 1
            continue

        stats["matched"] += 1
        dossier_id = dossier["id"]

        # Haal _inbox pad op
        inbox_pad = _get_inbox_pad(dossier)
        if not inbox_pad:
            await _log_email(message_id, sender_email, subject, dossier_id, "error",
                             error_message="Geen SharePoint _inbox pad")
            stats["errors"] += 1
            continue

        # Download en upload bijlagen
        uploaded_count = await _process_attachments(
            mailbox, message_id, dossier_id, inbox_pad, headers,
        )
        stats["uploaded"] += uploaded_count

        # Log succesvolle verwerking
        await _log_email(message_id, sender_email, subject, dossier_id, "processed",
                         attachments_count=uploaded_count)

        # Concept-bevestigingsmail voor adviseur
        if uploaded_count > 0:
            try:
                await _create_confirmation_draft(
                    mailbox, sender_email, subject, dossier, uploaded_count,
                )
            except Exception as e:
                logger.warning("Bevestigingsmail aanmaken mislukt: %s", e)

        logger.info(
            "Email van %s verwerkt: %d bijlagen → dossier %s",
            sender_email, uploaded_count, dossier.get("dossiernummer", "?"),
        )

    return stats


async def _is_already_processed(message_id: str) -> bool:
    """Check of dit Graph message_id al in de log staat."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/email_intake_log",
                headers=_sb_headers(),
                params={
                    "select": "id",
                    "message_id": f"eq.{message_id}",
                    "limit": "1",
                },
            )
            resp.raise_for_status()
            return bool(resp.json())
    except Exception:
        return False


async def _process_attachments(
    mailbox: str,
    message_id: str,
    dossier_id: str,
    inbox_pad: str,
    headers: dict,
) -> int:
    """Download bijlagen en upload naar SharePoint _inbox.

    Returns:
        Aantal succesvol geüploade bestanden.
    """
    url = f"{GRAPH_BASE_URL}/users/{mailbox}/messages/{message_id}/attachments"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            logger.warning("Bijlagen ophalen mislukt: %s", resp.status_code)
            return 0
        attachments = resp.json().get("value", [])

    uploaded = 0
    sb_headers = _sb_headers()

    for att in attachments:
        # Skip inline images (e-mail handtekeningen)
        if att.get("isInline", False):
            continue

        att_name = att.get("name", "")
        content_type = att.get("contentType", "application/octet-stream")
        content_bytes_b64 = att.get("contentBytes", "")

        if not content_bytes_b64 or not att_name:
            continue

        # Decodeer base64 content
        try:
            content = base64.b64decode(content_bytes_b64)
        except Exception:
            logger.warning("Base64 decode mislukt voor bijlage: %s", att_name)
            continue

        # Valideer bestandsgrootte
        if len(content) < MIN_FILE_SIZE:
            continue
        if len(content) > MAX_FILE_SIZE:
            logger.warning("Bijlage %s te groot (%d bytes), overgeslagen", att_name, len(content))
            continue

        # Valideer MIME type (probeer ook op extensie)
        if content_type not in ALLOWED_MIME_TYPES:
            ext = att_name.rsplit(".", 1)[-1].lower() if "." in att_name else ""
            ext_to_mime = {
                "pdf": "application/pdf",
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "png": "image/png",
                "tiff": "image/tiff",
                "tif": "image/tiff",
                "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }
            content_type = ext_to_mime.get(ext, content_type)
            if content_type not in ALLOWED_MIME_TYPES:
                continue

        # Upload naar SharePoint _inbox
        try:
            await sp_client.upload_file(inbox_pad, att_name, content, content_type)
        except GraphAPIError as e:
            logger.warning("SharePoint upload mislukt voor %s: %s", att_name, e.message)
            continue

        # Registreer in documents tabel (triggert webhook → automatische verwerking)
        doc_record = {
            "dossier_id": dossier_id,
            "bestandsnaam": att_name,
            "sharepoint_pad": f"{inbox_pad}/{att_name}",
            "bron": "email",
            "status": "pending",
            "mime_type": content_type,
            "bestandsgrootte": len(content),
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{SUPABASE_URL}/rest/v1/documents",
                    headers={**sb_headers, "Prefer": "return=minimal"},
                    json=doc_record,
                )
                resp.raise_for_status()
                uploaded += 1
        except Exception as e:
            logger.warning("Document registratie mislukt voor %s: %s", att_name, e)

    return uploaded


async def _create_confirmation_draft(
    advisor_mailbox: str,
    klant_email: str,
    original_subject: str,
    dossier: dict,
    attachment_count: int,
):
    """Maak concept-bevestigingsmail aan in Outlook van de adviseur."""
    from email_templates import _signature_html

    klant_naam = dossier.get("klant_naam", "")

    # Voornaam uit contactgegevens of klantnaam
    contact = dossier.get("klant_contact_gegevens") or {}
    aanvrager = contact.get("aanvrager", {})
    voornaam = aanvrager.get("voornaam", "")
    if not voornaam and klant_naam:
        voornaam = klant_naam.split(",")[1].strip() if "," in klant_naam else klant_naam

    subject = f"Re: {original_subject}" if original_subject else "Documenten ontvangen"

    doc_tekst = "het document" if attachment_count == 1 else f"de {attachment_count} documenten"
    ref_tekst = "het" if attachment_count == 1 else "deze"

    body_html = f"""\
<p>Beste {voornaam},</p>

<p>Bedankt voor het aanleveren van {doc_tekst}.
We hebben {ref_tekst} in goede orde ontvangen en toegevoegd aan uw dossier.</p>

<p>Mochten er nog aanvullende documenten nodig zijn, dan laten we dat uiteraard weten.</p>

{_signature_html(advisor_mailbox)}
"""

    token = await get_access_token()
    headers_graph = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    message_payload = {
        "subject": subject,
        "body": {"contentType": "HTML", "content": body_html},
        "toRecipients": [{"emailAddress": {"address": klant_email}}],
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{GRAPH_BASE_URL}/users/{advisor_mailbox}/messages",
            headers=headers_graph,
            json=message_payload,
        )
        if resp.status_code not in (200, 201):
            logger.warning("Bevestigings-draft mislukt: %s", resp.status_code)
            return

    logger.info("Bevestigings-concept aangemaakt in %s voor %s", advisor_mailbox, klant_email)


async def poll_all_mailboxes() -> list[dict]:
    """Poll alle geconfigureerde mailboxen.

    Returns:
        Lijst met statistieken per mailbox.
    """
    if not EMAIL_INTAKE_ENABLED:
        return [{"status": "disabled"}]

    if not is_configured():
        return [{"status": "error", "reason": "azure_not_configured"}]

    if not sp_client.is_configured():
        return [{"status": "error", "reason": "sharepoint_not_configured"}]

    mailboxes = [m.strip() for m in EMAIL_INTAKE_MAILBOXES.split(",") if m.strip()]

    results = []
    for mailbox in mailboxes:
        try:
            stats = await poll_mailbox(mailbox)
            results.append(stats)
        except Exception as e:
            logger.error("Polling mailbox %s mislukt: %s", mailbox, e)
            results.append({"mailbox": mailbox, "status": "error", "error": str(e)})

    return results
