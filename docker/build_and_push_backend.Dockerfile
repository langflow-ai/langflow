# syntax=docker/dockerfile:1
# Keep this syntax directive! It's used to enable Docker BuildKit
#
# Backend-only Langflow image
# - No frontend code or assets
# - No Playwright

################################
# BUILDER
################################
FROM ghcr.io/astral-sh/uv:latest AS uv_installer
FROM registry.access.redhat.com/ubi10/python-314-minimal AS builder
USER root
COPY --from=uv_installer /uv /usr/local/bin/uv
COPY --from=uv_installer /uvx /usr/local/bin/uvx

WORKDIR /app

# Required for apify-client
ENV RUSTFLAGS='--cfg reqwest_unstable'

# Install build dependencies
RUN microdnf install -y tar xz \
        gcc gcc-c++ make python3.14-devel \
        gcc \
        git \
        curl \
    && microdnf clean all

# Copy only backend source (excludes frontend)
COPY ./src/backend ./src/backend
COPY ./src/lfx ./src/lfx
COPY ./src/sdk ./src/sdk

# Create venv and install langflow-base with dependencies
# Using uv pip instead of uv sync to avoid workspace complexities
RUN uv venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV BASH_ENV="" \
    ENV="" \
    PROMPT_COMMAND=""
ENV VIRTUAL_ENV="/app/.venv"

# Install langflow-base with all extras except dev (which includes Playwright).
# This image ships the langflow-base core only.  Extension bundles
# (lfx-duckduckgo, lfx-arxiv, lfx-ibm, lfx-docling, lfx-oracle, lfx-firecrawl) are intentionally NOT
# installed here -- they belong to the full ``langflow`` distribution, not
# the lean core.  Use the ``langflow`` image, or ``pip install`` the bundle
# alongside this image, to add those components.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install \
        ./src/sdk \
        ./src/lfx \
        "./src/backend/base[complete,postgresql]"

################################
# RUNTIME
################################
FROM registry.access.redhat.com/ubi10/python-314-minimal AS runtime
USER root
# Install minimal runtime dependencies
RUN microdnf update -y \
    && microdnf install -y tar xz \
        curl \
        git \
        libpq \
        gnupg \
        xz tar \
    && microdnf clean all
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
COPY --from=builder /usr/local/bin/uvx /usr/local/bin/uvx
# Install Node.js (required for npx-based MCP stdio servers)
RUN ARCH=$(uname -m) \
    && if [ "$ARCH" = "x86_64" ]; then NODE_ARCH="x64"; \
       elif [ "$ARCH" = "aarch64" ]; then NODE_ARCH="arm64"; \
       else NODE_ARCH="$ARCH"; fi \
    && NODE_VERSION=$(curl -fsSL https://nodejs.org/dist/latest-v22.x/ \
                    | sed -nE "s/.*node-v([0-9]+\.[0-9]+\.[0-9]+)-linux-${NODE_ARCH}\.tar\.xz.*/\1/p" \
                    | head -1) \
    && if [ -z "$NODE_VERSION" ]; then echo "ERROR: Could not determine Node.js version" && exit 1; fi \
    && curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${NODE_ARCH}.tar.xz" \
    | tar -xJ -C /usr/local --strip-components=1

# Create non-root user
RUN useradd --uid 1000 --gid 0 --no-create-home --home-dir /app/data user

# Copy only the virtual environment
COPY --from=builder --chown=1000:0 /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV BASH_ENV="" \
    ENV="" \
    PROMPT_COMMAND=""

# Create home directory and ensure proper ownership
# The user needs write access to /app/data (home) and /app (workdir).
# Also pre-create /app/langflow (LANGFLOW_CONFIG_DIR used by the docker_example
# compose file) with the non-root user as owner, so a fresh named volume mounted
# at /app/langflow inherits the correct ownership/permissions and the in-container
# uid=1000 user can write secret_key, profile_pictures, etc. Without this, the
# volume would be initialized as root:root and Langflow would crash with
# PermissionError on /app/langflow/secret_key (issue #10437).
# Note: .venv is already owned by 1000:0 via COPY --chown above, so no recursive chown needed
RUN mkdir -p /app/data /app/langflow \
    && chown -R 1000:0 /app/data /app/langflow \
    && chmod -R g+rwX /app/langflow \
    && chown 1000:0 /app

LABEL org.opencontainers.image.title=langflow-backend
LABEL org.opencontainers.image.authors=['Langflow']
LABEL org.opencontainers.image.licenses=MIT
LABEL org.opencontainers.image.url=https://github.com/langflow-ai/langflow
LABEL org.opencontainers.image.source=https://github.com/langflow-ai/langflow

USER user
WORKDIR /app

ENV LANGFLOW_HOST=0.0.0.0
ENV LANGFLOW_PORT=7860
ENV LANGFLOW_AUTO_LOGIN=false

CMD ["python", "-m", "langflow", "run", "--backend-only"]
