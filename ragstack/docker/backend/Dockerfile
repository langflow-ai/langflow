FROM python:3.11-slim-bookworm as builder
RUN pip install poetry==1.7.1

ENV POETRY_VIRTUALENVS_IN_PROJECT=1
ENV POETRY_VIRTUALENVS_CREATE=1
ENV POETRY_CACHE_DIR=/tmp/poetry_cache

ARG DEBIAN_FRONTEND=noninteractive
RUN echo 'Acquire::http::Timeout "30";\nAcquire::http::ConnectionAttemptDelayMsec "2000";\nAcquire::https::Timeout "30";\nAcquire::https::ConnectionAttemptDelayMsec "2000";\nAcquire::ftp::Timeout "30";\nAcquire::ftp::ConnectionAttemptDelayMsec "2000";\nAcquire::Retries "15";' > /etc/apt/apt.conf.d/99timeout_and_retries \
  && apt-get update && apt-get -y dist-upgrade && apt-get -y install gcc
RUN mkdir /app
COPY pyproject.toml poetry.lock* README* /app/

COPY src/backend /app/src/backend

RUN cd /app && poetry install --no-interaction --no-ansi -E deploy

FROM python:3.11-slim-bookworm as runtime

LABEL org.opencontainers.image.title=ragstack-ai-langflow
LABEL org.opencontainers.image.version=0.0.2
LABEL org.opencontainers.image.authors=['DataStax']
LABEL org.opencontainers.image.licenses=BUSL-1.1
LABEL org.opencontainers.image.url=https://github.com/datastax/ragstack-ai-langflow
LABEL org.opencontainers.image.source=https://github.com/datastax/ragstack-ai-langflow

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

RUN useradd ragstack -u 10000 -g 0 --no-create-home --home-dir /app/data
USER 10000

WORKDIR /app
COPY --from=builder --chown=10000 /app/ /app/

ENV LANGFLOW_DATABASE_URL=sqlite:///$HOME/app/langflow.db