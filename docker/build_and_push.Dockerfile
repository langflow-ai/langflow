# syntax=docker/dockerfile:1
# Keep this syntax directive! It's used to enable Docker BuildKit


################################
# BUILDER-BASE
# Used to build deps + create our virtual environment
################################

# 1. use python:3.12.3-slim as the base image until https://github.com/pydantic/pydantic-core/issues/1292 gets resolved
# 2. do not add --platform=$BUILDPLATFORM because the pydantic binaries must be resolved for the final architecture
FROM python:3.12.3-slim as builder-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    \
    # pip
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    \
    # poetry
    # https://python-poetry.org/docs/configuration/#using-environment-variables
    POETRY_VERSION=1.8.2 \
    # make poetry install to this location
    POETRY_HOME="/opt/poetry" \
    # make poetry create the virtual environment in the project's root
    # it gets named `.venv`
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    # do not ask any interactive question
    POETRY_NO_INTERACTION=1 \
    \
    # paths
    # this is where our requirements + virtual environment will live
    PYSETUP_PATH="/opt/pysetup" \
    VENV_PATH="/opt/pysetup/.venv"

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

RUN --mount=type=cache,target=/root/.cache \
    curl -sSL https://install.python-poetry.org | python3 -

WORKDIR /app
COPY pyproject.toml poetry.lock README.md ./
COPY src/ ./src
COPY scripts/ ./scripts
RUN python -m pip install requests --user && cd ./scripts && python update_dependencies.py

# 1. Install the dependencies using the current poetry.lock file to create reproducible builds
# 2. Do not install dev dependencies
# 3. Install all the extras to ensure all optionals are installed as well
# 4. --sync to ensure nothing else is in the environment
# 5. Build the wheel and install "langflow" package (mainly for version)

# Note: moving to build and installing the wheel will make the docker images not reproducible.
RUN $POETRY_HOME/bin/poetry lock --no-update \
      # install current lock file with fixed dependencies versions \
      # do not install dev dependencies \
      && $POETRY_HOME/bin/poetry install --without dev --sync -E deploy -E couchbase -E cassio \
      && $POETRY_HOME/bin/poetry build -f wheel \
      && $POETRY_HOME/bin/poetry run pip install dist/*.whl

################################
# RUNTIME
# Setup user, utilities and copy the virtual environment only
################################
# 1. use python:3.12.3-slim as the base image until https://github.com/pydantic/pydantic-core/issues/1292 gets resolved
FROM python:3.12.3-slim as runtime

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
COPY --from=builder-base --chown=1000 /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

USER user
WORKDIR /app

ENTRYPOINT ["python", "-m", "langflow", "run"]
CMD ["--host", "0.0.0.0", "--port", "7860"]