# Pinned by digest for reproducible builds. The bare `python3.14-bookworm-slim`
# tag is floating — it silently advanced between rebuilds and broke psycopg
# (no `psycopg-binary` wheel for the new Python + no system libpq). Pinning the
# digest makes a Python bump deliberate and lockfile-aware.
# Stays on Python 3.14 to mirror prod (docker/build_and_push.Dockerfile), which
# runs 3.14 + libpq5 (see the apt layer below). Resolved 2026-06-03 from
# `docker pull ghcr.io/astral-sh/uv:python3.14-bookworm-slim` → Python 3.14.2.
# To bump: pull the new tag, copy its RepoDigest here, confirm `uv.lock` supports it.
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim@sha256:7cf77f594be8042dab6daa9fe326f90962252268b4f120a7f5dccce4d947e6c1
ENV TZ=UTC

WORKDIR /app

# pipefail so a failed NodeSource download fails the layer: under the default
# shell, `curl | bash` exits 0 when curl dies, the repo setup silently never
# runs, and `apt-get install nodejs` quietly installs Debian's ancient node.
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y \
    build-essential \
    curl \
    git \
    libpq5 \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    # Belt and braces: whatever the setup script did, the wrong node major
    # must fail the build here, not as tooling errors much later.
    && node --version | grep -q '^v22\.' \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install the d2 compiler (Epic D.3). The DIAGRAM_GENERATION engine shells out to
# `d2` to compile-validate generated D2 before persisting it (lothal/d2_compile.py).
# Pinned to track the `@terrastruct/d2` WASM build the frontend renders with (D.5);
# kept in lockstep with docker/build_and_push_backend.Dockerfile (the prod image).
ENV D2_VERSION=v0.7.1
RUN ARCH=$(dpkg --print-architecture) \
    && curl -fsSL "https://github.com/terrastruct/d2/releases/download/${D2_VERSION}/d2-${D2_VERSION}-linux-${ARCH}.tar.gz" \
       | tar -xz -C /tmp \
    && install "/tmp/d2-${D2_VERSION}/bin/d2" /usr/local/bin/d2 \
    && rm -rf "/tmp/d2-${D2_VERSION}" \
    && d2 --version

COPY . /app

# Install dependencies using uv
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=README.md,target=README.md \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=src/backend/base/README.md,target=src/backend/base/README.md \
    --mount=type=bind,source=src/backend/base/uv.lock,target=src/backend/base/uv.lock \
    --mount=type=bind,source=src/backend/base/pyproject.toml,target=src/backend/base/pyproject.toml \
    --mount=type=bind,source=src/lfx/README.md,target=src/lfx/README.md \
    --mount=type=bind,source=src/lfx/pyproject.toml,target=src/lfx/pyproject.toml \
    --mount=type=bind,source=src/sdk/README.md,target=src/sdk/README.md \
    --mount=type=bind,source=src/sdk/pyproject.toml,target=src/sdk/pyproject.toml \
    uv sync --frozen --no-install-project --no-dev --extra postgresql

EXPOSE 7860
EXPOSE 3000

CMD ["./docker/dev.start.sh"]
