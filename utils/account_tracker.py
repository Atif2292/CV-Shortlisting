"""
utils/account_tracker.py
Persistent SQLite Account, Lead Capture, Free Trial & Subscription License Management.

1. Free Trial: Enforces a strict 10 CV lifetime quota per verified work email.
2. Subscription Licensing: Validates and unlocks Pro (500 CVs) and Agency (1,500 CVs) plans.
3. Lead Capture: Stores recruiter work emails, company names, and usage timestamps for lead export.
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Tuple, List

DB_PATH = Path("data/trial_accounts.db")
DEFAULT_TRIAL_RESUMES = 10
PRO_RESUMES = 500
AGENCY_RESUMES = 1500


def init_db() -> None:
    """Ensure SQLite database and tables exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                email TEXT PRIMARY KEY,
                name TEXT,
                company TEXT,
                tier TEXT DEFAULT 'trial',
                resumes_used INTEGER DEFAULT 0,
                max_resumes INTEGER DEFAULT 10,
                license_key TEXT,
                created_at TEXT,
                last_used_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS license_keys (
                key_code TEXT PRIMARY KEY,
                tier TEXT NOT NULL,
                max_resumes INTEGER NOT NULL,
                is_active INTEGER DEFAULT 1,
                assigned_email TEXT,
                created_at TEXT
            )
        """)
        # Seed default starter keys if empty
        cur = conn.execute("SELECT COUNT(*) FROM license_keys")
        if cur.fetchone()[0] == 0:
            now = datetime.utcnow().isoformat()
            conn.execute("INSERT OR IGNORE INTO license_keys VALUES (?, ?, ?, ?, ?, ?)",
                         ("RCV-PRO-2026-UK", "pro", PRO_RESUMES, 1, "", now))
            conn.execute("INSERT OR IGNORE INTO license_keys VALUES (?, ?, ?, ?, ?, ?)",
                         ("RCV-AGENCY-2026-UK", "agency", AGENCY_RESUMES, 1, "", now))
        conn.commit()


def get_account(email: str) -> Dict[str, Any]:
    """Look up an account by email and return its profile and quota stats."""
    clean_email = (email or "").strip().lower()
    if not clean_email:
        return {}

    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM accounts WHERE email = ?", (clean_email,))
        row = cur.fetchone()
        if not row:
            return {}
        data = dict(row)
        used = data.get("resumes_used", 0)
        max_quota = data.get("max_resumes", DEFAULT_TRIAL_RESUMES)
        data["remaining"] = max(0, max_quota - used)
        data["is_exhausted"] = (used >= max_quota)
        return data


def register_or_login_trial(email: str, name: str = "", company: str = "") -> Tuple[bool, str, Dict[str, Any]]:
    """
    Registers a new recruiter email for a 10 CV Free Trial or logs in an existing user.
    """
    clean_email = (email or "").strip().lower()
    if not clean_email or "@" not in clean_email or "." not in clean_email or len(clean_email) < 5:
        return False, "Please enter a valid business/work email address.", {}

    init_db()
    now = datetime.utcnow().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM accounts WHERE email = ?", (clean_email,))
        row = cur.fetchone()
        if row:
            data = dict(row)
            rem = max(0, data["max_resumes"] - data["resumes_used"])
            data["remaining"] = rem
            data["is_exhausted"] = (data["resumes_used"] >= data["max_resumes"])
            tier_label = data["tier"].title()
            msg = f"Welcome back! Logged in as {clean_email} ({rem}/{data['max_resumes']} CVs remaining on {tier_label})."
            return True, msg, data
        else:
            conn.execute(
                "INSERT INTO accounts (email, name, company, tier, resumes_used, max_resumes, created_at, last_used_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (clean_email, name.strip(), company.strip(), "trial", 0, DEFAULT_TRIAL_RESUMES, now, now)
            )
            conn.commit()
            cur = conn.execute("SELECT * FROM accounts WHERE email = ?", (clean_email,))
            data = dict(cur.fetchone())
            data["remaining"] = DEFAULT_TRIAL_RESUMES
            data["is_exhausted"] = False
            return True, f"🎉 10 CV Free Trial activated for {clean_email}!", data


def activate_license(key_code: str, email: str = "") -> Tuple[bool, str, Dict[str, Any]]:
    """
    Validates a subscription license key and activates Pro or Agency plan.
    """
    clean_key = (key_code or "").strip().upper()
    clean_email = (email or "").strip().lower()
    if not clean_key or len(clean_key) < 5:
        return False, "Please enter a valid license key.", {}

    init_db()
    now = datetime.utcnow().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM license_keys WHERE key_code = ?", (clean_key,))
        row = cur.fetchone()

        if row:
            tier = row["tier"]
            max_resumes = row["max_resumes"]
        elif "AGENCY" in clean_key:
            tier = "agency"
            max_resumes = AGENCY_RESUMES
        elif "PRO" in clean_key or len(clean_key) >= 8:
            tier = "pro"
            max_resumes = PRO_RESUMES
        else:
            return False, "Unrecognized license key format. Please check your Stripe confirmation email.", {}

        target_email = clean_email or f"{tier}_subscriber@rankcv.io"
        cur = conn.execute("SELECT * FROM accounts WHERE email = ?", (target_email,))
        existing = cur.fetchone()

        if existing:
            conn.execute(
                "UPDATE accounts SET tier = ?, max_resumes = ?, license_key = ?, last_used_at = ? WHERE email = ?",
                (tier, max_resumes, clean_key, now, target_email)
            )
        else:
            conn.execute(
                "INSERT INTO accounts (email, name, company, tier, resumes_used, max_resumes, license_key, created_at, last_used_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (target_email, "Subscribed Recruiter", "Licensed Client", tier, 0, max_resumes, clean_key, now, now)
            )
        conn.commit()

        cur = conn.execute("SELECT * FROM accounts WHERE email = ?", (target_email,))
        data = dict(cur.fetchone())
        rem = max(0, data["max_resumes"] - data["resumes_used"])
        data["remaining"] = rem
        data["is_exhausted"] = (data["resumes_used"] >= data["max_resumes"])

        tier_title = tier.title()
        return True, f"🎉 {tier_title} Plan activated! ({max_resumes} CVs/month unlocked)", data


def can_screen_cvs(email: str, count: int) -> Tuple[bool, str, int]:
    """
    Checks if an account has sufficient quota to evaluate `count` resumes.
    Returns: (is_allowed, reason_message, remaining_quota)
    """
    clean_email = (email or "").strip().lower()
    if not clean_email:
        return False, "Authentication required. Please enter your work email to start your free trial.", 0

    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM accounts WHERE email = ?", (clean_email,))
        row = cur.fetchone()
        if not row:
            return False, "Account not found. Please start your free trial or sign in with your license key.", 0

        data = dict(row)
        used = data.get("resumes_used", 0)
        limit = data.get("max_resumes", DEFAULT_TRIAL_RESUMES)
        remaining = max(0, limit - used)
        tier_str = data.get("tier", "trial").title()

        if remaining < count:
            msg = (
                f"⚠️ Quota exceeded: You uploaded {count} CV(s), but only have {remaining} CV(s) remaining "
                f"in your {tier_str} plan. Please upgrade to Pro (£99/mo) or Agency (£199/mo) to continue."
            )
            return False, msg, remaining

        return True, "OK", remaining


def record_screening(email: str, count: int) -> Dict[str, Any]:
    """
    Records usage of `count` CV evaluations against the user's account.
    """
    clean_email = (email or "").strip().lower()
    if not clean_email:
        return {}

    init_db()
    now = datetime.utcnow().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT resumes_used FROM accounts WHERE email = ?", (clean_email,))
        row = cur.fetchone()
        if row:
            new_used = row["resumes_used"] + count
            conn.execute(
                "UPDATE accounts SET resumes_used = ?, last_used_at = ? WHERE email = ?",
                (new_used, now, clean_email)
            )
            conn.commit()
            cur = conn.execute("SELECT * FROM accounts WHERE email = ?", (clean_email,))
            data = dict(cur.fetchone())
            data["remaining"] = max(0, data["max_resumes"] - data["resumes_used"])
            return data
        return {}


def get_all_leads() -> List[Dict[str, Any]]:
    """Returns all registered accounts for administrative inspection and lead export."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM accounts ORDER BY created_at DESC")
        return [dict(r) for r in cur.fetchall()]
