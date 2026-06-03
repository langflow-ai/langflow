# syntax=docker/dockerfile:1
# Keep this syntax directive! It's used to enable Docker BuildKit


################################
# BUILDER-BASE
# Used to build deps + create our virtual environment
################################

# 1. use python:3.12.3-slim as the base image until https://github.com/pydantic/pydantic-core/issues/1292 gets resolved
# 2. do not add --platform=$BUILDPLATFORM because the pydantic binaries must be resolved for the final architecture
# Use a Python image with uv pre-installed
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS builder

# Install the project into `/app`
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Set RUSTFLAGS for reqwest unstable features needed by apify-client v2.0.0
ENV RUSTFLAGS='--cfg reqwest_unstable'

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y \
    # deps for building python deps
    build-essential \
    git \
    # npm
    npm \
    # gcc
    gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy files first to avoid permission issues with bind mounts
COPY ./uv.lock /app/uv.lock
COPY ./README.md /app/README.md
COPY ./pyproject.toml /app/pyproject.toml
COPY ./src/backend/base/README.md /app/src/backend/base/README.md
COPY ./src/backend/base/pyproject.toml /app/src/backend/base/pyproject.toml
# Copy lfx metadata files since it's a workspace member
COPY ./src/lfx/pyproject.toml /app/src/lfx/pyproject.toml
COPY ./src/lfx/README.md /app/src/lfx/README.md
# Copy sdk metadata files since it's a workspace member
COPY ./src/sdk/pyproject.toml /app/src/sdk/pyproject.toml
COPY ./src/sdk/README.md /app/src/sdk/README.md
# Workspace bundles (LE-1023 pilot+): every directory under ``src/bundles``
# is a uv workspace member, so each bundle's pyproject.toml must be present
# for ``uv sync --no-install-project`` to resolve the workspace.  Copy the
# whole tree once rather than enumerating each bundle, so a new bundle does
# not require a Dockerfile edit.
COPY ./src/bundles /app/src/bundles

# Install the project's dependencies using the lockfile and settings
# We need to mount the root uv.lock and pyproject.toml to build the base with uv because we're still using uv workspaces
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    cd src/backend/base && uv sync --frozen --no-install-project --no-dev --no-editable --extra postgresql

COPY ./src /app/src

COPY src/frontend /tmp/src/frontend
WORKDIR /tmp/src/frontend
# Increase memory and disable concurrent builds to avoid esbuild crashes on emulated architectures
# Force esbuild to use JS implementation on emulated architectures to avoid native binary crashes
RUN npm install \
    && ESBUILD_BINARY_PATH="" NODE_OPTIONS="--max-old-space-size=4096" JOBS=1 npm run build \
    && cp -r build /app/src/backend/base/langflow/frontend \
    && rm -rf /tmp/src/frontend

WORKDIR /app/src/backend/base
# langflow-base ships the core framework only.  The extension bundles
# (lfx-duckduckgo, lfx-arxiv, lfx-ibm, lfx-docling) are intentionally NOT
# installed in this image: they are dependencies of the full ``langflow``
# distribution, not of the lean ``langflow-base`` core, and we keep that
# boundary at the image layer too.  Consumers who want those components
# should use the ``langflow`` image, or ``pip install`` the bundle (e.g.
# ``lfx-duckduckgo``) alongside langflow-base.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv sync --frozen --no-dev --no-editable --extra postgresql

# Pilot Bundle re-attach (LE-1023): ``lfx-arxiv`` ships the ArXiv
# component as a standalone distribution (its pyproject lives at
# ``src/bundles/arxiv``).  The base image was the user-facing path for
# that component before the move; install the extracted bundle so the
# runtime image keeps the same component set.  ``--no-deps`` is
# intentional: the bundle's runtime deps (lfx, defusedxml) are now all in
# the langflow-base lockfile above, so installing them here would yank
# duplicates that fight the locked versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/arxiv

# Pilot Bundle re-attach (LE-1023): ``lfx-datastax`` ships the 11
# DataStax / AstraDB components plus the shared ``AstraDBBaseComponent``
# mixin that used to live at ``lfx.base.datastax.astradb_base``.
# ``--no-deps`` is intentional: ``langchain-astradb``, ``astrapy``,
# ``langchain-graph-retriever``, and ``graph-retriever`` are already in
# ``langflow-base[complete]`` (via the per-vendor extras the bundle's
# pyproject duplicates) so installing them here would yank duplicates
# that fight the locked versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/datastax

# Bundle re-attach: ``lfx-wikipedia`` ships the Wikipedia
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/wikipedia

# Bundle re-attach: ``lfx-wolframalpha`` ships the WolframAlpha
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/wolframalpha

