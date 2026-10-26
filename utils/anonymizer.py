"""
utils/anonymizer.py
UK GDPR Article 5(1)(c) Data Minimisation & Equality Act 2010 PII Stripper.

Removes candidate personal identifying information (PII) before CV data leaves
the recruiter's local environment or is passed to external AI models.

Only an explicit whitelist of candidate fields is forwarded (see ANON_LIST_FIELDS /
ANON_SCALAR_FIELDS); every free-text field in that whitelist is scrubbed with the same
name / contact / demographic rules. Redaction counters report every redaction performed.
"""

import re
import unicodedata
from typing import Tuple, Dict, List, Any, Iterable, Optional


COUNTER_KEYS = (
    "emails", "phones", "postcodes", "addresses", "profiles",
    "dob_age", "demographics", "ids", "names",
)


def _new_counts() -> Dict[str, int]:
    return {k: 0 for k in COUNTER_KEYS}


# ── Name heuristics (shared with utils/ai_scoring.py) ──

# Words that are never part of a person's name: CV headers, boilerplate, job titles, tech terms.
NAME_STOPWORDS = {
    # CV headers / boilerplate
    "curriculum", "vitae", "resume", "résumé", "cv", "profile", "contact", "personal", "information",
    "details", "summary", "about", "me", "objective", "experience", "work", "employment", "history",
    "education", "skills", "skill", "projects", "project", "certifications", "certification",
    "achievements", "awards", "languages", "interests", "hobbies", "references", "reference",
    "available", "upon", "on", "request", "declaration", "page", "of", "professional", "career",
    "technical", "key", "core", "competencies", "qualifications", "academic", "publications",
    "volunteering", "address", "phone", "email", "mobile", "linkedin", "github", "portfolio",
    "website", "birth", "nationality", "status", "name", "tech",
    # Job titles / seniority
    "senior", "junior", "principal", "intern", "trainee",
    "engineer", "developer", "programmer", "manager", "director", "analyst", "scientist",
    "consultant", "specialist", "designer", "architect", "administrator", "officer", "executive",
    "assistant", "associate", "coordinator", "representative", "accountant", "advisor", "technician",
    "supervisor", "nurse", "chef", "teacher", "student", "graduate", "fresher", "barista",
    "backend", "frontend", "full", "stack", "fullstack", "software", "data", "web",
    "cloud", "devops", "machine", "learning", "sales", "marketing", "product", "business",
    # Tech terms
    "python", "java", "javascript", "typescript", "golang", "kotlin",
    "scala", "php", "react", "angular", "vue", "django", "flask", "fastapi", "spring", "node",
    "docker", "kubernetes", "aws", "azure", "gcp", "sql", "mysql", "postgresql", "mongodb",
    "redis", "linux", "git", "html", "css", "api", "apis", "rest", "graphql", "microservices",
    # Document / organisation words ("TAX INVOICE", "Job Description", "Acme Ltd")
    "invoice", "receipt", "tax", "bill", "order", "statement", "shopping", "list", "job", "description",
    "title", "role", "position", "company", "ltd", "limited", "inc", "llc", "pvt", "university", "college",
    "school", "institute", "bank", "dear", "regards", "sincerely",
    # Generic e-mail local parts
    "info", "admin", "hello", "mail", "jobs", "careers", "hr", "test", "user", "dev", "ops",
    "office", "team", "support", "noreply",
}

# Lower-case particles allowed inside names ("Ludwig van Beethoven", "Maria de la Cruz").
NAME_PARTICLES = {"van", "von", "de", "da", "di", "del", "della", "der", "den", "la", "le", "du",
                  "bin", "binti", "al", "el", "ibn", "ter", "dos", "das", "y"}

_CJK_NAME_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]{2,4}")
_NAME_BAD_CHARS_RE = re.compile(r"[\d@/\\:|()\[\]{}<>=+#$%&*_~^\"]")


