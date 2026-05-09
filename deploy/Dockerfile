
# BrightEdge Crawler — production image
#
# Multi-stage build:
#   1. builder: install deps + pre-download MiniLM model
#   2. runtime: slim image with just the app + cached model
#
# This keeps the final image lean and avoids the 30s model
# download on first request in production.

# Stage 1: builder
FROM python:3.11-slim AS builder

# System deps for lxml (extruct/bs4 dependency).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install Python deps into a virtualenv we can copy to runtime stage.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Pre-download the MiniLM model so it's baked into the image.
# This avoids ~30s of model download on first request in production.
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('all-MiniLM-L6-v2')"


#  Stage 2: runtime 
FROM python:3.11-slim AS runtime

# Runtime libs for lxml (smaller than dev versions used in builder).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for security.
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Bring in venv from builder stage.
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Bring in the pre-downloaded HuggingFace model cache.
COPY --from=builder /root/.cache/huggingface /home/appuser/.cache/huggingface
RUN chown -R appuser:appuser /home/appuser/.cache

# Copy application code.
COPY --chown=appuser:appuser app/ ./app/

USER appuser

# Production env defaults.
ENV ENV=prod \
    LOG_FORMAT=json \
    LOG_LEVEL=INFO \
    PORT=8000 \
    HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Healthcheck for orchestrators (Render, ECS, k8s).
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

# uvicorn handles ASGI + signals correctly. Single worker is fine for
# the demo; scaling = multiple containers, not multiple workers.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]