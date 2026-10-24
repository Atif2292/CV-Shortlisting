# 🎯 RankCV — AI CV Screening for UK Hiring Teams

Streamlit app that scores and ranks candidate CVs against a job description, with a
recruiter-in-the-loop review workflow and a UK GDPR audit export.

- Paste or upload a job description, upload CVs (PDF, DOCX, DOC, TXT).
- **Cloud AI** (OpenAI, CVs scored in parallel batches of ~10) or **Private Engine** (keyword
  scoring on the server, no external AI calls).
- Names, contact details, postcodes, personal links, dates of birth and common
  protected-characteristic fields are redacted before Cloud AI scoring (best-effort).
- Every candidate starts as *Under Review*; recruiters record decisions, score adjustments
  and notes. The Excel report records what was actually decided and which engine scored each CV.
- Email-code sign-in, 10-CV free trial, paid plans read live from Stripe, atomic CV quotas.
- Uploaded files live in a per-run private temp folder and are deleted as soon as text is
  extracted. Results are kept in session memory only.

## Project structure

```
app.py                    Streamlit UI and screening flow
utils/
  config.py               All settings, plan limits and business details (env vars / st.secrets)
  account_tracker.py      Accounts, sign-in codes, Stripe entitlements, quotas (SQLAlchemy)
  admin.py                Operator CLI: list accounts, grant/revoke plans, force Stripe sync
  mailer.py               Sign-in code emails (Brevo API or SMTP with verified TLS)
  ai_scoring.py           JD parsing, CV feature extraction, Cloud AI + Private Engine scoring
  anonymizer.py           PII redaction before Cloud AI
  pdf_parser.py           PDF text extraction (PyMuPDF), drops hidden text
  docx_parser.py          DOCX text extraction (python-docx), drops hidden text
  cleanup.py              Per-run temp folders, random file names, stale-file sweep
  legal.py                Privacy notice, terms, DPA, sub-processors, cookie notice (?page=…)
tests/                    pytest suite (accounts, scoring, anonymiser, parsers)
dummy_cvs_pdf/            Sample CVs used by the test suite
static/rankcv-demo.mp4    "Watch how to use" video (hero and navbar buttons)
Dockerfile                Production image (includes antiword for .doc files)
```

## Run locally

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # optional: add OPENAI_API_KEY for Cloud AI
streamlit run app.py
```

Without email settings, local development shows the sign-in code on screen.
Without `OPENAI_API_KEY`, Cloud AI runs fall back to the Private Engine and the app says so.

Run the tests:

```bash
python -m pytest -q
```

## Deploy to production

### Option A — Streamlit Community Cloud (free tier, current setup)

1. In the Streamlit Cloud dashboard, the app must run **Python 3.11 or newer** (3.12 recommended).
   The Python version can't be changed on an existing app: if it's older, delete the app and
   redeploy it from this repo, choosing 3.12 under *Advanced settings*.
2. Open *Settings → Secrets* and paste `.streamlit/secrets.toml.example`, filled in. Required:
   `APP_SECRET`, `BREVO_API_KEY`, `STRIPE_SECRET_KEY`, `OPENAI_API_KEY` and `APP_ENV = "production"`.
   If one is missing the app shows exactly which instead of starting.
3. `packages.txt` installs `antiword` so legacy `.doc` CVs can be read.
4. Database: by default accounts live in a SQLite file on the app server. On the free tier that
   file is reset when the app restarts or redeploys. Paid plans are re-read from Stripe on the
   next sign-in, so customers keep their plan; usage counts and sign-in sessions start fresh.
   Set `DATABASE_URL` to a Postgres database (e.g. Supabase or Neon free tier) to keep them.
5. The *Keep-alive & uptime check* workflow pings the app every 10 minutes and fails (GitHub
   emails you) if it's down.

### Paying customers (automatic via Stripe)

- Create a Stripe **restricted key** with **Read** access to **Customers**, **Subscriptions** and
  **Payment Links** → `STRIPE_SECRET_KEY` (live key for real customers).
- The app reads the prices sold by the two Payment Links (`STRIPE_PRO_URL`, `STRIPE_AGENCY_URL`),
  so a subscription to the Pro link gives Pro and the Agency link gives Agency, in any currency.
  Nothing else on your Stripe account grants a plan.
- Customers subscribe, then sign in with the same email; the plan applies immediately and is
  re-checked every 15 minutes (renewals reset the monthly allowance; cancellations end it).
- Set `STRIPE_PORTAL_URL` (Customer Portal login link) so customers can cancel or update cards
  themselves.

### Option B — Docker on a UK/EU host

`Dockerfile` runs on Render, Fly.io, Railway, Cloud Run or a VPS (listens on `$PORT`, health
check at `/_stcore/health`). Use the same environment variables as above, plus a Postgres
`DATABASE_URL`.

### Operator commands

```bash
python -m utils.admin list
python -m utils.admin grant client@agency.co.uk agency --months 12   # invoiced customer
python -m utils.admin grant client@agency.co.uk trial                # revoke a manual plan
python -m utils.admin sync client@agency.co.uk                       # re-check Stripe now
```

## Before you take the first payment

- Have the Privacy Notice, Terms, DPA and sub-processor list (`utils/legal.py`) reviewed by a
  UK solicitor, and register with the ICO.
- Complete a DPIA for automated CV screening (ICO guidance on AI in recruitment).
- Check the testimonials on the page reflect real, attributable customer feedback (UK DMCC Act 2024).
- Send yourself a sign-in code in production to confirm email delivery (check spam too).
- Do a test purchase in Stripe test mode end-to-end, including cancellation.

## Limits and notes

- Scanned/image-only PDFs have no text layer and are skipped with a message (no OCR).
- Redaction is automated and best-effort; recruiters remain responsible for decisions.
- Cloud AI cost is roughly $0.50 per 100 CVs with `gpt-4o` (varies with CV length).
- Sign-in lasts 30 days (cookie). Screening results are kept only for the browser session —
  download the Excel report before closing or refreshing the page.

## License

MIT — use freely, attribution appreciated.
