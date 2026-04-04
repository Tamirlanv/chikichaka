"""Central Resend HTML email delivery (shared by auth, stage notifications, etc.)."""

from __future__ import annotations

import logging

import resend

from invision_api.core.config import get_settings

logger = logging.getLogger(__name__)


def send_html_email(to_email: str, subject: str, html: str) -> bool:
    """
    Send a transactional email via Resend.

    Returns True if the send was attempted and Resend accepted the request.
    Returns False if RESEND_API_KEY is missing (logged) or on failure (logged, no exception).
    """
    settings = get_settings()
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY is not set; skipping email to %s (subject=%s)", to_email, subject)
        return False
    try:
        resend.api_key = settings.resend_api_key
        resend.Emails.send(
            {
                "from": settings.email_from,
                "to": [to_email],
                "subject": subject,
                "html": html,
            }
        )
        return True
    except Exception:
        logger.exception("send_html_email failed to=%s subject=%s", to_email, subject)
        return False
