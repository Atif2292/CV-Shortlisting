"""End-to-end checks of app.py with Streamlit's AppTest (no network, no OpenAI)."""

import io
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from utils import account_tracker as at_mod
from utils import config

APP = str(Path(__file__).resolve().parent.parent / "app.py")
TIMEOUT = 60


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_URL", f"sqlite:///{tmp_path}/app.db")
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "")
    monkeypatch.setattr(config, "IS_PRODUCTION", False)
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setattr(at_mod, "_engine", None)
    yield
    at_mod._engine = None


def _all_markdown(at) -> str:
    return "\n".join(m.value for m in at.markdown)


def _button(at, label_part):
    return next(b for b in at.button if label_part in b.label)


def test_production_guard_blocks_unsafe_config(monkeypatch):
    monkeypatch.setattr(config, "IS_PRODUCTION", True)
    at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    assert at.error and "not configured for production" in at.error[0].value
    assert "APP_SECRET" in at.error[0].value


def test_legal_pages_render():
    for page, heading in [("privacy", "Privacy Notice"), ("terms", "Terms of Service"),
                          ("dpa", "Data Processing Agreement"), ("subprocessors", "Sub-processors"),
                          ("cookies", "Cookie Notice")]:
        at = AppTest.from_file(APP, default_timeout=TIMEOUT)
        at.query_params["page"] = page
        at.run()
        assert not at.exception, at.exception
        assert heading in _all_markdown(at)


def test_home_page_has_no_false_claims():
    at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    assert not at.exception, at.exception
    text = _all_markdown(at)
    for banned in ("Zero Cloud Storage", "Zapier", "£0.12", "Annual Billing", "14 days", "25 CV",
                   "99%", "Greenhouse", "interview scheduling", "RCV-PRO", "Try 10 Demo",
                   "WhatsApp", "wa.me", "Alex Chen"):
        assert banned not in text, banned
    assert "Reviews &amp; Testimonials" in text or "Reviews & Testimonials" in text
    assert "support@rankcv.io" in text
    for hidden in ("Bring Your Own Key", "Private Engine", "GDPR &amp; Legal", "own OpenAI"):
        assert hidden not in text, hidden
    assert not any("Cloud AI" in r.label for r in at.radio)
    for sample in ("Candidate A", "Candidate E"):
        assert sample in text


def test_screening_requires_sign_in():
    at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    _button(at, "Screen Candidates").click().run()
    assert at.query_params.get("auth") == ["signup"] or at.query_params.get("auth") == "signup"
    assert any(t.label == "Work email" for t in at.text_input)          # sign-up page is showing
    assert not at.session_state.results


def test_navbar_and_cta_offer_log_in_and_sign_up_without_reloading():
    at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    html_out = "\n".join(m.value for m in at.markdown if m.allow_html)
    assert "?auth=" not in html_out and "?page=" not in html_out        # no links that reload the app
    labels = [b.label for b in at.button]
    assert labels.count("Log in") == 1 and labels.count("Sign up free") == 1      # navbar only
    next(b for b in at.button if b.key == "nav_signup").click().run()
    assert any(t.label == "Work email" for t in at.text_input)


def test_legal_pages_open_as_pop_ups():
    at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    next(b for b in at.button if b.key == "legal_footer_main_terms").click().run()
    assert not at.exception, at.exception
    assert "Terms of Service" in "\n".join(m.value for m in at.markdown)


def test_candidate_text_is_html_escaped():
    evil = '<img src=x onerror="alert(1)">'
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    at.session_state["results"] = [{
        "candidate_index": 0, "candidate_name": evil, "email": "x@y.z", "match_score": 70,
        "recommendation": evil, "strengths": [evil], "concerns": [evil], "skills_match": evil,
        "relevant_experience": evil, "processing_mode": evil, "fit_band": "good",
    }]
    at.session_state["processed"] = True
    at.session_state["show_full"] = True
    at.session_state["run_meta"] = {"run_id": "t1", "mode_used": "offline"}
    at.session_state["recruiter_overrides"] = {}
    at.run()
    assert not at.exception, at.exception
    html_out = "\n".join(m.value for m in at.markdown if m.allow_html)
    assert "<img" not in html_out
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in html_out