def _is_name_token(tok: str) -> bool:
    core = tok.strip(".,")
    if not core:
        return False
    if not all(unicodedata.category(c)[0] in "LM" or c in "'’-." for c in core):
        return False
    if not unicodedata.category(core[0]).startswith("L"):
        return False
    return True


def looks_like_name(line: str, allow_single: bool = False) -> bool:
    """True if a line plausibly is a person's name (Unicode-aware, 1–4 parts)."""
    if not line:
        return False
    s = line.strip().strip("•·-–—|:,;")
    s = re.sub(r"\s+", " ", s).strip()
    if not (2 <= len(s) <= 50):
        return False
    if _NAME_BAD_CHARS_RE.search(s):
        return False
    if _CJK_NAME_RE.fullmatch(s):
        return True
    tokens = s.split(" ")
    min_tokens = 1 if allow_single else 2
    if not min_tokens <= len(tokens) <= 4:
        return False
    real_parts = 0
    for tok in tokens:
        if not _is_name_token(tok):
            return False
        core = tok.strip(".,")
        low = core.lower()
        if low in NAME_STOPWORDS:
            return False
        if low in NAME_PARTICLES and core == low:
            continue
        first = core[0]
        # Cased scripts must be capitalised; caseless scripts (Devanagari, Arabic…) pass.
        if first.lower() != first.upper() and not first.isupper():
            return False
        real_parts += 1
    return real_parts >= min_tokens


# ── UK & International PII Regex Patterns ──

EMAIL_REGEX = re.compile(
    r'(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b'
)

# Social / portfolio profiles (with or without scheme)
PROFILE_URL_REGEX = re.compile(
    r'(?<![\w.-])(?:https?://)?(?:www\.)?'
    r'(?:(?:linkedin\.com/(?:in|pub|profile)|github\.com|gitlab\.com|bitbucket\.org|twitter\.com|x\.com|'
    r'medium\.com|stackoverflow\.com/users|behance\.net|dribbble\.com|kaggle\.com|leetcode\.com|'
    r'hackerrank\.com|instagram\.com|facebook\.com|fb\.com|youtube\.com|t\.me|wa\.me|about\.me|dev\.to)'
    r'/[^\s,;()<>"\']+'
    r'|[A-Za-z0-9-]+\.(?:medium\.com|github\.io|gitlab\.io|vercel\.app|netlify\.app|herokuapp\.com|'
    r'wordpress\.com|blogspot\.com|wixsite\.com|carrd\.co|substack\.com|hashnode\.dev|notion\.site)\b[^\s,;()<>"\']*)',
    re.IGNORECASE,
)

# Any explicit URL
GENERIC_URL_REGEX = re.compile(
    r'\bhttps?://[^\s<>"\'()]+|(?<![\w.@-])www\.[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+[^\s<>"\'(),;]*',
    re.IGNORECASE,
)

# Bare personal-site domains on "personal" TLDs (e.g. janedoe.dev, aryan.me)
PERSONAL_DOMAIN_REGEX = re.compile(
    r'(?<![\w@.-])[a-z0-9][a-z0-9-]{1,62}\.(?:dev|me|io|xyz|page|site|online|website|blog|portfolio|app)'
    r'(?:/[^\s,;()<>"\']*)?(?![\w.-])',
    re.IGNORECASE,
)
_DOMAIN_NOT_PII = {"socket.io", "asp.net", "vb.net", "ado.net", "gitlab.io", "github.io", "deno.dev",
                   "web.dev", "fly.io", "render.app", "draw.io", "pub.dev", "hashnode.dev"}

# Labelled website / portfolio lines
WEBSITE_LABEL_REGEX = re.compile(
    r'(?im)(?P<label>\b(?:website|portfolio|blog|personal\s+site|homepage|site\s+web)[ \t]*[:\-–][ \t]*)'
    r'(?P<val>[A-Za-z0-9][^\s|;\[\]]*\.[A-Za-z]{2,}[^\s|;]*)'
)

