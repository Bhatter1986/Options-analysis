# ---- Base ----
FROM python:3.11-slim

# System deps (faster wheels, SSL, tz)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates tzdata && \
    rm -rf /var/lib/apt/lists/*

# Workdir
WORKDIR /app

# Copy only requirements first (better cache)
COPY requirements.txt /app/

# Install Python deps
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . /app

# Security: non-root user
RUN useradd -m appuser
USER appuser

# FastAPI expects PORT (Render sets this automatically)
ENV PORT=10000 \
    PYTHONUNBUFFERED=1

# Expose (for local)
EXPOSE 10000

# Start
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "${PORT}"]
