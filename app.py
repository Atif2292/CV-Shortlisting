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
        bg = "#0A0C14"; sf = "#141720"
        tx = "#F1F5F9"; sub = "#94A3B8"; br = "#1E2333"
        ibg = "#1A1D2E"; ibr = "#2A2D3E"; itx = "#F1F5F9"
        lbl = "#94A3B8"; mv = "#F1F5F9"; ml = "#94A3B8"
        tcbg = "#1A1D2E"
    else:
        bg = "#FFFFFF"; sf = "#F8FAFC"
        tx = "#0F172A"; sub = "#64748B"; br = "#E2E8F0"
        ibg = "#FFFFFF"; ibr = "#CBD5E1"; itx = "#0F172A"
        lbl = "#475569"; mv = "#0F172A"; ml = "#64748B"
        tcbg = "#FFFFFF"

    return f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

html,body,[class*="css"]{{font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;}}
[data-testid="stAppViewContainer"]{{background:{bg}!important;}}
[data-testid="stHeader"]{{background:transparent!important;box-shadow:none!important;}}
[data-testid="block-container"]{{background:{bg};padding-top:.6rem!important;}}
[data-testid="stMetricValue"]{{color:{mv}!important;}}
[data-testid="stMetricLabel"]{{color:{ml}!important;}}

