# syntax=docker/dockerfile:1
# Keep this syntax directive! It's used to enable Docker BuildKit

################################
# BUILDER
# Used to build LFX and create our virtual environment
################################

# Use a glibc-based image: onnxruntime publishes manylinux wheels but no
# musllinux wheel, so the former Alpine builder cannot install the locked LFX
# dependency set.
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS builder

ARG DEBIAN_MIRROR=mirrors.tuna.tsinghua.edu.cn
ARG UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple

ENV UV_DEFAULT_INDEX=${UV_DEFAULT_INDEX}

# Some optional LFX dependencies may need a compiler during installation.
RUN sed -i "s|deb.debian.org|${DEBIAN_MIRROR}|g; s|security.debian.org|${DEBIAN_MIRROR}|g" \
        /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install --no-install-recommends -y build-essential \
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

# Member pyproject files so uv knows about workspace packages (no source yet, better cache)
COPY src/lfx/pyproject.toml /app/src/lfx/pyproject.toml
COPY src/lfx/README.md /app/src/lfx/README.md
COPY src/sdk/pyproject.toml /app/src/sdk/pyproject.toml
COPY src/sdk/README.md /app/src/sdk/README.md

# Create the venv and install *only* what lfx needs (no dev)
# We expect some packages to be built from source, so we mount the cache
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package lfx

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
FROM python:3.14-slim-trixie AS runtime

# Create a non-root user and a writable working directory.
RUN useradd --uid 1000 --gid 0 --no-create-home --home-dir /app/data --shell /usr/sbin/nologin lfx \
    && mkdir -p /app/data \
    && chown -R 1000:0 /app \
    && chmod -R g+rwX /app

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

################################
# RUNNER
# One-shot image for executing a mounted Langflow flow JSON file.
# Build this target with: docker build --target runner ...
################################
FROM runtime AS runner

# Arguments supplied to `docker run` are appended to this entrypoint, so:
# docker run ... lfx-runner /flows/my-flow.json "hello"
# executes: lfx run /flows/my-flow.json "hello"
ENTRYPOINT ["lfx", "run"]
CMD ["/flows/flow.json"]

################################
# DEFAULT
# Keep the published/default image as the general-purpose LFX CLI image.
################################
FROM runtime

# Default command shows LFX help
CMD ["lfx", "--help"]
