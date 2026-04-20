# syntax=docker/dockerfile:1
# Keep this syntax directive! It's used to enable Docker BuildKit

################################
# BUILDER
# Used to build LFX and create our virtual environment
################################

# Use a Debian-slim Python image with uv pre-installed (glibc for manylinux wheels)
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# --- Copy only files that affect dependency resolution (best cache) ---
# Workspace root metadata + lockfile
COPY pyproject.toml uv.lock ./

# Member pyproject files so uv knows about workspace packages (no source yet, better cache)
COPY src/lfx/pyproject.toml /app/src/lfx/pyproject.toml
COPY src/lfx/README.md /app/src/lfx/README.md
COPY src/sdk/pyproject.toml /app/src/sdk/pyproject.toml
COPY src/sdk/README.md /app/src/sdk/README.md

# Create the venv and install *only* what lfx needs (no dev)
# --no-install-project keeps the deps layer cache-stable when source changes
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --package lfx

# --- Now copy the source (doesn't bust the deps layer) ---
COPY src/lfx/src /app/src/lfx/src
COPY src/sdk/src /app/src/sdk/src

# Install the LFX package into the virtual environment (non-editable)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package lfx

################################
# RUNTIME
# Setup user, utilities and copy the virtual environment only
################################
FROM python:3.13-slim-bookworm AS runtime

# Create a non-root user (Debian)
#   -u 1000               set UID
#   -g 0                  primary group root (matches prior Alpine behavior)
#   -d /app/data          home directory
#   -s /usr/sbin/nologin  no shell
#   -M                    don't auto-create home (we create it below with correct perms)
RUN useradd -u 1000 -g 0 -d /app/data -s /usr/sbin/nologin -M lfx \
    && mkdir -p /app/data \
    && chown -R 1000:0 /app/data

# Copy the virtual environment from the builder stage
COPY --from=builder --chown=1000 /app/.venv /app/.venv

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

LABEL org.opencontainers.image.title=lfx
LABEL org.opencontainers.image.authors=['Langflow']
LABEL org.opencontainers.image.licenses=MIT
LABEL org.opencontainers.image.url=https://github.com/langflow-ai/langflow
LABEL org.opencontainers.image.source=https://github.com/langflow-ai/langflow
LABEL org.opencontainers.image.description="LFX - Langflow Executor CLI Tool"

USER lfx
WORKDIR /app/data

# Default command shows LFX help
CMD ["lfx", "--help"]
