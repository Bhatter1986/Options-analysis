# ---- Base image -------------------------------------------------------------
FROM python:3.11-slim AS base

# Faster/cleaner Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UVICORN_WORKERS=2 \
    PYTHONPATH=/app

# System deps (only the basics; add more if your libs need)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# ---- Workdir ----------------------------------------------------------------
WORKDIR /app

# ---- Python deps layer (better cache) ---------------------------------------
# If you keep requirements.txt in repo root, this will cache deps smartly
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r /app/requirements.txt

# ---- App code ---------------------------------------------------------------
# Copy ENTIRE repo to ensure App/sudarshan/* is included
# (Render builds from repo root; this grabs everything that isn't .dockerignore'd)
COPY . /app

# Optional: show what got copied (debug during build)
# RUN find /app/App/sudarshan -maxdepth 2 -type f -print || true

# ---- Network ----------------------------------------------------------------
EXPOSE 8000

# ---- Start command ----------------------------------------------------------
# If your entry is main.py with `app = FastAPI(...)`
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