# National / personal ID numbers
ID_LABEL_REGEX = re.compile(
    r'(?i:\b(?:passport(?:[ \t]*(?:no\.?|number|#))?|pan(?:[ \t]*(?:card|no\.?|number))?|'
    r'aadh?aa?r(?:[ \t]*(?:card|no\.?|number))?|national[ \t]+insurance(?:[ \t]*(?:no\.?|number))?|'
    r'ni[ \t]*(?:no\.?|number)|ssn|social[ \t]+security(?:[ \t]*(?:no\.?|number))?|'
    r'driving[ \t]+licen[cs]e(?:[ \t]*(?:no\.?|number))?|voter[ \t]*id))'
    r'[ \t]*[:#=\-–]?[ \t]*(?P<val>[A-Z0-9][A-Z0-9\-]{4,18}[A-Z0-9])\b'
)
PAN_REGEX = re.compile(r'\b[A-Z]{5}\d{4}[A-Z]\b')
AADHAAR_REGEX = re.compile(r'\b[2-9]\d{3}[ \t]\d{4}[ \t]\d{4}\b')
NI_NUMBER_REGEX = re.compile(r'\b(?!BG|GB|NK|KN|TN|NT|ZZ)[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z][ \t]?\d{2}[ \t]?\d{2}[ \t]?\d{2}[ \t]?[A-D]\b')
SSN_REGEX = re.compile(r'\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b')

# Dates of birth and Age indicators
_MONTHS = (r'(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|'
           r'sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)')
_DATE_WORDS = (rf'(?:\d{{1,2}}(?:st|nd|rd|th)?[ \t\-/.]+(?:of[ \t]+)?{_MONTHS}\.?[ \t\-/.,]+\d{{2,4}}|'
               rf'{_MONTHS}\.?[ \t]+\d{{1,2}}(?:st|nd|rd|th)?,?[ \t]+\d{{4}})')
_DATE_NUM = r'(?:\d{1,2}[\-/.]\d{1,2}[\-/.]\d{2,4}|\d{4}[\-/.]\d{1,2}[\-/.]\d{1,2})'
_DOB_LABEL = (r'(?:d\.?o\.?b\b\.?|date[ \t]+of[ \t]+birth|birth[ \t]*date|birthday|'
              r'date[ \t]+de[ \t]+naissance|fecha[ \t]+de[ \t]+nacimiento|geburtsdatum)')

DOB_REGEXES = [
    # Label (or "born") followed by a recognisable date
    re.compile(rf'(?i)(?:\b{_DOB_LABEL}|\bborn(?:[ \t]+on)?)[ \t]*[:=\-–]?[ \t]*(?:{_DATE_WORDS}|{_DATE_NUM})'),
    # Explicit label with an unrecognised value — redact to end of the field
    re.compile(rf'(?i)\b{_DOB_LABEL}[ \t]*[:=\-–][ \t]*[^\n|;]{{1,30}}'),
    re.compile(r'(?:जन्म[ \t]*तिथि|出生日期|生日)[ \t]*[:：]?[ \t]*[^\n|;]{1,30}'),
    # Unlabelled full dates in words with a plausible birth year (e.g. "5th August 1995", "05-Aug-1995")
    re.compile(rf'(?i)\b\d{{1,2}}(?:st|nd|rd|th)?[ \t\-/]+(?:of[ \t]+)?{_MONTHS}\.?[ \t\-/,]+(?:19[4-9]\d|200\d|2010)\b'),
    re.compile(rf'(?i)\b{_MONTHS}\.?[ \t]+\d{{1,2}}(?:st|nd|rd|th)?,[ \t]*(?:19[4-9]\d|200\d|2010)\b'),
    # Age
    re.compile(r'(?i)\bage[ \t]*[:=\-–]?[ \t]*\d{2}\b(?:[ \t]*(?:years?|yrs?))?'),
    re.compile(r'(?i)\b\d{2}[ \t]*(?:years?|yrs?)[ \t\-]+old\b'),
]

