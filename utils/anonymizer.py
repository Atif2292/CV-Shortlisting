"""
utils/anonymizer.py
UK GDPR Article 5(1)(c) Data Minimisation & Equality Act 2010 PII Stripper.

Removes candidate personal identifying information (PII) before CV data leaves
the recruiter's local environment or is passed to external AI models.
"""

import re
from typing import Tuple, Dict, List, Any


# ── UK & International PII Regex Patterns ──

EMAIL_REGEX = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
    re.IGNORECASE
)

# Matches UK mobiles (+44 7..., 07...), UK landlines (+44 1/2..., 01/02...), and international numbers
PHONE_REGEX = re.compile(
    r'(?:(?:\+44\s?\(?0\)?\s?)|0)(?:7\d{3}|\d{4})\s?\d{3}\s?\d{3,4}\b|'
    r'(?:\+\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b',
    re.IGNORECASE
)

# Standard UK Postcodes (e.g., SW1A 1AA, RG41 1JQ, EC2A 4NE, M1 1AE, W1A 0AX)
UK_POSTCODE_REGEX = re.compile(
    r'\b(?:[A-Z]{1,2}[0-9][A-Z0-9]?\s*[0-9][A-Z]{2})\b',
    re.IGNORECASE
)

# UK & general street addresses
STREET_ADDRESS_REGEX = re.compile(
    r'\b\d{1,4}\s+[A-Za-z0-9\'-]+(?:\s+[A-Za-z0-9\'-]+){0,3}\s+'
    r'(?:Road|Rd|Street|St|Avenue|Ave|Lane|Ln|Drive|Dr|Way|Boulevard|Blvd|'
    r'Crescent|Cres|Court|Ct|Gardens|Gdns|Grove|Grv|Hill|Place|Pl|Park|Pk|'
    r'Terrace|Terr|Close|Cl)\b',
    re.IGNORECASE
)

# Social & Portfolio profile URLs (LinkedIn, GitHub, Twitter/X)
PROFILE_URL_REGEX = re.compile(
    r'(?:https?://)?(?:www\.)?'
    r'(?:linkedin\.com/(?:in|pub)/[^\s,;/()]+|'
    r'github\.com/[^\s,;/()]+|'
    r'twitter\.com/[^\s,;/()]+|'
    r'x\.com/[^\s,;/()]+)',
    re.IGNORECASE
)

# Dates of birth and Age indicators
DOB_AGE_REGEX = re.compile(
    r'\b(?:dob|date\s+of\s+birth|born)\s*[:=-]?\s*\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b|'
    r'\b(?:age)\s*[:=-]?\s*\d{2}\b',
    re.IGNORECASE
)

# Gender & Marital status declarations (often found on international/legacy CVs)
DEMOGRAPHIC_REGEX = re.compile(
    r'\b(?:gender|sex)\s*[:=-]?\s*(?:male|female|non-binary|other)\b|'
    r'\b(?:marital\s+status)\s*[:=-]?\s*(?:single|married|divorced|widowed)\b|'
    r'\b(?:nationality)\s*[:=-]?\s*[A-Za-z\s]{3,20}\b',
    re.IGNORECASE
)


