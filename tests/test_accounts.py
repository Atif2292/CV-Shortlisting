import threading
from datetime import datetime, timedelta, timezone

import pytest

from utils import account_tracker as at
from utils import config


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "")
    monkeypatch.setattr(config, "TRIAL_REQUIRE_WORK_EMAIL", True)
    monkeypatch.setattr(at, "_engine", None)
    yield
    at._engine = None


def _sign_in(email, company="Acme"):
    ok, _, code = at.request_login_code(email)
    assert ok
    return at.verify_login_code(email, code, company=company, accept_terms=True)


def test_sign_in_creates_trial_account():
    ok, msg, acc = _sign_in("Jane@Acme.co.uk")
    assert ok and acc["tier"] == "trial" and acc["remaining"] == config.PLAN_QUOTAS["trial"]
    assert acc["email"] == "jane@acme.co.uk"


def test_wrong_code_is_rejected_and_attempts_are_limited():
    ok, _, code = at.request_login_code("a@acme.co.uk")
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(at.CODE_MAX_ATTEMPTS):
        ok, msg, _ = at.verify_login_code("a@acme.co.uk", wrong, accept_terms=True)
        assert not ok
    ok, msg, _ = at.verify_login_code("a@acme.co.uk", code, accept_terms=True)
    assert not ok and "Too many" in msg


def test_code_is_single_use_and_expires(monkeypatch):
    ok, _, code = at.request_login_code("b@acme.co.uk")
    assert at.verify_login_code("b@acme.co.uk", code, accept_terms=True)[0]
    assert not at.verify_login_code("b@acme.co.uk", code, accept_terms=True)[0]

    at._engine = None
    monkeypatch.setattr(config, "DATABASE_URL", "sqlite://")
    ok, _, code = at.request_login_code("c@acme.co.uk")
    real_now = at._now
    monkeypatch.setattr(at, "_now", lambda: real_now() + timedelta(minutes=11))
    ok, msg, _ = at.verify_login_code("c@acme.co.uk", code, accept_terms=True)
    assert not ok and "expired" in msg


def test_new_account_requires_terms():
    ok, _, code = at.request_login_code("d@acme.co.uk")
    ok, msg, _ = at.verify_login_code("d@acme.co.uk", code, accept_terms=False)
    assert not ok and "Terms" in msg


def test_resend_is_rate_limited():
    assert at.request_login_code("e@acme.co.uk")[0]
    ok, msg, _ = at.request_login_code("e@acme.co.uk")
    assert not ok and "wait" in msg


def test_free_webmail_cannot_start_trial():
    ok, msg, _ = at.request_login_code("someone@gmail.com")
    assert not ok and "work email" in msg


def test_plus_addresses_share_one_trial():
    _sign_in("f+1@acme.co.uk")
    assert at.reserve_quota("f+1@acme.co.uk", 10)[0]
    ok, _, code = at.request_login_code("f+2@acme.co.uk")
    _, _, acc = at.verify_login_code("f+2@acme.co.uk", code, accept_terms=True)
    assert acc["email"] == "f@acme.co.uk" and acc["remaining"] == 0


def test_no_licence_key_backdoor():
    assert not hasattr(at, "activate_license")


def test_quota_reservation_is_atomic_under_concurrency():
    _sign_in("g@acme.co.uk")
    results = []

    def worker():
        results.append(at.reserve_quota("g@acme.co.uk", 3)[0])

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(results) == 3                     # 3 × 3 = 9 ≤ 10, a 4th would exceed
    assert at.get_account("g@acme.co.uk")["resumes_used"] == 9


def test_release_returns_unscored_cvs():
    _sign_in("h@acme.co.uk")
    at.reserve_quota("h@acme.co.uk", 8)
    assert at.release_quota("h@acme.co.uk", 5) == 7


def test_manual_grant_resets_each_period_and_expires(monkeypatch):
    at.grant_plan("i@acme.co.uk", "pro", months=2)
    assert at.reserve_quota("i@acme.co.uk", 400)[0]
    real_now = at._now
    monkeypatch.setattr(at, "_now", lambda: real_now() + timedelta(days=31))
    acc, _ = at.refresh_entitlements("i@acme.co.uk")
    assert acc["tier"] == "pro" and acc["resumes_used"] == 0
    monkeypatch.setattr(at, "_now", lambda: real_now() + timedelta(days=61))
    acc, _ = at.refresh_entitlements("i@acme.co.uk")
    assert acc["tier"] == "trial" and acc["remaining"] == 0


def test_stripe_subscription_grants_plan_and_cancellation_revokes(monkeypatch):
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_dummy")
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    plan = {"tier": "agency", "period_start": start, "period_end": start + timedelta(days=30),
            "customer_id": "cus_1"}
    monkeypatch.setattr(at, "lookup_stripe_plan", lambda email: plan)
    ok, _, acc = _sign_in("j@acme.co.uk")
    assert acc["tier"] == "agency" and acc["max_resumes"] == config.PLAN_QUOTAS["agency"]

    at.reserve_quota("j@acme.co.uk", 100)
    plan2 = dict(plan, period_start=start + timedelta(days=30), period_end=start + timedelta(days=60))
    monkeypatch.setattr(at, "lookup_stripe_plan", lambda email: plan2)
    acc, _ = at.refresh_entitlements("j@acme.co.uk", force=True)
    assert acc["resumes_used"] == 0                # new billing period → quota reset

    monkeypatch.setattr(at, "lookup_stripe_plan", lambda email: None)
    acc, _ = at.refresh_entitlements("j@acme.co.uk", force=True)
    assert acc["tier"] == "trial" and acc["remaining"] == 0