# Bundle re-attach: ``lfx-serpapi`` ships the SerpAPI
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/serpapi

# Bundle re-attach: ``lfx-tavily`` ships the Tavily
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/tavily

# Bundle re-attach: ``lfx-youtube`` ships the YouTube
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/youtube

# Bundle re-attach: ``lfx-exa`` ships the Exa
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/exa

# Bundle re-attach: ``lfx-bing`` ships the Bing
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/bing

# Bundle re-attach: ``lfx-baidu`` ships the Baidu
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/baidu

# Bundle re-attach: ``lfx-firecrawl`` ships the Firecrawl
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/firecrawl

# Bundle re-attach: ``lfx-glean`` ships the Glean
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/glean

# Bundle re-attach: ``lfx-scrapegraph`` ships the Scrapegraph
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/scrapegraph

# Bundle re-attach: ``lfx-searchapi`` ships the Searchapi
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/searchapi

# Bundle re-attach: ``lfx-jigsawstack`` ships the Jigsawstack
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/jigsawstack

# Bundle re-attach: ``lfx-needle`` ships the Needle
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/needle

# Bundle re-attach: ``lfx-openai`` ships the OpenAI
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/openai

# Bundle re-attach: ``lfx-aiml`` ships the Aiml
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/aiml

# Bundle re-attach: ``lfx-amazon`` ships the Amazon
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/amazon

# Bundle re-attach: ``lfx-anthropic`` ships the Anthropic
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/anthropic

# Bundle re-attach: ``lfx-azure`` ships the Azure
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/azure

# Bundle re-attach: ``lfx-cohere`` ships the Cohere
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/cohere

# Bundle re-attach: ``lfx-deepseek`` ships the Deepseek
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/deepseek

# Bundle re-attach: ``lfx-groq`` ships the Groq
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/groq

# Bundle re-attach: ``lfx-huggingface`` ships the Huggingface
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/huggingface

# Bundle re-attach: ``lfx-ibm`` ships the Ibm
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/ibm

# Bundle re-attach: ``lfx-litellm`` ships the Litellm
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/litellm

# Bundle re-attach: ``lfx-lmstudio`` ships the Lmstudio
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/lmstudio

# Bundle re-attach: ``lfx-maritalk`` ships the Maritalk
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/maritalk

# Bundle re-attach: ``lfx-mistral`` ships the Mistral
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/mistral

# Bundle re-attach: ``lfx-notdiamond`` ships the Notdiamond
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/notdiamond

# Bundle re-attach: ``lfx-novita`` ships the Novita
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/novita

# Bundle re-attach: ``lfx-nvidia`` ships the Nvidia
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/nvidia

# Bundle re-attach: ``lfx-ollama`` ships the Ollama
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/ollama

# Bundle re-attach: ``lfx-openrouter`` ships the Openrouter
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/openrouter

# Bundle re-attach: ``lfx-perplexity`` ships the Perplexity
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/perplexity

# Bundle re-attach: ``lfx-sambanova`` ships the Sambanova
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/sambanova

# Bundle re-attach: ``lfx-vertexai`` ships the Vertexai
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/vertexai

# Bundle re-attach: ``lfx-xai`` ships the Xai
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/xai

# Bundle re-attach: ``lfx-cometapi`` ships the Cometapi
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/cometapi

# Bundle re-attach: ``lfx-vllm`` ships the Vllm
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/vllm

# Bundle re-attach: ``lfx-cassandra`` ships the Cassandra
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/cassandra

# Bundle re-attach: ``lfx-chroma`` ships the Chroma
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/chroma

# Bundle re-attach: ``lfx-clickhouse`` ships the Clickhouse
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/clickhouse

# Bundle re-attach: ``lfx-couchbase`` ships the Couchbase
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/couchbase

# Bundle re-attach: ``lfx-elastic`` ships the Elastic
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/elastic

# Bundle re-attach: ``lfx-faiss`` ships the Faiss
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/faiss

# Bundle re-attach: ``lfx-milvus`` ships the Milvus
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/milvus

# Bundle re-attach: ``lfx-mongodb`` ships the Mongodb
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/mongodb

# Bundle re-attach: ``lfx-pgvector`` ships the Pgvector
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/pgvector

# Bundle re-attach: ``lfx-pinecone`` ships the Pinecone
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/pinecone

# Bundle re-attach: ``lfx-qdrant`` ships the Qdrant
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/qdrant

# Bundle re-attach: ``lfx-redis`` ships the Redis
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/redis

# Bundle re-attach: ``lfx-supabase`` ships the Supabase
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/supabase

# Bundle re-attach: ``lfx-upstash`` ships the Upstash
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/upstash

# Bundle re-attach: ``lfx-vectara`` ships the Vectara
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/vectara

