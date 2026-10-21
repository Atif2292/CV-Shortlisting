"""
utils/config.py
Single source of truth for settings, plan limits and business details.

Values come from environment variables first, then Streamlit secrets
(.streamlit/secrets.toml or the hosting provider's secrets UI).
"""

import os


def get_setting(name: str, default: str = "") -> str:
    val = os.getenv(name)
    if val is not None and str(val).strip():
        return str(val).strip()
    try:
        import streamlit as st
        if name in st.secrets and str(st.secrets[name]).strip():
            return str(st.secrets[name]).strip()
    except Exception:
        pass
    return default


def _int_setting(name: str, default: int) -> int:
    try:
        return int(get_setting(name, str(default)))
    except ValueError:
        return default


# ── Environment ──────────────────────────────────────────────────────────────
APP_ENV = get_setting("APP_ENV", "development").lower()
IS_PRODUCTION = APP_ENV == "production"
# Local development only: show sign-in codes on screen when no email provider is configured.
# Also requires the browser to be on localhost (see app.py), so it can never work on a public URL.
DEV_SHOW_LOGIN_CODE = (not IS_PRODUCTION) and get_setting("DEV_SHOW_LOGIN_CODE", "false").lower() == "true"
APP_URL = get_setting("APP_URL", "http://localhost:8501")

# Used to hash login codes. MUST be set to a long random value in production.
APP_SECRET = get_setting("APP_SECRET", "dev-only-insecure-secret")

# SQLAlchemy URL, e.g. postgresql+psycopg://user:pass@host:5432/rankcv
DATABASE_URL = get_setting("DATABASE_URL", "sqlite:///data/rankcv.db")

# ── Plans ────────────────────────────────────────────────────────────────────
PLAN_QUOTAS = {
    "trial":  _int_setting("TRIAL_CVS", 10),
    "pro":    _int_setting("PRO_CVS_PER_MONTH", 500),
    "agency": _int_setting("AGENCY_CVS_PER_MONTH", 1500),
}
PLAN_LABELS = {
    "trial":  "Free Trial",
    "pro":    "Professional",
    "agency": "Agency",
}
PLAN_PRICES_GBP = {"pro": 99, "agency": 199}

# Largest batch a single screening run accepts (keeps a run within a few minutes)
MAX_BATCH_CVS = _int_setting("MAX_BATCH_CVS", 100)
# Per-file limit enforced in code (Streamlit's maxUploadSize is the hard cap)
MAX_FILE_MB = _int_setting("MAX_FILE_MB", 10)

# Free-trial anti-abuse: refuse free webmail domains for trials (paid plans unaffected)
TRIAL_REQUIRE_WORK_EMAIL = get_setting("TRIAL_REQUIRE_WORK_EMAIL", "true").lower() == "true"

# ── Stripe ───────────────────────────────────────────────────────────────────
STRIPE_SECRET_KEY = get_setting("STRIPE_SECRET_KEY")
# Comma-separated Stripe Price IDs (monthly and/or annual) that grant each plan
STRIPE_PRICES_PRO = [p.strip() for p in get_setting("STRIPE_PRICE_IDS_PRO").split(",") if p.strip()]
STRIPE_PRICES_AGENCY = [p.strip() for p in get_setting("STRIPE_PRICE_IDS_AGENCY").split(",") if p.strip()]
STRIPE_PRO_URL = get_setting("STRIPE_PRO_URL", "https://buy.stripe.com/4gM28rdxmck239y8Mk43S03")
STRIPE_AGENCY_URL = get_setting("STRIPE_AGENCY_URL", "https://buy.stripe.com/4gM00j2SIfwebG41jS43S02")
# Stripe no-code customer portal login link (Billing → Customer portal)
STRIPE_PORTAL_URL = get_setting("STRIPE_PORTAL_URL")

