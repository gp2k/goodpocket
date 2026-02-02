# =============================================
# Bookmark Clustering API - Production Dockerfile
# Single-stage for faster Railway builds (uses PyPI pre-built wheels)
# =============================================

FROM python:3.11-slim

WORKDIR /app

# Runtime + build deps (for packages that need compile)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps in one step (faster than multi-stage: uses PyPI binaries)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY ./app ./app

# Non-root user
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

# Embedding model downloads on first request
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
