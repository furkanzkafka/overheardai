"""
Compose and send the daily digest via email (SMTP) and Slack webhook.
Notification targets are read from NotificationSettings (DB) first,
falling back to environment variables.
"""
import logging

import requests
from django.conf import settings
from django.utils import timezone

from .mailer import send_email
from .models import MatchedItem, NotificationSettings

logger = logging.getLogger(__name__)


def _notif_settings():
    try:
        return NotificationSettings.get()
    except Exception:
        return None

def _render_html(items, heading=None):
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
    head = heading or f'Overheard digest — {len(items)} new match{"es" if len(items) != 1 else ""}'
    return f"""<html><body style="max-width:640px;margin:40px auto;font-family:system-ui,sans-serif;">
    <h2 style="color:#1a1a2e;">{head}</h2>
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
    ns = _notif_settings()
    to_email = (ns.digest_to_email if ns else '') or settings.DIGEST_TO_EMAIL

    if not to_email:
        logger.info("No digest email configured — skipping email.")
        return False

    subject = f"Overheard: {len(items)} new match{'es' if len(items) != 1 else ''}"
    return send_email(to_email, subject, _render_html(items), _render_text(items))


def send_slack_digest(items: list) -> bool:
    ns = _notif_settings()
    webhook = (ns.slack_webhook_url if ns else '') or settings.SLACK_WEBHOOK_URL

    if not webhook:
        logger.info("No Slack webhook configured — skipping.")
        return False

    blocks = [{
        "type": "header",
        "text": {"type": "plain_text", "text": f"Overheard: {len(items)} new match{'es' if len(items) != 1 else ''}"},
    }]
    for item in items[:10]:
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
        resp = requests.post(webhook, json={"blocks": blocks}, timeout=10)
        resp.raise_for_status()
        logger.info("Slack digest sent.")
        return True
    except Exception as exc:
        logger.error("Slack digest failed: %s", exc)
        return False


def send_digest() -> dict:
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

def send_code(email, code):
    html = (
        '<div style="font-family:Georgia,serif;max-width:420px;margin:40px auto;color:#1b2232;">'
        '<p style="font-size:15px;">Your Overheard verification code:</p>'
        f'<p style="font-size:34px;letter-spacing:8px;font-weight:700;color:#b6452b;margin:10px 0;">{code}</p>'
        '<p style="font-size:13px;color:#6b7280;">It expires in 10 minutes. If you didn\'t request this, ignore it.</p>'
        '</div>'
    )
    text = f"Your Overheard verification code is {code}. It expires in 10 minutes."
    return send_email(email, "Your Overheard code", html, text)


def send_welcome(topic):
    if not topic.email:
        return False
    items = list(
        MatchedItem.objects.filter(topic=topic, status=MatchedItem.Status.NEW)
        .order_by('-score', '-fetched_at')
    )
    n = len(items)
    subject = "Overheard is listening — your first batch"
    if items:
        heading = f"You're all set — {n} conversation{'s' if n != 1 else ''} to start"
        html, text = _render_html(items, heading=heading), _render_text(items)
    else:
        html = ('<div style="font-family:Georgia,serif;max-width:560px;margin:40px auto;color:#1b2232;">'
                '<h2>You\'re all set.</h2><p style="color:#4f5260;">We\'re listening now. The moment someone '
                'starts looking for what you do, they\'ll land in your morning digest.</p></div>')
        text = "You're all set. We're listening — your first matches will arrive in the morning digest."
    return send_email(topic.email, subject, html, text)