FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
ENV TZ=UTC

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    npm \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

# Install dependencies using uv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r requirements.txt

EXPOSE 7860
EXPOSE 3000

CMD ["./docker/dev.start.sh"]
