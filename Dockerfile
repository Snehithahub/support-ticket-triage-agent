FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_SYSTEM_PYTHON=1 \
    EMBEDDINGS_CACHE_DIR=/opt/fastembed

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/* \
    && pip install "uv>=0.4,<1"

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN uv pip install --system ".[ui]"

# Bake the embedding model into the image so containers start without network access.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='/opt/fastembed')"

COPY kb ./kb
COPY config ./config
COPY ui ./ui
COPY data ./data

RUN useradd --create-home --uid 10001 app && chown -R app /app /opt/fastembed
USER app

ENV KB_DIR=/app/kb/articles POLICY_PATH=/app/config/automation_policy.yaml
EXPOSE 8000 8502
HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=5 \
    CMD curl -fsS http://localhost:8000/health || exit 1
CMD ["uvicorn", "triagedesk.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
