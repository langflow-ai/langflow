FROM ghcr.io/astral-sh/uv:python3.12-bookworm
ENV TZ=UTC

WORKDIR /app

# Install system dependencies (langflow + nsjail requirements)
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y \
    build-essential \
    curl \
    npm \
    git \
    libpq-dev \
    python3-dev \
    postgresql-client \
    pkg-config \
    libnl-route-3-dev \
    libnl-3-dev \
    libprotobuf-dev \
    protobuf-compiler \
    bison \
    flex \
    sudo \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

# Install Python dependencies using uv
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=README.md,target=README.md \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=src/backend/base/README.md,target=src/backend/base/README.md \
    --mount=type=bind,source=src/backend/base/uv.lock,target=src/backend/base/uv.lock \
    --mount=type=bind,source=src/backend/base/pyproject.toml,target=src/backend/base/pyproject.toml \
    uv pip install --system psycopg psycopg-binary sqlalchemy[postgresql] && \
    uv sync --frozen --no-install-project --no-dev --extra postgresql && \
    uv pip install --system certifi

# Build and install nsjail from source
RUN set -e \
    && git clone https://github.com/google/nsjail.git /tmp/nsjail \
    && cd /tmp/nsjail \
    && echo "Building nsjail..." \
    && make -j$(nproc) \
    && echo "Installing nsjail..." \
    && cp nsjail /usr/local/bin/ \
    && chmod +x /usr/local/bin/nsjail \
    && echo "Testing nsjail installation..." \
    && /usr/local/bin/nsjail --help > /dev/null \
    && echo "nsjail installed successfully" \
    && cd / \
    && rm -rf /tmp/nsjail

# Create sandbox directories and set permissions
RUN mkdir -p /tmp/langflow-sandbox \
    && mkdir -p /var/log/langflow-sandbox \
    && chown -R nobody:nogroup /tmp/langflow-sandbox \
    && chmod 755 /tmp/langflow-sandbox

# Create langflow user and configure sudo
RUN useradd -m -s /bin/bash langflow \
    && echo "langflow ALL=(ALL) NOPASSWD: /usr/local/bin/nsjail" >> /etc/sudoers

# Set sandbox environment variables
ENV LANGFLOW_SANDBOX_ENABLED=true

EXPOSE 7860
EXPOSE 3000

CMD ["./docker/dev.start.sh"]
