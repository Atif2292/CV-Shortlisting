"""
utils/ai_scoring.py

Two-phase screening pipeline:
  Phase 1 — extract_resume_keywords(): local regex & structure extraction, zero LLM calls.
  Phase 2 — rank_candidates_batch(): holistic candidate ranking via GPT-4o with deterministic,
            explainable heuristic fallback when running offline or without an API key.
"""

import os
import re
import json
from pathlib import Path

USE_MOCK = False

# ── Common tech keywords for skill detection across modern engineering roles ──
TECH_KEYWORDS = [
    # Languages
    "python", "javascript", "typescript", "java", "c++", "c#", ".net", "go", "golang",
    "rust", "ruby", "swift", "kotlin", "scala", "php", "julia", "bash", "shell",
    # Frameworks & Libraries
    "fastapi", "django", "flask", "spring", "spring boot", "react", "vue", "angular",
    "next.js", "svelte", "node.js", "nodejs", "express", "laravel", "rails",
    # Databases & Caching
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "cassandra",
    "sqlite", "dynamodb", "sql", "nosql",
    # Cloud & Infrastructure
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ansible",
    "ci/cd", "jenkins", "github actions", "linux",
    # Data & AI / ML
    "machine learning", "deep learning", "nlp", "tensorflow", "pytorch", "scikit-learn",
    "pandas", "numpy", "spark", "kafka", "airflow", "tableau", "jupyter", "llm", "rag",
    # Architecture & Practices
    "rest", "rest api", "graphql", "grpc", "microservices", "agile", "scrum",
    "html", "css", "tailwind", "figma",
    # Sales, B2B & Commercial
    "it sales", "b2b sales", "enterprise sales", "saas sales", "lead generation",
    "account management", "pipeline management", "crm", "salesforce", "hubspot",
    "quota attainment", "quota", "cold calling", "prospecting", "deal closing",
    "solution selling", "business development", "client acquisition", "negotiation",
    "sales strategy", "key account", "contract negotiation", "channel sales",
    # Marketing & Growth
    "seo", "sem", "digital marketing", "content marketing", "google analytics",
    "growth marketing", "social media", "email marketing", "copywriting",
    # Product & Operations
    "product management", "product strategy", "roadmap", "user research", "jira",
]

EDUCATION_PATTERNS = [
    (r'\b(ph\.?d|doctorate)\b',                                  "PhD"),
    (r"\b(master'?s?|m\.?sc?\.?|m\.?eng\.?|mba)\b",             "Master's"),
    (r"\b(bachelor'?s?|b\.?sc?\.?|b\.?eng\.?|b\.?tech\.?)\b",   "Bachelor's"),
    (r"\b(diploma|associate'?s?)\b",                             "Diploma"),
]

EXPERIENCE_RE = [
    r'(\d+)\+?\s+years?\s+(?:of\s+)?(?:professional|work|industry|relevant|internship|hands-on)?\s*experience',
    r'experience\s+(?:of\s+)?(\d+)\+?\s+years?',
    r'(\d+)\+?\s+years?\s+(?:managing|building|working|in|specialising|specializing)',
    r'(\d+)\+?\s+yrs?\s+(?:of\s+)?experience',
]


def _has_skill(kw: str, text_lower: str) -> bool:
    """Check if skill keyword appears in text with proper word boundaries."""
    kw = kw.strip().lower()
    if not kw:
        return False
    if kw in ["c++", "c#", ".net"]:
        return bool(re.search(r'(?:^|[\s,;/()|])' + re.escape(kw) + r'(?:$|[\s,;/()|])', text_lower))
    return bool(re.search(r'\b' + re.escape(kw) + r'\b', text_lower))


