# syntax=docker/dockerfile:1
# Keep this syntax directive! It's used to enable Docker BuildKit

################################
# BUILDER-BASE
# Used to build deps + create our virtual environment
################################

# 1. use python:3.12.3-slim as the base image until https://github.com/pydantic/pydantic-core/issues/1292 gets resolved
# 2. do not add --platform=$BUILDPLATFORM because the pydantic binaries must be resolved for the final architecture
# Use a Python image with uv pre-installed

ARG PYTHON_IMAGE=python:3.12.9-slim-bookworm
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
SHELL [ "/bin/bash", "-c" ]
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y \
    build-essential=12.9 \
    ca-certificates=20230311 \
    gcc=4:12.2.0-3 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install the project dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=README.md,target=README.md \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=src/backend/base/README.md,target=src/backend/base/README.md \
    --mount=type=bind,source=src/backend/base/uv.lock,target=src/backend/base/uv.lock \
    --mount=type=bind,source=src/backend/base/pyproject.toml,target=src/backend/base/pyproject.toml \
    uv sync --frozen --no-install-project --no-editable --extra postgresql

# Copy only the backend src code into the image
COPY ./src /app/src
COPY ./pyproject.toml /app/pyproject.toml
COPY ./uv.lock /app/uv.lock
COPY ./README.md /app/README.md

# Install the project's dependencies in non-editable mode
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable --extra postgresql

################################
# RUNTIME
# Setup user, utilities and copy the virtual environment only
################################
FROM ${PYTHON_IMAGE} AS runtime

# Set the working directory
WORKDIR /app

# Define the default environment variables
ARG DEFAULT_BACKEND_PORT=7860
ARG DEFAULT_BACKEND_HOST=0.0.0.0
### USING HIGHER UID AND GID TO AVOID CONFLICTS WITH HOST USERS (10k not 1k)
ARG UID=10000
ARG GID=10000

# Set the environment variables
ENV LANGFLOW_HOST=${DEFAULT_BACKEND_HOST} \
    LANGFLOW_PORT=${DEFAULT_BACKEND_PORT} \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANGFLOW_LOG_ENV="container_json"

# Copy the entrypoint script
COPY ./docker/backend_only_entrypoint.sh /entrypoint.sh

# Install system dependencies
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install tini=0.19.0-1 -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --gid ${GID} langflow \
    && useradd langflow --uid ${UID} --gid ${GID} --no-create-home --home-dir /app/data \
    && mkdir -p /app/data \
    && chown -R ${UID}:${GID} /app/data \
    && chmod +x /entrypoint.sh

# Copy the virtual environment from the builder stage
COPY --from=builder --chown=${UID}:${GID} /app/.venv /app/.venv

# Add metadata
LABEL org.opencontainers.image.title=langflow
LABEL org.opencontainers.image.authors=['Langflow']
LABEL org.opencontainers.image.licenses=MIT
LABEL org.opencontainers.image.url=https://github.com/langflow-ai/langflow
LABEL org.opencontainers.image.source=https://github.com/langflow-ai/langflow

USER langflow

EXPOSE ${DEFAULT_BACKEND_PORT}

# Use tini as the entrypoint to ensure signals are passed correctly
ENTRYPOINT [ "tini", "--","/entrypoint.sh" ]

# Base command to run the langflow backend (overridden kubernetes)
CMD []
