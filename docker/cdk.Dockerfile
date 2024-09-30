FROM --platform=linux/amd64 python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install gcc g++ curl build-essential postgresql-server-dev-all -y
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="${PATH}:/root/.local/bin"
# Copy poetry and packages files
COPY poetry.lock pyproject.toml ./
COPY ./ ./
# Run poetry installation fix any package conflict arises 
RUN poetry config virtualenvs.create false && poetry lock --no-update && poetry install --no-interaction --no-ansi

RUN poetry add botocore
RUN poetry add pymysql psycopg2-binary alembic
# Run the exact directory 
CMD ["sh", "./docker/container-cmd-cdk.sh"]