/* ── Navbar ── */
.iq-nav{{
    display:flex;align-items:center;justify-content:space-between;
    padding:.85rem 0;border-bottom:1px solid {br};margin-bottom:2.2rem;
}}
.iq-logo{{font-size:1.5rem;font-weight:900;color:{tx};letter-spacing:-.5px;}}
.iq-logo span{{color:#2563EB;}}
.iq-nav-r{{display:flex;align-items:center;gap:.85rem;}}
.iq-nav-login{{
    font-size:.88rem;font-weight:500;color:{sub};padding:.38rem .9rem;
    border-radius:6px;border:none;background:none;cursor:pointer;
}}
.iq-nav-demo{{
    font-size:.88rem;font-weight:600;color:#fff;background:#2563EB;
    padding:.42rem 1.1rem;border-radius:7px;border:none;cursor:pointer;
}}

/* ── Hero ── */
.iq-hero{{text-align:center;padding:2.8rem 1rem 1.8rem;max-width:820px;margin:0 auto;}}
.iq-eye{{
    font-size:.7rem;font-weight:700;letter-spacing:.15em;color:#2563EB;
    text-transform:uppercase;margin-bottom:.9rem;
}}
.iq-h1{{
    font-size:3.5rem;font-weight:900;line-height:1.07;
    color:{tx};margin:0 0 1rem;letter-spacing:-2px;
}}
.iq-h1 .bl{{color:#2563EB;}}
.iq-sub{{
    font-size:1.05rem;color:{sub};max-width:530px;
    margin:0 auto 1.8rem;line-height:1.7;
}}
.iq-btns{{display:flex;align-items:center;justify-content:center;gap:1rem;flex-wrap:wrap;}}
.iq-bp{{
    background:#2563EB;color:#fff;font-weight:600;font-size:.975rem;
    border:none;border-radius:8px;padding:.72rem 1.8rem;cursor:pointer;
    text-decoration:none;display:inline-block;
}}
.iq-bs{{
    background:none;color:{tx};font-weight:500;font-size:.975rem;
    border:1.5px solid {br};border-radius:8px;padding:.72rem 1.8rem;
    cursor:pointer;text-decoration:none;display:inline-block;
}}

/* ── Steps ── */
.iq-steps{{
    display:flex;align-items:flex-start;justify-content:center;
    gap:0;padding:2rem 0 2rem;max-width:760px;margin:0 auto;
}}
.iq-step{{flex:1;text-align:center;padding:0 1rem;}}
.iq-snum{{
    width:40px;height:40px;background:#2563EB;color:#fff;
    font-weight:700;font-size:.95rem;border-radius:50%;
    display:flex;align-items:center;justify-content:center;
    margin:0 auto .75rem;
}}
.iq-step h3{{font-size:.95rem;font-weight:700;color:{tx};margin:0 0 .3rem;}}
.iq-step p{{font-size:.82rem;color:{sub};margin:0;line-height:1.5;}}
.iq-arr{{color:{sub};font-size:1.1rem;margin-top:13px;flex-shrink:0;}}
.iq-div{{height:1px;background:{br};margin:0 0 2.4rem;}}

/* ── Form cards ── */
.iq-card{{
    background:{sf};border:1px solid {br};border-radius:14px;
    padding:1.5rem 1.7rem;margin-bottom:1.1rem;
}}
.iq-ct{{
    font-size:.75rem;font-weight:700;color:{sub};letter-spacing:.08em;
    text-transform:uppercase;margin-bottom:.9rem;
}}

/* ── Widget overrides ── */
.stTextInput>div>div>input,
.stTextArea>div>div>textarea,
input[type="number"]{{
    background:{ibg}!important;border:1.5px solid {ibr}!important;
    color:{itx}!important;border-radius:8px!important;font-size:.93rem!important;
}}
.stButton>button{{
    background:#2563EB!important;color:#fff!important;border:none!important;
    border-radius:8px!important;font-weight:600!important;
    font-size:.95rem!important;padding:.62rem 1.5rem!important;
}}
.stButton>button:hover{{background:#1D4ED8!important;opacity:1!important;}}
label,.stFileUploader label{{color:{lbl}!important;font-size:.88rem!important;}}
.stProgress>div>div>div{{background:linear-gradient(90deg,#2563EB,#60A5FA)!important;}}
.stDataFrame{{border-radius:10px;overflow:hidden;}}

/* ── Result list cards ── */
.iq-rc{{
    display:flex;align-items:center;justify-content:space-between;
    padding:.85rem 1.1rem;border:1px solid {br};border-radius:10px;
    margin-bottom:.6rem;background:{sf};
}}
.iq-rcl{{display:flex;align-items:center;gap:.85rem;}}
.iq-av{{
    width:40px;height:40px;border-radius:50%;
    background:linear-gradient(135deg,#DBEAFE,#EDE9FE);
    display:flex;align-items:center;justify-content:center;
    font-size:.95rem;font-weight:800;color:#2563EB;flex-shrink:0;
}}
.iq-rn{{font-weight:700;font-size:.93rem;color:{tx};}}
.iq-rr{{font-size:.79rem;color:{sub};margin-top:1px;}}
.iq-scr{{text-align:right;flex-shrink:0;}}
.iq-sv{{font-size:1.1rem;font-weight:900;color:#2563EB;}}
.iq-sd{{font-size:.8rem;color:{sub};font-weight:500;}}
.iq-stars{{font-size:.82rem;color:#FBBF24;line-height:1.3;}}

/* ── Candidate detail ── */
.iq-det{{background:{sf};border:1px solid {br};border-radius:11px;padding:1.3rem;}}
.iq-tag{{
    display:inline-block;background:rgba(37,99,235,.07);color:#2563EB;
    border:1px solid rgba(37,99,235,.16);border-radius:6px;
    padding:2px 8px;font-size:.77rem;margin:2px;
}}
.iq-tag-g{{background:rgba(16,185,129,.07);color:#059669;border-color:rgba(16,185,129,.16);}}
.iq-tag-m{{background:rgba(100,116,139,.07);color:#64748B;border-color:rgba(100,116,139,.16);}}
.iq-tag-r{{background:rgba(239,68,68,.07);color:#EF4444;border-color:rgba(239,68,68,.16);}}
.rec-highly     {{background:#DCFCE7;color:#15803D;border-radius:6px;padding:3px 10px;font-size:.82rem;font-weight:600;display:inline-block;}}
.rec-recommended{{background:#DBEAFE;color:#1D4ED8;border-radius:6px;padding:3px 10px;font-size:.82rem;font-weight:600;display:inline-block;}}
.rec-review     {{background:#FEF3C7;color:#B45309;border-radius:6px;padding:3px 10px;font-size:.82rem;font-weight:600;display:inline-block;}}
.rec-unsuitable {{background:#F3F4F6;color:#6B7280;border-radius:6px;padding:3px 10px;font-size:.82rem;font-weight:600;display:inline-block;}}

/* ── Testimonials ── */
.iq-ts-sec{{
    background:{sf};border:1px solid {br};border-radius:16px;
    padding:2.8rem 2rem;margin:2.5rem 0;
}}
.iq-ts-h{{text-align:center;font-size:1.9rem;font-weight:900;color:{tx};margin-bottom:.4rem;}}
.iq-ts-s{{text-align:center;color:{sub};font-size:.93rem;margin-bottom:2.2rem;}}
.iq-tg{{display:grid;grid-template-columns:repeat(3,1fr);gap:1.3rem;}}
.iq-tc{{background:{tcbg};border:1px solid {br};border-radius:11px;padding:1.4rem;}}
.iq-tq{{font-size:1.8rem;color:#2563EB;line-height:1;margin-bottom:.6rem;}}
.iq-tt{{font-size:.875rem;color:{sub};line-height:1.7;margin-bottom:1rem;}}
.iq-tp{{display:flex;align-items:center;gap:.65rem;}}
.iq-tav{{
    width:34px;height:34px;border-radius:50%;
    background:linear-gradient(135deg,#DBEAFE,#EDE9FE);
    display:flex;align-items:center;justify-content:center;
    font-weight:700;color:#2563EB;font-size:.82rem;flex-shrink:0;
}}
.iq-tpn{{font-weight:700;font-size:.83rem;color:{tx};}}
.iq-tpc{{font-size:.77rem;color:{sub};}}

/* ── Footer CTA ── */
.iq-fcta{{text-align:center;padding:3.5rem 2rem;border-top:1px solid {br};}}
.iq-fi{{font-size:2.2rem;margin-bottom:.8rem;}}
.iq-fh{{
    font-size:2.2rem;font-weight:900;color:{tx};
    line-height:1.15;margin-bottom:.7rem;letter-spacing:-1px;
}}
.iq-fh span{{color:#2563EB;}}
.iq-fs{{
    font-size:.98rem;color:{sub};margin-bottom:1.8rem;
    max-width:440px;margin-left:auto;margin-right:auto;
}}
.iq-fck{{font-size:.82rem;color:{sub};margin-top:.8rem;}}

hr{{border-color:{br}!important;}}
</style>"""


# ─────────────────────────── Init ────────────────────────────────────────────
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

_c_sub = "#94A3B8" if _dark else "#64748B"
_c_hl  = "#C4B5FD" if _dark else "#2563EB"
_c_tx  = "#F1F5F9" if _dark else "#0F172A"


# ─────────────────────────── Navbar ──────────────────────────────────────────
_nc, _tc = st.columns([9, 2])
with _tc:
    st.toggle("🌙 Night mode", key="nm_toggle")

st.markdown("""
<div class="iq-nav">
  <div class="iq-logo">Talent<span>IQ</span></div>
  <div class="iq-nav-r">
    <button class="iq-nav-login">Login</button>
    <button class="iq-nav-demo">Book a Demo</button>
  </div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────── Hero ────────────────────────────────────────────
st.markdown("""
<div class="iq-hero">
  <p class="iq-eye">AI-Powered CV Screening for Recruitment Agencies</p>
  <h1 class="iq-h1">Screen <span class="bl">100</span> CVs in<br>minutes not hours.</h1>
  <p class="iq-sub">TalentIQ analyses CVs, ranks candidates, generates summaries
  and helps recruiters shortlist top talent in minutes.</p>
  <div class="iq-btns">
    <a class="iq-bp">Try TalentIQ Free &nbsp;&rarr;</a>
    <a class="iq-bs">How it works &nbsp;&#9654;</a>
  </div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────── Steps ───────────────────────────────────────────
st.markdown("""
<div class="iq-steps">
  <div class="iq-step">
    <div class="iq-snum">1</div>
    <h3>Upload Job Description</h3>
    <p>Paste or upload the job description</p>
  </div>
  <div class="iq-arr">&rarr;</div>
  <div class="iq-step">
    <div class="iq-snum">2</div>
    <h3>Upload CVs</h3>
    <p>Upload any CV format. No friction.</p>
  </div>
  <div class="iq-arr">&rarr;</div>
  <div class="iq-step">
    <div class="iq-snum">3</div>
    <h3>Get Ranked Results</h3>
    <p>AI ranks and scores the best matches</p>
  </div>
</div>
<div class="iq-div"></div>
""", unsafe_allow_html=True)


# ─────────────────────────── Helpers ─────────────────────────────────────────
def _fmt_score(score: int):
    """Convert 0–100 → ('9.5', '★★★★★') for display."""
    s10   = round(score / 10, 1)
    label = f"{s10:.1f}" if s10 % 1 else f"{int(s10)}.0"
    full  = min(5, round(score / 20))
    return label, "★" * full + "☆" * (5 - full)


def _rec_badge(rec_text: str) -> str:
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
        return f'<span style="font-size:.92rem;color:{_c_sub}">{rec_text}</span>'
    return f'<span class="{css}">{rec_text}</span>'


def _extract_cv_text(path: str, fname: str) -> str:
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


# ─────────────────────────── Main layout ─────────────────────────────────────
left_col, right_col = st.columns([1, 1.8], gap="large")


# ══════════════════════════ LEFT — Form ══════════════════════════════════════
with left_col:

    # ── Job Description ───────────────────────────────────────────────────────
    st.markdown('<div class="iq-card"><div class="iq-ct">📋 Job Description</div>', unsafe_allow_html=True)
    job_title = st.text_input("Job Title", placeholder="e.g. Senior Backend Engineer")
    required_skills = st.text_area(
        "Required Skills (comma-separated)",
        placeholder="Python, FastAPI, PostgreSQL, Docker, AWS",
        height=82,
    )
    years_experience = st.number_input(
        "Minimum Years of Experience", min_value=0, max_value=30, value=3, step=1
    )
    job_description = st.text_area(
        "Full Job Description",
        placeholder="Paste the complete job description here…",
        height=200,
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Upload CVs ────────────────────────────────────────────────────────────
    st.markdown('<div class="iq-card"><div class="iq-ct">📂 Upload CVs</div>', unsafe_allow_html=True)
    cv_files = st.file_uploader(
        "PDF, DOCX, TXT — any format, no friction",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        key="cv_up",
    )
    total_uploaded = len(cv_files or [])
    if total_uploaded:
        st.caption(f"✅ {total_uploaded} file{'s' if total_uploaded != 1 else ''} ready · max 100")
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Email Settings ────────────────────────────────────────────────────────
    st.markdown('<div class="iq-card"><div class="iq-ct">✉️ Email Settings</div>', unsafe_allow_html=True)
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

    _ec1, _ec2 = st.columns(2)
    with _ec1:
        if st.button("🔑 Verify Key", use_container_width=True):
            with st.spinner("Checking…"):
                _ok, _msg = test_brevo_key(st.session_state.get("brevo_api_key", ""))
            (st.success if _ok else st.error)(f"{'✅' if _ok else '❌'} {_msg}")
    with _ec2:
        if st.button("📧 Test Email", use_container_width=True):
            with st.spinner("Sending…"):
                _ok, _msg = send_test_email(
                    st.session_state.get("brevo_api_key", ""),
                    st.session_state.get("brevo_from_email", ""),
                )
            (st.success if _ok else st.error)(f"{'✅' if _ok else '❌'} {_msg}")
    st.markdown('</div>', unsafe_allow_html=True)

    run_btn = st.button("🚀  Screen Candidates", use_container_width=True)


# ══════════════════════════ RIGHT — Results ═══════════════════════════════════
with right_col:

    if run_btn:
        # Validation
        errors = []
        if not job_title.strip():
            errors.append("Job Title is required.")
        if not required_skills.strip():
            errors.append("Required Skills are required.")
        if not job_description.strip():
            errors.append("Job Description is required.")
        if total_uploaded == 0:
            errors.append("Please upload at least one CV.")
        if total_uploaded > 100:
            errors.append("Maximum 100 CVs allowed per batch.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            # Save uploads to disk
            upload_dir = Path("uploads")
            upload_dir.mkdir(exist_ok=True)
            saved_paths, saved_names = [], []

            for f in (cv_files or []):
                dest = upload_dir / f.name
                dest.write_bytes(f.read())
                saved_paths.append(str(dest))
                saved_names.append(f.name)

            st.session_state.uploaded_paths = saved_paths

            job_context = {
                "title":            job_title.strip(),
                "skills":           required_skills.strip(),
                "years_experience": years_experience,
                "description":      job_description.strip(),
            }

            # Phase 1 — keyword extraction
            candidates = []
            bar   = st.progress(0, text="Reading CVs…")
            _info = st.empty()

            for idx, (path, fname) in enumerate(zip(saved_paths, saved_names), 1):
                _info.markdown(
                    f'<p style="color:{_c_sub};font-size:.87rem;">'
                    f'📄 Reading <b style="color:{_c_hl}">{fname}</b>'
                    f' ({idx}/{len(saved_paths)})</p>',
                    unsafe_allow_html=True,
                )
                try:
                    text = _extract_cv_text(path, fname)
                    if not text.strip():
                        st.warning(f"⚠️ No text found in {fname} — skipping.")
                        continue
                    candidates.append(
                        extract_resume_keywords(
                            cv_text=text, required_skills=required_skills.strip()
                        )
                    )
                except Exception as ex:
                    st.warning(f"⚠️ Error reading {fname}: {ex}")

                bar.progress(
                    idx / len(saved_paths) * 0.5,
                    text=f"Reading CVs — {idx}/{len(saved_paths)} done…",
                )

            # Phase 2 — AI ranking
            if candidates:
                _info.markdown(
                    f'<p style="color:{_c_sub};font-size:.87rem;">'
                    f'🤖 Ranking <b style="color:{_c_hl}">{len(candidates)} candidates</b>'
                    f' with AI…</p>',
                    unsafe_allow_html=True,
                )
                bar.progress(0.55, text=f"AI ranking {len(candidates)} candidates…")

                try:
                    results = rank_candidates_batch(
                        candidates=candidates, job_context=job_context
                    )
                except RuntimeError as _err:
                    bar.empty()
                    _info.empty()
                    _em = str(_err)
                    if "api" in _em.lower() and "key" in _em.lower():
                        st.error(
                            "❌ **OpenAI API key error** — missing or invalid.\n\n"
                            "Fix: Streamlit Cloud → your app → ⚙️ Settings → Secrets → add:\n"
                            "```\nOPENAI_API_KEY = \"sk-proj-...\"\n```"
                        )
                    else:
                        st.error(f"❌ **AI ranking failed:** {_em}")
                    st.session_state.processed = False
                    st.stop()
            else:
                results = []

            bar.progress(1.0, text="✅ Done!")
            _info.empty()

            st.session_state.results   = results
            st.session_state.processed = True

            # Send emails to top 10
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
                    st.success(f"📧 Shortlist emails sent to {len(report['sent'])} candidates.")
                if report["failed"]:
                    st.warning(f"⚠️ Failed: {', '.join(report['failed'])}")

            # Cleanup
            deleted, _ = delete_uploaded_files(saved_paths)
            if deleted:
                st.caption(f"🗑️ {len(deleted)} uploaded file(s) deleted from server.")

    # ── Render results ────────────────────────────────────────────────────────
    if st.session_state.processed and st.session_state.results:
        results = st.session_state.results

        # Summary metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Screened", len(results))
        m2.metric("Shortlisted",    min(10, len(results)))
        avg_raw = sum(r.get("match_score", 0) for r in results) / len(results)
        m3.metric("Avg Score", f"{round(avg_raw / 10, 1)}/10")

        st.markdown("---")
        st.markdown(
            f'<div style="font-size:.75rem;font-weight:700;letter-spacing:.09em;'
            f'text-transform:uppercase;color:{_c_sub};margin-bottom:.9rem">'
            f'🏆 Top Candidates</div>',
            unsafe_allow_html=True,
        )

        # Quick result list
        for rank, r in enumerate(results[:10], 1):
            score    = r.get("match_score", 0)
            name     = r.get("candidate_name", "Unknown")
            email    = r.get("email", "")
            s_label, s_stars = _fmt_score(score)
            initials = "".join(w[0].upper() for w in name.split()[:2]) if name != "Unknown" else "?"

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
    <div><span class="iq-sv">{s_label}</span><span class="iq-sd">/10</span></div>
    <div class="iq-stars">{s_stars}</div>
  </div>
</div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown(
            f'<div style="font-size:.75rem;font-weight:700;letter-spacing:.09em;'
            f'text-transform:uppercase;color:{_c_sub};margin-bottom:.9rem">'
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
            s_label, s_stars = _fmt_score(score)

            concern_cls = "iq-tag-m" if score >= 70 else "iq-tag-r"
            str_html = " ".join(
                f'<span class="iq-tag iq-tag-g">✓ {s}</span>' for s in strengths
            )
            con_html = " ".join(
                f'<span class="iq-tag {concern_cls}">✗ {c}</span>' for c in concerns
            )

            with st.expander(
                f"#{rank} — {name}  ·  {s_label}/10  {s_stars}",
                expanded=(rank <= 3),
            ):
                st.markdown(f"""
<div class="iq-det">
  <div style="font-weight:700;font-size:1rem;color:{_c_tx}">{name}</div>
  <div style="font-size:.82rem;color:{_c_sub};margin-bottom:.8rem">{email}</div>
  <span style="font-size:1.8rem;font-weight:900;color:#2563EB">{s_label}</span>
  <span style="font-size:.95rem;color:{_c_sub}">/10 &nbsp;{s_stars}</span>
  <hr style="margin:.7rem 0">
  <p style="font-size:.75rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:{_c_sub};margin-bottom:4px">STRENGTHS</p>
  {str_html or f'<span style="color:{_c_sub};font-size:.85rem">None noted</span>'}
  <p style="font-size:.75rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:{_c_sub};margin:.7rem 0 4px">CONCERNS</p>
  {con_html or f'<span style="color:{_c_sub};font-size:.85rem">None noted</span>'}
  <p style="font-size:.75rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:{_c_sub};margin:.7rem 0 4px">RECOMMENDATION</p>
  {_rec_badge(rec)}
</div>""", unsafe_allow_html=True)

        # Full table + CSV download
        st.markdown("---")
        df = pd.DataFrame([
            {
                "Rank":           i + 1,
                "Candidate":      r.get("candidate_name", ""),
                "Score":          f"{_fmt_score(r.get('match_score', 0))[0]}/10",
                "Email":          r.get("email", ""),
                "Recommendation": r.get("recommendation", ""),
            }
            for i, r in enumerate(results)
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)

        csv_data = pd.DataFrame([
            {
                "Rank":                i + 1,
                "Name":                r.get("candidate_name", ""),
                "Email":               r.get("email", ""),
                "Score":               f"{_fmt_score(r.get('match_score', 0))[0]}/10",
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
            "⬇️ Download Full Results CSV",
            data=csv_data,
            file_name="talentiq_results.csv",
            mime="text/csv",
            use_container_width=True,
        )

    elif st.session_state.processed and not st.session_state.results:
        st.error("❌ No candidates could be processed. Check your CV files and try again.")

    else:
        # Idle placeholder
        st.markdown(f"""
<div style="text-align:center;padding:4rem 2rem;">
  <div style="font-size:2.8rem;margin-bottom:1rem">📂</div>
  <p style="font-size:1.05rem;color:{_c_sub}">
    Fill in the job description, upload CVs,<br>
    then click <b style="color:#2563EB">Screen Candidates</b>.
  </p>
  <p style="font-size:.85rem;color:{'#4B5563' if _dark else '#94A3B8'};margin-top:.5rem">
    Supports PDF, DOCX &amp; TXT &nbsp;·&nbsp; Powered by GPT-4o &nbsp;·&nbsp; Scores shown as X/10
  </p>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════ TESTIMONIALS ══════════════════════════════════════
st.markdown("""
<div class="iq-ts-sec">
  <h2 class="iq-ts-h">Loved by Recruiters</h2>
  <p class="iq-ts-s">Here's what recruitment professionals say about TalentIQ</p>
  <div class="iq-tg">
    <div class="iq-tc">
      <div class="iq-tq">&ldquo;</div>
      <p class="iq-tt">TalentIQ has transformed how we screen candidates. We reduced screening time by over 70% and our shortlists are stronger than ever.</p>
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
      <p class="iq-tt">What used to take hours of reading CVs now takes minutes. TalentIQ helps us focus on what really matters — speaking to candidates and closing placements.</p>
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
      <p class="iq-tt">The AI matching accuracy is incredible. We never miss great candidates anymore. TalentIQ is a game changer for our business.</p>
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


# ══════════════════════════ FOOTER CTA ════════════════════════════════════════
st.markdown("""
<div class="iq-fcta">
  <div class="iq-fi">👥</div>
  <h2 class="iq-fh">Stop Reading CVs.<br><span>Start Making Placements.</span></h2>
  <p class="iq-fs">Book a 15-minute demo and see how TalentIQ can save your team hours every single day.</p>
  <div>
    <button style="background:#2563EB;color:#fff;font-weight:600;font-size:.975rem;
      border:none;border-radius:8px;padding:.75rem 2rem;cursor:pointer;">
      Book a 15-Minute Demo &nbsp;&rarr;
    </button>
  </div>
  <p class="iq-fck">&#10003; No credit card required &nbsp;&nbsp; &#10003; Cancel anytime</p>
</div>

<hr>
<p style="text-align:center;color:#94A3B8;font-size:.78rem;padding-bottom:1rem">
  TalentIQ &middot; AI CV Screening &middot; Built with Streamlit &amp; GPT-4o
</p>
""", unsafe_allow_html=True)