# Gender, marital status, religion, caste, nationality, family names (values stop at line end)
_VALUE = r"[^\W\d_][\w'’.\-]*(?:[ \t]+(?![^\W\d_][\w'’\-]*[ \t]*[:=])[^\W\d_][\w'’.\-]*){0,3}"
DEMOGRAPHIC_REGEXES = [
    re.compile(rf'(?i)\b(?:gender|sex)[ \t]*[:=\-–][ \t]*{_VALUE}'),
    re.compile(rf'(?i)\bmarital[ \t]+status[ \t]*[:=\-–]?[ \t]*{_VALUE}'),
    re.compile(rf"(?i)\b(?:religion|caste|sub[ \t-]?caste|nationality|citizenship|ethnicity|ethnic[ \t]+origin|"
               rf"race|blood[ \t]+group|height|weight)[ \t]*[:=\-–][ \t]*{_VALUE}"),
    re.compile(rf"(?i)\b(?:father|mother|husband|wife|spouse|guardian)(?:['’]s|s)?[ \t]+name[ \t]*[:=\-–]?[ \t]*{_VALUE}"),
    re.compile(rf'\b[SDWC]/[Oo]\.?[ \t]+{_VALUE}'),
    re.compile(r'(?i)\b(?:unmarried|married|divorced|widowed|widower)\b'),
]

# Phone candidates — validated in code (9–15 digits, not a run of years)
PHONE_REGEX = re.compile(
    r'(?<![\w+/.\-])(?:\+[ \t]?\d{1,3}[ \t.\-]*)?(?:\([ \t]?\d{1,5}[ \t]?\)[ \t.\-]*)?\d(?:[ \t.\-]?\d){6,16}(?![\w/\-])'
)

# Standard UK Postcodes (e.g., SW1A 1AA, RG41 1JQ, EC2A 4NE, M1 1AE) — case-sensitive
UK_POSTCODE_REGEX = re.compile(
    r'\b(?:GIR ?0AA|[A-PR-UWYZ][A-HK-Y]?\d[A-Z\d]? ?\d[ABD-HJLNP-UW-Z]{2})\b'
)

# US ZIP after a state code (e.g. "CA 94105", "NY 10001-1234")
_US_STATES = ("AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|"
              "NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC")
US_ZIP_REGEX = re.compile(rf'\b(?P<state>{_US_STATES})[ \t]+(?P<zip>\d{{5}}(?:-\d{{4}})?)\b')

# Postal codes introduced by an explicit label anywhere ("PIN: 560001", "Zip code 94105")
LABELLED_POSTCODE_REGEX = re.compile(
    r'(?i)\b(?P<label>pin[ \t]*(?:code)?|pincode|postal[ \t]*code|post[ \t]*code|zip[ \t]*(?:code)?)'
    r'(?P<sep>[ \t]*[:#\-–]?[ \t]*)(?P<code>\d{5,6}(?:-\d{4})?|\d{3}[ \t]\d{3})\b'
)

# Indian PIN codes on lines that read like an address
_ADDRESS_CONTEXT_RE = re.compile(
    r'(?i)\b(?:address|india|nagar|colony|sector|road|marg|street|lane|apartments?|flat|near|opp\.?|'
    r'dist(?:rict)?|taluk|tehsil|village|city|state|mumbai|delhi|new delhi|bangalore|bengaluru|chennai|'
    r'hyderabad|kolkata|pune|ahmedabad|jaipur|lucknow|noida|gurgaon|gurugram|kochi|thane|indore|'
    r'maharashtra|karnataka|tamil nadu|kerala|gujarat|rajasthan|uttar pradesh|telangana|west bengal|'
    r'haryana|punjab|bihar|odisha|madhya pradesh|andhra pradesh)\b'
)
IN_PIN_REGEX = re.compile(r'(?<![\d\-])\b[1-9]\d{2}[ \t]?\d{3}\b(?![\d\-])')

