# Dockerfile
# ----------
# Hugging Face Spaces Docker runtime entry point.
#
# HF Spaces requires the root Dockerfile.
# This builds and serves the FastAPI backend on port 7860
# (the HF Spaces default port).
#
# Local Docker usage (different port for dev):
#   docker build -f Dockerfile.backend -t fair-play-backend .  # uses port 8000
#   docker run --rm -p 8000:8000 fair-play-backend
#
# HF Spaces usage:
#   Push this repo to a Hugging Face Space (SDK: Docker).
#   HF builds this file automatically and exposes port 7860.

FROM python:3.11-slim

# HF Spaces runs as a non-root user — create one
RUN useradd -m -u 1000 appuser

WORKDIR /home/appuser/app

# ---------------------------------------------------------------------------
# Install uv — fast Python package manager
# ---------------------------------------------------------------------------
RUN pip install --no-cache-dir uv

# ---------------------------------------------------------------------------
# Install Python dependencies using uv
# --system: installs into the system Python (correct inside Docker, no venv needed)
# ---------------------------------------------------------------------------
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# ---------------------------------------------------------------------------
# Copy application source
# ---------------------------------------------------------------------------
COPY app/ ./app/

# Give the non-root user ownership (including the data dir for SQLite)
RUN mkdir -p /home/appuser/app/data && \
    chown -R appuser:appuser /home/appuser/app

USER appuser

# ---------------------------------------------------------------------------
# HF Spaces default port is 7860
# ---------------------------------------------------------------------------
ENV LLM_PROVIDER=mock
ENV APP_HOST=0.0.0.0
ENV APP_PORT=7860

EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
