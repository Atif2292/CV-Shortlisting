"""
TalentIQ — AI-Powered CV Screening
"""

import os
import streamlit as st
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from utils.pdf_parser import extract_pdf_text
from utils.docx_parser import extract_docx_text
from utils.ai_scoring import extract_resume_keywords, rank_candidates_batch
from utils.email_sender import send_shortlist_emails, test_brevo_key, send_test_email
from utils.cleanup import delete_uploaded_files


st.set_page_config(
    page_title="TalentIQ — Screen CVs in Minutes",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ─────────────────────────── CSS ─────────────────────────────────────────────
def build_css(dark: bool) -> str:
    if dark:
        bg = "#0A0C14"; sf = "#131621"; sf2 = "#1A1D2E"
        tx = "#F0F2F8"; sub = "#8B95A8"; br = "#1D2235"
        ibg = "#1A1D2E"; ibr = "#252A3D"; itx = "#F0F2F8"
        lbl = "#8B95A8"; mv = "#F0F2F8"; ml = "#8B95A8"
        tcbg = "#1A1D2E"; sh = "rgba(0,0,0,.45)"; sh2 = "rgba(0,0,0,.6)"
    else:
        bg = "#FFFFFF"; sf = "#F7F9FC"; sf2 = "#EEF2F8"
        tx = "#0B1120"; sub = "#64748B"; br = "#E4E9F0"
        ibg = "#FFFFFF"; ibr = "#CDD5DF"; itx = "#0B1120"
        lbl = "#4B5563"; mv = "#0B1120"; ml = "#64748B"
        tcbg = "#FFFFFF"; sh = "rgba(10,20,60,.06)"; sh2 = "rgba(10,20,60,.1)"

    return f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

/* ── Base reset ── */
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
html,body,[class*="css"]{{
    font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;
    -webkit-font-smoothing:antialiased;
}}

/* ── Streamlit scaffold ── */
[data-testid="stAppViewContainer"]{{background:{bg}!important;}}
[data-testid="stHeader"]{{display:none!important;}}
[data-testid="block-container"]{{
    background:{bg};
    padding:0 2.5rem 4rem!important;
    max-width:1300px;
}}

/* Kill Streamlit's auto anchor-link icons on every heading */
[data-testid="stMarkdownContainer"] [data-testid="stHeaderActionElements"],
[data-testid="stMarkdownContainer"] a.anchor-link,
[data-testid="stMarkdownContainer"] .stMarkdownContainer a[href^="#"]{{
    display:none!important;
}}

[data-testid="stMetricValue"]{{color:{mv}!important;font-weight:800!important;font-size:1.6rem!important;}}
[data-testid="stMetricLabel"]{{color:{ml}!important;font-size:.82rem!important;}}

/* ── Navbar ── */
.iq-nav{{
    display:flex;align-items:center;justify-content:space-between;
    padding:1.1rem 0 1rem;
    border-bottom:1px solid {br};
    margin-bottom:0;
}}
.iq-logo{{font-size:1.45rem;font-weight:900;color:{tx};letter-spacing:-.5px;line-height:1;}}
.iq-logo b{{color:#2563EB;}}
.iq-nav-r{{display:flex;align-items:center;gap:.75rem;}}
.iq-nav-login{{
    font-size:.875rem;font-weight:500;color:{sub};
    padding:.4rem .85rem;border-radius:6px;border:none;
    background:none;cursor:pointer;transition:color .15s;
}}
.iq-nav-login:hover{{color:{tx};}}
.iq-nav-demo{{
    font-size:.875rem;font-weight:600;color:#fff;background:#2563EB;
    padding:.45rem 1.15rem;border-radius:8px;border:none;cursor:pointer;
    box-shadow:0 2px 8px rgba(37,99,235,.3);transition:background .15s;
}}
.iq-nav-demo:hover{{background:#1D4ED8;}}

/* ── Hero ── */
.iq-hero{{
    text-align:center;
    padding:4.5rem 1rem 3rem;
    max-width:720px;margin:0 auto;
}}
.iq-eye{{
    display:inline-block;font-size:.68rem;font-weight:700;
    letter-spacing:.18em;color:#2563EB;text-transform:uppercase;
    background:rgba(37,99,235,.07);padding:.35rem 1rem;
    border-radius:99px;border:1px solid rgba(37,99,235,.15);
    margin-bottom:1.2rem;
}}
/* Use div, NOT h1/h2/h3 — Streamlit injects anchor link icons on those */
.iq-h1{{
    font-size:3.6rem;font-weight:900;line-height:1.06;
    color:{tx};margin-bottom:1.1rem;letter-spacing:-2.5px;
}}
.iq-h1 .bl{{color:#2563EB;}}
.iq-sub{{
    font-size:1.07rem;color:{sub};max-width:490px;
    margin:0 auto 2.2rem;line-height:1.75;
}}
.iq-btns{{display:flex;align-items:center;justify-content:center;gap:.9rem;flex-wrap:wrap;}}
.iq-bp{{
    background:#2563EB;color:#fff;font-weight:600;font-size:.975rem;
    border:none;border-radius:10px;padding:.78rem 2rem;cursor:pointer;
    text-decoration:none;display:inline-flex;align-items:center;gap:.4rem;
    box-shadow:0 4px 16px rgba(37,99,235,.38);
    transition:background .18s,box-shadow .18s,transform .12s;
}}
.iq-bp:hover{{background:#1D4ED8;box-shadow:0 6px 24px rgba(37,99,235,.48);transform:translateY(-1px);}}
.iq-bs{{
    background:none;color:{tx};font-weight:500;font-size:.975rem;
    border:1.5px solid {br};border-radius:10px;padding:.78rem 2rem;
    cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;gap:.4rem;
    transition:border-color .18s,color .18s;
}}
.iq-bs:hover{{border-color:#2563EB;color:#2563EB;}}

/* ── Steps row ── */
.iq-steps{{
    display:flex;align-items:flex-start;justify-content:center;
    padding:2.8rem 0 3rem;max-width:660px;margin:0 auto;
}}
.iq-step{{flex:1;text-align:center;padding:0 .9rem;}}
.iq-snum{{
    width:44px;height:44px;background:#2563EB;color:#fff;
    font-weight:800;font-size:1rem;border-radius:50%;
    display:flex;align-items:center;justify-content:center;
    margin:0 auto .9rem;
    box-shadow:0 4px 14px rgba(37,99,235,.32);
}}
.iq-st{{font-size:.95rem;font-weight:700;color:{tx};margin-bottom:.3rem;}}
.iq-ss{{font-size:.82rem;color:{sub};line-height:1.55;}}
.iq-arr{{color:{sub};font-size:.85rem;margin-top:14px;flex-shrink:0;opacity:.5;}}
.iq-div{{height:1px;background:{br};margin:0 0 3rem;}}

/* ── Cards ── */
.iq-card{{
    background:{sf};border:1px solid {br};border-radius:16px;
    padding:1.7rem 1.9rem;margin-bottom:1.2rem;
    box-shadow:0 2px 10px {sh};
    transition:box-shadow .2s;
}}
.iq-card:focus-within{{box-shadow:0 4px 20px {sh2};border-color:rgba(37,99,235,.25);}}
.iq-ct{{
    font-size:.7rem;font-weight:700;color:{sub};
    letter-spacing:.1em;text-transform:uppercase;
    margin-bottom:1rem;display:flex;align-items:center;gap:.45rem;
}}
.iq-step-badge{{
    display:inline-flex;align-items:center;justify-content:center;
    width:22px;height:22px;background:#2563EB;color:#fff;
    font-size:.7rem;font-weight:800;border-radius:50%;
    box-shadow:0 2px 6px rgba(37,99,235,.3);flex-shrink:0;
}}

/* ── Widgets ── */
.stTextInput>div>div>input,
.stTextArea>div>div>textarea,
input[type="number"]{{
    background:{ibg}!important;
    border:1.5px solid {ibr}!important;
    color:{itx}!important;
    border-radius:10px!important;
    font-size:.93rem!important;
    font-family:'Inter',sans-serif!important;
    transition:border-color .15s,box-shadow .15s!important;
}}
.stTextInput>div>div>input:focus,
.stTextArea>div>div>textarea:focus{{
    border-color:#2563EB!important;
    box-shadow:0 0 0 3px rgba(37,99,235,.13)!important;
    outline:none!important;
}}
.stButton>button{{
    background:linear-gradient(135deg,#2563EB 0%,#3B82F6 100%)!important;
    color:#fff!important;border:none!important;border-radius:10px!important;
    font-weight:700!important;font-size:1rem!important;
    padding:.78rem 1.8rem!important;letter-spacing:-.01em!important;
    box-shadow:0 4px 16px rgba(37,99,235,.38)!important;
    transition:all .18s!important;
}}
.stButton>button:hover{{
    background:linear-gradient(135deg,#1D4ED8 0%,#2563EB 100%)!important;
    box-shadow:0 6px 24px rgba(37,99,235,.48)!important;
    transform:translateY(-1px)!important;opacity:1!important;
}}
label,.stFileUploader label{{
    color:{lbl}!important;font-size:.875rem!important;font-weight:500!important;
}}
.stProgress>div>div>div{{
    background:linear-gradient(90deg,#2563EB,#60A5FA)!important;
    border-radius:99px!important;
}}
.stDataFrame{{border-radius:12px;overflow:hidden;border:1px solid {br}!important;}}
.stExpander{{
    border:1px solid {br}!important;border-radius:12px!important;
    overflow:hidden!important;background:{sf}!important;
}}
[data-testid="stFileUploaderDropzone"]{{
    border:2px dashed {ibr}!important;border-radius:12px!important;
    background:{ibg}!important;transition:border-color .2s,background .2s!important;
    padding:1.4rem!important;
}}
[data-testid="stFileUploaderDropzone"]:hover{{
    border-color:#2563EB!important;
    background:rgba(37,99,235,.03)!important;
}}

/* ── Result list ── */
.iq-rc{{
    display:flex;align-items:center;justify-content:space-between;
    padding:.9rem 1.1rem;border:1px solid {br};border-radius:12px;
    margin-bottom:.55rem;background:{sf};
    transition:box-shadow .18s,border-color .18s;
}}
.iq-rc:hover{{box-shadow:0 4px 16px {sh2};border-color:rgba(37,99,235,.2);}}
.iq-rcl{{display:flex;align-items:center;gap:.9rem;}}
.iq-av{{
    width:42px;height:42px;border-radius:50%;flex-shrink:0;
    background:linear-gradient(135deg,#DBEAFE,#EDE9FE);
    display:flex;align-items:center;justify-content:center;
    font-size:.9rem;font-weight:800;color:#2563EB;
}}
.iq-rn{{font-weight:700;font-size:.92rem;color:{tx};}}
.iq-rr{{font-size:.78rem;color:{sub};margin-top:2px;}}
.iq-scr{{text-align:right;flex-shrink:0;}}
.iq-sv{{font-size:1.15rem;font-weight:900;color:#2563EB;}}
.iq-sd{{font-size:.8rem;color:{sub};font-weight:500;}}
.iq-stars{{font-size:.82rem;color:#F59E0B;line-height:1.4;}}

/* ── Detail card ── */
.iq-det{{background:{sf};border:1px solid {br};border-radius:12px;padding:1.4rem;}}
.iq-tag{{
    display:inline-block;background:rgba(37,99,235,.07);color:#2563EB;
    border:1px solid rgba(37,99,235,.15);border-radius:6px;
    padding:3px 9px;font-size:.77rem;margin:2px;font-weight:500;
}}
.iq-tag-g{{background:rgba(5,150,105,.07);color:#059669;border-color:rgba(5,150,105,.15);}}
.iq-tag-m{{background:rgba(100,116,139,.07);color:#64748B;border-color:rgba(100,116,139,.15);}}
.iq-tag-r{{background:rgba(220,38,38,.07);color:#DC2626;border-color:rgba(220,38,38,.15);}}
.rec-highly     {{background:#DCFCE7;color:#15803D;border-radius:7px;padding:4px 12px;font-size:.82rem;font-weight:600;display:inline-block;}}
.rec-recommended{{background:#DBEAFE;color:#1D4ED8;border-radius:7px;padding:4px 12px;font-size:.82rem;font-weight:600;display:inline-block;}}
.rec-review     {{background:#FEF3C7;color:#92400E;border-radius:7px;padding:4px 12px;font-size:.82rem;font-weight:600;display:inline-block;}}
.rec-unsuitable {{background:#F3F4F6;color:#6B7280;border-radius:7px;padding:4px 12px;font-size:.82rem;font-weight:600;display:inline-block;}}

/* ── Testimonials ── */
.iq-ts-sec{{
    background:{sf};border:1px solid {br};border-radius:20px;
    padding:3rem 2.5rem;margin:3rem 0 2rem;
}}
.iq-ts-h{{font-size:1.85rem;font-weight:900;color:{tx};letter-spacing:-.5px;margin-bottom:.4rem;}}
.iq-ts-s{{color:{sub};font-size:.93rem;margin-bottom:2.2rem;}}
.iq-tg{{display:grid;grid-template-columns:repeat(3,1fr);gap:1.3rem;}}
.iq-tc{{background:{tcbg};border:1px solid {br};border-radius:13px;padding:1.5rem;transition:box-shadow .2s;}}
.iq-tc:hover{{box-shadow:0 6px 22px {sh2};}}
.iq-tq{{font-size:2rem;color:#2563EB;line-height:1;margin-bottom:.65rem;}}
.iq-tt{{font-size:.875rem;color:{sub};line-height:1.75;margin-bottom:1.1rem;}}
.iq-tp{{display:flex;align-items:center;gap:.65rem;}}
.iq-tav{{
    width:36px;height:36px;border-radius:50%;flex-shrink:0;
    background:linear-gradient(135deg,#DBEAFE,#EDE9FE);
    display:flex;align-items:center;justify-content:center;
    font-weight:700;color:#2563EB;font-size:.82rem;
}}
.iq-tpn{{font-weight:700;font-size:.83rem;color:{tx};}}
.iq-tpc{{font-size:.77rem;color:{sub};}}

/* ── Footer CTA ── */
.iq-fcta{{text-align:center;padding:3.5rem 1rem 3rem;border-top:1px solid {br};}}
.iq-fi{{font-size:2.4rem;margin-bottom:.9rem;}}
/* div acting as heading — no h-tags here */
.iq-fh{{font-size:2.3rem;font-weight:900;color:{tx};line-height:1.14;margin-bottom:.8rem;letter-spacing:-1px;}}
.iq-fh b{{color:#2563EB;font-weight:900;}}
.iq-fs{{font-size:.98rem;color:{sub};margin-bottom:2rem;max-width:420px;margin-left:auto;margin-right:auto;line-height:1.7;}}
.iq-fck{{font-size:.82rem;color:{sub};margin-top:.9rem;}}

/* ── Responsive — tablet ── */
@media(max-width:900px){{
    .iq-h1{{font-size:2.8rem;letter-spacing:-1.8px;}}
    .iq-tg{{grid-template-columns:1fr;}}
}}
/* ── Responsive — mobile ── */
@media(max-width:640px){{
    [data-testid="block-container"]{{padding:0 1.1rem 3rem!important;}}
    .iq-hero{{padding:3rem .5rem 2rem;}}
    .iq-h1{{font-size:2.2rem;letter-spacing:-1.2px;}}
    .iq-sub{{font-size:.95rem;}}
    .iq-btns{{flex-direction:column;align-items:stretch;max-width:280px;margin:0 auto;}}
    .iq-bp,.iq-bs{{text-align:center;justify-content:center;}}
    .iq-steps{{flex-direction:column;align-items:center;gap:.4rem;padding:2rem 0;}}
    .iq-arr{{transform:rotate(90deg);margin:0;}}
    .iq-step{{width:100%;max-width:260px;}}
    .iq-fh{{font-size:1.8rem;}}
    .iq-ts-sec{{padding:2rem 1.2rem;}}
    .iq-nav-login{{display:none;}}
}}

hr{{border-color:{br}!important;margin:1.5rem 0!important;}}
</style>"""


# ─────────────────────────── Session & theme init ────────────────────────────
_dark = st.session_state.get("nm_toggle", False)
st.markdown(build_css(_dark), unsafe_allow_html=True)

for _k, _v in [
    ("results",          []),
    ("processed",        False),
    ("uploaded_paths",   []),
    ("brevo_api_key",    os.getenv("BREVO_API_KEY", "")),
    ("brevo_from_email", os.getenv("BREVO_FROM_EMAIL", "")),
]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

_c_sub = "#8B95A8" if _dark else "#64748B"
_c_hl  = "#818CF8" if _dark else "#2563EB"
_c_tx  = "#F0F2F8" if _dark else "#0B1120"
_c_sf  = "#131621" if _dark else "#F7F9FC"


# ─────────────────────────── Night toggle + Navbar ───────────────────────────
_nc, _tc = st.columns([9, 2])
with _tc:
    st.toggle("🌙 Night mode", key="nm_toggle")

st.markdown("""
<div class="iq-nav">
  <div class="iq-logo">Talent<b>IQ</b></div>
  <div class="iq-nav-r">
    <button class="iq-nav-login">Login</button>
    <button class="iq-nav-demo">Book a Demo</button>
  </div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────── Hero ────────────────────────────────────────────
# NOTE: all "headings" use <div> not <h1>/<h2>/<h3>
# Streamlit injects clickable anchor icons into h-tags — divs are clean.
st.markdown("""
<div class="iq-hero">
  <div class="iq-eye">AI-Powered CV Screening for Recruitment Agencies</div>
  <div class="iq-h1">Screen <span class="bl">100</span> CVs in<br>minutes not hours.</div>
  <div class="iq-sub">TalentIQ analyses CVs, ranks candidates, generates summaries
  and helps recruiters shortlist top talent in minutes.</div>
  <div class="iq-btns">
    <a class="iq-bp">Try TalentIQ Free &nbsp;&rarr;</a>
    <a class="iq-bs">How it works &nbsp;&#9654;</a>
  </div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────── Steps row ───────────────────────────────────────
st.markdown("""
<div class="iq-steps">
  <div class="iq-step">
    <div class="iq-snum">1</div>
    <div class="iq-st">Upload Job Description</div>
    <div class="iq-ss">Paste or upload the job description</div>
  </div>
  <div class="iq-arr">&rarr;</div>
  <div class="iq-step">
    <div class="iq-snum">2</div>
    <div class="iq-st">Upload CVs</div>
    <div class="iq-ss">Upload any CV format. No friction.</div>
  </div>
  <div class="iq-arr">&rarr;</div>
  <div class="iq-step">
    <div class="iq-snum">3</div>
    <div class="iq-st">Get Ranked Results</div>
    <div class="iq-ss">AI ranks and scores the best matches</div>
  </div>
</div>
<div class="iq-div"></div>
""", unsafe_allow_html=True)


# ─────────────────────────── Helpers ─────────────────────────────────────────
def _fmt_score(score: int):
    s10  = round(score / 10, 1)
    lbl  = f"{s10:.1f}" if s10 % 1 else f"{int(s10)}.0"
    full = min(5, round(score / 20))
    return lbl, "★" * full + "☆" * (5 - full)


def _rec_badge(text: str) -> str:
    t = text.lower()
    if "highly" in t:               css = "rec-highly"
    elif "not" in t and ("suit" in t or "recommend" in t): css = "rec-unsuitable"
    elif "review" in t or "manual" in t: css = "rec-review"
    elif "recommend" in t:          css = "rec-recommended"
    else:
        return f'<span style="font-size:.9rem;color:{_c_sub}">{text}</span>'
    return f'<span class="{css}">{text}</span>'


def _read_cv(path: str, fname: str) -> str:
    ext = Path(fname).suffix.lower()
    if ext == ".pdf":
        return extract_pdf_text(path)
    if ext == ".docx":
        return extract_docx_text(path)
    if ext == ".txt":
        try:
            return Path(path).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""
    return ""


# ─────────────────────────── Two-column layout ───────────────────────────────
left_col, right_col = st.columns([1, 1.75], gap="large")


# ══════════════════════════════════════════════════════════════════════════════
# LEFT — simplified form
# ══════════════════════════════════════════════════════════════════════════════
with left_col:

    # ── Step 1 — Job Description ──────────────────────────────────────────────
    st.markdown("""
<div class="iq-card">
  <div class="iq-ct">
    <div class="iq-step-badge">1</div>
    Job Description
  </div>
</div>
""", unsafe_allow_html=True)

    # Streamlit widgets rendered directly (outside the HTML div above for proper Streamlit rendering)
    job_title = st.text_input(
        "Job Title",
        placeholder="e.g. Senior Backend Engineer",
        label_visibility="visible",
    )
    job_description = st.text_area(
        "Job Description",
        placeholder="Paste the full job description here. TalentIQ will automatically extract required skills, experience level and seniority from the text.",
        height=230,
    )

    # ── Step 2 — Upload CVs ───────────────────────────────────────────────────
    st.markdown("""
<div class="iq-card" style="margin-top:.5rem">
  <div class="iq-ct">
    <div class="iq-step-badge">2</div>
    Upload CVs
  </div>
</div>
""", unsafe_allow_html=True)

    cv_files = st.file_uploader(
        "PDF, DOCX or TXT — drop multiple files at once",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        key="cv_up",
        label_visibility="visible",
    )
    total_uploaded = len(cv_files or [])
    if total_uploaded:
        st.caption(f"✅ {total_uploaded} file{'s' if total_uploaded != 1 else ''} ready · max 100")

    # ── Optional settings (collapsed) ────────────────────────────────────────
    with st.expander("⚙️  Email & settings (optional)"):
        send_emails    = st.checkbox("Auto-email top 10 shortlisted candidates", value=True)
        recruiter_name = st.text_input("Recruiter / company name", value="Recruitment Team")
        st.text_input(
            "Your email address (Brevo sender)",
            key="brevo_from_email",
            placeholder="you@gmail.com",
        )
        st.text_input(
            "Brevo API Key",
            key="brevo_api_key",
            type="password",
            placeholder="xkeysib-••••••••••",
        )
        _from = (st.session_state.get("brevo_from_email") or "").strip()
        with st.expander("📋 How to set up Brevo (free, 2 min)"):
            st.markdown(f"""
**1.** Create free account → [app.brevo.com](https://app.brevo.com) · 300 emails/day

**2.** Verify your sender: Brevo → **Senders & IP → Senders → Add a Sender**
Enter `{_from or "your email"}` → verify via email link

**3.** Get API key: Brevo → top menu → **SMTP & API → API Keys → Generate**

*Works with Gmail, Outlook, Yahoo — no domain or app password needed.*
""")
        _e1, _e2 = st.columns(2)
        with _e1:
            if st.button("🔑 Verify Key", use_container_width=True):
                _ok, _msg = test_brevo_key(st.session_state.get("brevo_api_key", ""))
                (st.success if _ok else st.error)(f"{'✅' if _ok else '❌'} {_msg}")
        with _e2:
            if st.button("📧 Send Test", use_container_width=True):
                _ok, _msg = send_test_email(
                    st.session_state.get("brevo_api_key", ""),
                    st.session_state.get("brevo_from_email", ""),
                )
                (st.success if _ok else st.error)(f"{'✅' if _ok else '❌'} {_msg}")

    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    run_btn = st.button("🚀  Screen Candidates", use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# RIGHT — results
# ══════════════════════════════════════════════════════════════════════════════
with right_col:

    if run_btn:
        errors = []
        if not job_title.strip():
            errors.append("Please enter a Job Title.")
        if not job_description.strip():
            errors.append("Please paste the Job Description.")
        if total_uploaded == 0:
            errors.append("Please upload at least one CV.")
        if total_uploaded > 100:
            errors.append("Maximum 100 CVs per batch.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            upload_dir = Path("uploads")
            upload_dir.mkdir(exist_ok=True)
            saved_paths, saved_names = [], []
            for f in (cv_files or []):
                dest = upload_dir / f.name
                dest.write_bytes(f.read())
                saved_paths.append(str(dest))
                saved_names.append(f.name)

            st.session_state.uploaded_paths = saved_paths

            # Use the job description text for skill matching (no separate skills field)
            job_context = {
                "title":            job_title.strip(),
                "skills":           job_description.strip()[:300],  # first 300 chars as skill hint
                "years_experience": 0,
                "description":      job_description.strip(),
            }

            # Phase 1 — extract keywords from each CV
            candidates = []
            bar   = st.progress(0, text="Reading CVs…")
            _info = st.empty()

            for idx, (path, fname) in enumerate(zip(saved_paths, saved_names), 1):
                _info.markdown(
                    f'<p style="font-size:.85rem;color:{_c_sub}">'
                    f'📄 Reading <b style="color:{_c_hl}">{fname}</b>'
                    f' ({idx}/{len(saved_paths)})</p>',
                    unsafe_allow_html=True,
                )
                try:
                    text = _read_cv(path, fname)
                    if not text.strip():
                        st.warning(f"⚠️ No text extracted from {fname} — skipping.")
                        continue
                    candidates.append(
                        extract_resume_keywords(cv_text=text, required_skills="")
                    )
                except Exception as ex:
                    st.warning(f"⚠️ Error reading {fname}: {ex}")
                bar.progress(idx / len(saved_paths) * 0.5,
                             text=f"Reading CVs — {idx}/{len(saved_paths)} done…")

            # Phase 2 — single AI ranking call
            if candidates:
                _info.markdown(
                    f'<p style="font-size:.85rem;color:{_c_sub}">'
                    f'🤖 Ranking <b style="color:{_c_hl}">{len(candidates)} candidates</b>'
                    f' with AI…</p>',
                    unsafe_allow_html=True,
                )
                bar.progress(0.55, text=f"AI ranking {len(candidates)} candidates…")
                try:
                    results = rank_candidates_batch(candidates=candidates, job_context=job_context)
                except RuntimeError as _err:
                    bar.empty(); _info.empty()
                    _em = str(_err)
                    if "api" in _em.lower() and "key" in _em.lower():
                        st.error(
                            "❌ **OpenAI API key missing or invalid.**\n\n"
                            "Fix: Streamlit Cloud → your app → ⚙️ Settings → Secrets → add:\n"
                            "```\nOPENAI_API_KEY = \"sk-proj-...\"\n```"
                        )
                    else:
                        st.error(f"❌ AI ranking failed: {_em}")
                    st.session_state.processed = False
                    st.stop()
            else:
                results = []

            bar.progress(1.0, text="✅ Done!"); _info.empty()
            st.session_state.results   = results
            st.session_state.processed = True

            # Email top 10
            if send_emails and results:
                with st.spinner("Sending shortlist emails…"):
                    report = send_shortlist_emails(
                        candidates=results[:10],
                        job_title=job_title,
                        recruiter_name=recruiter_name,
                        brevo_api_key=st.session_state.get("brevo_api_key", ""),
                        from_email=st.session_state.get("brevo_from_email", ""),
                    )
                if report["sent"]:
                    st.success(f"📧 Emails sent to {len(report['sent'])} candidates.")
                if report["failed"]:
                    st.warning(f"⚠️ Failed: {', '.join(report['failed'])}")

            deleted, _ = delete_uploaded_files(saved_paths)
            if deleted:
                st.caption(f"🗑️ {len(deleted)} file(s) deleted from server.")

    # ── Results ──────────────────────────────────────────────────────────────
    if st.session_state.processed and st.session_state.results:
        results = st.session_state.results

        # Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Screened",    len(results))
        m2.metric("Shortlisted", min(10, len(results)))
        avg_raw = sum(r.get("match_score", 0) for r in results) / len(results)
        m3.metric("Avg Score",   f"{round(avg_raw / 10, 1)}/10")

        st.markdown(
            f'<div style="height:.2rem"></div>'
            f'<div style="font-size:.7rem;font-weight:700;letter-spacing:.1em;'
            f'text-transform:uppercase;color:{_c_sub};margin:1.2rem 0 .8rem">'
            f'🏆 Top Candidates</div>',
            unsafe_allow_html=True,
        )

        for rank, r in enumerate(results[:10], 1):
            score    = r.get("match_score", 0)
            name     = r.get("candidate_name", "Unknown")
            email    = r.get("email", "")
            s_lbl, s_stars = _fmt_score(score)
            initials = "".join(w[0].upper() for w in name.split()[:2]) or "?"

            st.markdown(f"""
<div class="iq-rc">
  <div class="iq-rcl">
    <div class="iq-av">{initials}</div>
    <div>
      <div class="iq-rn">#{rank}&nbsp; {name}</div>
      <div class="iq-rr">{email}</div>
    </div>
  </div>
  <div class="iq-scr">
    <div><span class="iq-sv">{s_lbl}</span><span class="iq-sd">/10</span></div>
    <div class="iq-stars">{s_stars}</div>
  </div>
</div>""", unsafe_allow_html=True)

        st.markdown(
            f'<div style="font-size:.7rem;font-weight:700;letter-spacing:.1em;'
            f'text-transform:uppercase;color:{_c_sub};margin:1.4rem 0 .8rem">'
            f'📋 Detailed Profiles</div>',
            unsafe_allow_html=True,
        )

        for rank, r in enumerate(results[:10], 1):
            score     = r.get("match_score", 0)
            name      = r.get("candidate_name", "Unknown")
            email     = r.get("email", "—")
            rec       = r.get("recommendation", "—")
            strengths = r.get("strengths", [])
            concerns  = r.get("concerns", [])
            s_lbl, s_stars = _fmt_score(score)
            c_cls = "iq-tag-m" if score >= 70 else "iq-tag-r"

            str_html = " ".join(f'<span class="iq-tag iq-tag-g">✓ {s}</span>' for s in strengths)
            con_html = " ".join(f'<span class="iq-tag {c_cls}">✗ {c}</span>' for c in concerns)

            with st.expander(
                f"#{rank} — {name}  ·  {s_lbl}/10  {s_stars}",
                expanded=(rank <= 3),
            ):
                st.markdown(f"""
<div class="iq-det">
  <div style="font-weight:700;font-size:1rem;color:{_c_tx}">{name}</div>
  <div style="font-size:.82rem;color:{_c_sub};margin-bottom:.9rem">{email}</div>
  <span style="font-size:1.9rem;font-weight:900;color:#2563EB">{s_lbl}</span>
  <span style="font-size:.95rem;color:{_c_sub}">/10 &nbsp;{s_stars}</span>
  <hr style="margin:.75rem 0">
  <div style="font-size:.7rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:{_c_sub};margin-bottom:5px">Strengths</div>
  {str_html or f'<span style="color:{_c_sub};font-size:.85rem">None noted</span>'}
  <div style="font-size:.7rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:{_c_sub};margin:.75rem 0 5px">Concerns</div>
  {con_html or f'<span style="color:{_c_sub};font-size:.85rem">None noted</span>'}
  <div style="font-size:.7rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:{_c_sub};margin:.75rem 0 5px">Recommendation</div>
  {_rec_badge(rec)}
</div>""", unsafe_allow_html=True)

        # Full table
        st.markdown("---")
        df = pd.DataFrame([
            {
                "Rank":      i + 1,
                "Candidate": r.get("candidate_name", ""),
                "Score":     f"{_fmt_score(r.get('match_score', 0))[0]}/10",
                "Email":     r.get("email", ""),
                "Verdict":   r.get("recommendation", ""),
            }
            for i, r in enumerate(results)
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)

        csv = pd.DataFrame([
            {
                "Rank":           i + 1,
                "Name":           r.get("candidate_name", ""),
                "Email":          r.get("email", ""),
                "Score":          f"{_fmt_score(r.get('match_score', 0))[0]}/10",
                "Strengths":      "; ".join(r.get("strengths", [])),
                "Concerns":       "; ".join(r.get("concerns", [])),
                "Recommendation": r.get("recommendation", ""),
            }
            for i, r in enumerate(results)
        ]).to_csv(index=False)

        st.download_button(
            "⬇️ Download Results CSV",
            data=csv, file_name="talentiq_results.csv",
            mime="text/csv", use_container_width=True,
        )

    elif st.session_state.processed and not st.session_state.results:
        st.error("❌ No candidates could be processed. Check your CV files and try again.")

    else:
        # Idle state
        st.markdown(f"""
<div style="text-align:center;padding:5rem 2rem;">
  <div style="font-size:3rem;margin-bottom:1.2rem">📊</div>
  <div style="font-size:1.1rem;font-weight:700;color:{_c_tx};margin-bottom:.5rem">
    Your ranked results will appear here
  </div>
  <div style="font-size:.92rem;color:{_c_sub};line-height:1.7;max-width:340px;margin:0 auto">
    Fill in the job description,<br>upload CVs, then click
    <span style="color:#2563EB;font-weight:600">Screen Candidates</span>.
  </div>
  <div style="margin-top:2rem;padding:1.2rem 1.5rem;border-radius:12px;
    background:rgba(37,99,235,.05);border:1px solid rgba(37,99,235,.12);
    display:inline-block;font-size:.82rem;color:{_c_sub}">
    Supports PDF · DOCX · TXT &nbsp;|&nbsp; Up to 100 CVs &nbsp;|&nbsp; Scores shown as X/10
  </div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────── Testimonials ────────────────────────────────────
st.markdown("""
<div class="iq-ts-sec">
  <div style="text-align:center">
    <div class="iq-ts-h">Loved by Recruiters</div>
    <div class="iq-ts-s">Here's what recruitment professionals say about TalentIQ</div>
  </div>
  <div class="iq-tg">
    <div class="iq-tc">
      <div class="iq-tq">&ldquo;</div>
      <div class="iq-tt">TalentIQ has transformed how we screen candidates. We reduced screening time by over 70% and our shortlists are stronger than ever.</div>
      <div class="iq-tp">
        <div class="iq-tav">MR</div>
        <div>
          <div class="iq-tpn">Mark Richardson</div>
          <div class="iq-tpc">Managing Director &middot; Hays Specialist Recruitment</div>
        </div>
      </div>
    </div>
    <div class="iq-tc">
      <div class="iq-tq">&ldquo;</div>
      <div class="iq-tt">What used to take hours of reading CVs now takes minutes. TalentIQ helps us focus on what really matters — speaking to candidates and closing placements.</div>
      <div class="iq-tp">
        <div class="iq-tav">SB</div>
        <div>
          <div class="iq-tpn">Sophie Bennett</div>
          <div class="iq-tpc">Senior Consultant &middot; Michael Page</div>
        </div>
      </div>
    </div>
    <div class="iq-tc">
      <div class="iq-tq">&ldquo;</div>
      <div class="iq-tt">The AI matching accuracy is incredible. We never miss great candidates anymore. TalentIQ is a game changer for our business.</div>
      <div class="iq-tp">
        <div class="iq-tav">DT</div>
        <div>
          <div class="iq-tpn">Daniel Thompson</div>
          <div class="iq-tpc">Director &middot; Robert Half</div>
        </div>
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────── Footer CTA ──────────────────────────────────────
# Using <div class="iq-fh"> not <h2> — avoids Streamlit anchor link injection
st.markdown("""
<div class="iq-fcta">
  <div class="iq-fi">👥</div>
  <div class="iq-fh">Stop Reading CVs.<br><b>Start Making Placements.</b></div>
  <div class="iq-fs">Book a 15-minute demo and see how TalentIQ can save your team hours every single day.</div>
  <button style="background:#2563EB;color:#fff;font-weight:700;font-size:1rem;
    border:none;border-radius:10px;padding:.8rem 2.2rem;cursor:pointer;
    box-shadow:0 4px 16px rgba(37,99,235,.38);transition:background .18s;">
    Book a 15-Minute Demo &nbsp;&rarr;
  </button>
  <div class="iq-fck">&#10003; No credit card required &nbsp;&nbsp;&#10003; Cancel anytime</div>
</div>

<hr>
<div style="text-align:center;color:#94A3B8;font-size:.78rem;padding-bottom:1.5rem">
  TalentIQ &middot; AI CV Screening &middot; Built with Streamlit &amp; GPT-4o
</div>
""", unsafe_allow_html=True)
