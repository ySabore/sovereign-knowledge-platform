"""SMTP invite email sender (best effort, non-blocking for API success)."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse

from app.config import settings

logger = logging.getLogger(__name__)


def _build_invite_url(token: str) -> str:
    base = (settings.invite_accept_url_base or "").strip()
    if not base:
        return token
    if "{token}" in base:
        return base.replace("{token}", token)
    parsed = urlparse(base)
    qs = dict(parse_qsl(parsed.query, keep_blank_values=True))
    qs["token"] = token
    return urlunparse(parsed._replace(query=urlencode(qs)))


def send_organization_invite_email(
    *,
    to_email: str,
    organization_name: str,
    role: str,
    inviter_email: str | None,
    token: str,
) -> bool:
    """
    Send invite email via SMTP.

    Returns True when sent, False when disabled/misconfigured/failed.
    """
    if not settings.invite_email_enabled:
        return False
    if not settings.smtp_host or not settings.smtp_from_email:
        logger.warning("invite email enabled but SMTP host/from_email missing")
        return False

    invite_url = _build_invite_url(token)
    role_label = "Admin" if role == "org_owner" else "Member"
    inviter_line = f"Invited by: {inviter_email}\n" if inviter_email else ""
    subject = f"Invitation to join {organization_name} on Sovereign Knowledge"
    body = (
        f"Hello,\n\n"
        f"You were invited to join '{organization_name}' as {role_label}.\n"
        f"{inviter_line}"
        f"Accept invite: {invite_url}\n\n"
        f"If the link does not open, use this token manually:\n{token}\n\n"
        f"This invite may expire in 7 days.\n"
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    msg["To"] = to_email
    msg.set_content(body)

    try:
        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
                if settings.smtp_username:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
                if settings.smtp_use_starttls:
                    smtp.starttls()
                if settings.smtp_username:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(msg)
        return True
    except Exception as exc:  # pragma: no cover - network dependent
        logger.warning("invite email send failed: %s", exc)
        return False
