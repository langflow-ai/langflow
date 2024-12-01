# Source: https://github.com/a5chin/python-uv
FROM debian:bookworm-slim AS builder

ENV CARGO_HOME="/opt/.cargo"

SHELL [ "/bin/bash", "-o", "pipefail", "-c" ]

WORKDIR /opt

# The installer requires curl (and certificates) to download the release archive
# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl

# Run uv installer
RUN curl -LsSf https://astral.sh/uv/install.sh | sh


FROM mcr.microsoft.com/vscode/devcontainers/base:bookworm


ENV CARGO_HOME="/opt/.cargo"
ENV PATH="$CARGO_HOME/bin/:$PATH"
ENV PYTHONUNBUFFERED=True
ENV UV_LINK_MODE=copy

WORKDIR /opt

COPY --from=builder --chown=vscode: $CARGO_HOME $CARGO_HOME