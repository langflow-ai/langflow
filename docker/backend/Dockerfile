FROM ubuntu:24.04 AS builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    python3.13 python3.13-venv python3.13-dev \
    gcc g++ build-essential libpq-dev cargo rustc git curl ca-certificates && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src/backend/ ./src/backend/

RUN python3.13 -m venv /app/.venv && \
    . /app/.venv/bin/activate && \
    uv sync --frozen --no-dev --no-cache && \
    uv pip install --force-reinstall pydantic==2.10.6 sqlalchemy==2.0.43 && \
    uv pip install --upgrade litellm>=1.61.15 setuptools>=78.1.1 && \
    # Cleanup
    find /app/.venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type f -name "*.pyc" -delete && \
    find /app/.venv -type f -name "*.pyo" -delete && \
    # Create tarball
    tar -czf /venv.tar.gz -C /app .venv

FROM ubuntu:24.04

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    python3.13 libpq5 curl ca-certificates git && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN groupadd -r aistudio && useradd -r -m -g aistudio aistudio

WORKDIR /app

# Extract tarball (MUCH faster than COPY directory)
COPY --from=builder /venv.tar.gz /tmp/
RUN tar -xzf /tmp/venv.tar.gz -C /app && rm /tmp/venv.tar.gz

COPY --chown=aistudio:aistudio LICENSE ./
COPY --chown=aistudio:aistudio src/backend/ ./src/backend/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/app/.venv/bin:$PATH" \
    HOST=0.0.0.0 \
    PORT=7860 \
    LANGFLOW_COMPONENTS_PATH="/app/.venv/lib/python3.13/site-packages/langflow/components:/app/src/backend/base/langflow/components"

RUN mkdir -p /tmp/langflow /home/aistudio/.cache /app/logs /app/data && \
    chown -R aistudio:aistudio /tmp/langflow /home/aistudio/.cache /app/logs /app/data /app/src/backend/base/langflow/alembic && \
    chmod 664 /app/src/backend/base/langflow/alembic/alembic.log || true

USER aistudio

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7860/api/v1/health || exit 1

CMD ["uvicorn", "langflow.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "7860"]