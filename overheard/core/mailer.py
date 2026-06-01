"""Generic email sender over SMTP (point SMTP_* at Resend's relay)."""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from django.conf import settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, html: str, text: str = "") -> bool:
    if not all([settings.SMTP_HOST, settings.SMTP_USER, settings.SMTP_PASS, settings.FROM_EMAIL]):
        logger.warning("SMTP settings incomplete — cannot send.")
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, settings.FROM_EMAIL, to
    msg.attach(MIMEText(text or html, "plain"))
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as s:
            s.ehlo(); s.starttls(); s.login(settings.SMTP_USER, settings.SMTP_PASS)
            s.sendmail(settings.FROM_EMAIL, to, msg.as_string())
        logger.info("Email sent to %s", to)
        return True
    except Exception as exc:
        logger.error("Email send failed: %s", exc)
        return False