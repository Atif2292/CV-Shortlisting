"""PII anonymiser tests: leak cases, over-redaction cases, counters and field whitelisting."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.anonymizer import (  # noqa: E402
    anonymize_candidate_batch,
    anonymize_text,
    looks_like_name,
    restore_candidate_identities,
)

LABEL = "Candidate #1"


def scrub(text, name=""):
    return anonymize_text(text, candidate_name=name, candidate_label=LABEL)


# ── Names ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name, body, leaks", [
    ("Siobhán O'Connor-Smith", "Reference: worked with Siobhán and Ms O’Connor-Smith; O'Connor led QA.",
     ["Siobhán", "O'Connor", "O’Connor", "Smith"]),
    ("José Müller", "José Müller built it. Contact JOSÉ MÜLLER or Jose Muller. Herr Müller agreed.",
     ["José", "Müller", "JOSÉ", "Jose", "Muller"]),
    ("Li Wu", "Li Wu joined in 2020. Wu mentored juniors; Li presented.", ["Li ", "Wu"]),
])
def test_names_scrubbed_including_unicode_and_short_parts(name, body, leaks):
    clean, counts = scrub(f"{name}\n{body}", name)
    for leak in leaks:
        assert leak not in clean, leak
    assert counts["names"] >= 3


def test_first_line_name_scrubbed_when_name_unknown():
    clean, counts = scrub("Priya Nair\nBackend Engineer\nPriya built payment APIs.", name="Candidate")
    assert "Priya" not in clean and "Nair" not in clean
    assert counts["names"] == 2


def test_name_from_email_local_part_scrubbed():
    clean, _ = scrub("Summary\nBackend engineer.\nReferee: Rohan Kapoor\nrohan.kapoor@yahoo.com")
    assert "Rohan" not in clean and "Kapoor" not in clean and "yahoo" not in clean


@pytest.mark.parametrize("bogus_name, text", [
    ("Python", "Python developer with Python 3 and FastAPI."),
    ("Experience", "Experience\n5 years of experience in Django."),
    ("Curriculum Vitae", "Curriculum Vitae\nSkills: Python"),
    ("References available on request", "References available on request"),
])
def test_header_or_tech_words_are_not_treated_as_names(bogus_name, text):
    clean, counts = scrub(text, bogus_name)
    assert clean == text.strip()
    assert counts["names"] == 0


@pytest.mark.parametrize("line, expected", [
    ("Aryan Mehta", True), ("ARYAN MEHTA", True), ("Li Wu", True), ("José Müller", True),
    ("Siobhán O'Connor-Smith", True), ("Maria de la Cruz", True), ("राहुल शर्मा", True), ("王伟", True),
    ("Python Developer", False), ("Curriculum Vitae", False), ("References available on request", False),
    ("Senior Backend Engineer", False), ("aryan@example.com", False), ("Experience", False),
    ("TAX INVOICE", False), ("2019 - 2021", False),
])
def test_looks_like_name(line, expected):
    assert looks_like_name(line) is expected


# ── Contact details & identifiers ────────────────────────────────────────────

@pytest.mark.parametrize("phone", [
    "+91 98765 43210", "+91-9876543210", "07700 900123", "(555) 123-4567", "+44 7700 900123",
    "+1-555-123-4567", "020 7946 0958", "+44 (0) 20 7946 0958", "555.123.4567",
])
def test_phone_numbers_redacted(phone):
    clean, counts = scrub(f"Phone: {phone} (mobile)")
    assert counts["phones"] == 1
    assert not any(ch.isdigit() for ch in clean)


@pytest.mark.parametrize("text, key", [
    ("London SW1A 1AA", "postcodes"), ("Manchester M1 1AE", "postcodes"), ("Reading RG41 1JQ", "postcodes"),
    ("Andheri West, Mumbai 400053", "postcodes"), ("PIN: 560001", "postcodes"), ("Pincode - 110001", "postcodes"),
    ("Boston, MA 02115", "postcodes"), ("Austin TX 78701-1234", "postcodes"),
    ("Address: 12 Baker Street, London", "addresses"), ("42 Oak Avenue, Reading", "addresses"),
    ("Flat 3, 221B Baker St, London", "addresses"), ("12 Hill Park, Leeds", "addresses"),
    ("Permanent Address - Flat 402, Sunshine Apartments, Andheri", "addresses"),
])
def test_addresses_and_postcodes_redacted(text, key):
    clean, counts = scrub(text)
    assert counts[key] >= 1
    assert not any(ch.isdigit() for ch in clean), clean


@pytest.mark.parametrize("text", [
    "DOB: 05/08/1995", "D.O.B - 1995-08-05", "Date of Birth: 5th August 1995", "Born on August 5, 1995",
    "5th August 1995", "05-Aug-1995", "DOB: not disclosed here", "Age: 29", "29 years old",
])
def test_date_of_birth_and_age_redacted(text):
    clean, counts = scrub(text)
    assert counts["dob_age"] >= 1
    assert "1995" not in clean and "29" not in clean and "disclosed" not in clean


@pytest.mark.parametrize("text, leaked", [
    ("Sex: M", " M"), ("Gender: Female", "Female"), ("Marital status: Married", "Married"),
    ("Marital Status - Unmarried", "Unmarried"), ("Unmarried", "Unmarried"), ("Religion: Hindu", "Hindu"),
    ("Caste: Brahmin", "Brahmin"), ("Nationality: Indian", "Indian"), ("Father's Name: Rajesh Kumar", "Rajesh"),
    ("S/o Ramesh Kumar", "Ramesh"), ("Citizenship: British", "British"),
])
def test_demographics_redacted(text, leaked):
    clean, counts = scrub(text)
    assert counts["demographics"] >= 1
    assert leaked not in clean


def test_demographic_value_stops_at_line_end():
    clean, counts = scrub("Nationality: Indian\nSkills: Python, Django\nSex: M  Religion: Hindu")
    assert "Skills: Python, Django" in clean
    assert "Indian" not in clean and "Hindu" not in clean
    assert counts["demographics"] == 3


@pytest.mark.parametrize("text", [
    "Passport No: K1234567", "Passport Number - Z9876543", "PAN: ABCDE1234F", "ABCDE1234F",
    "NI Number: AB123456C", "National Insurance No: AB 12 34 56 C", "SSN: 123-45-6789", "Aadhaar: 2345 6789 0123",
])
def test_identity_numbers_redacted(text):
    clean, counts = scrub(text)
    assert counts["ids"] == 1
    assert not any(ch.isdigit() for ch in clean)


@pytest.mark.parametrize("url", [
    "linkedin.com/in/janedoe", "https://www.linkedin.com/in/jane-doe-123/", "github.com/janedoe",
    "https://gitlab.com/janedoe", "https://medium.com/@janedoe", "janedoe.medium.com",
    "janedoe.github.io", "https://janedoe.com/portfolio", "www.janedoe.co.uk", "janedoe.dev",
    "https://twitter.com/janedoe", "x.com/janedoe", "dev.to/janedoe",
])
def test_personal_urls_redacted(url):
    clean, counts = scrub(f"Links: {url} | more")
    assert counts["profiles"] == 1
    assert "janedoe" not in clean and "jane-doe" not in clean


def test_labelled_website_on_plain_domain_redacted():
    clean, counts = scrub("Website: aryanmehta.com")
    assert "aryanmehta" not in clean and counts["profiles"] == 1


# ── Over-redaction guards ────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "Shipped 3 APIs the Django way",
    "Volunteered at Hill Park on weekends",
    "Python 3 microservices at Acme St",
    "Ported the service to Python 3 and Django Rest St",
    "Cut p99 from v2 5ms to 3ms",
    "Roles held in 2019 2020 2021",
    "Employment 2017-2019 2019-2021",
    "Reduced latency from 800ms to 120ms serving 2M+ daily requests",
    "AWS (EC2, RDS, Lambda, S3) and B2B SaaS",
    "B.Sc. Mathematics - St. Stephens College (2015-2018)",
    "St Stephens College, Hill Park Road",
    "CGPA 7.8 | Top 5 of 120",
    "Node.js, Next.js, Socket.IO and ASP.NET",
    "Built a pan-India sales dashboard",
    "Mentored a team of 4 junior engineers",
])
def test_no_over_redaction(text):
    clean, counts = scrub(text)
    assert clean == text
    assert sum(counts.values()) == 0


def test_counters_are_exact():
    text = (
        "Jane Roe\n"
        "jane.roe@example.com | j.roe@work.example.org\n"
        "+44 7700 900123 | 07700 900456 | (555) 123-4567\n"
        "Address: 1 High Street, Leeds LS1 4AP\n"
        "linkedin.com/in/janeroe | github.com/janeroe\n"
        "DOB: 01/02/1990 | Nationality: British\n"
        "Passport No: K1234567\n"
        "Jane led the migration in 2019 2020 2021.\n"
    )
    clean, counts = anonymize_text(text, "Jane Roe", LABEL)
    assert counts == {
        "emails": 2, "phones": 3, "postcodes": 1, "addresses": 1, "profiles": 2,
        "dob_age": 1, "demographics": 1, "ids": 1, "names": 2,
    }
    assert "2019 2020 2021" in clean


# ── Batch whitelist & identity restore ───────────────────────────────────────

def test_batch_whitelists_and_scrubs_every_free_text_field():
    cand = {
        "name": "Aryan Mehta",
        "email": "aryan.mehta@gmail.com",
        "cv_snippet": "Aryan Mehta\naryan.mehta@gmail.com | +91-9876543210\nSenior Backend Engineer at Razorpay",
        "recent_roles": ["Aryan Mehta — Lead Engineer, Razorpay", "Mentor to Mehta's team"],
        "validation_reason": "Uploaded by Aryan Mehta",
        "skills_detected": ["python", "fastapi"],
        "required_skills_matched": ["python"],
        "experience_years": 7,
        "education": "Bachelor's",
        "is_valid_cv": True,
        "doc_status": "cv",
        "skill_evidence": {"python": "context", "fastapi": "list", "bogus": "<script>"},
        "keyword_density": 0.12,
        "stuffing_flags": [],
        # Fields that must never be forwarded
        "filename": "Aryan_Mehta_CV.pdf",
        "phone": "+91-9876543210",
        "notes": "Aryan Mehta is my cousin",
        "raw_text": "Aryan Mehta full CV",
    }
    anon, identity, totals = anonymize_candidate_batch([cand])
    a = anon[0]
    assert set(a) <= {"candidate_index", "name", "cv_snippet", "validation_reason", "recent_roles", "skills_detected",
                      "required_skills_matched", "stuffing_flags", "experience_years", "keyword_density",
                      "keyword_max_repeat", "is_valid_cv", "education", "doc_status", "skill_evidence"}
    blob = repr(a)
    for leak in ("Aryan", "Mehta", "gmail", "9876543210", "cousin", "Aryan_Mehta_CV"):
        assert leak not in blob, leak
    assert a["name"] == LABEL and a["experience_years"] == 7 and a["education"] == "Bachelor's"
    assert a["skill_evidence"] == {"python": "context", "fastapi": "list"}
    assert a["recent_roles"][0].startswith(LABEL)
    assert totals["emails"] == 1 and totals["phones"] == 1 and totals["names"] >= 4
    assert identity[0]["real_name"] == "Aryan Mehta"

    restored = restore_candidate_identities(
        [{"candidate_index": 0, "candidate_name": LABEL, "email": "", "match_score": 50}], identity)
    assert restored[0]["candidate_name"] == "Aryan Mehta"
    assert restored[0]["email"] == "aryan.mehta@gmail.com"
    assert restored[0]["gdpr_audit"]["pii_anonymized"] is True


def test_batch_rejects_wrong_types_for_structured_fields():
    anon, _, _ = anonymize_candidate_batch([{
        "name": "Ben Okafor", "cv_snippet": "Ben Okafor\nEngineer",
        "experience_years": "seven (Ben Okafor)", "education": "Ben Okafor University", "is_valid_cv": "yes",
        "doc_status": "trust me",
    }])
    a = anon[0]
    assert a["experience_years"] is None and a["education"] is None
    assert a["is_valid_cv"] is None and a["doc_status"] is None
