"""
TalentIQ — AI-Powered CV Screening
"""

import os
import tempfile
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

# ─────────────────────────── CSS (light mode only) ────────────────────────────
def build_css() -> str:
    return """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

/* ── Base ── */
*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    -webkit-font-smoothing: antialiased;
}
[data-testid="stAppViewContainer"] { background: #F5F7FB !important; }
[data-testid="stHeader"]           { display: none !important; }
[data-testid="block-container"]    {
    background: #F5F7FB;
    padding: 0 2rem 4rem !important;
    max-width: 1280px;
}

/* Kill Streamlit anchor-link icons injected into h-tags */
[data-testid="stMarkdownContainer"] [data-testid="stHeaderActionElements"] { display:none!important; }

[data-testid="stMetricValue"]  { color:#0B1120!important; font-weight:800!important; font-size:1.55rem!important; }
[data-testid="stMetricLabel"]  { color:#64748B!important; font-size:.8rem!important; }

/* ── Panel cards (st.container border=True) ── */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 16px !important;
    box-shadow: 0 2px 12px rgba(10,20,60,.06) !important;
    padding: 1.5rem !important;
    transition: box-shadow .2s !important;
}
[data-testid="stVerticalBlockBorderWrapper"]:focus-within {
    box-shadow: 0 4px 20px rgba(10,20,60,.1) !important;
    border-color: rgba(37,99,235,.25) !important;
}

/* ── Tabs ── */
[data-testid="stTabsTabList"] {
    border-bottom: 1.5px solid #E2E8F0 !important;
    gap: 0 !important;
    margin-bottom: .4rem !important;
}
button[data-testid="stTab"] {
    font-size: .875rem !important;
    font-weight: 500 !important;
    color: #94A3B8 !important;
    padding: .5rem 1.1rem !important;
    border-radius: 0 !important;
    border-bottom: 2px solid transparent !important;
    transition: color .15s !important;
}
button[data-testid="stTab"][aria-selected="true"] {
    color: #2563EB !important;
    border-bottom: 2px solid #2563EB !important;
    font-weight: 600 !important;
    background: none !important;
}
button[data-testid="stTab"]:hover { color: #2563EB !important; }

/* ── Inputs ── */
.stTextInput  > div > div > input,
.stTextArea   > div > div > textarea,
input[type="number"] {
    background: #FFFFFF !important;
    border: 1.5px solid #CBD5E1 !important;
    color: #0B1120 !important;
    border-radius: 10px !important;
    font-size: .93rem !important;
    font-family: 'Inter', sans-serif !important;
    transition: border-color .15s, box-shadow .15s !important;
}
.stTextInput  > div > div > input:focus,
.stTextArea   > div > div > textarea:focus {
    border-color: #2563EB !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,.12) !important;
    outline: none !important;
}
label, .stFileUploader label {
    color: #4B5563 !important;
    font-size: .875rem !important;
    font-weight: 500 !important;
}

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg,#2563EB,#3B82F6) !important;
    color: #fff !important; border: none !important;
    border-radius: 10px !important; font-weight: 700 !important;
    font-size: 1rem !important; padding: .78rem 1.6rem !important;
    box-shadow: 0 4px 14px rgba(37,99,235,.38) !important;
    transition: all .18s !important; letter-spacing: -.01em !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg,#1D4ED8,#2563EB) !important;
    box-shadow: 0 6px 22px rgba(37,99,235,.48) !important;
    transform: translateY(-1px) !important; opacity:1!important;
}

/* ── Progress / upload ── */
.stProgress > div > div > div {
    background: linear-gradient(90deg,#2563EB,#60A5FA) !important;
    border-radius: 99px !important;
}
[data-testid="stFileUploaderDropzone"] {
    border: 2px dashed #CBD5E1 !important;
    border-radius: 12px !important;
    background: #F8FAFC !important;
    transition: border-color .2s, background .2s !important;
    text-align: center !important;
}
[data-testid="stFileUploaderDropzone"]:hover {
    border-color: #2563EB !important;
    background: rgba(37,99,235,.03) !important;
}
.stDataFrame { border-radius: 12px; overflow: hidden; border: 1px solid #E2E8F0 !important; }
.stExpander  { border: 1px solid #E2E8F0 !important; border-radius: 12px !important; background:#FFFFFF!important; }

/* ── Navbar ── */
.iq-nav {
    display: flex; align-items: center; justify-content: space-between;
    padding: 1.1rem 0 1rem; border-bottom: 1px solid #E2E8F0;
    margin-bottom: 0; background: #F5F7FB;
}
.iq-logo { font-size: 1.45rem; font-weight: 900; color: #0B1120; letter-spacing: -.5px; }
.iq-logo b { color: #2563EB; font-weight: 900; }
.iq-nav-demo {
    font-size: .875rem; font-weight: 600; color: #fff; background: #2563EB;
    padding: .45rem 1.15rem; border-radius: 8px; border: none; cursor: pointer;
    box-shadow: 0 2px 8px rgba(37,99,235,.3); transition: background .15s;
}
.iq-nav-demo:hover { background: #1D4ED8; }

/* ── Hero — use <div> not h-tags to avoid Streamlit anchor icons ── */
.iq-hero { text-align: center; padding: 4rem 1rem 2.8rem; max-width: 740px; margin: 0 auto; }
.iq-eye {
    display: inline-block; font-size: .69rem; font-weight: 700;
    letter-spacing: .17em; color: #2563EB; text-transform: uppercase;
    background: rgba(37,99,235,.07); padding: .35rem 1rem;
    border-radius: 99px; border: 1px solid rgba(37,99,235,.15); margin-bottom: 1.1rem;
}
.iq-h1 {
    font-size: 3.6rem; font-weight: 900; line-height: 1.06;
    color: #0B1120; margin-bottom: 1.1rem; letter-spacing: -2.5px;
}
.iq-h1 .bl { color: #2563EB; }
.iq-sub {
    font-size: 1.07rem; color: #64748B; max-width: 500px;
    margin: 0 auto 2rem; line-height: 1.75;
}
.iq-btns { display: flex; align-items: center; justify-content: center; gap: .9rem; flex-wrap: wrap; }
.iq-bp {
    background: #2563EB; color: #fff; font-weight: 600; font-size: .975rem;
    border: none; border-radius: 10px; padding: .78rem 2rem; cursor: pointer;
    text-decoration: none; display: inline-block;
    box-shadow: 0 4px 16px rgba(37,99,235,.38);
    transition: background .18s, box-shadow .18s, transform .12s;
}
.iq-bp:hover { background:#1D4ED8; box-shadow:0 6px 24px rgba(37,99,235,.48); transform:translateY(-1px); }
.iq-bs {
    background: none; color: #0B1120; font-weight: 500; font-size: .975rem;
    border: 1.5px solid #E2E8F0; border-radius: 10px; padding: .78rem 2rem;
    cursor: pointer; text-decoration: none; display: inline-block;
    transition: border-color .18s, color .18s;
}
.iq-bs:hover { border-color: #2563EB; color: #2563EB; }

/* ── Steps row ── */
.iq-steps {
    display: flex; align-items: flex-start; justify-content: center;
    padding: 2.5rem 0 2.2rem; max-width: 680px; margin: 0 auto;
}
.iq-step { flex: 1; text-align: center; padding: 0 .75rem; }
.iq-snum {
    width: 44px; height: 44px; background: #2563EB; color: #fff;
    font-weight: 800; font-size: 1rem; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    margin: 0 auto .85rem; box-shadow: 0 4px 12px rgba(37,99,235,.3);
}
.iq-st { font-size: .95rem; font-weight: 700; color: #0B1120; margin-bottom: .3rem; }
.iq-ss { font-size: .82rem; color: #64748B; line-height: 1.55; }
.iq-arr { color: #CBD5E1; font-size: .8rem; margin-top: 14px; flex-shrink: 0; }
.iq-div { height: 1px; background: #E2E8F0; margin: 0 0 2.2rem; }

/* ── Panel header inside cards ── */
.iq-phead {
    font-size: .7rem; font-weight: 700; letter-spacing: .1em;
    text-transform: uppercase; color: #94A3B8; margin-bottom: .9rem;
    display: flex; align-items: center; gap: .45rem;
}
.iq-pnum {
    display: inline-flex; align-items: center; justify-content: center;
    width: 20px; height: 20px; background: #2563EB; color: #fff;
    font-size: .68rem; font-weight: 800; border-radius: 50%;
    flex-shrink: 0; box-shadow: 0 2px 6px rgba(37,99,235,.3);
}

/* ── Status badges ── */
.iq-status-ok {
    display: inline-flex; align-items: center; gap: .4rem;
    font-size: .82rem; font-weight: 600; color: #059669;
    background: rgba(5,150,105,.08); border: 1px solid rgba(5,150,105,.18);
    border-radius: 99px; padding: .3rem .85rem; margin-top: .6rem;
}
.iq-status-wait {
    display: inline-flex; align-items: center; gap: .4rem;
    font-size: .82rem; font-weight: 500; color: #94A3B8;
    background: rgba(148,163,184,.08); border: 1px solid rgba(148,163,184,.18);
    border-radius: 99px; padding: .3rem .85rem; margin-top: .6rem;
}
.iq-char { font-size: .77rem; color: #94A3B8; margin-top: -.3rem; display:flex; justify-content:space-between; }

/* ── Result list cards ── */
.iq-rc {
    display: flex; align-items: center; justify-content: space-between;
    padding: .85rem .95rem; border: 1px solid #E2E8F0; border-radius: 11px;
    margin-bottom: .5rem; background: #FAFBFC;
    transition: box-shadow .18s, border-color .18s;
}
.iq-rc:hover { box-shadow: 0 4px 14px rgba(10,20,60,.1); border-color: rgba(37,99,235,.2); }
.iq-rcl { display: flex; align-items: center; gap: .8rem; }
.iq-av {
    width: 38px; height: 38px; border-radius: 50%; flex-shrink: 0;
    background: linear-gradient(135deg,#DBEAFE,#EDE9FE);
    display: flex; align-items: center; justify-content: center;
    font-size: .85rem; font-weight: 800; color: #2563EB;
}
.iq-rn  { font-weight: 700; font-size: .88rem; color: #0B1120; }
.iq-rr  { font-size: .76rem; color: #64748B; margin-top: 1px; }
.iq-scr { text-align: right; flex-shrink: 0; }
.iq-sv  { font-size: 1.05rem; font-weight: 900; color: #2563EB; }
.iq-sd  { font-size: .78rem; color: #94A3B8; font-weight: 500; }
.iq-stars { font-size: .8rem; color: #F59E0B; line-height: 1.4; }

/* ── Detailed candidate card ── */
.iq-det { background: #FAFBFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 1.3rem; }
.iq-tag { display:inline-block; background:rgba(37,99,235,.07); color:#2563EB; border:1px solid rgba(37,99,235,.15); border-radius:6px; padding:3px 9px; font-size:.77rem; margin:2px; font-weight:500; }
.iq-tag-g { background:rgba(5,150,105,.07); color:#059669; border-color:rgba(5,150,105,.15); }
.iq-tag-m { background:rgba(100,116,139,.07); color:#64748B; border-color:rgba(100,116,139,.15); }
.iq-tag-r { background:rgba(220,38,38,.07); color:#DC2626; border-color:rgba(220,38,38,.15); }
.rec-highly      { background:#DCFCE7; color:#15803D; border-radius:7px; padding:4px 12px; font-size:.82rem; font-weight:600; display:inline-block; }
.rec-recommended { background:#DBEAFE; color:#1D4ED8; border-radius:7px; padding:4px 12px; font-size:.82rem; font-weight:600; display:inline-block; }
.rec-review      { background:#FEF3C7; color:#92400E; border-radius:7px; padding:4px 12px; font-size:.82rem; font-weight:600; display:inline-block; }
.rec-unsuitable  { background:#F3F4F6; color:#6B7280; border-radius:7px; padding:4px 12px; font-size:.82rem; font-weight:600; display:inline-block; }

/* ── View full results link ── */
.iq-view-link {
    display: flex; align-items: center; justify-content: center; gap: .35rem;
    font-size: .875rem; font-weight: 600; color: #2563EB;
    border-top: 1px solid #E2E8F0; padding-top: .85rem; margin-top: .4rem;
    cursor: pointer;
}
.iq-view-link:hover { text-decoration: underline; }

/* ── Testimonials ── */
.iq-ts-sec { background:#fff; border:1px solid #E2E8F0; border-radius:20px; padding:3rem 2.5rem; margin:3rem 0 2rem; }
.iq-ts-h   { font-size:1.85rem; font-weight:900; color:#0B1120; letter-spacing:-.5px; margin-bottom:.4rem; }
.iq-ts-s   { color:#64748B; font-size:.93rem; margin-bottom:2.2rem; }
.iq-tg     { display:grid; grid-template-columns:repeat(3,1fr); gap:1.3rem; }
.iq-tc     { background:#F7F9FC; border:1px solid #E2E8F0; border-radius:13px; padding:1.5rem; transition:box-shadow .2s; }
.iq-tc:hover { box-shadow:0 6px 22px rgba(10,20,60,.1); }
.iq-tq     { font-size:2rem; color:#2563EB; line-height:1; margin-bottom:.65rem; }
.iq-tt     { font-size:.875rem; color:#64748B; line-height:1.75; margin-bottom:1.1rem; }
.iq-tp     { display:flex; align-items:center; gap:.65rem; }
.iq-tav    { width:36px; height:36px; border-radius:50%; flex-shrink:0; background:linear-gradient(135deg,#DBEAFE,#EDE9FE); display:flex; align-items:center; justify-content:center; font-weight:700; color:#2563EB; font-size:.82rem; }
.iq-tpn    { font-weight:700; font-size:.83rem; color:#0B1120; }
.iq-tpc    { font-size:.77rem; color:#64748B; }

/* ── Footer CTA ── */
.iq-fcta { text-align:center; padding:3.5rem 1rem 3rem; border-top:1px solid #E2E8F0; }
.iq-fi   { font-size:2.4rem; margin-bottom:.9rem; }
.iq-fh   { font-size:2.3rem; font-weight:900; color:#0B1120; line-height:1.14; margin-bottom:.8rem; letter-spacing:-1px; }
.iq-fh b { color:#2563EB; font-weight:900; }
.iq-fs   { font-size:.98rem; color:#64748B; margin-bottom:2rem; max-width:420px; margin-left:auto; margin-right:auto; line-height:1.7; }
.iq-fck  { font-size:.82rem; color:#94A3B8; margin-top:.9rem; }

/* ── Responsive ── */
@media(max-width:900px) {
    .iq-h1 { font-size:2.8rem; letter-spacing:-1.8px; }
    .iq-tg { grid-template-columns:1fr; }
}
@media(max-width:640px) {
    [data-testid="block-container"] { padding:0 1rem 3rem!important; }
    .iq-hero { padding:2.8rem .5rem 2rem; }
    .iq-h1   { font-size:2.1rem; letter-spacing:-1.2px; }
    .iq-sub  { font-size:.93rem; }
    .iq-btns { flex-direction:column; align-items:stretch; max-width:260px; margin:0 auto; }
    .iq-bp, .iq-bs { text-align:center; }
    .iq-steps { flex-direction:column; align-items:center; gap:.4rem; padding:2rem 0; }
    .iq-arr   { transform:rotate(90deg); margin:0; }
    .iq-step  { width:100%; max-width:260px; }
    .iq-fh    { font-size:1.8rem; }
    .iq-ts-sec { padding:2rem 1.2rem; }
}

hr { border-color:#E2E8F0!important; margin:1.5rem 0!important; }
</style>"""

