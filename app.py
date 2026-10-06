"""
TalentIQ — AI-Powered CV Screening
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
from utils.ai_scoring import extract_resume_keywords, rank_candidates_batch
from utils.cleanup import delete_uploaded_files
import altair as alt


st.set_page_config(
    page_title="TalentIQ — Screen CVs in Minutes",
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
}
[data-testid="stAppViewContainer"] { background: #F5F7FB !important; }
[data-testid="stHeader"]           { display: none !important; }
[data-testid="block-container"]    {
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
.iq-logo { font-size: 1.45rem; font-weight: 900; color: #2563EB; letter-spacing: -.5px; }
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

/* ── Testimonials & Early Beta Feedback ── */
.iq-ts-sec { background:#fff; border:1px solid #E2E8F0; border-radius:20px; padding:2.5rem 2rem; margin:3rem 0 2rem; }
.iq-ts-h   { font-size:1.65rem; font-weight:900; color:#0B1120; letter-spacing:-.5px; margin-bottom:.35rem; }
.iq-ts-s   { color:#64748B; font-size:.9rem; margin-bottom:1.6rem; }
.iq-beta-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 1.25rem;
}
.iq-beta-card {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 14px;
    padding: 1.4rem 1.4rem;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: transform .15s, box-shadow .15s;
}
.iq-beta-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(10,20,60,.06);
    border-color: #CBD5E1;
}
.iq-beta-text {
    font-size: .875rem;
    color: #334155;
    line-height: 1.6;
    margin-bottom: 1.1rem;
}
.iq-tp     { display:flex; align-items:center; gap:.65rem; }
.iq-tav    { width:36px; height:36px; border-radius:50%; flex-shrink:0; background:linear-gradient(135deg,#DBEAFE,#EDE9FE); display:flex; align-items:center; justify-content:center; font-weight:700; color:#2563EB; font-size:.82rem; }
.iq-tpn    { font-weight:700; font-size:.83rem; color:#0B1120; }
.iq-tpc    { font-size:.76rem; color:#64748B; }

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
    font-size: 2.15rem; font-weight: 900; color: #0F172A;
    letter-spacing: -1px; margin-bottom: .5rem; line-height: 1.2;
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

/* ── High-Fidelity Bento Grid & UI Mockups ── */
.iq-bento-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 1.5rem;
    margin-bottom: 3rem;
}
.iq-bento-card {
    background: #FFFFFF;
    border: 1.5px solid #E2E8F0;
    border-radius: 20px;
    padding: 1.8rem;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: transform .18s, box-shadow .18s, border-color .18s;
    box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.04);
}
.iq-bento-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 16px 36px -4px rgba(15, 23, 42, 0.08);
    border-color: #CBD5E1;
}
.iq-bento-tag {
    display: inline-block;
    font-size: .68rem;
    font-weight: 700;
    letter-spacing: .08em;
    text-transform: uppercase;
    color: #2563EB;
    background: #EFF6FF;
    border: 1px solid #DBEAFE;
    padding: .2rem .65rem;
    border-radius: 6px;
    margin-bottom: .75rem;
    width: fit-content;
}
.iq-bento-title {
    font-size: 1.22rem;
    font-weight: 800;
    color: #0F172A;
    line-height: 1.25;
    margin-bottom: .45rem;
}
.iq-bento-sub {
    font-size: .84rem;
    color: #64748B;
    line-height: 1.55;
    margin-bottom: 1.2rem;
}
.iq-mockup-box {
    background: #F8FAFC;
    border: 1.5px solid #E2E8F0;
    border-radius: 14px;
    padding: 1rem 1.15rem;
}
/* ── Visual Recruitment Funnel (Layman visual graphics) ── */
.iq-funnel-step {
    display: flex; align-items: center; justify-content: space-between;
    background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px;
    padding: .55rem .85rem; margin-bottom: .45rem;
    box-shadow: 0 1px 3px rgba(15,23,42,.03);
}
.iq-funnel-left { display: flex; align-items: center; gap: .6rem; }
.iq-funnel-icon { font-size: 1.1rem; }
.iq-funnel-txt { font-size: .8rem; font-weight: 700; color: #0F172A; }
.iq-funnel-sub { font-size: .68rem; color: #64748B; }
.iq-funnel-badge {
    font-size: .67rem; font-weight: 700; padding: .18rem .55rem;
    border-radius: 6px; background: #EFF6FF; color: #2563EB;
}
.iq-funnel-badge-green { background: #DCFCE7; color: #15803D; }
.iq-funnel-highlight {
    background: #ECFDF5; border: 1px solid #A7F3D0;
    border-radius: 10px; padding: .55rem; text-align: center;
    font-size: .76rem; font-weight: 800; color: #065F46; margin-top: .55rem;
}

.iq-gauge-row { margin-bottom: .6rem; }
.iq-gauge-row:last-child { margin-bottom: 0; }
.iq-gauge-info { display: flex; justify-content: space-between; font-size: .75rem; font-weight: 700; color: #334155; margin-bottom: .25rem; }
.iq-gauge-track { height: 6px; background: #E2E8F0; border-radius: 99px; overflow: hidden; }
.iq-gauge-bar { height: 100%; border-radius: 99px; }

.iq-cand-mini-row {
    display: flex; align-items: center; justify-content: space-between;
    padding: .45rem 0; border-bottom: 1px solid #EDF2F7;
}
.iq-cand-mini-row:last-child { border-bottom: none; }
.iq-cand-mini-left { display: flex; align-items: center; gap: .5rem; }
.iq-medal { font-size: 1rem; }
.iq-cand-mini-name { font-size: .82rem; font-weight: 800; color: #0F172A; }
.iq-cand-mini-role { font-size: .7rem; color: #64748B; }
.iq-score-pill {
    font-size: .68rem; font-weight: 700; padding: .2rem .55rem; border-radius: 6px;
}
.iq-score-pill-green { background: #DCFCE7; color: #15803D; }
.iq-score-pill-blue { background: #DBEAFE; color: #1D4ED8; }

.iq-excel-preview { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; overflow: hidden; margin-bottom: .65rem; }
.iq-excel-hdr-row {
    display: grid; grid-template-columns: 35px 1.4fr .8fr 1.6fr;
    background: #F1F5F9; padding: .35rem .6rem; font-size: .66rem;
    font-weight: 800; text-transform: uppercase; color: #475569; letter-spacing: .04em;
    border-bottom: 1px solid #CBD5E1;
}
.iq-excel-data-row {
    display: grid; grid-template-columns: 35px 1.4fr .8fr 1.6fr;
    padding: .35rem .6rem; font-size: .72rem; color: #334155;
    border-bottom: 1px solid #F1F5F9; align-items: center;
}
.iq-excel-data-row:last-child { border-bottom: none; }
.iq-excel-footer { display: flex; justify-content: space-between; align-items: center; font-size: .73rem; color: #64748B; }
.iq-dl-badge {
    background: #10B981; color: #FFFFFF; font-weight: 700;
    font-size: .68rem; padding: .25rem .65rem; border-radius: 6px;
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
    display:flex; align-items:flex-start; gap:.45rem;
    padding:.65rem .5rem; border:1px solid #EAEFF6;
    border-radius:12px; margin-bottom:.45rem; background:#fff;
    transition:background-color .15s ease, border-color .15s ease;
}
.iq-cr-row:hover { background-color:#F8FAFC; border-color:#CBD5E1; }
.iq-cr-rank {
    width:21px; height:21px; border-radius:50%;
    background:#2563EB; color:#fff; font-weight:800;
    font-size:.62rem; display:flex; align-items:center;
    justify-content:center; flex-shrink:0; margin-top:2px;
}
.iq-cr-av {
    width:38px; height:38px; border-radius:50%; flex-shrink:0;
    display:flex; align-items:center; justify-content:center;
    font-weight:800; font-size:.84rem; color:#fff;
}
.iq-cr-av1 { background:linear-gradient(135deg,#6366F1,#8B5CF6); }
.iq-cr-av2 { background:linear-gradient(135deg,#EC4899,#F97316); }
.iq-cr-av3 { background:linear-gradient(135deg,#0EA5E9,#14B8A6); }
.iq-cr-av4 { background:linear-gradient(135deg,#F59E0B,#EF4444); }
.iq-cr-av5 { background:linear-gradient(135deg,#10B981,#3B82F6); }
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
</style>"""

