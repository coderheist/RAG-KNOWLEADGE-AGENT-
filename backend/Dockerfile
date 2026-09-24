# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — builder: install dependencies into a virtual environment
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Install build tools required by some packages (e.g. asyncpg, pymupdf, paddleocr)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    tesseract-ocr \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — runtime: lean final image
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies for OCR and healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source and migrations
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Non-root user for security
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Phase 3 local models (BM25 sparse embedder + cross-encoder reranker), baked in so there are no
# runtime downloads. Keep the model names in sync with SPARSE_MODEL / RERANKER_MODEL in app/config.py.
ARG SPARSE_MODEL=Qdrant/bm25
ARG RERANKER_MODEL=Xenova/ms-marco-MiniLM-L-6-v2
ENV FASTEMBED_CACHE_PATH=/opt/fastembed_cache
RUN mkdir -p ${FASTEMBED_CACHE_PATH} \
 && python -c "from fastembed import SparseTextEmbedding; from fastembed.rerank.cross_encoder import TextCrossEncoder; SparseTextEmbedding('${SPARSE_MODEL}'); TextCrossEncoder('${RERANKER_MODEL}')" \
 && chown -R appuser:appgroup ${FASTEMBED_CACHE_PATH}

USER appuser

EXPOSE 8000

# Uvicorn with 1 worker to enforce process-level concurrency constraints
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
