"""
RankCV — AI-Powered CV Screening
"""

import datetime
import html
import json
import logging
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Imported after load_dotenv() so .env values are visible to utils.config
from utils import config  # noqa: E402
from utils.pdf_parser import extract_pdf_text_with_flags  # noqa: E402
from utils.docx_parser import extract_docx_text_with_flags  # noqa: E402
from utils.ai_scoring import extract_resume_keywords, rank_candidates_batch, extract_job_context  # noqa: E402
from utils.cleanup import screening_workspace, safe_upload_path, purge_stale_workspaces  # noqa: E402
from utils.account_tracker import (  # noqa: E402
    init_db,
    get_account,
    create_session,
    account_for_session,
    delete_session,
    normalize_email,
    refresh_entitlements,
    request_login_code,
    verify_login_code,
    reserve_quota,
    release_quota,
)
from utils.mailer import send_login_code, email_configured  # noqa: E402
from utils.legal import PAGES as LEGAL_PAGES, render_page as render_legal_page  # noqa: E402
from utils.report import (  # noqa: E402
    BAND_LABELS, MODE_LABELS as _MODE_LABELS, build_excel_report, fit_band as _fit_band, score as _score,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("rankcv")


st.set_page_config(
    page_title="RankCV — Screen CVs in Minutes",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def render_html(html_str: str, container=None):
    """Renders trusted layout HTML. Every dynamic value inside it must go through _e()."""
    clean = "\n".join(ln.strip() for ln in html_str.splitlines() if ln.strip())
    target = container if container is not None else st
    target.markdown(clean, unsafe_allow_html=True)


def _e(value) -> str:
    """HTML-escape any value before it goes into unsafe_allow_html markup."""
    return html.escape("" if value is None else str(value), quote=True)


# ─────────────────────────── CSS (light mode only) ────────────────────────────
def build_css() -> str:
    return """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

/* ── Base ── */
*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    -webkit-font-smoothing: antialiased;
    overflow-x: hidden !important;
    max-width: 100vw !important;
}
[data-testid="stAppViewContainer"] {
    background: #F5F7FB !important;
    overflow-x: hidden !important;
}
/* ── ELIMINATE ALL STREAMLIT BRANDING, MENUS, FOOTERS & ARTIFACTS ── */
#MainMenu,
header,
footer,
[data-testid="stHeader"],
header[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
[data-testid="stBottom"],
.viewerBadge_container,
[class*="viewerBadge"],
[class*="StatusWidget"],
[class*="ProfileButton"],
.stDeployButton,
div[data-testid="stToolbarActions"],
button[title*="Streamlit"],
a[href*="streamlit.io"],
a[href*="streamlit.app"] {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    min-height: 0 !important;
    max-height: 0 !important;
    width: 0 !important;
    opacity: 0 !important;
    pointer-events: none !important;
    margin: 0 !important;
    padding: 0 !important;
    border: none !important;
}
[data-testid="block-container"] {
    background: #F5F7FB;
    padding: 0 2rem 4rem !important;
    max-width: 1280px;
}
/* Kill Streamlit's default top padding on the main content area */
.main > div:first-child { padding-top: 0 !important; }
section[data-testid="stMain"] > div { padding-top: 0 !important; }
.stMainBlockContainer { padding-top: 0 !important; }

/* Kill Streamlit anchor-link icons injected into h-tags */
[data-testid="stMarkdownContainer"] [data-testid="stHeaderActionElements"] { display:none!important; }

[data-testid="stMetricValue"]  { color:#0B1120!important; font-weight:800!important; font-size:1.55rem!important; }
[data-testid="stMetricLabel"]  { color:#64748B!important; font-size:.8rem!important; }

/* ── Workspace Panel Cards (Equal Size, Equal Height) ── */
div[data-testid="stHorizontalBlock"]:has(.iq-phead) {
    display: flex !important;
    align-items: stretch !important;
}
div[data-testid="column"]:has(.iq-phead),
.stColumn:has(.iq-phead) {
    display: flex !important;
    flex-direction: column !important;
    align-self: stretch !important;
    flex: 1 1 0 !important;
    height: 100% !important;
}
/* Intermediate wrappers inside workspace column */
div[data-testid="column"]:has(.iq-phead) > div,
div[data-testid="column"]:has(.iq-phead) [data-testid="stVerticalBlock"] {
    display: flex !important;
    flex-direction: column !important;
    flex: 1 1 auto !important;
    height: 100% !important;
}
/* The card container border wrapper */
div[data-testid="column"]:has(.iq-phead) [data-testid="stVerticalBlockBorderWrapper"],
div[data-testid="stVerticalBlockBorderWrapper"]:has(.iq-phead) {
    display: flex !important;
    flex-direction: column !important;
    flex: 1 1 100% !important;
    height: 100% !important;
    min-height: 605px !important;
    justify-content: space-between !important;
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 16px !important;
    box-shadow: 0 2px 12px rgba(10,20,60,.06) !important;
    padding: 1.5rem !important;
    box-sizing: border-box !important;
    transition: box-shadow .2s, border-color .2s !important;
}
div[data-testid="column"]:has(.iq-phead) [data-testid="stVerticalBlockBorderWrapper"]:focus-within,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.iq-phead):focus-within {
    box-shadow: 0 4px 20px rgba(10,20,60,.1) !important;
    border-color: rgba(37,99,235,.25) !important;
}
/* Inside the card border wrapper, make the inner vertical block take 100% height and space-between */
div[data-testid="column"]:has(.iq-phead) [data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlock"] {
    display: flex !important;
    flex-direction: column !important;
    flex: 1 1 100% !important;
    height: 100% !important;
    justify-content: space-between !important;
}
/* Ensure regular non-workspace columns have zero extra height or styling */
div[data-testid="column"]:not(:has(.iq-phead)) {
    min-height: unset !important;
}
div[data-testid="column"]:not(:has(.iq-phead)) > div[data-testid="stVerticalBlockBorderWrapper"] {
    min-height: unset !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
}

/* ── Tabs ── */
[data-testid="stTabsTabList"] {
    border-bottom: 1.5px solid #E2E8F0 !important;
    gap: .4rem !important;
    margin-bottom: .8rem !important;
    justify-content: center !important;
}
button[data-testid="stTab"] {
    font-size: .88rem !important;
    font-weight: 600 !important;
    color: #64748B !important;
    padding: .55rem 1.25rem !important;
    border-radius: 8px 8px 0 0 !important;
    border-bottom: 2.5px solid transparent !important;
    transition: color .15s, border-color .15s !important;
}
button[data-testid="stTab"][aria-selected="true"] {
    color: #2563EB !important;
    border-bottom: 2.5px solid #2563EB !important;
    font-weight: 700 !important;
    background: transparent !important;
}
button[data-testid="stTab"]:hover { color: #1D4ED8 !important; }

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
/* Hide Streamlit's confusing Cmd+Enter instruction and duplicate counter */
div[data-testid="InputInstructions"] { display: none !important; }
label, .stFileUploader label {
    color: #4B5563 !important;
    font-size: .875rem !important;
    font-weight: 500 !important;
}

/* ── Buttons ── */
.stButton > button {
    border-radius: 10px !important; font-weight: 700 !important;
    font-size: .95rem !important; padding: .75rem 1.4rem !important;
    transition: all .18s !important; letter-spacing: -.01em !important;
}
.stButton > button,
.stButton > button[kind="primary"],
button[data-testid="baseButton-primary"] {
    background: linear-gradient(135deg,#2563EB,#3B82F6) !important;
    color: #fff !important; border: none !important;
    box-shadow: 0 4px 14px rgba(37,99,235,.35) !important;
}
.stButton > button:hover,
.stButton > button[kind="primary"]:hover,
button[data-testid="baseButton-primary"]:hover {
    background: linear-gradient(135deg,#1D4ED8,#2563EB) !important;
    box-shadow: 0 6px 20px rgba(37,99,235,.45) !important;
    transform: translateY(-1px) !important; opacity:1!important;
}
.stButton > button[kind="secondary"],
button[data-testid="baseButton-secondary"] {
    background: #FFFFFF !important;
    color: #2563EB !important;
    border: 1.5px solid #DBEAFE !important;
    box-shadow: 0 2px 6px rgba(37,99,235,.06) !important;
}
.stButton > button[kind="secondary"]:hover,
button[data-testid="baseButton-secondary"]:hover {
    background: #EFF6FF !important;
    border-color: #2563EB !important;
    color: #1D4ED8 !important;
    transform: translateY(-1px) !important;
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
    min-height: 290px !important;
    display: flex !important;
    flex-direction: column !important;
    justify-content: center !important;
    align-items: center !important;
    padding: 2rem 1.2rem !important;
    transition: border-color .2s, background .2s !important;
    text-align: center !important;
}
[data-testid="stFileUploaderDropzone"]:hover {
    border-color: #2563EB !important;
    background: rgba(37,99,235,.03) !important;
}
.stDataFrame { border-radius: 12px; overflow: hidden; border: 1px solid #E2E8F0 !important; }
.stExpander {
    border: 1.5px solid #E2E8F0 !important;
    border-radius: 14px !important;
    background: #fff !important;
    overflow: hidden !important;
    box-shadow: 0 2px 8px rgba(10,20,60,.06) !important;
    margin-bottom: .6rem !important;
    transition: box-shadow .2s, border-color .2s !important;
}
.stExpander:hover {
    box-shadow: 0 4px 18px rgba(37,99,235,.11) !important;
    border-color: #BFDBFE !important;
}
.stExpander summary {
    font-size: 1rem !important;
    font-weight: 700 !important;
    color: #0B1120 !important;
    padding: 1.05rem 1.4rem !important;
    background: linear-gradient(to right, #EFF6FF, #FAFBFF) !important;
    border-bottom: 1px solid transparent !important;
    letter-spacing: -.01em !important;
    transition: background .15s !important;
}
.stExpander:hover summary { background: linear-gradient(to right,#DBEAFE,#EFF6FF) !important; }
.stExpander details[open] > summary {
    border-bottom-color: #DBEAFE !important;
    background: linear-gradient(to right, #EBF2FF, #F0F6FF) !important;
}
/* ── Search / filter bar ── */
.iq-filter-bar {
    display:flex; align-items:center; gap:.75rem;
    background:#F8FAFF; border:1.5px solid #E2E8F0;
    border-radius:12px; padding:.65rem 1rem; margin-bottom:1rem;
}
.iq-filter-bar .iq-fi { font-size:.85rem; color:#94A3B8; flex-shrink:0; }
/* ── Download button (pure HTML anchor) ── */
.iq-dl-btn {
    display: block; width: 100%; text-align: center; box-sizing: border-box;
    background: linear-gradient(135deg, #1E40AF, #2563EB);
    color: #fff !important; text-decoration: none !important;
    border-radius: 12px; padding: 1rem 1.5rem;
    font-size: .97rem; font-weight: 700; letter-spacing: -.01em;
    box-shadow: 0 4px 18px rgba(37,99,235,.28);
    transition: transform .15s, box-shadow .15s;
    cursor: pointer;
}
.iq-dl-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 26px rgba(37,99,235,.4);
    background: linear-gradient(135deg, #1D4ED8, #3B82F6);
    color: #fff !important; text-decoration: none !important;
}
.iq-dl-btn:active { transform: translateY(0); }
.iq-dl-wrap { margin-top: 1.5rem; margin-bottom: .5rem; }
/* ── Results section heading ── */
.iq-results-hdr {
    display:flex; align-items:center; justify-content:space-between;
    margin:1.2rem 0 .8rem;
}
.iq-results-hdr-title {
    font-size:.7rem; font-weight:700; letter-spacing:.12em;
    text-transform:uppercase; color:#94A3B8;
}
.iq-results-count {
    font-size:.75rem; font-weight:600; color:#2563EB;
    background:#EFF6FF; border:1px solid #DBEAFE;
    border-radius:20px; padding:2px 10px;
}

/* ── Navbar ── */
.iq-nav {
    display: flex; align-items: center; justify-content: space-between;
    padding: 1.1rem 0 1rem; border-bottom: 1px solid #E2E8F0;
    margin-bottom: 0; background: #F5F7FB;
}
.iq-logo { font-size: 1.55rem; font-weight: 900; color: #0F172A; letter-spacing: -.5px; flex-shrink: 0; }
.iq-logo b { color: #2563EB; font-weight: 900; }
.iq-nav-center {
    display: flex; align-items: center; justify-content: center;
    gap: 2rem;
}
.iq-nav-link {
    font-size: .92rem; font-weight: 600; color: #64748B;
    text-decoration: none !important; transition: color .15s ease;
}
.iq-nav-link:hover { color: #2563EB !important; }
@media (max-width: 860px) {
    .iq-nav-center { display: none; }
}
.iq-nav a.iq-nav-demo,
.iq-nav a.iq-nav-demo:link,
.iq-nav a.iq-nav-demo:visited,
.iq-nav a.iq-nav-demo:hover,
.iq-nav a.iq-nav-demo:focus,
.iq-nav a.iq-nav-demo:active,
a.iq-nav-demo,
a.iq-nav-demo:link,
a.iq-nav-demo:visited,
a.iq-nav-demo:hover,
a.iq-nav-demo:focus,
a.iq-nav-demo:active,
.iq-nav-demo {
    font-size: .92rem !important; font-weight: 700 !important; color: #FFFFFF !important; background: #2563EB !important;
    padding: .55rem 1.4rem !important; border-radius: 9px !important; border: none !important; cursor: pointer !important;
    box-shadow: 0 2px 10px rgba(37,99,235,.25) !important; transition: all .15s ease !important;
    text-decoration: none !important; display: inline-flex !important; align-items: center !important;
    flex-shrink: 0;
}
.iq-nav a.iq-nav-demo:hover,
.iq-nav a.iq-nav-demo:active,
a.iq-nav-demo:hover,
a.iq-nav-demo:active {
    color: #FFFFFF !important; background: #1D4ED8 !important; text-decoration: none !important;
}

/* ── Hero — use <div> not h-tags to avoid Streamlit anchor icons ── */
.iq-hero { text-align: center; padding: 2.6rem 1rem 1.6rem; max-width: 860px; margin: 0 auto; }
.iq-eye {
    display: inline-block; font-size: .72rem; font-weight: 700;
    letter-spacing: .14em; color: #2563EB; text-transform: uppercase;
    background: rgba(37,99,235,.07); padding: .32rem 1rem;
    border-radius: 99px; border: 1px solid rgba(37,99,235,.15); margin-bottom: .75rem;
}
.iq-h1 {
    font-size: 2.75rem; font-weight: 900; line-height: 1.15;
    color: #0B1120; margin-bottom: .55rem; letter-spacing: -.025em;
}
.iq-h1 .bl { color: #2563EB; }
.iq-sub {
    font-size: 1.05rem; color: #64748B; max-width: 650px;
    margin: 0 auto .85rem; line-height: 1.55;
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
.iq-det {
    background:#fff; border:1px solid #E2E8F0;
    border-left:4px solid #2563EB;
    border-radius:14px; padding:1.55rem 1.7rem;
}
.iq-det-hrow {
    display:flex; align-items:center;
    justify-content:space-between; gap:1rem; margin-bottom:.95rem;
}
.iq-det-hinfo { flex:1; min-width:0; }
.iq-det-name  { font-weight:800; font-size:1.12rem; color:#0B1120; margin-bottom:.18rem; }
.iq-det-email { font-size:.82rem; color:#94A3B8; }
.iq-det-badge {
    flex-shrink:0; width:78px; height:78px; border-radius:50%;
    display:flex; flex-direction:column; align-items:center; justify-content:center;
    gap:.05rem;
}
.iq-det-badge-hi  { background:linear-gradient(135deg,#D1FAE5,#A7F3D0); }
.iq-det-badge-mid { background:linear-gradient(135deg,#FEF3C7,#FDE68A); }
.iq-det-badge-lo  { background:linear-gradient(135deg,#FEE2E2,#FECACA); }
.iq-det-badgenum  { font-size:1.45rem; font-weight:900; line-height:1.1; letter-spacing:-1px; color:#0B1120; }
.iq-det-badge-hi  .iq-det-badgenum  { color:#065F46; }
.iq-det-badge-mid .iq-det-badgenum  { color:#92400E; }
.iq-det-badge-lo  .iq-det-badgenum  { color:#991B1B; }
.iq-det-badgedenom { font-size:.65rem; color:#64748B; font-weight:600; }
.iq-det-badgestars { font-size:.7rem; color:#F59E0B; line-height:1.4; }
.iq-det-divider { height:1px; background:#F1F5F9; margin:.85rem 0 .95rem; }
.iq-det-lbl {
    font-size:.66rem; font-weight:700; letter-spacing:.13em;
    text-transform:uppercase; color:#94A3B8; margin-bottom:.5rem;
}
.iq-det-cols { display:grid; grid-template-columns:1fr 1fr; gap:1.4rem; margin-bottom:.2rem; }
.iq-det-tags { display:flex; flex-wrap:wrap; gap:.38rem; }
.iq-tag { display:inline-flex; align-items:center; gap:.28rem; background:rgba(37,99,235,.06); color:#2563EB; border:1px solid rgba(37,99,235,.14); border-radius:6px; padding:4px 10px; font-size:.77rem; font-weight:600; }
.iq-tag-g { background:rgba(5,150,105,.07); color:#059669; border-color:rgba(5,150,105,.15); }
.iq-tag-m { background:rgba(100,116,139,.07); color:#64748B; border-color:rgba(100,116,139,.15); }
.iq-tag-r { background:rgba(220,38,38,.06); color:#DC2626; border-color:rgba(220,38,38,.12); }
.rec-highly      { background:#DCFCE7; color:#15803D; border-radius:9px; padding:7px 16px; font-size:.88rem; font-weight:700; display:inline-block; border:1px solid rgba(5,150,105,.15); }
.rec-recommended { background:#DBEAFE; color:#1D4ED8; border-radius:9px; padding:7px 16px; font-size:.88rem; font-weight:700; display:inline-block; border:1px solid rgba(37,99,235,.15); }
.rec-review      { background:#FEF3C7; color:#92400E; border-radius:9px; padding:7px 16px; font-size:.88rem; font-weight:700; display:inline-block; border:1px solid rgba(245,158,11,.2); }
.rec-unsuitable  { background:#F3F4F6; color:#6B7280; border-radius:9px; padding:7px 16px; font-size:.88rem; font-weight:700; display:inline-block; border:1px solid #E2E8F0; }

/* ── View full results link ── */
.iq-view-link {
    display: flex; align-items: center; justify-content: center; gap: .35rem;
    font-size: .875rem; font-weight: 600; color: #2563EB;
    border-top: 1px solid #E2E8F0; padding-top: .85rem; margin-top: .4rem;
    cursor: pointer;
}
.iq-view-link:hover { text-decoration: underline; }

/* ── Testimonials & Early Beta Feedback (Scrolling Marquee) ── */
.iq-ts-sec {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 20px;
    padding: 3rem 0 2.5rem;
    margin: 3.5rem 0 2rem;
    overflow: hidden;
    position: relative;
}
.iq-ts-h { font-size: 1.65rem; font-weight: 900; color: #0B1120; letter-spacing: -.5px; margin-bottom: .35rem; }
.iq-ts-s { color: #64748B; font-size: .9rem; margin-bottom: 2rem; }
.iq-ts-track-wrap {
    width: 100%;
    overflow: hidden;
    position: relative;
    padding: .5rem 0;
    mask-image: linear-gradient(to right, transparent, black 4%, black 96%, transparent);
    -webkit-mask-image: linear-gradient(to right, transparent, black 4%, black 96%, transparent);
}
.iq-ts-track {
    display: flex;
    gap: 1.25rem;
    width: max-content;
    animation: iq-marquee 36s linear infinite;
}
.iq-ts-track:hover {
    animation-play-state: paused;
}
@keyframes iq-marquee {
    0% { transform: translateX(0); }
    100% { transform: translateX(-50%); }
}
.iq-beta-card {
    width: 335px;
    flex-shrink: 0;
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 14px;
    padding: 1.35rem 1.35rem;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    box-shadow: 0 4px 12px rgba(15,23,42,.03);
    transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
    user-select: none;
}
.iq-beta-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(37,99,235,.07);
    border-color: #CBD5E1;
}
.iq-beta-stars {
    color: #F59E0B;
    font-size: .84rem;
    margin-bottom: .5rem;
    letter-spacing: 2px;
}
.iq-beta-text {
    font-size: .865rem;
    color: #334155;
    line-height: 1.6;
    margin-bottom: 1.1rem;
    flex: 1;
}
.iq-tp {
    display: flex;
    align-items: center;
    gap: .7rem;
    border-top: 1px solid #EDF2F7;
    padding-top: .75rem;
}
.iq-tav {
    width: 34px;
    height: 34px;
    border-radius: 50%;
    flex-shrink: 0;
    background: linear-gradient(135deg, #DBEAFE, #EDE9FE);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    color: #2563EB;
    font-size: .78rem;
}
.iq-tpn {
    font-weight: 700;
    font-size: .82rem;
    color: #0F172A;
}
.iq-tpc {
    font-size: .72rem;
    color: #64748B;
    font-weight: 500;
}

/* ── Hero CTA buttons — force white text on <a> tags ── */
.iq-bp, .iq-bp:link, .iq-bp:visited, .iq-bp:hover, .iq-bp:active {
    color: #fff !important;
    text-decoration: none !important;
}
.iq-bs, .iq-bs:link, .iq-bs:visited { text-decoration: none !important; }

/* ── Free Trial Badge & Banner ── */
.iq-trial-tag {
    display: inline-flex; align-items: center; gap: .55rem;
    background: #EFF6FF; border: 1px solid #BFDBFE;
    padding: .4rem 1.15rem; border-radius: 99px;
    font-size: .86rem; color: #1E40AF; margin-bottom: 1.6rem;
    box-shadow: 0 2px 6px rgba(37,99,235,.08);
}
.iq-trial-pill {
    background: #2563EB; color: #fff; font-size: .68rem;
    font-weight: 800; letter-spacing: .08em; padding: .2rem .55rem;
    border-radius: 99px; text-transform: uppercase;
}
.iq-trial-info {
    background: #EFF6FF; border: 1px solid #DBEAFE;
    border-radius: 10px; padding: .65rem .85rem;
    font-size: .8rem; color: #1E40AF; line-height: 1.5;
    margin-bottom: .6rem;
}
.iq-trial-upgrade {
    margin-top: 1.8rem;
    background: linear-gradient(135deg, #F8FAFC 0%, #EFF6FF 100%);
    border: 1.5px solid #DBEAFE; border-radius: 16px;
    padding: 1.7rem 2rem; text-align: center;
}

.iq-account-exhausted {
    background: #FEF2F2;
    border: 1.5px solid #FCA5A5;
    border-radius: 12px;
    padding: .85rem 1rem;
    margin: .6rem 0;
    font-size: .83rem;
    color: #991B1B;
    line-height: 1.5;
}
.iq-account-exhausted a {
    color: #DC2626 !important;
    text-decoration: underline;
    font-weight: 700;
}

/* ── Interactive Feature Showcase Visualisations ── */
.iq-feat-box {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 16px;
    padding: 1.5rem;
    box-shadow: 0 4px 20px rgba(10,20,60,.04);
    margin-top: .75rem;
}
.iq-vis-statgrid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: .85rem;
    margin-bottom: 1.2rem;
}
.iq-vis-stat {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: .85rem 1rem;
    text-align: center;
}
.iq-vis-stat-val {
    font-size: 1.35rem;
    font-weight: 900;
    color: #2563EB;
    line-height: 1.1;
}
.iq-vis-stat-lbl {
    font-size: .74rem;
    color: #64748B;
    font-weight: 600;
    margin-top: .25rem;
}
.iq-pipeline-flow {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: .5rem;
    background: #F8FAFC;
    padding: .9rem 1.1rem;
    border-radius: 12px;
    border: 1px solid #E2E8F0;
    margin-bottom: 1.2rem;
    overflow-x: auto;
}
.iq-pipe-step {
    flex: 1;
    min-width: 140px;
    background: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    padding: .65rem .75rem;
    text-align: center;
    box-shadow: 0 2px 4px rgba(0,0,0,.02);
}
.iq-pipe-step-num {
    font-size: .63rem;
    font-weight: 800;
    color: #2563EB;
    text-transform: uppercase;
    letter-spacing: .06em;
}
.iq-pipe-step-title {
    font-size: .82rem;
    font-weight: 700;
    color: #0F172A;
    margin-top: .15rem;
}
.iq-pipe-arrow {
    color: #94A3B8;
    font-weight: 800;
    font-size: 1.1rem;
}
.iq-vis-table {
    width: 100%;
    border-collapse: collapse;
    font-size: .83rem;
    margin-top: .6rem;
}
.iq-vis-table th {
    background: #F1F5F9;
    color: #475569;
    font-weight: 700;
    font-size: .73rem;
    text-transform: uppercase;
    letter-spacing: .05em;
    padding: .55rem .75rem;
    text-align: left;
    border-bottom: 1px solid #E2E8F0;
}
.iq-vis-table td {
    padding: .65rem .75rem;
    border-bottom: 1px solid #F1F5F9;
    color: #1E293B;
}
.iq-score-bar-row {
    margin-bottom: .7rem;
}
.iq-score-bar-hdr {
    display: flex;
    justify-content: space-between;
    font-size: .78rem;
    font-weight: 700;
    color: #1E293B;
    margin-bottom: .25rem;
}
.iq-score-track {
    height: 7px;
    background: #E2E8F0;
    border-radius: 99px;
    overflow: hidden;
}
.iq-score-fill {
    height: 100%;
    border-radius: 99px;
    background: linear-gradient(90deg, #2563EB, #3B82F6);
}
.iq-score-fill-g {
    background: linear-gradient(90deg, #10B981, #34D399);
}
.iq-roi-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.1rem;
    margin-bottom: 1.1rem;
}
.iq-roi-box {
    border-radius: 12px;
    padding: 1.15rem;
    border: 1px solid #E2E8F0;
}
.iq-roi-manual {
    background: #FFFBFB;
    border-color: #FECACA;
}
.iq-roi-ai {
    background: #F0FDF4;
    border-color: #BBF7D0;
}

/* ── Feature Highlights (Bento Grid) ── */
.iq-feat-sec { margin: 3.5rem 0 2rem; }
.iq-feat-hdr { text-align: center; margin-bottom: 2.2rem; }
.iq-feat-eye {
    display: inline-block; font-size: .68rem; font-weight: 700;
    letter-spacing: .15em; color: #2563EB; text-transform: uppercase;
    background: #EFF6FF; padding: .35rem .95rem;
    border-radius: 99px; border: 1px solid #BFDBFE; margin-bottom: .85rem;
}
.iq-feat-h2 {
    font-size: clamp(1.4rem, 2.2vw, 2.15rem); font-weight: 900; color: #0F172A;
    letter-spacing: -0.5px; margin-bottom: .5rem; line-height: 1.2;
    white-space: nowrap;
}
@media (max-width: 860px) {
    .iq-feat-h2 { white-space: normal; }
}
.iq-feat-sub { font-size: 1rem; color: #64748B; max-width: 650px; margin: 0 auto; line-height: 1.5; }
.iq-feat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 1.35rem;
    margin-bottom: 2.5rem;
}
.iq-feat-card {
    background: #FFFFFF;
    border: 1.5px solid #E2E8F0;
    border-radius: 18px;
    padding: 1.8rem 1.5rem;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    transition: transform .15s, box-shadow .15s, border-color .15s;
}
.iq-feat-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 10px 28px rgba(15,23,42,.06);
    border-color: #CBD5E1;
}
.iq-feat-icon {
    width: 48px; height: 48px; border-radius: 12px;
    background: #EFF6FF; color: #2563EB; font-size: 1.35rem;
    display: flex; align-items: center; justify-content: center;
    margin-bottom: 1.1rem;
}
.iq-feat-badge {
    display: inline-block; font-size: .67rem; font-weight: 700;
    letter-spacing: .06em; text-transform: uppercase;
    background: #EFF6FF; color: #2563EB; border: 1px solid #DBEAFE;
    padding: .22rem .65rem; border-radius: 6px; margin-bottom: .75rem;
    width: fit-content;
}
.iq-feat-title { font-size: 1.12rem; font-weight: 800; color: #0F172A; margin-bottom: .45rem; line-height: 1.3; }
.iq-feat-desc { font-size: .84rem; color: #64748B; line-height: 1.6; }

/* ── High-Fidelity Bento Grid & UI Mockups (4 Cards in One Line) ── */
.iq-bento-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1.15rem;
    margin-bottom: 3rem;
}
@media (max-width: 1080px) {
    .iq-bento-grid {
        grid-template-columns: repeat(2, 1fr);
        gap: 1rem;
    }
}
@media (max-width: 600px) {
    .iq-bento-grid {
        grid-template-columns: 1fr;
    }
}
.iq-bento-card {
    background: #FFFFFF;
    border: 1.5px solid #E2E8F0;
    border-radius: 16px;
    padding: 1.35rem 1.1rem;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: transform .18s, box-shadow .18s, border-color .18s;
    box-shadow: 0 4px 16px -2px rgba(15, 23, 42, 0.04);
}
.iq-bento-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 12px 28px -4px rgba(15, 23, 42, 0.08);
    border-color: #BFDBFE;
}
.iq-bento-tag {
    display: inline-block;
    font-size: .65rem;
    font-weight: 700;
    letter-spacing: .06em;
    text-transform: uppercase;
    color: #2563EB;
    background: #EFF6FF;
    border: 1px solid #DBEAFE;
    padding: .18rem .55rem;
    border-radius: 6px;
    margin-bottom: .6rem;
    width: fit-content;
}
.iq-bento-title {
    font-size: 1.05rem;
    font-weight: 800;
    color: #0F172A;
    line-height: 1.3;
    margin-bottom: .35rem;
}
.iq-bento-sub {
    font-size: .78rem;
    color: #64748B;
    line-height: 1.45;
    margin-bottom: .95rem;
    min-height: 48px;
}
.iq-mockup-box {
    background: #F8FAFC;
    border: 1.5px solid #E2E8F0;
    border-radius: 12px;
    padding: .75rem;
}
/* ── Visual Recruitment Funnel (Layman visual graphics) ── */
.iq-funnel-step {
    display: flex; align-items: center; justify-content: space-between;
    background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px;
    padding: .4rem .55rem; margin-bottom: .4rem;
    box-shadow: 0 1px 3px rgba(15,23,42,.03);
}
.iq-funnel-left { display: flex; align-items: center; gap: .45rem; }
.iq-funnel-icon { font-size: .95rem; }
.iq-funnel-txt { font-size: .74rem; font-weight: 700; color: #0F172A; }
.iq-funnel-sub { font-size: .64rem; color: #64748B; }
.iq-funnel-badge {
    font-size: .62rem; font-weight: 700; padding: .15rem .45rem;
    border-radius: 4px; background: #EFF6FF; color: #2563EB;
    white-space: nowrap;
}
.iq-funnel-badge-green { background: #DCFCE7; color: #15803D; }
.iq-funnel-highlight {
    background: #ECFDF5; border: 1px solid #A7F3D0;
    border-radius: 8px; padding: .45rem .5rem; text-align: center;
    font-size: .7rem; font-weight: 700; color: #065F46; margin-top: .45rem;
}

.iq-gauge-row { margin-bottom: .5rem; }
.iq-gauge-row:last-child { margin-bottom: 0; }
.iq-gauge-info { display: flex; justify-content: space-between; font-size: .7rem; font-weight: 700; color: #334155; margin-bottom: .2rem; }
.iq-gauge-track { height: 5px; background: #E2E8F0; border-radius: 99px; overflow: hidden; }
.iq-gauge-bar { height: 100%; border-radius: 99px; }

.iq-cand-mini-row {
    display: flex; align-items: center; justify-content: space-between;
    padding: .38rem 0; border-bottom: 1px solid #EDF2F7;
}
.iq-cand-mini-row:last-child { border-bottom: none; }
.iq-cand-mini-left { display: flex; align-items: center; gap: .45rem; }
.iq-medal { font-size: .95rem; }
.iq-cand-mini-name { font-size: .76rem; font-weight: 800; color: #0F172A; }
.iq-cand-mini-role { font-size: .66rem; color: #64748B; }
.iq-score-pill {
    font-size: .64rem; font-weight: 700; padding: .18rem .45rem; border-radius: 4px; white-space: nowrap;
}
.iq-score-pill-green { background: #DCFCE7; color: #15803D; }
.iq-score-pill-blue { background: #DBEAFE; color: #1D4ED8; }

.iq-excel-preview { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; overflow: hidden; margin-bottom: .55rem; }
.iq-excel-hdr-row {
    display: grid; grid-template-columns: 18px 1.25fr .75fr 1.35fr;
    background: #F1F5F9; padding: .3rem .45rem; font-size: .58rem;
    font-weight: 800; text-transform: uppercase; color: #475569; letter-spacing: .02em;
    border-bottom: 1px solid #CBD5E1;
}
.iq-excel-data-row {
    display: grid; grid-template-columns: 18px 1.25fr .75fr 1.35fr;
    padding: .3rem .45rem; font-size: .66rem; color: #334155;
    border-bottom: 1px solid #F1F5F9; align-items: center;
}
.iq-excel-data-row:last-child { border-bottom: none; }
.iq-excel-footer { display: flex; justify-content: space-between; align-items: center; font-size: .66rem; color: #64748B; }
.iq-dl-badge {
    background: #10B981; color: #FFFFFF; font-weight: 700;
    font-size: .62rem; padding: .2rem .45rem; border-radius: 4px;
}

/* ── Why Recruiters Choose Pillars ── */
.iq-pillars-box {
    background: linear-gradient(175deg, #F8FAFC 0%, #EFF6FF 100%);
    border: 1.5px solid #DBEAFE; border-radius: 20px;
    padding: 2.4rem 2rem; margin: 3rem 0;
}
.iq-pillars-top { text-align: center; margin-bottom: 2rem; }
.iq-pillars-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 1.5rem;
}
.iq-pillar-item {
    background: #FFFFFF; border: 1px solid #E2E8F0;
    border-radius: 14px; padding: 1.5rem 1.4rem;
    box-shadow: 0 4px 12px rgba(15,23,42,.03);
}
.iq-pillar-stat { font-size: 1.85rem; font-weight: 900; color: #2563EB; line-height: 1.1; margin-bottom: .3rem; }
.iq-pillar-title { font-size: .95rem; font-weight: 800; color: #0F172A; margin-bottom: .35rem; }
.iq-pillar-desc { font-size: .8rem; color: #64748B; line-height: 1.5; }

/* ── FAQ Section (TuraHire style) ── */
.iq-faq-sec {
    max-width: 820px;
    margin: 4.5rem auto 3rem;
    padding: 0 1rem;
}
.iq-faq-hdr {
    text-align: center;
    margin-bottom: 2.2rem;
}
.iq-faq-eye {
    font-size: .75rem;
    font-weight: 800;
    color: #2563EB;
    letter-spacing: .12em;
    text-transform: uppercase;
    margin-bottom: .45rem;
}
.iq-faq-h2 {
    font-size: 2.15rem;
    font-weight: 900;
    color: #0F172A;
    letter-spacing: -.6px;
    margin-bottom: .5rem;
}
.iq-faq-sub {
    font-size: .94rem;
    color: #64748B;
    max-width: 560px;
    margin: 0 auto;
    line-height: 1.55;
}
.iq-faq-list {
    display: flex;
    flex-direction: column;
    gap: .75rem;
}
.iq-faq-item {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    overflow: hidden;
    transition: all .2s ease;
}
.iq-faq-item:hover {
    border-color: #CBD5E1;
    background: #F8FAFC;
}
.iq-faq-item[open] {
    background: #F8FAFC;
    border-color: #C7D2FE;
    box-shadow: 0 4px 16px rgba(99,102,241,.06);
}
.iq-faq-summary {
    padding: 1.15rem 1.35rem;
    font-size: 1.02rem;
    font-weight: 700;
    color: #0F172A;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    list-style: none;
    user-select: none;
}
.iq-faq-summary::-webkit-details-marker {
    display: none;
}
.iq-faq-summary::marker {
    display: none;
}
.iq-faq-arrow {
    width: 20px;
    height: 20px;
    color: #7C3AED;
    transition: transform .25s cubic-bezier(0.4, 0, 0.2, 1);
    flex-shrink: 0;
    margin-left: 1rem;
}
.iq-faq-item[open] .iq-faq-arrow {
    transform: rotate(180deg);
}
.iq-faq-body {
    padding: 0 1.35rem 1.25rem;
    font-size: .92rem;
    color: #475569;
    line-height: 1.65;
    border-top: 1px solid #F1F5F9;
    padding-top: .85rem;
}

/* ── Pricing & Payment Section (Compact & Minimal) ── */
.iq-price-sec { max-width: 740px; margin: 2.2rem auto 1.8rem; padding: 0 1rem; }
.iq-price-hdr { text-align: center; margin-bottom: 1.25rem; }
.iq-price-eye { display: inline-block; font-size: .68rem; font-weight: 800; color: #2563EB; text-transform: uppercase; letter-spacing: .08em; background: #EFF6FF; border: 1px solid #BFDBFE; padding: .18rem .6rem; border-radius: 999px; margin-bottom: .35rem; }
.iq-price-h2 { font-size: 1.45rem; font-weight: 800; color: #0B1120; margin-bottom: .25rem; letter-spacing: -.02em; }
.iq-price-sub { font-size: .82rem; color: #64748B; max-width: 520px; margin: 0 auto; line-height: 1.45; }
.iq-price-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.1rem; margin-top: 1.1rem; }
@media (max-width: 720px) { .iq-price-grid { grid-template-columns: 1fr; max-width: 360px; margin: 1.1rem auto 0; } }
.iq-plan-card { background: #FFFFFF; border: 1.5px solid #E2E8F0; border-radius: 14px; padding: 1.15rem 1.25rem; display: flex; flex-direction: column; justify-content: space-between; transition: all .25s ease; box-shadow: 0 2px 8px rgba(15,23,42,.03); position: relative; }
.iq-plan-card:hover { border-color: #93C5FD; box-shadow: 0 8px 20px rgba(37,99,235,.08); transform: translateY(-2px); }
.iq-plan-card.featured { border: 2px solid #2563EB; background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%); box-shadow: 0 8px 22px rgba(37,99,235,.09); }
.iq-plan-badge { display: inline-block; padding: .18rem .5rem; font-size: .62rem; font-weight: 800; border-radius: 999px; margin-bottom: .55rem; text-transform: uppercase; letter-spacing: .05em; }
.iq-badge-starter { background: #EFF6FF; color: #1E40AF; border: 1px solid #DBEAFE; }
.iq-badge-agency { background: #2563EB; color: #FFFFFF; box-shadow: 0 2px 6px rgba(37,99,235,.2); }
.iq-plan-name { font-size: 1.15rem; font-weight: 800; color: #0F172A; margin-bottom: .15rem; letter-spacing: -.01em; }
.iq-plan-desc { font-size: .78rem; color: #64748B; margin-bottom: .7rem; line-height: 1.4; }
.iq-plan-price-row { margin-bottom: .8rem; padding-bottom: .7rem; border-bottom: 1px solid #F1F5F9; }
.iq-plan-price-wrap { display: flex; align-items: baseline; gap: .25rem; }
.iq-plan-curr { font-size: 1.15rem; font-weight: 700; color: #0F172A; }
.iq-plan-amt { font-size: 2.05rem; font-weight: 900; color: #0F172A; line-height: 1; letter-spacing: -.03em; }
.iq-plan-period { font-size: .78rem; font-weight: 600; color: #64748B; }
.iq-plan-annual-sub { font-size: .72rem; color: #2563EB; font-weight: 700; margin-top: .15rem; }
.iq-plan-features { list-style: none; padding: 0; margin: 0 0 1rem 0; display: flex; flex-direction: column; gap: .45rem; }
.iq-plan-feat-item { display: flex; align-items: flex-start; gap: .45rem; font-size: .78rem; color: #334155; line-height: 1.35; }
.iq-feat-icon { color: #10B981; font-weight: 900; font-size: .85rem; flex-shrink: 0; margin-top: 1px; }
.iq-feat-icon-gold { color: #F59E0B; font-weight: 900; font-size: .88rem; flex-shrink: 0; margin-top: 1px; }
.iq-plan-btn { display: block; width: 100%; text-align: center; padding: .62rem 1rem; border-radius: 9px; font-weight: 800; font-size: .84rem; text-decoration: none !important; transition: all .2s ease; cursor: pointer; box-sizing: border-box; }
.iq-btn-primary { background: #2563EB !important; color: #FFFFFF !important; box-shadow: 0 3px 10px rgba(37,99,235,.22); }
.iq-btn-primary:hover { background: #1D4ED8 !important; transform: translateY(-1px); box-shadow: 0 5px 14px rgba(37,99,235,.28); }
.iq-btn-agency { background: #0F172A !important; color: #FFFFFF !important; box-shadow: 0 3px 10px rgba(15,23,42,.18); }
.iq-btn-agency:hover { background: #1E293B !important; transform: translateY(-1px); box-shadow: 0 5px 14px rgba(15,23,42,.24); }
.iq-guarantee { text-align: center; margin-top: .55rem; font-size: .7rem; color: #94A3B8; display: flex; align-items: center; justify-content: center; gap: .3rem; }
.iq-terms-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: .65rem; margin-top: 1.15rem; }
@media (max-width: 720px) { .iq-terms-grid { grid-template-columns: 1fr 1fr; } }
@media (max-width: 440px) { .iq-terms-grid { grid-template-columns: 1fr; } }
.iq-term-item { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: .65rem .75rem; text-align: left; box-shadow: 0 1px 3px rgba(15,23,42,.03); }
.iq-term-title { font-size: .74rem; font-weight: 800; color: #0F172A; margin-bottom: .2rem; display: flex; align-items: center; gap: .35rem; }
.iq-term-desc { font-size: .68rem; color: #64748B; line-height: 1.35; margin: 0; }
.iq-pay-badges { display: flex; align-items: center; justify-content: center; gap: .5rem; margin-top: 1.3rem; padding-top: 1rem; border-top: 1px solid #E2E8F0; flex-wrap: wrap; }
.iq-pay-pill { display: inline-flex; align-items: center; gap: .35rem; background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 7px; padding: .25rem .55rem; font-size: .72rem; font-weight: 700; color: #334155; }

.iq-foot { text-align:center; padding:2rem 0 1.5rem; border-top:1px solid #E2E8F0; margin-top:2rem; }
.iq-foot-txt { font-size:.78rem; color:#94A3B8; }

/* ── Responsive ── */
@media(max-width:1050px) {
    .iq-h1  { font-size:3.8rem; letter-spacing:-2.5px; }
    .iq-dskills { display:none; }
}
@media(max-width:900px) {
    .iq-h1  { font-size:3.2rem; letter-spacing:-2px; }
    .iq-tg  { grid-template-columns:1fr; }
    .iq-pg  { grid-template-columns:1fr; }
    .iq-pc-feat { transform:none; }
    .iq-fbar { flex-wrap:wrap; }
    .iq-fbar-item { min-width:50%; border-bottom:1px solid #E2E8F0; }
    .iq-fbar-item:nth-child(2) { border-right:none; }
    .iq-fbar-item:nth-child(3) { border-bottom:none; }
    .iq-fbar-item:nth-child(4) { border-right:none; border-bottom:none; }
    .iq-dskills { display:none; }
    .iq-drec-cell { display:none; }
}
@media(max-width:640px) {
    [data-testid="block-container"] { padding:0 1rem 3rem!important; }
    .iq-hero { padding:2.8rem .5rem 2rem; }
    .iq-h1   { font-size:2.6rem; letter-spacing:-1.5px; }
    .iq-sub  { font-size:.93rem; }
    .iq-btns { flex-direction:column; align-items:stretch; max-width:270px; margin:0 auto; }
    .iq-bp, .iq-bs { text-align:center; }
    .iq-ts-sec { padding:2rem 1.2rem; }
    .iq-fbar { display:none; }
    .iq-dash-outer { padding:1.3rem 1.3rem 0; }
    .iq-dash-sidebar { width:120px; }
    .iq-dnavitem span.iq-dnavtxt { display:none; }
    .iq-dskills { display:none; }
    .iq-drec-cell { display:none; }
}

hr { border-color:#E2E8F0!important; margin:1.5rem 0!important; }

/* ── Candidate Rankings panel ── */
.iq-cr-head {
    display:flex; align-items:center; justify-content:space-between;
    margin-bottom:.9rem;
}
.iq-cr-title { font-size:1.05rem; font-weight:800; color:#0B1120; }
.iq-cr-tools { display:flex; gap:.4rem; align-items:center; }
.iq-cr-search {
    font-size:.7rem; color:#94A3B8; background:#F8FAFC;
    border:1px solid #E2E8F0; border-radius:7px; padding:.28rem .7rem;
}
.iq-cr-filter {
    font-size:.7rem; color:#374151; font-weight:600;
    border:1px solid #E2E8F0; border-radius:7px; padding:.28rem .65rem; background:#fff;
}
.iq-cr-cols {
    display:flex; align-items:center; gap:.4rem;
    padding:.25rem 0 .5rem; border-bottom:1.5px solid #F1F5F9; margin-bottom:.5rem;
}
.iq-cr-col-sp { flex:1.8; }
.iq-cr-col {
    font-size:.6rem; font-weight:700; letter-spacing:.09em;
    text-transform:uppercase; color:#94A3B8; flex:1;
}
.iq-cr-row {
    display:flex; align-items:flex-start; gap:.65rem;
    padding:.75rem .85rem; border:1px solid #E2E8F0;
    border-radius:12px; margin-bottom:.55rem; background:#fff;
    box-shadow: 0 1px 3px rgba(15,23,42,.03);
    transition:background-color .15s ease, border-color .15s ease, box-shadow .15s ease;
}
.iq-cr-row:hover { background-color:#F8FAFC; border-color:#BFDBFE; box-shadow: 0 4px 14px rgba(37,99,235,.08); }
.iq-cr-rank {
    width:24px; height:24px; border-radius:6px;
    background:#EFF6FF; color:#2563EB; font-weight:800;
    font-size:.75rem; display:flex; align-items:center;
    justify-content:center; flex-shrink:0; margin-top:2px;
    border: 1px solid #DBEAFE;
}
.iq-cr-main { flex:1; min-width:0; }
.iq-cr-toprow { display:flex; align-items:center; gap:.35rem; margin-bottom:.4rem; }
.iq-cr-info   { flex:1; min-width:0; }
.iq-cr-name   { font-size:.84rem; font-weight:700; color:#0B1120; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.iq-cr-sub    { font-size:.7rem; color:#94A3B8; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.iq-cr-sc     { flex-shrink:0; min-width:52px; }
.iq-cr-pct    { font-size:1.15rem; font-weight:900; color:#10B981; line-height:1; margin-bottom:3px; }
.iq-cr-bar    { height:3px; background:#E2E8F0; border-radius:99px; overflow:hidden; width:88%; }
.iq-cr-barfill { height:100%; background:linear-gradient(90deg,#10B981,#34D399); border-radius:99px; }
.iq-cr-rec    { flex-shrink:0; }
.iq-cr-rbadge { font-size:.67rem; font-weight:700; padding:.26rem .65rem; border-radius:6px; white-space:nowrap; display:inline-block; }
.iq-cr-rb-strong { background:#D1FAE5; color:#065F46; }
.iq-cr-rb-good   { background:#DCFCE7; color:#166534; }
.iq-cr-rb-ok     { background:#FEF3C7; color:#92400E; }
.iq-cr-rb-no     { background:#F3F4F6; color:#6B7280; }
.iq-cr-sk-row    { display:flex; flex-wrap:wrap; gap:.28rem; }
.iq-cr-sk    { font-size:.65rem; background:#EFF6FF; color:#2563EB; border:1px solid #DBEAFE; border-radius:5px; padding:.18rem .5rem; font-weight:600; white-space:nowrap; }
.iq-cr-skmore { font-size:.65rem; background:#F1F5F9; color:#64748B; border-radius:5px; padding:.18rem .5rem; font-weight:600; }
.iq-cr-footer { border-top:1px solid #F1F5F9; margin-top:.4rem; padding-top:.6rem; }

/* ── Play button circle in secondary CTA ── */
.iq-play {
    display:inline-flex; align-items:center; justify-content:center;
    width:24px; height:24px; border-radius:50%;
    border:1.5px solid #CBD5E1; font-size:.52rem;
    flex-shrink:0; vertical-align:middle; margin-right:.4rem;
    color:#0B1120; transition:border-color .18s, color .18s;
}
.iq-bs:hover .iq-play { border-color:#2563EB; color:#2563EB; }

/* ── Feature bar ── */
.iq-fbar {
    display:flex; background:#fff;
    border:1px solid #E2E8F0; border-radius:16px;
    margin:1.6rem 0 1.8rem; overflow:hidden;
}
.iq-fbar-item {
    flex: 1 1 0; display:flex; align-items:center; gap:.85rem;
    padding:1.1rem 1.4rem; border-right:1px solid #E2E8F0;
}
.iq-fbar-item:last-child { border-right:none; }
.iq-fbar-icon {
    width:42px; height:42px; border-radius:50%;
    background:rgba(37,99,235,.08);
    display:flex; align-items:center; justify-content:center;
    font-size:1.1rem; flex-shrink:0;
}
.iq-fbar-t1 { font-size:.88rem; font-weight:700; color:#0B1120; line-height:1.35; }
.iq-fbar-t2 { font-size:.78rem; color:#64748B; line-height:1.35; }

/* ── Dashboard mockup ── */
.iq-dash-outer {
    background:linear-gradient(175deg,#EEF4FF 0%,#F5F7FB 65%);
    border-radius:22px; padding:2.2rem 2.2rem 0;
    border:1px solid #DBEAFE;
    margin-bottom:3rem; overflow:hidden;
}
.iq-dash-card {
    background:#fff; border-radius:14px 14px 0 0;
    box-shadow:0 24px 64px rgba(10,20,60,.14);
    display:flex; overflow:hidden;
    border:1px solid #E2E8F0; border-bottom:none;
}
.iq-dash-sidebar {
    width:175px; flex-shrink:0;
    padding:1.4rem 1rem;
    border-right:1px solid #F1F5F9;
    background:#FAFBFF;
}
.iq-dlogo {
    font-size:1.05rem; font-weight:900; color:#2563EB;
    letter-spacing:-.3px; margin-bottom:1.5rem; padding:0 .3rem;
}
.iq-dnavitem {
    display:flex; align-items:center; gap:.52rem;
    font-size:.8rem; color:#94A3B8; font-weight:500;
    padding:.44rem .58rem; border-radius:8px; margin-bottom:.12rem;
}
.iq-dnavitem.iq-active { background:#EFF6FF; color:#2563EB; font-weight:700; }
.iq-dnavico { width:15px; text-align:center; flex-shrink:0; font-size:.8rem; }
.iq-dash-content { flex:1; padding:1.4rem 1.6rem; overflow:hidden; min-width:0; }
.iq-dtopbar {
    display:flex; align-items:center; justify-content:space-between;
    margin-bottom:1.1rem;
}
.iq-dtitle { font-size:1.05rem; font-weight:800; color:#0B1120; }
.iq-dtopactions { display:flex; gap:.5rem; align-items:center; }
.iq-dsearch {
    font-size:.73rem; color:#94A3B8; background:#F8FAFC;
    border:1px solid #E2E8F0; border-radius:7px;
    padding:.32rem .8rem; min-width:138px;
}
.iq-dfilter {
    font-size:.73rem; color:#64748B; font-weight:600;
    border:1px solid #E2E8F0; border-radius:7px;
    padding:.32rem .72rem; background:#fff;
}
.iq-dtheader {
    display:flex; align-items:center; gap:.65rem;
    padding:.35rem 0 .5rem;
    border-bottom:1.5px solid #F1F5F9;
}
.iq-dth {
    font-size:.63rem; font-weight:700; letter-spacing:.07em;
    text-transform:uppercase; color:#94A3B8; flex:1;
}
.iq-drow {
    display:flex; align-items:center; gap:.65rem;
    padding:.7rem 0; border-bottom:1px solid #F8FAFC;
}
.iq-drank {
    width:21px; height:21px; border-radius:50%;
    background:#2563EB; color:#fff; font-weight:800;
    font-size:.63rem; display:flex; align-items:center;
    justify-content:center; flex-shrink:0;
}
.iq-davatar {
    width:37px; height:37px; border-radius:50%; flex-shrink:0;
    display:flex; align-items:center; justify-content:center;
    font-weight:800; font-size:.78rem; color:#fff;
}
.iq-dav1 { background:linear-gradient(135deg,#6366F1,#8B5CF6); }
.iq-dav2 { background:linear-gradient(135deg,#EC4899,#F97316); }
.iq-dav3 { background:linear-gradient(135deg,#0EA5E9,#14B8A6); }
.iq-dinfo { flex:1.5; min-width:0; }
.iq-dname { font-size:.83rem; font-weight:700; color:#0B1120; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.iq-drole { font-size:.72rem; color:#64748B; }
.iq-dexp  { font-size:.67rem; color:#94A3B8; }
.iq-dscore-cell { flex:.85; }
.iq-dpct { font-size:1.18rem; font-weight:900; color:#10B981; line-height:1; margin-bottom:3px; }
.iq-dbar { height:3px; background:#E2E8F0; border-radius:99px; overflow:hidden; width:78%; }
.iq-dbarfill { height:100%; background:linear-gradient(90deg,#10B981,#34D399); border-radius:99px; }
.iq-drec-cell { flex:1.1; }
.iq-drec { font-size:.69rem; font-weight:700; padding:.24rem .65rem; border-radius:6px; white-space:nowrap; display:inline-block; }
.iq-drec-strong { background:#D1FAE5; color:#065F46; }
.iq-drec-good   { background:#DCFCE7; color:#166534; }
.iq-dskills { flex:1.5; display:flex; flex-wrap:wrap; gap:.28rem; align-items:center; }
.iq-dsk { font-size:.66rem; background:#EFF6FF; color:#2563EB; border-radius:4px; padding:.2rem .52rem; font-weight:600; white-space:nowrap; }
.iq-dskmore { font-size:.66rem; background:#F1F5F9; color:#64748B; border-radius:4px; padding:.2rem .52rem; font-weight:600; }
.iq-dviewall {
    text-align:center; padding:.9rem 0;
    font-size:.83rem; font-weight:700; color:#2563EB;
    border-top:1px solid #F1F5F9; cursor:pointer;
}

/* ── UK GDPR Compliance & Engine Controls Bar ── */
.iq-sec-bar {
    background: #FFFFFF;
    border: 1.5px solid #DBEAFE;
    border-radius: 14px;
    padding: 1.1rem 1.4rem;
    margin-bottom: 1.4rem;
    box-shadow: 0 4px 14px rgba(37,99,235,.05);
}
.iq-sec-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: .8rem;
    margin-bottom: .85rem;
}
.iq-sec-title {
    font-size: 1rem;
    font-weight: 800;
    color: #0F172A;
    display: flex;
    align-items: center;
    gap: .5rem;
}
.iq-sec-badges {
    display: flex;
    align-items: center;
    gap: .5rem;
    flex-wrap: wrap;
}
.iq-sec-pill {
    font-size: .78rem;
    font-weight: 700;
    padding: .35rem .85rem;
    border-radius: 99px;
    display: inline-flex;
    align-items: center;
    gap: .35rem;
}
.iq-pill-green {
    background: #ECFDF5;
    color: #047857;
    border: 1px solid #A7F3D0;
}
.iq-pill-blue {
    background: #EFF6FF;
    color: #1D4ED8;
    border: 1px solid #BFDBFE;
}
.iq-pill-purple {
    background: #FAF5FF;
    color: #7E22CE;
    border: 1px solid #E9D5FF;
}

/* ── Top 3 Showcase Podium ── */
.iq-podium-wrap {
    margin: 1.5rem 0 2rem;
}
.iq-podium-hdr {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1rem;
}
.iq-podium-title {
    font-size: 1.25rem;
    font-weight: 900;
    color: #0F172A;
    letter-spacing: -.02em;
    display: flex;
    align-items: center;
    gap: .5rem;
}
.iq-podium-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(290px, 1fr));
    gap: 1.25rem;
}
.iq-podium-card {
    background: #FFFFFF;
    border-radius: 16px;
    padding: 1.4rem;
    border: 2px solid #E2E8F0;
    box-shadow: 0 4px 18px rgba(15,23,42,.04);
    position: relative;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: transform .2s ease, box-shadow .2s ease;
}
.iq-podium-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(37,99,235,.08);
}
.iq-podium-gold {
    border-color: #FCD34D;
    background: linear-gradient(180deg, #FFFDF5 0%, #FFFFFF 100%);
}
.iq-podium-silver {
    border-color: #CBD5E1;
    background: linear-gradient(180deg, #F8FAFC 0%, #FFFFFF 100%);
}
.iq-podium-bronze {
    border-color: #FDBA74;
    background: linear-gradient(180deg, #FFF7ED 0%, #FFFFFF 100%);
}
.iq-podium-badge {
    position: absolute;
    top: 1rem;
    right: 1rem;
    font-size: .75rem;
    font-weight: 800;
    padding: .25rem .65rem;
    border-radius: 99px;
    text-transform: uppercase;
    letter-spacing: .04em;
}
.iq-pbadge-gold { background: #FEF3C7; color: #92400E; border: 1px solid #FDE68A; }
.iq-pbadge-silver { background: #F1F5F9; color: #334155; border: 1px solid #E2E8F0; }
.iq-pbadge-bronze { background: #FFEDD5; color: #9A3412; border: 1px solid #FED7AA; }

/* ── Podium Decision Strip & Active Card Animations ── */
@keyframes decPop {
    0% { transform: scale(0.92); opacity: 0; }
    60% { transform: scale(1.03); }
    100% { transform: scale(1); opacity: 1; }
}
.iq-decision-strip {
    display: flex;
    align-items: center;
    gap: .5rem;
    padding: .5rem .75rem;
    border-radius: 8px;
    font-size: .8rem;
    font-weight: 700;
    margin-top: .85rem;
    animation: decPop .25s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.iq-dec-strip-shortlisted {
    background: #ECFDF5;
    border: 1.5px solid #10B981;
    color: #047857;
    box-shadow: 0 2px 10px rgba(16, 185, 129, 0.15);
}
.iq-dec-strip-passed {
    background: #FEF2F2;
    border: 1.5px solid #EF4444;
    color: #B91C1C;
    box-shadow: 0 2px 10px rgba(239, 68, 68, 0.12);
}
.iq-dec-strip-consider {
    background: #EFF6FF;
    border: 1.5px solid #3B82F6;
    color: #1D4ED8;
}
.iq-card-shortlisted {
    border-color: #10B981 !important;
    box-shadow: 0 8px 24px rgba(16, 185, 129, 0.18) !important;
    transition: all .25s cubic-bezier(0.4, 0, 0.2, 1);
}
.iq-card-passed {
    border-color: #F87171 !important;
    opacity: 0.9;
    background: #FFFBFB !important;
    transition: all .25s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Specific styling for decision buttons */
button[kind="primary"]:has(div:contains("Shortlist")),
button[kind="primary"]:has(div:contains("Shortlisted")) {
    background: linear-gradient(135deg, #059669, #10B981) !important;
    border-color: #059669 !important;
    color: #FFFFFF !important;
    box-shadow: 0 4px 14px rgba(16, 185, 129, 0.35) !important;
}
button[kind="primary"]:has(div:contains("Pass")),
button[kind="primary"]:has(div:contains("Passed")) {
    background: linear-gradient(135deg, #DC2626, #EF4444) !important;
    border-color: #DC2626 !important;
    color: #FFFFFF !important;
    box-shadow: 0 4px 14px rgba(220, 38, 38, 0.35) !important;
}

/* ── Human-in-the-Loop Override Panel ── */
.iq-override-card {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: .9rem 1.1rem;
    margin-top: .8rem;
}
.iq-override-title {
    font-size: .78rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: .06em;
    color: #475569;
    margin-bottom: .4rem;
    display: flex;
    align-items: center;
    gap: .4rem;
}
</style>"""

st.markdown(build_css(), unsafe_allow_html=True)


# ─────────────────────────── Production guard & housekeeping ─────────────────
_cfg_errors = config.production_config_errors()
if _cfg_errors:
    st.error("RankCV is not configured for production yet:\n\n" + "\n".join(f"- {e}" for e in _cfg_errors))
    st.stop()


@st.cache_resource
def _startup_housekeeping() -> bool:
    init_db()
    purge_stale_workspaces()
    for warning in config.production_config_warnings():
        log.warning("Config: %s", warning)
    return True


_startup_housekeeping()


def _render_footer() -> None:
    links = " &middot; ".join(
        f'<a href="?page={slug}" target="_self" style="color:#475569;">{_e(title)}</a>'
        for slug, title in LEGAL_PAGES.items()
    )
    parts = [config.COMPANY_NAME]
    if config.COMPANY_NUMBER:
        parts.append(f"Registered in England and Wales No. {config.COMPANY_NUMBER}")
    if config.COMPANY_ADDRESS:
        parts.append(config.COMPANY_ADDRESS)
    if config.ICO_REG_NUMBER:
        parts.append(f"ICO registration {config.ICO_REG_NUMBER}")
    parts.append(config.SUPPORT_EMAIL)
    details = " &middot; ".join(_e(x) for x in parts)
    render_html(f"""
<div class="iq-foot">
<div class="iq-foot-txt">RankCV &middot; AI CV Screening &amp; Candidate Ranking Platform</div>
<div class="iq-foot-txt" style="margin-top:.4rem;">{links}</div>
<div class="iq-foot-txt" style="margin-top:.4rem;font-size:.75rem;">{details}</div>
</div>
""")


# ─────────────────────────── Legal pages (?page=…) ───────────────────────────
_page = st.query_params.get("page", "")
if _page in LEGAL_PAGES:
    render_html('<div class="iq-nav"><div class="iq-logo">Rank<b>CV</b></div>'
                '<div><a href="./" target="_self" class="iq-nav-link">&larr; Back to RankCV</a></div></div>')
    st.markdown(render_legal_page(_page))
    _render_footer()
    st.stop()


# ─────────────────────────── Session state ───────────────────────────────────
for _k, _v in [
    ("results",              []),
    ("processed",            False),
    ("show_full",            False),
    ("engine_mode",          "cloud"),
    ("custom_api_key",       ""),
    ("custom_base_url",      ""),
    ("recruiter_overrides",  {}),
    ("audit_stats",          {}),
    ("run_meta",             {}),
    ("flash",                []),
    ("auth_pending_email",   ""),
    ("auth_pending_company", ""),
    ("auth_codes_sent",      0),
    ("dev_login_code",       ""),
]:
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ─────────────────────────── Helpers ─────────────────────────────────────────
def _flash(kind: str, msg: str) -> None:
    """Queue a message that survives the next st.rerun()."""
    st.session_state.flash.append((kind, msg))


def _show_flash() -> None:
    for kind, msg in st.session_state.flash:
        getattr(st, kind, st.info)(msg)
    st.session_state.flash = []


def _fmt_score(score: int):
    s10  = round(score / 10, 1)
    lbl  = f"{s10:.1f}" if s10 % 1 else f"{int(s10)}.0"
    full = min(5, round(score / 20))
    return lbl, "★" * full + "☆" * (5 - full)


_BAND_BADGE = {
    "strong":   ("iq-cr-rb-strong", BAND_LABELS["strong"]),
    "good":     ("iq-cr-rb-good",   BAND_LABELS["good"]),
    "moderate": ("iq-cr-rb-ok",     BAND_LABELS["moderate"]),
    "weak":     ("iq-cr-rb-no",     BAND_LABELS["weak"]),
    "invalid":  ("iq-cr-rb-no",     BAND_LABELS["invalid"]),
}
_BAND_REC_CSS = {
    "strong": "rec-highly", "good": "rec-recommended", "moderate": "rec-review",
    "weak": "rec-unsuitable", "invalid": "rec-unsuitable",
}


def _rec_badge(r: dict) -> str:
    return f'<span class="{_BAND_REC_CSS[_fit_band(r)]}">{_e(r.get("recommendation", "—"))}</span>'


def _extract_doc_file(path: str) -> str:
    """Extract text from Word 97-2003 .doc files (docx-in-disguise, textutil on macOS, antiword on Linux)."""
    try:
        from docx import Document
        doc = Document(path)
        t = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        if t.strip():
            return t.strip()
    except Exception:
        pass

    if sys.platform == "darwin" and shutil.which("textutil"):
        cmd = ["textutil", "-convert", "txt", "-stdout", path]
    elif shutil.which("antiword"):
        cmd = ["antiword", path]
    else:
        raise ValueError("old .doc files aren't supported on this server — please save it as .docx or PDF")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        raise ValueError("took too long to read — please save it as .docx or PDF")
    if res.returncode == 0 and res.stdout.strip():
        return res.stdout.strip()
    raise ValueError("couldn't be read as a Word document — please save it as .docx or PDF")


def _read_text_file(path: str) -> str:
    raw = Path(path).read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", errors="ignore")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="ignore")


def _extract_excel_file(path: str, fname: str) -> str:
    """Extract job-description content from Excel (.xlsx, .xls) and CSV files."""
    ext = Path(fname).suffix.lower()
    try:
        if ext == ".csv":
            try:
                df = pd.read_csv(path)
            except UnicodeDecodeError:
                df = pd.read_csv(path, encoding="cp1252")
        else:
            engine = "openpyxl" if ext == ".xlsx" else None
            sheets = pd.read_excel(path, sheet_name=None, engine=engine)
            df = pd.concat(list(sheets.values()), ignore_index=True) if sheets else pd.DataFrame()
    except Exception:
        log.exception("Spreadsheet parse failed")
        return ""
    df = df.dropna(how="all")
    lines = []
    for _, row in df.iterrows():
        parts = [f"{col}: {val}" for col, val in row.items() if pd.notna(val) and str(val).strip()]
        if parts:
            lines.append(" | ".join(parts))
    return "\n".join(lines)


def _read_cv_with_notes(path: str, fname: str):
    """Returns (text, notes) where notes are user-facing remarks about what was ignored."""
    ext = Path(fname).suffix.lower()
    notes = []
    if ext == ".pdf":
        text, flags = extract_pdf_text_with_flags(path)
        if flags.get("hidden_spans_dropped"):
            notes.append("contained hidden or tiny text, which was ignored")
        if flags.get("pages_truncated") or flags.get("chars_truncated"):
            notes.append("is very long; only the first part was read")
        return text, notes
    if ext == ".docx":
        text, flags = extract_docx_text_with_flags(path)
        if flags.get("hidden_runs_dropped"):
            notes.append("contained hidden or tiny text, which was ignored")
        if flags.get("chars_truncated"):
            notes.append("is very long; only the first part was read")
        return text, notes
    if ext == ".doc":
        return _extract_doc_file(path), notes
    if ext in (".xlsx", ".xls", ".csv"):
        return _extract_excel_file(path, fname), notes
    if ext == ".txt":
        return _read_text_file(path), notes
    raise ValueError("unsupported file type")


def _read_cv(path: str, fname: str) -> str:
    return _read_cv_with_notes(path, fname)[0]


def _extract_from_upload(f) -> str:
    """Extract text from a Streamlit UploadedFile inside a private temp folder."""
    if f.size > config.MAX_FILE_MB * 1024 * 1024:
        raise ValueError(f"is larger than {config.MAX_FILE_MB} MB")
    with screening_workspace() as wd:
        path = safe_upload_path(wd, f.name)
        f.seek(0)
        path.write_bytes(f.read())
        return _read_cv(str(path), f.name)


def _exp_subtitle(text: str) -> str:
    """Extract a short subtitle from relevant_experience text."""
    text = str(text or "")
    m = re.search(r'(\d+)\+?\s+years?', text, re.I)
    if m:
        return f"{m.group(1)}+ years experience"
    return text[:44].rstrip() + ("…" if len(text) > 44 else "")


# ─────────────────────────── Session & Client Auth State ─────────────────────
_TRIAL_Q = config.PLAN_QUOTAS["trial"]
_GUEST_AUTH = {
    "logged_in": False, "email": "", "contact_email": "", "company": "", "tier": "guest",
    "resumes_used": 0, "max_resumes": _TRIAL_Q, "remaining": _TRIAL_Q,
}


def _set_auth(acc: dict) -> None:
    st.session_state.client_auth = {
        "logged_in": True,
        "email": acc["email"],
        "contact_email": acc.get("contact_email") or acc["email"],
        "company": acc.get("company") or "",
        "tier": acc.get("tier", "trial"),
        "resumes_used": int(acc.get("resumes_used", 0)),
        "max_resumes": int(acc.get("max_resumes", _TRIAL_Q)),
        "remaining": int(acc.get("remaining", 0)),
    }


def _dev_codes_allowed() -> bool:
    """On-screen sign-in codes: local development only (flag set AND browser on localhost)."""
    if not config.DEV_SHOW_LOGIN_CODE:
        return False
    try:
        host = (st.context.headers.get("Host") or "").split(":")[0].lower()
    except Exception:
        host = ""
    return host in ("localhost", "127.0.0.1", "[::1]")


def _reset_results() -> None:
    for k in list(st.session_state.keys()):
        if isinstance(k, str) and k.startswith(("sel_stat_", "num_adj_", "txt_notes_")):
            del st.session_state[k]
    st.session_state.results = []
    st.session_state.audit_stats = {}
    st.session_state.run_meta = {}
    st.session_state.recruiter_overrides = {}
    st.session_state.processed = False
    st.session_state.show_full = False


_SESSION_COOKIE = "rankcv_session"


def _queue_cookie(token: str, max_age: int) -> None:
    """The cookie is written by a small script rendered at the end of the run (see bottom of file)."""
    st.session_state.cookie_write = (token, max_age)


def _sign_in(acc: dict) -> None:
    _set_auth(acc)
    token = create_session(acc["email"])
    st.session_state.session_token = token
    _queue_cookie(token, config.SESSION_DAYS * 86400)


def _sign_out() -> None:
    delete_session(st.session_state.get("session_token", ""))
    st.session_state.session_token = ""
    _queue_cookie("", 0)
    st.session_state.client_auth = dict(_GUEST_AUTH)
    _reset_results()


if "client_auth" not in st.session_state:
    st.session_state.client_auth = dict(_GUEST_AUTH)

# Stay signed in across refreshes: restore the session from the browser cookie once per session
if not st.session_state.client_auth.get("logged_in") and not st.session_state.get("cookie_checked"):
    st.session_state.cookie_checked = True
    try:
        _cookie_token = st.context.cookies.get(_SESSION_COOKIE, "")
    except Exception:
        _cookie_token = ""
    if _cookie_token:
        _restored = account_for_session(_cookie_token)
        if _restored:
            _set_auth(_restored)
            st.session_state.session_token = _cookie_token

_acc_warn = ""

# Keep the plan and quota current (also picks up a new or cancelled Stripe subscription)
if st.session_state.client_auth.get("logged_in"):
    _acc, _acc_warn = refresh_entitlements(st.session_state.client_auth["email"])
    if _acc:
        _set_auth(_acc)
    else:
        _sign_out()

_is_auth = st.session_state.client_auth.get("logged_in", False)
_auth_email = st.session_state.client_auth.get("contact_email", "")
_auth_tier = st.session_state.client_auth.get("tier", "guest")
_auth_rem = st.session_state.client_auth.get("remaining", _TRIAL_Q)
_auth_max = st.session_state.client_auth.get("max_resumes", _TRIAL_Q)

if _is_auth:
    _badge_text = f"{config.PLAN_LABELS.get(_auth_tier, 'Plan')}: {_auth_rem}/{_auth_max} left"
    _email_display = _auth_email if len(_auth_email) <= 20 else _auth_email[:18] + "…"
    nav_auth_btn = f'''
    <a href="#client-auth" style="font-size:.82rem !important;font-weight:700 !important;color:#1E3A8A !important;background:#EFF6FF !important;border:1.5px solid #BFDBFE !important;padding:.42rem .85rem !important;border-radius:8px !important;text-decoration:none !important;display:inline-flex !important;align-items:center !important;gap:.35rem !important;box-shadow:0 1px 3px rgba(0,0,0,.05) !important;">
      <span>🛡️</span><span>{_e(_email_display)} ({_e(_badge_text)})</span>
    </a>
    '''
else:
    nav_auth_btn = '''
    <a href="#client-auth" style="font-size:.82rem !important;font-weight:700 !important;color:#334155 !important;background:#FFFFFF !important;border:1.5px solid #CBD5E1 !important;padding:.42rem .85rem !important;border-radius:8px !important;text-decoration:none !important;display:inline-flex !important;align-items:center !important;gap:.35rem !important;box-shadow:0 1px 3px rgba(0,0,0,.05) !important;transition:all .15s ease !important;cursor:pointer !important;">
      <span>👤</span><span>Client Login</span>
    </a>
    '''

# ─────────────────────────── Navbar ──────────────────────────────────────────
render_html(f"""
<div class="iq-nav">
  <div class="iq-logo">Rank<b>CV</b></div>
  <div class="iq-nav-center">
    <a href="#screening-workspace" class="iq-nav-link">Screen CVs</a>
    <a href="#how-it-works" class="iq-nav-link">How It Works</a>
    <a href="#features" class="iq-nav-link">Features</a>
    <a href="#pricing" class="iq-nav-link">Pricing</a>
    <a href="#security" class="iq-nav-link">Security &amp; GDPR</a>
    <a href="#faq" class="iq-nav-link">FAQ</a>
  </div>
  <div style="display:flex;align-items:center;gap:.65rem;flex-shrink:0;">
    {nav_auth_btn}
    <a class="iq-nav-demo" href="#pricing" style="font-size:.84rem !important;font-weight:700 !important;color:#FFFFFF !important;background:#2563EB !important;padding:.44rem 1.15rem !important;border-radius:8px !important;border:none !important;box-shadow:0 2px 8px rgba(37,99,235,.25) !important;text-decoration:none !important;display:inline-flex !important;align-items:center !important;cursor:pointer !important;">
      <span>Upgrade &nbsp;&rarr;</span>
    </a>
  </div>
</div>
""")


# ─────────────────────────── Hero ────────────────────────────────────────────
render_html("""
<div class="iq-hero">
<div class="iq-eye">&#10022; &nbsp;Visual AI Resume Screening &amp; Candidate Ranking</div>
<div class="iq-h1">Shortlist Top Talent <span class="bl">in Minutes</span></div>
<div class="iq-sub">Upload a job description and candidate CVs to screen, score, and rank applicants &mdash; then review and decide.</div>
</div>
""")


# ─────────────────────────── Feature Bar ─────────────────────────────────────
render_html("""
<div class="iq-fbar">
<div class="iq-fbar-item">
<div class="iq-fbar-icon">&#9889;</div>
<div>
<div class="iq-fbar-t1">Screen 100s of CVs</div>
<div class="iq-fbar-t2">In minutes, not days</div>
</div>
</div>
<div class="iq-fbar-item">
<div class="iq-fbar-icon">&#11088;</div>
<div>
<div class="iq-fbar-t1">AI Scoring &amp; Ranking</div>
<div class="iq-fbar-t2">0&ndash;100 match score</div>
</div>
</div>
<div class="iq-fbar-item">
<div class="iq-fbar-icon">&#128200;</div>
<div>
<div class="iq-fbar-t1">Identify Top Talent</div>
<div class="iq-fbar-t2">Strengths &amp; concerns per CV</div>
</div>
</div>
<div class="iq-fbar-item">
<div class="iq-fbar-icon">&#9201;</div>
<div>
<div class="iq-fbar-t1">Save Hours Weekly</div>
<div class="iq-fbar-t2">1-Click Shortlist Reports</div>
</div>
</div>
</div>
""")


# ─────────────────────────── UK GDPR Security & Engine Bar ───────────────────
render_html("""
<div id="security" class="iq-sec-bar">
  <div class="iq-sec-top">
    <div class="iq-sec-title">
      <span>🛡️ UK GDPR Privacy Controls &amp; Screening Engine</span>
    </div>
    <div class="iq-sec-badges">
      <span class="iq-sec-pill iq-pill-green">🔒 PII Redaction Before AI Scoring</span>
      <span class="iq-sec-pill iq-pill-blue">⚖️ Article 22 Human Review</span>
      <span class="iq-sec-pill iq-pill-purple">🗑️ CV Files Deleted After Each Run</span>
    </div>
  </div>
</div>
""")

sec_c1, sec_c2, sec_c3 = st.columns([1.6, 1.2, 1.2])
with sec_c1:
    engine_choice = st.radio(
        "Screening Engine Mode:",
        ["⚡ Cloud AI (OpenAI)", "🛡️ Private Engine (no external AI calls)"],
        index=0 if st.session_state.get("engine_mode", "cloud") == "cloud" else 1,
        horizontal=True,
        key="engine_choice_radio",
        label_visibility="collapsed"
    )
    st.session_state.engine_mode = "private" if "Private" in engine_choice else "cloud"

with sec_c2:
    with st.popover("🔑 Your Own OpenAI Key (optional)"):
        st.markdown("### 🔑 Bring Your Own Key (BYOK)")
        st.markdown(
            "Cloud AI uses RankCV's OpenAI account by default. Enter your organisation's own key "
            "to have OpenAI process requests under **your** agreement with them."
        )
        st.session_state.custom_api_key = st.text_input(
            "OpenAI API Key (sk-...)",
            value=st.session_state.get("custom_api_key", ""),
            type="password",
            placeholder="sk-proj-...",
            help="Held in server memory for this session only. Never stored or logged."
        )
        st.session_state.custom_base_url = st.text_input(
            "Custom endpoint (optional, advanced)",
            value=st.session_state.get("custom_base_url", ""),
            placeholder="https://<resource>.openai.azure.com/openai/v1/",
            help="Azure OpenAI (v1 API) or api.openai.com only, and only with your own key. "
                 f"Your Azure deployment must be named '{config.get_setting('OPENAI_MODEL', 'gpt-4o')}'.",
        )
        st.caption(
            "Before Cloud AI scoring, names, emails, phone numbers, postcodes, personal links, dates of "
            "birth and common protected-characteristic fields are redacted automatically (best-effort). "
            "Choose the Private Engine to keep CV content away from third-party AI entirely."
        )

with sec_c3:
    with st.popover("⚖️ GDPR & Legal"):
        st.markdown("### ⚖️ How RankCV handles candidate data")
        st.markdown(f"""
- **Roles:** your organisation is the **controller** of candidate data. RankCV ({config.COMPANY_NAME}) is your **processor** under our [Data Processing Agreement](?page=dpa).
- **AI provider:** in Cloud AI mode, redacted CV text is sent to OpenAI (US) as our sub-processor, or under your own agreement if you use your own key. The Private Engine sends nothing to any AI provider.
- **Storage:** uploaded files are deleted as soon as their text is extracted. Results stay in your session's memory only and are never written to our database.
- **Human oversight (Article 22):** scores are decision support. Every candidate starts as *Under Review*; a recruiter must record each decision.
- **Law:** England and Wales.

[Privacy Notice](?page=privacy) · [Terms](?page=terms) · [Sub-processors](?page=subprocessors) · [Cookies](?page=cookies)
""")


# ─────────────────────────── Client Authentication ───────────────────────────
render_html('<div id="client-auth"></div>')

_c_logged_in = st.session_state.client_auth.get("logged_in", False)

if _c_logged_in:
    _ca = st.session_state.client_auth
    _c_tier, _c_rem, _c_max, _c_used = _ca["tier"], _ca["remaining"], _ca["max_resumes"], _ca["resumes_used"]
    _plan_name = (f"{config.PLAN_LABELS.get(_c_tier, 'Plan')} ({_c_max:,} CVs per billing period)"
                  if _c_tier in ("pro", "agency") else f"Free Trial ({_c_max} CVs)")
    _plan_icon = "★" if _c_tier in ("pro", "agency") else "🎁"
    render_html(f"""
    <div style="background:#EFF6FF;border:1.5px solid #BFDBFE;border-radius:12px;padding:.85rem 1.25rem;margin:0.5rem 0 0.8rem;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.75rem;">
      <div style="display:flex;align-items:center;gap:.75rem;">
        <span style="font-size:1.4rem;">{_plan_icon}</span>
        <div>
          <div style="font-size:.9rem;font-weight:800;color:#1E3A8A;">Active Plan: {_e(_plan_name)}</div>
          <div style="font-size:.78rem;color:#3B82F6;font-weight:600;">
            Signed in as <b>{_e(_ca['contact_email'])}</b> &bull; <b>{_c_rem:,}/{_c_max:,} CVs remaining</b> ({_c_used:,} used)
          </div>
        </div>
      </div>
      <div style="display:flex;align-items:center;gap:.6rem;">
        <span style="font-size:.72rem;background:#10B981;color:#fff;font-weight:800;padding:.22rem .65rem;border-radius:99px;">✓ VERIFIED</span>
      </div>
    </div>
    """)
    if _acc_warn:
        st.warning(_acc_warn)
    col_so0, col_so1, col_so2, col_so3 = st.columns([3, 1.1, 1.1, 1])
    with col_so1:
        if st.button("↻ Refresh plan", key="btn_refresh_plan", use_container_width=True,
                     help="Just subscribed? Pull your plan from Stripe now."):
            _acc2, _w2 = refresh_entitlements(_ca["email"], force=True)
            if _acc2:
                _set_auth(_acc2)
            _flash("warning" if _w2 else "success", _w2 or "Plan refreshed.")
            st.rerun()
    with col_so2:
        if config.STRIPE_PORTAL_URL:
            st.link_button("Manage billing", config.STRIPE_PORTAL_URL, use_container_width=True)
    with col_so3:
        if st.button("🚪 Sign Out", key="btn_signout", use_container_width=True):
            _sign_out()
            st.rerun()
else:
    _show_exp = st.session_state.get("show_auth_portal", False) or bool(st.session_state.auth_pending_email)
    with st.expander(f"👤 Sign In / Start Your {_TRIAL_Q} CV Free Trial", expanded=_show_exp):
        _pending = st.session_state.auth_pending_email
        if not _pending:
            st.markdown(
                f"Enter your **work email** and we'll send you a 6-digit sign-in code. New accounts get "
                f"**{_TRIAL_Q} free CV evaluations**. Subscribed through Stripe? Use your billing email "
                f"and your plan is applied automatically."
            )
            col_e1, col_e2, col_e3 = st.columns([2.2, 1.8, 1.2])
            with col_e1:
                email_in = st.text_input("Work Email", placeholder="recruiter@yourcompany.co.uk",
                                         key="client_email_input").strip()
            with col_e2:
                company_in = st.text_input("Company Name (Optional)", placeholder="e.g. Acme Recruitment",
                                           key="client_company_input").strip()
            with col_e3:
                st.write("")
                st.write("")
                send_code = st.button("Email me a code →", type="primary", use_container_width=True,
                                      key="btn_send_code")
            if send_code:
                if st.session_state.auth_codes_sent >= 8:
                    st.error("Too many sign-in attempts from this browser session. Please try again later.")
                else:
                    ok, msg, code = request_login_code(email_in)
                    if not ok:
                        st.error(msg)
                    else:
                        st.session_state.auth_codes_sent += 1
                        if email_configured():
                            sent = send_login_code(normalize_email(email_in), code)
                        elif _dev_codes_allowed():
                            sent = True
                            st.session_state.dev_login_code = code
                        else:
                            sent = False
                        if sent:
                            st.session_state.auth_pending_email = normalize_email(email_in)
                            st.session_state.auth_pending_company = company_in
                            st.session_state.show_auth_portal = True
                            _flash("success", msg)
                            st.rerun()
                        else:
                            st.error("We couldn't send the sign-in email. Please try again shortly or contact support.")
        else:
            _is_new = not get_account(_pending)
            st.markdown(f"Enter the 6-digit code we sent to **{_pending}**.")
            if st.session_state.dev_login_code:
                st.info(f"Development mode (email delivery not configured): your code is "
                        f"**{st.session_state.dev_login_code}**")
            col_v1, col_v2 = st.columns([2.2, 3])
            with col_v1:
                code_in = st.text_input("Sign-in code", max_chars=6, placeholder="123456", key="auth_code_input")
            terms_ok = True
            if _is_new:
                terms_ok = st.checkbox(
                    "I agree to the [Terms of Service](?page=terms) and the [Data Processing Agreement](?page=dpa), "
                    "and I have read the [Privacy Notice](?page=privacy).",
                    key="auth_terms",
                )
            col_b1, col_b2, col_b3, _ = st.columns([1.3, 1.1, 1.3, 2])
            with col_b1:
                if st.button("Verify & sign in", type="primary", use_container_width=True, key="btn_verify"):
                    ok, msg, acc = verify_login_code(_pending, code_in,
                                                     company=st.session_state.auth_pending_company,
                                                     accept_terms=terms_ok)
                    if ok:
                        _sign_in(acc)
                        st.session_state.auth_pending_email = ""
                        st.session_state.dev_login_code = ""
                        st.session_state.show_auth_portal = False
                        _flash("success", msg)
                        st.rerun()
                    else:
                        st.error(msg)
            with col_b2:
                if st.button("Resend code", use_container_width=True, key="btn_resend"):
                    ok, msg, code = request_login_code(_pending)
                    if ok:
                        if email_configured():
                            ok = send_login_code(_pending, code)
                        elif _dev_codes_allowed():
                            st.session_state.dev_login_code = code
                        else:
                            ok = False
                    if ok:
                        st.success("A new code is on its way.")
                    else:
                        st.error(msg if "wait" in msg or "Too many" in msg else "We couldn't send the email. Please try again shortly.")
            with col_b3:
                if st.button("Use a different email", use_container_width=True, key="btn_change_email"):
                    st.session_state.auth_pending_email = ""
                    st.session_state.dev_login_code = ""
                    st.rerun()

_show_flash()


# ─────────────────────────── 3-panel layout ──────────────────────────────────
render_html('<div id="screening-workspace" style="margin-top:0.8rem;"></div>')
col1, col2, col3 = st.columns([1, 1, 1], gap="medium")

# ══════════════════════════ PANEL 1 — Job Description ═════════════════════════
SAMPLE_ROLES = {
    "Custom (Paste your own JD)": "",
    "Senior Python Backend Engineer": (
        "Job Title: Senior Python Backend Engineer\n"
        "Location: Remote\n"
        "Experience: 5+ years\n\n"
        "About the Role:\n"
        "We are looking for a Senior Python Backend Engineer to build high-performance APIs and scalable cloud services.\n\n"
        "Key Requirements:\n"
        "- 5+ years building backend applications in Python (FastAPI, Django, Flask)\n"
        "- Strong experience with relational databases (PostgreSQL, MySQL)\n"
        "- Hands-on expertise with AWS cloud infrastructure (ECS, Lambda, S3)\n"
        "- Containerisation using Docker and CI/CD pipelines\n"
        "- Strong understanding of microservices architecture and REST APIs\n"
        "- Familiarity with caching systems (Redis) and message queues"
    ),
    "Cloud Solutions Architect": (
        "Job Title: Cloud Solutions Architect\n"
        "Location: Remote / Hybrid\n"
        "Experience: 7+ years\n\n"
        "About the Role:\n"
        "Seeking an experienced Cloud Architect to design resilient cloud infrastructure, microservices, and secure deployments.\n\n"
        "Key Requirements:\n"
        "- 7+ years in software engineering and cloud infrastructure design\n"
        "- AWS / GCP Certified Solutions Architect preferred\n"
        "- Deep knowledge of Kubernetes, Docker, and Infrastructure as Code (Terraform)\n"
        "- Proven experience architecting multi-region, high-availability distributed systems\n"
        "- Strong background in database scaling, security compliance, and disaster recovery"
    ),
    "Lead Data Scientist (ML/AI)": (
        "Job Title: Lead Data Scientist / ML Engineer\n"
        "Location: Remote\n"
        "Experience: 5+ years\n\n"
        "About the Role:\n"
        "We are seeking a Lead Data Scientist to design, train, and deploy production machine learning models and NLP pipelines.\n\n"
        "Key Requirements:\n"
        "- 5+ years applied machine learning experience using Python (PyTorch, TensorFlow, Scikit-Learn)\n"
        "- Expertise in NLP, LLMs, and semantic search architectures\n"
        "- Experience with distributed computing (Spark, Airflow) and vector databases\n"
        "- Strong SQL and data pipeline optimization skills\n"
        "- Proven track record taking models from research to high-throughput production deployment"
    ),
    "IT Sales Manager (B2B SaaS)": (
        "Job Title: IT Sales Manager (B2B SaaS)\n"
        "Location: London / Hybrid\n"
        "Experience: 6+ years\n\n"
        "About the Role:\n"
        "We are looking for an IT Sales Manager to lead enterprise B2B sales cycles, manage pipeline, and drive software license revenue.\n\n"
        "Key Requirements:\n"
        "- 6+ years experience in B2B IT sales, enterprise sales, and SaaS software solutions\n"
        "- Proven track record of quota attainment, pipeline management, and deal closing\n"
        "- Strong experience with CRM (Salesforce / HubSpot), lead generation, and client acquisition\n"
        "- Excellent client presentation, negotiation, and contract closing skills"
    ),
}

def _on_role_select():
    sel = st.session_state.get("sample_role_sel")
    if sel and sel != "Custom (Paste your own JD)":
        st.session_state["jd_paste"] = SAMPLE_ROLES.get(sel, "")

with col1:
    with st.container(border=True):
        render_html("""
<div class="iq-phead">
  <div class="iq-pnum">1</div>Job Description
</div>""")

        st.selectbox(
            "💡 Or choose a sample role:",
            list(SAMPLE_ROLES.keys()),
            key="sample_role_sel",
            index=0,
            on_change=_on_role_select,
            label_visibility="visible",
        )

        tab_paste, tab_file = st.tabs(["Paste Text", "Upload File"])

        jd_text = st.session_state.get("jd_paste", "").strip()

        with tab_paste:
            jd_input = st.text_area(
                "Job description",
                placeholder="Paste your job description, role overview, and key requirements here…",
                height=270,
                max_chars=10000,
                key="jd_paste",
                label_visibility="collapsed",
            )
            render_html(f'<div class="iq-char"><span id="iq-live-chars">{len(jd_input):,} / 10,000</span></div>')
            if jd_input.strip():
                jd_text = jd_input.strip()

        with tab_file:
            jd_file = st.file_uploader(
                "Upload your JD (PDF, Word, TXT, Excel)",
                type=["pdf", "docx", "doc", "txt", "xlsx", "xls", "csv"],
                key="jd_file_up",
                label_visibility="collapsed",
            )
            if jd_file:
                cache_key = f"_jd_cache_{jd_file.file_id}"
                if cache_key not in st.session_state:
                    for _old in [k for k in st.session_state.keys() if str(k).startswith("_jd_cache_")]:
                        del st.session_state[_old]
                    try:
                        st.session_state[cache_key] = _extract_from_upload(jd_file)[:10000]
                    except ValueError as ex:
                        st.session_state[cache_key] = ""
                        st.error(f"This file {ex}.")
                    except Exception:
                        log.exception("JD file parse failed")
                        st.session_state[cache_key] = ""
                        st.error("We couldn't read that file. Try PDF, DOCX or TXT, or paste the text.")
                extracted = st.session_state[cache_key]
                if extracted.strip():
                    jd_text = extracted.strip()
                    st.caption(f"✅ Extracted {len(jd_text):,} characters from your file")

        if jd_text:
            render_html(f'<div id="iq-jd-status-badge" class="iq-status-ok">✅ Job description ready ({len(jd_text):,} chars)</div>')
        else:
            render_html('<div id="iq-jd-status-badge" class="iq-status-wait">✍️ Type or paste your job requirements above</div>')


# ══════════════════════════ PANEL 2 — Upload CVs ══════════════════════════════
with col2:
    with st.container(border=True):
        _ca = st.session_state.client_auth
        if _ca.get("logged_in"):
            _c_tier, _c_rem = _ca["tier"], _ca["remaining"]
            if _c_tier in ("pro", "agency"):
                _tier_label = f"★ {config.PLAN_LABELS[_c_tier]} ({_c_rem:,} CVs left)"
            else:
                _tier_label = f"🎁 Free Trial ({_c_rem}/{_ca['max_resumes']} CVs left)"
            _max_cvs = min(config.MAX_BATCH_CVS, _c_rem)
        else:
            _tier_label = f"🎁 {_TRIAL_Q} CVs Free Trial"
            _max_cvs = _TRIAL_Q

        render_html(f"""
<div class="iq-phead">
  <div class="iq-pnum">2</div>Upload Candidate CVs
</div>
<div class="iq-cr-head">
  <div style="font-size:.82rem;font-weight:700;color:#64748B;">Candidate Resumes (PDF, DOCX, TXT)</div>
  <div style="background:#EFF6FF; color:#2563EB; font-size:.68rem; font-weight:700; padding:.22rem .6rem; border-radius:6px; border:1px solid #DBEAFE;">{_e(_tier_label)}</div>
</div>""")

        cv_files = st.file_uploader(
            f"Upload CVs (PDF, DOC/DOCX, TXT — up to {_max_cvs} files, {config.MAX_FILE_MB} MB each)",
            type=["pdf", "docx", "doc", "txt"],
            accept_multiple_files=True,
            key="cv_up",
            label_visibility="collapsed",
        )
        total_uploaded = len(cv_files or [])

        if total_uploaded > _max_cvs:
            render_html(
                f'<div class="iq-status-wait" style="background:#FEF2F2;color:#DC2626;border-color:#FCA5A5">'
                f'⚠️ <b>{total_uploaded} CVs uploaded</b> — this run is limited to {_max_cvs} CVs '
                f'(your remaining quota, max {config.MAX_BATCH_CVS} per batch). '
                f'Please remove {total_uploaded - _max_cvs} file(s) or upgrade your plan.</div>'
            )
        elif total_uploaded > 0:
            render_html(f'<div class="iq-status-ok">✅ <b>{total_uploaded}/{_max_cvs} CVs selected</b> ready for screening</div>')
        else:
            render_html('<div class="iq-status-wait">⏳ Drag &amp; drop resumes or test with 5 demo CVs below…</div>')

        render_html("<div style='height:.7rem'></div>")
        col_btn1, col_btn2 = st.columns([1.15, 1])
        with col_btn1:
            run_btn = st.button("🚀  Screen Candidates", use_container_width=True, type="primary")
        with col_btn2:
            demo_btn = st.button("⚡  Try 5 Demo CVs", use_container_width=True)


# ══════════════════════════ PANEL 3 — Results ═════════════════════════════════
def _run_screening(sources, jd: str, *, offline: bool, demo: bool):
    """
    Parse every source inside a private temp folder (deleted on exit, even on error or
    rerun), then score. `sources` is a list of (display_name, Path | UploadedFile).
    Returns (results, audit_stats, skipped, run_meta).
    """
    run_id = uuid.uuid4().hex[:12]
    job_context = extract_job_context(jd)
    candidates, skipped, file_notes = [], [], []
    bar = st.progress(0.0, text=f"Reading {len(sources)} CV(s)…")
    info = st.empty()

    with screening_workspace() as wd:
        for idx, (fname, src) in enumerate(sources, 1):
            render_html(
                f'<p style="font-size:.82rem;color:#64748B">📄 <b style="color:#2563EB">{_e(fname)}</b> '
                f'({idx}/{len(sources)})</p>', container=info)
            try:
                if isinstance(src, Path):
                    path = src
                else:
                    if src.size > config.MAX_FILE_MB * 1024 * 1024:
                        raise ValueError(f"is larger than {config.MAX_FILE_MB} MB")
                    path = safe_upload_path(wd, fname)
                    src.seek(0)
                    path.write_bytes(src.read())
                text, notes = _read_cv_with_notes(str(path), fname)
                for note in notes:
                    file_notes.append((fname, note))
                if not text.strip():
                    raise ValueError("has no readable text (it may be a scanned image)")
                candidates.append(extract_resume_keywords(
                    cv_text=text, required_skills=job_context.get("skills", ""), filename=fname))
            except ValueError as ex:
                skipped.append((fname, str(ex)))
            except Exception:
                log.exception("CV parse failed")
                skipped.append((fname, "could not be read"))
            bar.progress(idx / len(sources) * 0.4, text=f"Reading CVs — {idx}/{len(sources)} done…")
    # All uploaded files are gone at this point; only extracted text remains in memory.

    results, audit = [], {}
    if candidates:
        def _progress(done: int, total: int) -> None:
            bar.progress(0.4 + 0.6 * done / max(1, total),
                         text=f"Scoring {len(candidates)} candidate(s) — {done}/{total} batches done…")

        render_html(f'<p style="font-size:.82rem;color:#64748B">🤖 Scoring <b style="color:#2563EB">'
                    f'{len(candidates)} candidate(s)</b>…</p>', container=info)
        try:
            results, audit = rank_candidates_batch(
                candidates=candidates,
                job_context=job_context,
                custom_api_key=st.session_state.get("custom_api_key", "").strip(),
                offline_mode=offline,
                base_url=st.session_state.get("custom_base_url", "").strip(),
                return_audit=True,
                progress_cb=_progress,
            )
        except Exception:
            log.exception("Scoring failed")
            results, audit = [], {}
            skipped.append(("All CVs", "scoring failed unexpectedly — nothing was charged; please try again"))
    bar.progress(1.0, text="✅ Done")
    info.empty()

    results = sorted(results or [], key=_score, reverse=True)
    modes = {r.get("scoring_engine") or ("offline" if "Private" in str(r.get("processing_mode", "")) else "cloud")
             for r in results}
    mode_used = audit.get("mode_used") or ("mixed" if len(modes) > 1 else (modes.pop() if modes else ""))
    run_meta = {
        "run_id": run_id,
        "started_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "demo": demo,
        "mode_requested": "offline" if offline else "cloud",
        "mode_used": mode_used,
        "fallback_reason": audit.get("fallback_reason", ""),
        "files_received": len(sources),
        "files_scored": len(results),
        "file_notes": file_notes,
    }
    return results, audit, skipped, run_meta


def _store_run(results, audit, run_meta) -> None:
    _reset_results()
    st.session_state.results = results
    st.session_state.audit_stats = audit
    st.session_state.run_meta = run_meta
    st.session_state.recruiter_overrides = {
        r.get("candidate_index", i): {"status": "Under Review", "score_delta": 0, "notes": "", "decided_at": ""}
        for i, r in enumerate(results)
    }
    st.session_state.processed = True
    st.session_state.show_full = True


def _flash_run_outcome(results, skipped, run_meta) -> None:
    if results:
        _flash("success", f"🎯 Scored {len(results)} candidate(s). Every candidate starts as "
                          f"*Under Review* — record your decision for each one below.")
    for fname, why in skipped:
        _flash("warning", f"⚠️ Skipped **{fname}**: {why}.")
    for fname, note in run_meta.get("file_notes", []):
        _flash("info", f"ℹ️ **{fname}** {note}.")
    if run_meta.get("mode_requested") == "cloud" and run_meta.get("mode_used") in ("offline", "mixed"):
        reason = (run_meta.get("fallback_reason") or "Cloud AI was unavailable").strip().rstrip(".")
        _flash("warning", f"⚠️ {reason}. Affected CVs were scored by the keyword-based Private Engine "
                          f"instead of Cloud AI — see the *Scoring engine* column in the report.")


with col3:
    with st.container(border=True):
        render_html("""
<div class="iq-phead">
  <div class="iq-pnum">3</div>Candidate Rankings
</div>""")

        # ── Demo: 5 bundled sample CVs, always on the Private Engine, no quota ──
        if demo_btn:
            demo_files = sorted(Path("dummy_cvs_pdf").glob("*.pdf"))[:5]
            if not demo_files:
                st.error("Demo CVs not found on server.")
            else:
                _jd = jd_text.strip() or SAMPLE_ROLES["Senior Python Backend Engineer"]
                results, audit, skipped, meta = _run_screening(
                    [(p.name, p) for p in demo_files], _jd, offline=True, demo=True)
                _store_run(results, audit, meta)
                _flash("info", "Demo: 5 sample CVs scored with the Private Engine. Sign in to screen your own CVs.")
                _flash_run_outcome(results, skipped, meta)
                st.rerun()

        # ── Real screening ───────────────────────────────────────────────────
        if run_btn:
            _ca = st.session_state.client_auth
            if not _ca.get("logged_in"):
                st.session_state["show_auth_portal"] = True
                _flash("error", f"🔒 Please sign in (or start your {_TRIAL_Q} CV free trial) above before screening your own CVs.")
                st.rerun()

            active_jd = (jd_text or "").strip() or st.session_state.get("jd_paste", "").strip()
            if not active_jd:
                sel_r = st.session_state.get("sample_role_sel")
                if sel_r and SAMPLE_ROLES.get(sel_r, "").strip():
                    active_jd = SAMPLE_ROLES[sel_r].strip()

            errors = []
            if not active_jd:
                errors.append("Please provide a Job Description in Panel 1 (paste text or choose a sample).")
            if total_uploaded == 0:
                errors.append("Please upload at least one candidate CV in Panel 2.")
            elif total_uploaded > _max_cvs:
                errors.append(f"This batch has {total_uploaded} CVs but the limit for this run is {_max_cvs}. "
                              f"Remove some files or upgrade your plan.")

            if errors:
                for err in errors:
                    st.error(err)
            else:
                ok, quota_msg, _ = reserve_quota(_ca["email"], total_uploaded)
                if not ok:
                    st.error(quota_msg)
                else:
                    scored = 0
                    try:
                        results, audit, skipped, meta = _run_screening(
                            [(f.name, f) for f in cv_files], active_jd,
                            offline=st.session_state.get("engine_mode") == "private", demo=False)
                        # Documents flagged as not being CVs are not charged
                        scored = sum(1 for r in results if _fit_band(r) != "invalid")
                        _store_run(results, audit, meta)
                    finally:
                        # Only CVs that were actually scored count against the quota
                        release_quota(_ca["email"], total_uploaded - scored)
                        _acc3 = get_account(_ca["email"])
                        if _acc3:
                            _set_auth(_acc3)
                    _flash_run_outcome(results, skipped, meta)
                    st.rerun()

        # ── Show results ─────────────────────────────────────────────────────
        if st.session_state.processed and st.session_state.results:
            results = st.session_state.results
            _meta = st.session_state.run_meta

            render_html(f"""
<div class="iq-cr-head">
<div style="font-size:.82rem;font-weight:700;color:#64748B;">Top Matches ({len(results)} evaluated)</div>
<div style="font-size:.7rem;font-weight:700;color:#475569;">{_e(_MODE_LABELS.get(_meta.get('mode_used'), ''))}</div>
</div>
<div class="iq-cr-cols">
<div class="iq-cr-col-sp"></div>
<div class="iq-cr-col">Match Score</div>
<div class="iq-cr-col">AI Fit</div>
</div>""")

            for rank, r in enumerate(results[:5], 1):
                score    = _score(r)
                name     = r.get("candidate_name") or "Unknown"
                skills   = str(r.get("skills_match", "") or "")
                sub      = _exp_subtitle(r.get("relevant_experience", ""))
                skill_list = [s.strip() for s in skills.split(",") if s.strip()]
                extra = max(0, len(skill_list) - 3)
                sk_html = "".join(f'<span class="iq-cr-sk">{_e(s)}</span>' for s in skill_list[:3])
                if extra:
                    sk_html += f'<span class="iq-cr-skmore">+{extra}</span>'
                rb_cls, rb_txt = _BAND_BADGE[_fit_band(r)]

                render_html(f"""
<div class="iq-cr-row">
<div class="iq-cr-rank">{rank}</div>
<div class="iq-cr-main">
<div class="iq-cr-toprow">
<div class="iq-cr-info">
<div class="iq-cr-name">{_e(name)}</div>
<div class="iq-cr-sub">{_e(sub)}</div>
</div>
<div class="iq-cr-sc">
<div class="iq-cr-pct">{score}%</div>
<div class="iq-cr-bar"><div class="iq-cr-barfill" style="width:{score}%"></div></div>
</div>
<div class="iq-cr-rec"><span class="iq-cr-rbadge {rb_cls}">{rb_txt}</span></div>
</div>
<div class="iq-cr-sk-row">{sk_html}</div>
</div>
</div>""")

            render_html('<div class="iq-cr-footer"></div>')
            if st.button("View All Candidates →", use_container_width=True, key="view_full_btn"):
                st.session_state.show_full = True

        elif st.session_state.processed and not st.session_state.results:
            st.error("❌ No candidates could be scored. Check the messages above for each file.")

        else:
            # Idle state — illustrative sample preview
            render_html("""
<div class="iq-cr-head">
<div style="font-size:.82rem;font-weight:700;color:#64748B;">Top Matches Preview</div>
<div style="background:#EFF6FF; color:#2563EB; font-size:.68rem; font-weight:700; padding:.22rem .6rem; border-radius:6px; border:1px solid #DBEAFE;">✨ Sample Preview</div>
</div>
<div class="iq-cr-cols">
<div class="iq-cr-col-sp"></div>
<div class="iq-cr-col">Match Score</div>
<div class="iq-cr-col">AI Fit</div>
</div>

<div class="iq-cr-row">
<div class="iq-cr-rank">1</div>
<div class="iq-cr-main">
<div class="iq-cr-toprow">
<div class="iq-cr-info">
<div class="iq-cr-name">Alex Chen</div>
<div class="iq-cr-sub">8+ years experience &bull; Senior Cloud Architect</div>
</div>
<div class="iq-cr-sc">
<div class="iq-cr-pct">94%</div>
<div class="iq-cr-bar"><div class="iq-cr-barfill" style="width:94%"></div></div>
</div>
<div class="iq-cr-rec"><span class="iq-cr-rbadge iq-cr-rb-strong">Strong Match</span></div>
</div>
<div class="iq-cr-sk-row">
<span class="iq-cr-sk">Python</span>
<span class="iq-cr-sk">FastAPI</span>
<span class="iq-cr-sk">AWS</span>
<span class="iq-cr-sk">PostgreSQL</span>
<span class="iq-cr-sk">Docker</span>
</div>
</div>
</div>

<div class="iq-cr-row">
<div class="iq-cr-rank">2</div>
<div class="iq-cr-main">
<div class="iq-cr-toprow">
<div class="iq-cr-info">
<div class="iq-cr-name">Maria Santos</div>
<div class="iq-cr-sub">5+ years experience &bull; Backend API Engineer</div>
</div>
<div class="iq-cr-sc">
<div class="iq-cr-pct">89%</div>
<div class="iq-cr-bar"><div class="iq-cr-barfill" style="width:89%"></div></div>
</div>
<div class="iq-cr-rec"><span class="iq-cr-rbadge iq-cr-rb-good">Good Match</span></div>
</div>
<div class="iq-cr-sk-row">
<span class="iq-cr-sk">Python</span>
<span class="iq-cr-sk">PostgreSQL</span>
<span class="iq-cr-sk">Docker</span>
<span class="iq-cr-sk">Kubernetes</span>
<span class="iq-cr-sk">Redis</span>
</div>
</div>
</div>

<div class="iq-cr-row">
<div class="iq-cr-rank">3</div>
<div class="iq-cr-main">
<div class="iq-cr-toprow">
<div class="iq-cr-info">
<div class="iq-cr-name">Siddharth Rao</div>
<div class="iq-cr-sub">4+ years experience &bull; Full-Stack Services</div>
</div>
<div class="iq-cr-sc">
<div class="iq-cr-pct">78%</div>
<div class="iq-cr-bar"><div class="iq-cr-barfill" style="width:78%; background:linear-gradient(90deg,#3B82F6,#60A5FA)"></div></div>
</div>
<div class="iq-cr-rec"><span class="iq-cr-rbadge iq-cr-rb-ok">Review</span></div>
</div>
<div class="iq-cr-sk-row">
<span class="iq-cr-sk">Python</span>
<span class="iq-cr-sk">FastAPI</span>
<span class="iq-cr-sk">PostgreSQL</span>
<span class="iq-cr-sk">Docker</span>
</div>
</div>
</div>

<div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:10px; padding:.7rem .85rem; margin-top:.7rem; text-align:center;">
<div style="font-size:.78rem; color:#475569; font-weight:600;">
💡 <b>Interactive Demo Ready:</b> Click <b style="color:#2563EB;">⚡ Try 5 Demo CVs</b> in Panel 2 to screen sample resumes.
</div>
</div>
""")


# ─────────────────────────── Full results (below panels) ─────────────────────
_STATUS_OPTIONS = ["Under Review", "Shortlisted", "Consider", "Rejected"]


def _record_decision(c_idx, *, status=None, score_delta=None, notes=None) -> None:
    ov = st.session_state.recruiter_overrides.setdefault(
        c_idx, {"status": "Under Review", "score_delta": 0, "notes": "", "decided_at": ""})
    changed = False
    for field, val in (("status", status), ("score_delta", score_delta), ("notes", notes)):
        if val is not None and ov.get(field) != val:
            ov[field] = val
            changed = True
    if changed:
        ov["decided_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


if st.session_state.get("show_full") and st.session_state.results:
    results = st.session_state.results
    _meta = st.session_state.run_meta
    _run = _meta.get("run_id", "run")
    _ovs = st.session_state.recruiter_overrides
    render_html("<div style='height:1rem'></div>")

    if _meta.get("demo"):
        st.info("These are demo results for 5 bundled sample CVs, scored with the Private Engine.")
    st.caption("🔒 Results are kept only for this browser session and are never stored by RankCV. "
               "Download the report below before closing or refreshing the page.")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Screened", len(results))
    m2.metric("Shortlisted by you", sum(1 for o in _ovs.values() if o.get("status") == "Shortlisted"))
    m3.metric("Avg Match", f"{round(sum(_score(r) for r in results) / len(results), 1)}%")
    m4.metric("Top Match", f"{max(_score(r) for r in results)}%")

    # ── Candidate Showcase (top 6) ──────────────────────────────────────
    _PODIUM_THEMES = [
        ("🥇 Rank #1", "iq-podium-gold", "iq-pbadge-gold", "#B45309"),
        ("🥈 Rank #2", "iq-podium-silver", "iq-pbadge-silver", "#334155"),
        ("🥉 Rank #3", "iq-podium-bronze", "iq-pbadge-bronze", "#C2410C"),
    ]
    _showcase = results[:6]
    render_html(f"""
<div class="iq-podium-wrap">
  <div class="iq-podium-hdr">
    <div class="iq-podium-title">🏆 Top {len(_showcase)} of {len(results)} Candidates</div>
    <div style="font-size:.78rem;font-weight:700;color:#047857;background:#ECFDF5;padding:.25rem .75rem;border-radius:99px;border:1px solid #A7F3D0;">
      ✓ Human decision required for every candidate
    </div>
  </div>
</div>
""")

    BATCH_SIZE = 3
    for b_start in range(0, len(_showcase), BATCH_SIZE):
        batch = _showcase[b_start: b_start + BATCH_SIZE]
        _pod_cols = st.columns(len(batch))
        for i_in_batch, c_r in enumerate(batch):
            p_i = b_start + i_in_batch
            p_t, p_c, pb_c, p_col = (_PODIUM_THEMES[p_i] if p_i < len(_PODIUM_THEMES)
                                     else (f"📋 Rank #{p_i + 1}", "iq-podium-silver", "iq-pbadge-silver", "#64748B"))
            with _pod_cols[i_in_batch]:
                p_score = _score(c_r)
                p_name = c_r.get("candidate_name") or "Unknown"
                p_skills = [s.strip() for s in str(c_r.get("skills_match", "") or "").split(",") if s.strip()][:3]
                p_idx = c_r.get("candidate_index", p_i)
                curr_status = _ovs.get(p_idx, {}).get("status", "Under Review")

                if curr_status == "Shortlisted":
                    card_status_cls = "iq-card-shortlisted"
                    dec_strip_html = ('<div class="iq-decision-strip iq-dec-strip-shortlisted">'
                                      '<span>✅</span><span>Your decision: <b>Shortlisted</b></span></div>')
                elif curr_status == "Rejected":
                    card_status_cls = "iq-card-passed"
                    dec_strip_html = ('<div class="iq-decision-strip iq-dec-strip-passed">'
                                      '<span>❌</span><span>Your decision: <b>Passed</b></span></div>')
                else:
                    card_status_cls = ""
                    dec_strip_html = ('<div class="iq-decision-strip iq-dec-strip-consider">'
                                      f'<span>⚡</span><span>Your decision: <b>{_e(curr_status)}</b></span></div>')

                sk_badges = "".join(f'<span class="iq-cr-sk" style="font-size:.72rem;">{_e(s)}</span>' for s in p_skills)
                render_html(f"""
<div class="iq-podium-card {p_c} {card_status_cls}">
  <span class="iq-podium-badge {pb_c}">{_e(p_t)} &mdash; {_BAND_BADGE[_fit_band(c_r)][1]}</span>
  <div>
    <div style="font-size:1.15rem;font-weight:800;color:#0F172A;margin-top:.4rem;">{_e(p_name)}</div>
    <div style="font-size:.78rem;color:#64748B;font-weight:500;margin-bottom:.8rem;">{_e(c_r.get("relevant_experience", ""))}</div>
    <div style="display:flex;align-items:baseline;gap:.4rem;margin-bottom:.4rem;">
      <span style="font-size:1.6rem;font-weight:900;color:{p_col};">{p_score}%</span>
      <span style="font-size:.8rem;color:#64748B;font-weight:600;">AI Match</span>
    </div>
    <div style="height:6px;background:#E2E8F0;border-radius:99px;overflow:hidden;margin-bottom:.9rem;">
      <div style="height:100%;width:{p_score}%;background:{p_col};border-radius:99px;"></div>
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:.3rem;margin-bottom:1rem;">{sk_badges}</div>
    <div style="font-size:.8rem;color:#334155;line-height:1.45;background:rgba(255,255,255,.7);padding:.6rem .8rem;border-radius:8px;border:1px solid rgba(0,0,0,.05);">
      <b>AI Rationale:</b> {_e(c_r.get("recommendation", ""))}
    </div>
    {dec_strip_html}
  </div>
</div>
""")
                p_b1, p_b2 = st.columns([1, 1])
                with p_b1:
                    is_short = curr_status == "Shortlisted"
                    if st.button("✓ Shortlisted" if is_short else "✅ Shortlist", key=f"btn_short_{_run}_{p_idx}",
                                 use_container_width=True, type="primary" if is_short else "secondary"):
                        _record_decision(p_idx, status="Shortlisted")
                        st.session_state[f"sel_stat_{_run}_{p_idx}"] = "Shortlisted"
                        st.toast(f"🎯 {p_name} shortlisted", icon="✅")
                        st.rerun()
                with p_b2:
                    is_pass = curr_status == "Rejected"
                    if st.button("✕ Passed" if is_pass else "❌ Pass", key=f"btn_pass_{_run}_{p_idx}",
                                 use_container_width=True, type="primary" if is_pass else "secondary"):
                        _record_decision(p_idx, status="Rejected")
                        st.session_state[f"sel_stat_{_run}_{p_idx}"] = "Rejected"
                        st.toast(f"📋 {p_name} marked as Pass", icon="❌")
                        st.rerun()
        render_html("<div style='height:.75rem'></div>")

    # ── Score Distribution Visualisation ─────────────────────────────
    with st.expander("📊 Candidate Match Score Visualisation", expanded=True):
        chart_data = pd.DataFrame([
            {"Candidate": f"{i + 1}. {r.get('candidate_name') or 'Candidate'}", "Match Score (%)": _score(r)}
            for i, r in enumerate(results[:20])
        ])
        chart = alt.Chart(chart_data).mark_bar(cornerRadius=6, color="#2563EB").encode(
            x=alt.X("Match Score (%):Q", scale=alt.Scale(domain=[0, 100]), title="Match Score (%)"),
            y=alt.Y("Candidate:N", sort="-x", title=""),
            tooltip=["Candidate", "Match Score (%)"]
        ).properties(height=max(160, len(chart_data) * 28))
        st.altair_chart(chart, use_container_width=True)

    # ── Search + Filter bar ──────────────────────────────────────────
    _fc1, _fc2, _fc3 = st.columns([3, 2, 1.2])
    with _fc1:
        _search = st.text_input("Search candidates", placeholder="🔍  Search candidates by name or skill…",
                                label_visibility="collapsed", key="res_search")
    with _fc2:
        _filter = st.selectbox("Filter candidates",
                               ["All Candidates", "Strong Match", "Good Match", "Review", "Weak / Not a CV",
                                "Not yet decided"],
                               label_visibility="collapsed", key="res_filter")

    _ranked = list(enumerate(results, 1))
    if _search:
        _sq = _search.strip().lower()
        _ranked = [(rk, r) for rk, r in _ranked
                   if _sq in str(r.get("candidate_name", "")).lower() or _sq in str(r.get("skills_match", "")).lower()]
    _band_filter = {"Strong Match": ("strong",), "Good Match": ("good",), "Review": ("moderate",),
                    "Weak / Not a CV": ("weak", "invalid")}
    if _filter in _band_filter:
        _ranked = [(rk, r) for rk, r in _ranked if _fit_band(r) in _band_filter[_filter]]
    elif _filter == "Not yet decided":
        _ranked = [(rk, r) for rk, r in _ranked
                   if _ovs.get(r.get("candidate_index", rk - 1), {}).get("status", "Under Review") == "Under Review"]

    _PAGE = 20
    _pages = max(1, -(-len(_ranked) // _PAGE))
    with _fc3:
        _pg = st.number_input("Page", min_value=1, max_value=_pages, value=1, step=1,
                              key=f"res_page_{_run}", label_visibility="collapsed",
                              disabled=_pages == 1, help=f"{_pages} page(s) of {_PAGE}")
    _shown = _ranked[(_pg - 1) * _PAGE: _pg * _PAGE]

    render_html(
        f'<div class="iq-results-hdr">'
        f'<span class="iq-results-hdr-title">📋 All Candidate Profiles &amp; Recruiter Review</span>'
        f'<span class="iq-results-count">{len(_ranked)} match &middot; page {_pg}/{_pages}</span>'
        f'</div>'
    )

    if not _ranked:
        render_html(
            '<div style="text-align:center;padding:2.5rem 1rem;color:#94A3B8;'
            'font-size:.92rem;background:#F8FAFF;border:1.5px dashed #E2E8F0;'
            'border-radius:12px;margin:.5rem 0">No candidates match your filter.</div>'
        )

    _MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}

    for rank, r in _shown:
        score     = _score(r)
        name      = r.get("candidate_name") or "Unknown"
        strengths = [str(s) for s in (r.get("strengths") or [])]
        concerns  = [str(c) for c in (r.get("concerns") or [])]
        sub       = _exp_subtitle(r.get("relevant_experience", ""))
        s_lbl, s_stars = _fmt_score(score)
        band = _fit_band(r)
        c_cls = "iq-tag-m" if band in ("strong", "good") else "iq-tag-r"
        score_level = "hi" if score >= 80 else ("mid" if score >= 65 else "lo")
        accent_col  = "#10B981" if score >= 80 else ("#F59E0B" if score >= 65 else "#EF4444")
        c_idx = r.get("candidate_index", rank - 1)
        c_ov = _ovs.setdefault(c_idx, {"status": "Under Review", "score_delta": 0, "notes": "", "decided_at": ""})

        medal = _MEDALS.get(rank, f"#{rank}")
        exp_label = (f"{medal}  {name}   ·   {s_lbl}/10  {s_stars}   ·   {_BAND_BADGE[band][1]}"
                     f"   ·   Decision: {c_ov.get('status', 'Under Review')}")

        str_html = "".join(f'<span class="iq-tag iq-tag-g">&#10003; {_e(s)}</span>' for s in strengths) \
                   or '<span class="iq-tag iq-tag-m">None noted</span>'
        con_html = "".join(f'<span class="iq-tag {c_cls}">&#10007; {_e(c)}</span>' for c in concerns) \
                   or '<span class="iq-tag iq-tag-m">None noted</span>'

        with st.expander(exp_label, expanded=(rank == 1 and _pg == 1)):
            render_html(f"""
<div class="iq-det" style="border-left:4px solid {accent_col}">
  <div class="iq-det-hrow">
    <div class="iq-det-hinfo">
      <div class="iq-det-name">{_e(name)}</div>
      <div style="font-size:.78rem;color:#64748B;font-weight:500;margin-top:2px;">{_e(sub)}</div>
    </div>
    <div class="iq-det-badge iq-det-badge-{score_level}">
      <div class="iq-det-badgenum">{s_lbl}</div>
      <div class="iq-det-badgedenom">/10</div>
      <div class="iq-det-badgestars">{s_stars}</div>
    </div>
  </div>
  <div class="iq-det-divider"></div>
  <div class="iq-det-cols">
    <div>
      <div class="iq-det-lbl">Strengths</div>
      <div class="iq-det-tags">{str_html}</div>
    </div>
    <div>
      <div class="iq-det-lbl">Concerns</div>
      <div class="iq-det-tags">{con_html}</div>
    </div>
  </div>
  <div class="iq-det-divider"></div>
  <div class="iq-det-lbl">AI Recommendation</div>
  <div style="margin-top:.5rem">{_rec_badge(r)}</div>
  <div style="font-size:.72rem;color:#94A3B8;margin-top:.5rem;">Scored by: {_e(r.get("processing_mode", ""))}</div>
</div>""")

            render_html("""
<div class="iq-override-card">
  <div class="iq-override-title">
    <span>⚖️ Recruiter Oversight &amp; Decision (UK GDPR Art. 22)</span>
  </div>
  <div style="font-size:.76rem;color:#64748B;margin-bottom:.5rem;">
    The AI score is advice only. Review the candidate and record your own decision.
  </div>
</div>""")
            _sk, _nk, _tk = f"sel_stat_{_run}_{c_idx}", f"num_adj_{_run}_{c_idx}", f"txt_notes_{_run}_{c_idx}"
            if _sk not in st.session_state:
                st.session_state[_sk] = c_ov.get("status", "Under Review")
            if _nk not in st.session_state:
                st.session_state[_nk] = int(c_ov.get("score_delta", 0))
            if _tk not in st.session_state:
                st.session_state[_tk] = c_ov.get("notes", "")
            ov_col1, ov_col2, ov_col3 = st.columns([1.2, 1.2, 2.2])
            with ov_col1:
                new_status = st.selectbox("Decision Status:", _STATUS_OPTIONS, key=_sk)
            with ov_col2:
                new_pts = st.number_input("Score Adj (+/-):", min_value=-20, max_value=20, step=1, key=_nk)
            with ov_col3:
                new_note = st.text_input("Reviewer Notes:", max_chars=500,
                                         placeholder="e.g. Verified technical references; invite to interview…",
                                         key=_tk)
            _record_decision(c_idx, status=new_status, score_delta=int(new_pts), notes=new_note)
            if c_ov.get("decided_at"):
                st.caption(f"Decision recorded {c_ov['decided_at']}")

    # ── Download — Excel report with an accurate audit sheet ─────────
    _reviewed = sum(1 for o in _ovs.values() if o.get("decided_at"))
    _controller = (st.session_state.client_auth.get("company")
                   or st.session_state.client_auth.get("contact_email") or "Customer")
    _xl_bytes = build_excel_report(results, _ovs, _meta, st.session_state.get("audit_stats", {}), _controller)
    st.download_button(
        "⬇️  Download Shortlist Report with UK GDPR Audit Log (.xlsx)",
        data=_xl_bytes,
        file_name=f"rankcv_results_{_run}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary",
        key=f"dl_{_run}",
    )
    if _reviewed < len(results):
        st.caption(f"{len(results) - _reviewed} candidate(s) have no recorded decision yet; the report marks them 'Not reviewed'.")

    render_html(f"""
<div class="iq-trial-upgrade">
  <div style="font-size:1.15rem;font-weight:800;color:#0B1120;margin-bottom:.35rem">
    Ready to screen 100s of CVs across active roles?
  </div>
  <div style="font-size:.9rem;color:#64748B;max-width:540px;margin:0 auto 1.1rem;line-height:1.6">
    RankCV helps recruitment &amp; HR teams screen, score and shortlist CVs in bulk &mdash; with a recruiter in control of every decision.
  </div>
  <a class="iq-bp" href="{_e(config.WHATSAPP_URL)}" target="_blank" rel="noopener" style="padding:.65rem 1.6rem;font-size:.9rem">
    Book a Quick Walkthrough on WhatsApp &nbsp;&rarr;
  </a>
</div>
""")


# ─────────────────────────── Features & Platform Capabilities ────────────────
render_html("""
<div id="how-it-works"></div>
<div id="features" class="iq-feat-sec">
<div class="iq-feat-hdr">
<div class="iq-feat-eye">Platform Capabilities</div>
<div class="iq-feat-h2">Visual AI Resume Screening &amp; Candidate Ranking</div>
<div class="iq-feat-sub">Built specifically for hiring teams and recruitment leads. Spot top talent in seconds without reading through hundreds of pages.</div>
</div>
<div class="iq-bento-grid">
<div class="iq-bento-card">
<div>
<div class="iq-bento-tag">Instant Funnel</div>
<div class="iq-bento-title">Screen 100+ CVs in Minutes</div>
<div class="iq-bento-sub">Rank bulk resumes automatically. Cut out hours of manual reading with parallel batch scoring.</div>
</div>
<div class="iq-mockup-box">
<div class="iq-funnel-step">
<div class="iq-funnel-left">
<span class="iq-funnel-icon">&#128229;</span>
<div>
<div class="iq-funnel-txt">150 Resumes Uploaded</div>
<div class="iq-funnel-sub">Bulk PDF &amp; Word files</div>
</div>
</div>
<span class="iq-funnel-badge">&#10003; Ingested</span>
</div>
<div class="iq-funnel-step">
<div class="iq-funnel-left">
<span class="iq-funnel-icon">&#9889;</span>
<div>
<div class="iq-funnel-txt">AI Semantic Evaluation</div>
<div class="iq-funnel-sub">Matched to job requirements</div>
</div>
</div>
<span class="iq-funnel-badge">Minutes</span>
</div>
<div class="iq-funnel-step">
<div class="iq-funnel-left">
<span class="iq-funnel-icon">&#127942;</span>
<div>
<div class="iq-funnel-txt">Top 5 Shortlisted</div>
<div class="iq-funnel-sub">Ranked &amp; interview-ready</div>
</div>
</div>
<span class="iq-funnel-badge iq-funnel-badge-green">Shortlist Ready</span>
</div>
<div class="iq-funnel-highlight">
&#9201; Hours of manual screening saved on every role
</div>
</div>
</div>

<div class="iq-bento-card">
<div>
<div class="iq-bento-tag">Objective Scorecards</div>
<div class="iq-bento-title">Visual Candidate Fit Breakdown</div>
<div class="iq-bento-sub">Intuitive visual ratings across core competencies, seniority depth, and qualification requirements.</div>
</div>
<div class="iq-mockup-box">
<div class="iq-gauge-row">
<div class="iq-gauge-info"><span>&#127919; Core Role Requirements</span><span style="color:#2563EB">96% Match</span></div>
<div class="iq-gauge-track"><div class="iq-gauge-bar" style="width:96%; background:#2563EB"></div></div>
</div>
<div class="iq-gauge-row">
<div class="iq-gauge-info"><span>&#128188; Experience Depth</span><span style="color:#6366F1">92% Match</span></div>
<div class="iq-gauge-track"><div class="iq-gauge-bar" style="width:92%; background:#6366F1"></div></div>
</div>
<div class="iq-gauge-row">
<div class="iq-gauge-info"><span>&#127891; Qualifications &amp; Background</span><span style="color:#10B981">88% Match</span></div>
<div class="iq-gauge-track"><div class="iq-gauge-bar" style="width:88%; background:#10B981"></div></div>
</div>
<div class="iq-gauge-row">
<div class="iq-gauge-info"><span>&#11088; Overall Recruiter Rating</span><span style="color:#8B5CF6">94% (Strong Match)</span></div>
<div class="iq-gauge-track"><div class="iq-gauge-bar" style="width:94%; background:#8B5CF6"></div></div>
</div>
</div>
</div>

<div class="iq-bento-card">
<div>
<div class="iq-bento-tag">Ranked Shortlist</div>
<div class="iq-bento-title">Top Talent Leaderboard</div>
<div class="iq-bento-sub">Surfaces your best applicants with medals, match percentages, and clear hiring recommendations.</div>
</div>
<div class="iq-mockup-box">
<div class="iq-cand-mini-row">
<div class="iq-cand-mini-left">
<span class="iq-medal">&#129351;</span>
<div>
<div class="iq-cand-mini-name">Alex Chen</div>
<div class="iq-cand-mini-role">8+ yrs &bull; Senior Lead</div>
</div>
</div>
<span class="iq-score-pill iq-score-pill-green">94% Match</span>
</div>
<div class="iq-cand-mini-row">
<div class="iq-cand-mini-left">
<span class="iq-medal">&#129352;</span>
<div>
<div class="iq-cand-mini-name">Maria Santos</div>
<div class="iq-cand-mini-role">5+ yrs &bull; Lead Specialist</div>
</div>
</div>
<span class="iq-score-pill iq-score-pill-green">89% Match</span>
</div>
<div class="iq-cand-mini-row">
<div class="iq-cand-mini-left">
<span class="iq-medal">&#129353;</span>
<div>
<div class="iq-cand-mini-name">Siddharth Rao</div>
<div class="iq-cand-mini-role">4+ yrs &bull; Project Consultant</div>
</div>
</div>
<span class="iq-score-pill iq-score-pill-blue">78% Match</span>
</div>
</div>
</div>

<div class="iq-bento-card">
<div>
<div class="iq-bento-tag">Client &amp; Manager Reports</div>
<div class="iq-bento-title">Executive Shortlist Reports</div>
<div class="iq-bento-sub">Export interview-ready candidate reports formatted with scores, strengths, concerns, and your recruiter decisions.</div>
</div>
<div class="iq-mockup-box">
<div class="iq-excel-preview">
<div class="iq-excel-hdr-row">
<span>#</span><span>Candidate</span><span>Score</span><span>Recommendation</span>
</div>
<div class="iq-excel-data-row">
<span>1</span><span>Alex Chen</span><span style="font-weight:700;color:#10B981">94%</span><span>Highly Recommended</span>
</div>
<div class="iq-excel-data-row">
<span>2</span><span>Maria Santos</span><span style="font-weight:700;color:#10B981">89%</span><span>Recommend Screen</span>
</div>
<div class="iq-excel-data-row">
<span>3</span><span>Siddharth Rao</span><span style="font-weight:700;color:#2563EB">78%</span><span>Consider / Interview</span>
</div>
</div>
<div class="iq-excel-footer">
<span>&#128196; Shortlist_Candidate_Report.xlsx</span>
<span class="iq-dl-badge">&#10515; Ready</span>
</div>
</div>
</div>
</div>

<div class="iq-pillars-box">
<div class="iq-pillars-top">
<div style="font-size:.72rem;font-weight:800;color:#2563EB;letter-spacing:.12em;text-transform:uppercase;margin-bottom:.4rem;">Built for High-Volume Hiring</div>
<div style="font-size:1.55rem;font-weight:900;color:#0F172A;letter-spacing:-.5px;">Why Recruiters Choose RankCV</div>
<div style="font-size:.86rem;color:#64748B;margin-top:.25rem;">Speed up time-to-shortlist while maintaining strict candidate evaluation quality</div>
</div>
<div class="iq-pillars-grid">
<div class="iq-pillar-item">
<div class="iq-pillar-stat">Minutes</div>
<div class="iq-pillar-title">Not Days</div>
<div class="iq-pillar-desc">Cut CV screening from days of manual reading to minutes with parallel batch parsing and automated scoring.</div>
</div>
<div class="iq-pillar-item">
<div class="iq-pillar-stat">0&ndash;100</div>
<div class="iq-pillar-title">Explained Scores</div>
<div class="iq-pillar-desc">Every score comes with strengths and concerns, so recruiters can see why a candidate ranked where they did.</div>
</div>
<div class="iq-pillar-item">
<div class="iq-pillar-stat">Excel</div>
<div class="iq-pillar-title">Works Beside Your ATS</div>
<div class="iq-pillar-desc">No integration needed. Upload a batch, rank it, and export the shortlist to Excel for your ATS.</div>
</div>
</div>
</div>
</div>
""")


# ─────────────────────────── Testimonials ────────────────────────────────────
render_html("""
<div class="iq-ts-sec">
<div style="text-align:center;padding:0 1rem;">
<div class="iq-ts-h">Reviews &amp; Testimonials</div>
<div class="iq-ts-s">Early feedback from recruiters and HR leads testing our pre-launch pilot</div>
</div>
<div class="iq-ts-track-wrap">
<div class="iq-ts-track">

<div class="iq-beta-card">
<div class="iq-beta-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
<div class="iq-beta-text">&ldquo;Tested the pilot on 15 resumes for an engineering role. The top 3 ranked candidates were spot on and it saved me an hour of manual skimming.&rdquo;</div>
<div class="iq-tp">
<div>
<div class="iq-tpn">Verified Beta Reviewer</div>
<div class="iq-tpc">Technical Recruitment Agency</div>
</div>
</div>
</div>

<div class="iq-beta-card">
<div class="iq-beta-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
<div class="iq-beta-text">&ldquo;The strengths and concerns breakdown cuts out the fluff. Really helpful when evaluating a quick batch of applicants on a busy Friday.&rdquo;</div>
<div class="iq-tp">
<div>
<div class="iq-tpn">Early Access Partner</div>
<div class="iq-tpc">Fast-Growth Tech Team</div>
</div>
</div>
</div>

<div class="iq-beta-card">
<div class="iq-beta-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
<div class="iq-beta-text">&ldquo;Super straightforward. Uploaded CVs, got instant match scores, and downloaded the shortlist report in seconds. Clean, objective, and fast.&rdquo;</div>
<div class="iq-tp">
<div>
<div class="iq-tpn">Verified Pilot User</div>
<div class="iq-tpc">Executive Staffing Firm</div>
</div>
</div>
</div>

<div class="iq-beta-card">
<div class="iq-beta-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
<div class="iq-beta-text">&ldquo;Saved our hiring team roughly 12 hours during our first week screening for two open positions. The candidate fit ranking is remarkably accurate.&rdquo;</div>
<div class="iq-tp">
<div>
<div class="iq-tpn">Early Access Reviewer</div>
<div class="iq-tpc">People &amp; Talent Operations</div>
</div>
</div>
</div>

<div class="iq-beta-card">
<div class="iq-beta-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
<div class="iq-beta-text">&ldquo;Works seamlessly beside our existing hiring stack. Just dropped in the resume files, ran the screening, and had interview-ready summaries in seconds.&rdquo;</div>
<div class="iq-tp">
<div>
<div class="iq-tpn">Verified Beta Partner</div>
<div class="iq-tpc">High-Volume Hiring Agency</div>
</div>
</div>
</div>

<div class="iq-beta-card">
<div class="iq-beta-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
<div class="iq-beta-text">&ldquo;The objective scorecard gives us complete confidence that we aren&rsquo;t overlooking top candidates due to keyword variations. Truly impressive matching.&rdquo;</div>
<div class="iq-tp">
<div>
<div class="iq-tpn">Verified Pilot Reviewer</div>
<div class="iq-tpc">Recruitment Operations Group</div>
</div>
</div>
</div>

<!-- Duplicate for infinite seamless scroll -->
<div class="iq-beta-card">
<div class="iq-beta-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
<div class="iq-beta-text">&ldquo;Tested the pilot on 15 resumes for an engineering role. The top 3 ranked candidates were spot on and it saved me an hour of manual skimming.&rdquo;</div>
<div class="iq-tp">
<div>
<div class="iq-tpn">Verified Beta Reviewer</div>
<div class="iq-tpc">Technical Recruitment Agency</div>
</div>
</div>
</div>

<div class="iq-beta-card">
<div class="iq-beta-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
<div class="iq-beta-text">&ldquo;The strengths and concerns breakdown cuts out the fluff. Really helpful when evaluating a quick batch of applicants on a busy Friday.&rdquo;</div>
<div class="iq-tp">
<div>
<div class="iq-tpn">Early Access Partner</div>
<div class="iq-tpc">Fast-Growth Tech Team</div>
</div>
</div>
</div>

<div class="iq-beta-card">
<div class="iq-beta-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
<div class="iq-beta-text">&ldquo;Super straightforward. Uploaded CVs, got instant match scores, and downloaded the shortlist report in seconds. Clean, objective, and fast.&rdquo;</div>
<div class="iq-tp">
<div>
<div class="iq-tpn">Verified Pilot User</div>
<div class="iq-tpc">Executive Staffing Firm</div>
</div>
</div>
</div>

<div class="iq-beta-card">
<div class="iq-beta-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
<div class="iq-beta-text">&ldquo;Saved our hiring team roughly 12 hours during our first week screening for two open positions. The candidate fit ranking is remarkably accurate.&rdquo;</div>
<div class="iq-tp">
<div>
<div class="iq-tpn">Early Access Reviewer</div>
<div class="iq-tpc">People &amp; Talent Operations</div>
</div>
</div>
</div>

<div class="iq-beta-card">
<div class="iq-beta-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
<div class="iq-beta-text">&ldquo;Works seamlessly beside our existing hiring stack. Just dropped in the resume files, ran the screening, and had interview-ready summaries in seconds.&rdquo;</div>
<div class="iq-tp">
<div>
<div class="iq-tpn">Verified Beta Partner</div>
<div class="iq-tpc">High-Volume Hiring Agency</div>
</div>
</div>
</div>

<div class="iq-beta-card">
<div class="iq-beta-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
<div class="iq-beta-text">&ldquo;The objective scorecard gives us complete confidence that we aren&rsquo;t overlooking top candidates due to keyword variations. Truly impressive matching.&rdquo;</div>
<div class="iq-tp">
<div>
<div class="iq-tpn">Verified Pilot Reviewer</div>
<div class="iq-tpc">Recruitment Operations Group</div>
</div>
</div>
</div>

</div>
</div>
</div>
""")


# ─────────────────────────── Pricing & Payment ────────────────────────────────
def _checkout_url(base: str) -> str:
    """Pre-fill the signed-in email on Stripe Checkout so the plan links to this account."""
    email = st.session_state.client_auth.get("contact_email", "") if st.session_state.client_auth.get("logged_in") else ""
    if not email or not base.startswith("https://buy.stripe.com/"):
        return base
    from urllib.parse import quote
    return f"{base}{'&' if '?' in base else '?'}prefilled_email={quote(email)}"


_stripe_pro_url = _checkout_url(config.STRIPE_PRO_URL)
_stripe_agency_url = _checkout_url(config.STRIPE_AGENCY_URL)
_PRO_Q, _AG_Q = config.PLAN_QUOTAS["pro"], config.PLAN_QUOTAS["agency"]
_PRO_P, _AG_P = config.PLAN_PRICES_GBP["pro"], config.PLAN_PRICES_GBP["agency"]

render_html(f"""
<div id="pricing" class="iq-price-sec">
  <div class="iq-price-hdr">
    <div class="iq-price-eye">Transparent Pricing</div>
    <div class="iq-price-h2">Simple Plans for Fast-Moving Hiring Teams</div>
    <div class="iq-price-sub">Instant activation. Cancel anytime. Human-review workflow and UK GDPR audit sheet included in every plan.</div>
  </div>

  <div class="iq-price-grid">
    <!-- Plan 1: Professional -->
    <div class="iq-plan-card">
      <div>
        <span class="iq-plan-badge iq-badge-starter">Boutique &amp; In-House</span>
        <div class="iq-plan-name">Professional</div>
        <div class="iq-plan-desc">Plug-and-play AI screening for in-house recruiters &amp; boutique teams.</div>
        <div class="iq-plan-price-row">
          <div class="iq-plan-price-wrap">
            <span class="iq-plan-curr">&pound;</span>
            <span class="iq-plan-amt">{_PRO_P}</span>
            <span class="iq-plan-period">/ month</span>
          </div>
          <div class="iq-plan-annual-sub">Billed monthly &bull; cancel anytime</div>
        </div>
        <ul class="iq-plan-features">
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>{_PRO_Q:,} CVs per month</b> (up to {config.MAX_BATCH_CVS} per batch)</span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>Cloud AI or Private Engine</b> &mdash; optional own OpenAI key</span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>Top candidate podium</b> &amp; Excel shortlist report</span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>UK GDPR Article 22</b> review workflow &amp; audit sheet</span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>Standard email support</b> &amp; instant activation</span></li>
        </ul>
      </div>
      <div>
        <a class="iq-plan-btn iq-btn-primary" href="{_e(_stripe_pro_url)}" target="_blank" rel="noopener">
          Subscribe to Pro &nbsp;&rarr;
        </a>
        <div class="iq-guarantee">&#128274; {_TRIAL_Q} CV free trial first &bull; Cancel anytime</div>
      </div>
    </div>

    <!-- Plan 2: Agency -->
    <div class="iq-plan-card featured">
      <div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.55rem;">
          <span class="iq-plan-badge iq-badge-agency">&#9733; Agency &amp; Scale-up</span>
          <span style="font-size:.62rem;font-weight:800;color:#2563EB;background:#EFF6FF;border:1px solid #BFDBFE;padding:.15rem .45rem;border-radius:5px;">FOUNDING LOCK</span>
        </div>
        <div class="iq-plan-name">Agency</div>
        <div class="iq-plan-desc">High-volume screening for staffing firms &amp; agencies.</div>
        <div class="iq-plan-price-row">
          <div class="iq-plan-price-wrap">
            <span class="iq-plan-curr">&pound;</span>
            <span class="iq-plan-amt">{_AG_P}</span>
            <span class="iq-plan-period">/ month</span>
          </div>
          <div class="iq-plan-annual-sub">Billed monthly &bull; cancel anytime</div>
        </div>
        <ul class="iq-plan-features">
          <li class="iq-plan-feat-item"><span class="iq-feat-icon-gold">&#9889;</span><span><b>{_AG_Q:,} CVs per month</b> (up to {config.MAX_BATCH_CVS} per batch)</span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>Everything in Professional</b> included</span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>Excel export</b> ready to import into any ATS</span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>Use your own OpenAI account</b> (optional)</span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>Priority email support</b> &amp; 1 guided setup session</span></li>
        </ul>
      </div>
      <div>
        <a class="iq-plan-btn iq-btn-agency" href="{_e(_stripe_agency_url)}" target="_blank" rel="noopener">
          Subscribe to Agency &nbsp;&rarr;
        </a>
        <div class="iq-guarantee">&#128274; First 20 customers lock this price for 12 months</div>
      </div>
    </div>
  </div>

  <!-- Supporting terms -->
  <div class="iq-terms-grid">
    <div class="iq-term-item">
      <div class="iq-term-title">&#10024; Free Trial</div>
      <div class="iq-term-desc">{_TRIAL_Q} CV evaluations, no card needed. Full scoring &amp; audit reports.</div>
    </div>
    <div class="iq-term-item">
      <div class="iq-term-title">&#128273; Instant Activation</div>
      <div class="iq-term-desc">Subscribe with your work email, then sign in with the same email &mdash; your plan applies automatically.</div>
    </div>
    <div class="iq-term-item">
      <div class="iq-term-title">&#128200; Monthly Quota</div>
      <div class="iq-term-desc">Your CV allowance resets each billing period. Screening pauses at your limit; upgrade any time.</div>
    </div>
    <div class="iq-term-item">
      <div class="iq-term-title">&#128274; Founding Lock</div>
      <div class="iq-term-desc">The first 20 customers keep their subscription price for 12 months.</div>
    </div>
  </div>

  <!-- Trust & Payment Methods Footer -->
  <div class="iq-pay-badges">
    <span style="font-size:.82rem;font-weight:700;color:#64748B;margin-right:.5rem;">Accepted Payment Methods:</span>
    <span class="iq-pay-pill"><svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" style="margin-right:2px"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M15.97 6.37c.62-.75 1.04-1.8 0.92-2.85-.9.04-2 .6-2.65 1.35-.58.66-1.08 1.74-.95 2.76.99.08 2.04-.51 2.68-1.26z"/></svg>Apple Pay</span>
    <span class="iq-pay-pill" style="font-weight:800;color:#1A1F71">VISA</span>
    <span class="iq-pay-pill"><span style="color:#EB001B">&#9679;</span><span style="color:#F79E1B;margin-left:-4px">&#9679;</span> Mastercard</span>
    <span class="iq-pay-pill">UK Debit Cards</span>
    <span class="iq-pay-pill" style="color:#6366F1;font-weight:800;">&#128274; Secure payments by Stripe</span>
  </div>
</div>
""")


# ─────────────────────────── FAQ ─────────────────────────────────────────────
_FAQ_ARROW = ('<svg class="iq-faq-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" '
              'stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>')


def _faq(question: str, answer_html: str) -> str:
    return (f'<details class="iq-faq-item"><summary class="iq-faq-summary"><span>{question}</span>{_FAQ_ARROW}'
            f'</summary><div class="iq-faq-body">{answer_html}</div></details>')


_faq_items = [
    ("What is included in the free trial?",
     f"Sign in with your work email to screen <b>{_TRIAL_Q} candidate CVs free&mdash;no credit card required</b>. "
     "You get 0&ndash;100 match scores, strengths &amp; concerns for every candidate, the recruiter review workflow, "
     "and the Excel shortlist report with its UK GDPR audit sheet."),
    ("What are the plan limits?",
     f"<b>Professional</b> includes <b>{_PRO_Q:,} CVs per month</b> and <b>Agency</b> includes <b>{_AG_Q:,} CVs per month</b>, "
     f"screened in batches of up to {config.MAX_BATCH_CVS}. Your allowance resets at the start of each billing period. "
     "When you reach it, screening pauses until the next period or until you upgrade. Only CVs that are actually "
     "scored count towards your allowance."),
    ("How do I subscribe, cancel or change plan?",
     "Choose a plan above and pay through Stripe using your work email. Then sign in to RankCV with that same email "
     "and your plan is applied automatically. You can update your card, switch plans or cancel at any time from the "
     "billing portal (<i>Manage billing</i> once you're signed in); cancellations take effect at the end of the paid month."),
    ("What is the Founding Customer price guarantee?",
     "The <b>first 20 customers</b> who subscribe to either Professional or Agency keep their introductory "
     "subscription price for a full <b>12 months</b>."),
    ("Where does my candidate data go?",
     "Uploaded files are saved to a private temporary folder on our server under random names and <b>deleted as soon "
     "as their text has been extracted</b>. Screening results stay in your browser session's memory so you can review "
     "them; they are never written to our database and are discarded when your session ends.<br><br>"
     "In <b>Cloud AI</b> mode, CV text is sent to OpenAI's API (United States) after names, contact details, postcodes, "
     "personal links, dates of birth and common protected-characteristic fields are redacted automatically. Under "
     "OpenAI's API terms this data is not used to train models and is kept for up to 30 days for abuse monitoring. "
     "In <b>Private Engine</b> mode no CV content leaves our server. You can also use your own OpenAI key. "
     "See our <a href=\"?page=privacy\" target=\"_self\">Privacy Notice</a> and "
     "<a href=\"?page=subprocessors\" target=\"_self\">sub-processors</a>."),
    ("Does RankCV integrate with my ATS?",
     "RankCV works alongside your ATS: upload a batch, review the ranking, and export the shortlist to Excel, which "
     "most ATS and CRM tools can import. Direct integrations are not available yet."),
    ("How does RankCV help hiring teams comply with UK GDPR?",
     "RankCV is a <b>decision-support tool</b>:"
     '<ul style="margin:0.5rem 0 0.5rem 1.2rem; padding:0; line-height:1.6;">'
     "<li><b>Article 22 human review:</b> no candidate is rejected automatically. Every candidate starts as "
     "<i>Under Review</i> and recruiters record each decision, score adjustment and note.</li>"
     "<li><b>Data minimisation:</b> automatic, best-effort redaction of identifying details before Cloud AI scoring, "
     "or the Private Engine with no external AI at all.</li>"
     "<li><b>Storage limitation:</b> CV files are deleted after each run and results are not stored in our database.</li>"
     "<li><b>Accountability:</b> the Excel report records which engine scored each CV and which decisions a recruiter "
     "actually made, with timestamps.</li>"
     "<li><b>Processor terms:</b> our <a href=\"?page=dpa\" target=\"_self\">Data Processing Agreement</a> applies to every account.</li>"
     "</ul>"),
    ("How fast is the batch screening process?",
     "The Private Engine scores a batch in seconds. Cloud AI scores CVs in parallel batches of about ten; a batch of "
     "50 CVs typically takes around a minute, depending on OpenAI's response times."),
]

render_html(f"""
<div id="faq" class="iq-faq-sec">
<div class="iq-faq-hdr">
<div class="iq-faq-eye">Frequently Asked Questions</div>
<div class="iq-faq-h2">Got Questions? We&rsquo;ve Got Answers</div>
<div class="iq-faq-sub">Everything you need to know about plans, CV limits, candidate data privacy, and UK GDPR Article 22.</div>
</div>
<div class="iq-faq-list">
{"".join(_faq(q, a) for q, a in _faq_items)}
</div>
</div>
""")


_render_footer()


# ─────────────────────────── Session cookie writer ───────────────────────────
_cw = st.session_state.pop("cookie_write", None)
if _cw is not None:
    _token, _max_age = _cw
    try:
        st.html(
            "<script>document.cookie = " + json.dumps(f"{_SESSION_COOKIE}=") + " + " + json.dumps(_token)
            + f' + "; Max-Age={int(_max_age)}; Path=/; SameSite=Strict"'
            + ' + (location.protocol === "https:" ? "; Secure" : "");</script>',
            unsafe_allow_javascript=True,
        )
    except TypeError:
        log.warning("This Streamlit version can't run scripts in st.html; sign-in won't persist across refreshes")