# Bundle re-attach: ``lfx-weaviate`` ships the Weaviate
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/weaviate

# Bundle re-attach: ``lfx-zep`` ships the Zep
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/zep

# Bundle re-attach: ``lfx-notion`` ships the Notion
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/notion

# Bundle re-attach: ``lfx-agentql`` ships the Agentql
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/agentql

# Bundle re-attach: ``lfx-apify`` ships the Apify
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/apify

# Bundle re-attach: ``lfx-assemblyai`` ships the Assemblyai
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/assemblyai

# Bundle re-attach: ``lfx-cleanlab`` ships the Cleanlab
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/cleanlab

# Bundle re-attach: ``lfx-cloudflare`` ships the Cloudflare
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/cloudflare

# Bundle re-attach: ``lfx-composio`` ships the Composio
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/composio

# Bundle re-attach: ``lfx-confluence`` ships the Confluence
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/confluence

# Bundle re-attach: ``lfx-docling`` ships the Docling
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/docling

# Bundle re-attach: ``lfx-git`` ships the Git
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/git

# Bundle re-attach: ``lfx-homeassistant`` ships the Homeassistant
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/homeassistant

# Bundle re-attach: ``lfx-icosacomputing`` ships the Icosacomputing
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/icosacomputing

# Bundle re-attach: ``lfx-langwatch`` ships the Langwatch
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/langwatch

# Bundle re-attach: ``lfx-mem0`` ships the Mem0
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/mem0

# Bundle re-attach: ``lfx-twelvelabs`` ships the Twelvelabs
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/twelvelabs

# Bundle re-attach: ``lfx-unstructured`` ships the Unstructured
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/unstructured

# Bundle re-attach: ``lfx-agentics`` ships the Agentics
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/agentics

# Bundle re-attach: ``lfx-altk`` ships the Altk
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/altk

# Bundle re-attach: ``lfx-codeagents`` ships the Codeagents
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/codeagents

# Bundle re-attach: ``lfx-crewai`` ships the Crewai
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/crewai

# Bundle re-attach: ``lfx-cuga`` ships the Cuga
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/cuga

# Bundle re-attach: ``lfx-olivya`` ships the Olivya
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/olivya

# Bundle re-attach: ``lfx-vlmrun`` ships the Vlmrun
# components as a standalone distribution.  ``--no-deps`` is intentional
# -- the bundle's runtime deps live in the langflow-base lockfile so
# installing them here would yank duplicates that fight the locked
# versions.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps /app/src/bundles/vlmrun

# Google split (4 bundles from the in-tree ``google/`` directory).
# Each ships ``--no-deps`` because the SDK pins they need
# (langchain-google-genai, langchain-google-community,
# google-cloud-bigquery, google-api-python-client) are already in the
# langflow-base lockfile via per-vendor extras the bundle pyprojects
# duplicate.
RUN --mount=type=cache,target=/root/.cache/uv \
    RUSTFLAGS='--cfg reqwest_unstable' \
    uv pip install --no-deps \
        /app/src/bundles/google_genai \
        /app/src/bundles/google_workspace \
        /app/src/bundles/google_bigquery \
        /app/src/bundles/google_search

################################
# RUNTIME
# Setup user, utilities and copy the virtual environment only
################################
FROM python:3.14-slim-trixie AS runtime


RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y curl git libpq5 gnupg xz-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
COPY --from=builder /usr/local/bin/uvx /usr/local/bin/uvx
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
RUN useradd user -u 1000 -g 0 --no-create-home --home-dir /app/data

COPY --from=builder --chown=1000 /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Pre-create LANGFLOW_CONFIG_DIR (the default location used by the docker_example
# compose file) with the non-root user as owner. When the official compose mounts
# a fresh named volume at /app/langflow, Docker copies this directory's ownership
# and permissions into the new volume, so the in-container uid=1000 user can
# write secret_key, profile_pictures, etc. Without this, the volume is created
# as root:root and Langflow crashes during startup with PermissionError on
# /app/langflow/secret_key. See https://github.com/langflow-ai/langflow/issues/10437
RUN mkdir -p /app/langflow && chown -R 1000:0 /app/langflow && chmod -R g+rwX /app/langflow

LABEL org.opencontainers.image.title=langflow
LABEL org.opencontainers.image.authors=['Langflow']
LABEL org.opencontainers.image.licenses=MIT
LABEL org.opencontainers.image.url=https://github.com/langflow-ai/langflow
LABEL org.opencontainers.image.source=https://github.com/langflow-ai/langflow

USER user
WORKDIR /app

ENV LANGFLOW_HOST=0.0.0.0
ENV LANGFLOW_PORT=7860

CMD ["langflow-base", "run"]
