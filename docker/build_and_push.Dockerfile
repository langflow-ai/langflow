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

# Set RUSTFLAGS for reqwest unstable features needed by apify-client v2.0.0
ENV RUSTFLAGS='--cfg reqwest_unstable'

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
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
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
    uv sync --frozen --no-install-project --no-editable --no-dev --extra postgresql

COPY ./src /app/src

COPY src/frontend /tmp/src/frontend
WORKDIR /tmp/src/frontend
RUN --mount=type=cache,target=/root/.npm \
    npm ci \
    && ESBUILD_BINARY_PATH="" NODE_OPTIONS="--max-old-space-size=12288" JOBS=1 npm run build \
    && cp -r build /app/src/backend/langflow/frontend \
    && rm -rf /tmp/src/frontend

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv sync --frozen --no-editable --no-dev --extra postgresql

# Clean up build artifacts and unnecessary files before copying to runtime
# This is critical: cleanup must happen BEFORE COPY to avoid creating layers with whiteout markers
RUN cd /app/.venv && \
    # Remove test directories and files
    find . -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find . -type d -name "test" -exec rm -rf {} + 2>/dev/null || true && \
    find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true && \
    # Remove documentation files
    find . -type f \( -name "*.md" -o -name "*.rst" \) -delete 2>/dev/null || true && \
    find . -path '*/.dist-info' -prune -o -type f \( -name "*.txt" -o -name "*.TXT" \) -print -delete 2>/dev/null || true && \
    # Remove C/C++ source and headers (not needed after compilation)
    find . -type f \( -name "*.c" -o -name "*.h" -o -name "*.cpp" -o -name "*.hpp" -o -name "*.cc" \) -delete 2>/dev/null || true && \
    # Remove Cython source files
    find . -type f \( -name "*.pyx" -o -name "*.pxd" -o -name "*.pxi" \) -delete 2>/dev/null || true && \
    # Strip debug symbols from shared libraries
    find . -name "*.so" -exec strip --strip-unneeded {} \; 2>/dev/null || true && \
    # Remove man pages and docs
    rm -rf share/man man 2>/dev/null || true

################################
# RUNTIME
# Setup user, utilities and copy the virtual environment only
################################
FROM python:3.12.12-slim-trixie AS runtime

# Install only essential runtime dependencies:
# - libpq5: PostgreSQL client library (for database connections)
# - curl: Required for Node.js installation
# - Chromium dependencies for Playwright (minimal set for headless operation)
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y \
    libpq5 \
    curl \
    xz-utils \
    # Chromium dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0t64 \
    libatk-bridge2.0-0t64 \
    libcups2t64 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2t64 \
    libatspi2.0-0t64 \
    libxshmfence1 \
    # Fonts (using Debian Trixie package names)
    fonts-liberation \
    fonts-noto-color-emoji \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (needed for MCP servers that use npx)
# Use minimal installation: download pre-built binaries directly
RUN ARCH=$(dpkg --print-architecture) \
    && if [ "$ARCH" = "amd64" ]; then NODE_ARCH="x64"; \
       elif [ "$ARCH" = "arm64" ]; then NODE_ARCH="arm64"; \
       else NODE_ARCH="$ARCH"; fi \
    && NODE_VERSION=$(curl -fsSL https://nodejs.org/dist/latest-v22.x/ \
                    | grep -oP "node-v\K[0-9]+\.[0-9]+\.[0-9]+(?=-linux-${NODE_ARCH}\.tar\.xz)" \
                    | head -1) \
    && curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${NODE_ARCH}.tar.xz" \
    | tar -xJ -C /usr/local --strip-components=1 \
    && npm cache clean --force \
    && rm -rf /usr/local/lib/node_modules/npm/docs \
    && rm -rf /usr/local/lib/node_modules/npm/man

RUN useradd user -u 1000 -g 0 --no-create-home --home-dir /app/data

COPY --from=builder --chown=1000 /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Install only Chromium browser for Playwright (not all browsers)
# This saves ~1.5GB compared to installing all browsers
# Install without --with-deps since we manually installed dependencies above
RUN /app/.venv/bin/playwright install chromium

LABEL org.opencontainers.image.title=langflow
LABEL org.opencontainers.image.authors=['Langflow']
LABEL org.opencontainers.image.licenses=MIT
LABEL org.opencontainers.image.url=https://github.com/langflow-ai/langflow
LABEL org.opencontainers.image.source=https://github.com/langflow-ai/langflow

USER user
WORKDIR /app

ENV LANGFLOW_HOST=0.0.0.0
ENV LANGFLOW_PORT=7860

CMD ["langflow", "run"]

