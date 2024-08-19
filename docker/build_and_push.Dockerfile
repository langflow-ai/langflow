# syntax=docker/dockerfile:1
# Keep this syntax directive! It's used to enable Docker BuildKit


################################
# BUILDER-BASE
# Used to build deps + create our virtual environment
################################

# 1. use python:3.12.3-slim as the base image until https://github.com/pydantic/pydantic-core/issues/1292 gets resolved
# 2. do not add --platform=$BUILDPLATFORM because the pydantic binaries must be resolved for the final architecture
FROM python:3.12.3-slim AS builder-base
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Place entry points in the environment at the front of the path
ENV PATH="/opt/venv/bin:$PATH"
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    # deps for installing poetry
    curl \
    # deps for building python deps
    build-essential npm \
    # gcc
    gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /app

# 1. Install the dependencies using the current poetry.lock file to create reproducible builds
# 2. Do not install dev dependencies
# 3. Install all the extras to ensure all optionals are installed as well
# 4. --sync to ensure nothing else is in the environment
# 5. Build the wheel and install "langflow" package (mainly for version)

# Note: moving to build and installing the wheel will make the docker images not reproducible.
ENV VIRTUAL_ENV=/opt/venv
RUN uv venv /opt/venv
COPY src/backend/langflow/pyproject.toml src/backend/langflow/pyproject.toml
# COPY src/backend/langflow-base/pyproject.toml src/backend/langflow-base/pyproject.toml
RUN cd src/backend/langflow && uv pip install -r pyproject.toml --no-sources
COPY src/backend/langflow/ ./src/backend/langflow
COPY src/backend/langflow-base/ ./src/backend/langflow-base/
RUN cd src/backend/langflow && uv pip install . --no-sources
################################
# RUNTIME
# Setup user, utilities and copy the virtual environment only
################################
# 1. use python:3.12.3-slim as the base image until https://github.com/pydantic/pydantic-core/issues/1292 gets resolved
FROM python:3.12.3-slim AS runtime

RUN apt-get -y update \
    && apt-get install --no-install-recommends -y \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

LABEL org.opencontainers.image.title=langflow
LABEL org.opencontainers.image.authors=['Langflow']
LABEL org.opencontainers.image.licenses=MIT
LABEL org.opencontainers.image.url=https://github.com/langflow-ai/langflow
LABEL org.opencontainers.image.source=https://github.com/langflow-ai/langflow

RUN useradd user -u 1000 -g 0 --no-create-home --home-dir /app/data
COPY --from=builder-base --chown=1000 /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
USER user
WORKDIR /app

ENV LANGFLOW_HOST=0.0.0.0
ENV LANGFLOW_PORT=7860

CMD ["langflow", "run"]