def test_excel_export_neutralises_formulas_and_reports_real_review_state():
    from utils.report import build_excel_report
    results = [{
        "candidate_index": 0, "candidate_name": '=HYPERLINK("http://evil")', "email": "a@b.co",
        "match_score": 45, "recommendation": "Not recommended.", "strengths": ["+1 skill"],
        "concerns": ["-gap"], "skills_match": "Python", "relevant_experience": "3 years",
        "processing_mode": "Private Engine", "fit_band": "weak",
    }, {
        "candidate_index": 1, "candidate_name": "Reviewed Person", "email": "c@d.co", "match_score": "85",
        "recommendation": "Good", "strengths": [], "concerns": [], "processing_mode": "Cloud AI",
    }]
    overrides = {0: {"status": "Under Review", "score_delta": 0, "notes": "", "decided_at": ""},
                 1: {"status": "Shortlisted", "score_delta": 5, "notes": "@ref", "decided_at": "2026-10-21 10:00 UTC"}}
    xl = build_excel_report(results, overrides, {"run_id": "t2", "mode_used": "offline"}, {}, "Acme")
    sheets = pd.read_excel(io.BytesIO(xl), sheet_name=None)
    res = sheets["RankCV Results"]
    assert res.loc[0, "Name"].startswith("'=")
    assert res.loc[0, "Strengths"].startswith("'+")
    assert res.loc[0, "Recruiter Decision"] == "Under Review"
    assert res.loc[0, "Decision Recorded (UTC)"] == "Not reviewed"
    assert res.loc[1, "Final Score"] == "90%" and res.loc[1, "Recruiter Notes"] == "'@ref"
    audit = sheets["GDPR Audit"].set_index("Audit Parameter")["Record"]
    assert audit["Article 22 Human Oversight"].startswith("1 of 2")
    assert audit["External AI Sub-processor"] == "None (backup engine on our server)"
    assert "VERIFIED" not in " ".join(audit.astype(str))


def _auth_page(mode):
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    at.query_params["auth"] = mode
    return at.run()


def _text(at, label):
    return next(t for t in at.text_input if t.label == label)


@pytest.mark.parametrize("dev_flag", [False, True])
def test_sign_in_code_never_shown_on_screen_outside_localhost(monkeypatch, dev_flag):
    # No email provider configured, as on a fresh deployment before secrets are added.
    for name in ("BREVO_API_KEY", "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"):
        monkeypatch.setattr(config, name, "")
    monkeypatch.setattr(config, "DEV_SHOW_LOGIN_CODE", dev_flag)
    at = _auth_page("signup")
    _text(at, "Work email").set_value("lead@acme-recruit.co.uk")
    next(c for c in at.checkbox if "Terms" in c.label).check()
    _button(at, "Sign Up").click().run()
    assert not at.exception, at.exception
    assert "Development mode" not in " ".join(i.value for i in at.info)
    assert any("couldn't send the email" in e.value for e in at.error)
    assert not at.session_state.auth_pending_email


def test_log_in_with_unknown_email_moves_to_sign_up():
    at = _auth_page("login")
    _text(at, "Email address").set_value("nobody@acme-recruit.co.uk")
    _button(at, "Send login code").click().run()
    assert any(t.label == "Work email" and t.value == "nobody@acme-recruit.co.uk" for t in at.text_input)


def test_sign_up_requires_terms(monkeypatch):
    import utils.mailer as mailer
    monkeypatch.setattr(mailer, "email_configured", lambda: True)
    monkeypatch.setattr(mailer, "send_login_code", lambda to, code: True)
    at = _auth_page("signup")
    _text(at, "Work email").set_value("lead@acme-recruit.co.uk")
    _button(at, "Sign Up").click().run()
    assert any("accept the Terms" in e.value for e in at.error)
    assert not at.session_state.auth_pending_email


def test_sign_up_then_log_in_flow(monkeypatch):
    sent = {}
    import utils.mailer as mailer
    monkeypatch.setattr(mailer, "email_configured", lambda: True)
    monkeypatch.setattr(mailer, "send_login_code", lambda to, code: sent.update(to=to, code=code) or True)

    # Sign up
    at = _auth_page("signup")
    _text(at, "Work email").set_value("Lead@Acme-Recruit.co.uk")
    next(c for c in at.checkbox if "Terms" in c.label).check()
    _button(at, "Sign Up").click().run()
    assert sent["to"] == "lead@acme-recruit.co.uk"
    assert at.session_state.auth_pending_email == "lead@acme-recruit.co.uk"

    wrong = "000000" if sent["code"] != "000000" else "111111"
    _text(at, "6-digit code").set_value(wrong)
    _button(at, "Continue").click().run()
    assert any("Incorrect code" in e.value for e in at.error)

    _text(at, "6-digit code").set_value(sent["code"])
    _button(at, "Continue").click().run()
    assert not at.exception, at.exception
    auth = at.session_state.client_auth
    assert auth["logged_in"] and auth["email"] == "lead@acme-recruit.co.uk" and auth["remaining"] == 10
    assert "auth" not in at.query_params
    token = at.session_state.session_token
    assert at_mod.account_for_session(token)["email"] == "lead@acme-recruit.co.uk"

    # Sign out kills the server-side session
    _button(at, "Sign Out").click().run()
    assert not at.session_state.client_auth["logged_in"]
    assert at_mod.account_for_session(token) == {}

    # Log back in (existing account: no terms box)
    at2 = _auth_page("login")
    _text(at2, "Email address").set_value("lead@acme-recruit.co.uk")
    real_time = at_mod._now
    monkeypatch.setattr(at_mod, "_now", lambda: real_time() + __import__("datetime").timedelta(seconds=61))
    _button(at2, "Send login code").click().run()
    _text(at2, "6-digit code").set_value(sent["code"])
    _button(at2, "Continue").click().run()
    assert at2.session_state.client_auth["logged_in"]