st.markdown(build_css(), unsafe_allow_html=True)

# ─────────────────────────── Session state ───────────────────────────────────
for _k, _v in [
    ("results",          []),
    ("processed",        False),
    ("uploaded_paths",   []),
    ("show_full",        False),
    ("brevo_api_key",    os.getenv("BREVO_API_KEY", "")),
    ("brevo_from_email", os.getenv("BREVO_FROM_EMAIL", "")),
]:
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ─────────────────────────── Helpers ─────────────────────────────────────────
def _fmt_score(score: int):
    s10  = round(score / 10, 1)
    lbl  = f"{s10:.1f}" if s10 % 1 else f"{int(s10)}.0"
    full = min(5, round(score / 20))
    return lbl, "★" * full + "☆" * (5 - full)


def _rec_badge(text: str) -> str:
    t = text.lower()
    if   "highly" in t:                                  css = "rec-highly"
    elif "not" in t and ("suit" in t or "recommend" in t): css = "rec-unsuitable"
    elif "review" in t or "manual" in t:                 css = "rec-review"
    elif "recommend" in t:                               css = "rec-recommended"
    else:
        return f'<span style="font-size:.9rem;color:#64748B">{text}</span>'
    return f'<span class="{css}">{text}</span>'


def _read_cv(path: str, fname: str) -> str:
    ext = Path(fname).suffix.lower()
    if ext == ".pdf":   return extract_pdf_text(path)
    if ext == ".docx":  return extract_docx_text(path)
    if ext == ".txt":
        try:    return Path(path).read_text(encoding="utf-8", errors="ignore")
        except: return ""
    return ""