def anonymize_text(text: str, candidate_name: str = "", candidate_label: str = "Candidate") -> Tuple[str, Dict[str, int]]:
    """
    Strips personal identifying information from a CV text string.

    Args:
        text: Raw CV text snippet.
        candidate_name: Candidate's real name if known, to scrub all occurrences.
        candidate_label: Anonymous replacement label (e.g. "Candidate #1").

    Returns:
        Tuple of (clean_anonymized_text, redaction_counts)
    """
    if not text:
        return "", {}

    counts: Dict[str, int] = {
        "emails": 0,
        "phones": 0,
        "postcodes": 0,
        "addresses": 0,
        "profiles": 0,
        "dob_age": 0,
        "demographics": 0,
        "names": 0,
    }

    # 1. Redact Emails
    def _sub_email(m):
        counts["emails"] += 1
        return "[REDACTED_EMAIL]"
    cleaned = EMAIL_REGEX.sub(_sub_email, text)

    # 2. Redact Phone numbers
    def _sub_phone(m):
        # Avoid redacting 4-digit years like 2021-2024
        val = m.group(0).strip()
        if re.match(r'^(?:19|20)\d{2}(?:[-–/](?:19|20)\d{2})?$', val):
            return val
        counts["phones"] += 1
        return "[REDACTED_PHONE]"
    cleaned = PHONE_REGEX.sub(_sub_phone, cleaned)

    # 3. Redact UK Postcodes
    def _sub_postcode(m):
        counts["postcodes"] += 1
        return "[REDACTED_POSTCODE]"
    cleaned = UK_POSTCODE_REGEX.sub(_sub_postcode, cleaned)

    # 4. Redact Street Addresses
    def _sub_address(m):
        counts["addresses"] += 1
        return "[REDACTED_ADDRESS]"
    cleaned = STREET_ADDRESS_REGEX.sub(_sub_address, cleaned)

    # 5. Redact Social & Profile Links
    def _sub_profile(m):
        counts["profiles"] += 1
        return "[REDACTED_PROFILE]"
    cleaned = PROFILE_URL_REGEX.sub(_sub_profile, cleaned)

    # 6. Redact DOB & Age
    def _sub_dob(m):
        counts["dob_age"] += 1
        return "[REDACTED_DOB]"
    cleaned = DOB_AGE_REGEX.sub(_sub_dob, cleaned)

    # 7. Redact Demographic / Protected Characteristics
    def _sub_demo(m):
        counts["demographics"] += 1
        return "[REDACTED_DEMOGRAPHIC]"
    cleaned = DEMOGRAPHIC_REGEX.sub(_sub_demo, cleaned)

    # 8. Redact candidate name occurrences if provided
    if candidate_name and candidate_name.strip() and candidate_name.lower() != "candidate":
        name_parts = [p.strip() for p in candidate_name.split() if len(p.strip()) > 2]
        if name_parts:
            # First scrub full name
            full_pattern = re.compile(r'\b' + re.escape(candidate_name.strip()) + r'\b', re.IGNORECASE)
            subbed, n = full_pattern.subn(candidate_label, cleaned)
            counts["names"] += n
            cleaned = subbed

            # Scrub individual first/last name parts if distinct
            for part in name_parts:
                part_pattern = re.compile(r'\b' + re.escape(part) + r'\b', re.IGNORECASE)
                subbed, n = part_pattern.subn(candidate_label, cleaned)
                counts["names"] += n
                cleaned = subbed

    # Normalize excessive spaces
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

    return cleaned.strip(), counts


def anonymize_candidate_batch(candidates: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[int, Dict[str, Any]], Dict[str, int]]:
    """
    Anonymize an entire batch of candidate dictionaries before passing to external AI models.

    Args:
        candidates: List of candidate dicts with 'name', 'email', 'skills_detected', 'cv_snippet', etc.

    Returns:
        Tuple of:
          - anonymized_candidates: Clean list for LLM consumption (no PII)
          - identity_map: Local in-memory mapping from candidate index to real identity & stats
          - total_audit_stats: Aggregated counts of PII elements stripped across the batch
    """
    anonymized_list = []
    identity_map = {}
    total_stats: Dict[str, int] = {
        "emails": 0,
        "phones": 0,
        "postcodes": 0,
        "addresses": 0,
        "profiles": 0,
        "dob_age": 0,
        "demographics": 0,
        "names": 0,
    }

    for idx, cand in enumerate(candidates):
        real_name = cand.get("name") or f"Candidate #{idx + 1}"
        real_email = cand.get("email") or ""
        anon_label = f"Candidate #{idx + 1}"

        # Anonymize the CV snippet
        raw_snippet = cand.get("cv_snippet", "")
        clean_snippet, stats = anonymize_text(raw_snippet, candidate_name=real_name, candidate_label=anon_label)

        # Accumulate totals
        for k, v in stats.items():
            total_stats[k] = total_stats.get(k, 0) + v

        # Construct anonymous candidate object for AI
        anon_cand = dict(cand)
        anon_cand["candidate_index"] = idx
        anon_cand["name"] = anon_label
        anon_cand["email"] = "[REDACTED_EMAIL]"
        anon_cand["cv_snippet"] = clean_snippet

        anonymized_list.append(anon_cand)

        # Save local identity map
        identity_map[idx] = {
            "real_name": real_name,
            "real_email": real_email,
            "anon_label": anon_label,
            "redaction_stats": stats,
            "total_redactions": sum(stats.values()),
        }

    return anonymized_list, identity_map, total_stats


def restore_candidate_identities(ranked_results: List[Dict[str, Any]], identity_map: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Re-associates the real candidate identity to the AI results using the local identity map.

    Args:
        ranked_results: List of candidate ranking results from LLM or heuristic.
        identity_map: Local in-memory identity mapping from anonymize_candidate_batch.

    Returns:
        List of results with original candidate names and emails restored, plus GDPR audit metadata.
    """
    restored = []
    for item in ranked_results:
        res = dict(item)
        idx = res.get("candidate_index")

        # If index found in map, restore
        if idx is not None and idx in identity_map:
            meta = identity_map[idx]
            res["candidate_name"] = meta["real_name"]
            res["email"] = meta["real_email"]
            res["anon_label"] = meta["anon_label"]
            res["gdpr_audit"] = {
                "pii_anonymized": True,
                "redactions": meta["redaction_stats"],
                "total_redactions": meta["total_redactions"],
            }
        restored.append(res)

    return restored
