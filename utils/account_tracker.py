"""
utils/account_tracker.py
Accounts, email-code sign-in, plan entitlements and CV quotas.

- Sign-in: a 6-digit code is emailed to the address; only someone with access
  to that inbox can sign in. Codes are stored as HMAC hashes, expire after
  10 minutes and allow 5 attempts.
- Plans: paid plans come from the customer's live Stripe subscription (looked up
  by billing email), or from a manual grant made with `python -m utils.admin`.
  There are no shared licence keys.
- Quotas: reserved atomically before a run and released for CVs that were not
  scored, so parallel sessions cannot overspend. Paid quotas reset each billing
  period; the free trial is a one-off allowance.
- Storage: any SQLAlchemy database via DATABASE_URL (managed Postgres in
  production; SQLite only for local development).
"""

import hashlib
import hmac
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import (
    Column, DateTime, Integer, MetaData, String, Table, create_engine, insert,
    select, update,
)
from sqlalchemy.engine import Engine

from utils import config

log = logging.getLogger(__name__)

CODE_TTL = timedelta(minutes=10)
CODE_MAX_ATTEMPTS = 5
CODE_RESEND_SECONDS = 60
CODE_MAX_PER_HOUR = 5
STRIPE_SYNC_INTERVAL = timedelta(minutes=15)
MANUAL_PERIOD = timedelta(days=30)

FREE_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "hotmail.co.uk",
    "live.com", "live.co.uk", "msn.com", "yahoo.com", "yahoo.co.uk", "ymail.com",
    "icloud.com", "me.com", "mac.com", "aol.com", "proton.me", "protonmail.com",
    "gmx.com", "gmx.co.uk", "mail.com", "zoho.com", "yandex.com", "tutanota.com",
    "mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com",
    "temp-mail.org", "sharklasers.com", "yopmail.com", "trashmail.com",
}

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+'-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")

metadata = MetaData()