def _extract_from_upload(f) -> str:
    """Extract text from a Streamlit UploadedFile object."""
    suffix = Path(f.name).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(f.read())
        path = tmp.name
    try:
        return _read_cv(path, f.name)
    finally:
        Path(path).unlink(missing_ok=True)


# ─────────────────────────── Navbar ──────────────────────────────────────────
# No login button, no night mode — clean product nav
st.markdown("""
<div class="iq-nav">
  <div class="iq-logo">Talent<b>IQ</b></div>
  <button class="iq-nav-demo">Book a Demo</button>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────── Hero ────────────────────────────────────────────
# All "headings" use <div> — Streamlit adds anchor icons to actual h1/h2/h3 tags
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
  <div class="iq-arr">&nbsp;- - -&nbsp;&rarr;</div>
  <div class="iq-step">
    <div class="iq-snum">2</div>
    <div class="iq-st">Upload CVs</div>
    <div class="iq-ss">Upload any CV format. No friction.</div>
  </div>
  <div class="iq-arr">&nbsp;- - -&nbsp;&rarr;</div>
  <div class="iq-step">
    <div class="iq-snum">3</div>
    <div class="iq-st">Get Ranked Results</div>
    <div class="iq-ss">AI ranks and scores the best matches</div>
  </div>
</div>
<div class="iq-div"></div>
""", unsafe_allow_html=True)


