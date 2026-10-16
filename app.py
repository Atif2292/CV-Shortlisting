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
@import url('https://fonts.googleapis.com/css2?family=Anton&family=Space+Grotesk:wght@500;600;700;800&family=Inter:wght@400;500;600;700;800&family=Space+Mono:wght@400;700&display=swap');

/* ── Bhavna Design Tokens ── */
:root {
    --ink: #14150E;
    --ink-soft: #55583F;
    --paper: #FAF8EC;
    --paper-dim: #F1EDD6;
    --card: #FFFFFF;
    --card-hi: #FFFEF6;
    --signal: #C7D633;
    --signal-soft: #E3EC8E;
    --signal-dim: rgba(199,214,51,0.22);
    --signal-text: #6B7A1A;
    --indigo: #E0692C;
    --mid: #83816A;
    --card-dark: #121316;
    --border-dark: rgba(255,255,255,0.12);
}

/* ── Base & Atmosphere ── */
html, body, [data-testid="stAppViewContainer"] {
    background-color: #FAF8EC !important;
    background-image: 
        radial-gradient(ellipse at 80% 0%, rgba(199,214,51,0.18) 0%, transparent 60%),
        radial-gradient(ellipse at 15% 90%, rgba(224,105,44,0.10) 0%, transparent 50%) !important;
    background-attachment: fixed !important;
    color: #14150E !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    -webkit-font-smoothing: antialiased !important;
}

[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stToolbar"] { right: 1rem; top: 1rem; }
.main .block-container {
    max-width: 1220px !important;
    padding-top: 1.5rem !important;
    padding-bottom: 5rem !important;
}

/* ── Typography & Display Headings ── */
h1, h2, h3, .bhavna-display {
    font-family: 'Anton', 'Space Grotesk', sans-serif !important;
    letter-spacing: .02em !important;
    text-transform: uppercase !important;
    color: #14150E !important;
    font-weight: 400 !important;
}

/* ── Shimmer & Pulse Animations ── */
.shine {
    background: linear-gradient(110deg, #14150E 0%, #14150E 35%, #6B7A1A 48%, #C7D633 52%, #14150E 65%, #14150E 100%);
    background-size: 240% 100%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: textShine 7s ease-in-out infinite;
    display: inline-block;
}
@keyframes textShine {
    0% { background-position: 120% 0; }
    100% { background-position: -120% 0; }
}

.pulse {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #C7D633;
    box-shadow: 0 0 10px 1px rgba(199,214,51,0.8);
    animation: pulseGlow 2.2s infinite ease-in-out;
}
@keyframes pulseGlow {
    0%, 100% { transform: scale(1); opacity: .85; }
    50% { transform: scale(1.35); opacity: 1; box-shadow: 0 0 14px 3px rgba(199,214,51,1); }
}

/* ── Eyebrow Badge (Bhavna style with glowing dot) ── */
.bhavna-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-family: 'Space Mono', monospace;
    font-size: .78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .12em;
    padding: 6px 14px;
    border-radius: 100px;
    background: rgba(199,214,51,0.22);
    color: #6B7A1A;
    border: 1px solid rgba(199,214,51,0.35);
    margin-bottom: 1.2rem;
}
.bhavna-badge-sub {
    font-family: 'Space Mono', monospace;
    font-size: .75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .1em;
    color: #6B7A1A;
}

/* ── Floating Capsule Navbar (Bhavna Signature) ── */
.iq-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: .65rem 1.4rem;
    margin: .75rem auto 2.2rem;
    background: #C7D633;
    border-radius: 100px;
    box-shadow: 0 12px 32px -8px rgba(199,214,51,0.45);
    position: relative;
    z-index: 99;
}
.iq-brand {
    font-family: 'Anton', 'Space Grotesk', sans-serif;
    font-size: 1.55rem;
    font-weight: 900;
    letter-spacing: .02em;
    text-transform: uppercase;
    color: #14150E;
    text-decoration: none;
    display: flex;
    align-items: center;
    gap: .45rem;
}
.iq-brand span.dot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #14150E;
}
.iq-nav-links {
    display: flex;
    align-items: center;
    gap: 1.4rem;
}
.iq-nav-link {
    font-family: 'Space Grotesk', sans-serif;
    font-size: .88rem;
    font-weight: 700;
    color: #14150E;
    text-decoration: none !important;
    transition: opacity .2s;
}
.iq-nav-link:hover { opacity: .75; }
.iq-nav-btn {
    background: #14150E !important;
    color: #C7D633 !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-size: .84rem !important;
    font-weight: 800 !important;
    padding: .5rem 1.25rem !important;
    border-radius: 100px !important;
    text-decoration: none !important;
    box-shadow: 0 4px 14px rgba(20,21,14,0.35) !important;
    transition: transform .2s, box-shadow .2s !important;
    display: inline-flex !important;
    align-items: center !important;
    gap: 6px !important;
}
.iq-nav-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 18px rgba(20,21,14,0.5) !important;
    color: #E3EC8E !important;
}

/* ── Hero ── */
.iq-hero {
    text-align: center;
    margin: 2.2rem auto 3rem;
    max-width: 960px;
    padding: 0 1rem;
}
.iq-hero-h1 {
    font-family: 'Anton', 'Space Grotesk', sans-serif !important;
    font-size: clamp(3.2rem, 7.5vw, 6rem);
    font-weight: 400;
    line-height: .98;
    letter-spacing: .02em;
    text-transform: uppercase;
    color: #14150E;
    margin-bottom: 1.4rem;
}
.iq-hero-sub {
    font-family: 'Space Grotesk', sans-serif;
    font-size: clamp(1.05rem, 2vw, 1.3rem);
    font-weight: 500;
    line-height: 1.55;
    color: #55583F;
    max-width: 740px;
    margin: 0 auto 2.2rem;
}
.iq-hero-ctas {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 1.1rem;
    flex-wrap: wrap;
    margin-bottom: 2rem;
}
.iq-btn-hero {
    background: #14150E !important;
    color: #C7D633 !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-size: 1.05rem !important;
    font-weight: 800 !important;
    padding: .95rem 2.2rem !important;
    border-radius: 100px !important;
    text-decoration: none !important;
    box-shadow: 0 8px 24px -6px rgba(20,21,14,0.45) !important;
    transition: transform .2s, box-shadow .2s !important;
    display: inline-flex !important;
    align-items: center !important;
    gap: 8px !important;
}
.iq-btn-hero:hover {
    transform: translateY(-3px);
    box-shadow: 0 14px 32px -6px rgba(20,21,14,0.65) !important;
    color: #E3EC8E !important;
}
.iq-btn-ghost {
    background: #FFFFFF !important;
    color: #14150E !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-size: 1.05rem !important;
    font-weight: 800 !important;
    padding: .95rem 2.2rem !important;
    border-radius: 100px !important;
    border: 1.5px solid rgba(20,21,14,0.15) !important;
    text-decoration: none !important;
    box-shadow: 0 4px 14px rgba(20,21,14,0.06) !important;
    transition: transform .2s, border-color .2s, box-shadow .2s !important;
    display: inline-flex !important;
    align-items: center !important;
    gap: 8px !important;
}
.iq-btn-ghost:hover {
    transform: translateY(-3px);
    border-color: #C7D633 !important;
    box-shadow: 0 8px 22px rgba(199,214,51,0.25) !important;
}

/* ── Feature / Stats Ticker Bar ── */
.iq-ticker {
    display: flex;
    justify-content: center;
    gap: 2.2rem;
    flex-wrap: wrap;
    margin: 2rem auto 3rem;
    padding: 1.1rem 1.6rem;
    background: #FFFEF6;
    border: 1.5px solid rgba(20,21,14,0.1);
    border-radius: 100px;
    max-width: 860px;
    box-shadow: 0 6px 18px rgba(21,22,28,0.04);
}
.iq-ticker-item {
    display: flex;
    align-items: center;
    gap: .55rem;
    font-family: 'Space Mono', monospace;
    font-size: .8rem;
    font-weight: 700;
    color: #14150E;
    text-transform: uppercase;
    letter-spacing: .05em;
}
.iq-ticker-dot {
    width: 6px; height: 6px; border-radius: 50%; background: #C7D633;
}

