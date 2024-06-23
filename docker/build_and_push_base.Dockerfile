

# syntax=docker/dockerfile:1
# Keep this syntax directive! It's used to enable Docker BuildKit

# Based on https://github.com/python-poetry/poetry/discussions/1879?sort=top#discussioncomment-216865
# but I try to keep it updated (see history)

################################
# PYTHON-BASE
# Sets up all our shared environment variables
################################

# use python:3.12.3-slim as the base image until https://github.com/pydantic/pydantic-core/issues/1292 gets resolved
FROM python:3.12.3-slim as python-base

# python
ENV PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
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


# prepend poetry and venv to path
ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"


################################
# BUILDER-BASE
# Used to build deps + create our virtual environment
################################
FROM python-base as builder-base
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    # deps for installing poetry
    curl \
    # deps for building python deps
    build-essential \
    # npm
    npm \
    # gcc
    gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache \
    curl -sSL https://install.python-poetry.org | python3 -

# Now we need to copy the entire project into the image
COPY pyproject.toml poetry.lock ./
COPY src/frontend/package.json /tmp/package.json
RUN cd /tmp && npm install
WORKDIR /app
COPY src/frontend ./src/frontend
RUN rm -rf src/frontend/node_modules
RUN cp -a /tmp/node_modules /app/src/frontend
COPY scripts ./scripts
COPY Makefile ./
COPY README.md ./
RUN cd src/frontend && npm run build
COPY src/backend ./src/backend
RUN cp -r src/frontend/build src/backend/base/langflow/frontend
RUN rm -rf src/backend/base/dist
RUN useradd -m -u 1000 user && \
    mkdir -p /app/langflow && \
    chown -R user:user /app && \
    chmod -R u+w /app/langflow

# Update PATH with home/user/.local/bin
ENV PATH="/home/user/.local/bin:${PATH}"
RUN cd src/backend/base && $POETRY_HOME/bin/poetry build

# Copy virtual environment and built .tar.gz from builder base

USER user
# Install the package from the .tar.gz
RUN python -m pip install /app/src/backend/base/dist/*.tar.gz --user


ENTRYPOINT ["python", "-m", "langflow", "run"]
CMD ["--host", "0.0.0.0", "--port", "7860"]
