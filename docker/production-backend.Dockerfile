# Build stage - Use Ubuntu 24.04 for better security
FROM ubuntu:24.04 AS builder

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    gcc \
    g++ \
    build-essential \
    libpq-dev \
    cargo \
    rustc \
    git \
    curl \
    ca-certificates \
    npm \
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

# Copy dependency files
COPY uv.lock pyproject.toml README.md ./
COPY src/backend/base/README.md src/backend/base/uv.lock src/backend/base/pyproject.toml ./src/backend/base/
COPY src/lfx/README.md src/lfx/pyproject.toml ./src/lfx/

# Create virtual environment and install dependencies
RUN python3.12 -m venv /app/.venv && \
    . /app/.venv/bin/activate && \
    if command -v uv >/dev/null 2>&1; then \
        echo "Using uv for installation..." && \
        uv sync --frozen --no-cache --no-dev --extra postgresql && \
        uv pip install --upgrade setuptools; \
    else \
        echo "uv not found, using pip..." && \
        pip install --upgrade pip && \
        pip install -e . --extra postgresql && \
        pip install --upgrade setuptools; \
    fi

# Production stage - Use minimal Ubuntu for backend-only deployment
FROM ubuntu:24.04

# Install only runtime dependencies with minimal packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3.12 \
    libpq5 \
    curl \
    ca-certificates \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r ai-studio && useradd -r -m -g ai-studio ai-studio

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=ai-studio:ai-studio /app/.venv /app/.venv

# Copy application files
COPY --chown=ai-studio:ai-studio LICENSE ./
COPY --chown=ai-studio:ai-studio src/backend/base/langflow /app/src/backend/base/langflow

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/app/.venv/bin:$PATH" \
    AI_STUDIO_HOST=0.0.0.0 \
    AI_STUDIO_PORT=7860

# Create necessary directories
RUN mkdir -p /tmp/ai-studio /home/ai-studio/.cache /app/logs /app/data && \
    chown -R ai-studio:ai-studio /tmp/ai-studio /home/ai-studio/.cache /app/logs /app/data

# Switch to non-root user
USER ai-studio

# Expose port
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# Run the application
CMD ["python", "-m", "langflow", "run", "--host", "$AI_STUDIO_HOST", "--port", "$AI_STUDIO_PORT", "--backend-only"]