accounts = Table(
    "accounts", metadata,
    Column("email", String(320), primary_key=True),       # canonical address
    Column("contact_email", String(320)),                  # address the user typed
    Column("company", String(200), default=""),
    Column("tier", String(20), nullable=False, default="trial"),
    Column("plan_source", String(20), nullable=False, default="trial"),  # trial | stripe | manual
    Column("resumes_used", Integer, nullable=False, default=0),
    Column("max_resumes", Integer, nullable=False, default=10),
    Column("period_start", DateTime(timezone=True)),
    Column("period_end", DateTime(timezone=True)),
    Column("plan_expires_at", DateTime(timezone=True)),    # manual grants only
    Column("stripe_customer_id", String(64)),
    Column("last_stripe_sync", DateTime(timezone=True)),
    Column("terms_accepted_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True)),
    Column("last_login_at", DateTime(timezone=True)),
    Column("last_used_at", DateTime(timezone=True)),
)

login_codes = Table(
    "login_codes", metadata,
    Column("email", String(320), primary_key=True),
    Column("code_hash", String(64), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("attempts", Integer, nullable=False, default=0),
    Column("last_sent_at", DateTime(timezone=True)),
    Column("window_start", DateTime(timezone=True)),
    Column("sent_in_window", Integer, nullable=False, default=0),
)

usage_events = Table(
    "usage_events", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", String(320), nullable=False, index=True),
    Column("cvs", Integer, nullable=False),
    Column("kind", String(20), nullable=False),            # reserve | release
    Column("created_at", DateTime(timezone=True), nullable=False),
)

sessions = Table(
    "sessions", metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("email", String(320), nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)

_engine: Optional[Engine] = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = config.DATABASE_URL
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        kwargs: Dict[str, Any] = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            db_file = url.split("///", 1)[-1]
            if db_file and db_file != ":memory:":
                Path(db_file).parent.mkdir(parents=True, exist_ok=True)
            kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
        _engine = create_engine(url, **kwargs)
        metadata.create_all(_engine)
    return _engine


def init_db() -> None:
    get_engine()


# ─────────────────────────── Email helpers ───────────────────────────────────
def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def canonical_email(email: str) -> str:
    """Account key: strips +tags (and dots for Gmail) so one inbox = one account."""
    e = normalize_email(email)
    if "@" not in e:
        return e
    local, domain = e.rsplit("@", 1)
    local = local.split("+", 1)[0]
    if domain in ("gmail.com", "googlemail.com"):
        local = local.replace(".", "")
        domain = "gmail.com"
    return f"{local}@{domain}"


def validate_email(email: str) -> Tuple[bool, str]:
    e = normalize_email(email)
    if not e or len(e) > 254 or not _EMAIL_RE.match(e):
        return False, "Please enter a valid email address."
    return True, ""


def _code_hash(email: str, code: str) -> str:
    return hmac.new(config.APP_SECRET.encode(), f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


# ─────────────────────────── Account views ───────────────────────────────────
def _view(row: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(row)
    used = int(data.get("resumes_used") or 0)
    limit = int(data.get("max_resumes") or 0)
    data["remaining"] = max(0, limit - used)
    data["is_exhausted"] = used >= limit
    for k in ("period_start", "period_end", "plan_expires_at", "last_stripe_sync",
              "terms_accepted_at", "created_at", "last_login_at", "last_used_at"):
        data[k] = _aware(data.get(k))
    return data


def get_account(email: str) -> Dict[str, Any]:
    key = canonical_email(email)
    if not key:
        return {}
    with get_engine().connect() as conn:
        row = conn.execute(select(accounts).where(accounts.c.email == key)).mappings().first()
    return _view(row) if row else {}


def list_accounts() -> List[Dict[str, Any]]:
    with get_engine().connect() as conn:
        rows = conn.execute(select(accounts).order_by(accounts.c.created_at.desc())).mappings().all()
    return [_view(r) for r in rows]


# ─────────────────────────── Stripe entitlements ─────────────────────────────
_MONTHS_PER_INTERVAL = {"day": 1 / 30, "week": 12 / 52, "month": 1, "year": 12}


LINK_MAP_TTL = timedelta(hours=1)
_link_price_cache: Dict[str, Any] = {"at": None, "map": {}}


def _payment_link_prices() -> Dict[str, str]:
    """
    {price_id: tier} read from the Pro and Agency Payment Links themselves (STRIPE_PRO_URL /
    STRIPE_AGENCY_URL), so whatever those links sell maps to the right plan. Cached for an hour.
    """
    now = _now()
    cached_at = _link_price_cache["at"]
    if cached_at and now - cached_at < LINK_MAP_TTL:
        return _link_price_cache["map"]
    wanted = {config.STRIPE_PRO_URL.rstrip("/"): "pro", config.STRIPE_AGENCY_URL.rstrip("/"): "agency"}
    mapping: Dict[str, str] = {}
    try:
        import stripe
        client = stripe.StripeClient(config.STRIPE_SECRET_KEY)
        for link in client.v1.payment_links.list(params={"limit": 100}).data:
            tier = wanted.get(str(link.url or "").rstrip("/"))
            if not tier:
                continue
            for item in client.v1.payment_links.line_items.list(link.id, params={"limit": 20}).data:
                price_id = (item.to_dict().get("price") or {}).get("id")
                if price_id:
                    mapping[price_id] = tier
    except Exception:
        log.warning("Could not read Stripe Payment Links; falling back to price amounts", exc_info=True)
        _link_price_cache.update(at=now - LINK_MAP_TTL + timedelta(minutes=5), map={})  # retry in 5 min
        return {}
    if not mapping:
        log.warning("Neither Payment Link URL was found in Stripe; falling back to price amounts")
    _link_price_cache.update(at=now, map=mapping)
    return mapping


def _tier_for_price(price: Dict[str, Any]) -> Optional[str]:
    """
    Map a Stripe Price to a plan, in order: configured Price IDs, the prices sold by the Pro /
    Agency Payment Links, then (only if neither is available) the GBP monthly amount.
    """
    price_id = price.get("id", "")
    if price_id in config.STRIPE_PRICES_AGENCY:
        return "agency"
    if price_id in config.STRIPE_PRICES_PRO:
        return "pro"
    if config.STRIPE_PRICES_PRO or config.STRIPE_PRICES_AGENCY:
        return None                      # explicit configuration wins
    link_prices = _payment_link_prices() if config.STRIPE_SECRET_KEY else {}
    if link_prices:
        return link_prices.get(price_id)  # only what the two Payment Links sell grants a plan
    amount = price.get("unit_amount")
    recurring = price.get("recurring") or {}
    if not amount or str(price.get("currency", "")).lower() != "gbp" or not recurring:
        return None
    months = _MONTHS_PER_INTERVAL.get(recurring.get("interval"), 1) * (recurring.get("interval_count") or 1)
    monthly = amount / 100 / max(months, 1e-9)
    pro, agency = config.PLAN_PRICES_GBP["pro"], config.PLAN_PRICES_GBP["agency"]
    if monthly >= (pro + agency) / 2:
        return "agency"
    if monthly >= pro / 2:
        return "pro"
    return None


def _ts(value: Any) -> Optional[datetime]:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc) if value else None
    except (TypeError, ValueError):
        return None


def lookup_stripe_plan(email: str) -> Optional[Dict[str, Any]]:
    """
    Returns {"tier", "period_start", "period_end", "customer_id"} for the best
    active Stripe subscription billed to this email, None if there is none,
    or raises RuntimeError if Stripe could not be reached.
    """
    if not config.STRIPE_SECRET_KEY:
        return None
    try:
        import stripe
        client = stripe.StripeClient(config.STRIPE_SECRET_KEY)
        best = None
        addr = normalize_email(email)
        customers = list(client.v1.customers.list(params={"email": addr, "limit": 10}).data)
        if not customers:
            # The list filter is case-sensitive; search catches "Jane@Acme.com" entered at checkout
            try:
                found = client.v1.customers.search(params={"query": f"email:'{addr}'", "limit": 10})
                customers = list(found.data)
            except Exception:
                log.warning("Stripe customer search unavailable", exc_info=True)
        for cust in customers:
            subs = client.v1.subscriptions.list(params={"customer": cust.id, "status": "all", "limit": 20})
            for sub_obj in subs.data:
                sub = sub_obj.to_dict()
                if sub.get("status") not in ("active", "trialing", "past_due"):
                    continue
                for item in (sub.get("items") or {}).get("data", []):
                    tier = _tier_for_price(item.get("price") or {})
                    if not tier:
                        continue
                    cand = {
                        "tier": tier,
                        "period_start": _ts(item.get("current_period_start") or sub.get("current_period_start")),
                        "period_end": _ts(item.get("current_period_end") or sub.get("current_period_end")),
                        "customer_id": cust.id,
                    }
                    if best is None or (best["tier"] == "pro" and tier == "agency"):
                        best = cand
        return best
    except Exception as exc:
        log.exception("Stripe lookup failed")
        raise RuntimeError("Could not verify your subscription with Stripe right now.") from exc


def _apply_plan(conn, row: Dict[str, Any], plan: Optional[Dict[str, Any]], now: datetime) -> None:
    """Bring the stored plan in line with Stripe."""
    key = row["email"]
    vals: Dict[str, Any] = {"last_stripe_sync": now}
    if plan:
        vals.update(tier=plan["tier"], plan_source="stripe",
                    max_resumes=config.PLAN_QUOTAS[plan["tier"]],
                    stripe_customer_id=plan["customer_id"],
                    period_end=plan["period_end"])
        if _aware(row.get("period_start")) != plan["period_start"] or row.get("plan_source") != "stripe":
            vals.update(period_start=plan["period_start"], resumes_used=0)
    elif row.get("plan_source") == "stripe":
        # Subscription ended or was cancelled → back to the (already used) trial allowance
        vals.update(tier="trial", plan_source="trial", max_resumes=config.PLAN_QUOTAS["trial"],
                    resumes_used=config.PLAN_QUOTAS["trial"], period_start=None, period_end=None)
    conn.execute(update(accounts).where(accounts.c.email == key).values(**vals))


def _roll_manual_period(conn, row: Dict[str, Any], now: datetime) -> None:
    expires = _aware(row.get("plan_expires_at"))
    if expires and now >= expires:
        conn.execute(update(accounts).where(accounts.c.email == row["email"]).values(
            tier="trial", plan_source="trial", max_resumes=config.PLAN_QUOTAS["trial"],
            resumes_used=config.PLAN_QUOTAS["trial"], period_start=None, period_end=None,
            plan_expires_at=None))
        return
    end = _aware(row.get("period_end"))
    if end and now >= end:
        conn.execute(update(accounts).where(accounts.c.email == row["email"]).values(
            resumes_used=0, period_start=now, period_end=now + MANUAL_PERIOD))


def refresh_entitlements(email: str, force: bool = False) -> Tuple[Dict[str, Any], str]:
    """Re-check the plan (Stripe at most every 15 min unless forced). Returns (account, warning)."""
    key = canonical_email(email)
    now = _now()
    warning = ""
    with get_engine().begin() as conn:
        row = conn.execute(select(accounts).where(accounts.c.email == key)).mappings().first()
        if not row:
            return {}, ""
        row = dict(row)
        if row.get("plan_source") == "manual":
            _roll_manual_period(conn, row, now)
        else:
            last = _aware(row.get("last_stripe_sync"))
            if config.STRIPE_SECRET_KEY and (force or not last or now - last >= STRIPE_SYNC_INTERVAL):
                try:
                    plan = lookup_stripe_plan(row.get("contact_email") or key)
                    if plan is None and row.get("contact_email") and row["contact_email"] != key:
                        plan = lookup_stripe_plan(key)
                    _apply_plan(conn, row, plan, now)
                except RuntimeError as exc:
                    warning = str(exc)
        row = conn.execute(select(accounts).where(accounts.c.email == key)).mappings().first()
    return _view(row), warning


# ─────────────────────────── Sign-in codes ───────────────────────────────────
def request_login_code(email: str) -> Tuple[bool, str, Optional[str]]:
    """
    Creates and stores a sign-in code. Returns (ok, message, code).
    The caller emails `code`; only its hash is stored.
    """
    ok, msg = validate_email(email)
    if not ok:
        return False, msg, None
    addr = normalize_email(email)
    key = canonical_email(addr)
    domain = addr.rsplit("@", 1)[1]

    if config.TRIAL_REQUIRE_WORK_EMAIL and domain in FREE_EMAIL_DOMAINS and not get_account(key):
        try:
            paying = lookup_stripe_plan(addr) is not None
        except RuntimeError:
            paying = False
        if not paying:
            return False, ("Please use your work email address. Free webmail and disposable "
                           "addresses can't start a free trial."), None

    now = _now()
    code = f"{secrets.randbelow(1_000_000):06d}"
    with get_engine().begin() as conn:
        row = conn.execute(select(login_codes).where(login_codes.c.email == addr)).mappings().first()
        if row:
            last = _aware(row["last_sent_at"])
            if last and (now - last).total_seconds() < CODE_RESEND_SECONDS:
                wait = CODE_RESEND_SECONDS - int((now - last).total_seconds())
                return False, f"Please wait {wait}s before requesting another code.", None
            win = _aware(row["window_start"])
            sent = row["sent_in_window"] or 0
            if win and now - win < timedelta(hours=1):
                if sent >= CODE_MAX_PER_HOUR:
                    return False, "Too many codes requested. Please try again in an hour.", None
            else:
                win, sent = now, 0
            conn.execute(update(login_codes).where(login_codes.c.email == addr).values(
                code_hash=_code_hash(addr, code), expires_at=now + CODE_TTL, attempts=0,
                last_sent_at=now, window_start=win, sent_in_window=sent + 1))
        else:
            conn.execute(insert(login_codes).values(
                email=addr, code_hash=_code_hash(addr, code), expires_at=now + CODE_TTL,
                attempts=0, last_sent_at=now, window_start=now, sent_in_window=1))
    return True, f"We've sent a 6-digit code to {addr}. It expires in 10 minutes.", code


def verify_login_code(email: str, code: str, company: str = "",
                      accept_terms: bool = False) -> Tuple[bool, str, Dict[str, Any]]:
    """Checks the code; on success creates the account if needed and syncs the plan."""
    addr = normalize_email(email)
    key = canonical_email(addr)
    code = re.sub(r"\D", "", code or "")
    if len(code) != 6:
        return False, "Enter the 6-digit code from your email.", {}

    now = _now()
    with get_engine().begin() as conn:
        row = conn.execute(select(login_codes).where(login_codes.c.email == addr)).mappings().first()
        if not row:
            return False, "Request a new code first.", {}
        if now > _aware(row["expires_at"]):
            return False, "That code has expired. Request a new one.", {}
        if row["attempts"] >= CODE_MAX_ATTEMPTS:
            return False, "Too many incorrect attempts. Request a new code.", {}
        if not hmac.compare_digest(row["code_hash"], _code_hash(addr, code)):
            conn.execute(update(login_codes).where(login_codes.c.email == addr)
                         .values(attempts=login_codes.c.attempts + 1))
            left = CODE_MAX_ATTEMPTS - row["attempts"] - 1
            return False, f"Incorrect code. {left} attempt(s) left.", {}

        existing = conn.execute(select(accounts).where(accounts.c.email == key)).mappings().first()
        if not existing and not accept_terms:
            return False, "Please accept the Terms of Service and Privacy Notice to continue.", {}

        # Single use
        conn.execute(update(login_codes).where(login_codes.c.email == addr)
                     .values(expires_at=now, attempts=CODE_MAX_ATTEMPTS))
        if existing:
            conn.execute(update(accounts).where(accounts.c.email == key).values(
                last_login_at=now, contact_email=addr,
                company=(company.strip()[:200] or existing["company"] or "")))
        else:
            conn.execute(insert(accounts).values(
                email=key, contact_email=addr, company=company.strip()[:200], tier="trial",
                plan_source="trial", resumes_used=0, max_resumes=config.PLAN_QUOTAS["trial"],
                terms_accepted_at=now, created_at=now, last_login_at=now))

    account, warning = refresh_entitlements(key, force=True)
    label = config.PLAN_LABELS.get(account.get("tier"), "Free Trial")
    msg = f"Signed in as {addr} · {label} · {account['remaining']}/{account['max_resumes']} CVs left."
    if warning:
        msg += f" ({warning} Your previous plan is shown.)"
    return True, msg, account


# ─────────────────────────── Quota ───────────────────────────────────────────
def reserve_quota(email: str, count: int) -> Tuple[bool, str, int]:
    """Atomically reserve `count` CVs. Returns (ok, message, remaining_after)."""
    key = canonical_email(email)
    if not key:
        return False, "Please sign in to screen your own CVs.", 0
    account, _ = refresh_entitlements(key)
    if not account:
        return False, "Account not found. Please sign in again.", 0
    if count <= 0:
        return True, "OK", account["remaining"]

    now = _now()
    with get_engine().begin() as conn:
        res = conn.execute(
            update(accounts)
            .where(accounts.c.email == key)
            .where(accounts.c.resumes_used + count <= accounts.c.max_resumes)
            .values(resumes_used=accounts.c.resumes_used + count, last_used_at=now)
        )
        if res.rowcount != 1:
            row = conn.execute(select(accounts).where(accounts.c.email == key)).mappings().first()
            rem = max(0, row["max_resumes"] - row["resumes_used"]) if row else 0
            label = config.PLAN_LABELS.get(row["tier"] if row else "trial", "plan")
            return False, (f"Not enough CVs left: this batch has {count}, your {label} plan has "
                           f"{rem} remaining. Remove some files or upgrade your plan."), rem
        conn.execute(insert(usage_events).values(email=key, cvs=count, kind="reserve", created_at=now))
        row = conn.execute(select(accounts).where(accounts.c.email == key)).mappings().first()
    return True, "OK", max(0, row["max_resumes"] - row["resumes_used"])


def release_quota(email: str, count: int) -> int:
    """Give back CVs that were reserved but not scored. Returns remaining."""
    key = canonical_email(email)
    if not key:
        return 0
    if count <= 0:
        return get_account(key).get("remaining", 0)
    now = _now()
    with get_engine().begin() as conn:
        conn.execute(
            update(accounts).where(accounts.c.email == key)
            .where(accounts.c.resumes_used >= count)
            .values(resumes_used=accounts.c.resumes_used - count)
        )
        conn.execute(insert(usage_events).values(email=key, cvs=count, kind="release", created_at=now))
        row = conn.execute(select(accounts).where(accounts.c.email == key)).mappings().first()
    return max(0, row["max_resumes"] - row["resumes_used"]) if row else 0


# ─────────────────────────── Persistent sessions ─────────────────────────────
def _token_hash(token: str) -> str:
    return hmac.new(config.APP_SECRET.encode(), f"session:{token}".encode(), hashlib.sha256).hexdigest()


def create_session(email: str) -> str:
    """Create a sign-in session; returns the raw token for the browser cookie (only its hash is stored)."""
    token = secrets.token_urlsafe(32)
    now = _now()
    with get_engine().begin() as conn:
        conn.execute(insert(sessions).values(
            token_hash=_token_hash(token), email=canonical_email(email), created_at=now,
            expires_at=now + timedelta(days=config.SESSION_DAYS)))
        conn.execute(sessions.delete().where(sessions.c.expires_at < now))
    return token


def account_for_session(token: str) -> Dict[str, Any]:
    """Account for a valid, unexpired session token, else {}."""
    if not token or len(token) > 100:
        return {}
    with get_engine().connect() as conn:
        row = conn.execute(select(sessions).where(sessions.c.token_hash == _token_hash(token))).mappings().first()
    if not row or _now() >= _aware(row["expires_at"]):
        return {}
    return get_account(row["email"])


def delete_session(token: str) -> None:
    if not token:
        return
    with get_engine().begin() as conn:
        conn.execute(sessions.delete().where(sessions.c.token_hash == _token_hash(token)))


# ─────────────────────────── Admin ───────────────────────────────────────────
def grant_plan(email: str, tier: str, months: int = 1, company: str = "") -> Dict[str, Any]:
    """Manually grant a plan (e.g. invoiced customers). Usage resets every 30 days."""
    if tier not in ("trial", "pro", "agency"):
        raise ValueError("tier must be trial, pro or agency")
    addr = normalize_email(email)
    key = canonical_email(addr)
    now = _now()
    paid = tier != "trial"
    vals = dict(tier=tier, plan_source="manual" if paid else "trial",
                max_resumes=config.PLAN_QUOTAS[tier], resumes_used=0,
                period_start=now if paid else None,
                period_end=now + MANUAL_PERIOD if paid else None,
                plan_expires_at=now + timedelta(days=30 * months) if paid else None)
    with get_engine().begin() as conn:
        exists = conn.execute(select(accounts.c.email).where(accounts.c.email == key)).first()
        if exists:
            conn.execute(update(accounts).where(accounts.c.email == key).values(**vals))
        else:
            conn.execute(insert(accounts).values(email=key, contact_email=addr, company=company,
                                                 created_at=now, **vals))
    return get_account(key)