# ─────────────────────────── 3-panel layout ──────────────────────────────────
col1, col2, col3 = st.columns([1, 1, 1.15], gap="large")

# ══════════════════════════ PANEL 1 — Job Description ═════════════════════════
with col1:
    with st.container(border=True):
        st.markdown("""
<div class="iq-phead">
  <div class="iq-pnum">1</div>Job Description
</div>""", unsafe_allow_html=True)

        tab_paste, tab_file = st.tabs(["Paste Text", "Upload File"])

        jd_text = ""

        with tab_paste:
            jd_input = st.text_area(
                "",
                placeholder=(
                    "We are looking for a Senior SAP SuccessFactors Consultant "
                    "with strong experience in Employee Central, Core HR, reporting "
                    "and end-to-end implementation projects…"
                ),
                height=270,
                max_chars=5000,
                key="jd_paste",
                label_visibility="collapsed",
            )
            char_count = len(jd_input)
            st.markdown(
                f'<div class="iq-char">'
                f'<span>{char_count:,} / 5,000</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if jd_input.strip():
                jd_text = jd_input.strip()

        with tab_file:
            jd_file = st.file_uploader(
                "Upload your JD",
                type=["pdf", "docx", "txt"],
                key="jd_file_up",
                label_visibility="collapsed",
            )
            if jd_file:
                extracted = _extract_from_upload(jd_file)
                if extracted.strip():
                    jd_text = extracted.strip()
                    st.caption(f"✅ Extracted {len(jd_text):,} characters from {jd_file.name}")

        # Status badge
        if jd_text:
            st.markdown('<div class="iq-status-ok">✅ Job description added</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="iq-status-wait">⏳ Waiting for job description…</div>', unsafe_allow_html=True)


# ══════════════════════════ PANEL 2 — Upload CVs ══════════════════════════════
with col2:
    with st.container(border=True):
        st.markdown("""
<div class="iq-phead">
  <div class="iq-pnum">2</div>Upload CVs
</div>""", unsafe_allow_html=True)

        cv_files = st.file_uploader(
            "PDF, DOCX, TXT — Any format supported",
            type=["pdf", "docx", "txt"],
            accept_multiple_files=True,
            key="cv_up",
            label_visibility="visible",
        )
        total_uploaded = len(cv_files or [])

        # Status badge
        if total_uploaded > 0:
            st.markdown(
                f'<div class="iq-status-ok">✅ {total_uploaded} CV{"s" if total_uploaded != 1 else ""} uploaded</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown('<div class="iq-status-wait">⏳ No CVs uploaded yet…</div>', unsafe_allow_html=True)

        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

        # Optional email settings
        with st.expander("⚙️  Email settings (optional)"):
            send_emails    = st.checkbox("Auto-email top 10 candidates", value=True)
            recruiter_name = st.text_input("Recruiter / company name", value="Recruitment Team")
            st.text_input("Your email (Brevo sender)", key="brevo_from_email", placeholder="you@gmail.com")
            st.text_input("Brevo API Key", key="brevo_api_key", type="password", placeholder="xkeysib-…")
            _from = (st.session_state.get("brevo_from_email") or "").strip()
            with st.expander("📋 Brevo setup guide"):
                st.markdown(f"""
**1.** Create free account → [app.brevo.com](https://app.brevo.com) · 300 emails/day
**2.** Verify sender: Brevo → Senders & IP → Senders → Add a Sender → enter `{_from or "your email"}` → verify via email
**3.** API key: Brevo → top menu → SMTP & API → API Keys → Generate
""")
            _e1, _e2 = st.columns(2)
            with _e1:
                if st.button("🔑 Verify Key", use_container_width=True):
                    _ok, _msg = test_brevo_key(st.session_state.get("brevo_api_key",""))
                    (st.success if _ok else st.error)(f"{'✅' if _ok else '❌'} {_msg}")
            with _e2:
                if st.button("📧 Test Email", use_container_width=True):
                    _ok, _msg = send_test_email(st.session_state.get("brevo_api_key",""), st.session_state.get("brevo_from_email",""))
                    (st.success if _ok else st.error)(f"{'✅' if _ok else '❌'} {_msg}")

        st.markdown("<div style='height:.3rem'></div>", unsafe_allow_html=True)
        run_btn = st.button("🚀  Screen Candidates", use_container_width=True)


# ══════════════════════════ PANEL 3 — Results ═════════════════════════════════
with col3:
    with st.container(border=True):
        st.markdown("""
<div class="iq-phead">
  <div class="iq-pnum">3</div>Top Candidates
</div>""", unsafe_allow_html=True)

        # ── Trigger screening ────────────────────────────────────────────────
        if run_btn:
            errors = []
            if not jd_text:
                errors.append("Please add a Job Description (paste text or upload a file).")
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

                # Infer job title from first non-empty line of JD
                first_line = next(
                    (ln.strip() for ln in jd_text.splitlines() if ln.strip()), ""
                )[:80]
                job_context = {
                    "title":            first_line,
                    "skills":           "",
                    "years_experience": 0,
                    "description":      jd_text,
                }

                candidates = []
                bar   = st.progress(0, text="Reading CVs…")
                _info = st.empty()

                for idx, (path, fname) in enumerate(zip(saved_paths, saved_names), 1):
                    _info.markdown(
                        f'<p style="font-size:.82rem;color:#64748B">'
                        f'📄 <b style="color:#2563EB">{fname}</b> ({idx}/{len(saved_paths)})</p>',
                        unsafe_allow_html=True,
                    )
                    try:
                        text = _read_cv(path, fname)
                        if not text.strip():
                            st.warning(f"⚠️ No text in {fname} — skipping.")
                            continue
                        candidates.append(extract_resume_keywords(cv_text=text, required_skills=""))
                    except Exception as ex:
                        st.warning(f"⚠️ Error reading {fname}: {ex}")
                    bar.progress(idx / len(saved_paths) * 0.5,
                                 text=f"Reading CVs — {idx}/{len(saved_paths)} done…")

                if candidates:
                    _info.markdown(
                        f'<p style="font-size:.82rem;color:#64748B">'
                        f'🤖 Ranking <b style="color:#2563EB">{len(candidates)} candidates</b>…</p>',
                        unsafe_allow_html=True,
                    )
                    bar.progress(0.55, text=f"AI ranking {len(candidates)} candidates…")
                    try:
                        results = rank_candidates_batch(candidates=candidates, job_context=job_context)
                    except RuntimeError as _err:
                        bar.empty(); _info.empty()
                        _em = str(_err)
                        if "api" in _em.lower() and "key" in _em.lower():
                            st.error("❌ OpenAI API key missing.\n\nFix: Streamlit Cloud → Settings → Secrets → add `OPENAI_API_KEY = \"sk-proj-...\"`")
                        else:
                            st.error(f"❌ AI ranking failed: {_em}")
                        st.session_state.processed = False
                        st.stop()
                else:
                    results = []

                bar.progress(1.0, text="✅ Done!"); _info.empty()
                st.session_state.results   = results
                st.session_state.processed = True
                st.session_state.show_full = False

                if send_emails and results:
                    with st.spinner("Sending shortlist emails…"):
                        report = send_shortlist_emails(
                            candidates=results[:10],
                            job_title=first_line,
                            recruiter_name=recruiter_name,
                            brevo_api_key=st.session_state.get("brevo_api_key",""),
                            from_email=st.session_state.get("brevo_from_email",""),
                        )
                    if report["sent"]:
                        st.success(f"📧 Emails sent to {len(report['sent'])} candidates.")
                    if report["failed"]:
                        st.warning(f"⚠️ Failed: {', '.join(report['failed'])}")

                deleted, _ = delete_uploaded_files(saved_paths)
                if deleted:
                    st.caption(f"🗑️ {len(deleted)} file(s) deleted from server.")

        # ── Show results ─────────────────────────────────────────────────────
        if st.session_state.processed and st.session_state.results:
            results = st.session_state.results

            for rank, r in enumerate(results[:5], 1):
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
      <div class="iq-rn">{name}</div>
      <div class="iq-rr">{email}</div>
    </div>
  </div>
  <div class="iq-scr">
    <div><span class="iq-sv">{s_lbl}</span><span class="iq-sd">/10</span></div>
    <div class="iq-stars">{s_stars}</div>
  </div>
</div>""", unsafe_allow_html=True)

            if len(results) > 5:
                if st.button("View Full Results →", use_container_width=True, key="view_full_btn"):
                    st.session_state.show_full = True

        elif st.session_state.processed and not st.session_state.results:
            st.error("❌ No candidates processed. Check your CV files.")

        else:
            # Idle state — mirroring what a results panel looks like
            st.markdown("""
<div style="text-align:center;padding:2.5rem 1rem 1rem">
  <div style="font-size:2.5rem;margin-bottom:.8rem">📊</div>
  <div style="font-size:.95rem;font-weight:600;color:#0B1120;margin-bottom:.4rem">
    Ranked results appear here
  </div>
  <div style="font-size:.82rem;color:#94A3B8;line-height:1.65">
    Add a job description, upload CVs,<br>
    then click <b style="color:#2563EB">Screen Candidates</b>
  </div>
</div>
<div style="margin:1rem 0;border-top:1px dashed #E2E8F0;padding-top:1rem">
  <div style="display:flex;align-items:center;justify-content:space-between;padding:.7rem .9rem;border:1px dashed #E2E8F0;border-radius:10px;margin-bottom:.45rem;opacity:.4">
    <div style="display:flex;align-items:center;gap:.7rem">
      <div style="width:36px;height:36px;border-radius:50%;background:#DBEAFE"></div>
      <div><div style="width:90px;height:9px;background:#E2E8F0;border-radius:4px;margin-bottom:5px"></div><div style="width:60px;height:7px;background:#EEF2FF;border-radius:4px"></div></div>
    </div>
    <div style="width:40px;height:18px;background:#DBEAFE;border-radius:6px"></div>
  </div>
  <div style="display:flex;align-items:center;justify-content:space-between;padding:.7rem .9rem;border:1px dashed #E2E8F0;border-radius:10px;margin-bottom:.45rem;opacity:.25">
    <div style="display:flex;align-items:center;gap:.7rem">
      <div style="width:36px;height:36px;border-radius:50%;background:#EDE9FE"></div>
      <div><div style="width:75px;height:9px;background:#E2E8F0;border-radius:4px;margin-bottom:5px"></div><div style="width:50px;height:7px;background:#EEF2FF;border-radius:4px"></div></div>
    </div>
    <div style="width:40px;height:18px;background:#EDE9FE;border-radius:6px"></div>
  </div>
  <div style="display:flex;align-items:center;justify-content:space-between;padding:.7rem .9rem;border:1px dashed #E2E8F0;border-radius:10px;opacity:.15">
    <div style="display:flex;align-items:center;gap:.7rem">
      <div style="width:36px;height:36px;border-radius:50%;background:#FCE7F3"></div>
      <div><div style="width:85px;height:9px;background:#E2E8F0;border-radius:4px;margin-bottom:5px"></div><div style="width:55px;height:7px;background:#EEF2FF;border-radius:4px"></div></div>
    </div>
    <div style="width:40px;height:18px;background:#FCE7F3;border-radius:6px"></div>
  </div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────── Full results (below panels) ─────────────────────
if st.session_state.get("show_full") and st.session_state.results:
    results = st.session_state.results
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Screened", len(results))
    m2.metric("Shortlisted",    min(10, len(results)))
    avg = sum(r.get("match_score", 0) for r in results) / len(results)
    m3.metric("Avg Score", f"{round(avg / 10, 1)}/10")

    st.markdown(
        '<div style="font-size:.7rem;font-weight:700;letter-spacing:.1em;'
        'text-transform:uppercase;color:#94A3B8;margin:1.2rem 0 .8rem">'
        '📋 All Candidate Profiles</div>',
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

        with st.expander(f"#{rank} — {name}  ·  {s_lbl}/10  {s_stars}", expanded=(rank == 1)):
            st.markdown(f"""
<div class="iq-det">
  <div style="font-weight:700;font-size:.98rem;color:#0B1120">{name}</div>
  <div style="font-size:.81rem;color:#64748B;margin-bottom:.85rem">{email}</div>
  <span style="font-size:1.85rem;font-weight:900;color:#2563EB">{s_lbl}</span>
  <span style="font-size:.93rem;color:#64748B">/10 &nbsp;{s_stars}</span>
  <hr style="margin:.7rem 0">
  <div style="font-size:.7rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#94A3B8;margin-bottom:5px">Strengths</div>
  {str_html or '<span style="color:#94A3B8;font-size:.85rem">None noted</span>'}
  <div style="font-size:.7rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#94A3B8;margin:.75rem 0 5px">Concerns</div>
  {con_html or '<span style="color:#94A3B8;font-size:.85rem">None noted</span>'}
  <div style="font-size:.7rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#94A3B8;margin:.75rem 0 5px">Recommendation</div>
  {_rec_badge(rec)}
</div>""", unsafe_allow_html=True)

    st.markdown("---")
    df = pd.DataFrame([
        {
            "Rank":           i + 1,
            "Candidate":      r.get("candidate_name", ""),
            "Score":          f"{_fmt_score(r.get('match_score',0))[0]}/10",
            "Email":          r.get("email", ""),
            "Recommendation": r.get("recommendation", ""),
        }
        for i, r in enumerate(results)
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)

    csv = pd.DataFrame([
        {
            "Rank":           i + 1,
            "Name":           r.get("candidate_name", ""),
            "Email":          r.get("email", ""),
            "Score":          f"{_fmt_score(r.get('match_score',0))[0]}/10",
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
      <div class="iq-tp"><div class="iq-tav">MR</div><div><div class="iq-tpn">Mark Richardson</div><div class="iq-tpc">Managing Director &middot; Hays Specialist Recruitment</div></div></div>
    </div>
    <div class="iq-tc">
      <div class="iq-tq">&ldquo;</div>
      <div class="iq-tt">What used to take hours now takes minutes. TalentIQ helps us focus on what really matters — speaking to candidates and closing placements.</div>
      <div class="iq-tp"><div class="iq-tav">SB</div><div><div class="iq-tpn">Sophie Bennett</div><div class="iq-tpc">Senior Consultant &middot; Michael Page</div></div></div>
    </div>
    <div class="iq-tc">
      <div class="iq-tq">&ldquo;</div>
      <div class="iq-tt">The AI matching accuracy is incredible. We never miss great candidates anymore. TalentIQ is a game changer for our business.</div>
      <div class="iq-tp"><div class="iq-tav">DT</div><div><div class="iq-tpn">Daniel Thompson</div><div class="iq-tpc">Director &middot; Robert Half</div></div></div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────── Footer CTA ──────────────────────────────────────
st.markdown("""
<div class="iq-fcta">
  <div class="iq-fi">👥</div>
  <div class="iq-fh">Stop Reading CVs.<br><b>Start Making Placements.</b></div>
  <div class="iq-fs">Book a 15-minute demo and see how TalentIQ can save your team hours every single day.</div>
  <button style="background:#2563EB;color:#fff;font-weight:700;font-size:1rem;border:none;
    border-radius:10px;padding:.8rem 2.2rem;cursor:pointer;
    box-shadow:0 4px 16px rgba(37,99,235,.38);">
    Book a 15-Minute Demo &nbsp;&rarr;
  </button>
  <div class="iq-fck">&#10003; No credit card required &nbsp;&nbsp;&#10003; Cancel anytime</div>
</div>
<hr>
<div style="text-align:center;color:#94A3B8;font-size:.78rem;padding-bottom:1.5rem">
  TalentIQ &middot; AI CV Screening &middot; Built with Streamlit &amp; GPT-4o
</div>
""", unsafe_allow_html=True)
