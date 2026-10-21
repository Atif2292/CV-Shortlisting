"""
utils/legal.py
Privacy notice, terms, DPA, sub-processors and cookie notice.

These are working drafts that match how the app actually behaves. Have them
reviewed by a UK solicitor before launch. Business details come from
utils/config.py (environment variables).
"""

from utils import config as c

PAGES = {
    "privacy": "Privacy Notice",
    "terms": "Terms of Service",
    "dpa": "Data Processing Agreement",
    "subprocessors": "Sub-processors",
    "cookies": "Cookie Notice",
}


def _company_block() -> str:
    text = f"**{c.COMPANY_NAME}**"
    if c.COMPANY_NUMBER:
        text += f", a company registered in England and Wales (company number {c.COMPANY_NUMBER})"
    if c.COMPANY_ADDRESS:
        text += f", {'registered office' if c.COMPANY_NUMBER else 'address'}: {c.COMPANY_ADDRESS}"
    text += "."
    if c.ICO_REG_NUMBER:
        text += f" ICO registration number: {c.ICO_REG_NUMBER}."
    return text + f" Contact: {c.CONTACT}."


def _privacy() -> str:
    return f"""
# Privacy Notice

*Last updated: {c.LEGAL_LAST_UPDATED}*

RankCV is operated by {_company_block()}

This notice explains how we handle two kinds of personal data:

1. **Account data** about recruiters who use RankCV. We are the **controller** of this data.
2. **Candidate data** contained in CVs that customers upload. The customer (the hiring
   organisation) is the **controller**; we act as their **processor** under our
   [Data Processing Agreement](?page=dpa).

## 1. Account data (we are the controller)

| What | Why | Lawful basis | How long |
|---|---|---|---|
| Work email address, company name | To sign you in with an emailed code and run your account | Contract (Art. 6(1)(b)) | While your account is active, then up to 24 months after last use |
| Plan, CV usage counts, sign-in and usage timestamps | To enforce plan limits and prevent abuse | Contract; legitimate interests (Art. 6(1)(f)) | As above |
| Billing details | Handled by Stripe; we see your subscription status, not your card | Contract; legal obligation | As required by tax law (6 years) |
| Hashed one-time sign-in codes | Security | Legitimate interests | Expire after 10 minutes |
| Sign-in session (hashed token; cookie in your browser) | Keep you signed in | Contract | {c.SESSION_DAYS} days, or until you sign out |

We do not sell account data or use it for advertising. We only email you about your
account (for example sign-in codes) unless you ask us to do otherwise.

## 2. Candidate data (customer is the controller)

When you screen CVs:

- **Files** are saved to a private, per-run temporary folder on our server under random
  names, read, and **deleted as soon as text has been extracted** (normally within seconds,
  and always when the run ends, even if it fails).
- **CV text and screening results** are held in server memory for your browser session only,
  so you can review them. They are not written to our database and are discarded when your
  session ends.
- **Cloud AI mode:** before text is sent to OpenAI, we automatically redact names, email
  addresses, phone numbers, postcodes, personal web links, dates of birth and common
  protected-characteristic fields (such as gender, marital status, religion and nationality).
  Redaction is automated and best-effort, so it may miss some details. OpenAI processes the
  redacted text in the United States under its API terms. Under those terms, API data is not
  used to train models and is kept for up to 30 days for abuse monitoring.
- **Private Engine mode:** scoring happens entirely on our server; no CV content is sent to
  any AI provider.
- **Your own OpenAI key (BYOK):** if you enter your own key, requests go to OpenAI under your
  organisation's agreement with OpenAI. Your key is held in server memory for your session
  only and is never stored or logged.

RankCV gives decision support only. Scores must be reviewed by a person before any decision
about a candidate is made (UK GDPR Article 22).

## 3. International transfers

OpenAI processes data in the United States. Our application host ({c.HOSTING_PROVIDER}) may also
process data outside the UK. Transfers rely on the UK Extension to the EU–US Data Privacy Framework
and/or the UK International Data Transfer Addendum. See [Sub-processors](?page=subprocessors).

## 4. Security

TLS in transit; per-run private temporary storage with automatic deletion; hashed sign-in
codes; access to production systems limited to authorised staff.

## 5. Your rights

You can ask to access, correct, delete or export your account data, or object to processing,
by contacting us ({c.CONTACT}). Candidates should contact the hiring organisation (the
controller) first; we will help that organisation respond. You can also complain to the
Information Commissioner's Office (ico.org.uk).
"""


