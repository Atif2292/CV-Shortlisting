"""
AI-Powered Recruitment Screening Application
Main entry point — Streamlit UI
"""

import os
import json
import tempfile
import streamlit as st
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Local utility imports
from utils.pdf_parser import extract_pdf_text
from utils.docx_parser import extract_docx_text
from utils.ai_scoring import extract_resume_keywords, rank_candidates_batch
from utils.email_sender import send_shortlist_emails, test_brevo_key, send_test_email
from utils.cleanup import delete_uploaded_files


# ─────────────────────────── Page Config ────────────────────────────────────
st.set_page_config(
    page_title="TalentSift — AI Recruitment Screener",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────── Theme CSS ──────────────────────────────────────
def build_css(dark: bool) -> str:
    """Return full CSS for light (default) or dark (night) mode."""
    if dark:
        c_app_bg       = "#0D0F14"
        c_app_text     = "#E8EAF0"
        c_hero_bg      = "linear-gradient(135deg, #1A1D2E 0%, #111827 60%, #0D1117 100%)"
        c_hero_border  = "#2A2D3E"
        c_hero_glow    = "rgba(99,102,241,0.18)"
        c_title_grad   = "linear-gradient(90deg, #818CF8 0%, #C4B5FD 60%, #F472B6 100%)"
        c_hero_sub     = "#9CA3AF"
        c_card_bg      = "#141720"
        c_card_border  = "#1F2333"
        c_card_title   = "#818CF8"
        c_cand_bg      = "#181B28"
        c_cand_border  = "#252840"
        c_cand_name    = "#E8EAF0"
        c_cand_email   = "#818CF8"
        c_tag_bg       = "rgba(129,140,248,0.12)"
        c_tag_color    = "#818CF8"
        c_tag_border   = "rgba(129,140,248,0.25)"
        c_input_bg     = "#1A1D2E"
        c_input_border = "#2A2D3E"
        c_input_text   = "#E8EAF0"
        c_label        = "#9CA3AF"
        c_expander_bg  = "#141720"
        c_expander_txt = "#C4B5FD"
        c_hr           = "#1F2333"
        c_metric_val   = "#E8EAF0"
        c_metric_lbl   = "#9CA3AF"
    else:
        c_app_bg       = "#F8FAFC"
        c_app_text     = "#0F172A"
        c_hero_bg      = "linear-gradient(135deg, #EEF2FF 0%, #F0F9FF 60%, #F8FAFC 100%)"
        c_hero_border  = "#C7D2FE"
        c_hero_glow    = "rgba(99,102,241,0.10)"
        c_title_grad   = "linear-gradient(90deg, #4F46E5 0%, #7C3AED 60%, #DB2777 100%)"
        c_hero_sub     = "#475569"
        c_card_bg      = "#FFFFFF"
        c_card_border  = "#E2E8F0"
        c_card_title   = "#4F46E5"
        c_cand_bg      = "#F8FAFC"
        c_cand_border  = "#E2E8F0"
        c_cand_name    = "#0F172A"
        c_cand_email   = "#4F46E5"
        c_tag_bg       = "rgba(79,70,229,0.07)"
        c_tag_color    = "#4F46E5"
        c_tag_border   = "rgba(79,70,229,0.18)"
        c_input_bg     = "#FFFFFF"
        c_input_border = "#CBD5E1"
        c_input_text   = "#0F172A"
        c_label        = "#475569"
        c_expander_bg  = "#F1F5F9"
        c_expander_txt = "#4F46E5"
        c_hr           = "#E2E8F0"
        c_metric_val   = "#0F172A"
        c_metric_lbl   = "#475569"

    return f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Syne:wght@700;800&display=swap');

/* ── Base ── */
html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}

[data-testid="stAppViewContainer"] {{
    background: {c_app_bg} !important;
    color: {c_app_text};
}}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="block-container"] {{ background: {c_app_bg}; }}

/* ── Metrics ── */
[data-testid="stMetricValue"] {{ color: {c_metric_val} !important; }}
[data-testid="stMetricLabel"] {{ color: {c_metric_lbl} !important; }}

