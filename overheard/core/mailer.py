"""Generic email sender via the Resend HTTP API (https://resend.com).

Uses Resend's REST endpoint over HTTPS (port 443) instead of SMTP, so it works
on hosts that block outbound SMTP ports — including Render's free tier.
Only two settings are needed: RESEND_API_KEY and FROM_EMAIL.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_RESEND_URL = "https://api.resend.com/emails"


def send_email(to: str, subject: str, html: str, text: str = "") -> bool:
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — cannot send.")
        return False
    if not settings.FROM_EMAIL:
        logger.warning("FROM_EMAIL not set — cannot send.")
        return False

    payload = {
        "from": settings.FROM_EMAIL,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text

    try:
        resp = requests.post(
            _RESEND_URL,
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        logger.info("Email sent to %s (Resend id=%s)", to, resp.json().get("id", "?"))
        return True
    except Exception as exc:
        # Surface Resend's error body — it's specific (unverified domain, bad key, rate limit).
        body = getattr(getattr(exc, "response", None), "text", "")
        logger.error("Email send failed: %s %s", exc, body)
        return False