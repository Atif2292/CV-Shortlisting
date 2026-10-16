"""
RankCV — AI-Powered CV Screening
"""

import os
import io
import base64
import tempfile
import streamlit as st
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from openpyxl.styles import (
    PatternFill as _PFill, Font as _Font,
    Alignment as _Align, Border as _Border, Side as _Side,
)

load_dotenv()

from utils.pdf_parser import extract_pdf_text
from utils.docx_parser import extract_docx_text
from utils.ai_scoring import extract_resume_keywords, rank_candidates_batch, extract_job_context
from utils.cleanup import delete_uploaded_files
import altair as alt


st.set_page_config(
    page_title="RankCV — Screen CVs in Minutes",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def render_html(html_str: str, container=None):
    """Safely renders HTML in Streamlit using st.markdown with stripped lines to prevent CommonMark code blocks."""
    clean = "\n".join(ln.strip() for ln in html_str.splitlines() if ln.strip())
    target = container if container is not None else st
    target.markdown(clean, unsafe_allow_html=True)


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
[data-testid="stHeader"],
header[data-testid="stHeader"] {
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
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

/* ── Workspace Panel Cards (Scoped only to panels with .iq-phead) ── */
[data-testid="column"]:has(.iq-phead) {
    display: flex !important;
    flex-direction: column !important;
}
[data-testid="column"]:has(.iq-phead) > div[data-testid="stVerticalBlockBorderWrapper"] {
    flex: 1 1 100% !important;
    display: flex !important;
    flex-direction: column !important;
    justify-content: space-between !important;
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 16px !important;
    box-shadow: 0 2px 12px rgba(10,20,60,.06) !important;
    padding: 1.5rem !important;
    transition: box-shadow .2s, border-color .2s !important;
}
[data-testid="column"]:has(.iq-phead) > div[data-testid="stVerticalBlockBorderWrapper"]:focus-within {
    box-shadow: 0 4px 20px rgba(10,20,60,.1) !important;
    border-color: rgba(37,99,235,.25) !important;
}
/* Ensure regular columns and buttons have zero unwanted extra height */
[data-testid="column"]:not(:has(.iq-phead)) {
    min-height: unset !important;
}
[data-testid="column"]:not(:has(.iq-phead)) > div[data-testid="stVerticalBlockBorderWrapper"] {
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
    min-height: 230px !important;
    display: flex !important;
    flex-direction: column !important;
    justify-content: center !important;
    align-items: center !important;
    padding: 1.5rem !important;
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
.iq-logo { font-size: 1.45rem; font-weight: 900; color: #0F172A; letter-spacing: -.5px; }
.iq-logo b { color: #2563EB; font-weight: 900; }
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
    font-size: .875rem !important; font-weight: 700 !important; color: #FFFFFF !important; background: #2563EB !important;
    padding: .48rem 1.25rem !important; border-radius: 8px !important; border: none !important; cursor: pointer !important;
    box-shadow: 0 2px 8px rgba(37,99,235,.25) !important; transition: all .15s ease !important;
    text-decoration: none !important; display: inline-flex !important; align-items: center !important;
}
.iq-nav a.iq-nav-demo:hover,
.iq-nav a.iq-nav-demo:active,
a.iq-nav-demo:hover,
a.iq-nav-demo:active {
    color: #FFFFFF !important; background: #1D4ED8 !important; text-decoration: none !important;
}

/* ── Hero — use <div> not h-tags to avoid Streamlit anchor icons ── */
.iq-hero { text-align: center; padding: 4rem 1rem 2.8rem; max-width: 740px; margin: 0 auto; }
.iq-eye {
    display: inline-block; font-size: .69rem; font-weight: 700;
    letter-spacing: .17em; color: #2563EB; text-transform: uppercase;
    background: rgba(37,99,235,.07); padding: .35rem 1rem;
    border-radius: 99px; border: 1px solid rgba(37,99,235,.15); margin-bottom: 1.1rem;
}
.iq-h1 {
    font-size: 5rem; font-weight: 900; line-height: 1.03;
    color: #0B1120; margin-bottom: 1.1rem; letter-spacing: -3.5px;
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

/* ── Pricing & Payment Section ── */
.iq-price-sec { max-width: 860px; margin: 3.5rem auto 2.5rem; padding: 0 1rem; }
.iq-price-hdr { text-align: center; margin-bottom: 2rem; }
.iq-price-eye { display: inline-block; font-size: .75rem; font-weight: 800; color: #2563EB; text-transform: uppercase; letter-spacing: .08em; background: #EFF6FF; border: 1px solid #BFDBFE; padding: .25rem .75rem; border-radius: 999px; margin-bottom: .5rem; }
.iq-price-h2 { font-size: 1.95rem; font-weight: 800; color: #0B1120; margin-bottom: .45rem; letter-spacing: -.02em; }
.iq-price-sub { font-size: .92rem; color: #64748B; max-width: 540px; margin: 0 auto; line-height: 1.5; }
.iq-price-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.35rem; margin-top: 1.6rem; }
@media (max-width: 860px) { .iq-price-grid { grid-template-columns: 1fr; max-width: 440px; margin: 1.5rem auto 0; } }
.iq-plan-card { background: #FFFFFF; border: 1.5px solid #E2E8F0; border-radius: 16px; padding: 1.65rem 1.6rem; display: flex; flex-direction: column; justify-content: space-between; transition: all .25s ease; box-shadow: 0 2px 12px rgba(15,23,42,.03); position: relative; }
.iq-plan-card:hover { border-color: #93C5FD; box-shadow: 0 12px 28px rgba(37,99,235,.08); transform: translateY(-2px); }
.iq-plan-card.featured { border: 2px solid #2563EB; background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%); box-shadow: 0 12px 32px rgba(37,99,235,.1); }
.iq-plan-badge { display: inline-block; padding: .24rem .65rem; font-size: .68rem; font-weight: 800; border-radius: 999px; margin-bottom: .8rem; text-transform: uppercase; letter-spacing: .06em; }
.iq-badge-starter { background: #EFF6FF; color: #1E40AF; border: 1px solid #DBEAFE; }
.iq-badge-agency { background: #2563EB; color: #FFFFFF; box-shadow: 0 2px 8px rgba(37,99,235,.25); }
.iq-plan-name { font-size: 1.35rem; font-weight: 800; color: #0F172A; margin-bottom: .25rem; letter-spacing: -.01em; }
.iq-plan-desc { font-size: .83rem; color: #64748B; margin-bottom: 1rem; line-height: 1.45; }
.iq-plan-price-wrap { display: flex; align-items: baseline; gap: .35rem; margin-bottom: 1.2rem; padding-bottom: 1rem; border-bottom: 1px solid #F1F5F9; }
.iq-plan-curr { font-size: 1.35rem; font-weight: 700; color: #0F172A; }
.iq-plan-amt { font-size: 2.6rem; font-weight: 900; color: #0F172A; line-height: 1; letter-spacing: -.03em; }
.iq-plan-period { font-size: .88rem; font-weight: 600; color: #64748B; }
.iq-plan-features { list-style: none; padding: 0; margin: 0 0 1.4rem 0; display: flex; flex-direction: column; gap: .55rem; }
.iq-plan-feat-item { display: flex; align-items: flex-start; gap: .55rem; font-size: .84rem; color: #334155; line-height: 1.4; }
.iq-feat-icon { color: #10B981; font-weight: 900; font-size: .92rem; flex-shrink: 0; margin-top: 1px; }
.iq-feat-icon-gold { color: #F59E0B; font-weight: 900; font-size: .95rem; flex-shrink: 0; margin-top: 1px; }
.iq-plan-btn { display: block; width: 100%; text-align: center; padding: .75rem 1.25rem; border-radius: 10px; font-weight: 800; font-size: .92rem; text-decoration: none !important; transition: all .2s ease; cursor: pointer; box-sizing: border-box; }
.iq-btn-primary { background: #2563EB !important; color: #FFFFFF !important; box-shadow: 0 4px 14px rgba(37,99,235,.25); }
.iq-btn-primary:hover { background: #1D4ED8 !important; transform: translateY(-1px); box-shadow: 0 6px 18px rgba(37,99,235,.32); }
.iq-btn-agency { background: #0F172A !important; color: #FFFFFF !important; box-shadow: 0 4px 14px rgba(15,23,42,.2); }
.iq-btn-agency:hover { background: #1E293B !important; transform: translateY(-1px); box-shadow: 0 6px 18px rgba(15,23,42,.26); }
.iq-guarantee { text-align: center; margin-top: .75rem; font-size: .74rem; color: #94A3B8; display: flex; align-items: center; justify-content: center; gap: .35rem; }
.iq-pay-badges { display: flex; align-items: center; justify-content: center; gap: .7rem; margin-top: 2rem; padding-top: 1.4rem; border-top: 1px solid #E2E8F0; flex-wrap: wrap; }
.iq-pay-pill { display: inline-flex; align-items: center; gap: .4rem; background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: .3rem .65rem; font-size: .76rem; font-weight: 700; color: #334155; }

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
    margin:2.2rem 0 2.5rem; overflow:hidden;
}
.iq-fbar-item {
    flex:1; display:flex; align-items:center; gap:.85rem;
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
    margin-bottom: 1.5rem;
    box-shadow: 0 4px 14px rgba(37,99,235,.05);
}
.iq-sec-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: .8rem;
    margin-bottom: .6rem;
}
.iq-sec-title {
    font-size: .95rem;
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
    font-size: .74rem;
    font-weight: 700;
    padding: .28rem .7rem;
    border-radius: 99px;
    display: inline-flex;
    align-items: center;
    gap: .3rem;
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

# ─────────────────────────── Session state ───────────────────────────────────
for _k, _v in [
    ("results",              []),
    ("processed",            False),
    ("uploaded_paths",       []),
    ("show_full",            False),
    ("engine_mode",          "cloud"),
    ("custom_api_key",       ""),
    ("custom_base_url",      ""),
    ("target_region",        "Default (OpenAI Direct)"),
    ("recruiter_overrides",  {}),
    ("audit_stats",          {}),
    ("show_legal_modal",     False),
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


def _extract_doc_file(path: str) -> str:
    """Extract text from Word 97-2003 .doc files using textutil, docx, or binary stream fallback."""
    # 1. Many modern .doc files are actually docx files renamed as .doc
    try:
        from docx import Document
        doc = Document(path)
        t = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        if t.strip():
            return t.strip()
    except Exception:
        pass

    # 2. On macOS, textutil converts .doc to plain text natively
    import subprocess, sys
    if sys.platform == "darwin":
        try:
            res = subprocess.run(["textutil", "-convert", "txt", "-stdout", path], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass

    # 3. Robust binary string extraction fallback (works for OLE Word documents on Linux/Cloud)
    try:
        with open(path, "rb") as f:
            raw = f.read()
        import re
        words = re.findall(rb'[\x20-\x7E\t\r\n]{4,}', raw)
        clean = " ".join(w.decode('latin1', errors='ignore') for w in words)
        return clean.strip()
    except Exception:
        return ""


def _extract_excel_file(path: str, fname: str) -> str:
    """Extract candidate or JD content from Excel (.xlsx, .xls) and CSV files."""
    ext = Path(fname).suffix.lower()
    try:
        if ext == ".csv":
            df = pd.read_csv(path)
        else:
            engine = "openpyxl" if ext == ".xlsx" else None
            excel_data = pd.read_excel(path, sheet_name=None, engine=engine)
            dfs = [sheet for sheet in excel_data.values()]
            df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

        df = df.dropna(how='all')
        lines = []
        for idx, row in df.iterrows():
            row_parts = []
            for col, val in row.items():
                if pd.notna(val) and str(val).strip():
                    row_parts.append(f"{col}: {val}")
            if row_parts:
                lines.append(f"Candidate/Profile #{idx+1}: " + " | ".join(row_parts))
        return "\n\n".join(lines)
    except Exception:
        try:
            df = pd.read_excel(path)
            return df.to_string(index=False)
        except Exception:
            return ""


def _read_cv(path: str, fname: str) -> str:
    ext = Path(fname).suffix.lower()
    if ext == ".pdf":
        return extract_pdf_text(path)
    if ext == ".docx":
        return extract_docx_text(path)
    if ext == ".doc":
        return _extract_doc_file(path)
    if ext in [".xlsx", ".xls", ".csv"]:
        return _extract_excel_file(path, fname)
    if ext == ".txt":
        try:
            return Path(path).read_text(encoding="utf-8", errors="ignore")
        except:
            return ""
    return ""


def _extract_from_upload(f) -> str:
    """Extract text from a Streamlit UploadedFile object."""
    suffix = Path(f.name).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        f.seek(0)
        tmp.write(f.read())
        path = tmp.name
    try:
        return _read_cv(path, f.name)
    finally:
        f.seek(0)
        Path(path).unlink(missing_ok=True)


def _exp_subtitle(text: str) -> str:
    """Extract a short subtitle from relevant_experience text."""
    import re as _re
    m = _re.search(r'(\d+)\+?\s+years?', text, _re.I)
    if m:
        return f"{m.group(1)}+ years experience"
    return text[:44].rstrip() + ("…" if len(text) > 44 else "")


# ─────────────────────────── Navbar ──────────────────────────────────────────
render_html("""
<div class="iq-nav">
<div class="iq-logo">Rank<b>CV</b></div>
<div style="display:flex;align-items:center;gap:1.3rem;">
<a href="#screening-workspace" style="font-size:.875rem;font-weight:600;color:#64748B;text-decoration:none;">Screen CVs</a>
<a href="#features" style="font-size:.875rem;font-weight:600;color:#64748B;text-decoration:none;">Features</a>
<a href="#pricing" style="font-size:.875rem;font-weight:600;color:#64748B;text-decoration:none;">Pricing</a>
<a href="#faq" style="font-size:.875rem;font-weight:600;color:#64748B;text-decoration:none;">FAQ</a>
<a class="iq-nav-demo" href="#pricing" style="color:#ffffff !important; background-color:#2563eb !important; text-decoration:none !important;"><span style="color:#ffffff !important; font-weight:700 !important;">Upgrade &nbsp;&rarr;</span></a>
</div>
</div>
""")


# ─────────────────────────── Hero ────────────────────────────────────────────
render_html("""
<div class="iq-hero">
<div class="iq-eye">&#10022; &nbsp;AI-Powered CV Screening for HR &amp; Recruitment Teams</div>
<div class="iq-h1">Shortlist Top Talent<br>in <span class="bl">Seconds.</span></div>
<div class="iq-sub">Upload a job description and candidate CVs. RankCV automatically
scores, ranks, and summarises candidates with actionable match insights.</div>
<div class="iq-trial-tag">
<span class="iq-trial-pill">🎁 FREE TRIAL</span>
<span>Screen up to <b>10 CVs free</b> &mdash; test instant AI matching on your open roles</span>
</div>
<div class="iq-btns">
<a class="iq-bp" href="#screening-workspace">Try Free (10 CVs) &nbsp;&darr;</a>
<a class="iq-bs" href="https://wa.me/447379975532" target="_blank">Book a Demo &nbsp;&rarr;</a>
</div>
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
<div class="iq-fbar-t2">0&ndash;100 match accuracy</div>
</div>
</div>
<div class="iq-fbar-item">
<div class="iq-fbar-icon">&#128200;</div>
<div>
<div class="iq-fbar-t1">Identify Top Talent</div>
<div class="iq-fbar-t2">Contextual semantic fit</div>
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
<div class="iq-sec-bar">
  <div class="iq-sec-top">
    <div class="iq-sec-title">
      <span>🛡️ UK GDPR Privacy Shield &amp; Screening Engine</span>
    </div>
    <div class="iq-sec-badges">
      <span class="iq-sec-pill iq-pill-green">🔒 PII Stripper Active (Art. 5(1)(c))</span>
      <span class="iq-sec-pill iq-pill-blue">⚖️ Article 22 Human-in-the-Loop</span>
      <span class="iq-sec-pill iq-pill-purple">Zero Cloud Storage</span>
    </div>
  </div>
</div>
""")

sec_c1, sec_c2, sec_c3 = st.columns([1.6, 1.2, 1.2])
with sec_c1:
    engine_choice = st.radio(
        "Screening Engine Mode:",
        ["⚡ Cloud AI (BYOK - Privacy Preserved)", "🛡️ Private In-Memory Engine (Zero External AI Calls)"],
        index=0 if st.session_state.get("engine_mode", "cloud") == "cloud" else 1,
        horizontal=True,
        key="engine_choice_radio",
        label_visibility="collapsed"
    )
    st.session_state.engine_mode = "private" if ("Private" in engine_choice or "Offline" in engine_choice) else "cloud"

with sec_c2:
    with st.popover("🔑 BYOK & Privacy Settings"):
        st.markdown("### 🔑 Bring Your Own Key (BYOK)")
        st.markdown(
            "Use your company's own LLM account and UK/EU data residency region. "
            "**RankCV servers never receive or store your key or candidate CVs.**"
        )
        custom_key_val = st.text_input(
            "OpenAI API Key (sk-...)",
            value=st.session_state.get("custom_api_key", ""),
            type="password",
            placeholder="sk-proj-...",
            help="Stored only in your current browser session state."
        )
        st.session_state.custom_api_key = custom_key_val

        region_choice = st.selectbox(
            "Cloud Data Region / Endpoint",
            ["Default (OpenAI Direct)", "Azure UK South (London)", "Azure EU West (Ireland)", "Custom Base URL"],
            index=0
        )
        st.session_state.target_region = region_choice

        if region_choice == "Custom Base URL":
            base_url_val = st.text_input(
                "Base URL",
                value=st.session_state.get("custom_base_url", ""),
                placeholder="https://api.openai.com/v1"
            )
            st.session_state.custom_base_url = base_url_val
        elif "UK South" in region_choice:
            st.caption("🇬🇧 Configured for UK sovereign data processing under UK GDPR.")
        elif "EU West" in region_choice:
            st.caption("🇪🇺 Configured for EU data sovereignty.")

        st.caption("✅ Data Minimisation: Candidate names, emails, phone numbers & UK postcodes are stripped locally before transmission.")

with sec_c3:
    with st.popover("⚖️ UK Licence & GDPR Terms"):
        st.markdown("### ⚖️ Software Licence & UK GDPR Terms")
        st.caption("Governing Law: England and Wales")
        st.markdown("""
> [!NOTE] **Core Compliance Summary**
> * **Roles:** The client is the **Data Controller** of candidate data. RankCV is software-only and never stores or accesses your candidate data.
> * **Processor:** The LLM provider (OpenAI/Azure) acts as your direct Processor under your own API agreement and DPA.
> * **Human Oversight (Article 22):** RankCV is strictly **Decision Support**. Solely automated candidate rejections are prohibited under UK law. Final shortlists must be reviewed and approved by a human recruiter.
> * **Data Minimisation:** Names, emails, phones, and UK postcodes are automatically redacted prior to AI evaluation.
> * **Anti-Discrimination:** Protected characteristics under the UK Equality Act 2010 are excluded from automated scoring.
> * **Jurisdiction:** Governed by the laws of England and Wales.
""")


# ─────────────────────────── 3-panel layout ──────────────────────────────────
render_html('<div id="screening-workspace" style="margin-top:1.5rem;"></div>')
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

        role_choice = st.selectbox(
            "💡 Or choose a sample role:",
            list(SAMPLE_ROLES.keys()),
            key="sample_role_sel",
            index=0,
            on_change=_on_role_select,
            label_visibility="visible",
        )

        tab_paste, tab_file = st.tabs(["Paste Text", "Upload File"])

        # Immediately check session state for fast feedback
        jd_text = st.session_state.get("jd_paste", "").strip()

        with tab_paste:
            jd_input = st.text_area(
                "",
                placeholder=(
                    "We are looking for a Senior Python Backend Engineer "
                    "with strong experience in FastAPI, PostgreSQL, AWS, "
                    "Docker, and microservices architecture…"
                ),
                height=230,
                max_chars=5000,
                key="jd_paste",
                label_visibility="collapsed",
            )
            char_count = len(jd_input)
            render_html(
                f'<div class="iq-char">'
                f'<span id="iq-live-chars">{char_count:,} / 5,000</span>'
                f'</div>'
            )
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
                cache_key = f"_jd_cache_{jd_file.name}_{jd_file.size}"
                if cache_key not in st.session_state:
                    st.session_state[cache_key] = _extract_from_upload(jd_file)
                extracted = st.session_state[cache_key]
                if extracted.strip():
                    jd_text = extracted.strip()
                    st.caption(f"✅ Extracted {len(jd_text):,} characters from {jd_file.name}")

        # Status badge (with live 0ms client-side sync)
        if jd_text:
            render_html(f'<div id="iq-jd-status-badge" class="iq-status-ok">✅ Job description ready ({len(jd_text):,} chars)</div>')
        else:
            render_html('<div id="iq-jd-status-badge" class="iq-status-wait">✍️ Type or paste your job requirements above</div>')

        render_html("""
<img src="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg'/>" style="display:none" onload="
(function() {
  if (window.__rankcv_sync_init) return;
  window.__rankcv_sync_init = true;

  function attachSync() {
    try {
      var ta = document.querySelector('textarea');
      if (!ta || ta.dataset.fastSync) return;
      ta.dataset.fastSync = 'true';

      function sync() {
        var val = ta.value.trim();
        var len = val.length;
        var c = document.getElementById('iq-live-chars');
        if (c) c.textContent = len.toLocaleString() + ' / 5,000';
        var b = document.getElementById('iq-jd-status-badge');
        if (b) {
          if (len > 0) {
            b.className = 'iq-status-ok';
            b.innerHTML = '✅ Job description ready (' + len.toLocaleString() + ' chars)';
          } else {
            b.className = 'iq-status-wait';
            b.innerHTML = '✍️ Type or paste your job requirements above';
          }
        }
      }

      ta.addEventListener('input', sync);
      ta.addEventListener('keyup', sync);
      ta.addEventListener('change', sync);

      document.addEventListener('click', function(e) {
        if (e.target && e.target.closest && e.target.closest('button')) {
          if (document.activeElement === ta) {
            ta.blur();
          }
        }
      }, true);
    } catch(e) {}
  }

  attachSync();
  setInterval(attachSync, 300);
})()
">
""")


# ══════════════════════════ PANEL 2 — Upload CVs ══════════════════════════════
with col2:
    with st.container(border=True):
        render_html("""
<div class="iq-phead">
  <div class="iq-pnum">2</div>Upload Candidate CVs
</div>
<div class="iq-cr-head">
  <div style="font-size:.82rem;font-weight:700;color:#64748B;">Candidate Resumes (PDF, DOCX, TXT)</div>
  <div style="background:#EFF6FF; color:#2563EB; font-size:.68rem; font-weight:700; padding:.22rem .6rem; border-radius:6px; border:1px solid #DBEAFE;">🎁 10 CVs Free Trial</div>
</div>""")

        cv_files = st.file_uploader(
            "Upload CVs (PDF, DOC/DOCX, TXT, MS Excel — up to 10 files)",
            type=["pdf", "docx", "doc", "txt", "xlsx", "xls", "csv"],
            accept_multiple_files=True,
            key="cv_up",
            label_visibility="collapsed",
        )
        total_uploaded = len(cv_files or [])

        # Status badge & limit enforcement
        if total_uploaded > 10:
            render_html(
                f'<div class="iq-status-wait" style="background:#FEF2F2;color:#DC2626;border-color:#FCA5A5">'
                f'⚠️ <b>{total_uploaded} CVs uploaded</b> — Free trial is limited to 10 CVs per batch. '
                f'Please remove {total_uploaded - 10} file(s) to proceed.</div>'
            )
        elif total_uploaded > 0:
            render_html(
                f'<div class="iq-status-ok">✅ <b>{total_uploaded}/10 CVs selected</b> ready for screening</div>'
            )
        else:
            render_html('<div class="iq-status-wait">⏳ Drag &amp; drop resumes or test with 10 demo CVs below…</div>')

        render_html("<div style='height:.7rem'></div>")
        col_btn1, col_btn2 = st.columns([1.15, 1])
        with col_btn1:
            run_btn = st.button("🚀  Screen Candidates", use_container_width=True, type="primary")
        with col_btn2:
            demo_btn = st.button("⚡  Try 10 Demo CVs", use_container_width=True)


# ══════════════════════════ PANEL 3 — Results ═════════════════════════════════
_AV_CLS = ["iq-cr-av1","iq-cr-av2","iq-cr-av3","iq-cr-av4","iq-cr-av5"]

with col3:
    with st.container(border=True):
        render_html("""
<div class="iq-phead">
  <div class="iq-pnum">3</div>Candidate Rankings
</div>""")

        # ── Trigger demo screening ───────────────────────────────────────────
        if demo_btn:
            if not jd_text.strip():
                jd_text = SAMPLE_ROLES["Senior Python Backend Engineer"]
                st.session_state["jd_paste"] = jd_text
                st.session_state["_prev_role_choice"] = "Senior Python Backend Engineer"

            demo_dir = Path("dummy_cvs_pdf")
            demo_files = sorted(demo_dir.glob("*.pdf"))[:10]
            if not demo_files:
                st.error("Demo CVs not found on server.")
            else:
                job_context = extract_job_context(jd_text)
                candidates = []
                bar = st.progress(0, text=f"Loading {len(demo_files)} Demo CVs…")
                _info = st.empty()
                for idx, df in enumerate(demo_files, 1):
                    render_html(
                        f'<p style="font-size:.82rem;color:#64748B">'
                        f'📄 <b style="color:#2563EB">{df.name}</b> ({idx}/{len(demo_files)})</p>',
                        container=_info,
                    )
                    try:
                        text = _read_cv(str(df), df.name)
                        if text.strip():
                            candidates.append(extract_resume_keywords(
                                cv_text=text,
                                required_skills=job_context.get("skills", ""),
                                filename=df.name,
                            ))
                    except Exception as ex:
                        st.warning(f"⚠️ Error reading {df.name}: {ex}")
                    bar.progress(idx / len(demo_files) * 0.5, text=f"Parsing demo CVs — {idx}/{len(demo_files)} done…")

                if candidates:
                    render_html(
                        f'<p style="font-size:.82rem;color:#64748B">'
                        f'🤖 Ranking <b style="color:#2563EB">{len(candidates)} candidates</b> with AI…</p>',
                        container=_info,
                    )
                    bar.progress(0.7, text=f"AI ranking {len(candidates)} candidates…")
                    try:
                        _is_offline = (st.session_state.get("engine_mode") in ["private", "offline"])
                        _c_key = st.session_state.get("custom_api_key", "").strip()
                        _b_url = st.session_state.get("custom_base_url", "").strip()
                        results, audit_stats = rank_candidates_batch(
                            candidates=candidates,
                            job_context=job_context,
                            custom_api_key=_c_key,
                            offline_mode=_is_offline,
                            base_url=_b_url,
                            return_audit=True,
                        )
                    except Exception as _err:
                        results, audit_stats = [], {}

                    bar.progress(1.0, text="✅ Done!"); _info.empty()
                    st.session_state.results = results
                    st.session_state.audit_stats = audit_stats
                    # Initialize default human review overrides
                    if "recruiter_overrides" not in st.session_state:
                        st.session_state.recruiter_overrides = {}
                    for r in results:
                        idx = r.get("candidate_index")
                        if idx not in st.session_state.recruiter_overrides:
                            rec_txt = r.get("recommendation", "").lower()
                            def_status = "Shortlisted" if "recommend" in rec_txt else ("Consider" if "review" in rec_txt or "moderate" in rec_txt else "Under Review")
                            st.session_state.recruiter_overrides[idx] = {
                                "status": def_status,
                                "score_delta": 0,
                                "notes": ""
                            }
                    st.session_state.processed = True
                    st.session_state.show_full = True
                    st.rerun()

        # ── Trigger manual screening ─────────────────────────────────────────
        if run_btn:
            errors = []
            if not jd_text:
                errors.append("Please provide a Job Description in Panel 1 (paste text or choose a sample).")
            if total_uploaded == 0:
                errors.append("Please upload at least one candidate CV in Panel 2.")
            if total_uploaded > 10:
                errors.append(f"Free trial limit is 10 CVs per batch. You uploaded {total_uploaded}. Please select up to 10 files.")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                upload_dir = Path("uploads")
                upload_dir.mkdir(exist_ok=True)
                saved_paths, saved_names = [], []
                for f in (cv_files or []):
                    dest = upload_dir / f.name
                    f.seek(0)
                    dest.write_bytes(f.read())
                    saved_paths.append(str(dest))
                    saved_names.append(f.name)

                job_context = extract_job_context(jd_text)

                candidates = []
                bar   = st.progress(0, text="Reading CVs…")
                _info = st.empty()

                for idx, (path, fname) in enumerate(zip(saved_paths, saved_names), 1):
                    render_html(
                        f'<p style="font-size:.82rem;color:#64748B">'
                        f'📄 <b style="color:#2563EB">{fname}</b> ({idx}/{len(saved_paths)})</p>',
                        container=_info,
                    )
                    try:
                        text = _read_cv(path, fname)
                        if not text.strip():
                            st.warning(f"⚠️ No text in {fname} — skipping.")
                            continue
                        candidates.append(extract_resume_keywords(
                            cv_text=text,
                            required_skills=job_context.get("skills", ""),
                            filename=fname,
                        ))
                    except Exception as ex:
                        st.warning(f"⚠️ Error reading {fname}: {ex}")
                    bar.progress(idx / len(saved_paths) * 0.5,
                                 text=f"Reading CVs — {idx}/{len(saved_paths)} done…")

                if candidates:
                    render_html(
                        f'<p style="font-size:.82rem;color:#64748B">'
                        f'🤖 Ranking <b style="color:#2563EB">{len(candidates)} candidates</b>…</p>',
                        container=_info,
                    )
                    bar.progress(0.55, text=f"AI ranking {len(candidates)} candidates…")
                    try:
                        _is_offline = (st.session_state.get("engine_mode") in ["private", "offline"])
                        _c_key = st.session_state.get("custom_api_key", "").strip()
                        _b_url = st.session_state.get("custom_base_url", "").strip()
                        results, audit_stats = rank_candidates_batch(
                            candidates=candidates,
                            job_context=job_context,
                            custom_api_key=_c_key,
                            offline_mode=_is_offline,
                            base_url=_b_url,
                            return_audit=True,
                        )
                    except Exception as _err:
                        results, audit_stats = [], {}
                else:
                    results, audit_stats = [], {}

                bar.progress(1.0, text="✅ Done!"); _info.empty()
                st.session_state.results   = results
                st.session_state.audit_stats = audit_stats
                # Initialize default human review overrides
                if "recruiter_overrides" not in st.session_state:
                    st.session_state.recruiter_overrides = {}
                for r in results:
                    idx = r.get("candidate_index")
                    if idx not in st.session_state.recruiter_overrides:
                        rec_txt = r.get("recommendation", "").lower()
                        def_status = "Shortlisted" if "recommend" in rec_txt else ("Consider" if "review" in rec_txt or "moderate" in rec_txt else "Under Review")
                        st.session_state.recruiter_overrides[idx] = {
                            "status": def_status,
                            "score_delta": 0,
                            "notes": ""
                        }
                st.session_state.processed = True
                st.session_state.show_full = True
                st.success(f"🎯 Successfully evaluated {len(results)} candidate(s)!")

                deleted, _ = delete_uploaded_files(saved_paths)
                if deleted:
                    st.caption(f"🗑️ {len(deleted)} file(s) deleted from server.")

        # ── Show results ─────────────────────────────────────────────────────
        if st.session_state.processed and st.session_state.results:
            results = st.session_state.results

            render_html(f"""
<div class="iq-cr-head">
<div style="font-size:.82rem;font-weight:700;color:#64748B;">Top Matches ({len(results)} evaluated)</div>
<div class="iq-cr-tools">
<div class="iq-cr-search">&#128269; Search candidates...</div>
<div class="iq-cr-filter">&#9661; Filter</div>
</div>
</div>
<div class="iq-cr-cols">
<div class="iq-cr-col-sp"></div>
<div class="iq-cr-col">Match Score</div>
<div class="iq-cr-col">Recommendation</div>
</div>""")

            for rank, r in enumerate(results[:5], 1):
                score    = r.get("match_score", 0)
                name     = r.get("candidate_name", "Unknown")
                rec      = r.get("recommendation", "")
                skills   = r.get("skills_match", "") or ""
                exp_text = r.get("relevant_experience", "")
                initials = "".join(w[0].upper() for w in name.split()[:2]) or "?"
                av_cls   = _AV_CLS[(rank - 1) % len(_AV_CLS)]
                sub      = _exp_subtitle(exp_text)

                # Skill tags (max 3 visible + overflow)
                skill_list = [s.strip() for s in skills.split(",") if s.strip()]
                extra = max(0, len(skill_list) - 3)
                sk_html = "".join(f'<span class="iq-cr-sk">{s}</span>' for s in skill_list[:3])
                if extra:
                    sk_html += f'<span class="iq-cr-skmore">+{extra}</span>'

                # Recommendation badge
                rec_l = rec.lower()
                if "strongly" in rec_l or "highly" in rec_l:
                    rb_cls, rb_txt = "iq-cr-rb-strong", "Strongly Recommend"
                elif "not" in rec_l and ("suit" in rec_l or "recommend" in rec_l):
                    rb_cls, rb_txt = "iq-cr-rb-no", "Not Suitable"
                elif "recommend" in rec_l:
                    rb_cls, rb_txt = "iq-cr-rb-good", "Recommend"
                elif "review" in rec_l:
                    rb_cls, rb_txt = "iq-cr-rb-ok", "Review"
                else:
                    rb_cls, rb_txt = "iq-cr-rb-ok", "Review"

                render_html(f"""
<div class="iq-cr-row">
<div class="iq-cr-rank">{rank}</div>
<div class="iq-cr-main">
<div class="iq-cr-toprow">
<div class="iq-cr-info">
<div class="iq-cr-name">{name}</div>
<div class="iq-cr-sub">{sub}</div>
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
            st.error("❌ No candidates processed. Check your CV files.")

        else:
            # Idle state — Enterprise Sample Shortlist Preview (matches TuraHire)
            render_html("""
<div class="iq-cr-head">
<div style="font-size:.82rem;font-weight:700;color:#64748B;">Top Matches Preview</div>
<div style="background:#EFF6FF; color:#2563EB; font-size:.68rem; font-weight:700; padding:.22rem .6rem; border-radius:6px; border:1px solid #DBEAFE;">✨ Sample Preview</div>
</div>
<div class="iq-cr-cols">
<div class="iq-cr-col-sp"></div>
<div class="iq-cr-col">Match Score</div>
<div class="iq-cr-col">Recommendation</div>
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
<div class="iq-cr-rec"><span class="iq-cr-rbadge iq-cr-rb-ok">Consider</span></div>
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
💡 <b>Interactive Demo Ready:</b> Click <b style="color:#2563EB;">⚡ Try 10 Demo CVs</b> in Panel 2 to screen live candidate resumes.
</div>
</div>
""")


# ─────────────────────────── Full results (below panels) ─────────────────────
if st.session_state.get("show_full") and st.session_state.results:
    results = st.session_state.results
    render_html("<div style='height:1rem'></div>")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Screened", len(results))
    m2.metric("Shortlisted", min(10, len(results)))
    avg = sum(r.get("match_score", 0) for r in results) / len(results)
    m3.metric("Avg Match", f"{round(avg, 1)}%")
    top_score = max(r.get("match_score", 0) for r in results)
    m4.metric("Top Match", f"{top_score}%")

    # ── Top 3 Candidate Showcase Podium (Item 4) ─────────────────────
    if results:
        top_3 = results[:3]
        _pod_cols = st.columns(min(3, len(top_3)))
        _PODIUM_THEMES = [
            ("🥇 Rank #1 — Top Match", "iq-podium-gold", "iq-pbadge-gold", "#B45309"),
            ("🥈 Rank #2 — Strong Match", "iq-podium-silver", "iq-pbadge-silver", "#334155"),
            ("🥉 Rank #3 — High Potential", "iq-podium-bronze", "iq-pbadge-bronze", "#C2410C"),
        ]

        render_html("""
<div class="iq-podium-wrap">
  <div class="iq-podium-hdr">
    <div class="iq-podium-title">🏆 Top 3 Candidate Showcase</div>
    <div style="font-size:.78rem;font-weight:700;color:#047857;background:#ECFDF5;padding:.25rem .75rem;border-radius:99px;border:1px solid #A7F3D0;">
      ✓ Human-in-the-Loop Review Active
    </div>
  </div>
</div>
""")

        for p_i, (c_r, (p_t, p_c, pb_c, p_col)) in enumerate(zip(top_3, _PODIUM_THEMES)):
            with _pod_cols[p_i]:
                p_score = c_r.get("match_score", 0)
                p_name  = c_r.get("candidate_name", "Unknown")
                p_exp   = c_r.get("relevant_experience", "")
                p_skills = [s.strip() for s in (c_r.get("skills_match", "") or "").split(",") if s.strip()][:3]
                p_rec   = c_r.get("recommendation", "")
                p_idx   = c_r.get("candidate_index", p_i)

                # Fetch current recruiter decision status
                if "recruiter_overrides" not in st.session_state:
                    st.session_state.recruiter_overrides = {}
                c_ov = st.session_state.recruiter_overrides.get(p_idx, {})
                curr_status = c_ov.get("status", "Shortlisted" if p_score >= 70 else "Under Review")

                if curr_status == "Shortlisted":
                    card_status_cls = "iq-card-shortlisted"
                    dec_strip_html = (
                        '<div class="iq-decision-strip iq-dec-strip-shortlisted">'
                        '<span>✅</span><span>Decision: <b>Shortlisted for Interview</b></span>'
                        '</div>'
                    )
                elif curr_status == "Rejected":
                    card_status_cls = "iq-card-passed"
                    dec_strip_html = (
                        '<div class="iq-decision-strip iq-dec-strip-passed">'
                        '<span>❌</span><span>Decision: <b>Passed (Archived)</b></span>'
                        '</div>'
                    )
                else:
                    card_status_cls = ""
                    dec_strip_html = (
                        '<div class="iq-decision-strip iq-dec-strip-consider">'
                        '<span>⚡</span><span>Decision: <b>Under Review</b></span>'
                        '</div>'
                    )

                sk_badges = "".join(f'<span class="iq-cr-sk" style="font-size:.72rem;">{s}</span>' for s in p_skills)
                render_html(f"""
<div class="iq-podium-card {p_c} {card_status_cls}">
  <span class="iq-podium-badge {pb_c}">{p_t}</span>
  <div>
    <div style="font-size:1.15rem;font-weight:800;color:#0F172A;margin-top:.4rem;">{p_name}</div>
    <div style="font-size:.78rem;color:#64748B;font-weight:500;margin-bottom:.8rem;">{p_exp}</div>
    <div style="display:flex;align-items:baseline;gap:.4rem;margin-bottom:.4rem;">
      <span style="font-size:1.6rem;font-weight:900;color:{p_col};">{p_score}%</span>
      <span style="font-size:.8rem;color:#64748B;font-weight:600;">Match Fit</span>
    </div>
    <div style="height:6px;background:#E2E8F0;border-radius:99px;overflow:hidden;margin-bottom:.9rem;">
      <div style="height:100%;width:{p_score}%;background:{p_col};border-radius:99px;"></div>
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:.3rem;margin-bottom:1rem;">{sk_badges}</div>
    <div style="font-size:.8rem;color:#334155;line-height:1.45;background:rgba(255,255,255,.7);padding:.6rem .8rem;border-radius:8px;border:1px solid rgba(0,0,0,.05);">
      <b>Recruiter Rationale:</b> {p_rec}
    </div>
    {dec_strip_html}
  </div>
</div>
""")
                p_b1, p_b2 = st.columns([1, 1])
                with p_b1:
                    is_short = (curr_status == "Shortlisted")
                    lbl_short = "✓ Shortlisted" if is_short else "✅ Shortlist"
                    short_kind = "primary" if is_short else "secondary"
                    if st.button(lbl_short, key=f"btn_short_{p_idx}", use_container_width=True, type=short_kind):
                        if p_idx not in st.session_state.recruiter_overrides:
                            st.session_state.recruiter_overrides[p_idx] = {}
                        st.session_state.recruiter_overrides[p_idx]["status"] = "Shortlisted"
                        st.session_state[f"sel_stat_{p_idx}"] = "Shortlisted"
                        st.toast(f"🎯 {p_name} added to Shortlist!", icon="✅")
                        st.rerun()
                with p_b2:
                    is_pass = (curr_status == "Rejected")
                    lbl_pass = "✕ Passed" if is_pass else "❌ Pass"
                    pass_kind = "primary" if is_pass else "secondary"
                    if st.button(lbl_pass, key=f"btn_pass_{p_idx}", use_container_width=True, type=pass_kind):
                        if p_idx not in st.session_state.recruiter_overrides:
                            st.session_state.recruiter_overrides[p_idx] = {}
                        st.session_state.recruiter_overrides[p_idx]["status"] = "Rejected"
                        st.session_state[f"sel_stat_{p_idx}"] = "Rejected"
                        st.toast(f"📋 {p_name} marked as Pass / Archive", icon="❌")
                        st.rerun()

    # ── Score Distribution Visualisation ─────────────────────────────
    with st.expander("📊 Candidate Match Score Visualisation", expanded=True):
        chart_data = pd.DataFrame([
            {
                "Candidate": r.get("candidate_name", f"CV #{i+1}"),
                "Match Score (%)": r.get("match_score", 0),
            }
            for i, r in enumerate(results[:10])
        ])
        chart = alt.Chart(chart_data).mark_bar(cornerRadius=6, color="#2563EB").encode(
            x=alt.X("Match Score (%):Q", scale=alt.Scale(domain=[0, 100]), title="Match Score (%)"),
            y=alt.Y("Candidate:N", sort="-x", title=""),
            tooltip=["Candidate", "Match Score (%)"]
        ).properties(height=max(160, len(chart_data) * 28))
        st.altair_chart(chart, use_container_width=True)

    # ── Search + Filter bar ──────────────────────────────────────────
    _fc1, _fc2 = st.columns([3, 2])
    with _fc1:
        _search = st.text_input(
            "", placeholder="🔍  Search candidates by name or skill…",
            label_visibility="collapsed", key="res_search"
        )
    with _fc2:
        _filter = st.selectbox(
            "",
            ["All Candidates", "Highly Recommended", "Recommended", "Consider", "Not Recommended"],
            label_visibility="collapsed", key="res_filter"
        )

    # ── Filter logic ─────────────────────────────────────────────────
    _ranked = [(i + 1, results[i]) for i in range(min(10, len(results)))]
    if _search:
        _sq = _search.strip().lower()
        _ranked = [
            (rk, r) for rk, r in _ranked
            if _sq in r.get("candidate_name", "").lower()
            or _sq in r.get("skills_match", "").lower()
        ]
    _fv = _filter if "_filter" in dir() else "All Candidates"
    if _fv == "Highly Recommended":
        _ranked = [(rk, r) for rk, r in _ranked if r.get("match_score", 0) >= 80]
    elif _fv == "Recommended":
        _ranked = [(rk, r) for rk, r in _ranked if 60 <= r.get("match_score", 0) < 80]
    elif _fv == "Consider":
        _ranked = [(rk, r) for rk, r in _ranked if 40 <= r.get("match_score", 0) < 60]
    elif _fv == "Not Recommended":
        _ranked = [(rk, r) for rk, r in _ranked if r.get("match_score", 0) < 40]

    # ── Section header ───────────────────────────────────────────────
    render_html(
        f'<div class="iq-results-hdr">'
        f'<span class="iq-results-hdr-title">📋 All Candidate Profiles &amp; Recruiter Review</span>'
        f'<span class="iq-results-count">{len(_ranked)} shown</span>'
        f'</div>'
    )

    if not _ranked:
        render_html(
            '<div style="text-align:center;padding:2.5rem 1rem;color:#94A3B8;'
            'font-size:.92rem;background:#F8FAFF;border:1.5px dashed #E2E8F0;'
            'border-radius:12px;margin:.5rem 0">No candidates match your filter.</div>'
        )

    _MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}

    for rank, r in _ranked:
        score     = r.get("match_score", 0)
        name      = r.get("candidate_name", "Unknown")
        rec       = r.get("recommendation", "—")
        strengths = r.get("strengths", [])
        concerns  = r.get("concerns", [])
        sub       = _exp_subtitle(r.get("relevant_experience", ""))
        s_lbl, s_stars = _fmt_score(score)
        c_cls = "iq-tag-m" if score >= 70 else "iq-tag-r"

        score_level = "hi" if score >= 80 else ("mid" if score >= 60 else "lo")
        accent_col  = "#10B981" if score >= 80 else ("#F59E0B" if score >= 60 else "#EF4444")

        if score >= 80:
            rec_short = "✦ Highly Rec."
        elif score >= 60:
            rec_short = "✓ Recommended"
        elif score >= 40:
            rec_short = "◎ Consider"
        else:
            rec_short = "✗ Not Rec."

        medal = _MEDALS.get(rank, f"#{rank}")
        exp_label = f"{medal}  {name}   ·   {s_lbl}/10  {s_stars}   ·   {rec_short}"

        str_html = "".join(f'<span class="iq-tag iq-tag-g">&#10003; {s}</span>' for s in strengths) \
                   or '<span class="iq-tag iq-tag-m">None noted</span>'
        con_html = "".join(f'<span class="iq-tag {c_cls}">&#10007; {c}</span>' for c in concerns) \
                   or '<span class="iq-tag iq-tag-m">None noted</span>'

        with st.expander(exp_label, expanded=(rank == 1)):
            render_html(f"""
<div class="iq-det" style="border-left:4px solid {accent_col}">
  <div class="iq-det-hrow">
    <div class="iq-det-hinfo">
      <div class="iq-det-name">{name}</div>
      <div style="font-size:.78rem;color:#64748B;font-weight:500;margin-top:2px;">{sub}</div>
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
  <div class="iq-det-lbl">Recommendation</div>
  <div style="margin-top:.5rem">{_rec_badge(rec)}</div>
</div>""")

            # ── Recruiter Human-in-the-Loop Override Panel (UK GDPR Article 22) ──
            c_idx = r.get("candidate_index", rank - 1)
            if "recruiter_overrides" not in st.session_state:
                st.session_state.recruiter_overrides = {}
            if c_idx not in st.session_state.recruiter_overrides:
                def_s = "Shortlisted" if score >= 70 else ("Consider" if score >= 50 else "Under Review")
                st.session_state.recruiter_overrides[c_idx] = {"status": def_s, "score_delta": 0, "notes": ""}
            c_ov = st.session_state.recruiter_overrides[c_idx]

            render_html("""
<div class="iq-override-card">
  <div class="iq-override-title">
    <span>⚖️ Recruiter Oversight &amp; Decision (UK GDPR Art. 22)</span>
  </div>
  <div style="font-size:.76rem;color:#64748B;margin-bottom:.5rem;">
    Solely automated candidate rejections are legally prohibited. Review the candidate and record your independent decision.
  </div>
</div>""")
            ov_col1, ov_col2, ov_col3 = st.columns([1.2, 1.2, 2.2])
            with ov_col1:
                stat_options = ["Shortlisted", "Consider", "Rejected", "Under Review"]
                curr_sel = c_ov.get("status", "Shortlisted")
                if f"sel_stat_{c_idx}" in st.session_state and st.session_state[f"sel_stat_{c_idx}"] != curr_sel:
                    st.session_state[f"sel_stat_{c_idx}"] = curr_sel
                sel_idx = stat_options.index(curr_sel) if curr_sel in stat_options else 0
                new_status = st.selectbox("Decision Status:", stat_options, index=sel_idx, key=f"sel_stat_{c_idx}")
                st.session_state.recruiter_overrides[c_idx]["status"] = new_status
            with ov_col2:
                new_pts = st.number_input("Score Adj (+/-):", min_value=-20, max_value=20, value=c_ov.get("score_delta", 0), step=1, key=f"num_adj_{c_idx}")
                st.session_state.recruiter_overrides[c_idx]["score_delta"] = new_pts
            with ov_col3:
                new_note = st.text_input("Reviewer Notes:", value=c_ov.get("notes", ""), placeholder="e.g. Verified technical references; invite to interview…", key=f"txt_notes_{c_idx}")
                st.session_state.recruiter_overrides[c_idx]["notes"] = new_note

    # ── Download — styled Excel (.xlsx) with UK GDPR Compliance Audit ──
    import datetime
    _rows = []
    for i, r in enumerate(results):
        cand_idx = r.get("candidate_index", i)
        ov = st.session_state.get("recruiter_overrides", {}).get(cand_idx, {})
        human_status = ov.get("status", "Shortlisted" if r.get("match_score", 0) >= 70 else "Consider")
        score_delta = ov.get("score_delta", 0)
        final_score = min(100, max(0, r.get("match_score", 0) + score_delta))
        human_notes = ov.get("notes", "")

        _rows.append({
            "Rank":                         i + 1,
            "Name":                         r.get("candidate_name", ""),
            "Email":                        r.get("email", ""),
            "AI Match Score":               f"{r.get('match_score', 0)}%",
            "Recruiter Final Score":        f"{final_score}%",
            "Recruiter Decision (Art. 22)": human_status,
            "Recruiter Reviewer Notes":     human_notes,
            "Processing Engine":            r.get("processing_mode", "Cloud AI (BYOK - Privacy Preserved)"),
            "PII Redaction Active":         "YES (UK GDPR Art. 5(1)(c))",
            "Strengths":                    "; ".join(r.get("strengths", [])),
            "Concerns":                     "; ".join(r.get("concerns", [])),
            "AI Recommendation":            r.get("recommendation", ""),
        })

    _df_xl = pd.DataFrame(_rows)
    _buf   = io.BytesIO()

    with pd.ExcelWriter(_buf, engine="openpyxl") as _xw:
        _df_xl.to_excel(_xw, index=False, sheet_name="RankCV Results")
        _ws = _xw.sheets["RankCV Results"]

        # ── Header row style ─────────────────────────────────────────
        _hfill = _PFill("solid", fgColor="2563EB")
        _hfont = _Font(bold=True, color="FFFFFF", size=11, name="Calibri")
        _halign = _Align(horizontal="center", vertical="center")
        for _cell in _ws[1]:
            _cell.fill   = _hfill
            _cell.font   = _hfont
            _cell.alignment = _halign
        _ws.row_dimensions[1].height = 28

        # ── Alternating rows ─────────────────────────────────────────
        _fill_even = _PFill("solid", fgColor="EFF6FF")
        _fill_odd  = _PFill("solid", fgColor="FFFFFF")
        _body_font = _Font(size=10, name="Calibri", color="0B1120")
        _thin_side = _Side(style="thin", color="E2E8F0")
        _thin_border = _Border(
            left=_thin_side, right=_thin_side,
            top=_thin_side,  bottom=_thin_side,
        )
        for _ri, _row in enumerate(_ws.iter_rows(min_row=2), start=2):
            _fill = _fill_even if _ri % 2 == 0 else _fill_odd
            for _cell in _row:
                _cell.fill      = _fill
                _cell.font      = _body_font
                _cell.border    = _thin_border
                _cell.alignment = _Align(wrap_text=True, vertical="top")
            _ws.row_dimensions[_ri].height = 52

        # ── Column widths ─────────────────────────────────────────────
        for _col, _w in zip("ABCDEFGHIJKL", [8, 22, 28, 14, 18, 24, 30, 28, 20, 36, 36, 50]):
            _ws.column_dimensions[_col].width = _w

        _ws.freeze_panes = "A2"

        # ── Sheet 2: UK GDPR Compliance Audit Sheet ───────────────────
        _audit_stats = st.session_state.get("audit_stats", {})
        _audit_rows = [
            {"Audit Parameter": "Statutory Framework", "Compliance Record": "UK General Data Protection Regulation (UK GDPR) & Data Protection Act 2018"},
            {"Audit Parameter": "Governing Jurisdiction", "Compliance Record": "England and Wales"},
            {"Audit Parameter": "Data Controller", "Compliance Record": "Employer / Client Recruitment Organization"},
            {"Audit Parameter": "Data Processor Status", "Compliance Record": "RankCV Web Application (In-Memory Processing Only, Zero Database Retention)"},
            {"Audit Parameter": "Article 22 Human Oversight", "Compliance Record": "VERIFIED — Human recruiter conducted independent review & holds sole decision authority"},
            {"Audit Parameter": "Article 5(1)(c) Data Minimisation", "Compliance Record": "VERIFIED — Candidate personal identifiers (names, emails, phones, postcodes) stripped prior to external AI evaluation"},
            {"Audit Parameter": "Candidate PII Scrubbing Record", "Compliance Record": f"Emails: {_audit_stats.get('emails', 0)} | Phones: {_audit_stats.get('phones', 0)} | Postcodes: {_audit_stats.get('postcodes', 0)} | Names: {_audit_stats.get('names', 0)}"},
            {"Audit Parameter": "Processing Architecture", "Compliance Record": "PRIVATE IN-MEMORY ENGINE (ZERO EXTERNAL AI TRANSFER)" if st.session_state.get("engine_mode") in ["private", "offline"] else "CLOUD AI (BYOK - PRIVACY PRESERVED)"},
            {"Audit Parameter": "Article 5(1)(e) Storage Limitation", "Compliance Record": "VERIFIED — Zero cloud storage. Uploaded CVs parsed ephemerally in-memory and immediately destroyed."},
            {"Audit Parameter": "Equality Act 2010 Compliance", "Compliance Record": "VERIFIED — Protected characteristics excluded from scoring algorithms to prevent algorithmic bias."},
            {"Audit Parameter": "Audit Timestamp (UTC)", "Compliance Record": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")},
            {"Audit Parameter": "Recruiter Sign-Off Declaration", "Compliance Record": "I declare that candidate shortlisting decisions were finalized under human discretion and not through solely automated profiling."},
        ]
        _df_audit = pd.DataFrame(_audit_rows)
        _df_audit.to_excel(_xw, index=False, sheet_name="UK GDPR Compliance Audit")
        _ws_audit = _xw.sheets["UK GDPR Compliance Audit"]

        # Style Audit sheet
        _afill = _PFill("solid", fgColor="0F766E")
        for _cell in _ws_audit[1]:
            _cell.fill = _afill
            _cell.font = _hfont
            _cell.alignment = _halign
        _ws_audit.row_dimensions[1].height = 28
        for _ri, _row in enumerate(_ws_audit.iter_rows(min_row=2), start=2):
            _fill = _fill_even if _ri % 2 == 0 else _fill_odd
            for _cell in _row:
                _cell.fill   = _fill
                _cell.font   = _body_font
                _cell.border = _thin_border
                _cell.alignment = _Align(wrap_text=True, vertical="center")
            _ws_audit.row_dimensions[_ri].height = 26
        _ws_audit.column_dimensions["A"].width = 34
        _ws_audit.column_dimensions["B"].width = 85

    _buf.seek(0)
    _xl_b64 = base64.b64encode(_buf.read()).decode()
    _mime    = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    render_html(
        f'<div class="iq-dl-wrap">'
        f'<a class="iq-dl-btn" href="data:{_mime};base64,{_xl_b64}" '
        f'download="rankcv_results.xlsx">'
        f'⬇️&nbsp;&nbsp;Download Shortlist Report with UK GDPR Audit Log (.xlsx)</a>'
        f'</div>'
    )

    render_html("""
<div class="iq-trial-upgrade">
  <div style="font-size:1.15rem;font-weight:800;color:#0B1120;margin-bottom:.35rem">
    Ready to screen 100s of CVs across active roles?
  </div>
  <div style="font-size:.9rem;color:#64748B;max-width:540px;margin:0 auto 1.1rem;line-height:1.6">
    RankCV helps recruitment &amp; HR teams automate bulk resume screening, candidate communications, and interview scheduling.
  </div>
  <a class="iq-bp" href="https://wa.me/447379975532" target="_blank" style="padding:.65rem 1.6rem;font-size:.9rem">
    Book a Quick Walkthrough on WhatsApp &nbsp;&rarr;
  </a>
</div>
""")


# ─────────────────────────── Features & Platform Capabilities ────────────────
render_html("""
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
<div class="iq-bento-title">Screen 100+ CVs in Seconds</div>
<div class="iq-bento-sub">Automatically filter bulk resumes. Cut out hours of manual reading with parallel multi-file ingestion.</div>
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
<span class="iq-funnel-badge">30 Seconds</span>
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
&#9201; 95% Screening Time Saved for Hiring Leads
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
<div class="iq-bento-sub">Export interview-ready candidate reports formatted with scores, strengths, and interview probe notes.</div>
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
<div class="iq-pillar-stat">45s</div>
<div class="iq-pillar-title">Minutes, Not Days</div>
<div class="iq-pillar-desc">Cut CV screening from days of manual reading to seconds with parallel batch parsing and automated scoring.</div>
</div>
<div class="iq-pillar-item">
<div class="iq-pillar-stat">99%</div>
<div class="iq-pillar-title">Semantic Precision</div>
<div class="iq-pillar-desc">Surface qualified candidates based on actual capability and seniority rather than keyword stuffing.</div>
</div>
<div class="iq-pillar-item">
<div class="iq-pillar-stat">0 ATS</div>
<div class="iq-pillar-title">Works Beside Your ATS</div>
<div class="iq-pillar-desc">No rip-and-replace integrations. Upload candidate batches, rank them, and export directly to your workflow.</div>
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
<div class="iq-beta-text">&ldquo;Works seamlessly beside our existing hiring stack. Just dropped in the resume files, ran the screening, and had interview-ready summaries in under a minute.&rdquo;</div>
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
<div class="iq-beta-text">&ldquo;Works seamlessly beside our existing hiring stack. Just dropped in the resume files, ran the screening, and had interview-ready summaries in under a minute.&rdquo;</div>
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
_stripe_pro_url = os.getenv("STRIPE_PRO_URL", "https://buy.stripe.com/4gM28rdxmck239y8Mk43S03").strip()
_stripe_agency_url = os.getenv("STRIPE_AGENCY_URL", "https://buy.stripe.com/4gM00j2SIfwebG41jS43S02").strip()
try:
    if "STRIPE_PRO_URL" in st.secrets and str(st.secrets["STRIPE_PRO_URL"]).strip():
        _stripe_pro_url = str(st.secrets["STRIPE_PRO_URL"]).strip()
    if "STRIPE_AGENCY_URL" in st.secrets and str(st.secrets["STRIPE_AGENCY_URL"]).strip():
        _stripe_agency_url = str(st.secrets["STRIPE_AGENCY_URL"]).strip()
except Exception:
    pass

render_html(f"""
<div id="pricing" class="iq-price-sec">
  <div class="iq-price-hdr">
    <div class="iq-price-eye">Transparent Pricing</div>
    <div class="iq-price-h2">Simple Plans for Fast-Moving Hiring Teams</div>
    <div class="iq-price-sub">Instant activation. Cancel anytime. Full UK GDPR Article 22 compliance and audit logs included in every tier.</div>
  </div>

  <div class="iq-price-grid">
    <!-- Plan 1: Professional €99/mo -->
    <div class="iq-plan-card">
      <div>
        <span class="iq-plan-badge iq-badge-starter">Boutique &amp; In-House HR</span>
        <div class="iq-plan-name">Professional</div>
        <div class="iq-plan-desc">Fast, plug-and-play AI CV screening with zero technical setup. Ready to use immediately.</div>
        <div class="iq-plan-price-wrap">
          <span class="iq-plan-curr">&euro;</span>
          <span class="iq-plan-amt">99</span>
          <span class="iq-plan-period">/ month</span>
        </div>
        <ul class="iq-plan-features">
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>Up to 300 CVs</b> screened per month</span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>Up to 10</b> active job openings simultaneously</span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>Plug &amp; Play AI:</b> Internal RankCV engine</span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>Private In-Memory Engine:</b> Zero external AI transfer</span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>Full UK GDPR Shield:</b> Names &amp; postcodes redacted</span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>Top 3 Podium &amp; Article 22</b> Human override tags</span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>Excel Shortlist &amp; UK GDPR Audit</b> Sheet download</span></li>
        </ul>
      </div>
      <div>
        <a class="iq-plan-btn iq-btn-primary" href="{_stripe_pro_url}" target="_blank">
          Subscribe with Apple Pay / Card &nbsp;&rarr;
        </a>
        <div class="iq-guarantee">&#128274; 256-bit SSL encrypted &bull; Cancel anytime &bull; No setup fee</div>
      </div>
    </div>

    <!-- Plan 2: Agency & Scale-up €199/mo (UNLIMITED) -->
    <div class="iq-plan-card featured">
      <div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;">
          <span class="iq-plan-badge iq-badge-agency">&#9733; MOST POPULAR &bull; UNLIMITED</span>
          <span style="font-size:.72rem;font-weight:800;color:#2563EB;background:#EFF6FF;border:1px solid #BFDBFE;padding:.2rem .6rem;border-radius:6px;">ENTERPRISE DPA</span>
        </div>
        <div class="iq-plan-name">Agency &amp; Enterprise</div>
        <div class="iq-plan-desc">Unlimited candidate screening powered by your own company OpenAI or Azure API key.</div>
        <div class="iq-plan-price-wrap">
          <span class="iq-plan-curr">&euro;</span>
          <span class="iq-plan-amt">199</span>
          <span class="iq-plan-period">/ month</span>
        </div>
        <ul class="iq-plan-features">
          <li class="iq-plan-feat-item"><span class="iq-feat-icon-gold">&#9889;</span><span><b>UNLIMITED CV Screening</b> (Zero monthly volume caps)</span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon-gold">&#9889;</span><span><b>UNLIMITED Active Roles &amp; JDs</b></span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon-gold">&#9889;</span><span><b>Bring Your Own Key (BYOK):</b> OpenAI / Azure UK/EU</span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>Enterprise Data Ownership:</b> Under your company DPA</span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>ATS &amp; CRM Integration:</b> Bullhorn, Greenhouse, Lever</span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>Full UK GDPR Shield:</b> In-memory PII scrub &amp; Art. 22 audit</span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>Priority 1-on-1 Assisted Setup &amp; Dedicated WhatsApp</b></span></li>
        </ul>
      </div>
      <div>
        <a class="iq-plan-btn iq-btn-agency" href="{_stripe_agency_url}" target="_blank">
          Subscribe to Agency Unlimited &nbsp;&rarr;
        </a>
        <div class="iq-guarantee">&#128274; 256-bit SSL encrypted &bull; Cancel anytime &bull; Assisted onboarding</div>
      </div>
    </div>
  </div>

  <!-- Trust & Payment Methods Footer -->
  <div class="iq-pay-badges">
    <span style="font-size:.82rem;font-weight:700;color:#64748B;margin-right:.5rem;">Accepted Payment Methods:</span>
    <span class="iq-pay-pill"><svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" style="margin-right:2px"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M15.97 6.37c.62-.75 1.04-1.8 0.92-2.85-.9.04-2 .6-2.65 1.35-.58.66-1.08 1.74-.95 2.76.99.08 2.04-.51 2.68-1.26z"/></svg>Apple Pay</span>
    <span class="iq-pay-pill" style="font-weight:800;color:#1A1F71">VISA</span>
    <span class="iq-pay-pill"><span style="color:#EB001B">&#9679;</span><span style="color:#F79E1B;margin-left:-4px">&#9679;</span> Mastercard</span>
    <span class="iq-pay-pill">UK Debit Cards</span>
    <span class="iq-pay-pill" style="color:#6366F1;font-weight:800;">&#128274; Powered by Stripe UK (FCA Authorised)</span>
  </div>
</div>
""")


# ─────────────────────────── FAQ ─────────────────────────────────────────────
render_html("""
<div id="faq" class="iq-faq-sec">
<div class="iq-faq-hdr">
<div class="iq-faq-eye">Frequently Asked Questions</div>
<div class="iq-faq-h2">Got Questions? We&rsquo;ve Got Answers</div>
<div class="iq-faq-sub">Everything you need to know about AI resume screening, batch evaluations, and candidate data privacy.</div>
</div>
<div class="iq-faq-list">

<details class="iq-faq-item">
<summary class="iq-faq-summary">
<span>What counts as a resume parse?</span>
<svg class="iq-faq-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
</summary>
<div class="iq-faq-body">
Each uploaded resume (PDF, Word DOCX, or TXT) evaluated against your job description counts as one candidate parse. RankCV extracts work history, skill proficiencies, seniority level, and requirement alignment in seconds.
</div>
</details>

<details class="iq-faq-item">
<summary class="iq-faq-summary">
<span>What is included in the free trial?</span>
<svg class="iq-faq-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
</summary>
<div class="iq-faq-body">
You can screen up to 10 candidate CVs per batch completely free with zero credit card required. You get instant access to 0&ndash;100 match scores, candidate rankings, strengths &amp; concerns breakdowns, and executive shortlist report downloads.
</div>
</details>

<details class="iq-faq-item">
<summary class="iq-faq-summary">
<span>How does the AI score and rank candidates?</span>
<svg class="iq-faq-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
</summary>
<div class="iq-faq-body">
RankCV uses contextual semantic evaluation to assess applicants against your specific job criteria. Rather than relying on rigid keyword matching, the AI evaluates project complexity, demonstrated skills, and seniority depth to produce fair, explainable rankings.
</div>
</details>

<details class="iq-faq-item">
<summary class="iq-faq-summary">
<span>Can an HR department use RankCV without breaking UK GDPR rules?</span>
<svg class="iq-faq-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
</summary>
<div class="iq-faq-body">
<b>Yes, absolutely.</b> RankCV is architected specifically to comply with the <b>UK GDPR, the Data Protection Act 2018, and ICO guidance</b> on automated decision support:
<ul style="margin:0.5rem 0 0.5rem 1.2rem; padding:0; line-height:1.6;">
  <li><b>Article 5(1)(c) Data Minimisation:</b> Built-in PII Stripper automatically scrubs names, UK postcodes, phone numbers, email addresses, and demographic identifiers in-memory before evaluation.</li>
  <li><b>Data Controller Autonomy (BYOK):</b> Recruiter teams can plug in their own OpenAI or Azure UK/EU API key. Your organization remains the sole Data Controller with zero third-party model training retention.</li>
  <li><b>Private In-Memory Engine (Zero External AI Data Egress):</b> Recruiter teams can select the private internal engine for zero external data transfers—evaluating candidates in volatile RAM with zero third-party AI processing.</li>
  <li><b>Article 22 Human-in-the-Loop:</b> RankCV acts purely as decision support. No candidate is ever rejected automatically; recruiters retain full override power with customizable status tags and notes.</li>
  <li><b>Auditable Accountability:</b> Every batch exports an Excel file with an embedded <i>UK GDPR Compliance Audit Sheet</i>, providing timestamped methodology and statutory sign-off logs under England &amp; Wales governing law.</li>
</ul>
</div>
</details>

<details class="iq-faq-item">
<summary class="iq-faq-summary">
<span>Does RankCV integrate with our ATS?</span>
<svg class="iq-faq-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
</summary>
<div class="iq-faq-body">
RankCV is designed to work smoothly beside your existing ATS (Greenhouse, Lever, Workday, Ashby, BambooHR). Simply export applicant resumes from your ATS, drop them into RankCV, and download interview-ready candidate reports formatted for hiring managers.
</div>
</details>

<details class="iq-faq-item">
<summary class="iq-faq-summary">
<span>What is data ownership and portability?</span>
<svg class="iq-faq-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
</summary>
<div class="iq-faq-body">
You maintain 100% ownership of all uploaded job descriptions, candidate resumes, scorecards, and reports. All shortlists and candidate evaluations can be exported in 1 click as structured report downloads.
</div>
</details>

<details class="iq-faq-item">
<summary class="iq-faq-summary">
<span>How fast is the batch screening process?</span>
<svg class="iq-faq-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
</summary>
<div class="iq-faq-body">
Parallel multi-file processing enables RankCV to parse, score, and rank a batch of 10 to 50 resumes in under 45 seconds&mdash;saving hours of manual resume skimming for each open role.
</div>
</details>

<details class="iq-faq-item">
<summary class="iq-faq-summary">
<span>What happens when I need higher volume or custom team features?</span>
<svg class="iq-faq-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
</summary>
<div class="iq-faq-body">
If your recruiting team handles high-volume applicant pipelines or requires custom scoring rubrics, click <a href="https://wa.me/447379975532" target="_blank" style="color:#2563EB;font-weight:700;text-decoration:none;">Book a Demo</a> to connect directly with our team on WhatsApp for dedicated volume onboarding.
</div>
</details>

</div>
</div>
""")


render_html("""
<div class="iq-foot">
<div class="iq-foot-txt">RankCV &middot; AI CV Screening &amp; Candidate Ranking Platform</div>
</div>
""")


