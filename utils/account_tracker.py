"""
utils/account_tracker.py
Track free trial usage per account (email address).
Each account gets up to 10 resume evaluations.
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

DB_PATH = Path("data/trial_accounts.db")
MAX_FREE_RESUMES = 10


def init_db() -> None:
    """Ensure SQLite database and accounts table exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                email TEXT PRIMARY KEY,
                resumes_used INTEGER DEFAULT 0,
                created_at TEXT,
                last_used_at TEXT
            )
        """)
        conn.commit()


def get_account_usage(email: str) -> Dict[str, Any]:
    """
    Look up an account by email and return usage stats.
    Returns:
        dict: {
            "email": str,
            "resumes_used": int,
            "remaining": int,
            "max": int,
            "is_exhausted": bool
        }
    """
    clean_email = (email or "").strip().lower()
    if not clean_email:
        return {
            "email": "",
            "resumes_used": 0,
            "remaining": MAX_FREE_RESUMES,
            "max": MAX_FREE_RESUMES,
            "is_exhausted": False,
        }

    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "SELECT resumes_used FROM accounts WHERE email = ?",
            (clean_email,)
        )
        row = cursor.fetchone()
        used = int(row[0]) if row else 0
        remaining = max(0, MAX_FREE_RESUMES - used)
        return {
            "email": clean_email,
            "resumes_used": used,
            "remaining": remaining,
            "max": MAX_FREE_RESUMES,
            "is_exhausted": (remaining == 0 and used >= MAX_FREE_RESUMES),
        }


def record_account_usage(email: str, count: int) -> Dict[str, Any]:
    """
    Add `count` resumes to the account's used tally.
    """
    clean_email = (email or "").strip().lower()
    if not clean_email:
        return get_account_usage("")

    init_db()
    now = datetime.utcnow().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "SELECT resumes_used FROM accounts WHERE email = ?",
            (clean_email,)
        )
        row = cursor.fetchone()
        if row:
            new_used = int(row[0]) + count
            conn.execute(
                "UPDATE accounts SET resumes_used = ?, last_used_at = ? WHERE email = ?",
                (new_used, now, clean_email)
            )
        else:
            new_used = count
            conn.execute(
                "INSERT INTO accounts (email, resumes_used, created_at, last_used_at) VALUES (?, ?, ?, ?)",
                (clean_email, count, now, now)
            )
        conn.commit()

    return get_account_usage(clean_email)
