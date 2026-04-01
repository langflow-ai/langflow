# syntax=docker/dockerfile:1
# Langflow + Keycloak SSO plugin
#
# Build:
#   docker build -f docker/keycloak-sso.Dockerfile -t langflow-keycloak-sso .
#
# Run (single instance):
#   docker run -p 7860:7860 \
#     -e KEYCLOAK_ENABLED=true \
#     -e KEYCLOAK_SERVER_URL=https://keycloak.company.com \
#     -e KEYCLOAK_REALM=company \
#     -e KEYCLOAK_CLIENT_ID=langflow-project-a \
#     -e KEYCLOAK_CLIENT_SECRET=<secret> \
#     -e KEYCLOAK_REDIRECT_URI=http://localhost:7860/api/v1/keycloak/callback \
#     -e KEYCLOAK_SHARED_USERNAME=langflow-shared-project-a \
#     -e LANGFLOW_AUTO_LOGIN=false \
#     -e LANGFLOW_SECRET_KEY=<random-32-chars> \
#     langflow-keycloak-sso

################################
# BUILDER
################################
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV RUSTFLAGS='--cfg reqwest_unstable'

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y \
        build-essential \
        gcc \
        git \
        curl \
        npm \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies (lockfile-driven, cached layer) ──────────────────────
COPY ./uv.lock ./README.md ./pyproject.toml /app/
COPY ./src/backend/base/README.md ./src/backend/base/uv.lock ./src/backend/base/pyproject.toml /app/src/backend/base/
COPY ./src/lfx/README.md ./src/lfx/pyproject.toml /app/src/lfx/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-editable \
        --extra postgresql --no-group dev

# ── Application source ────────────────────────────────────────────────────────
COPY ./src /app/src

# ── Build frontend ────────────────────────────────────────────────────────────
COPY ./src/frontend /tmp/src/frontend
WORKDIR /tmp/src/frontend
RUN --mount=type=cache,target=/root/.npm \
    npm ci \
    && LANGFLOW_AUTO_LOGIN=false NODE_OPTIONS="--max-old-space-size=4096" JOBS=1 npm run build \
    && rm -rf /app/src/backend/base/langflow/frontend \
    && cp -r build /app/src/backend/base/langflow/frontend

WORKDIR /app

# ── Final sync (install project itself) ──────────────────────────────────────
# NOTE: no cache mount here — ensures local packages (langflow, langflow-base)
# are always rebuilt from source, picking up frontend build output changes.
RUN uv sync --frozen --no-editable \
        --extra postgresql --no-group dev

# ── Install keycloak-sso plugin AFTER uv sync (not in lockfile) ──────────────
# Must come after uv sync to prevent being removed by --frozen cleanup
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /app/.venv \
        ./src/backend/langflow-keycloak-sso

################################
# RUNTIME
################################
FROM python:3.12.12-slim-trixie AS runtime

# Install system deps + Node.js via nodesource (avoids grep -P regex issues)
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y \
        curl git libpq5 gnupg xz-utils ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/bin/uv  /usr/local/bin/uv
COPY --from=builder /usr/local/bin/uvx /usr/local/bin/uvx

RUN useradd --uid 1000 --gid 0 --no-create-home --home-dir /app/data user

COPY --from=builder --chown=1000:0 /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

RUN mkdir -p /app/data && chown -R 1000:0 /app/data && chown 1000:0 /app

LABEL org.opencontainers.image.title="langflow-keycloak-sso"
LABEL org.opencontainers.image.description="Langflow with Keycloak SSO plugin"
LABEL org.opencontainers.image.licenses=MIT

USER user
WORKDIR /app

# ── Langflow defaults ─────────────────────────────────────────────────────────
ENV LANGFLOW_HOST=0.0.0.0
ENV LANGFLOW_PORT=7860
ENV LANGFLOW_AUTO_LOGIN=false

# ── Keycloak SSO defaults (override at runtime) ───────────────────────────────
ENV KEYCLOAK_ENABLED=false
ENV KEYCLOAK_BUTTON_TEXT="SK하이닉스 SSO 로그인"
ENV KEYCLOAK_SHARED_USERNAME=langflow-shared

CMD ["langflow", "run"]
