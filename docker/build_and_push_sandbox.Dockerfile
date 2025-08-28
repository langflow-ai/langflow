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
    # sandbox dependencies
    libpq-dev \
    python3-dev \
    pkg-config \
    libnl-route-3-dev \
    libnl-3-dev \
    libprotobuf-dev \
    protobuf-compiler \
    bison \
    flex \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=README.md,target=README.md \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=src/backend/base/README.md,target=src/backend/base/README.md \
    --mount=type=bind,source=src/backend/base/uv.lock,target=src/backend/base/uv.lock \
    --mount=type=bind,source=src/backend/base/pyproject.toml,target=src/backend/base/pyproject.toml \
    uv sync --frozen --no-install-project --no-editable --extra postgresql

COPY ./src /app/src

COPY src/frontend /tmp/src/frontend
WORKDIR /tmp/src/frontend
# Set Node.js memory limit for build
ENV NODE_OPTIONS="--max-old-space-size=4096"
RUN --mount=type=cache,target=/root/.npm \
    npm ci \
    && npm run build \
    && cp -r build /app/src/backend/langflow/frontend \
    && rm -rf /tmp/src/frontend

WORKDIR /app
COPY ./pyproject.toml /app/pyproject.toml
COPY ./uv.lock /app/uv.lock
COPY ./README.md /app/README.md

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable --extra postgresql

# Build and install nsjail from source
RUN set -e \
    && git clone https://github.com/google/nsjail.git /tmp/nsjail \
    && cd /tmp/nsjail \
    && echo "Building nsjail..." \
    && make -j$(nproc) \
    && echo "Installing nsjail..." \
    && cp nsjail /app/nsjail \
    && chmod +x /app/nsjail \
    && echo "Testing nsjail installation..." \
    && /app/nsjail --help > /dev/null \
    && echo "nsjail built successfully" \
    && cd / \
    && rm -rf /tmp/nsjail

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
    libpq5 \
    gnupg \
    # sandbox runtime dependencies
    postgresql-client \
    sudo \
    libprotobuf32 \
    libnl-3-200 \
    libnl-route-3-200 \
    libnl-genl-3-200 \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && useradd user -u 1000 -g 0 --no-create-home --home-dir /app/data

COPY --from=builder --chown=1000 /app/.venv /app/.venv
COPY --from=builder --chown=root /app/nsjail /usr/local/bin/nsjail

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

# Create sandbox directories and set permissions
RUN mkdir -p /tmp/langflow-sandbox \
    && mkdir -p /var/log/langflow-sandbox \
    && chown -R nobody:nogroup /tmp/langflow-sandbox \
    && chmod 755 /tmp/langflow-sandbox

# Configure sudo for nsjail access
RUN echo "user ALL=(ALL) NOPASSWD: /usr/local/bin/nsjail" >> /etc/sudoers

# Set sandbox environment variables
ENV LANGFLOW_SANDBOX_ENABLED=true

LABEL org.opencontainers.image.title=langflow-sandbox
LABEL org.opencontainers.image.authors=['Langflow']
LABEL org.opencontainers.image.licenses=MIT
LABEL org.opencontainers.image.url=https://github.com/langflow-ai/langflow
LABEL org.opencontainers.image.source=https://github.com/langflow-ai/langflow

USER user
WORKDIR /app

ENV LANGFLOW_HOST=0.0.0.0
ENV LANGFLOW_PORT=7860

CMD ["langflow", "run", "--host", "0.0.0.0", "--port", "7860"]