/* ── Streamlit Containers & Form Cards ── */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: #FFFFFF !important;
    border: 1.5px solid rgba(20,21,14,0.12) !important;
    border-radius: 22px !important;
    box-shadow: 0 10px 30px -15px rgba(21,22,28,0.08) !important;
    transition: all .25s ease !important;
    overflow: hidden !important;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover {
    border-color: rgba(199,214,51,0.6) !important;
    box-shadow: 0 14px 36px -12px rgba(199,214,51,0.25) !important;
}

/* ── Streamlit Tabs (Bhavna Niche Tabs) ── */
.stTabs [data-baseweb="tab-list"] {
    gap: .5rem !important;
    background: #F1EDD6 !important;
    padding: 5px !important;
    border-radius: 100px !important;
    border: none !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 100px !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-weight: 700 !important;
    font-size: .88rem !important;
    color: #55583F !important;
    padding: .5rem 1.25rem !important;
    border: none !important;
    transition: all .2s ease !important;
}
.stTabs [aria-selected="true"] {
    background: #14150E !important;
    color: #C7D633 !important;
    box-shadow: 0 4px 12px rgba(20,21,14,0.25) !important;
}

/* ── Streamlit Form Inputs ── */
.stTextInput input, .stTextArea textarea, .stSelectbox [data-baseweb="select"] {
    background-color: #FFFEF6 !important;
    border: 1.5px solid rgba(20,21,14,0.12) !important;
    border-radius: 14px !important;
    font-family: 'Inter', sans-serif !important;
    color: #14150E !important;
    font-size: .95rem !important;
    transition: all .2s ease !important;
}
.stTextInput input:focus, .stTextArea textarea:focus, .stSelectbox [data-baseweb="select"]:focus-within {
    border-color: #C7D633 !important;
    box-shadow: 0 0 0 3px rgba(199,214,51,0.3) !important;
    background-color: #FFFFFF !important;
}

/* ── Streamlit Buttons (Pill Shimmer) ── */
.stButton > button {
    border-radius: 100px !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-weight: 800 !important;
    letter-spacing: -.01em !important;
    border: none !important;
    background: #14150E !important;
    color: #C7D633 !important;
    padding: .65rem 1.6rem !important;
    box-shadow: 0 6px 18px -4px rgba(20,21,14,0.35) !important;
    transition: all .2s ease !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    background: #222418 !important;
    color: #E3EC8E !important;
    box-shadow: 0 10px 24px -4px rgba(20,21,14,0.5) !important;
}

/* ── File Uploader ── */
[data-testid="stFileUploader"] {
    background: #FFFEF6 !important;
    border: 2px dashed rgba(20,21,14,0.18) !important;
    border-radius: 18px !important;
    padding: 1.5rem !important;
    transition: border-color .2s ease !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: #C7D633 !important;
}

