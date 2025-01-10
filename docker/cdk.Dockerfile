FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y \
    build-essential \
    curl \
    npm \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# # Add Poetry to PATH
ENV PATH="${PATH}:/root/.local/bin"
# # Copy the pyproject.toml and poetry.lock files
COPY pyproject.toml ./
# Copy the rest of the application codes
COPY ./ ./

# Install dependencies
RUN uv sync

RUN uv add botocore==1.34.162 && uv add pymysql 

CMD ["sh", "./docker/container-cmd-cdk.sh"]