def extract_job_context(jd_text: str) -> dict:
    """Extract job title, required skills, and years of experience from job description text."""
    if not jd_text or not jd_text.strip():
        return {
            "title": "General Role",
            "skills": "",
            "years_experience": 0,
            "description": "",
        }

    lines = [ln.strip() for ln in jd_text.splitlines() if ln.strip()]
    first_line = lines[0][:80] if lines else "Target Position"
    title = first_line

    # If line has Job Title: X, extract X
    m_title = re.search(r'(?:job\s+title|role|position)\s*:\s*([^\n\r]+)', jd_text, re.IGNORECASE)
    if m_title:
        title = m_title.group(1).strip()[:80]

    # Extract years of experience
    exp_years = 0
    m_exp = re.search(r'(\d+)\+?\s*years?(?:\s+(?:of\s+)?(?:experience|exp))?', jd_text, re.IGNORECASE)
    if m_exp:
        exp_years = int(m_exp.group(1))

    # Extract tech skills from JD text
    text_lower = jd_text.lower()
    found_skills = [kw for kw in TECH_KEYWORDS if _has_skill(kw, text_lower)]

    return {
        "title": title,
        "skills": ", ".join(found_skills[:12]),
        "years_experience": exp_years,
        "description": jd_text.strip(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1 — Local keyword extraction (no LLM)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_name(cv_text: str, filename: str = "") -> str:
    """Extract candidate name from CV text, filename, or email prefix."""
    # 1. Inspect first 5 non-empty lines of CV text
    lines = [l.strip() for l in cv_text.splitlines() if l.strip()]
    skip_headers = {
        "curriculum vitae", "resume", "cv", "profile", "contact",
        "personal information", "personal details", "summary", "about me",
        "work experience", "skills", "education",
    }
    for line in lines[:5]:
        clean_line = re.sub(r'[^A-Za-z\s\.]', '', line).strip()
        if clean_line.lower() in skip_headers:
            continue
        # Standard Name: 2 to 4 capitalized words, length between 3 and 40
        if re.match(r'^[A-Za-z]+([\s][A-Za-z]+){1,3}$', clean_line) and 3 <= len(clean_line) <= 40:
            return clean_line

    # 2. Extract from filename if available
    if filename:
        stem = Path(filename).stem
        clean_stem = re.sub(r'^\d+[\s_-]*', '', stem)
        clean_stem = re.sub(r'[\s_-]*(?:resume|cv|profile|final)[\s_-]*', '', clean_stem, flags=re.IGNORECASE)
        clean_stem = re.sub(r'[_.-]+', ' ', clean_stem).strip()
        if re.match(r'^[A-Za-z]+([\s][A-Za-z]+){1,3}$', clean_stem) and 3 <= len(clean_stem) <= 40:
            return clean_stem.title()

    # 3. Extract from email prefix
    m = re.search(r'([\w\.]+)@[\w\.-]+\.\w+', cv_text)
    if m:
        parts = m.group(1).split('.')
        if len(parts) == 2 and all(p.isalpha() and len(p) >= 2 for p in parts):
            return f"{parts[0].title()} {parts[1].title()}"

    return "Candidate"


def _extract_email(cv_text: str) -> str:
    m = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', cv_text)
    return m.group() if m else ""


def extract_resume_keywords(cv_text: str, required_skills: str = "", filename: str = "") -> dict:
    """
    Extract structured data from raw CV text using regex and string matching.
    Returns a rich candidate dictionary for AI or heuristic evaluation.
    """
    text_lower = cv_text.lower()

    # Required skills from the job posting
    req_list = [s.strip().lower() for s in required_skills.split(",") if s.strip()]
    matched_required = [s for s in req_list if _has_skill(s, text_lower)]

    # General tech keywords
    detected_tech = [kw for kw in TECH_KEYWORDS if _has_skill(kw, text_lower)]

    # Merge and dedup
    all_skills = list(dict.fromkeys(matched_required + detected_tech))[:25]

    # Years of experience
    exp_years = None
    for pattern in EXPERIENCE_RE:
        m = re.search(pattern, text_lower)
        if m:
            exp_years = int(m.group(1))
            break

    # Highest education level
    education = None
    for pattern, label in EDUCATION_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            education = label
            break

    # Extract lines that represent job titles / roles
    title_kws = {
        "engineer", "developer", "architect", "manager", "lead", "director",
        "analyst", "scientist", "consultant", "specialist", "designer", "intern",
    }
    job_titles = []
    for line in cv_text.splitlines():
        line = line.strip()
        if (4 < len(line) < 80
                and any(kw in line.lower() for kw in title_kws)
                and not any(c in line for c in ("@", "http", ".com"))):
            job_titles.append(line)
            if len(job_titles) >= 4:
                break

    return {
        "name":                    _extract_name(cv_text, filename),
        "email":                   _extract_email(cv_text),
        "skills_detected":         all_skills,
        "required_skills_matched": matched_required,
        "experience_years":        exp_years,
        "education":               education,
        "recent_roles":            job_titles,
        "cv_snippet":              cv_text[:3000].replace("\n", " ").strip(),
    }


from utils.anonymizer import anonymize_candidate_batch, restore_candidate_identities


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 — Batch ranking (OpenAI GPT-4o with deterministic fallback & BYOK)
# ─────────────────────────────────────────────────────────────────────────────

def _get_openai_api_key(custom_key: str = None) -> str:
    """Fetch OpenAI API key from custom user input, environment, or Streamlit secrets."""
    if custom_key and custom_key.strip():
        return custom_key.strip()
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        try:
            import streamlit as st
            if "OPENAI_API_KEY" in st.secrets:
                key = str(st.secrets["OPENAI_API_KEY"]).strip()
        except Exception:
            pass
    return key


BATCH_SYSTEM_PROMPT = """You are an expert senior technical recruiter performing a batch candidate ranking.
Candidates are presented with privacy-preserved anonymous identifiers (Candidate #1, Candidate #2) in compliance with UK GDPR Article 5(1)(c) data minimisation and the UK Equality Act 2010.
Evaluate candidates strictly on demonstrated technical competency, skill depth, and relevant experience alignment with zero demographic assumptions.

You will receive a job description and a JSON array of anonymised candidate summaries.
Analyse ALL candidates holistically and produce a RELATIVISTIC ranking — scores must reflect each candidate's standing relative to the others in this specific batch, not just absolute fit.

Return ONLY a JSON array (no markdown fences, no extra text), sorted best-first.
Each element must have exactly these fields:
{
  "candidate_index": <integer — same index as in the input array>,
  "candidate_name": "<string — keep the anonymous Candidate #X label>",
  "email": "<string>",
  "match_score": <integer 0-100>,
  "percentile": <integer 0-100, percentile rank within this batch>,
  "skills_match": "<comma-separated matched skills>",
  "relevant_experience": "<one concise sentence>",
  "strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
  "concerns": ["<concern 1>", "<concern 2>"],
  "recommendation": "<one sentence recruiter recommendation>"
}
Every candidate in the input must appear in the output array."""


def rank_candidates_batch(
    candidates: list,
    job_context: dict,
    custom_api_key: str = None,
    offline_mode: bool = False,
    base_url: str = None,
    return_audit: bool = False,
):
    """
    Phase 2: privacy-preserving candidate ranking pipeline.
    1. Anonymises all candidate PII (names, emails, phones, postcodes) before processing.
    2. Runs either 100% Offline Local Engine (air-gapped) or Cloud LLM using client's BYOK key.
    3. Restores real candidate identities locally in-memory for the recruiter.
    """
    if not candidates:
        return ([], {}) if return_audit else []

    # Step 1: Strip PII and generate anonymised candidate representations
    anon_candidates, identity_map, audit_stats = anonymize_candidate_batch(candidates)

    mode_label = "Private In-Memory Engine (Zero External AI Calls)" if offline_mode else "Cloud AI (BYOK - Privacy Preserved)"

    # Step 2: Evaluate candidates
    if offline_mode:
        raw_results = _mock_rank_batch(anon_candidates, job_context)
    else:
        api_key = _get_openai_api_key(custom_key=custom_api_key)
        if USE_MOCK or not api_key:
            mode_label = "Private In-Memory Engine (Zero External AI Calls)"
            raw_results = _mock_rank_batch(anon_candidates, job_context)
        else:
            try:
                from openai import OpenAI
                client_kwargs = {"api_key": api_key}
                if base_url and base_url.strip():
                    client_kwargs["base_url"] = base_url.strip()

                client = OpenAI(**client_kwargs)

                user_msg = (
                    f"JOB POSTING:\n"
                    f"Title: {job_context.get('title')}\n"
                    f"Required Skills: {job_context.get('skills')}\n"
                    f"Minimum Experience: {job_context.get('years_experience')} years\n"
                    f"Description: {job_context.get('description')}\n\n"
                    f"ANONYMISED CANDIDATES ({len(anon_candidates)} total - Zero PII):\n"
                    f"{json.dumps(anon_candidates, indent=2)}\n\n"
                    f"Rank all {len(anon_candidates)} candidates. Every candidate must appear in the output."
                )

                resp = client.chat.completions.create(
                    model="gpt-4o",
                    temperature=0.2,
                    max_tokens=16000,
                    messages=[
                        {"role": "system", "content": BATCH_SYSTEM_PROMPT},
                        {"role": "user",   "content": user_msg},
                    ],
                )
                raw = resp.choices[0].message.content or ""
                cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`")
                raw_results = json.loads(cleaned)
                if not isinstance(raw_results, list):
                    raise ValueError("Expected a JSON array from the LLM")
            except Exception as exc:
                print(f"[ai_scoring] Cloud LLM error (falling back to local deterministic scoring): {exc}")
                mode_label = "Private In-Memory Engine (Cloud Fallback)"
                raw_results = _mock_rank_batch(anon_candidates, job_context)

    # Step 3: Re-associate real candidate identities locally in-memory
    restored_results = restore_candidate_identities(raw_results, identity_map)

    # Attach processing mode and audit metadata to each candidate record
    for r in restored_results:
        r["processing_mode"] = mode_label

    if return_audit:
        return restored_results, audit_stats
    return restored_results


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic Heuristic Scoring (Explainable, Accurate, Grounded in Resume Data)
# ─────────────────────────────────────────────────────────────────────────────

def _mock_rank_batch(candidates: list, job_context: dict) -> list:
    """
    Deterministic, explainable heuristic ranking:
    Calculates candidate match score from required skill coverage, experience alignment,
    seniority fit, and education/certifications.
    """
    raw_skills = job_context.get("skills", "")
    req_skills = [s.strip().lower() for s in raw_skills.split(",") if s.strip()]
    target_exp = int(job_context.get("years_experience") or 3)
    title_lower = job_context.get("title", "").lower()

    ranked = []

    for idx, cand in enumerate(candidates):
        cand_name = cand.get("name") or f"Candidate #{idx + 1}"
        email = cand.get("email") or f"{cand_name.lower().replace(' ', '.')}@example.com"
        cand_skills = cand.get("skills_detected", [])
        snippet_lower = cand.get("cv_snippet", "").lower()
        cand_exp = cand.get("experience_years")
        education = cand.get("education") or "Bachelor's"
        roles = cand.get("recent_roles", [])

        # 1. Skill scoring (up to 50 points)
        if req_skills:
            matched_req = [s for s in req_skills if s in cand_skills or _has_skill(s, snippet_lower)]
            missing_req = [s for s in req_skills if s not in matched_req]
            skill_ratio = len(matched_req) / len(req_skills)
            skill_pts = skill_ratio * 42
            tech_depth = min(8, len(cand_skills) * 0.5)
            skill_score = min(50, skill_pts + tech_depth)
        else:
            matched_req = cand_skills[:5]
            missing_req = []
            skill_score = min(50, len(cand_skills) * 2.5)

        # 2. Experience scoring (up to 30 points)
        if cand_exp is not None:
            if cand_exp >= target_exp:
                exp_score = 30
            elif cand_exp > 0:
                exp_score = round(30 * (cand_exp / max(1, target_exp)))
            else:
                exp_score = 8
        else:
            # Estimate from number of roles mentioned
            exp_score = min(22, 12 + len(roles) * 3)

        # 3. Role / Seniority alignment (up to 10 points)
        senior_kw = ["senior", "lead", "architect", "principal", "head"]
        has_senior = any(any(sk in r.lower() for sk in senior_kw) for r in roles)
        target_senior = any(sk in title_lower for sk in senior_kw)

        if target_senior and has_senior:
            role_score = 10
        elif any(any(w in r.lower() for w in ["engineer", "developer", "scientist"]) for r in roles):
            role_score = 8
        else:
            role_score = 5

        # 4. Education & Certifications (up to 10 points)
        edu_score = 7
        if education in ["Master's", "PhD"]:
            edu_score = 9
        if "certified" in snippet_lower or "solutions architect" in snippet_lower:
            edu_score = min(10, edu_score + 2)

        # Domain mismatch detection (e.g. Pure Tech Engineer applying for Sales / Commercial role)
        sales_terms = ["sales", "account executive", "business development", "bdr", "sdr", "account manager", "commercial", "client acquisition"]
        is_sales_job = any(st in title_lower for st in sales_terms) or any(st in raw_skills.lower() for st in ["it sales", "b2b sales", "crm", "lead generation", "pipeline management", "quota"])
        
        cand_roles_lower = " ".join(r.lower() for r in roles)
        is_pure_tech_cand = any(tk in cand_roles_lower for tk in ["engineer", "developer", "architect", "programmer", "data scientist"])
        cand_sales_overlap = any(s in cand_skills for s in ["it sales", "b2b sales", "enterprise sales", "saas sales", "lead generation", "account management", "pipeline management", "crm", "salesforce", "hubspot", "quota attainment", "quota", "business development", "client acquisition"])

        domain_mismatch = (is_sales_job and is_pure_tech_cand and not cand_sales_overlap)

        if domain_mismatch:
            # Severely cap score: pure tech developers are unsuitable for sales manager positions
            match_score = min(28, max(15, round(exp_score * 0.35 + edu_score * 0.5)))
            strengths = []
            if cand_skills:
                strengths.append(f"Demonstrated technical skills in software development ({', '.join([s.title() for s in cand_skills[:3]])})")
            if education:
                strengths.append(f"Holds {education} degree")
            if not strengths:
                strengths.append("Verified academic and technical background")

            concerns = [
                "Zero demonstrated experience in B2B/IT sales, pipeline management, or quota achievement",
                "Candidate profile is technical software development, not commercial or client-facing sales"
            ]
            recommendation = "Unsuitable for this position. Candidate qualifications are purely technical development rather than commercial sales management."
        else:
            # Final score calculation (clamped between 25 and 98)
            match_score = min(98, max(25, round(skill_score + exp_score + role_score + edu_score)))

            # Strengths (grounded in candidate's actual qualifications)
            strengths = []
            if matched_req:
                top_skills = [s.title() for s in matched_req[:4]]
                strengths.append(f"Strong match in core skills: {', '.join(top_skills)}")
            if cand_exp is not None and cand_exp >= target_exp:
                strengths.append(f"{cand_exp}+ years of experience aligns with role seniority requirement")
            elif cand_exp is not None and cand_exp >= 3:
                strengths.append(f"{cand_exp} years demonstrated experience in technical roles")
            if education:
                strengths.append(f"Holds {education} degree with relevant technical foundation")
            if "certified" in snippet_lower:
                strengths.append("Holds verified industry/cloud certifications")
            if len(strengths) < 3:
                strengths.append(f"Hands-on experience with modern tooling ({', '.join([s.title() for s in cand_skills[:3]])})")

            # Concerns (grounded in actual missing criteria)
            concerns = []
            if missing_req:
                top_missing = [s.title() for s in missing_req[:3]]
                concerns.append(f"Missing core requirements: {', '.join(top_missing)}")
            if cand_exp is not None and cand_exp < target_exp:
                concerns.append(f"Experience ({cand_exp} yrs) is below requested {target_exp} yrs")
            if not matched_req:
                concerns.append("Limited direct evidence of target framework in recent projects")
            if len(concerns) < 2:
                concerns.append("Assess depth of domain design and practical execution in screen")

            # Recommendation based on score
            if match_score >= 85:
                recommendation = "Outstanding match with deep stack alignment and requisite seniority. Strongly recommended for interview."
            elif match_score >= 70:
                recommendation = "Solid candidate meeting most requirements with manageable gaps. Recommended for screening call."
            elif match_score >= 50:
                recommendation = "Moderate match with relevant foundation but missing key requirements. Consider for junior/adjacent variant."
            else:
                recommendation = "Does not meet the core technical and seniority requirements for this role. Not recommended."

        # Skills match string
        skills_match_str = ", ".join([s.title() for s in (matched_req or cand_skills[:3])])

        # Relevant experience sentence
        exp_disp = f"{cand_exp} years" if cand_exp else "Demonstrated"
        relevant_exp_sentence = f"{exp_disp} of relevant experience across {roles[0] if roles else 'software engineering'}."

        ranked.append({
            "candidate_index":    cand.get("candidate_index", idx),
            "candidate_name":     cand_name,
            "email":              email,
            "match_score":        match_score,
            "percentile":         0,
            "skills_match":       skills_match_str,
            "relevant_experience": relevant_exp_sentence,
            "strengths":          strengths[:3],
            "concerns":           concerns[:2],
            "recommendation":     recommendation,
        })

    # Sort descending by match score
    ranked.sort(key=lambda x: x["match_score"], reverse=True)

    n = len(ranked)
    for i, r in enumerate(ranked):
        r["percentile"] = round(100 * (n - i) / n)

    return ranked
