"""
utils/ai_scoring.py

Two-phase screening pipeline:
  Phase 1 — extract_resume_keywords(): local regex extraction, zero LLM calls.
  Phase 2 — rank_candidates_batch(): one LLM call for the entire batch.

Set USE_MOCK = False and add OPENAI_API_KEY to .env to use real GPT-4o.
"""

import os
import re
import json
import random

USE_MOCK = False

# ── Common tech keywords for skill detection ──────────────────────────────────
TECH_KEYWORDS = [
    "python", "javascript", "typescript", "java", "c++", "c#", "go", "rust", "ruby",
    "swift", "kotlin", "scala", "php",
    "react", "vue", "angular", "next.js", "svelte",
    "node.js", "express", "fastapi", "django", "flask", "spring",
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "cassandra", "sqlite",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ansible",
    "git", "ci/cd", "jenkins", "github actions",
    "machine learning", "deep learning", "nlp", "tensorflow", "pytorch", "scikit-learn",
    "pandas", "numpy", "spark", "kafka", "airflow",
    "rest", "graphql", "grpc", "microservices",
    "agile", "scrum", "linux", "bash", "sql", "nosql", "html", "css", "tailwind",
]

EDUCATION_PATTERNS = [
    (r'\b(ph\.?d|doctorate)\b',                                  "PhD"),
    (r"\b(master'?s?|m\.?sc?\.?|m\.?eng\.?|mba)\b",             "Master's"),
    (r"\b(bachelor'?s?|b\.?sc?\.?|b\.?eng\.?|b\.?tech\.?)\b",   "Bachelor's"),
    (r"\b(diploma|associate'?s?)\b",                             "Diploma"),
]

EXPERIENCE_RE = [
    r'(\d+)\+?\s+years?\s+of\s+(?:professional\s+)?experience',
    r'(\d+)\+?\s+years?\s+(?:of\s+)?(?:work|industry|relevant)',
    r'experience\s+of\s+(\d+)\+?\s+years?',
    r'(\d+)\+?\s+yrs?\s+(?:of\s+)?experience',
]

# ── Mock data pools ───────────────────────────────────────────────────────────
MOCK_NAMES = [
    "Arjun Sharma", "Priya Patel", "Rahul Mehta", "Sneha Iyer",
    "Kiran Desai", "Amit Nair", "Divya Krishnan", "Rohan Gupta",
    "Anjali Singh", "Vikram Joshi", "Pooja Reddy", "Suresh Kumar",
    "Nisha Verma", "Aakash Malhotra", "Ritu Banerjee", "Dev Kapoor",
    "Meera Pillai", "Saurabh Tiwari", "Kavya Rao", "Nikhil Bose",
]
MOCK_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "proton.me"]

STRENGTHS_POOL = [
    "Strong problem-solving skills demonstrated through projects",
    "Excellent communication and teamwork abilities",
    "Relevant industry experience matching job requirements",
    "Proficient in required tech stack",
    "Track record of delivering projects on time",
    "Leadership experience managing small teams",
    "Open source contributions showing initiative",
    "Certifications aligned with role requirements",
    "Fast learner with diverse technical background",
    "Strong academic foundation in Computer Science",
    "Experience with Agile/Scrum methodologies",
    "Portfolio demonstrates hands-on practical skills",
]

CONCERNS_POOL = [
    "Limited years of experience for a senior role",
    "No direct experience with required cloud platform",
    "Gap in employment history not explained",
    "Skills listed without evidence of applied usage",
    "No formal degree in relevant field",
    "Overqualified — may not stay long-term",
    "Primarily startup experience, no enterprise exposure",
    "Missing some key technical skills from job spec",
    "Location may require relocation support",
    "Salary expectations may exceed budget",
]

RECOMMENDATIONS_POOL = [
    "Strong candidate who aligns well with the role. Recommended for technical interview.",
    "Good overall profile with minor gaps. Worth a screening call to assess fit.",
    "Meets most requirements. Recommend advancing to the next stage.",
    "Solid background but lacks some key skills. Consider for a junior variant of the role.",
    "Impressive profile that exceeds expectations. Fast-track to final round.",
    "Average match. Recommend only if stronger candidates are unavailable.",
    "Some red flags in experience gaps. Needs clarification before proceeding.",
    "Well-rounded candidate with a strong portfolio. Highly recommended.",
    "Good technical skills but limited leadership experience for this role.",
    "Borderline candidate. Suggest a brief phone screen to evaluate further.",
]


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1 — Local keyword extraction (no LLM)
# ─────────────────────────────────────────────────────────────────────────────