def test_hero_copy_and_no_demo_cvs():
    at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    text = _all_markdown(at)
    assert "Shortlist top talent in" in text and "RankCV scores and ranks every applicant" in text
    assert "Free account includes 10 CV evaluations. No card needed." in text
    assert "Explainable scores. You make the final decision." in text
    assert not any("Demo CVs" in b.label or "demo CVs" in b.label for b in at.button)
    assert "demo CVs" not in text.replace("Demo CVs", "demo CVs")


def test_how_to_use_video_opens():
    at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    next(b for b in at.button if b.key == "hero_video_btn").click().run()
    assert not at.exception, at.exception
    assert len(at.get("video")) == 1


def _signed_in(monkeypatch, email="lead@acme-recruit.co.uk"):
    sent = {}
    import utils.mailer as mailer
    monkeypatch.setattr(mailer, "email_configured", lambda: True)
    monkeypatch.setattr(mailer, "send_login_code", lambda to, code: sent.update(code=code) or True)
    at = _auth_page("signup")
    _text(at, "Work email").set_value(email)
    next(c for c in at.checkbox if "Terms" in c.label).check()
    _button(at, "Sign Up").click().run()
    _text(at, "6-digit code").set_value(sent["code"])
    _button(at, "Continue").click().run()
    assert at.session_state.client_auth["logged_in"]
    return at


def test_signed_in_upload_screen_and_quota(monkeypatch):
    root = Path(APP).parent
    at = _signed_in(monkeypatch)
    jd = next(t for t in at.text_area if "job description" in t.placeholder.lower())
    jd.set_value("Senior Python Backend Engineer with 5 years experience in FastAPI, Django and AWS").run()

    pdfs = sorted((root / "dummy_cvs_pdf").glob("*.pdf"))[:2]
    docx = sorted((root / "dummy_cvs").glob("*.docx"))[:1]
    files = [(p.name, p.read_bytes(), "application/pdf") for p in pdfs]
    files += [(p.name, p.read_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
              for p in docx]
    files.append(("shopping.txt", b"milk\neggs\nbread\nbutter\napples\n", "text/plain"))
    next(u for u in at.file_uploader if u.proto.multiple_files).set_value(files).run()
    _button(at, "Screen Candidates").click().run()
    assert not at.exception, at.exception

    results = at.session_state.results
    assert len(results) >= 3
    statuses = {o["status"] for o in at.session_state.recruiter_overrides.values()}
    assert statuses == {"Under Review"}
    assert all(not o["decided_at"] for o in at.session_state.recruiter_overrides.values())
    # Only scored CVs use quota, and the account matches the session
    auth = at.session_state.client_auth
    assert auth["resumes_used"] == auth["max_resumes"] - auth["remaining"]
    assert 3 <= auth["resumes_used"] <= 4
    assert any("Download Shortlist Report" in d.label for d in at.get("download_button"))


def test_upload_over_remaining_quota_is_blocked(monkeypatch):
    root = Path(APP).parent
    at = _signed_in(monkeypatch, "big@acme-recruit.co.uk")
    pdfs = sorted((root / "dummy_cvs_pdf").glob("*.pdf"))
    files = [(f"{i}_{p.name}", p.read_bytes(), "application/pdf") for i in range(2) for p in pdfs][:11]
    next(u for u in at.file_uploader if u.proto.multiple_files).set_value(files).run()
    assert "this run is limited to 10 CVs" in _all_markdown(at)
    _button(at, "Screen Candidates").click().run()
    assert not at.exception, at.exception
    assert not at.session_state.results
    assert at.session_state.client_auth["resumes_used"] == 0