def test_stripe_outage_keeps_existing_plan(monkeypatch):
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_dummy")
    at.grant_plan("k@acme.co.uk", "trial")

    def boom(email):
        raise RuntimeError("Stripe down")
    monkeypatch.setattr(at, "lookup_stripe_plan", boom)
    acc, warn = at.refresh_entitlements("k@acme.co.uk", force=True)
    assert acc["tier"] == "trial" and "Stripe down" in warn


def test_production_config_rejects_unsafe_defaults(monkeypatch):
    monkeypatch.setattr(config, "IS_PRODUCTION", True)
    for name in ("BREVO_API_KEY", "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "EMAIL_FROM"):
        monkeypatch.setattr(config, name, "")
    errs = " ".join(config.production_config_errors())
    assert "APP_SECRET" in errs and "BREVO_API_KEY" in errs


def test_production_needs_only_secret_and_email(monkeypatch):
    monkeypatch.setattr(config, "IS_PRODUCTION", True)
    monkeypatch.setattr(config, "APP_SECRET", "x" * 40)
    monkeypatch.setattr(config, "BREVO_API_KEY", "xkeysib-test")
    for name in ("STRIPE_SECRET_KEY", "EMAIL_FROM", "SUPPORT_EMAIL", "COMPANY_NUMBER"):
        monkeypatch.setattr(config, name, "")
    assert config.production_config_errors() == []
    warns = " ".join(config.production_config_warnings())
    assert "PAID_CUSTOMERS" in warns and "SQLite" in warns


def test_paid_customers_setting_is_parsed():
    parsed = config._parse_paid_customers(" Jane@Agency.co.uk = agency ; bob@firm.co.uk=pro, bad, x@y.z=gold")
    assert parsed == {"jane@agency.co.uk": "agency", "bob@firm.co.uk": "pro"}


def test_listed_customer_gets_plan_and_loses_it_when_removed(monkeypatch):
    _sign_in("buyer@acme.co.uk")
    assert at.reserve_quota("buyer@acme.co.uk", 4)[0]
    monkeypatch.setattr(config, "PAID_CUSTOMERS", {"buyer+billing@acme.co.uk": "pro"})
    acc, _ = at.refresh_entitlements("buyer@acme.co.uk")
    assert acc["tier"] == "pro" and acc["remaining"] == config.PLAN_QUOTAS["pro"]
    assert at.reserve_quota("buyer@acme.co.uk", 100)[0]
    acc, _ = at.refresh_entitlements("buyer@acme.co.uk")
    assert acc["resumes_used"] == 100                       # not reset on every refresh

    real_now = at._now
    monkeypatch.setattr(at, "_now", lambda: real_now() + timedelta(days=31))
    acc, _ = at.refresh_entitlements("buyer@acme.co.uk")
    assert acc["resumes_used"] == 0                         # new 30-day period

    monkeypatch.setattr(config, "PAID_CUSTOMERS", {})
    acc, _ = at.refresh_entitlements("buyer@acme.co.uk")
    assert acc["tier"] == "trial" and acc["remaining"] == 0


def test_listed_customer_with_free_webmail_can_sign_in(monkeypatch):
    monkeypatch.setattr(config, "PAID_CUSTOMERS", {"owner@gmail.com": "agency"})
    ok, _, code = at.request_login_code("owner@gmail.com")
    assert ok
    ok, _, acc = at.verify_login_code("owner@gmail.com", code, accept_terms=True)
    assert ok and acc["tier"] == "agency"


def test_sessions_survive_lookup_and_sign_out():
    _sign_in("s@acme.co.uk")
    token = at.create_session("s@acme.co.uk")
    assert at.account_for_session(token)["email"] == "s@acme.co.uk"
    assert at.account_for_session("not-a-real-token") == {}
    at.delete_session(token)
    assert at.account_for_session(token) == {}


def test_expired_session_is_rejected(monkeypatch):
    _sign_in("t@acme.co.uk")
    token = at.create_session("t@acme.co.uk")
    real_now = at._now
    monkeypatch.setattr(at, "_now", lambda: real_now() + timedelta(days=config.SESSION_DAYS + 1))
    assert at.account_for_session(token) == {}


@pytest.mark.parametrize("price,tier", [
    ({"id": "p1", "unit_amount": 9900, "currency": "gbp", "recurring": {"interval": "month"}}, "pro"),
    ({"id": "p2", "unit_amount": 19900, "currency": "gbp", "recurring": {"interval": "month"}}, "agency"),
    ({"id": "p3", "unit_amount": 99000, "currency": "gbp", "recurring": {"interval": "year"}}, "pro"),
    ({"id": "p4", "unit_amount": 199000, "currency": "gbp", "recurring": {"interval": "year"}}, "agency"),
    ({"id": "p5", "unit_amount": 900, "currency": "gbp", "recurring": {"interval": "month"}}, None),
    ({"id": "p6", "unit_amount": 9900, "currency": "usd", "recurring": {"interval": "month"}}, None),
    ({"id": "p7", "unit_amount": 9900, "currency": "gbp"}, None),
])
def test_plan_detected_from_price_amount_when_ids_not_configured(monkeypatch, price, tier):
    monkeypatch.setattr(config, "STRIPE_PRICES_PRO", [])
    monkeypatch.setattr(config, "STRIPE_PRICES_AGENCY", [])
    assert at._tier_for_price(price) == tier


def test_configured_price_ids_take_precedence(monkeypatch):
    monkeypatch.setattr(config, "STRIPE_PRICES_PRO", ["price_pro"])
    monkeypatch.setattr(config, "STRIPE_PRICES_AGENCY", ["price_agency"])
    assert at._tier_for_price({"id": "price_agency", "unit_amount": 100}) == "agency"
    big = {"id": "other", "unit_amount": 19900, "currency": "gbp", "recurring": {"interval": "month"}}
    assert at._tier_for_price(big) is None
