# syntax=docker/dockerfile:1
# Keep this syntax directive! It's used to enable Docker BuildKit

# Toggle Docling and heavyweight OCR deps inside the virtualenv.
# Default keeps the image slim by stripping them after install.
ARG INCLUDE_DOCLING=false

################################
# BUILDER
# Used to build LFX and create our virtual environment
################################

# Use an Alpine-based Python image with uv pre-installed
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# ARG TARGETARCH
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libaio-dev \
        linux-headers-generic \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# --- Copy only files that affect dependency resolution (best cache) ---
# Workspace root metadata + lockfile
COPY pyproject.toml uv.lock ./

# Member's pyproject so uv knows about 'lfx' (no source yet, better cache)
COPY src/lfx/pyproject.toml /app/src/lfx/pyproject.toml
COPY src/lfx/README.md /app/src/lfx/README.md

# Create the venv and install *only* what lfx needs (no dev)
# We expect some packages to be built from source, so we mount the cache
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package lfx

# --- Now copy the source (doesn't bust the deps layer) ---
COPY src/lfx/src /app/src/lfx/src

# Install the LFX package into the virtual environment (non-editable)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package lfx

# Remove Docling + OCR extras when not requested to keep the image leaner
RUN if [ "$INCLUDE_DOCLING" = "false" ]; then \
        .venv/bin/python -m pip uninstall -y \
            docling \
            docling-core \
            docling-parse \
            docling-ibm-models \
            langchain-docling \
            rapidocr-onnxruntime \
            tesserocr \
            easyocr \
            ocrmac \
            mlx \
            mlx-vlm || true; \
    fi

################################
# RUNTIME
# Setup user, utilities and copy the virtual environment only
################################
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS runtime
ARG INCLUDE_DOCLING

# Create a non-root user
# -D: Don't assign a password
# -u: Set user ID
# -G: Add to group (root)
# -h: Set home directory
# -s: Set shell
RUN useradd --uid 1000 --gid 0 --home-dir /app/data --shell /sbin/nologin lfx

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