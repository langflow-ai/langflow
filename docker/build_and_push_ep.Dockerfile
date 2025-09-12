# syntax=docker/dockerfile:1
# Keep this syntax directive! It's used to enable Docker BuildKit

################################
# BUILDER-BASE
# Used to build deps + create our virtual environment
################################

# 1. use python:3.12.3-slim as the base image until https://github.com/pydantic/pydantic-core/issues/1292 gets resolved
# 2. do not add --platform=$BUILDPLATFORM because the pydantic binaries must be resolved for the final architecture
# Use a Python image with uv pre-installed
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Install the project into `/app`
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y \
    # deps for building python deps
    build-essential \
    git \
    # npm
    npm \
    # gcc
    gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy files first to avoid permission issues with bind mounts
COPY ./uv.lock /app/uv.lock
COPY ./README.md /app/README.md
COPY ./pyproject.toml /app/pyproject.toml
COPY ./src/backend/base/README.md /app/src/backend/base/README.md
COPY ./src/backend/base/uv.lock /app/src/backend/base/uv.lock
COPY ./src/backend/base/pyproject.toml /app/src/backend/base/pyproject.toml
COPY ./src/lfx/README.md /app/src/lfx/README.md
COPY ./src/lfx/pyproject.toml /app/src/lfx/pyproject.toml

RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv sync --frozen --no-install-project --no-editable --extra nv-ingest --extra postgresql

COPY ./src /app/src

COPY src/frontend /tmp/src/frontend
WORKDIR /tmp/src/frontend
RUN --mount=type=cache,target=/root/.npm \
    npm ci \
    && NODE_OPTIONS="--max-old-space-size=4096" npm run build \
    && cp -r build /app/src/backend/langflow/frontend \
    && rm -rf /tmp/src/frontend

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv sync --frozen --no-editable --extra nv-ingest --extra postgresql

################################
# RUNTIME
# Setup user, utilities and copy the virtual environment only
################################
FROM python:3.12.3-slim AS runtime

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y \
        curl \
        git \
        # Add PostgreSQL client libraries
        libpq5 \
        gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && useradd user -u 1000 -g 0 --no-create-home --home-dir /app/data \
    && mkdir /data && chown -R 1000:0 /data

COPY --from=builder --chown=1000 /app/.venv /app/.venv

# curl is required for langflow health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

LABEL org.opencontainers.image.title=langflow
LABEL org.opencontainers.image.authors=['Langflow']
LABEL org.opencontainers.image.licenses=MIT
LABEL org.opencontainers.image.url=https://github.com/langflow-ai/langflow
LABEL org.opencontainers.image.source=https://github.com/langflow-ai/langflow

WORKDIR /app

ENV LANGFLOW_HOST=0.0.0.0
ENV LANGFLOW_PORT=7860
ENV LANGFLOW_EVENT_DELIVERY=polling

USER 1000
CMD ["python", "-m", "langflow", "run", "--host", "0.0.0.0", "--backend-only"]
