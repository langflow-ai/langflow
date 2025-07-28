# syntax=docker/dockerfile:1
# Keep this syntax directive! It's used to enable Docker BuildKit

################################
# BUILDER
# Used to build LFX and create our virtual environment
################################

# Use a Python image with uv pre-installed
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# OS deps (trimmed)
RUN apt-get update && apt-get install --no-install-recommends -y build-essential git \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

# --- Copy only files that affect dependency resolution (best cache) ---
# Workspace root metadata + lockfile
COPY pyproject.toml uv.lock ./

# Member's pyproject so uv knows about 'lfx' (no source yet, better cache)
COPY src/lfx/pyproject.toml /app/src/lfx/pyproject.toml
COPY src/lfx/README.md /app/src/lfx/README.md

# Create the venv and install *only* what lfx needs (no dev)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package lfx

# --- Now copy the source (doesn't bust the deps layer) ---
COPY src/lfx/src /app/src/lfx/src

# Install the LFX package into the virtual environment (non-editable)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package lfx

################################
# RUNTIME
# Setup user, utilities and copy the virtual environment only
################################
FROM python:3.12.3-slim AS runtime

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y \
    git \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && useradd lfx -u 1000 -g 0 --no-create-home --home-dir /app/data

# Copy the virtual environment from the builder stage
COPY --from=builder --chown=1000 /app/.venv /app/.venv

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

LABEL org.opencontainers.image.title=lfx
LABEL org.opencontainers.image.authors=['Langflow']
LABEL org.opencontainers.image.licenses=MIT
LABEL org.opencontainers.image.url=https://github.com/langflow-ai/langflow
LABEL org.opencontainers.image.source=https://github.com/langflow-ai/langflow
LABEL org.opencontainers.image.description="LFX - Langflow Extension CLI Tool"

USER lfx
WORKDIR /app/data

# Default command shows LFX help
CMD ["lfx", "--help"]