def extract_resume_keywords(cv_text: str, required_skills: str = "") -> dict:
    """
    Extract structured data from raw CV text using regex and string matching.
    Returns a compact dict suitable for batching into a single LLM ranking call.
    """
    text_lower = cv_text.lower()

    # Required skills from the job posting
    req_list = [s.strip().lower() for s in required_skills.split(",") if s.strip()]
    matched_required = [s for s in req_list if s in text_lower]

    # General tech keywords
    detected_tech = [kw for kw in TECH_KEYWORDS if kw in text_lower]

    # Merge, dedup, cap at 20
    all_skills = list(dict.fromkeys(matched_required + detected_tech))[:20]

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

    # Heuristic: lines that look like job titles
    title_kws = {"engineer", "developer", "architect", "manager", "lead", "director",
                 "analyst", "scientist", "consultant", "specialist", "designer"}
    job_titles = []
    for line in cv_text.splitlines():
        line = line.strip()
        if (4 < len(line) < 80
                and any(kw in line.lower() for kw in title_kws)
                and not any(c in line for c in ("|", "@", "http", ".com"))):
            job_titles.append(line)
            if len(job_titles) >= 3:
                break

    return {
        "name":                    _extract_name(cv_text),
        "email":                   _extract_email(cv_text),
        "skills_detected":         all_skills,
        "required_skills_matched": matched_required,
        "experience_years":        exp_years,
        "education":               education,
        "recent_roles":            job_titles,
        "cv_snippet":              cv_text[:400].replace("\n", " ").strip(),
    }


def _extract_name(cv_text: str) -> str:
    lines = [l.strip() for l in cv_text.splitlines() if l.strip()]
    if lines and re.match(r'^[A-Za-z]+([\s][A-Za-z]+){1,3}$', lines[0]):
        return lines[0]
    return ""


def _extract_email(cv_text: str) -> str:
    m = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', cv_text)
    return m.group() if m else ""


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 — Batch LLM ranking (one call for all candidates)
# ─────────────────────────────────────────────────────────────────────────────

BATCH_SYSTEM_PROMPT = """You are an expert senior technical recruiter performing a batch candidate ranking.

You will receive a job description and a JSON array of candidate summaries.
Analyse ALL candidates holistically and produce a RELATIVISTIC ranking — scores must reflect each candidate's standing relative to the others in this specific batch, not just absolute fit.

Return ONLY a JSON array (no markdown fences, no extra text), sorted best-first.
Each element must have exactly these fields:
{
  "candidate_index": <integer — same index as in the input array>,
  "candidate_name": "<string>",
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


def rank_candidates_batch(candidates: list, job_context: dict) -> list:
    """
    Phase 2: single LLM call that ranks ALL candidates at once.

    candidates — list of dicts from extract_resume_keywords()
    job_context — {title, skills, years_experience, description}
    Returns a list of result dicts sorted best-first, or [] on failure.
    """
    if not candidates:
        return []

    if USE_MOCK:
        return _mock_rank_batch(candidates, job_context)

    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    user_msg = (
        f"JOB POSTING:\n"
        f"Title: {job_context.get('title')}\n"
        f"Required Skills: {job_context.get('skills')}\n"
        f"Minimum Experience: {job_context.get('years_experience')} years\n"
        f"Description: {job_context.get('description')}\n\n"
        f"CANDIDATES ({len(candidates)} total):\n"
        f"{json.dumps(candidates, indent=2)}\n\n"
        f"Rank all {len(candidates)} candidates. Every candidate must appear in the output."
    )

    try:
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
        results = json.loads(cleaned)
        if not isinstance(results, list):
            raise ValueError("Expected a JSON array from the LLM")
        return results
    except Exception as exc:
        print(f"[ai_scoring] Batch ranking error: {exc}")
        # Re-raise so the UI can display the real error message to the user
        raise RuntimeError(str(exc)) from exc


# ─────────────────────────────────────────────────────────────────────────────
# Mock batch ranking
# ─────────────────────────────────────────────────────────────────────────────

def _mock_rank_batch(candidates: list, job_context: dict) -> list:
    """Deterministic mock ranking — no API call."""
    required = [s.strip() for s in job_context.get("skills", "").split(",") if s.strip()]
    ranked = []

    for idx, cand in enumerate(candidates):
        snippet = cand.get("cv_snippet", "")
        seed = len(snippet) + (hash(snippet[:50]) % 1000 if snippet else idx * 37)
        rng = random.Random(seed)

        score = rng.randint(30, 95)
        strengths = rng.sample(STRENGTHS_POOL, 3)
        concerns  = rng.sample(CONCERNS_POOL,  2)

        matched = cand.get("required_skills_matched") or cand.get("skills_detected", [])
        n_match  = max(1, int(len(required) * score / 100)) if required else 0
        if required:
            skill_str = ", ".join(rng.sample(required, min(n_match, len(required))))
        else:
            skill_str = ", ".join(matched[:3]) if matched else "General skills"

        name  = cand.get("name") or rng.choice(MOCK_NAMES)
        email = cand.get("email") or (
            f"{rng.choice(MOCK_NAMES).lower().replace(' ', '.')}"
            f"{rng.randint(10, 99)}@{rng.choice(MOCK_DOMAINS)}"
        )

        ranked.append({
            "candidate_index":    idx,
            "candidate_name":     name,
            "email":              email,
            "match_score":        score,
            "percentile":         0,   # filled in after sort
            "skills_match":       skill_str,
            "relevant_experience": (
                f"{rng.randint(1, 8)} years of relevant experience in similar roles, "
                f"with exposure to {rng.choice(required) if required else 'the required stack'}."
            ),
            "strengths":          strengths,
            "concerns":           concerns,
            "recommendation":     rng.choice(RECOMMENDATIONS_POOL),
        })

    ranked.sort(key=lambda x: x["match_score"], reverse=True)

    n = len(ranked)
    for i, r in enumerate(ranked):
        r["percentile"] = round(100 * (n - i) / n)

    return ranked
