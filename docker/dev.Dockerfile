FROM ghcr.io/astral-sh/uv:latest AS uv_installer
FROM registry.access.redhat.com/ubi10/python-314-minimal
USER root
COPY --from=uv_installer /uv /usr/local/bin/uv
COPY --from=uv_installer /uvx /usr/local/bin/uvx
ENV TZ=UTC

WORKDIR /app

RUN microdnf install -y tar xz \
    gcc gcc-c++ make python3.14-devel \
    curl \
    npm \
    git \
    && microdnf clean all

COPY . /app

# Install dependencies using uv
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=README.md,target=README.md \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=src/backend/base/README.md,target=src/backend/base/README.md \
    --mount=type=bind,source=src/backend/base/pyproject.toml,target=src/backend/base/pyproject.toml \
    --mount=type=bind,source=src/lfx/README.md,target=src/lfx/README.md \
    --mount=type=bind,source=src/lfx/pyproject.toml,target=src/lfx/pyproject.toml \
    --mount=type=bind,source=src/sdk/README.md,target=src/sdk/README.md \
    --mount=type=bind,source=src/sdk/pyproject.toml,target=src/sdk/pyproject.toml \
    --mount=type=bind,source=src/bundles,target=src/bundles \
    uv sync --frozen --no-install-project --no-dev --extra postgresql

EXPOSE 7860
EXPOSE 3000

CMD ["./docker/dev.start.sh"]