# Labelled address lines ("Address: …", "Permanent Address - …")
ADDRESS_LINE_REGEX = re.compile(
    r'(?im)^[ \t]*(?:(?:home|current|permanent|residential|postal|correspondence|present)[ \t]+)?'
    r'(?:address|addr\.?|adresse|dirección|direccion|पता|地址)[ \t]*[:：\-–][ \t]*\S[^\n]*'
)

# Flat / apartment / suite numbers ("Flat 3", "Apt. 4B", "House No. 12")
UNIT_NUMBER_REGEX = re.compile(
    r'\b(?:Flat|Apt\.?|Apartment|Suite|House[ \t]+No\.?|Door[ \t]+No\.?|Plot[ \t]+No\.?)[ \t]*#?[ \t]*\d{1,5}[A-Za-z]?\b'
)

# Street addresses: house number + capitalised street name + suffix, at line start or after a separator.
# Strong suffixes always qualify; ambiguous ones (St, Dr, Park, Hill, Way…) must end the field.
_STRONG_SUFFIX = (r'(?:Road|Rd|Street|Avenue|Ave|Lane|Ln|Boulevard|Blvd|Crescent|Cres|Drive|Terrace|'
                  r'Gardens|Gdns|Grove|Mews|Parade|Marg)')
_WEAK_SUFFIX = r'(?:St|Dr|Way|Hill|Park|Place|Pl|Court|Ct|Close|Square|Sq|View|Rise|Walk|Row|Green)'
STREET_ADDRESS_REGEX = re.compile(
    r'(?m)(?:^|(?<=[:,;|]))(?P<sp>[ \t]*)'
    r'(?P<addr>\d{1,5}[A-Za-z]?(?:[/\-]\d{1,4})?,?[ \t]+(?:[A-Z][A-Za-z\'’.\-]*[ \t]+){1,3}'
    r'(?:' + _STRONG_SUFFIX + r'\b\.?|' + _WEAK_SUFFIX + r'\b\.?(?=[ \t]*(?:,|$))))'
)


def _ascii_fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _phone_is_plausible(val: str) -> bool:
    digits = re.sub(r'\D', '', val)
    if not 9 <= len(digits) <= 15:
        return False
    groups = [g for g in re.split(r'\D+', val) if g]
    # Runs of years ("2019 2020 2021", "2017-2019 2019") are dates, not phone numbers
    if groups and all(len(g) == 4 and g[:2] in ("19", "20") for g in groups):
        return False
    return True


def _is_year_run(val: str) -> bool:
    groups = [g for g in re.split(r'\D+', val) if g]
    return bool(groups) and all(len(g) == 4 and g[:2] in ("19", "20") for g in groups)


def _name_regexes(name_terms: Iterable[str]) -> List[re.Pattern]:
    """Build case-sensitive, word-bounded regexes for full names and each name part (≥2 chars)."""
    fulls, parts = set(), set()
    for name in name_terms or []:
        name = unicodedata.normalize("NFC", re.sub(r"\s+", " ", str(name or "")).strip())
        if not name or name.lower() in ("candidate",):
            continue
        tokens = [t.strip(".,") for t in re.split(r"[\s\-]+", name) if t.strip(".,")]
        core = [t for t in tokens if not (t.lower() in NAME_PARTICLES and t == t.lower())]
        # Do not scrub when the "name" is really a header / tech phrase
        if not core or all(t.lower() in NAME_STOPWORDS for t in core):
            continue
        for variant in {name, name.title(), name.upper(), _ascii_fold(name)}:
            if len(variant) >= 2:
                fulls.add(variant)
        for t in set(name.split(" ")) | set(tokens):
            t = t.strip(".,")
            if len(t) < 2 or t.lower() in NAME_STOPWORDS or (t.lower() in NAME_PARTICLES and t == t.lower()):
                continue
            for variant in {t, t[:1].upper() + t[1:], t.upper(), _ascii_fold(t)}:
                parts.add(variant)
    terms = sorted(fulls, key=len, reverse=True) + sorted(parts - fulls, key=len, reverse=True)
    out = []
    for term in terms:
        esc = re.sub(r"['’]", lambda _m: "['’]", re.escape(term))
        out.append(re.compile(r"(?<!\w)" + esc + r"(?!\w)"))
    return out


