# syntax=docker/dockerfile:1
# Keep this syntax directive! It's used to enable Docker BuildKit.

# Both public images are built from this checkout. Keep toolchain versions here
# so the core and full targets cannot silently resolve different build tools.
ARG UV_VERSION=0.10.4
ARG PYTHON_IMAGE=registry.access.redhat.com/ubi10/python-314-minimal
ARG NODE_VERSION=22.14.0

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv-installer

################################
# BUILDER BASE
# Shared pinned toolchain for dependency and frontend builders.
################################
FROM ${PYTHON_IMAGE} AS builder-base

USER root
ARG NODE_VERSION

COPY --from=uv-installer /uv /usr/local/bin/uv
COPY --from=uv-installer /uvx /usr/local/bin/uvx

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    RUSTFLAGS='--cfg reqwest_unstable'

RUN microdnf install -y \
        curl \
        gcc \
        gcc-c++ \
        git \
        make \
        python3.14-devel \
        tar \
        xz \
    && ARCH=$(uname -m) \
    && if [ "$ARCH" = "x86_64" ]; then NODE_ARCH="x64"; \
       elif [ "$ARCH" = "aarch64" ]; then NODE_ARCH="arm64"; \
       else NODE_ARCH="$ARCH"; fi \
    && curl -fsSLo /tmp/node.tar.xz \
        "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${NODE_ARCH}.tar.xz" \
    && tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1 \
    && rm -f /tmp/node.tar.xz \
    && microdnf clean all

################################
# WORKSPACE METADATA
# Resolve locked third-party dependencies before source copies invalidate cache.
################################
FROM builder-base AS workspace-metadata

COPY ./uv.lock /app/uv.lock
COPY ./README.md /app/README.md
COPY ./pyproject.toml /app/pyproject.toml
COPY ./src/backend/base/README.md /app/src/backend/base/README.md
COPY ./src/backend/base/pyproject.toml /app/src/backend/base/pyproject.toml
COPY ./src/langflow-core/README.md /app/src/langflow-core/README.md
COPY ./src/langflow-core/pyproject.toml /app/src/langflow-core/pyproject.toml
COPY ./src/langflow-stepflow/README.md /app/src/langflow-stepflow/README.md
COPY ./src/langflow-stepflow/pyproject.toml /app/src/langflow-stepflow/pyproject.toml
COPY ./src/lfx/README.md /app/src/lfx/README.md
COPY ./src/lfx/pyproject.toml /app/src/lfx/pyproject.toml
COPY ./src/sdk/README.md /app/src/sdk/README.md
COPY ./src/sdk/pyproject.toml /app/src/sdk/pyproject.toml

# Every directory under src/bundles is a uv workspace member. Copy the tree
# once so adding a bundle does not also require another Dockerfile edit.
COPY ./src/bundles /app/src/bundles

FROM workspace-metadata AS core-dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --package langflow-core --extra postgresql \
        --no-default-groups --no-install-workspace

FROM workspace-metadata AS full-dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --extra postgresql --no-default-groups --no-install-workspace

################################
# FRONTEND BUILDER
# Build the shared web UI once for both Python distribution targets.
################################
FROM builder-base AS frontend-builder

COPY ./src/frontend /tmp/src/frontend
WORKDIR /tmp/src/frontend

# PUPPETEER_SKIP_DOWNLOAD: puppeteer (via accessibility-checker, test-only)
# must not download Chrome here; the production image never runs it.
RUN --mount=type=cache,target=/root/.npm \
    PUPPETEER_SKIP_DOWNLOAD=true npm ci \
    && ESBUILD_BINARY_PATH="" NODE_OPTIONS="--max-old-space-size=4096" JOBS=1 npm run build \
    && mkdir -p /tmp/frontend-build \
    && cp -a build/. /tmp/frontend-build/

################################
# PACKAGE BUILDERS
# Materialize isolated core and full virtual environments from this checkout.
################################
FROM core-dependencies AS core-builder

ARG CORE_VERSION=""
COPY ./src /app/src
COPY --from=frontend-builder /tmp/frontend-build/ /app/src/backend/base/langflow/frontend/

# Release workflows can resolve an RC version without mutating the source tag.
# The dependency lock was already resolved from the unmodified workspace.
RUN if [ -n "$CORE_VERSION" ]; then \
        sed -i "s/^version = .*/version = \"${CORE_VERSION}\"/" \
            /app/src/langflow-core/pyproject.toml; \
    fi \
    && uv sync --frozen --package langflow-core --extra postgresql \
        --no-default-groups --no-editable \
    && uv pip check --python /app/.venv/bin/python \
    && /app/.venv/bin/python -c 'import importlib.metadata as m; names = {d.metadata["Name"].lower() for d in m.distributions()}; required = {"langflow-core", "langflow-base", "lfx", "langflow-sdk"}; missing = sorted(required - names); forbidden = sorted(name for name in names if name.startswith("lfx-")); assert not missing, f"missing core distributions: {missing}"; assert not forbidden, f"extension distributions installed: {forbidden}"'

