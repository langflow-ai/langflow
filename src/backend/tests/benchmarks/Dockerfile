# syntax=docker/dockerfile:1.7
# Measurement Dockerfile for cold-start benchmarks. Phase 1 decisions:
#   Lives at src/backend/tests/benchmarks/Dockerfile, separate from docker/.
#   Base image python:3.13-slim (matches deployed Python version).
#   Installs lfx + benchmarks dep-group only. Forbidden: extras and groups sync flags.
#   BENCH_VARIANT build arg selects lean vs prebaked image.
#   Prebaked variant adds openai + langchain-openai + pandas + scipy + numpy.
#
# Two images from this one file:
#   benchmarks-lean      -- only lfx + benchmarks deps. First-run pays dep-install.
#   benchmarks-prebaked  -- lean + basic_prompting transitive deps pre-installed.
# Delta between them isolates dep-install cost.
#
# Security notes (threat model T-01-04-01..06):
#   No secrets, no API keys, no tokens anywhere in this file.
#   Base image tag pinned (no :latest). uv binary copied from official astral-sh image.

ARG PYTHON_IMAGE=python:3.13-slim
FROM ${PYTHON_IMAGE} AS base

RUN apt-get update \
    && apt-get install -y --no-install-recommends hyperfine ca-certificates curl git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_NO_SYNC=1 \
    UV_NO_DEFAULT_GROUPS=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependency layer. COPY pyproject + uv.lock + README.md files needed for resolution.
# Each workspace member's README.md is referenced by its pyproject.toml (readme = "README.md"),
# so hatchling's editable-build metadata introspection requires them present at uv sync time.
COPY pyproject.toml uv.lock README.md /app/
COPY src/lfx/pyproject.toml src/lfx/README.md /app/src/lfx/
COPY src/backend/base/pyproject.toml src/backend/base/README.md /app/src/backend/base/
COPY src/sdk/pyproject.toml src/sdk/README.md /app/src/sdk/

# Resolve + install deps only (not workspace members). D-09 forbids whole-extra or whole-group sync.
# --no-default-groups skips the dev group (which pulls heavy toolchain deps like crosshair-tool
# requiring gcc); --group benchmarks picks up the measurement tooling only.
RUN uv sync --frozen --no-install-project --no-default-groups --group benchmarks

# Source layer. COPY actual source AFTER deps so source-only changes hit only this layer.
COPY src/lfx /app/src/lfx
COPY src/backend/base /app/src/backend/base
COPY src/sdk /app/src/sdk
COPY src/backend/tests/benchmarks /app/src/backend/tests/benchmarks

# Install workspace members into the managed venv at /app/.venv.
RUN uv sync --frozen --no-default-groups --group benchmarks

# Variant selector. Default is lean; CI flips BENCH_VARIANT=prebaked for the second image.
ARG BENCH_VARIANT=lean
ENV BENCH_VARIANT=${BENCH_VARIANT}

# Prebake conditional layer. CRITICAL: install into the SAME managed venv created by
# the previous uv sync (at /app/.venv), NOT into --system. "uv run" activates /app/.venv, so
# installing into --system would place packages where "uv run" will not find them, silently
# regressing the prebaked variant to the lean scenario at runtime.
#
# Pinning rationale: langchain-openai<1.0 avoids the langchain_core.memory removal issue
# that lfx/cli/run.py's _check_langchain_version_compatibility guards against.
RUN if [ "$BENCH_VARIANT" = "prebaked" ]; then \
      uv pip install --python /app/.venv/bin/python --no-cache \
        "openai>=1.0.0,<2.0.0" \
        "langchain-openai>=0.3.0,<1.0.0" \
        "pandas>=2.0.0" \
        "scipy>=1.10.0" \
        "numpy>=1.24.0" ; \
    elif [ "$BENCH_VARIANT" != "lean" ]; then \
      echo "ERROR: BENCH_VARIANT must be 'lean' or 'prebaked' (got: ${BENCH_VARIANT})" ; \
      exit 1 ; \
    fi

# Convenience symlink: /fixtures -> the benchmarks fixtures directory.
RUN ln -s /app/src/backend/tests/benchmarks/fixtures /fixtures

# Build-time sanity checks so docker build fails loudly if tools are not wired.
RUN uv run lfx --help > /dev/null 2>&1 && hyperfine --version

# Variant-specific sanity: on prebaked, confirm the prebake deps are importable under uv run
# (this catches the --system vs --python /app/.venv/bin/python mistake at build time).
RUN [ "$BENCH_VARIANT" = "lean" ] || uv run python -c "import openai, langchain_openai; print('prebake-verified')"

# Benign default. The driver overrides this at run time.
CMD ["uv", "run", "lfx", "--help"]