_NAME_LABEL_RE = re.compile(r"(?im)^[ \t]*(?:full[ \t]+)?(?:name|nom|nombre|nome)[ \t]*[:：][ \t]*([^\n|;,]{2,50})")


def collect_name_terms(text: str, candidate_name: str = "", email: str = "") -> List[str]:
    """Gather every plausible spelling of the candidate's name: given name, first line, labelled
    'Name:' lines and the e-mail local part (john.smith@ → John Smith)."""
    names: List[str] = []
    if candidate_name and candidate_name.strip() and not re.match(r"(?i)^candidate(?:\s*#\d+)?$", candidate_name.strip()):
        names.append(candidate_name.strip())
    text = text or ""
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    for piece in [first] + [p.strip() for p in first.split("|")]:
        if looks_like_name(piece, allow_single=False):
            names.append(piece.strip().strip("•·-–—|:,;").strip())
            break
    for m in _NAME_LABEL_RE.finditer(text):
        val = m.group(1).strip()
        if looks_like_name(val, allow_single=True):
            names.append(val)
    emails = [email] if email else []
    emails += EMAIL_REGEX.findall(text)
    for em in emails:
        local = em.split("@", 1)[0]
        user_alpha = re.sub(r"\d+", "", local).strip("._-")
        bits = [b for b in re.split(r"[._\-]+", user_alpha) if b]
        if len(bits) == 2 and all(b.isalpha() and len(b) >= 2 for b in bits):
            if not any(b.lower() in NAME_STOPWORDS for b in bits):
                names.append(f"{bits[0].title()} {bits[1].title()}")
        elif len(bits) == 1 and bits[0].isalpha() and len(bits[0]) >= 2:
            if bits[0].lower() not in NAME_STOPWORDS:
                names.append(bits[0].title())
    return list(dict.fromkeys(names))


