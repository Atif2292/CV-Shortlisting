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
                   "99%", "Greenhouse", "interview scheduling", "RCV-PRO", "Try 10 Demo"):
        assert banned not in text, banned
    assert "Reviews &amp; Testimonials" in text or "Reviews & Testimonials" in text


def test_screening_requires_sign_in():
    at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    _button(at, "Screen Candidates").click().run()
    assert any("Please sign in" in e.value for e in at.error)
    assert not at.session_state.results


def test_demo_runs_offline_and_defaults_everyone_to_under_review():
    at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    _button(at, "Try 5 Demo CVs").click().run()
    assert not at.exception, at.exception
    results = at.session_state.results
    assert len(results) == 5
    assert at.session_state.run_meta["mode_used"] == "offline"
    statuses = {o["status"] for o in at.session_state.recruiter_overrides.values()}
    assert statuses == {"Under Review"}
    assert all(not o["decided_at"] for o in at.session_state.recruiter_overrides.values())


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
    audit = sheets["UK GDPR Audit"].set_index("Audit Parameter")["Record"]
    assert audit["Article 22 Human Oversight"].startswith("1 of 2")
    assert audit["External AI Sub-processor"] == "None (Private Engine)"
    assert "VERIFIED" not in " ".join(audit.astype(str))
