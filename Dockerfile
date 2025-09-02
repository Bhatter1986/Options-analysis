# ---- Base image -------------------------------------------------------------
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    UVICORN_WORKERS=2

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---- Python deps (cache layer) ---------------------------------------------
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r /app/requirements.txt

# ---- App code ---------------------------------------------------------------
# Copy whole repo (but .dockerignore will exclude junk like .venv, __pycache__, etc.)
COPY . /app

# ---- Network ----------------------------------------------------------------
EXPOSE 8000

# ---- Start command ----------------------------------------------------------
# Bind to Render's PORT if present, else 8000 locally
CMD ["bash", "-lc", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${UVICORN_WORKERS}"]
