# AI Studio Backend Dockerfile
# Adapted from genesis-studio-service for monorepo structure
# Build stage - Use Ubuntu 24.04 for better security
FROM ubuntu:24.04 AS builder

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    python3.13 \
    python3.13-venv \
    python3.13-dev \
    gcc \
    g++ \
    build-essential \
    libpq-dev \
    cargo \
    rustc \
    git \
    curl \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install uv with retry logic and fallback
RUN for i in 1 2 3; do \
        curl -LsSf https://astral.sh/uv/install.sh | sh && break || \
        (echo "Attempt $i failed, retrying..." && sleep 5); \
    done || \
    (echo "Primary installation failed, trying alternative method..." && \
     curl -LsSf https://github.com/astral-sh/uv/releases/latest/download/uv-installer.sh | sh) || \
    (echo "Installing via pip as fallback..." && \
     pip install uv)

ENV PATH="/root/.local/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy dependency files from monorepo root
COPY pyproject.toml uv.lock ./
COPY README.md LICENSE ./

# Copy backend source code from monorepo structure
COPY src/backend/ ./src/backend/

# Create virtual environment and install dependencies
RUN python3.13 -m venv /app/.venv && \
    . /app/.venv/bin/activate && \
    if command -v uv >/dev/null 2>&1; then \
        echo "Using uv for installation..." && \
        uv sync --frozen --no-cache --no-dev && \
        echo "Force installing exact versions..." && \
        uv pip install --force-reinstall pydantic==2.10.6 sqlalchemy==2.0.43 && \
        uv pip install --upgrade litellm>=1.61.15 setuptools>=78.1.1; \
    else \
        echo "uv not found, using pip..." && \
        pip install --upgrade pip && \
        pip install -e . && \
        pip install --force-reinstall pydantic==2.10.6 sqlalchemy==2.0.43 && \
        pip install --upgrade litellm>=1.61.15 setuptools>=78.1.1; \
    fi

# Production stage - Use minimal Ubuntu
FROM ubuntu:24.04

# Install only runtime dependencies with minimal packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    python3.13 \
    libpq5 \
    curl \
    ca-certificates \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r aistudio && useradd -r -m -g aistudio aistudio

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=aistudio:aistudio /app/.venv /app/.venv

# Copy application files from monorepo structure
COPY --chown=aistudio:aistudio LICENSE ./
COPY --chown=aistudio:aistudio src/backend/ ./src/backend/

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/app/.venv/bin:$PATH" \
    HOST=0.0.0.0 \
    PORT=7860 \
    LANGFLOW_COMPONENTS_PATH="/app/.venv/lib/python3.13/site-packages/langflow/components:/app/src/backend/base/langflow/components"

# Create necessary directories and ensure alembic can write logs
RUN mkdir -p /tmp/langflow /home/aistudio/.cache /app/logs /app/data && \
    chown -R aistudio:aistudio /tmp/langflow /home/aistudio/.cache /app/logs /app/data /app/src/backend/base/langflow/alembic && \
    chmod 664 /app/src/backend/base/langflow/alembic/alembic.log || true

# Switch to non-root user
USER aistudio

# Expose port
EXPOSE 7860

# Health check - validates service health
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7860/api/v1/health || exit 1

# Run the application
CMD ["uvicorn", "langflow.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "7860"]