def anonymize_text(
    text: str,
    candidate_name: str = "",
    candidate_label: str = "Candidate",
    name_terms: Optional[Iterable[str]] = None,
) -> Tuple[str, Dict[str, int]]:
    """
    Strips personal identifying information from a CV text string.

    Args:
        text: Raw CV text snippet.
        candidate_name: Candidate's real name if known, to scrub all occurrences.
        candidate_label: Anonymous replacement label (e.g. "Candidate #1").
        name_terms: Pre-computed name spellings (see collect_name_terms). When omitted they are
                    derived from candidate_name, the first line and any e-mail in the text.

    Returns:
        Tuple of (clean_anonymized_text, redaction_counts)
    """
    if not text:
        return "", {}

    counts = _new_counts()
    if name_terms is None:
        name_terms = collect_name_terms(text, candidate_name)
    cleaned = unicodedata.normalize("NFC", str(text))

    def _counter(key: str, token: str):
        def _sub(m):
            counts[key] += 1
            return token
        return _sub

    # 1. Emails
    cleaned = EMAIL_REGEX.sub(_counter("emails", "[REDACTED_EMAIL]"), cleaned)

    # 2. Profile links, personal sites and other URLs
    cleaned = PROFILE_URL_REGEX.sub(_counter("profiles", "[REDACTED_PROFILE]"), cleaned)
    cleaned = GENERIC_URL_REGEX.sub(_counter("profiles", "[REDACTED_PROFILE]"), cleaned)

    def _sub_domain(m):
        if m.group(0).lower().split("/")[0] in _DOMAIN_NOT_PII:
            return m.group(0)
        counts["profiles"] += 1
        return "[REDACTED_PROFILE]"
    cleaned = PERSONAL_DOMAIN_REGEX.sub(_sub_domain, cleaned)
    def _sub_site(m):
        counts["profiles"] += 1
        return m.group("label") + "[REDACTED_PROFILE]"
    cleaned = WEBSITE_LABEL_REGEX.sub(_sub_site, cleaned)

    # 3. Government / personal ID numbers
    def _sub_id_label(m):
        if len(re.findall(r"\d", m.group("val"))) < 2:
            return m.group(0)
        counts["ids"] += 1
        return "[REDACTED_ID]"
    cleaned = ID_LABEL_REGEX.sub(_sub_id_label, cleaned)

    def _sub_id(m):
        if _is_year_run(m.group(0)):
            return m.group(0)
        counts["ids"] += 1
        return "[REDACTED_ID]"
    for rx in (PAN_REGEX, AADHAAR_REGEX, NI_NUMBER_REGEX, SSN_REGEX):
        cleaned = rx.sub(_sub_id, cleaned)

    # 4. Dates of birth & age
    for rx in DOB_REGEXES:
        cleaned = rx.sub(_counter("dob_age", "[REDACTED_DOB]"), cleaned)

    # 5. Postal codes that could look like phone numbers (US ZIP+4 after a state, labelled codes)
    def _sub_zip(m):
        counts["postcodes"] += 1
        return f"{m.group('state')} [REDACTED_POSTCODE]"
    cleaned = US_ZIP_REGEX.sub(_sub_zip, cleaned)

    def _sub_labelled_code(m):
        counts["postcodes"] += 1
        return f"{m.group('label')}{m.group('sep')}[REDACTED_POSTCODE]"
    cleaned = LABELLED_POSTCODE_REGEX.sub(_sub_labelled_code, cleaned)

    # 6. Phone numbers (≥9 digits, not year sequences)
    def _sub_phone(m):
        if not _phone_is_plausible(m.group(0)):
            return m.group(0)
        counts["phones"] += 1
        return "[REDACTED_PHONE]"
    cleaned = PHONE_REGEX.sub(_sub_phone, cleaned)

    # 7. Postcodes: UK, Indian PIN in address context
    cleaned = UK_POSTCODE_REGEX.sub(_counter("postcodes", "[REDACTED_POSTCODE]"), cleaned)

    out_lines = []
    for line in cleaned.split("\n"):
        if _ADDRESS_CONTEXT_RE.search(line):
            line = IN_PIN_REGEX.sub(_counter("postcodes", "[REDACTED_POSTCODE]"), line)
        out_lines.append(line)
    cleaned = "\n".join(out_lines)

    # 8. Street addresses (labelled address lines, unit numbers, then house-number + street patterns)
    cleaned = ADDRESS_LINE_REGEX.sub(_counter("addresses", "[REDACTED_ADDRESS]"), cleaned)
    cleaned = UNIT_NUMBER_REGEX.sub(_counter("addresses", "[REDACTED_ADDRESS]"), cleaned)

    def _sub_street(m):
        counts["addresses"] += 1
        return m.group("sp") + "[REDACTED_ADDRESS]"
    cleaned = STREET_ADDRESS_REGEX.sub(_sub_street, cleaned)

    # 9. Demographic / protected characteristics
    for rx in DEMOGRAPHIC_REGEXES:
        cleaned = rx.sub(_counter("demographics", "[REDACTED_DEMOGRAPHIC]"), cleaned)

    # 10. Candidate name (full name first, then each part) — case-sensitive, word-bounded
    for rx in _name_regexes(name_terms):
        cleaned, n = rx.subn(candidate_label, cleaned)
        counts["names"] += n

    # Normalize excessive spaces
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

    return cleaned.strip(), counts


