"""
Compose and send the digest via email (SMTP) and Slack webhook.
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from django.conf import settings
from django.utils import timezone

from .models import MatchedItem

logger = logging.getLogger(__name__)


def _render_html(items):
    rows = ""
    for item in items:
        platform_label = item.get_platform_display()
        rows += f"""
        <div style="border:1px solid #e5e7eb;border-radius:8px;padding:20px;margin-bottom:20px;font-family:system-ui,sans-serif;">
          <div style="display:flex;gap:10px;align-items:center;margin-bottom:8px;">
            <span style="background:#ede9fe;color:#6d28d9;border-radius:4px;padding:2px 8px;font-size:12px;font-weight:600;">{platform_label}</span>
            <span style="color:#6b7280;font-size:13px;">by {item.author}</span>
            <span style="background:#dcfce7;color:#166534;border-radius:4px;padding:2px 8px;font-size:12px;font-weight:600;">Score {item.score}</span>
          </div>
          <p style="margin:0 0 10px;color:#374151;font-size:14px;">{item.text_snippet[:400]}</p>
          <p style="margin:0 0 4px;font-size:13px;color:#111827;"><strong>Why it matters:</strong> {item.why_relevant}</p>
          <p style="margin:0 0 4px;font-size:13px;color:#111827;"><strong>What they want:</strong> {item.what_theyre_asking}</p>
          <p style="margin:0 0 10px;font-size:13px;color:#111827;"><strong>Angle:</strong> {item.suggested_angle}</p>
          <a href="{item.source_url}" style="font-size:13px;color:#4f46e5;">View original →</a>
        </div>"""
    return f"""<html><body style="max-width:640px;margin:40px auto;font-family:system-ui,sans-serif;">
    <h2 style="color:#1a1a2e;">Overheard digest — {len(items)} new match{"es" if len(items) != 1 else ""}</h2>
    {rows}
    <p style="color:#9ca3af;font-size:12px;margin-top:40px;">These posts were found and scored automatically. No replies have been sent.</p>
    </body></html>"""


def _render_text(items):
    lines = [f"Overheard digest — {len(items)} new match{'es' if len(items) != 1 else ''}\n"]
    for item in items:
        lines.append(f"[{item.get_platform_display()}] @{item.author}  Score: {item.score}")
        lines.append(f"  {item.text_snippet[:200]}")
        lines.append(f"  Why: {item.why_relevant}")
        lines.append(f"  Asking: {item.what_theyre_asking}")
        lines.append(f"  Angle: {item.suggested_angle}")
        lines.append(f"  Link: {item.source_url}\n")
    return "\n".join(lines)


def send_email_digest(items: list) -> bool:
    if not all([settings.SMTP_HOST, settings.SMTP_USER, settings.SMTP_PASS,
                settings.FROM_EMAIL, settings.DIGEST_TO_EMAIL]):
        logger.warning("SMTP not fully configured — skipping email digest.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Overheard: {len(items)} new match{'es' if len(items) != 1 else ''}"
    msg["From"] = settings.FROM_EMAIL
    msg["To"] = settings.DIGEST_TO_EMAIL
    msg.attach(MIMEText(_render_text(items), "plain"))
    msg.attach(MIMEText(_render_html(items), "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASS)
            server.sendmail(settings.FROM_EMAIL, settings.DIGEST_TO_EMAIL, msg.as_string())
        logger.info("Email digest sent to %s", settings.DIGEST_TO_EMAIL)
        return True
    except Exception as exc:
        logger.error("Email digest failed: %s", exc)
        return False


def send_slack_digest(items: list) -> bool:
    if not settings.SLACK_WEBHOOK_URL:
        logger.info("SLACK_WEBHOOK_URL not set — skipping Slack digest.")
        return False

    blocks = [{
        "type": "header",
        "text": {"type": "plain_text", "text": f"Overheard: {len(items)} new match{'es' if len(items) != 1 else ''}"},
    }]
    for item in items[:10]:  # Slack blocks have a 50-block limit; cap at 10 items
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*[{item.get_platform_display()}]* @{item.author} — score {item.score}\n"
                    f"_{item.text_snippet[:200]}_\n"
                    f"*Why:* {item.why_relevant}\n"
                    f"*Asking:* {item.what_theyre_asking}\n"
                    f"*Angle:* {item.suggested_angle}"
                ),
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "View"},
                "url": item.source_url,
            },
        })

    try:
        resp = requests.post(settings.SLACK_WEBHOOK_URL, json={"blocks": blocks}, timeout=10)
        resp.raise_for_status()
        logger.info("Slack digest sent.")
        return True
    except Exception as exc:
        logger.error("Slack digest failed: %s", exc)
        return False


def send_digest() -> dict:
    """
    Find all NEW items, send email + Slack, mark them as SENT.
    Returns a summary dict.
    """
    items = list(MatchedItem.objects.filter(status=MatchedItem.Status.NEW).order_by('-score', '-fetched_at'))
    if not items:
        logger.info("No new items to digest.")
        return {"items": 0, "email": False, "slack": False}

    email_ok = send_email_digest(items)
    slack_ok = send_slack_digest(items)

    now = timezone.now()
    for item in items:
        item.status = MatchedItem.Status.SENT
        item.sent_at = now
    MatchedItem.objects.bulk_update(items, ["status", "sent_at"])

    return {"items": len(items), "email": email_ok, "slack": slack_ok}
