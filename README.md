# 🎯 TalentSift — AI Recruitment Screening Application

An end-to-end AI-powered recruitment tool built with **Python + Streamlit + OpenAI GPT-4o**.

- Upload up to 100 CVs (PDF & DOCX)
- AI scores each candidate against your job requirements (0–100)
- Auto-ranks candidates and generates a Top 10 shortlist
- Sends personalised shortlist emails via SMTP
- Deletes uploaded files after processing

---

## Project Structure

```
talentsift/
│
├── app.py                  ← Streamlit UI & orchestration logic
├── requirements.txt        ← Python dependencies
├── .env.example            ← Environment variable template
├── .gitignore
│
├── utils/
│   ├── __init__.py
│   ├── pdf_parser.py       ← PDF text extraction (PyMuPDF)
│   ├── docx_parser.py      ← DOCX text extraction (python-docx)
│   ├── ai_scoring.py       ← OpenAI GPT-4o CV screening
│   ├── email_sender.py     ← SMTP email automation
│   └── cleanup.py          ← Post-processing file deletion
│
├── uploads/                ← Temporary CV storage (auto-purged)
├── data/                   ← Optional: saved results / CSVs
└── .streamlit/
    └── config.toml         ← Streamlit server settings
```

---

## Quick Start (Local)

### 1. Clone / download the project

```bash
git clone https://github.com/your-org/talentsift.git
cd talentsift
```

### 2. Create & activate a virtual environment

**macOS / Linux**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (PowerShell)**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` in your editor and fill in:

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | Your OpenAI API key (from platform.openai.com) |
| `SMTP_HOST` | SMTP server hostname (e.g. `smtp.gmail.com`) |
| `SMTP_PORT` | SMTP port (usually `587` for TLS) |
| `SMTP_USER` | Your email address or SMTP username |
| `SMTP_PASSWORD` | Your email password or App Password |
| `EMAIL_FROM` | The "From" address in outgoing emails |

#### Gmail Setup (recommended for testing)
1. Enable 2-Factor Authentication on your Google account.
2. Go to **Google Account → Security → App Passwords**.
3. Generate an App Password for "Mail" → "Other".
4. Use that 16-character password as `SMTP_PASSWORD`.

### 5. Create required directories

```bash
mkdir -p uploads data
```

### 6. Run locally

```bash
streamlit run app.py
```

The app opens at **http://localhost:8501**

---

## VS Code Setup

1. Install the **Python** and **Pylance** extensions.
2. Open the project folder: `File → Open Folder`.
3. Select your venv interpreter: `Ctrl+Shift+P` → *Python: Select Interpreter* → choose `./venv`.
4. Install the **Streamlit** VS Code extension (optional, adds syntax helpers).
5. Open the terminal inside VS Code and run `streamlit run app.py`.

---

## Ubuntu VPS Deployment

Tested on Ubuntu 22.04 / 24.04.

### A. Server preparation

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv nginx git ufw
```

### B. Create a system user (optional, for security)

```bash
sudo adduser --disabled-password --gecos "" talentsift
sudo su - talentsift
```

### C. Clone and set up the project

```bash
git clone https://github.com/your-org/talentsift.git /home/talentsift/app
cd /home/talentsift/app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env          # fill in your real values
mkdir -p uploads data
```

### D. Create a systemd service

Exit to root / sudo user, then:

```bash
sudo nano /etc/systemd/system/talentsift.service
```

Paste:

```ini
[Unit]
Description=TalentSift Streamlit App
After=network.target

[Service]
User=talentsift
WorkingDirectory=/home/talentsift/app
Environment="PATH=/home/talentsift/app/venv/bin"
ExecStart=/home/talentsift/app/venv/bin/streamlit run app.py \
          --server.port=8501 \
          --server.headless=true
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable talentsift
sudo systemctl start talentsift
sudo systemctl status talentsift   # should show "active (running)"
```

### E. Nginx reverse proxy

```bash
sudo nano /etc/nginx/sites-available/talentsift
```

Paste (replace `yourdomain.com`):

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    # Max upload size — increase if you're uploading many large CVs
    client_max_body_size 200M;

    location / {
        proxy_pass         http://127.0.0.1:8501;
        proxy_http_version 1.1;

        # Required for Streamlit WebSocket (hot-reload & progress bars)
        proxy_set_header Upgrade    $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/talentsift /etc/nginx/sites-enabled/
sudo nginx -t        # check config
sudo systemctl reload nginx
```

### F. Domain & SSL (Let's Encrypt)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
sudo systemctl reload nginx
```

Certbot auto-renews certificates via a cron job.

### G. Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

### H. Useful commands

```bash
# View logs
sudo journalctl -u talentsift -f

# Restart after code updates
sudo systemctl restart talentsift

# Check Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

---

## How It Works

```
Recruiter fills form
        │
        ▼
CVs uploaded → saved to uploads/
        │
        ▼
Each CV parsed (PDF → PyMuPDF, DOCX → python-docx)
        │
        ▼
OpenAI GPT-4o screens each CV vs job description
 └─ Returns JSON: name, email, score, strengths, concerns, recommendation
        │
        ▼
Results sorted by match_score descending
        │
        ├─ Ranked table displayed in Streamlit UI
        │
        ├─ Top 10 → SMTP emails sent automatically
        │
        ├─ Full results exportable as CSV
        │
        └─ All uploaded CVs deleted from server
```

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | ✅ | — | OpenAI API key |
| `SMTP_HOST` | ✅ for email | `smtp.gmail.com` | SMTP server |
| `SMTP_PORT` | ✅ for email | `587` | SMTP port |
| `SMTP_USER` | ✅ for email | — | SMTP username / email |
| `SMTP_PASSWORD` | ✅ for email | — | SMTP password / App Password |
| `EMAIL_FROM` | — | `SMTP_USER` | From address on outgoing emails |

---

## Supported SMTP Providers

| Provider | SMTP Host | Port |
|---|---|---|
| Gmail | `smtp.gmail.com` | 587 |
| SendGrid | `smtp.sendgrid.net` | 587 |
| Mailgun | `smtp.mailgun.org` | 587 |
| AWS SES | `email-smtp.us-east-1.amazonaws.com` | 587 |
| Outlook | `smtp-mail.outlook.com` | 587 |

---

## Limitations & Notes

- **OpenAI costs**: GPT-4o charges per token. Screening 100 CVs costs approximately $0.30–$1.00 depending on CV length.
- **CV quality**: Text-based PDFs extract cleanly. Image/scanned PDFs will return empty text — OCR is not included.
- **Email deliverability**: Use a verified sender domain for production to avoid spam folders.
- **Data privacy**: Uploaded CVs are deleted from the server after processing. Results are held in Streamlit session state only (not persisted to disk unless you export the CSV).

---

## License

MIT — use freely, attribution appreciated.
