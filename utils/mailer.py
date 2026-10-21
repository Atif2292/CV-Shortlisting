"""
utils/mailer.py
Transactional email (sign-in codes) via Brevo API or SMTP with verified TLS.
"""

import json
import logging
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage
from html import escape

from utils import config

log = logging.getLogger(__name__)


def email_configured() -> bool:
    return bool(config.BREVO_API_KEY or (config.SMTP_HOST and config.SMTP_USER
                                         and config.SMTP_PASSWORD and config.EMAIL_FROM))


def _clean_header(value: str) -> str:
    return " ".join(str(value).replace("\r", " ").replace("\n", " ").split())


def _send_brevo(to_addr: str, subject: str, text: str, html: str) -> bool:
    payload = {
        "sender": {"email": config.EMAIL_FROM, "name": "RankCV"},
        "to": [{"email": to_addr}],
        "subject": subject,
        "textContent": text,
        "htmlContent": html,
    }
    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode("utf-8"),
        headers={"api-key": config.BREVO_API_KEY, "Content-Type": "application/json",
                 "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError):
        log.exception("Brevo send failed")
        return False


def _send_smtp(to_addr: str, subject: str, text: str, html: str) -> bool:
    msg = EmailMessage()
    msg["From"] = _clean_header(f"RankCV <{config.EMAIL_FROM}>")
    msg["To"] = _clean_header(to_addr)
    msg["Subject"] = _clean_header(subject)
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    ctx = ssl.create_default_context()
    try:
        if config.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=15, context=ctx) as s:
                s.login(config.SMTP_USER, config.SMTP_PASSWORD)
                s.send_message(msg)
        else:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as s:
                s.starttls(context=ctx)
                s.login(config.SMTP_USER, config.SMTP_PASSWORD)
                s.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError):
        log.exception("SMTP send failed")
        return False


def send_login_code(to_addr: str, code: str) -> bool:
    """Send a one-time sign-in code. Returns True if the provider accepted it."""
    subject = f"Your RankCV sign-in code: {code}"
    text = (
        f"Your RankCV sign-in code is {code}\n\n"
        "It expires in 10 minutes. If you didn't request it, you can ignore this email.\n"
    )
    html = (
        "<div style=\"font-family:Arial,sans-serif;font-size:15px;color:#0F172A\">"
        "<p>Your RankCV sign-in code is:</p>"
        f"<p style=\"font-size:28px;font-weight:700;letter-spacing:6px\">{escape(code)}</p>"
        "<p style=\"color:#64748B\">It expires in 10 minutes. If you didn't request it, you can ignore this email.</p>"
        "</div>"
    )
    if config.BREVO_API_KEY:
        return _send_brevo(to_addr, subject, text, html)
    if email_configured():
        return _send_smtp(to_addr, subject, text, html)
    return False
