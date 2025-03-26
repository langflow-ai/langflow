# syntax=docker/dockerfile:1
# Keep this syntax directive! It's used to enable Docker BuildKit

################################
# BUILDER-BASE
# Used to build deps + create our virtual environment
################################
ARG PYTHON_VERSION=3.12.9
ARG PYTHON_IMAGE=python:${PYTHON_VERSION}-slim-bookworm
ARG BUILDER_BASE_IMAGE=ghcr.io/astral-sh/uv:python3.12-bookworm-slim

FROM --platform=$BUILDPLATFORM ${BUILDER_BASE_IMAGE} AS builder

# Install the project into `/app`
WORKDIR /app

# Set the environment variables
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install --no-install-recommends --no-install-suggests -y \
    build-essential=12.9 \
    ca-certificates=20230311 \
    gcc=4:12.2.0-3 \
    git=1:2.39.5-0+deb12u2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* /var/tmp/*

# Copy only the files needed for dependency installation
COPY ./uv.lock ./uv.lock
COPY ./README.md ./README.md
COPY ./pyproject.toml ./pyproject.toml
COPY ./src/backend/base/README.md ./src/backend/base/README.md
COPY ./src/backend/base/uv.lock ./src/backend/base/uv.lock
COPY ./src/backend/base/pyproject.toml ./src/backend/base/pyproject.toml

# Install the project dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    cd src/backend/base && uv sync --frozen --no-install-project --no-dev --no-editable --extra postgresql

# Copy src code into the image
COPY ./src /app/src

# Install the project's dependencies in non-editable mode
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --extra postgresql

################################
# RUNTIME
################################
FROM ${PYTHON_IMAGE} AS runtime

# Set the working directory
WORKDIR /app

# Build arguments
ARG DEFAULT_BACKEND_PORT=7860
ARG DEFAULT_BACKEND_HOST=0.0.0.0
### USING HIGHER UID AND GID TO AVOID CONFLICTS WITH HOST USERS (10k not 1k)
ARG UID=10000
ARG GID=10000
ARG APP_USER=langflow
ARG APP_GROUP=langflow

# Set the environment variables
ENV LANGFLOW_HOST=${DEFAULT_BACKEND_HOST} \
    LANGFLOW_PORT=${DEFAULT_BACKEND_PORT} \
    PATH="/app/.venv/bin:$PATH" \
    # Don't create .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    # Disable Python's buffering of stdout and stderr
    PYTHONUNBUFFERED=1 \
    # Set Python to run in production mode
    PYTHON_ENV=production \
    # Set timezone
    TZ=UTC \
    LANGFLOW_LOG_ENV="container_json" \
    XDG_CACHE_HOME="/app/cache" \
    PLATFORMDIRS_CACHE_DIR="/app/cache/langflow" \
    # Set temporary directory
    TMPDIR="/app/tmp" \
    TEMP="/app/tmp" \
    TMP="/app/tmp" \
    # Set Composio temporary directory location to prevent
    # lock file creation in read-only filesystem
    COMPOSIO_TMP_DIR="/app/tmp"

# Copy the entrypoint script
COPY ./docker/backend_only_entrypoint.sh /entrypoint.sh

# Install system dependencies
# updated zlib1g to fix CVE-2023-45853
RUN echo 'deb http://deb.debian.org/debian trixie main' > /etc/apt/sources.list.d/trixie.list \
    && echo 'APT::Default-Release "bookworm";' > /etc/apt/apt.conf.d/99defaultrelease \
    && apt-get update \
    && apt-get upgrade -y \
    && apt-get install --no-install-recommends --no-install-suggests -y \
        # Process supervisor for proper signal handling
        tini=0.19.0-1 \
        git=1:2.39.5-0+deb12u2 -y \
        # PostgreSQL client libraries
        libpq5=15.12-0+deb12u2 \
        # Required for healthcheck
        curl=7.88.1-10+deb12u12 \
    # Install zlib1g from trixie for CVE-2023-45853
    && apt-get -t trixie install --no-install-recommends --no-install-suggests -y zlib1g=1:1.3.dfsg+really1.3.1-1+b1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* /var/tmp/* \
    && rm -f /etc/apt/sources.list.d/trixie.list \
    # Create non-root user for running the application
    && groupadd --gid ${GID} ${APP_GROUP} \
    && useradd ${APP_USER} --uid ${UID} --gid ${GID} --no-create-home --home-dir /app/data \
    # Create necessary directories
    && mkdir -p \
        /app/data \
        /app/cache/langflow \
        /app/flows \
        /app/db \
        /app/tmp \
    # Set correct permissions
    && chown -R ${UID}:${GID} \
        /app/data \
        /app/cache \
        /app/flows \
        /app/db \
        /app/tmp \
    && chmod +x /entrypoint.sh

# Copy the virtual environment from the builder stage
COPY --from=builder --chown=${UID}:${GID} /app/.venv /app/.venv

# Health check: Dynamic port detection with content validation
# Verifies not just HTTP 200 response but actual content indicating healthy service
HEALTHCHECK --interval=30s \
    --timeout=30s \
    --start-period=20s \
    --retries=3 \
    CMD curl -f -s http://localhost:${LANGFLOW_PORT}/health | grep -q '"status":"ok"' || exit 1

# Add metadata
LABEL org.opencontainers.image.title=="Langflow Backend Service" \
    org.opencontainers.image.description="Production-ready backend service for Langflow" \
    org.opencontainers.image.authors=['Langflow Team'] \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.url="https://github.com/langflow-ai/langflow" \
    org.opencontainers.image.source="https://github.com/langflow-ai/langflow"

# Define persistent volumes for data that should survive container restarts
# Separating different types of data for better management
VOLUME [ "/app/data", "/app/flows", "/app/db", "/app/cache", "/app/tmp" ]

# Switch to non-root user
USER ${APP_USER}

# Expose API port
EXPOSE ${DEFAULT_BACKEND_PORT}

# Use tini as an init system to properly handle signals and prevent zombie processes
ENTRYPOINT [ "tini", "--","/entrypoint.sh" ]

# Default command (intentionally empty to allow override at runtime)
# This will be executed by the entrypoint script
CMD []
