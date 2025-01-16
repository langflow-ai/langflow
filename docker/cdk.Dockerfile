FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
ENV TZ=UTC

WORKDIR /app

# Install system dependencies including PostgreSQL
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y \
    gcc \
    g++ \ 
    curl \
    build-essential \
    postgresql \
    postgresql-contrib \
    postgresql-server-dev-all \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create PostgreSQL user and database
USER postgres
RUN /etc/init.d/postgresql start && \
    psql --command "CREATE USER langflow WITH SUPERUSER PASSWORD 'langflow';" && \
    createdb -O langflow langflow && \
    /etc/init.d/postgresql stop

USER root

# Install dependencies using uv
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=README.md,target=README.md \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=src/backend/base/README.md,target=src/backend/base/README.md \
    --mount=type=bind,source=src/backend/base/uv.lock,target=src/backend/base/uv.lock \
    --mount=type=bind,source=src/backend/base/pyproject.toml,target=src/backend/base/pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

ENV PATH="${PATH}:/root/.local/bin"
# Copy the application code
COPY ./ ./

# Create startup script
RUN echo '#!/bin/bash\n\
service postgresql start\n\
python src/backend/base/langflow/main.py' > /app/start.sh && \
chmod +x /app/start.sh

CMD ["/app/start.sh"]
