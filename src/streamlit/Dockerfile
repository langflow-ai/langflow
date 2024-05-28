# Builder stage
FROM python:3.10-slim as builder

# Set environment variables
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
RUN poetry add watchdog[watchmedo] && poetry install --no-interaction --no-ansi

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

COPY ./script.py /tmp
COPY ./restart_script.sh /tmp
COPY ./start.sh /app

RUN apt-get update && apt-get install -y procps && rm -rf /var/lib/apt/lists/*
# Create a script to run both Uvicorn and Streamlit
RUN chmod +x /tmp/restart_script.sh /app/start.sh

# Command to run the applications
CMD ["/app/start.sh"]