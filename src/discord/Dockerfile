FROM python:3.10-slim as builder

ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

COPY base/pyproject.toml base/poetry.lock* /app/

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && export PATH="/root/.local/bin:$PATH" \
    && poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

COPY ./base /app

FROM python:3.10-slim

WORKDIR /app

COPY --from=builder /app /app
COPY --from=builder /root/.local /root/.local


CMD ["uvicorn", "--factory", "src.main:create_app", "--host", "0.0.0.0", "--port", "7880", "--reload", "--log-level", "debug", "--loop", "asyncio"]