st.markdown(build_css(), unsafe_allow_html=True)

# ─────────────────────────── Session state ───────────────────────────────────
for _k, _v in [
    ("results",          []),
    ("processed",        False),
    ("uploaded_paths",   []),
    ("show_full",        False),
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
<div class="iq-logo">Talent<b>IQ</b></div>
<div style="display:flex;align-items:center;gap:1.3rem;">
<a href="#screening-workspace" style="font-size:.875rem;font-weight:600;color:#64748B;text-decoration:none;">Screen CVs</a>
<a href="#features" style="font-size:.875rem;font-weight:600;color:#64748B;text-decoration:none;">Features</a>
<a class="iq-nav-demo" href="https://wa.me/447379975532" target="_blank">Book a Demo &nbsp;&rarr;</a>
</div>
</div>
""")


# ─────────────────────────── Hero ────────────────────────────────────────────
render_html("""
<div class="iq-hero">
<div class="iq-eye">&#10022; &nbsp;AI-Powered CV Screening for HR &amp; Recruitment Teams</div>
<div class="iq-h1">Shortlist Top Talent<br>in <span class="bl">Seconds.</span></div>
<div class="iq-sub">Upload a job description and candidate CVs. TalentIQ automatically
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
<div class="iq-fbar-t2">Instant Excel reports</div>
</div>
</div>
</div>
""")


# ─────────────────────────── 3-panel layout ──────────────────────────────────
render_html('<div id="screening-workspace" style="margin-top:1.5rem;"></div>')
col1, col2, col3 = st.columns([1, 1, 1.15], gap="large")

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
            label_visibility="visible",
        )
        if role_choice != "Custom (Paste your own JD)" and st.session_state.get("_prev_role_choice") != role_choice:
            st.session_state["_prev_role_choice"] = role_choice
            st.session_state["jd_paste"] = SAMPLE_ROLES[role_choice]
            st.rerun()

        tab_paste, tab_file = st.tabs(["Paste Text", "Upload File"])

        jd_text = ""

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
                f'<span>{char_count:,} / 5,000</span>'
                f'</div>'
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
            render_html('<div class="iq-status-ok">✅ Job description added</div>')
        else:
            render_html('<div class="iq-status-wait">⏳ Waiting for job description…</div>')


# ══════════════════════════ PANEL 2 — Upload CVs ══════════════════════════════
with col2:
    with st.container(border=True):
        render_html("""
<div class="iq-phead">
  <div class="iq-pnum">2</div>Upload Candidate CVs
</div>""")

        render_html(
            '<div class="iq-trial-info">🎁 <b>Free Trial:</b> Screen up to <b>10 CVs per batch</b>. '
            'Upload resumes in PDF, DOCX or TXT format.</div>'
        )

        cv_files = st.file_uploader(
            "Upload CVs (PDF, DOCX, TXT — up to 10 files)",
            type=["pdf", "docx", "txt"],
            accept_multiple_files=True,
            key="cv_up",
            label_visibility="visible",
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
            render_html('<div class="iq-status-wait">⏳ Drag &amp; drop resumes or test with 5 demo CVs below…</div>')

        render_html("<div style='height:.7rem'></div>")
        col_btn1, col_btn2 = st.columns([1.15, 1])
        with col_btn1:
            run_btn = st.button("🚀  Screen Candidates", use_container_width=True, type="primary")
        with col_btn2:
            demo_btn = st.button("⚡  Try 5 Demo CVs", use_container_width=True)


# ══════════════════════════ PANEL 3 — Results ═════════════════════════════════
_AV_CLS = ["iq-cr-av1","iq-cr-av2","iq-cr-av3","iq-cr-av4","iq-cr-av5"]

with col3:
    with st.container(border=True):

        # ── Trigger demo screening ───────────────────────────────────────────
        if demo_btn:
            if not jd_text.strip():
                jd_text = SAMPLE_ROLES["Senior Python Backend Engineer"]
                st.session_state["jd_paste"] = jd_text
                st.session_state["_prev_role_choice"] = "Senior Python Backend Engineer"

            demo_dir = Path("dummy_cvs_pdf")
            demo_files = sorted(demo_dir.glob("*.pdf"))[:5]
            if not demo_files:
                st.error("Demo CVs not found on server.")
            else:
                job_context = {
                    "title": "Senior Python Backend Engineer",
                    "skills": "Python, FastAPI, AWS, PostgreSQL, Docker",
                    "years_experience": 5,
                    "description": jd_text,
                }
                candidates = []
                bar = st.progress(0, text="Loading 5 Demo CVs…")
                _info = st.empty()
                for idx, df in enumerate(demo_files, 1):
                    render_html(
                        f'<p style="font-size:.82rem;color:#64748B">'
                        f'📄 <b style="color:#2563EB">{df.name}</b> ({idx}/5)</p>',
                        container=_info,
                    )
                    try:
                        text = _read_cv(str(df), df.name)
                        if text.strip():
                            candidates.append(extract_resume_keywords(cv_text=text, required_skills="Python, FastAPI, AWS, PostgreSQL, Docker"))
                    except Exception as ex:
                        st.warning(f"⚠️ Error reading {df.name}: {ex}")
                    bar.progress(idx / 5 * 0.5, text=f"Parsing demo CVs — {idx}/5 done…")

                if candidates:
                    render_html(
                        f'<p style="font-size:.82rem;color:#64748B">'
                        f'🤖 Ranking <b style="color:#2563EB">{len(candidates)} candidates</b> with AI…</p>',
                        container=_info,
                    )
                    bar.progress(0.7, text=f"AI ranking {len(candidates)} candidates…")
                    try:
                        results = rank_candidates_batch(candidates=candidates, job_context=job_context)
                    except Exception as _err:
                        results = []

                    bar.progress(1.0, text="✅ Done!"); _info.empty()
                    st.session_state.results = results
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
                    dest.write_bytes(f.read())
                    saved_paths.append(str(dest))
                    saved_names.append(f.name)

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
                        candidates.append(extract_resume_keywords(cv_text=text, required_skills=""))
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
                        results = rank_candidates_batch(candidates=candidates, job_context=job_context)
                    except Exception as _err:
                        results = []
                else:
                    results = []

                bar.progress(1.0, text="✅ Done!"); _info.empty()
                st.session_state.results   = results
                st.session_state.processed = True
                st.session_state.show_full = True
                st.success(f"🎯 Successfully evaluated {len(results)} candidate(s)!")

                deleted, _ = delete_uploaded_files(saved_paths)
                if deleted:
                    st.caption(f"🗑️ {len(deleted)} file(s) deleted from server.")

        # ── Show results ─────────────────────────────────────────────────────
        if st.session_state.processed and st.session_state.results:
            results = st.session_state.results

            render_html("""
<div class="iq-cr-head">
<div class="iq-cr-title">Candidate Rankings</div>
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
<div class="iq-cr-av {av_cls}">{initials}</div>
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
<div class="iq-cr-title">Candidate Rankings</div>
<div style="background:#EFF6FF; color:#2563EB; font-size:.68rem; font-weight:700; padding:.22rem .6rem; border-radius:6px; border:1px solid #DBEAFE;">✨ Sample Preview</div>
</div>
<div class="iq-cr-cols">
<div class="iq-cr-col-sp"></div>
<div class="iq-cr-col">Match Score</div>
<div class="iq-cr-col">Recommendation</div>
</div>

<div class="iq-cr-row">
<div class="iq-cr-rank">1</div>
<div class="iq-cr-av iq-cr-av1">AC</div>
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
<div class="iq-cr-av iq-cr-av2">MS</div>
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
<div class="iq-cr-av iq-cr-av3">SR</div>
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
💡 <b>Interactive Demo Ready:</b> Click <b style="color:#2563EB;">⚡ Try 5 Demo CVs</b> in Panel 2 to screen live candidate resumes.
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
        f'<span class="iq-results-hdr-title">📋 All Candidate Profiles</span>'
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

    # ── Download — styled Excel (.xlsx) ─────────────────────────────
    _rows = [
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
    ]
    _df_xl = pd.DataFrame(_rows)
    _buf   = io.BytesIO()

    with pd.ExcelWriter(_buf, engine="openpyxl") as _xw:
        _df_xl.to_excel(_xw, index=False, sheet_name="TalentIQ Results")
        _ws = _xw.sheets["TalentIQ Results"]

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
        for _col, _w in zip("ABCDEFG", [8, 22, 28, 10, 38, 38, 55]):
            _ws.column_dimensions[_col].width = _w

        # ── Freeze header row ─────────────────────────────────────────
        _ws.freeze_panes = "A2"

    _buf.seek(0)
    _xl_b64 = base64.b64encode(_buf.read()).decode()
    _mime    = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    render_html(
        f'<div class="iq-dl-wrap">'
        f'<a class="iq-dl-btn" href="data:{_mime};base64,{_xl_b64}" '
        f'download="talentiq_results.xlsx">'
        f'⬇️&nbsp;&nbsp;Download Results (.xlsx)</a>'
        f'</div>'
    )

    render_html("""
<div class="iq-trial-upgrade">
  <div style="font-size:1.15rem;font-weight:800;color:#0B1120;margin-bottom:.35rem">
    Ready to screen 100s of CVs across active roles?
  </div>
  <div style="font-size:.9rem;color:#64748B;max-width:540px;margin:0 auto 1.1rem;line-height:1.6">
    TalentIQ helps recruitment &amp; HR teams automate bulk resume screening, candidate communications, and interview scheduling.
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
<div class="iq-bento-title">1-Click Formatted Spreadsheets</div>
<div class="iq-bento-sub">Download executive-ready Excel reports formatted with candidate scores, strengths, and interview notes.</div>
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
<span>&#128196; Shortlist_Executive_Report.xlsx</span>
<span class="iq-dl-badge">&#10515; Ready</span>
</div>
</div>
</div>
</div>

<div class="iq-pillars-box">
<div class="iq-pillars-top">
<div style="font-size:.72rem;font-weight:800;color:#2563EB;letter-spacing:.12em;text-transform:uppercase;margin-bottom:.4rem;">Built for High-Volume Hiring</div>
<div style="font-size:1.55rem;font-weight:900;color:#0F172A;letter-spacing:-.5px;">Why Recruiters Choose TalentIQ</div>
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
<div style="text-align:center">
<div class="iq-ts-h">Reviews &amp; Testimonials</div>
<div class="iq-ts-s">Early feedback from recruiters and HR leads testing our pre-launch pilot</div>
</div>
<div class="iq-beta-grid">
<div class="iq-beta-card">
<div class="iq-beta-text">&ldquo;Tested the pilot on 15 resumes for an engineering role. The top 3 ranked candidates were spot on and it saved me an hour of manual skimming.&rdquo;</div>
<div class="iq-tp">
<div class="iq-tav">AM</div>
<div>
<div class="iq-tpn">Alex Miller</div>
<div class="iq-tpc">Technical Recruiter &middot; Beta Tester</div>
</div>
</div>
</div>
<div class="iq-beta-card">
<div class="iq-beta-text">&ldquo;The strengths and concerns breakdown cuts out the fluff. Really helpful when evaluating a quick batch of applicants on a Friday afternoon.&rdquo;</div>
<div class="iq-tp">
<div class="iq-tav">SK</div>
<div>
<div class="iq-tpn">Sarah Khan</div>
<div class="iq-tpc">Talent Acquisition &middot; Early Access</div>
</div>
</div>
</div>
<div class="iq-beta-card">
<div class="iq-beta-text">&ldquo;Super straightforward. Uploaded CVs, got instant match scores, and exported the Excel sheet in seconds. Looking forward to the official launch.&rdquo;</div>
<div class="iq-tp">
<div class="iq-tav">DL</div>
<div>
<div class="iq-tpn">David Lee</div>
<div class="iq-tpc">Independent Recruiter &middot; Beta Tester</div>
</div>
</div>
</div>
</div>
</div>
""")


render_html("""
<div class="iq-foot">
<div class="iq-foot-txt">TalentIQ &middot; AI CV Screening &middot; Built with Streamlit &amp; GPT-4o</div>
</div>
""")