FROM full-dependencies AS full-builder

ARG MAIN_VERSION=""
ARG CORE_VERSION=""
COPY ./src /app/src
COPY --from=frontend-builder /tmp/frontend-build/ /app/src/backend/langflow/frontend/

RUN --mount=type=cache,target=/root/.cache/uv \
    if [ -n "$MAIN_VERSION" ]; then \
        sed -i "s/^version = .*/version = \"${MAIN_VERSION}\"/" \
            /app/pyproject.toml; \
    fi \
    && if [ -n "$CORE_VERSION" ]; then \
        sed -i "s/^version = .*/version = \"${CORE_VERSION}\"/" \
            /app/src/langflow-core/pyproject.toml; \
        core_major=${CORE_VERSION%%.*}; \
        core_remainder=${CORE_VERSION#*.}; \
        core_minor=${core_remainder%%.*}; \
        core_upper_bound="${core_major}.$((core_minor + 1)).dev0"; \
        sed -i -E \
            "s|\"langflow-core(\\[[^]]+\\])?[^\";]*\"|\"langflow-core\\1>=${CORE_VERSION},<${core_upper_bound}\"|g" \
            /app/pyproject.toml; \
    fi \
    && uv sync --frozen --extra postgresql --no-default-groups --no-editable \
    && uv pip check --python /app/.venv/bin/python \
    && /app/.venv/bin/python -c 'import importlib.metadata as m; names = {d.metadata["Name"].lower() for d in m.distributions()}; required = {"langflow", "langflow-core"}; missing = sorted(required - names); assert not missing, f"missing full distributions: {missing}"' \
    && if [ -n "$MAIN_VERSION" ]; then \
        MAIN_VERSION="$MAIN_VERSION" /app/.venv/bin/python -c 'import importlib.metadata as m, os; actual = m.version("langflow"); expected = os.environ["MAIN_VERSION"]; assert actual == expected, f"langflow version {actual} != {expected}"'; \
    fi \
    && if [ -n "$CORE_VERSION" ]; then \
        CORE_VERSION="$CORE_VERSION" /app/.venv/bin/python -c 'import importlib.metadata as m, os; actual = m.version("langflow-core"); expected = os.environ["CORE_VERSION"]; assert actual == expected, f"langflow-core version {actual} != {expected}"'; \
    fi

################################
# SHARED RUNTIME
# One user, utility, label, and runtime defaults contract for every public target.
################################
FROM ${PYTHON_IMAGE} AS runtime

USER root

RUN microdnf update -y \
    && microdnf install -y curl git gnupg libpq shadow-utils tar xz \
    && microdnf clean all

COPY --from=builder-base /usr/local/bin/uv /usr/local/bin/uv
COPY --from=builder-base /usr/local/bin/uvx /usr/local/bin/uvx
COPY --from=builder-base /usr/local/bin/node /usr/local/bin/node
COPY --from=builder-base /usr/local/lib/node_modules /usr/local/lib/node_modules

# COPY dereferences the npm/npx symlinks from the Node archive. Recreate them
# against the copied module tree so their relative imports resolve correctly.
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

RUN useradd user -u 1000 -g 0 --no-create-home --home-dir /app/data \
    && mkdir -p /app/langflow \
    && chown -R 1000:0 /app/langflow \
    && chmod -R g+rwX /app/langflow

# Give uid 1000 a writable npm cache. The image ships Node so users can spawn
# stdio MCP servers via npx, while the UBI HOME is not owned by that uid.
RUN mkdir -p /app/.npm /opt/app-root/src/.npm \
    && chown -R 1000:0 /app/.npm /opt/app-root/src/.npm \
    && chmod -R g+rwX /app/.npm /opt/app-root/src/.npm

LABEL org.opencontainers.image.authors=['Langflow'] \
      org.opencontainers.image.licenses=MIT \
      org.opencontainers.image.url=https://github.com/langflow-ai/langflow \
      org.opencontainers.image.source=https://github.com/langflow-ai/langflow

ENV PATH="/app/.venv/bin:$PATH" \
    BASH_ENV="" \
    ENV="" \
    PROMPT_COMMAND="" \
    NPM_CONFIG_CACHE=/app/.npm \
    LANGFLOW_HOST=0.0.0.0 \
    LANGFLOW_PORT=7860

# Keep auto-login disabled in every public target through the shared runtime stage.
ENV LANGFLOW_AUTO_LOGIN=false

USER user
WORKDIR /app

CMD ["langflow", "run"]

################################
# CORE IMAGE
# Service-complete Langflow without provider bundle distributions.
################################
FROM runtime AS core

COPY --from=core-builder --chown=1000:0 /app/.venv /app/.venv
LABEL org.opencontainers.image.title=langflow-core

################################
# FULL IMAGE (default/final target)
# Core application plus the curated provider bundle set.
################################
FROM runtime AS full

COPY --from=full-builder --chown=1000:0 /app/.venv /app/.venv
LABEL org.opencontainers.image.title=langflow
