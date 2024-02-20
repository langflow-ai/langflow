

# syntax=docker/dockerfile:1
# Keep this syntax directive! It's used to enable Docker BuildKit

# Based on https://github.com/python-poetry/poetry/discussions/1879?sort=top#discussioncomment-216865
# but I try to keep it updated (see history)

################################
# PYTHON-BASE
# Sets up all our shared environment variables
################################
FROM python:3.10-slim as python-base

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
    POETRY_VERSION=1.7.1 \
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
RUN
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    # deps for installing poetry
    curl \
    # deps for building python deps
    build-essential \
    # npm
    npm


# Now we need to copy the entire project into the image
WORKDIR /app
COPY pyproject.toml poetry.lock ./
COPY src ./src
COPY Makefile ./
COPY README.md ./
RUN curl -sSL https://install.python-poetry.org | python3 - && make build

# Final stage for the application
FROM python-base as final

# Copy virtual environment and built .tar.gz from builder base
COPY --from=builder-base /app/dist/*.tar.gz ./

# Install the package from the .tar.gz
RUN pip install *.tar.gz

WORKDIR /app
CMD ["python", "-m", "langflow", "run", "--host", "0.0.0.0", "--port", "7860"]