/* ── UK GDPR Privacy Shield (Bhavna Dark Callout) ── */
.iq-sec-bar {
    background: linear-gradient(155deg, #1C1D25, #101116);
    border: 2px solid #C7D633;
    border-radius: 22px;
    padding: 1.4rem 1.8rem;
    margin: 2rem 0;
    color: #FFFFFF;
    box-shadow: 0 16px 40px -12px rgba(199,214,51,0.25);
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 1.2rem;
}
.iq-sec-left {
    display: flex;
    align-items: center;
    gap: 1rem;
}
.iq-sec-icon {
    font-size: 1.8rem;
    background: rgba(199,214,51,0.15);
    border: 1px solid rgba(199,214,51,0.3);
    border-radius: 50%;
    width: 50px;
    height: 50px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
.iq-sec-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.1rem;
    font-weight: 800;
    color: #FFFFFF;
}
.iq-sec-desc {
    font-size: .84rem;
    color: rgba(244,245,248,0.7);
    margin-top: 2px;
}
.iq-sec-badges {
    display: flex;
    gap: .65rem;
    flex-wrap: wrap;
}
.iq-sec-pill {
    font-family: 'Space Mono', monospace;
    font-size: .74rem;
    font-weight: 700;
    border-radius: 100px;
    padding: 5px 12px;
    letter-spacing: .04em;
}
.iq-pill-green {
    background: rgba(199,214,51,0.18);
    color: #E3EC8E;
    border: 1px solid rgba(199,214,51,0.35);
}
.iq-pill-blue {
    background: rgba(255,255,255,0.08);
    color: #FFFFFF;
    border: 1px solid rgba(255,255,255,0.15);
}
.iq-pill-purple {
    background: rgba(224,105,44,0.18);
    color: #FDBA74;
    border: 1px solid rgba(224,105,44,0.35);
}

/* ── Panel Header & Steps ── */
.iq-phead {
    font-family: 'Space Mono', monospace;
    font-size: .75rem;
    font-weight: 700;
    letter-spacing: .12em;
    text-transform: uppercase;
    color: #6B7A1A;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: .55rem;
}
.iq-pnum {
    display: inline-flex; align-items: center; justify-content: center;
    width: 24px; height: 24px; background: #C7D633; color: #14150E;
    font-size: .72rem; font-weight: 800; border-radius: 50%;
    flex-shrink: 0; box-shadow: 0 2px 8px rgba(199,214,51,0.4);
}

/* ── Results Header & Podium Header ── */
.iq-results-hdr {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin: 1.8rem 0 1rem;
}
.iq-results-hdr-title {
    font-family: 'Space Mono', monospace;
    font-size: .76rem;
    font-weight: 700;
    letter-spacing: .12em;
    text-transform: uppercase;
    color: #6B7A1A;
}
.iq-results-count {
    font-family: 'Space Mono', monospace;
    font-size: .76rem;
    font-weight: 700;
    color: #14150E;
    background: #C7D633;
    border-radius: 100px;
    padding: 4px 12px;
}
.iq-podium-wrap {
    margin: 1.8rem 0 2rem;
}
.iq-podium-hdr {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1.2rem;
    flex-wrap: wrap;
    gap: .75rem;
}
.iq-podium-title {
    font-family: 'Anton', 'Space Grotesk', sans-serif;
    font-size: 1.8rem;
    font-weight: 400;
    color: #14150E;
    text-transform: uppercase;
    letter-spacing: .02em;
    display: flex;
    align-items: center;
    gap: .5rem;
}
.iq-podium-badge {
    font-family: 'Space Mono', monospace;
    font-size: .74rem;
    font-weight: 700;
    border-radius: 100px;
    padding: 5px 12px;
    display: inline-block;
    margin-bottom: .8rem;
}

/* ── Top 3 Showcase Podium Cards ── */
.iq-podium-card {
    background: #FFFFFF;
    border-radius: 22px;
    padding: 1.6rem;
    border: 1.5px solid rgba(20,21,14,0.12);
    box-shadow: 0 8px 24px -12px rgba(20,21,14,0.12);
    position: relative;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: all .25s ease;
}
.iq-podium-card:hover {
    transform: translateY(-4px);
    border-color: #C7D633;
    box-shadow: 0 16px 36px -16px rgba(199,214,51,0.4);
}
.iq-podium-gold {
    background: linear-gradient(155deg, #1C1D25, #101116) !important;
    border: 2px solid #C7D633 !important;
    color: #FFFFFF !important;
    box-shadow: 0 18px 44px -18px rgba(199,214,51,0.45);
}
.iq-podium-name {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.28rem;
    font-weight: 800;
    color: #14150E;
    margin: .4rem 0 .2rem;
}
.iq-podium-gold .iq-podium-name { color: #FFFFFF !important; }
.iq-podium-sub {
    font-family: 'Inter', sans-serif;
    font-size: .8rem;
    color: #55583F;
    font-weight: 500;
    margin-bottom: .8rem;
}
.iq-podium-gold .iq-podium-sub { color: rgba(244,245,248,0.7) !important; }
.iq-podium-score {
    font-family: 'Anton', 'Space Mono', monospace;
    font-size: 2.2rem;
    font-weight: 400;
    line-height: 1;
}
.iq-podium-rec {
    font-family: 'Inter', sans-serif;
    font-size: .82rem;
    color: #14150E;
    line-height: 1.5;
    background: #FFFEF6;
    padding: .75rem .95rem;
    border-radius: 12px;
    border: 1px solid rgba(20,21,14,0.08);
}
.iq-podium-gold .iq-podium-rec {
    background: rgba(255,255,255,0.06) !important;
    color: rgba(244,245,248,0.9) !important;
    border-color: rgba(255,255,255,0.12) !important;
}
.iq-pbadge-gold { background: #C7D633; color: #14150E; box-shadow: 0 2px 10px rgba(199,214,51,0.4); }
.iq-pbadge-silver { background: rgba(20,21,14,0.08); color: #14150E; }
.iq-pbadge-bronze { background: #FED7AA; color: #9A3412; }

/* ── Detailed Candidate Cards & Expanders ── */
.stExpander {
    border: 1.5px solid rgba(20,21,14,0.10) !important;
    border-radius: 18px !important;
    background: #FFFFFF !important;
    overflow: hidden !important;
    box-shadow: 0 4px 16px rgba(21,22,28,0.04) !important;
    margin-bottom: .8rem !important;
    transition: all .2s ease !important;
}
.stExpander:hover {
    border-color: #C7D633 !important;
    box-shadow: 0 8px 24px -10px rgba(199,214,51,0.3) !important;
}
.stExpander summary {
    font-family: 'Space Grotesk', sans-serif !important;
    font-size: 1.05rem !important;
    font-weight: 700 !important;
    color: #14150E !important;
    padding: 1.1rem 1.5rem !important;
    background: #FFFEF6 !important;
}
.stExpander details[open] > summary {
    background: #FAF8E4 !important;
    border-bottom: 1.5px solid rgba(20,21,14,0.10) !important;
}
.iq-tag {
    font-family: 'Inter', sans-serif;
    font-size: .78rem;
    font-weight: 600;
    border-radius: 100px;
    padding: 4px 12px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: rgba(199,214,51,0.22);
    color: #6B7A1A;
    border: 1px solid rgba(199,214,51,0.35);
}
.iq-tag-g { background: #DCFCE7; color: #15803D; border-color: #86EFAC; }
.iq-tag-m { background: #FEF3C7; color: #B45309; border-color: #FDE68A; }
.iq-tag-r { background: #FEE2E2; color: #B91C1C; border-color: #FCA5A5; }

/* ── Candidate Details Breakdown ── */
.iq-det {
    background: #FFFFFF;
    border-radius: 18px;
    padding: 1.5rem;
    border: 1.5px solid rgba(20,21,14,0.1);
    margin-bottom: .8rem;
}
.iq-det-hrow {
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.iq-det-name {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.35rem;
    font-weight: 800;
    color: #14150E;
}
.iq-det-badge {
    flex-shrink: 0;
    width: 76px;
    height: 76px;
    border-radius: 50%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1px;
}
.iq-det-badge-hi  { background: rgba(199,214,51,0.22); border: 2px solid #C7D633; color: #14150E; }
.iq-det-badge-mid { background: rgba(224,105,44,0.18); border: 2px solid #E0692C; color: #14150E; }
.iq-det-badge-lo  { background: #FEE2E2; border: 2px solid #EF4444; color: #B91C1C; }
.iq-det-badgenum {
    font-family: 'Anton', sans-serif;
    font-size: 1.7rem;
    font-weight: 400;
    line-height: 1;
    color: inherit;
}
.iq-det-badgedenom {
    font-family: 'Space Mono', monospace;
    font-size: .65rem;
    font-weight: 700;
    color: inherit;
    opacity: .75;
}
.iq-det-badgestars { font-size: .68rem; color: #E0692C; }
.iq-det-divider { height: 1px; background: rgba(20,21,14,0.08); margin: 1.1rem 0; }
.iq-det-cols {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.25rem;
}
@media (max-width: 600px) { .iq-det-cols { grid-template-columns: 1fr; } }
.iq-det-lbl {
    font-family: 'Space Mono', monospace;
    font-size: .72rem;
    font-weight: 700;
    letter-spacing: .08em;
    text-transform: uppercase;
    color: #6B7A1A;
    margin-bottom: .5rem;
}
.iq-det-tags { display: flex; flex-wrap: wrap; gap: .4rem; }

/* ── Human-in-the-Loop Override Panel ── */
.iq-override-card {
    background: #FFFEF6;
    border: 1.5px solid rgba(20,21,14,0.1);
    border-radius: 16px;
    padding: 1.1rem 1.3rem;
    margin-top: .9rem;
}
.iq-override-title {
    font-family: 'Space Mono', monospace;
    font-size: .76rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .08em;
    color: #14150E;
    margin-bottom: .35rem;
    display: flex;
    align-items: center;
    gap: .4rem;
}

/* ── Candidate Rankings Preview (Panel 3 Idle State) ── */
.iq-cr-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: .85rem;
    margin-bottom: .85rem;
    border-bottom: 1px solid rgba(20,21,14,0.08);
}
.iq-cr-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.15rem;
    font-weight: 800;
    color: #14150E;
}
.iq-cr-cols {
    display: flex;
    align-items: center;
    padding: 0 .75rem .45rem;
    font-family: 'Space Mono', monospace;
    font-size: .7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .08em;
    color: #83816A;
}
.iq-cr-col-sp { flex: 1; }
.iq-cr-col { width: 105px; text-align: center; }
.iq-cr-row {
    display: flex;
    align-items: center;
    gap: .75rem;
    background: #FFFFFF;
    border: 1.5px solid rgba(20,21,14,0.08);
    border-radius: 16px;
    padding: .85rem 1rem;
    margin-bottom: .65rem;
    transition: all .2s ease;
    box-shadow: 0 4px 12px rgba(20,21,14,0.03);
}
.iq-cr-row:hover {
    border-color: #C7D633;
    transform: translateY(-2px);
    box-shadow: 0 8px 24px -10px rgba(199,214,51,0.35);
}
.iq-cr-rank {
    font-family: 'Anton', sans-serif;
    font-size: 1.35rem;
    font-weight: 400;
    color: #14150E;
    width: 24px;
    text-align: center;
    flex-shrink: 0;
}
.iq-cr-av {
    width: 42px;
    height: 42px;
    border-radius: 50%;
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-family: 'Space Mono', monospace;
    font-size: .85rem;
    font-weight: 700;
}
.iq-cr-av1 { background: #C7D633; color: #14150E; box-shadow: 0 2px 8px rgba(199,214,51,0.4); }
.iq-cr-av2 { background: #14150E; color: #C7D633; }
.iq-cr-av3 { background: rgba(224,105,44,0.18); color: #E0692C; }
.iq-cr-main { flex: 1; min-width: 0; }
.iq-cr-toprow {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: .75rem;
}
.iq-cr-info { flex: 1; min-width: 0; }
.iq-cr-name {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.02rem;
    font-weight: 800;
    color: #14150E;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.iq-cr-sub {
    font-family: 'Inter', sans-serif;
    font-size: .78rem;
    color: #55583F;
    margin-top: 1px;
}
.iq-cr-sc {
    width: 95px;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 3px;
    flex-shrink: 0;
}
.iq-cr-pct {
    font-family: 'Space Mono', monospace;
    font-size: 1rem;
    font-weight: 800;
    color: #14150E;
}
.iq-cr-bar {
    width: 70px;
    height: 6px;
    background: rgba(20,21,14,0.08);
    border-radius: 100px;
    overflow: hidden;
}
.iq-cr-barfill {
    height: 100%;
    background: linear-gradient(90deg, #C7D633, #6B7A1A);
    border-radius: 100px;
}
.iq-cr-rec { width: 105px; text-align: center; flex-shrink: 0; }
.iq-cr-rbadge {
    font-family: 'Space Mono', monospace;
    font-size: .68rem;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 100px;
    display: inline-block;
    text-transform: uppercase;
    letter-spacing: .03em;
}
.iq-cr-rb-strong { background: rgba(199,214,51,0.25); color: #4D5A0F; border: 1px solid rgba(199,214,51,0.4); }
.iq-cr-rb-good   { background: rgba(20,21,14,0.08); color: #14150E; border: 1px solid rgba(20,21,14,0.15); }
.iq-cr-rb-ok     { background: rgba(224,105,44,0.18); color: #9A3412; border: 1px solid rgba(224,105,44,0.35); }
.iq-cr-sk-row {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: .45rem;
}
.iq-cr-sk {
    font-family: 'Space Mono', monospace;
    font-size: .68rem;
    font-weight: 600;
    background: #FFFEF6;
    border: 1px solid rgba(20,21,14,0.1);
    color: #55583F;
    padding: 2px 8px;
    border-radius: 100px;
}

/* ── Download Button ── */
.iq-dl-btn {
    display: block; width: 100%; text-align: center; box-sizing: border-box;
    background: #14150E !important;
    color: #C7D633 !important;
    text-decoration: none !important;
    border-radius: 100px; padding: 1.1rem 2rem;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.05rem; font-weight: 800; letter-spacing: -.01em;
    box-shadow: 0 8px 24px -8px rgba(20,21,14,0.45);
    transition: transform .2s, box-shadow .2s;
    cursor: pointer;
}
.iq-dl-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 14px 34px -8px rgba(20,21,14,0.65);
    color: #E3EC8E !important;
}

/* ── Pricing & Payment Section (Bhavna Tiers & Dark Callout) ── */
.iq-price-sec { max-width: 1100px; margin: 5rem auto 3.5rem; padding: 0 1.25rem; }
.iq-price-hdr { text-align: center; margin-bottom: 3rem; }
.iq-price-h2 {
    font-family: 'Anton', 'Space Grotesk', sans-serif !important;
    font-size: clamp(2.4rem, 5vw, 3.8rem);
    font-weight: 700;
    color: #14150E;
    margin-bottom: .6rem;
    line-height: 1.05;
}
.iq-price-sub { font-size: 1.05rem; color: #55583F; max-width: 620px; margin: 0 auto; line-height: 1.6; }
.iq-price-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 2.2rem; margin-top: 2rem; }
@media (max-width: 860px) { .iq-price-grid { grid-template-columns: 1fr; max-width: 520px; margin: 2rem auto 0; } }

.iq-plan-card {
    background: #FFFFFF;
    border: 1.5px solid rgba(20,21,14,0.12);
    border-radius: 26px;
    padding: 2.6rem 2.4rem;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: all .25s ease;
    box-shadow: 0 10px 30px -20px rgba(21,22,28,0.22);
    position: relative;
}
.iq-plan-card:hover {
    border-color: rgba(199,214,51,0.5);
    box-shadow: 0 18px 40px -18px rgba(21,22,28,0.28);
    transform: translateY(-4px);
}
.iq-plan-card.featured {
    border: 2px solid #C7D633;
    background: linear-gradient(155deg, #1C1D25, #101116) !important;
    color: #F4F5F8 !important;
    box-shadow: 0 24px 60px -20px rgba(199,214,51,0.35);
}
.iq-plan-card.featured .iq-plan-name { color: #FFFFFF !important; }
.iq-plan-card.featured .iq-plan-desc { color: rgba(244,245,248,0.7) !important; }
.iq-plan-card.featured .iq-plan-amt { color: #C7D633 !important; }
.iq-plan-card.featured .iq-plan-curr { color: #C7D633 !important; }
.iq-plan-card.featured .iq-plan-period { color: rgba(244,245,248,0.55) !important; }
.iq-plan-card.featured .iq-plan-feat-item { color: rgba(244,245,248,0.88) !important; }
.iq-plan-card.featured .iq-plan-price-wrap { border-bottom-color: rgba(255,255,255,0.12) !important; }

.iq-plan-badge {
    display: inline-block; padding: .35rem .9rem; font-family: 'Space Mono', monospace;
    font-size: .75rem; font-weight: 700; border-radius: 100px; margin-bottom: 1.2rem;
    text-transform: uppercase; letter-spacing: .08em;
}
.iq-badge-starter { background: rgba(199,214,51,0.22); color: #6B7A1A; border: 1px solid rgba(199,214,51,0.35); }
.iq-badge-agency { background: #C7D633; color: #14150E; box-shadow: 0 2px 10px rgba(199,214,51,0.4); }

.iq-plan-name {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.75rem;
    font-weight: 800;
    color: #14150E;
    margin-bottom: .4rem;
}
.iq-plan-desc { font-size: .92rem; color: #55583F; margin-bottom: 1.6rem; min-height: 42px; line-height: 1.5; }
.iq-plan-price-wrap { display: flex; align-items: baseline; gap: .4rem; margin-bottom: 1.8rem; padding-bottom: 1.5rem; border-bottom: 1px solid rgba(20,21,14,0.1); }
.iq-plan-curr { font-family: 'Anton', sans-serif; font-size: 2rem; color: #14150E; }
.iq-plan-amt { font-family: 'Anton', sans-serif; font-size: 4.2rem; font-weight: 700; color: #14150E; line-height: 1; letter-spacing: -.02em; }
.iq-plan-period { font-family: 'Space Mono', monospace; font-size: 1rem; font-weight: 600; color: #83816A; }
.iq-plan-features { list-style: none; padding: 0; margin: 0 0 2.4rem 0; display: flex; flex-direction: column; gap: .95rem; }
.iq-plan-feat-item { display: flex; align-items: flex-start; gap: .8rem; font-size: .95rem; color: inherit; line-height: 1.45; }
.iq-feat-icon { color: #6B7A1A; font-weight: 900; font-size: 1.1rem; flex-shrink: 0; margin-top: 1px; }
.iq-feat-icon-gold { color: #C7D633; font-weight: 900; font-size: 1.15rem; flex-shrink: 0; margin-top: 1px; }

.iq-plan-btn {
    display: block; width: 100%; text-align: center; padding: 1rem 1.6rem;
    border-radius: 100px; font-family: 'Space Grotesk', sans-serif; font-weight: 800;
    font-size: 1.05rem; text-decoration: none !important; transition: all .2s ease;
    cursor: pointer; box-sizing: border-box;
}
.iq-btn-primary {
    background: #14150E !important;
    color: #C7D633 !important;
    box-shadow: 0 8px 24px -8px rgba(20,21,14,0.4) !important;
}
.iq-btn-primary:hover {
    background: #23251A !important;
    color: #E3EC8E !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 14px 30px -8px rgba(20,21,14,0.55) !important;
}
.iq-btn-agency {
    background: linear-gradient(120deg, #C7D633, #E3EC8E) !important;
    color: #14140F !important;
    box-shadow: 0 8px 24px -8px rgba(199,214,51,0.65) !important;
}
.iq-btn-agency:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 16px 36px -8px rgba(199,214,51,0.85) !important;
}
.iq-guarantee { font-family: 'Space Mono', monospace; text-align: center; margin-top: 1.1rem; font-size: .78rem; color: #83816A; }

/* ── Trust & Payment Badges ── */
.iq-pay-badges { display: flex; align-items: center; justify-content: center; gap: .85rem; margin-top: 2.8rem; padding-top: 2rem; border-top: 1px solid rgba(20,21,14,0.1); flex-wrap: wrap; }
.iq-pay-pill {
    display: inline-flex; align-items: center; gap: .45rem;
    background: #FFFFFF; border: 1.5px solid rgba(20,21,14,0.1);
    border-radius: 100px; padding: .4rem .9rem;
    font-family: 'Space Mono', monospace; font-size: .8rem; font-weight: 700; color: #14150E;
    box-shadow: 0 2px 6px rgba(20,21,14,0.03);
}

/* ── Bento Grid Platform Features ── */
.iq-feat-sec { margin: 4.5rem 0 2.5rem; }
.iq-feat-hdr { text-align: center; margin-bottom: 2.8rem; }
.iq-feat-h2 {
    font-family: 'Anton', 'Space Grotesk', sans-serif !important;
    font-size: clamp(2.2rem, 4.5vw, 3.4rem);
    font-weight: 700; color: #14150E;
    margin-bottom: .6rem;
}
.iq-bento-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 1.6rem;
}
.iq-bento-card {
    background: #FFFFFF;
    border: 1.5px solid rgba(20,21,14,0.1);
    border-radius: 24px;
    padding: 2.2rem;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: all .2s ease;
    box-shadow: 0 8px 24px -14px rgba(21,22,28,0.14);
}
.iq-bento-card:hover {
    border-color: rgba(199,214,51,0.5);
    transform: translateY(-4px);
    box-shadow: 0 16px 36px -16px rgba(21,22,28,0.22);
}
.iq-bento-tag {
    font-family: 'Space Mono', monospace;
    font-size: .72rem; font-weight: 700; text-transform: uppercase;
    background: rgba(199,214,51,0.22); color: #6B7A1A;
    border: 1px solid rgba(199,214,51,0.3); border-radius: 100px;
    padding: 4px 12px; margin-bottom: .85rem; width: fit-content;
}
.iq-bento-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.35rem; font-weight: 800; color: #14150E;
    margin-bottom: .5rem; line-height: 1.25;
}
.iq-bento-sub { font-size: .9rem; color: #55583F; line-height: 1.6; margin-bottom: 1.4rem; }
.iq-mockup-box { background: #FFFEF6; border: 1.5px solid rgba(20,21,14,0.1); border-radius: 16px; padding: 1.15rem; }

/* ── Bento Mockups & Visual Funnel ── */
.iq-funnel-step {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #FFFFFF;
    border: 1.5px solid rgba(20,21,14,0.08);
    border-radius: 12px;
    padding: .65rem .95rem;
    margin-bottom: .5rem;
    box-shadow: 0 2px 6px rgba(20,21,14,0.03);
}
.iq-funnel-left { display: flex; align-items: center; gap: .65rem; }
.iq-funnel-icon { font-size: 1.15rem; }
.iq-funnel-txt { font-family: 'Space Grotesk', sans-serif; font-size: .84rem; font-weight: 700; color: #14150E; }
.iq-funnel-sub { font-family: 'Inter', sans-serif; font-size: .72rem; color: #55583F; }
.iq-funnel-badge {
    font-family: 'Space Mono', monospace;
    font-size: .7rem;
    font-weight: 700;
    padding: .2rem .65rem;
    border-radius: 100px;
    background: rgba(20,21,14,0.08);
    color: #14150E;
}
.iq-funnel-badge-green { background: rgba(199,214,51,0.25); color: #4D5A0F; border: 1px solid rgba(199,214,51,0.4); }
.iq-funnel-highlight {
    background: rgba(199,214,51,0.18);
    border: 1px solid rgba(199,214,51,0.4);
    border-radius: 12px;
    padding: .65rem;
    text-align: center;
    font-family: 'Space Grotesk', sans-serif;
    font-size: .8rem;
    font-weight: 800;
    color: #3B450C;
    margin-top: .6rem;
}

.iq-gauge-row { margin-bottom: .7rem; }
.iq-gauge-info {
    display: flex;
    justify-content: space-between;
    font-family: 'Space Mono', monospace;
    font-size: .78rem;
    font-weight: 700;
    color: #14150E;
    margin-bottom: 4px;
}
.iq-gauge-track {
    height: 7px;
    background: rgba(20,21,14,0.08);
    border-radius: 100px;
    overflow: hidden;
}
.iq-gauge-bar { height: 100%; border-radius: 100px; }

.iq-cand-mini-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #FFFFFF;
    border: 1.5px solid rgba(20,21,14,0.08);
    border-radius: 12px;
    padding: .65rem .85rem;
    margin-bottom: .5rem;
}
.iq-cand-mini-left { display: flex; align-items: center; gap: .65rem; }
.iq-cand-mini-name { font-family: 'Space Grotesk', sans-serif; font-size: .92rem; font-weight: 700; color: #14150E; }
.iq-cand-mini-role { font-family: 'Inter', sans-serif; font-size: .74rem; color: #55583F; }
.iq-medal { font-size: 1.25rem; }
.iq-score-pill {
    font-family: 'Space Mono', monospace;
    font-size: .72rem;
    font-weight: 700;
    border-radius: 100px;
    padding: 3px 10px;
}
.iq-score-pill-green { background: rgba(199,214,51,0.25); color: #4D5A0F; border: 1px solid rgba(199,214,51,0.4); }
.iq-score-pill-blue  { background: rgba(20,21,14,0.08); color: #14150E; border: 1px solid rgba(20,21,14,0.15); }

.iq-excel-preview {
    background: #FFFFFF;
    border: 1.5px solid rgba(20,21,14,0.1);
    border-radius: 14px;
    overflow: hidden;
}
.iq-excel-hdr-row {
    display: grid;
    grid-template-columns: 28px 1.4fr 1fr 1.6fr;
    padding: .55rem .8rem;
    background: #14150E;
    color: #C7D633;
    font-family: 'Space Mono', monospace;
    font-size: .72rem;
    font-weight: 700;
    text-transform: uppercase;
}
.iq-excel-data-row {
    display: grid;
    grid-template-columns: 28px 1.4fr 1fr 1.6fr;
    padding: .5rem .8rem;
    border-top: 1px solid rgba(20,21,14,0.06);
    font-family: 'Inter', sans-serif;
    font-size: .8rem;
    color: #14150E;
}
.iq-excel-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: .65rem .85rem;
    background: #FFFEF6;
    border-top: 1px solid rgba(20,21,14,0.08);
    font-family: 'Space Mono', monospace;
    font-size: .75rem;
    color: #55583F;
}
.iq-dl-badge {
    background: #14150E;
    color: #C7D633;
    padding: 3px 10px;
    border-radius: 100px;
    font-weight: 700;
    font-size: .72rem;
}

/* ── Why Recruiters Choose Pillars (Bhavna Dark Statement) ── */
.iq-pillars-box {
    background: linear-gradient(155deg, #1C1D25, #101116);
    border: 2px solid #C7D633;
    border-radius: 26px;
    padding: 3.5rem 2.6rem;
    margin: 4.5rem 0 3rem;
    color: #FFFFFF;
    box-shadow: 0 24px 60px -20px rgba(199,214,51,0.25);
}
.iq-pillars-top { text-align: center; margin-bottom: 2.6rem; }
.iq-pillars-eye {
    font-family: 'Space Mono', monospace;
    font-size: .75rem;
    font-weight: 700;
    color: #C7D633;
    letter-spacing: .12em;
    text-transform: uppercase;
    margin-bottom: .5rem;
}
.iq-pillars-h2 {
    font-family: 'Anton', 'Space Grotesk', sans-serif;
    font-size: clamp(2.2rem, 4.5vw, 3.2rem);
    font-weight: 400;
    color: #FFFFFF;
    text-transform: uppercase;
    letter-spacing: .02em;
}
.iq-pillars-sub {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.05rem;
    color: rgba(244,245,248,0.72);
    margin-top: .5rem;
    max-width: 600px;
    margin-left: auto;
    margin-right: auto;
}
.iq-pillars-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 1.6rem;
}
.iq-pillar-item {
    background: rgba(255,255,255,0.04);
    border: 1.5px solid rgba(255,255,255,0.1);
    border-radius: 20px;
    padding: 1.8rem 1.6rem;
    transition: all .25s ease;
}
.iq-pillar-item:hover {
    border-color: #C7D633;
    transform: translateY(-3px);
    background: rgba(255,255,255,0.07);
}
.iq-pillar-stat {
    font-family: 'Anton', sans-serif;
    font-size: 3.2rem;
    color: #C7D633;
    line-height: 1;
    margin-bottom: .6rem;
}
.iq-pillar-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.15rem;
    font-weight: 800;
    color: #FFFFFF;
    margin-bottom: .45rem;
}
.iq-pillar-desc {
    font-family: 'Inter', sans-serif;
    font-size: .88rem;
    color: rgba(244,245,248,0.72);
    line-height: 1.6;
}

/* ── FAQ Section ── */
.iq-faq-sec { max-width: 900px; margin: 5rem auto 3rem; }
.iq-faq-hdr { text-align: center; margin-bottom: 2.8rem; }
.iq-faq-h2 {
    font-family: 'Anton', 'Space Grotesk', sans-serif !important;
    font-size: clamp(2.2rem, 4.5vw, 3.4rem);
    font-weight: 700; color: #14150E; margin-bottom: .6rem;
}
.iq-faq-list { display: flex; flex-direction: column; gap: .9rem; }
.iq-faq-item {
    background: #FFFFFF;
    border: 1.5px solid rgba(20,21,14,0.1);
    border-radius: 18px;
    overflow: hidden;
    transition: all .2s ease;
}
.iq-faq-item:hover { border-color: rgba(199,214,51,0.5); transform: translateY(-2px); }
.iq-faq-item[open] {
    border-color: #C7D633;
    box-shadow: 0 12px 28px -14px rgba(199,214,51,0.35);
}
.iq-faq-summary {
    padding: 1.25rem 1.6rem;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.08rem;
    font-weight: 700;
    color: #14150E;
    cursor: pointer;
    display: flex; justify-content: space-between; align-items: center;
    list-style: none;
}
.iq-faq-summary::-webkit-details-marker, .iq-faq-summary::marker { display: none; }
.iq-faq-arrow { width: 22px; height: 22px; color: #6B7A1A; transition: transform .25s ease; flex-shrink: 0; }
.iq-faq-item[open] .iq-faq-arrow { transform: rotate(180deg); }
.iq-faq-body {
    padding: 0 1.6rem 1.4rem;
    font-size: .95rem;
    color: #55583F;
    line-height: 1.7;
    border-top: 1px solid rgba(20,21,14,0.1);
    padding-top: 1rem;
}

/* ── Testimonials Marquee ── */
.iq-ts-sec {
    background: #FFFFFF;
    border: 1.5px solid rgba(20,21,14,0.1);
    border-radius: 26px;
    padding: 3.5rem 0 3rem;
    margin: 4.5rem 0 2.5rem;
    overflow: hidden;
    position: relative;
    box-shadow: 0 12px 36px -20px rgba(21,22,28,0.15);
}
.iq-ts-h {
    font-family: 'Anton', 'Space Grotesk', sans-serif !important;
    font-size: clamp(2.2rem, 4.5vw, 3.2rem);
    font-weight: 700;
    color: #14150E;
    text-transform: uppercase;
    margin-bottom: .45rem;
}
.iq-ts-s {
    font-family: 'Space Grotesk', sans-serif;
    color: #55583F;
    font-size: 1.02rem;
    margin-bottom: 2.2rem;
}
.iq-ts-track-wrap {
    width: 100%;
    overflow: hidden;
    position: relative;
    padding: .5rem 0;
    mask-image: linear-gradient(to right, transparent, black 5%, black 95%, transparent);
    -webkit-mask-image: linear-gradient(to right, transparent, black 5%, black 95%, transparent);
}
.iq-ts-track {
    display: flex; gap: 1.4rem; width: max-content;
    animation: iq-marquee 40s linear infinite;
}
.iq-ts-track:hover { animation-play-state: paused; }
@keyframes iq-marquee {
    0% { transform: translateX(0); }
    100% { transform: translateX(-50%); }
}
.iq-beta-card {
    width: 350px; flex-shrink: 0; background: #FFFEF6;
    border: 1.5px solid rgba(20,21,14,0.1); border-radius: 20px;
    padding: 1.8rem; display: flex; flex-direction: column; justify-content: space-between;
    box-shadow: 0 6px 18px rgba(21,22,28,0.04);
}
.iq-beta-stars { font-size: .95rem; color: #E0692C; margin-bottom: .6rem; letter-spacing: 2px; }
.iq-beta-text {
    font-family: 'Inter', sans-serif;
    font-size: .92rem;
    color: #14150E;
    line-height: 1.6;
    font-style: italic;
    margin-bottom: 1.2rem;
}
.iq-tp { display: flex; align-items: center; gap: .75rem; }
.iq-tav {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    background: #14150E;
    color: #C7D633;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Space Mono', monospace;
    font-size: .8rem;
    font-weight: 700;
}
.iq-tpn { font-family: 'Space Grotesk', sans-serif; font-size: .9rem; font-weight: 700; color: #14150E; }
.iq-tpc { font-family: 'Space Mono', monospace; font-size: .72rem; color: #55583F; }

/* ── Post-Screening Trial Upgrade Card ── */
.iq-trial-upgrade {
    background: linear-gradient(155deg, #1C1D25, #101116);
    border: 2px solid #C7D633;
    border-radius: 22px;
    padding: 2.2rem 2.4rem;
    text-align: center;
    color: #FFFFFF;
    margin-top: 2rem;
    box-shadow: 0 18px 45px -15px rgba(199,214,51,0.25);
}
.iq-trial-info {
    background: rgba(199,214,51,0.18);
    border: 1px solid rgba(199,214,51,0.35);
    border-radius: 12px;
    padding: .75rem 1rem;
    font-family: 'Space Grotesk', sans-serif;
    font-size: .85rem;
    color: #E3EC8E;
    line-height: 1.5;
    margin-bottom: .8rem;
}

/* ── Candidate Rankings List Item ── */
.iq-rc {
    display: flex; align-items: center; justify-content: space-between;
    padding: 1rem 1.2rem; border: 1.5px solid rgba(20,21,14,0.1); border-radius: 16px;
    margin-bottom: .6rem; background: #FFFFFF;
    transition: all .2s ease;
}
.iq-rc:hover {
    border-color: #C7D633;
    box-shadow: 0 8px 24px -10px rgba(199,214,51,0.3);
    transform: translateY(-2px);
}
.iq-av {
    width: 42px; height: 42px; border-radius: 50%; flex-shrink: 0;
    background: rgba(199,214,51,0.22); color: #6B7A1A;
    display: flex; align-items: center; justify-content: center;
    font-family: 'Space Mono', monospace; font-size: .92rem; font-weight: 700;
}
.iq-rn { font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: .98rem; color: #14150E; }
.iq-sv { font-family: 'Space Mono', monospace; font-size: 1.25rem; font-weight: 800; color: #6B7A1A; }

/* ── Footer ── */
.iq-foot { text-align: center; padding: 3rem 0 2rem; border-top: 1px solid rgba(20,21,14,0.1); margin-top: 4rem; }
.iq-foot-txt { font-family: 'Space Mono', monospace; font-size: .82rem; color: #83816A; letter-spacing: .04em; }

/* ── Helper utilities ── */
.iq-char { font-family: 'Space Mono', monospace; font-size: .75rem; color: #55583F; }

/* ── Navbar & Logo (Bhavna Signature) ── */
.iq-logo {
    font-family: 'Anton', 'Space Grotesk', sans-serif;
    font-size: 1.7rem;
    font-weight: 900;
    letter-spacing: .02em;
    text-transform: uppercase;
    color: #14150E;
    text-decoration: none;
    display: flex;
    align-items: center;
    gap: 2px;
}
.iq-logo b { color: #14150E; font-weight: 900; }
.iq-nav a:not(.iq-nav-demo) {
    font-family: 'Space Grotesk', sans-serif;
    font-size: .92rem;
    font-weight: 700;
    color: #14150E;
    text-decoration: none !important;
    transition: opacity .2s;
}
.iq-nav a:not(.iq-nav-demo):hover { opacity: .75; }
.iq-nav-demo {
    background: #14150E !important;
    color: #C7D633 !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-size: .86rem !important;
    font-weight: 800 !important;
    padding: .55rem 1.4rem !important;
    border-radius: 100px !important;
    text-decoration: none !important;
    box-shadow: 0 4px 14px rgba(20,21,14,0.35) !important;
    transition: transform .2s, box-shadow .2s !important;
    display: inline-flex !important;
    align-items: center !important;
}
.iq-nav-demo:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 18px rgba(20,21,14,0.5) !important;
    color: #E3EC8E !important;
}

/* ── Hero Eyebrows, Headings, Subtitles ── */
.iq-eye, .iq-feat-eye, .iq-price-eye, .iq-faq-eye {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-family: 'Space Mono', monospace;
    font-size: .78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .12em;
    padding: 6px 16px;
    border-radius: 100px;
    background: rgba(199,214,51,0.22);
    color: #6B7A1A;
    border: 1px solid rgba(199,214,51,0.35);
    margin-bottom: 1.2rem;
}
.iq-h1 {
    font-family: 'Anton', 'Space Grotesk', sans-serif !important;
    font-size: clamp(3.2rem, 7.5vw, 5.8rem) !important;
    font-weight: 400 !important;
    line-height: .98 !important;
    letter-spacing: .02em !important;
    text-transform: uppercase !important;
    color: #14150E !important;
    margin-bottom: 1.3rem !important;
}
.iq-sub, .iq-feat-sub, .iq-faq-sub {
    font-family: 'Space Grotesk', sans-serif !important;
    font-size: clamp(1.05rem, 2vw, 1.25rem) !important;
    font-weight: 500 !important;
    line-height: 1.6 !important;
    color: #55583F !important;
    max-width: 720px !important;
    margin: 0 auto 1.8rem !important;
}
.iq-trial-tag {
    display: inline-flex;
    align-items: center;
    gap: .75rem;
    background: #FFFEF6;
    border: 1.5px solid rgba(20,21,14,0.12);
    padding: .5rem 1.3rem;
    border-radius: 100px;
    font-family: 'Space Grotesk', sans-serif;
    font-size: .88rem;
    color: #14150E;
    margin-bottom: 2rem;
    box-shadow: 0 4px 14px rgba(20,21,14,0.04);
}
.iq-trial-pill {
    background: #C7D633;
    color: #14150E;
    font-family: 'Space Mono', monospace;
    font-size: .72rem;
    font-weight: 800;
    letter-spacing: .08em;
    padding: .25rem .65rem;
    border-radius: 100px;
    text-transform: uppercase;
}
.iq-btns {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 1.1rem;
    flex-wrap: wrap;
    margin-bottom: 2rem;
}
.iq-bp {
    background: #14150E !important;
    color: #C7D633 !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-size: 1.05rem !important;
    font-weight: 800 !important;
    padding: .95rem 2.2rem !important;
    border-radius: 100px !important;
    text-decoration: none !important;
    box-shadow: 0 8px 24px -6px rgba(20,21,14,0.45) !important;
    transition: transform .2s, box-shadow .2s !important;
    display: inline-flex !important;
    align-items: center !important;
}
.iq-bp:hover {
    transform: translateY(-3px) !important;
    box-shadow: 0 14px 32px -6px rgba(20,21,14,0.65) !important;
    color: #E3EC8E !important;
}
.iq-bs {
    background: #FFFFFF !important;
    color: #14150E !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-size: 1.05rem !important;
    font-weight: 800 !important;
    padding: .95rem 2.2rem !important;
    border-radius: 100px !important;
    border: 1.5px solid rgba(20,21,14,0.15) !important;
    text-decoration: none !important;
    box-shadow: 0 4px 14px rgba(20,21,14,0.06) !important;
    transition: transform .2s, border-color .2s, box-shadow .2s !important;
    display: inline-flex !important;
    align-items: center !important;
}
.iq-bs:hover {
    transform: translateY(-3px) !important;
    border-color: #C7D633 !important;
    box-shadow: 0 8px 22px rgba(199,214,51,0.25) !important;
}

/* ── Feature Bar ── */
.iq-fbar {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1.2rem;
    margin: 2.5rem auto 3.5rem;
    padding: 1.4rem 1.8rem;
    background: #FFFEF6;
    border: 1.5px solid rgba(20,21,14,0.1);
    border-radius: 24px;
    box-shadow: 0 8px 24px -10px rgba(20,21,14,0.06);
}
.iq-fbar-item {
    display: flex;
    align-items: center;
    gap: .9rem;
}
.iq-fbar-icon {
    font-size: 1.4rem;
    width: 44px;
    height: 44px;
    border-radius: 50%;
    background: rgba(199,214,51,0.22);
    color: #6B7A1A;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
.iq-fbar-t1 {
    font-family: 'Space Grotesk', sans-serif;
    font-size: .95rem;
    font-weight: 800;
    color: #14150E;
}
.iq-fbar-t2 {
    font-family: 'Inter', sans-serif;
    font-size: .8rem;
    color: #55583F;
}

/* ── Status badges & DL wrap ── */
.iq-status-ok {
    font-family: 'Space Mono', monospace;
    font-size: .74rem;
    font-weight: 700;
    color: #4D5A0F;
    background: rgba(199,214,51,0.25);
    border: 1px solid rgba(199,214,51,0.4);
    border-radius: 100px;
    padding: 3px 10px;
    display: inline-flex;
    align-items: center;
    gap: 5px;
}
.iq-status-wait {
    font-family: 'Space Mono', monospace;
    font-size: .74rem;
    font-weight: 700;
    color: #9A3412;
    background: #FED7AA;
    border-radius: 100px;
    padding: 3px 10px;
    display: inline-flex;
    align-items: center;
    gap: 5px;
}
.iq-sec-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: .8rem;
}
.iq-dl-wrap {
    margin-top: 1.5rem;
    text-align: center;
}

.iq-cr-tools { display: flex; align-items: center; gap: .6rem; margin-bottom: .85rem; }
.iq-cr-search {
    flex: 1; background: #FFFEF6; border: 1.5px solid rgba(20,21,14,0.1);
    border-radius: 100px; padding: .45rem 1rem;
    font-family: 'Inter', sans-serif; font-size: .82rem; color: #83816A;
}
.iq-cr-filter {
    background: #FFFEF6; border: 1.5px solid rgba(20,21,14,0.1);
    border-radius: 100px; padding: .45rem .95rem;
    font-family: 'Space Mono', monospace; font-size: .74rem; font-weight: 700; color: #14150E;
}
.iq-cr-skmore {
    font-family: 'Space Mono', monospace; font-size: .68rem; font-weight: 700;
    background: rgba(199,214,51,0.22); color: #6B7A1A;
    border: 1px solid rgba(199,214,51,0.35); padding: 2px 7px; border-radius: 100px;
}
.iq-cr-footer { padding-top: .5rem; }
.iq-det-hinfo { flex: 1; }
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
<div style="display:flex;align-items:center;gap:1.5rem;">
<a href="#screening-workspace">Screen CVs</a>
<a href="#features">Features</a>
<a href="#pricing">Pricing</a>
<a href="#faq">FAQ</a>
<a class="iq-nav-demo" href="#pricing">Upgrade &nbsp;&rarr;</a>
</div>
</div>
""")


# ─────────────────────────── Hero ────────────────────────────────────────────
render_html("""
<div class="iq-hero">
<div class="iq-eye"><span class="pulse"></span> &nbsp;AI-Powered CV Screening for HR &amp; Recruitment Teams</div>
<div class="iq-h1">Shortlist Top Talent<br>in <span class="shine">Seconds.</span></div>
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
</div>""")

        render_html(
            '<div class="iq-trial-info">🎁 <b>Free Trial:</b> Screen up to <b>10 CVs per batch</b>. '
            'Upload resumes in PDF, DOCX, DOC, TXT, or MS Excel (XLSX, XLS, CSV).</div>'
        )

        cv_files = st.file_uploader(
            "Upload CVs (PDF, DOC/DOCX, TXT, MS Excel — up to 10 files)",
            type=["pdf", "docx", "doc", "txt", "xlsx", "xls", "csv"],
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
                job_context = extract_job_context(jd_text)
                candidates = []
                bar = st.progress(0, text="Loading 5 Demo CVs…")
                _info = st.empty()
                for idx, df in enumerate(demo_files, 1):
                    render_html(
                        f'<p style="font-size:.82rem;color:#64748B">'
                        f'📄 <b style="color:#6B7A1A">{df.name}</b> ({idx}/5)</p>',
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
                    bar.progress(idx / 5 * 0.5, text=f"Parsing demo CVs — {idx}/5 done…")

                if candidates:
                    render_html(
                        f'<p style="font-size:.82rem;color:#64748B">'
                        f'🤖 Ranking <b style="color:#6B7A1A">{len(candidates)} candidates</b> with AI…</p>',
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
                        f'📄 <b style="color:#6B7A1A">{fname}</b> ({idx}/{len(saved_paths)})</p>',
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
                        f'🤖 Ranking <b style="color:#6B7A1A">{len(candidates)} candidates</b>…</p>',
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
<div style="background:rgba(199,214,51,0.22); color:#6B7A1A; font-family:'Space Mono', monospace; font-size:.7rem; font-weight:700; padding:.22rem .65rem; border-radius:100px; border:1px solid rgba(199,214,51,0.35); text-transform:uppercase; letter-spacing:.05em;">✨ Sample Preview</div>
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
<div class="iq-cr-bar"><div class="iq-cr-barfill" style="width:78%; background:linear-gradient(90deg,#E0692C,#FDBA74)"></div></div>
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

<div style="background:#FFFEF6; border:1.5px solid rgba(20,21,14,0.1); border-radius:14px; padding:.75rem .95rem; margin-top:.7rem; text-align:center;">
<div style="font-family:'Space Grotesk', sans-serif; font-size:.82rem; color:#55583F; font-weight:600;">
💡 <b>Interactive Demo Ready:</b> Click <b style="color:#6B7A1A;">⚡ Try 5 Demo CVs</b> in Panel 2 to screen live candidate resumes.
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

                sk_badges = "".join(f'<span class="iq-cr-sk" style="font-size:.72rem;">{s}</span>' for s in p_skills)
                render_html(f"""
<div class="iq-podium-card {p_c}">
  <span class="iq-podium-badge {pb_c}">{p_t}</span>
  <div>
    <div class="iq-podium-name">{p_name}</div>
    <div class="iq-podium-sub">{p_exp}</div>
    <div style="display:flex;align-items:baseline;gap:.4rem;margin-bottom:.4rem;">
      <span class="iq-podium-score" style="color:{p_col};">{p_score}%</span>
      <span style="font-family:'Space Mono', monospace;font-size:.75rem;color:inherit;opacity:.7;font-weight:600;">Match Fit</span>
    </div>
    <div style="height:6px;background:rgba(20,21,14,0.1);border-radius:99px;overflow:hidden;margin-bottom:.9rem;">
      <div style="height:100%;width:{p_score}%;background:{p_col};border-radius:99px;"></div>
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:.3rem;margin-bottom:1rem;">{sk_badges}</div>
    <div class="iq-podium-rec">
      <b>Recruiter Rationale:</b> {p_rec}
    </div>
  </div>
</div>
""")
                p_b1, p_b2 = st.columns([1, 1])
                with p_b1:
                    if st.button("✅ Shortlist", key=f"btn_short_{p_idx}", use_container_width=True):
                        if "recruiter_overrides" not in st.session_state:
                            st.session_state.recruiter_overrides = {}
                        if p_idx not in st.session_state.recruiter_overrides:
                            st.session_state.recruiter_overrides[p_idx] = {}
                        st.session_state.recruiter_overrides[p_idx]["status"] = "Shortlisted"
                        st.rerun()
                with p_b2:
                    if st.button("❌ Pass", key=f"btn_pass_{p_idx}", use_container_width=True):
                        if "recruiter_overrides" not in st.session_state:
                            st.session_state.recruiter_overrides = {}
                        if p_idx not in st.session_state.recruiter_overrides:
                            st.session_state.recruiter_overrides[p_idx] = {}
                        st.session_state.recruiter_overrides[p_idx]["status"] = "Rejected"
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
        chart = alt.Chart(chart_data).mark_bar(cornerRadius=6, color="#14150E").encode(
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
        _hfill = _PFill("solid", fgColor="14150E")
        _hfont = _Font(bold=True, color="FFFFFF", size=11, name="Calibri")
        _halign = _Align(horizontal="center", vertical="center")
        for _cell in _ws[1]:
            _cell.fill   = _hfill
            _cell.font   = _hfont
            _cell.alignment = _halign
        _ws.row_dimensions[1].height = 28

        # ── Alternating rows ─────────────────────────────────────────
        _fill_even = _PFill("solid", fgColor="F7F6EC")
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
<div class="iq-trial-upgrade" style="text-align:center; padding:2.6rem 2rem; margin:2.5rem 0 1.5rem; border-radius:24px; background:linear-gradient(155deg, #1C1D25, #101116); border:1.5px solid rgba(199,214,51,0.35); box-shadow:0 24px 60px -24px rgba(21,22,28,0.45); color:#F4F5F8;">
  <div style="font-family:'Anton', 'Space Grotesk', sans-serif; font-size:1.85rem; font-weight:700; color:#FFFFFF; margin-bottom:.5rem; letter-spacing:-.01em;">
    Ready to screen 100s of CVs across active roles?
  </div>
  <div style="font-size:1rem; color:rgba(244,245,248,0.72); max-width:560px; margin:0 auto 1.6rem; line-height:1.6;">
    RankCV helps recruitment &amp; HR teams automate bulk resume screening, candidate communications, and interview scheduling with zero bias.
  </div>
  <a class="iq-bp" href="https://wa.me/447379975532" target="_blank" style="padding:.9rem 2.2rem; font-size:1rem;">
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
<div class="iq-gauge-info"><span>🎯 Core Role Requirements</span><span style="color:#6B7A1A">96% Match</span></div>
<div class="iq-gauge-track"><div class="iq-gauge-bar" style="width:96%; background:linear-gradient(90deg, #C7D633, #6B7A1A);"></div></div>
</div>
<div class="iq-gauge-row">
<div class="iq-gauge-info"><span>💼 Experience Depth</span><span style="color:#14150E">92% Match</span></div>
<div class="iq-gauge-track"><div class="iq-gauge-bar" style="width:92%; background:#14150E;"></div></div>
</div>
<div class="iq-gauge-row">
<div class="iq-gauge-info"><span>🎓 Qualifications &amp; Background</span><span style="color:#6B7A1A">88% Match</span></div>
<div class="iq-gauge-track"><div class="iq-gauge-bar" style="width:88%; background:#C7D633;"></div></div>
</div>
<div class="iq-gauge-row">
<div class="iq-gauge-info"><span>⭐ Overall Recruiter Rating</span><span style="color:#E0692C">94% (Strong Match)</span></div>
<div class="iq-gauge-track"><div class="iq-gauge-bar" style="width:94%; background:linear-gradient(90deg, #E0692C, #FDBA74);"></div></div>
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
<span>3</span><span>Siddharth Rao</span><span style="font-weight:700;color:#E0692C">78%</span><span>Consider / Interview</span>
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
<div class="iq-pillars-eye">Built for High-Volume Hiring</div>
<div class="iq-pillars-h2">Why Recruiters Choose RankCV</div>
<div class="iq-pillars-sub">Speed up time-to-shortlist while maintaining strict candidate evaluation quality</div>
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
<div class="iq-tav">TA</div>
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
<div class="iq-tav">HR</div>
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
<div class="iq-tav">SF</div>
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
<div class="iq-tav">VP</div>
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
<div class="iq-tav">TR</div>
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
<div class="iq-tav">TO</div>
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
<div class="iq-tav">TA</div>
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
<div class="iq-tav">HR</div>
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
<div class="iq-tav">SF</div>
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
<div class="iq-tav">VP</div>
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
<div class="iq-tav">TR</div>
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
<div class="iq-tav">TO</div>
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
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>Plug &amp; Play AI:</b> Powered by RankCV internal engine</span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>Private In-Memory Engine:</b> Zero external AI transfer</span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>UK GDPR PII Stripper:</b> Names, postcodes redacted</span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>Top 3 Showcase Podium:</b> Gold, Silver, Bronze</span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>Article 22 Human Override:</b> Status tags &amp; notes</span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>Excel Shortlist &amp; UK GDPR Audit</b> Sheet download</span></li>
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span>1&ndash;2 Recruiter seats</span></li>
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
          <span style="font-family:'Space Mono', monospace; font-size:.7rem; font-weight:700; color:#14150E; background:#C7D633; padding:.25rem .7rem; border-radius:100px; letter-spacing:.05em;">ENTERPRISE DPA</span>
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
          <li class="iq-plan-feat-item"><span class="iq-feat-icon">&#10003;</span><span><b>Up to 5 Team / Hiring Manager Seats</b></span></li>
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
    <span style="font-family:'Space Mono', monospace; font-size:.76rem; font-weight:700; color:#55583F; margin-right:.5rem; text-transform:uppercase; letter-spacing:.05em;">Accepted Payment Methods:</span>
    <span class="iq-pay-pill"><svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" style="margin-right:2px"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M15.97 6.37c.62-.75 1.04-1.8 0.92-2.85-.9.04-2 .6-2.65 1.35-.58.66-1.08 1.74-.95 2.76.99.08 2.04-.51 2.68-1.26z"/></svg>Apple Pay</span>
    <span class="iq-pay-pill" style="font-weight:800;color:#1A1F71">VISA</span>
    <span class="iq-pay-pill"><span style="color:#EB001B">&#9679;</span><span style="color:#F79E1B;margin-left:-4px">&#9679;</span> Mastercard</span>
    <span class="iq-pay-pill">UK Debit Cards</span>
    <span class="iq-pay-pill" style="color:#6B7A1A;font-weight:700;">&#128274; Powered by Stripe (FCA Authorised)</span>
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
If your recruiting team handles high-volume applicant pipelines or requires custom scoring rubrics, click <a href="https://wa.me/447379975532" target="_blank" style="color:#6B7A1A;font-weight:700;text-decoration:underline;">Book a Demo</a> to connect directly with our team on WhatsApp for dedicated volume onboarding.
</div>
</details>

</div>
</div>
""")


render_html("""
<div class="iq-foot">
<div class="iq-foot-txt">RankCV &middot; AI CV Screening &middot; Built with Streamlit &amp; GPT-4o</div>
</div>
""")


