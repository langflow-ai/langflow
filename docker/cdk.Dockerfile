FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
ENV TZ=UTC
ENV UV_LOCKFILE=/app/uv.lock

WORKDIR /app

# Install system dependencies including PostgreSQL
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y \
    gcc \
    g++ \
    curl \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER root

# Install dependencies using uv
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=/app/uv.lock \
    --mount=type=bind,source=README.md,target=/app/README.md \
    --mount=type=bind,source=src/backend/base/uv.lock,target=/app/src/backend/base/uv.lock \
    --mount=type=bind,source=src/backend/base/README.md,target=/app/src/backend/base/README.md \
    --mount=type=bind,source=src/backend/base/pyproject.toml,target=/app/src/backend/base/pyproject.toml \
    --mount=type=bind,source=pyproject.toml,target=/app/pyproject.toml \
    uv pip install --system \
        build \
        wheel \
        setuptools && \
    uv sync --frozen --no-dev


ENV PATH="${PATH}:/root/.local/bin"

# Copy the application code
COPY ./ ./

# Create startup script
RUN echo '#!/bin/bash\n\
uv run uvicorn --factory langflow.main:create_app --host 0.0.0.0 --port 7860 --reload --env-file .env --loop asyncio --workers 1' > /app/start.sh && \
    chmod +x /app/start.sh

CMD ["/app/start.sh"]