/* ── Hero banner ── */
.hero {{
    background: {c_hero_bg};
    border: 1px solid {c_hero_border};
    border-radius: 16px;
    padding: 3rem 2.5rem;
    margin-bottom: 0.5rem;
    position: relative;
    overflow: hidden;
}}
.hero::before {{
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 240px; height: 240px;
    background: radial-gradient(circle, {c_hero_glow} 0%, transparent 70%);
    border-radius: 50%;
}}
.hero-title {{
    font-family: 'Syne', sans-serif;
    font-size: 2.6rem;
    font-weight: 800;
    background: {c_title_grad};
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0 0 0.4rem;
    line-height: 1.1;
}}
.hero-sub {{
    color: {c_hero_sub};
    font-size: 1.05rem;
    font-weight: 400;
    margin: 0;
}}

/* ── Section cards ── */
.card {{
    background: {c_card_bg};
    border: 1px solid {c_card_border};
    border-radius: 12px;
    padding: 1.6rem 1.8rem;
    margin-bottom: 1.4rem;
}}
.card-title {{
    font-family: 'Syne', sans-serif;
    font-size: 1.05rem;
    font-weight: 700;
    color: {c_card_title};
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-bottom: 0.9rem;
}}

/* ── Score badge ── */
.score-high   {{ color: #14B8A6; font-weight: 700; }}
.score-medium {{ color: #FBBF24; font-weight: 700; }}
.score-low    {{ color: #F87171; font-weight: 700; }}

/* ── Candidate card ── */
.cand-card {{
    background: {c_cand_bg};
    border: 1px solid {c_cand_border};
    border-radius: 10px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 1rem;
}}
.cand-name {{
    font-family: 'Syne', sans-serif;
    font-size: 1.1rem;
    font-weight: 700;
    color: {c_cand_name};
}}
.cand-email {{ color: {c_cand_email}; font-size: 0.875rem; }}
.tag {{
    display: inline-block;
    background: {c_tag_bg};
    color: {c_tag_color};
    border: 1px solid {c_tag_border};
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.78rem;
    margin: 2px;
}}
.tag-green {{
    background: rgba(52,211,153,0.10);
    color: #059669;
    border-color: rgba(52,211,153,0.22);
}}
.tag-red {{
    background: rgba(248,113,113,0.10);
    color: #F87171;
    border-color: rgba(248,113,113,0.22);
}}
.tag-muted {{
    background: rgba(100,116,139,0.10);
    color: #64748B;
    border-color: rgba(100,116,139,0.22);
}}

/* ── Recommendation badges ── */
.rec-highly      {{ background:#DCFCE7; color:#15803D; border-radius:6px; padding:3px 10px; font-size:0.82rem; font-weight:600; display:inline-block; }}
.rec-recommended {{ background:#DBEAFE; color:#1D4ED8; border-radius:6px; padding:3px 10px; font-size:0.82rem; font-weight:600; display:inline-block; }}
.rec-review      {{ background:#FEF3C7; color:#B45309; border-radius:6px; padding:3px 10px; font-size:0.82rem; font-weight:600; display:inline-block; }}
.rec-unsuitable  {{ background:#F3F4F6; color:#6B7280; border-radius:6px; padding:3px 10px; font-size:0.82rem; font-weight:600; display:inline-block; }}

/* ── Streamlit widget overrides ── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div,
input[type="number"] {{
    background: {c_input_bg} !important;
    border: 1px solid {c_input_border} !important;
    color: {c_input_text} !important;
    border-radius: 8px !important;
}}
.stButton > button {{
    background: linear-gradient(135deg, #6366F1, #8B5CF6);
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    padding: 0.55rem 1.6rem;
    font-size: 0.95rem;
    transition: opacity 0.2s;
}}
.stButton > button:hover {{ opacity: 0.88; }}

label, .stFileUploader label {{ color: {c_label} !important; font-size: 0.9rem !important; }}

/* progress bar */
.stProgress > div > div > div {{ background: linear-gradient(90deg, #3B82F6, #14B8A6) !important; }}

/* table */
.stDataFrame {{ border-radius: 10px; overflow: hidden; }}

/* divider */
hr {{ border-color: {c_hr} !important; }}

/* expander */
.streamlit-expanderHeader {{
    background: {c_expander_bg} !important;
    color: {c_expander_txt} !important;
    border-radius: 8px !important;
}}
</style>"""


# ─────────────────────────── Night-mode detection ────────────────────────────
_dark = st.session_state.get("nm_toggle", False)
st.markdown(build_css(_dark), unsafe_allow_html=True)

# ─────────────────────────── Session State ──────────────────────────────────
if "results" not in st.session_state:
    st.session_state.results = []
if "processed" not in st.session_state:
    st.session_state.processed = False
if "uploaded_paths" not in st.session_state:
    st.session_state.uploaded_paths = []

# ── Email (Brevo) — pre-fill from .env if already set ───────────────────────
if "brevo_api_key" not in st.session_state:
    st.session_state["brevo_api_key"] = os.getenv("BREVO_API_KEY", "")
if "brevo_from_email" not in st.session_state:
    st.session_state["brevo_from_email"] = os.getenv("BREVO_FROM_EMAIL", "")

# ─────────────────────────── Hero ───────────────────────────────────────────
st.markdown("""
<div class="hero">
  <p class="hero-title">🎯 TalentSift</p>
  <p class="hero-sub">AI-powered CV screening · Rank candidates instantly · Auto-email your shortlist</p>
</div>
""", unsafe_allow_html=True)

# ── Night-mode toggle (top-right) ────────────────────────────────────────────
_gap, _tc = st.columns([10, 2])
with _tc:
    st.toggle("🌙  Night mode", key="nm_toggle")

# ─────────────────────────── Layout: two columns ─────────────────────────────
left_col, right_col = st.columns([1, 1.8], gap="large")

# ══════════════════════════ LEFT — Job Form ══════════════════════════════════
with left_col:
    st.markdown('<div class="card"><div class="card-title">📋 Job Requirements</div>', unsafe_allow_html=True)

    job_title = st.text_input("Job Title", placeholder="e.g. Senior Backend Engineer")
    required_skills = st.text_area(
        "Required Skills (comma-separated)",
        placeholder="Python, FastAPI, PostgreSQL, Docker, AWS",
        height=90,
    )
    years_experience = st.number_input(
        "Minimum Years of Experience", min_value=0, max_value=30, value=3, step=1
    )
    job_description = st.text_area(
        "Full Job Description",
        placeholder="Paste the complete job description here…",
        height=220,
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # ── CV Upload ────────────────────────────────────────────────────────────
    st.markdown('<div class="card"><div class="card-title">📂 Upload CVs</div>', unsafe_allow_html=True)
    pdf_files  = st.file_uploader("PDF CVs",  type=["pdf"],  accept_multiple_files=True, key="pdf_up")
    docx_files = st.file_uploader("DOCX CVs", type=["docx"], accept_multiple_files=True, key="docx_up")

    total_uploaded = len(pdf_files or []) + len(docx_files or [])
    if total_uploaded:
        st.caption(f"✅ {total_uploaded} file{'s' if total_uploaded != 1 else ''} ready to process (max 100)")
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Email config ─────────────────────────────────────────────────────────
    st.markdown('<div class="card"><div class="card-title">✉️ Email Settings</div>', unsafe_allow_html=True)

    send_emails    = st.checkbox("Auto-email top 10 shortlisted candidates", value=True)
    recruiter_name = st.text_input("Recruiter / Company name", value="Recruitment Team")

    st.text_input(
        "Your Email Address (sends from here)",
        key="brevo_from_email",
        placeholder="you@gmail.com",
    )
    st.text_input(
        "Brevo API Key",
        key="brevo_api_key",
        type="password",
        placeholder="xkeysib-••••••••••••••••",
    )

    # ── Setup guide ───────────────────────────────────────────────────────
    _from = (st.session_state.get("brevo_from_email") or "").strip()
    with st.expander("📋 Setup Guide (free, 2 min)", expanded=not st.session_state.get("brevo_api_key")):
        st.markdown(f"""
**Step 1 — Create a free Brevo account**
→ [app.brevo.com](https://app.brevo.com) · free plan: 300 emails/day

**Step 2 — Verify your sender email**
1. In Brevo go to **Senders & IP → Senders**
2. Click **Add a Sender**
3. Enter `{_from if _from else "your email"}` → click **Save**
4. Check your inbox → click the **verification link** Brevo sends

**Step 3 — Create an API key**
→ Brevo → top-right menu → **SMTP & API** → **API Keys**
→ Click **Generate a new API key** → paste it above

*Works with Gmail, Outlook, Yahoo — no domain, no app password needed.*
""")

    # ── Buttons: verify key + send test ──────────────────────────────────
    _col1, _col2 = st.columns(2)
    with _col1:
        if st.button("🔑 Verify API Key", use_container_width=True):
            with st.spinner("Checking…"):
                _ok, _msg = test_brevo_key(st.session_state.get("brevo_api_key", ""))
            if _ok:
                st.success(f"✅ {_msg}")
            else:
                st.error(f"❌ {_msg}")
    with _col2:
        if st.button("📧 Send Test Email", use_container_width=True):
            with st.spinner("Sending…"):
                _ok, _msg = send_test_email(
                    st.session_state.get("brevo_api_key", ""),
                    st.session_state.get("brevo_from_email", ""),
                )
            if _ok:
                st.success(f"✅ {_msg}")
            else:
                st.error(f"❌ {_msg}")

    st.markdown('</div>', unsafe_allow_html=True)

    run_btn = st.button("🚀 Screen Candidates", use_container_width=True)

# ══════════════════════════ RIGHT — Results ══════════════════════════════════
with right_col:
    # Mode-aware colours for HTML blocks (picked up from top-level _dark)
    _c_sec_lbl  = "#9CA3AF" if _dark else "#64748B"
    _c_batch    = "#818CF8" if _dark else "#6366F1"
    _c_proc_txt = "#9CA3AF" if _dark else "#475569"
    _c_proc_hl  = "#C4B5FD" if _dark else "#6366F1"

    if run_btn:
        # ── Validation ───────────────────────────────────────────────────────
        errors = []
        if not job_title.strip():
            errors.append("Job Title is required.")
        if not required_skills.strip():
            errors.append("Required Skills are required.")
        if not job_description.strip():
            errors.append("Job Description is required.")
        if total_uploaded == 0:
            errors.append("Please upload at least one CV (PDF or DOCX).")
        if total_uploaded > 100:
            errors.append("Maximum 100 CVs allowed per batch.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            # ── Save uploads to disk ──────────────────────────────────────────
            upload_dir = Path("uploads")
            upload_dir.mkdir(exist_ok=True)
            saved_paths = []

            all_files = list(pdf_files or []) + list(docx_files or [])
            for f in all_files:
                dest = upload_dir / f.name
                dest.write_bytes(f.read())
                saved_paths.append(str(dest))

            st.session_state.uploaded_paths = saved_paths

            # ── Build job context dict ────────────────────────────────────────
            job_context = {
                "title": job_title.strip(),
                "skills": required_skills.strip(),
                "years_experience": years_experience,
                "description": job_description.strip(),
            }

            # ── Phase 1: Extract keywords from every CV (local, no LLM) ─────────
            candidates = []
            progress_bar = st.progress(0, text="Reading CVs…")
            status_box   = st.empty()

            for idx, path in enumerate(saved_paths, start=1):
                fname = Path(path).name
                status_box.markdown(
                    f'<p style="color:{_c_proc_txt};font-size:0.88rem;">'
                    f'📄 Extracting <b style="color:{_c_proc_hl}">{fname}</b>'
                    f' ({idx}/{len(saved_paths)})</p>',
                    unsafe_allow_html=True,
                )
                try:
                    text = extract_pdf_text(path) if path.endswith(".pdf") else extract_docx_text(path)
                    if not text.strip():
                        st.warning(f"⚠️ Could not extract text from {fname} — skipping.")
                        continue
                    keywords = extract_resume_keywords(
                        cv_text=text,
                        required_skills=required_skills.strip(),
                    )
                    candidates.append(keywords)
                except Exception as ex:
                    st.warning(f"⚠️ Error processing {fname}: {ex}")

                progress_bar.progress(
                    idx / len(saved_paths) * 0.5,
                    text=f"Extracting keywords — {idx}/{len(saved_paths)} CVs done…",
                )

            # ── Phase 2: Single batch LLM call for all candidates ─────────────
            if candidates:
                status_box.markdown(
                    f'<p style="color:{_c_proc_txt};font-size:0.88rem;">'
                    f'🤖 Sending <b style="color:{_c_proc_hl}">{len(candidates)} candidates</b>'
                    f' to AI for ranking…</p>',
                    unsafe_allow_html=True,
                )
                progress_bar.progress(0.55, text=f"AI is ranking {len(candidates)} candidates in one call…")

                results = rank_candidates_batch(
                    candidates=candidates,
                    job_context=job_context,
                )
            else:
                results = []

            progress_bar.progress(1.0, text="✅ Screening complete!")
            status_box.empty()

            st.session_state.results = results
            st.session_state.processed = True

            # ── Send emails to Top 10 ─────────────────────────────────────────
            if send_emails and results:
                top10 = results[:10]
                with st.spinner("Sending shortlist emails…"):
                    email_report = send_shortlist_emails(
                        candidates=top10,
                        job_title=job_title,
                        recruiter_name=recruiter_name,
                        brevo_api_key=st.session_state.get("brevo_api_key", ""),
                        from_email=st.session_state.get("brevo_from_email", ""),
                    )
                if email_report["sent"]:
                    st.success(f"📧 Emails sent to {len(email_report['sent'])} candidates.")
                if email_report["failed"]:
                    st.warning(f"⚠️ Failed to send to: {', '.join(email_report['failed'])}")

            # ── Delete uploaded files ─────────────────────────────────────────
            deleted, not_deleted = delete_uploaded_files(saved_paths)
            if deleted:
                st.caption(f"🗑️ {len(deleted)} uploaded file(s) deleted from server.")

    # ── Render results ────────────────────────────────────────────────────────
    if st.session_state.processed and st.session_state.results:
        results = st.session_state.results

        st.markdown('<div class="card-title" style="margin-top:0.5rem">📊 Ranked Candidates</div>', unsafe_allow_html=True)

        # Summary metrics
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Total Screened", len(results))
        with m2:
            shortlisted = min(10, len(results))
            st.metric("Shortlisted", shortlisted)
        with m3:
            avg_score = round(sum(r.get("match_score", 0) for r in results) / len(results), 1)
            st.metric("Avg Match Score", f"{avg_score}%")

        st.markdown("---")

        # ── Ranked Table ──────────────────────────────────────────────────────
        table_data = []
        for rank, r in enumerate(results, 1):
            score      = r.get("match_score", 0)
            percentile = r.get("percentile", 0)
            emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"
            table_data.append({
                "Rank":           emoji,
                "Candidate":      r.get("candidate_name", "Unknown"),
                "Email":          r.get("email", "—"),
                "Score (%)":      score,
                "Percentile":     percentile,
                "Recommendation": r.get("recommendation", "—"),
            })

        df = pd.DataFrame(table_data)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Score (%)": st.column_config.ProgressColumn(
                    "Score (%)", min_value=0, max_value=100, format="%d%%"
                ),
                "Percentile": st.column_config.ProgressColumn(
                    "Percentile", min_value=0, max_value=100, format="%d%%"
                ),
            },
        )

        # ── Shortlist banner ──────────────────────────────────────────────────
        st.markdown("---")
        st.markdown(
            '<div class="card-title">🏆 Top 10 Shortlist — Detailed Profiles</div>',
            unsafe_allow_html=True,
        )

        def _rec_badge(rec_text):
            t = rec_text.lower()
            if "highly" in t:
                css = "rec-highly"
            elif "not" in t and ("suit" in t or "recommend" in t):
                css = "rec-unsuitable"
            elif "review" in t or "manual" in t:
                css = "rec-review"
            elif "recommend" in t:
                css = "rec-recommended"
            else:
                return f'<span style="color:{_c_sec_lbl};font-size:0.92rem">{rec_text}</span>'
            return f'<span class="{css}">{rec_text}</span>'

        for rank, r in enumerate(results[:10], 1):
            score = r.get("match_score", 0)
            score_cls = "score-high" if score >= 70 else "score-medium" if score >= 45 else "score-low"

            strengths  = r.get("strengths", [])
            concerns   = r.get("concerns", [])
            name       = r.get("candidate_name", "Unknown")
            email      = r.get("email", "—")
            rec        = r.get("recommendation", "—")
            percentile = r.get("percentile", 0)

            strengths_html = " ".join(f'<span class="tag tag-green">✓ {s}</span>' for s in strengths)
            concern_tag    = "tag-muted" if score >= 70 else "tag-red"
            concerns_html  = " ".join(f'<span class="tag {concern_tag}">✗ {c}</span>' for c in concerns)

            with st.expander(f"#{rank} — {name}  ·  {score}% match  ·  top {100 - percentile + 1}%", expanded=(rank <= 3)):
                st.markdown(f"""
                <div class="cand-card">
                  <div class="cand-name">{name}</div>
                  <div class="cand-email">{email}</div>
                  <br>
                  <span class="{score_cls}" style="font-size:1.6rem">{score}%</span>
                  <span style="color:{_c_sec_lbl};font-size:0.85rem"> match score</span>
                  &nbsp;&nbsp;
                  <span style="color:{_c_batch};font-size:0.92rem">top {100 - percentile + 1}% of batch</span>
                  <hr style="margin:0.8rem 0">
                  <p style="color:{_c_sec_lbl};font-size:0.82rem;margin-bottom:4px">STRENGTHS</p>
                  {strengths_html or '<span style="color:#94A3B8">None noted</span>'}
                  <p style="color:{_c_sec_lbl};font-size:0.82rem;margin:0.7rem 0 4px">CONCERNS</p>
                  {concerns_html or '<span style="color:#94A3B8">None noted</span>'}
                  <p style="color:{_c_sec_lbl};font-size:0.82rem;margin:0.7rem 0 4px">RECOMMENDATION</p>
                  {_rec_badge(rec)}
                </div>
                """, unsafe_allow_html=True)

        # ── Download CSV ──────────────────────────────────────────────────────
        st.markdown("---")
        csv_data = pd.DataFrame([
            {
                "Rank":                i + 1,
                "Name":                r.get("candidate_name", ""),
                "Email":               r.get("email", ""),
                "Score":               r.get("match_score", 0),
                "Percentile":          r.get("percentile", 0),
                "Skills Match":        r.get("skills_match", ""),
                "Relevant Experience": r.get("relevant_experience", ""),
                "Strengths":           "; ".join(r.get("strengths", [])),
                "Concerns":            "; ".join(r.get("concerns", [])),
                "Recommendation":      r.get("recommendation", ""),
            }
            for i, r in enumerate(results)
        ]).to_csv(index=False)

        st.download_button(
            label="⬇️ Download Full Results CSV",
            data=csv_data,
            file_name="recruitment_results.csv",
            mime="text/csv",
            use_container_width=True,
        )

    elif st.session_state.processed and not st.session_state.results:
        st.warning("No candidates could be processed. Check your CV files and try again.")
    else:
        # Idle state placeholder
        st.markdown("""
        <div style="text-align:center;padding:4rem 2rem;">
          <div style="font-size:3rem;margin-bottom:1rem">📂</div>
          <p style="font-size:1.05rem;color:#64748B">Fill in the job requirements, upload CVs,<br>then click <b style="color:#6366F1">Screen Candidates</b>.</p>
          <p style="font-size:0.85rem;color:#94A3B8;margin-top:0.5rem">Supports up to 100 PDF &amp; DOCX files · Powered by GPT-4o</p>
        </div>
        """, unsafe_allow_html=True)

# ─────────────────────────── Footer ──────────────────────────────────────────
st.markdown("""
<hr>
<p style="text-align:center;color:#94A3B8;font-size:0.8rem">
  TalentSift · AI Recruitment Screener · Built with Streamlit &amp; OpenAI
</p>
""", unsafe_allow_html=True)
