# syntax=docker/dockerfile:1
# Keep this syntax directive! It's used to enable Docker BuildKit.

################################
# BUILDER
# Build the frontend and install only the langflow-core dependency chain.
################################

FROM ghcr.io/astral-sh/uv:latest AS uv_installer
FROM registry.access.redhat.com/ubi10/python-314-minimal AS builder

USER root
ARG CORE_VERSION=""
COPY --from=uv_installer /uv /usr/local/bin/uv
COPY --from=uv_installer /uvx /usr/local/bin/uvx

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV RUSTFLAGS='--cfg reqwest_unstable'

RUN microdnf install -y tar xz \
    gcc gcc-c++ make python3.14-devel \
    git npm \
    && microdnf clean all

# Intentionally do not copy the root workspace manifest, lockfile, or
# src/bundles. Build the four local distributions independently so the image
# cannot acquire extension packages through the root ``langflow`` project.
COPY ./src/sdk /app/src/sdk
COPY ./src/lfx /app/src/lfx
COPY ./src/backend/base /app/src/backend/base
COPY ./src/langflow-core /app/src/langflow-core

# Release workflows can resolve an RC version without mutating the source tag.
# Keep the distribution metadata inside the image aligned with its image tag.
RUN if [ -n "$CORE_VERSION" ]; then \
      sed -i "s/^version = .*/version = \"${CORE_VERSION}\"/" /app/src/langflow-core/pyproject.toml; \
    fi

COPY ./src/frontend /tmp/src/frontend
WORKDIR /tmp/src/frontend
RUN --mount=type=cache,target=/root/.npm \
    PUPPETEER_SKIP_DOWNLOAD=true npm install \
    && ESBUILD_BINARY_PATH="" NODE_OPTIONS="--max-old-space-size=4096" JOBS=1 npm run build \
    && cp -r build /app/src/backend/base/langflow/frontend \
    && rm -rf /tmp/src/frontend

# Build local wheels first, then seed them without dependencies. Installing the
# core wheel a second time with its PostgreSQL extra resolves third-party
# dependencies while preserving the exact SDK/LFX/base/core wheels from this
# checkout. No bundle source or bundle wheel is available to the resolver.
WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    mkdir -p /app/dist \
    && cd /app/src/sdk \
    && uv build --wheel --out-dir /app/dist \
    && cd /app/src/lfx \
    && uv build --wheel --out-dir /app/dist \
    && cd /app/src/backend/base \
    && uv build --wheel --out-dir /app/dist \
    && cd /app/src/langflow-core \
    && uv build --wheel --out-dir /app/dist \
    && uv venv /app/.venv \
    && uv pip install --python /app/.venv/bin/python --no-deps \
        /app/dist/langflow_sdk-*.whl \
        /app/dist/lfx-*.whl \
        /app/dist/langflow_base-*.whl \
        /app/dist/langflow_core-*.whl \
    && CORE_WHEEL=$(find /app/dist -maxdepth 1 -name 'langflow_core-*.whl' -print -quit) \
    && uv pip install --python /app/.venv/bin/python --prerelease=allow "${CORE_WHEEL}[postgresql]" \
    && /app/.venv/bin/python -c 'import importlib.metadata as m; forbidden = sorted(d.metadata["Name"] for d in m.distributions() if d.metadata["Name"].lower().startswith("lfx-")); assert not forbidden, f"extension distributions installed: {forbidden}"'

################################
# RUNTIME
# Copy only the resolved virtual environment and runtime utilities.
################################

FROM registry.access.redhat.com/ubi10/python-314-minimal AS runtime

USER root
RUN microdnf update -y \
    && microdnf install -y curl git libpq gnupg xz tar shadow-utils \
    && microdnf clean all
RUN python3.14 -m pip install --upgrade pip

COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
COPY --from=builder /usr/local/bin/uvx /usr/local/bin/uvx

RUN ARCH=$(uname -m) \
    && if [ "$ARCH" = "x86_64" ]; then NODE_ARCH="x64"; \
       elif [ "$ARCH" = "aarch64" ]; then NODE_ARCH="arm64"; \
       else NODE_ARCH="$ARCH"; fi \
    && NODE_VERSION=$(curl -fsSL https://nodejs.org/dist/latest-v22.x/ \
                    | sed -nE "s/.*node-v([0-9]+\.[0-9]+\.[0-9]+)-linux-${NODE_ARCH}\.tar\.xz.*/\1/p" \
                    | head -1) \
    && if [ -z "$NODE_VERSION" ]; then echo "ERROR: Could not determine Node.js version" && exit 1; fi \
    && curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${NODE_ARCH}.tar.xz" \
    | tar -xJ -C /usr/local --strip-components=1 \
    && npm install -g npm@latest

RUN useradd user -u 1000 -g 0 --no-create-home --home-dir /app/data

COPY --from=builder --chown=1000 /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV BASH_ENV="" \
    ENV="" \
    PROMPT_COMMAND=""

RUN mkdir -p /app/langflow \
    && chown -R 1000:0 /app/langflow \
    && chmod -R g+rwX /app/langflow

ENV NPM_CONFIG_CACHE=/app/.npm
RUN mkdir -p /app/.npm /opt/app-root/src/.npm \
    && chown -R 1000:0 /app/.npm /opt/app-root/src/.npm \
    && chmod -R g+rwX /app/.npm /opt/app-root/src/.npm

LABEL org.opencontainers.image.title=langflow-core
LABEL org.opencontainers.image.authors=['Langflow']
LABEL org.opencontainers.image.licenses=MIT
LABEL org.opencontainers.image.url=https://github.com/langflow-ai/langflow
LABEL org.opencontainers.image.source=https://github.com/langflow-ai/langflow

USER user
WORKDIR /app

ENV LANGFLOW_HOST=0.0.0.0
ENV LANGFLOW_PORT=7860

# Harden the public image defaults.
ENV LANGFLOW_AUTO_LOGIN=false
ENV LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false
ENV LANGFLOW_BLOCK_CODE_INTERPRETER_COMPONENTS=true
ENV LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS=true
ENV LANGFLOW_MCP_SERVER_DOCKER_HARDENING=true
ENV LANGFLOW_MCP_SERVER_INTERPRETER_HARDENING=true
ENV LANGFLOW_MCP_SERVER_ALLOWED_PACKAGES=mcp-proxy,lfx

CMD ["langflow", "run"]