# ── Whitelisted candidate fields forwarded to the scoring engines ──
# Free-text fields are scrubbed; structured fields are type-checked. Anything else is dropped.
ANON_TEXT_FIELDS = ("cv_snippet", "validation_reason")
ANON_TEXT_LIST_FIELDS = ("recent_roles", "skills_detected", "required_skills_matched", "stuffing_flags")
ANON_SCALAR_FIELDS = {
    "experience_years": (int, float),
    "keyword_density": (int, float),
    "keyword_max_repeat": (int, float),
    "is_valid_cv": (bool,),
}
ANON_ENUM_FIELDS = {
    "education": {"PhD", "Master's", "Bachelor's", "Diploma"},
    "doc_status": {"cv", "uncertain", "not_cv", "job_description"},
}


def anonymize_candidate_batch(candidates: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[int, Dict[str, Any]], Dict[str, int]]:
    """
    Anonymize an entire batch of candidate dictionaries before passing to external AI models.

    Args:
        candidates: List of candidate dicts with 'name', 'email', 'skills_detected', 'cv_snippet', etc.

    Returns:
        Tuple of:
          - anonymized_candidates: Clean list for LLM consumption (whitelisted fields only, no PII)
          - identity_map: Local in-memory mapping from candidate index to real identity & stats
          - total_audit_stats: Aggregated counts of PII elements stripped across the batch
    """
    anonymized_list = []
    identity_map = {}
    total_stats = _new_counts()

    for idx, cand in enumerate(candidates):
        cand = cand or {}
        given_name = str(cand.get("name") or "").strip()
        if not given_name or given_name.lower() in ("candidate", "unknown"):
            try:
                from utils.ai_scoring import _extract_name
                extracted = _extract_name(cand.get("cv_snippet") or "", cand.get("filename") or "")
                if extracted and extracted.lower() not in ("candidate", "unknown"):
                    given_name = extracted
            except Exception:
                pass
        real_name = given_name or f"Candidate #{idx + 1}"
        real_email = str(cand.get("email") or "")
        anon_label = f"Candidate #{idx + 1}"

        raw_snippet = str(cand.get("cv_snippet") or "")
        name_terms = collect_name_terms(raw_snippet, given_name, real_email)
        stats = _new_counts()

        def _scrub(value: str) -> str:
            clean, st = anonymize_text(value, candidate_label=anon_label, name_terms=name_terms)
            for k, v in st.items():
                stats[k] = stats.get(k, 0) + v
            return clean

        anon_cand: Dict[str, Any] = {"candidate_index": idx, "name": anon_label}

        for field in ANON_TEXT_FIELDS:
            val = cand.get(field)
            if isinstance(val, str):
                anon_cand[field] = _scrub(val)

        for field in ANON_TEXT_LIST_FIELDS:
            val = cand.get(field)
            if isinstance(val, (list, tuple)):
                anon_cand[field] = [_scrub(str(v)[:200]) for v in val if isinstance(v, str) and v.strip()]

        for field, types in ANON_SCALAR_FIELDS.items():
            if field not in cand:
                continue
            val = cand.get(field)
            if bool in types:
                anon_cand[field] = val if isinstance(val, bool) else None
            else:
                anon_cand[field] = val if isinstance(val, types) and not isinstance(val, bool) else None

        for field, allowed in ANON_ENUM_FIELDS.items():
            val = cand.get(field)
            anon_cand[field] = val if val in allowed else None

        evidence = cand.get("skill_evidence")
        if isinstance(evidence, dict):
            anon_cand["skill_evidence"] = {
                _scrub(str(k)[:80]): v for k, v in evidence.items()
                if isinstance(k, str) and v in ("context", "list")
            }

        # Accumulate totals
        for k, v in stats.items():
            total_stats[k] = total_stats.get(k, 0) + v

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
