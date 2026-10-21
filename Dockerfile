# Production image for any container host (Render, Fly.io, Railway, Cloud Run, a VPS…).
# Choose a UK or EU region on the host and set the env vars from .env.example there.
FROM python:3.12-slim

# antiword: reads legacy .doc CVs on Linux
RUN apt-get update \
 && apt-get install -y --no-install-recommends antiword \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home app

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=app:app . .
USER app

ENV APP_ENV=production PYTHONUNBUFFERED=1
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://localhost:{os.getenv(\"PORT\",\"8501\")}/_stcore/health')"
CMD ["sh", "-c", "streamlit run app.py --server.port=${PORT:-8501} --server.address=0.0.0.0"]
