FROM tiangolo/uvicorn-gunicorn-fastapi:python3.10

WORKDIR /app

# Install Poetry
RUN apt-get update && apt-get install -y curl
RUN curl -sSL https://install.python-poetry.org | python3 - 
# Add Poetry to PATH
ENV PATH="${PATH}:/root/.local/bin"
# Copy the pyproject.toml and poetry.lock files
COPY poetry.lock pyproject.toml ./
# Copy the rest of the application codes
COPY ./ ./


# install dependencies
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi


CMD ["uvicorn", "langflow.cli:app", "--host", "0.0.0.0", "--port", "5003"]
