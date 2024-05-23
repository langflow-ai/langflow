# Builder stage
FROM python:3.10-slim as builder

# Set environment variables to prevent Python from writing pyc files to disc (unneeded in a container)
# and for Python to not buffer outputs, useful for Docker logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl build-essential

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - \
    && poetry config virtualenvs.create false

# Copy Python dependencies files
COPY base/pyproject.toml base/poetry.lock* /app/

# Install dependencies with Poetry
RUN poetry install --no-interaction --no-ansi

# Copy the application files
COPY ./base /app

# Final stage
FROM python:3.10-slim

WORKDIR /app

# Ensure local Python is in the PATH
ENV PATH="/root/.local/bin:$PATH"

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
COPY --from=builder /usr/local /usr/local
COPY --from=builder /app /app

ENV PYTHONPATH="/root/.local/lib/python3.10/site-packages:$PYTHONPATH"

# Command to run the application
CMD ["uvicorn", "src.main:create_app", "--host", "0.0.0.0", "--port", "7880", "--reload", "--log-level", "debug", "--loop", "asyncio"]
