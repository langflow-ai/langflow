FROM python:3.10-slim

WORKDIR /app

ENV PATH="${PATH}:/root/.local/bin"

COPY ./base ./

RUN apt-get update &&\
    curl -sSL https://install.python-poetry.org | python3 - &&\
    poetry config virtualenvs.create false &&\
    poetry install --no-interaction --no-ansi

CMD ["uvicorn", "--factory", "src.main:create_app", "--host", "0.0.0.0", "--port", "7880", "--reload", "--log-level", "debug", "--loop", "asyncio"]
