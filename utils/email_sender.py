"""
utils/email_sender.py
Send shortlist notification emails to top candidates.

Primary method  : Brevo API  (free, 300 emails/day, verifies Gmail addresses directly)
Fallback method : SMTP       (for custom / corporate servers)

Uses only Python stdlib (urllib) to avoid urllib3 / LibreSSL compatibility
issues present in this Python 3.9 / macOS environment.
"""

import os
import json as _json
import smtplib
import time
import urllib.request
import urllib.error
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

# ─────────────────────────── Brevo API helpers ───────────────────────────────
_BREVO_BASE = "https://api.brevo.com/v3"


def _brevo_call(method: str, path: str, api_key: str, payload: Optional[dict] = None) -> tuple:
    """
    Make a Brevo API call using urllib (avoids urllib3/LibreSSL issues).
    Returns (http_status: int, body: dict).
    Status 0 means a network/connection-level error.
    """
    body_bytes = _json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(
        f"{_BREVO_BASE}{path}",
        data=body_bytes,
        headers={
            "api-key":      api_key.strip(),   # Brevo uses "api-key", not Bearer
            "Content-Type": "application/json",
            "Accept":       "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            return resp.status, (_json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, _json.loads(raw)
        except Exception:
            return exc.code, {"message": exc.reason}
    except urllib.error.URLError as exc:
        return 0, {"message": str(exc.reason)}
    except Exception as exc:
        return 0, {"message": str(exc)}


def test_brevo_key(api_key: str) -> tuple:
    """
    Verify a Brevo API key by fetching the account info.
    Returns (success: bool, human_readable_message: str).
    """
    if not api_key.strip():
        return False, "API key is empty."

    status, data = _brevo_call("GET", "/account", api_key)

    if status == 200:
        email = data.get("email", "")
        plan  = (data.get("plan") or [{}])[0].get("type", "free")
        return True, f"API key valid — account: {email} ({plan} plan)."
    if status == 401:
        return False, "Invalid API key — copy it from app.brevo.com → SMTP & API → API Keys."
    if status == 0:
        return False, f"Could not reach brevo.com: {data.get('message', 'network error')}."
    return False, f"Unexpected response (HTTP {status}): {data.get('message', '')}."


def send_test_email(api_key: str, from_email: str) -> tuple:
    """
    Send a test email from `from_email` back to itself.
    Validates both the API key AND that `from_email` is a verified sender in Brevo.
    Returns (success: bool, human_readable_message: str).
    """
    if not api_key.strip():
        return False, "API key is empty."
    if not from_email.strip() or "@" not in from_email:
        return False, "Enter a valid From email address first."

    status, data = _brevo_call(
        "POST", "/smtp/email", api_key,
        {
            "sender":      {"name": "TalentSift", "email": from_email.strip()},
            "to":          [{"email": from_email.strip()}],
            "subject":     "✅ TalentSift — email connection verified",
            "htmlContent": (
                "<p style='font-family:sans-serif'>"
                "Your email is working. TalentSift can now send shortlist "
                "notifications to candidates.</p>"
            ),
            "textContent": "Your email is working. TalentSift can now send shortlist notifications.",
        },
    )

    if status in (200, 201, 202):
        return True, f"Test email sent to {from_email} — check your inbox."

    msg = data.get("message") or str(data)
    m   = msg.lower()

    if "sender" in m or "not authorised" in m or "unauthorized" in m or "not verified" in m:
        return False, (
            f"'{from_email}' is not yet a verified sender in Brevo.\n"
            "Fix: Brevo dashboard → Senders & IP → Senders → Add a Sender → "
            f"enter {from_email} → click the verification link in your inbox."
        )
    if status == 401:
        return False, "Invalid API key — copy it from app.brevo.com."
    return False, msg


def _send_one_brevo(
    api_key: str,
    from_email: str,
    from_name: str,
    to_email: str,
    to_name: str,
    subject: str,
    html: str,
    text: str,
) -> tuple:
    """Send one email via Brevo. Returns (success: bool, error: str)."""
    status, data = _brevo_call(
        "POST", "/smtp/email", api_key,
        {
            "sender":      {"name": from_name, "email": from_email},
            "to":          [{"email": to_email, "name": to_name}],
            "subject":     subject,
            "htmlContent": html,
            "textContent": text,
        },
    )
    if status in (200, 201, 202):
        return True, ""
    err = data.get("message") or str(data)
    return False, err


# ─────────────────────────── SMTP fallback ────────────────────────────────────
_ENV_USER     = os.getenv("SMTP_USER",     "")
_ENV_PASSWORD = os.getenv("SMTP_PASSWORD", "")
_ENV_HOST     = os.getenv("SMTP_HOST",     "")
_ENV_PORT     = int(os.getenv("SMTP_PORT", "587"))
_ENV_FROM     = os.getenv("EMAIL_FROM",    _ENV_USER)

DOMAIN_TO_SMTP = {
    "gmail.com":      ("smtp.gmail.com",         587),
    "googlemail.com": ("smtp.gmail.com",         587),
    "outlook.com":    ("smtp-mail.outlook.com",  587),
    "hotmail.com":    ("smtp-mail.outlook.com",  587),
    "live.com":       ("smtp-mail.outlook.com",  587),
    "yahoo.com":      ("smtp.mail.yahoo.com",     587),
    "icloud.com":     ("smtp.mail.me.com",        587),
}


def smtp_for_email(email: str) -> Optional[tuple]:
    domain = email.strip().lower().split("@")[-1] if "@" in email else ""
    return DOMAIN_TO_SMTP.get(domain)


def _smtp_resolve(smtp_config: Optional[dict]) -> tuple:
    cfg       = smtp_config or {}
    user      = cfg.get("user")     or _ENV_USER
    password  = cfg.get("password") or _ENV_PASSWORD
    from_addr = cfg.get("from_addr") or _ENV_FROM or user
    if cfg.get("host"):
        host, port = cfg["host"], int(cfg.get("port") or 587)
    else:
        detected   = smtp_for_email(user) if user else None
        host, port = detected if detected else (_ENV_HOST or "smtp.gmail.com", _ENV_PORT)
    return host, port, user, password, from_addr


def test_smtp_connection(smtp_config: dict) -> tuple:
    host, port, user, password, _ = _smtp_resolve(smtp_config)
    if not user or not password:
        return False, "Email and password are required."
    try:
        server = smtplib.SMTP(host, port, timeout=10)
        server.ehlo(); server.starttls(); server.login(user, password); server.quit()
        return True, f"Connected as {user}."
    except smtplib.SMTPAuthenticationError:
        return False, "Authentication failed."
    except Exception as exc:
        return False, f"Error: {exc}"


# ─────────────────────────── Email body ──────────────────────────────────────
def _build_email_body(candidate_name: str, job_title: str, recruiter_name: str) -> tuple:
    plain = f"""Hello {candidate_name},

Congratulations!

We are delighted to inform you that, following our initial screening process,
you have been shortlisted for the next stage of our recruitment process for
the position of {job_title}.

Our team was impressed by your profile and we look forward to learning more
about you. You will receive further details regarding the next steps shortly.

If you have any questions in the meantime, please feel free to reply to this email.

Best regards,
{recruiter_name}
"""
    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: 'Helvetica Neue', Arial, sans-serif; background:#f5f5f5; margin:0; padding:0; }}
    .wrapper {{ max-width:560px; margin:40px auto; background:#ffffff; border-radius:10px;
                box-shadow:0 2px 12px rgba(0,0,0,.08); overflow:hidden; }}
    .header {{ background:linear-gradient(135deg,#6366F1,#8B5CF6); padding:36px 32px; }}
    .header h1 {{ color:#fff; font-size:22px; margin:0; }}
    .header p  {{ color:rgba(255,255,255,.75); font-size:13px; margin:6px 0 0; }}
    .body {{ padding:32px; color:#374151; line-height:1.7; font-size:15px; }}
    .body h2 {{ color:#111827; font-size:18px; margin-top:0; }}
    .badge {{ display:inline-block; background:#EEF2FF; color:#6366F1; border-radius:6px;
              padding:4px 12px; font-size:13px; font-weight:600; margin-bottom:18px; }}
    .footer {{ background:#F9FAFB; padding:18px 32px; font-size:12px; color:#9CA3AF;
               border-top:1px solid #E5E7EB; }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <h1>🎯 TalentSift</h1>
      <p>Recruitment Screening Platform</p>
    </div>
    <div class="body">
      <h2>Hello {candidate_name},</h2>
      <p>Congratulations! 🎉</p>
      <div class="badge">✅ Application Shortlisted</div>
      <p>
        You have been <strong>shortlisted for the next stage</strong> of our
        recruitment process for <strong>{job_title}</strong>.
      </p>
      <p>You will receive further details regarding the next steps shortly.</p>
      <p>If you have any questions, please reply to this email.</p>
      <p style="margin-top:28px">Best regards,<br><strong>{recruiter_name}</strong></p>
    </div>
    <div class="footer">
      You received this because you applied for a role we are recruiting for.
    </div>
  </div>
</body>
</html>"""
    return plain, html


# ─────────────────────────── Main send function ───────────────────────────────
def send_shortlist_emails(
    candidates: list,
    job_title: str,
    recruiter_name: str,
    brevo_api_key: str = "",
    from_email: str = "",
    smtp_config: Optional[dict] = None,
) -> dict:
    """
    Send shortlist emails.

    Preferred : brevo_api_key + from_email  →  Brevo API (no password needed).
    Fallback  : smtp_config dict            →  SMTP.
    """
    report: dict = {"sent": [], "failed": [], "skipped": []}

    # ── Brevo path ────────────────────────────────────────────────────────────
    if brevo_api_key and from_email:
        for candidate in candidates:
            to_addr = (candidate.get("email") or "").strip()
            cname   = candidate.get("candidate_name", "Candidate")

            if not to_addr or "@" not in to_addr:
                report["skipped"].append(cname)
                continue

            plain, html = _build_email_body(cname, job_title, recruiter_name)
            ok, err = _send_one_brevo(
                api_key    = brevo_api_key,
                from_email = from_email,
                from_name  = recruiter_name,
                to_email   = to_addr,
                to_name    = cname,
                subject    = f"Application Shortlisted — {job_title}",
                html       = html,
                text       = plain,
            )
            if ok:
                report["sent"].append(to_addr)
                time.sleep(0.2)
            else:
                print(f"[email_sender] Brevo failed → {to_addr}: {err}")
                report["failed"].append(to_addr)
        return report

    # ── SMTP fallback ─────────────────────────────────────────────────────────
    host, port, user, password, from_addr = _smtp_resolve(smtp_config)
    if not user or not password:
        report["failed"] = [c.get("email", "?") for c in candidates if c.get("email")]
        return report

    try:
        server = smtplib.SMTP(host, port, timeout=10)
        server.ehlo(); server.starttls(); server.login(user, password)
    except Exception as exc:
        print(f"[email_sender] SMTP connect failed: {exc}")
        report["failed"] = [c.get("email", "?") for c in candidates if c.get("email")]
        return report

    for candidate in candidates:
        to_addr = (candidate.get("email") or "").strip()
        cname   = candidate.get("candidate_name", "Candidate")
        if not to_addr or "@" not in to_addr:
            report["skipped"].append(cname); continue
        plain, html = _build_email_body(cname, job_title, recruiter_name)
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Application Shortlisted — {job_title}"
        msg["From"]    = from_addr
        msg["To"]      = to_addr
        msg.attach(MIMEText(plain, "plain", "utf-8"))
        msg.attach(MIMEText(html,  "html",  "utf-8"))
        try:
            server.sendmail(from_addr, to_addr, msg.as_string())
            report["sent"].append(to_addr)
            time.sleep(0.3)
        except Exception as exc:
            print(f"[email_sender] SMTP send failed → {to_addr}: {exc}")
            report["failed"].append(to_addr)

    try:
        server.quit()
    except Exception:
        pass

    return report