def _terms() -> str:
    return f"""
# Terms of Service

*Last updated: {c.LEGAL_LAST_UPDATED}*

These terms are between you (the business using RankCV) and {_company_block()}

1. **Business use only.** RankCV is for organisations and recruiters acting in the course of
   business. By creating an account you confirm you have authority to accept these terms for
   your organisation.
2. **The service.** RankCV extracts text from CVs and produces match scores, strengths and
   concerns against a job description you provide. It is a **decision-support tool**. You must
   not use it to make solely automated decisions about candidates, and you are responsible for
   reviewing every result before acting on it.
3. **Your responsibilities.** You are the controller of candidate data. You must have a lawful
   basis to process the CVs you upload, give candidates an appropriate privacy notice, and
   handle candidate requests. Our [Data Processing Agreement](?page=dpa) forms part of these
   terms.
4. **Plans and billing.** The free trial includes {c.PLAN_QUOTAS['trial']} CV evaluations, once
   per organisation email. Paid plans are billed monthly in advance through Stripe and include
   the number of CV evaluations shown on the pricing page per billing period. Unused
   evaluations do not roll over. Screening pauses when you reach your limit; you can upgrade
   at any time.
5. **Cancellation.** You can cancel at any time from the billing portal or by contacting us. Your plan stays active
   until the end of the paid period. Fees already paid are non-refundable except where the law
   requires otherwise.
6. **Acceptable use.** Do not upload content you have no right to process, attempt to bypass
   plan limits or security, or use RankCV to discriminate unlawfully.
7. **Accuracy.** AI scoring can be wrong or incomplete. We do not guarantee any particular
   result and RankCV is not a substitute for professional judgement.
8. **Liability.** Nothing limits liability that cannot be limited by law. Otherwise, our total
   liability in any 12-month period is limited to the fees you paid us in that period, and we
   are not liable for indirect or consequential loss, or loss of profit or opportunity.
9. **Changes.** We may update these terms with at least 30 days' notice by email for material
   changes.
10. **Law.** These terms are governed by the laws of England and Wales, and the courts of
    England and Wales have exclusive jurisdiction.
"""


def _dpa() -> str:
    return f"""
# Data Processing Agreement (UK GDPR Article 28)

*Last updated: {c.LEGAL_LAST_UPDATED}*

This agreement applies when {c.COMPANY_NAME} ("Processor") processes candidate personal data
for a customer ("Controller") through RankCV.

- **Subject matter and duration:** CV screening for the duration of the customer's use of
  RankCV.
- **Nature and purpose:** text extraction, automated redaction, and scoring of CVs against a
  job description supplied by the Controller.
- **Data subjects:** job applicants and candidates.
- **Personal data:** contents of CVs (contact details, employment and education history,
  skills, and any other data the CV contains).
- **Special category data:** not required by the service. Controllers should avoid uploading
  it; automated redaction of such fields is best-effort.

The Processor will:

1. Process personal data only on the Controller's documented instructions (using the
   service as designed constitutes those instructions).
2. Ensure staff with access are bound by confidentiality.
3. Apply appropriate technical and organisational measures (Art. 32), including encryption
   in transit, per-run temporary storage deleted at the end of every run, no persistence of
   CV content in databases, and restricted production access.
4. Use only the sub-processors listed on the [Sub-processors](?page=subprocessors) page and
   give at least 30 days' notice of changes, during which the Controller may object.
5. Assist the Controller with data-subject requests, DPIAs and security obligations.
6. Notify the Controller without undue delay, and in any event within 48 hours, after
   becoming aware of a personal data breach affecting Controller data.
7. Delete Controller data at the end of processing. CV content is not retained after the
   session ends.
8. Make available information needed to demonstrate compliance and allow reasonable audits
   on 30 days' notice.

International transfers to sub-processors outside the UK are made under the UK
International Data Transfer Addendum or the UK Extension to the EU–US Data Privacy Framework.

Contact for data-protection matters: {c.CONTACT}.
"""


def _subprocessors() -> str:
    separate_db = not c.DATABASE_PROVIDER.startswith("Stored on our application host")
    hosting_purpose = "Application hosting" if separate_db else "Application hosting and account database"
    hosting_data = "CV files during a run; CV text in session memory" + (
        "" if separate_db else "; recruiter email, company, plan and usage counts")
    db_row = (f"| {c.DATABASE_PROVIDER} | Account database | Recruiter email, company, plan and usage counts "
              f"| See provider |\n" if separate_db else "")
    return f"""
# Sub-processors

*Last updated: {c.LEGAL_LAST_UPDATED}*

| Provider | Purpose | Data | Location |
|---|---|---|---|
| OpenAI, L.L.C. | AI scoring (Cloud AI mode only, unless you use your own key) | Redacted CV text, job description | United States |
| {c.HOSTING_PROVIDER} | {hosting_purpose} | {hosting_data} | See provider |
{db_row}| {c.EMAIL_PROVIDER} | Sending sign-in codes | Recruiter email address | See provider |
| Stripe Payments UK Ltd | Subscriptions and payments | Billing details (entered on Stripe) | UK / EU / US |
| Google LLC (Google Fonts) | Web font delivery | Visitor IP address and browser details | United States |

Private Engine mode sends no CV content to OpenAI.
"""


def _cookies() -> str:
    return f"""
# Cookie Notice

*Last updated: {c.LEGAL_LAST_UPDATED}*

RankCV does not use advertising or analytics cookies, so we don't ask for cookie consent.

- **Strictly necessary:** the app keeps a live connection between your browser and our server
  for your session. When you sign in we set a `rankcv_session` cookie so you stay signed in for
  up to {c.SESSION_DAYS} days (it is removed when you sign out). Our hosting provider may set a
  strictly necessary cookie to route your connection. These are exempt from consent under PECR.
- **Stripe:** when you open a checkout or billing page, Stripe sets its own cookies for fraud
  prevention and payment processing. See Stripe's cookie policy.
- **Google Fonts:** your browser downloads the Inter font from Google, which receives your IP
  address. Google Fonts does not set cookies.

Questions: {c.CONTACT}.
"""


def render_page(page: str) -> str:
    return {
        "privacy": _privacy,
        "terms": _terms,
        "dpa": _dpa,
        "subprocessors": _subprocessors,
        "cookies": _cookies,
    }[page]()
