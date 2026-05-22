# syntax=docker/dockerfile:1
# Keep this syntax directive! It's used to enable Docker BuildKit
#
# Backend-only Langflow image
# - No frontend code or assets
# - No Playwright

################################
# BUILDER
################################
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS builder

WORKDIR /app

# Required for apify-client
ENV RUSTFLAGS='--cfg reqwest_unstable'

# Install build dependencies
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y \
        build-essential \
        gcc \
        git \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy only backend source (excludes frontend)
COPY ./src/backend ./src/backend
COPY ./src/lfx ./src/lfx
COPY ./src/sdk ./src/sdk
# Workspace bundles (LE-1023 pilot+): each Bundle is shipped as a
# separate distribution that langflow-base depends on by name (e.g.
# ``lfx-duckduckgo``).  Without copying the source tree, the install
# below cannot resolve the path-based bundle deps and ends up with a
# Langflow image missing components that previously lived in lfx.
COPY ./src/bundles ./src/bundles

# Create venv and install langflow-base with dependencies
# Using uv pip instead of uv sync to avoid workspace complexities
RUN uv venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/.venv"

# Install langflow-base with all extras except dev (which includes Playwright).
# Each pilot-extracted bundle is installed alongside so the runtime image
# keeps shipping the same component set users had before LE-1023.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install \
        ./src/sdk \
        ./src/lfx \
        ./src/bundles/duckduckgo \
        ./src/bundles/arxiv \
        ./src/bundles/datastax \
        ./src/bundles/wikipedia \
        ./src/bundles/wolframalpha \
        ./src/bundles/serpapi \
        ./src/bundles/tavily \
        ./src/bundles/youtube \
        ./src/bundles/exa \
        ./src/bundles/bing \
        ./src/bundles/baidu \
        ./src/bundles/firecrawl \
        ./src/bundles/glean \
        ./src/bundles/scrapegraph \
        ./src/bundles/searchapi \
        ./src/bundles/jigsawstack \
        ./src/bundles/needle \
        ./src/bundles/openai \
        ./src/bundles/aiml \
        ./src/bundles/amazon \
        ./src/bundles/anthropic \
        ./src/bundles/azure \
        ./src/bundles/cohere \
        ./src/bundles/deepseek \
        ./src/bundles/groq \
        ./src/bundles/huggingface \
        ./src/bundles/ibm \
        ./src/bundles/litellm \
        ./src/bundles/lmstudio \
        ./src/bundles/maritalk \
        ./src/bundles/mistral \
        ./src/bundles/notdiamond \
        ./src/bundles/novita \
        ./src/bundles/nvidia \
        ./src/bundles/ollama \
        ./src/bundles/openrouter \
        ./src/bundles/perplexity \
        ./src/bundles/sambanova \
        ./src/bundles/vertexai \
        ./src/bundles/xai \
        ./src/bundles/cometapi \
        ./src/bundles/vllm \
        ./src/bundles/cassandra \
        ./src/bundles/chroma \
        ./src/bundles/clickhouse \
        ./src/bundles/couchbase \
        ./src/bundles/elastic \
        ./src/bundles/faiss \
        ./src/bundles/milvus \
        ./src/bundles/mongodb \
        ./src/bundles/pgvector \
        ./src/bundles/pinecone \
        ./src/bundles/qdrant \
        ./src/bundles/redis \
        ./src/bundles/supabase \
        ./src/bundles/upstash \
        ./src/bundles/vectara \
        ./src/bundles/weaviate \
        ./src/bundles/zep \
        ./src/bundles/notion \
        ./src/bundles/agentql \
        ./src/bundles/apify \
        ./src/bundles/assemblyai \
        ./src/bundles/cleanlab \
        ./src/bundles/cloudflare \
        ./src/bundles/composio \
        ./src/bundles/confluence \
        ./src/bundles/docling \
        ./src/bundles/git \
        ./src/bundles/homeassistant \
        ./src/bundles/icosacomputing \
        ./src/bundles/langwatch \
        ./src/bundles/mem0 \
        ./src/bundles/twelvelabs \
        ./src/bundles/unstructured \
        ./src/bundles/agentics \
        ./src/bundles/altk \
        ./src/bundles/codeagents \
        ./src/bundles/crewai \
        ./src/bundles/cuga \
        ./src/bundles/olivya \
        ./src/bundles/vlmrun \
        ./src/bundles/google_genai \
        ./src/bundles/google_workspace \
        ./src/bundles/google_bigquery \
        ./src/bundles/google_search \
        "./src/backend/base[complete,postgresql]"

################################
# RUNTIME
################################
FROM python:3.14-slim-trixie AS runtime

# Install minimal runtime dependencies
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y \
        curl \
        git \
        libpq5 \
        gnupg \
        xz-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
COPY --from=builder /usr/local/bin/uvx /usr/local/bin/uvx
# Install Node.js (required for npx-based MCP stdio servers)
RUN ARCH=$(dpkg --print-architecture) \
    && if [ "$ARCH" = "amd64" ]; then NODE_ARCH="x64"; \
       elif [ "$ARCH" = "arm64" ]; then NODE_ARCH="arm64"; \
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

CMD ["python", "-m", "langflow", "run", "--backend-only"]
