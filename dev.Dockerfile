FROM tiangolo/uvicorn-gunicorn-fastapi:python3.10

WORKDIR /app

# Install Poetry
# RUN apt-get update && apt-get install -y curl
# RUN curl -sSL https://install.python-poetry.org | python3 - 
# # Add Poetry to PATH
# ENV PATH="${PATH}:/root/.local/bin"
# # Copy the pyproject.toml and poetry.lock files
# COPY poetry.lock pyproject.toml ./
# Copy the rest of the application codes
COPY ./ ./

# Install dependencies
RUN pip install -e .


WORKDIR /app/langflow/backend

CMD ["uvicorn", "langflow_backend.main:app", "--host", "127.0.0.1", "--port", "5003", "--reload"]