# ── Email (login codes) ──────────────────────────────────────────────────────
SMTP_HOST = get_setting("SMTP_HOST")
SMTP_PORT = _int_setting("SMTP_PORT", 587)
SMTP_USER = get_setting("SMTP_USER")
SMTP_PASSWORD = get_setting("SMTP_PASSWORD")
EMAIL_FROM = get_setting("EMAIL_FROM", SMTP_USER)
BREVO_API_KEY = get_setting("BREVO_API_KEY")

# ── Business details (shown in footer and legal pages) ───────────────────────
COMPANY_NAME = get_setting("COMPANY_NAME", "[Company or trading name]")
COMPANY_NUMBER = get_setting("COMPANY_NUMBER")        # optional (sole traders have none)
COMPANY_ADDRESS = get_setting("COMPANY_ADDRESS")      # optional but recommended
ICO_REG_NUMBER = get_setting("ICO_REG_NUMBER")        # optional until registered with the ICO
SUPPORT_EMAIL = get_setting("SUPPORT_EMAIL", "[support email]")
WHATSAPP_URL = get_setting("WHATSAPP_URL", "https://wa.me/447379975532")
HOSTING_PROVIDER = get_setting("HOSTING_PROVIDER", "Streamlit Community Cloud (Snowflake Inc.), United States")
DATABASE_PROVIDER = get_setting("DATABASE_PROVIDER", "Stored on our application host (see hosting provider)")
EMAIL_PROVIDER = get_setting(
    "EMAIL_PROVIDER",
    "Brevo (Sendinblue SAS), EU" if BREVO_API_KEY else (f"SMTP provider ({SMTP_HOST})" if SMTP_HOST else "[Email provider]"),
)
LEGAL_LAST_UPDATED = get_setting("LEGAL_LAST_UPDATED", "21 October 2026")

# Stay signed in across page refreshes (secure cookie + server-side session)
SESSION_DAYS = _int_setting("SESSION_DAYS", 30)


def production_config_errors() -> list:
    """Settings that must be real before the app may serve production traffic."""
    errors = []
    if not IS_PRODUCTION:
        return errors
    if APP_SECRET == "dev-only-insecure-secret" or len(APP_SECRET) < 32:
        errors.append("APP_SECRET must be a random string of at least 32 characters.")
    if not (BREVO_API_KEY or (SMTP_HOST and SMTP_USER and SMTP_PASSWORD and EMAIL_FROM)):
        errors.append("Sign-in emails can't be sent: set BREVO_API_KEY "
                      "(or SMTP_HOST/SMTP_USER/SMTP_PASSWORD).")
    if not STRIPE_SECRET_KEY:
        errors.append("STRIPE_SECRET_KEY is required so paid subscriptions can be verified.")
    for name, val in [("COMPANY_NAME", COMPANY_NAME), ("SUPPORT_EMAIL", SUPPORT_EMAIL)]:
        if val.startswith("["):
            errors.append(f"{name} must be set (shown in the footer and legal pages).")
    return errors


def production_config_warnings() -> list:
    """Things that don't block launch but should be fixed soon (logged at startup)."""
    warnings = []
    if not IS_PRODUCTION:
        return warnings
    if DATABASE_URL.startswith("sqlite"):
        warnings.append("Using SQLite on the app server: usage counts and sign-in sessions reset when the "
                        "host restarts. Paid plans are re-read from Stripe, but manual grants are lost.")
    if not (STRIPE_PRICES_PRO and STRIPE_PRICES_AGENCY):
        warnings.append("STRIPE_PRICE_IDS_* not set: plans are detected from the monthly price amount.")
    for name, val in [("COMPANY_ADDRESS", COMPANY_ADDRESS), ("ICO_REG_NUMBER", ICO_REG_NUMBER)]:
        if not val:
            warnings.append(f"{name} is not set.")
    if not STRIPE_PORTAL_URL:
        warnings.append("STRIPE_PORTAL_URL not set: customers can't manage or cancel billing themselves.")
    return warnings
