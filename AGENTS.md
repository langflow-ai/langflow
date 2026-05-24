# AGENTS.md

Guidance for AI coding agents working in this repository.

> **Before you write code, read [docs/agents/PHILOSOPHY.md](./docs/agents/PHILOSOPHY.md).** Most off-narrative work comes from skipping it.

## What Langflow is

Langflow is a **visual flow builder first**. Users drag components onto a canvas, wire them together, and either run the resulting flow in the Playground, deploy it as an API, or expose it as an MCP server. Saved flows are persistent JSON artifacts running in production — backwards compatibility for components is non-negotiable.

The repo is three Python packages and one frontend:

- **`lfx`** (`src/lfx/`): the executor core. Component base classes, the graph engine, and built-in components live here. Should not depend on `langflow` or `langflow-base` — see [docs/agents/ARCHITECTURE.md](./docs/agents/ARCHITECTURE.md) for the ~14 known violations to fix-not-extend.
- **`langflow-base`** (`src/backend/base/langflow/`): the platform. FastAPI routes, auth, persistence, alembic, services. May import `lfx`.
- **`langflow`**: the integration distribution that ships everything together.
- **`frontend`** (`src/frontend/`): React 19 + TypeScript + Vite + Zustand + `@xyflow/react`. Talks to the backend over HTTP/WebSocket only.

Dependencies flow one way: `frontend → langflow → langflow-base → lfx`. See [docs/agents/ARCHITECTURE.md](./docs/agents/ARCHITECTURE.md).

## Non-negotiable tenets

These are extracted from [PHILOSOPHY.md](./docs/agents/PHILOSOPHY.md). The full file has the rest; these are the ones every change must respect.

1. **Flows are user artifacts.** Component class names, `name` attributes, input/output names, and input types are frozen once shipped. Mark old components `legacy=True` instead of editing.
2. **Every backend feature must land on the canvas.** If it can't be a component or a property of one, it's an SDK feature and belongs in `lfx`, not `langflow-base`.
3. **Components are the unit of work.** Don't add a route, store, or service unless a component or UI page consumes it.
4. **Visible data flow beats clever magic.** Pass data through inputs and outputs. No hidden globals or side-channel state.
5. **Composition over capability.** One job per component. Split before you add a tenth input.
6. **It is not a fix without evidence.** Adding error handling, retries, type widening, or skipping a flaky test does not constitute a fix.

## Documentation map

Read the file that matches your task before you write code.

| Topic | File | When to read |
|---|---|---|
| Project story, design tenets | [docs/agents/PHILOSOPHY.md](./docs/agents/PHILOSOPHY.md) | Before any non-trivial change |
| Package boundaries, where code goes, API versioning | [docs/agents/ARCHITECTURE.md](./docs/agents/ARCHITECTURE.md) | Before adding a file or endpoint |
| Component dev: scope, breaking changes, conventions, icons | [docs/agents/COMPONENTS.md](./docs/agents/COMPONENTS.md) | Before adding or editing a component |
| User-facing contracts: flow JSON, REST API, MCP, env vars | [docs/agents/CONTRACTS.md](./docs/agents/CONTRACTS.md) | Before changing anything user-visible |
| Test patterns, fixtures, mocking policy | [docs/agents/TESTING.md](./docs/agents/TESTING.md) | Before writing or changing tests |
| Don't/do rules, "fixes that aren't," before-claiming-done checklist | [docs/agents/ANTI-PATTERNS.md](./docs/agents/ANTI-PATTERNS.md) | Before claiming work is done |

## Prerequisites

- **Python:** 3.10–3.13
- **uv:** ≥0.4 (always use `uv run` for Python commands)
- **Node.js:** ≥20.19.0 (v22.12 LTS recommended)
- **npm:** v10.9+
- **make:** for build coordination

## Common commands

### Development setup

```bash
make init              # Install all dependencies + pre-commit hooks
make run_cli           # Build and run Langflow (http://localhost:7860)
make run_clic          # Clean build and run (use when frontend issues occur)
```

### Development mode (hot reload)

```bash
make backend           # FastAPI on port 7860 (terminal 1)
make frontend          # Vite dev server on port 3000 (terminal 2)
```

For component development with dynamic loading:

```bash
LFX_DEV=1 make backend                    # Load all components dynamically
LFX_DEV=mistral,openai make backend       # Load only specific modules
```

### Code quality

```bash
make format_backend    # Format Python (ruff) — run FIRST before lint
make format_frontend   # Format TypeScript (biome)
make format            # Both
make lint              # mypy type checking
```

### Testing

```bash
make unit_tests                            # Backend unit tests (pytest, parallel)
make unit_tests async=false                # Sequential
uv run pytest path/to/test.py              # Single test file
uv run pytest path/to/test.py::test_name   # Single test

make test_frontend                         # Jest unit tests
make tests_frontend                        # Playwright e2e tests

# lfx tests specifically — run uv sync inside src/lfx (not src/lfx/src/lfx)
cd src/lfx && uv sync && uv run pytest

# Sub-package tests (langflow-base, lfx) — sync that package's dev group first,
# otherwise dev-only deps like fakeredis stay uninstalled.
uv sync --group dev --package langflow-base
```

See [docs/agents/TESTING.md](./docs/agents/TESTING.md) for fixtures, base classes, and the graph testing pattern.

### Database migrations

```bash
make alembic-revision message="Description"  # Create migration
make alembic-upgrade                          # Apply migrations
make alembic-downgrade                        # Rollback one version
```

Never edit a past migration. Run `test_database.py` sequentially after any DB change.

### Version management

```bash
make patch v=1.5.0  # Update version across all packages
```

## Pre-commit workflow

Pre-commit hooks run ruff and biome automatically on `git commit`, so manual formatting isn't required. To avoid an extra commit cycle:

1. Run `make format_backend` once before staging — fixes most ruff issues up front.
2. Run `uv run git commit` (the `uv run` ensures pre-commit finds the right Python).
3. If you touched backend code, run `make unit_tests` locally for faster feedback than CI.

## Pull request guidelines

- Follow [semantic commit conventions](https://www.conventionalcommits.org/).
- Reference issues fixed (`Fixes #1234`).
- Target the active `release-X.Y.Z` branch, not `main`. See [CONTRIBUTING.md](./CONTRIBUTING.md).
- Don't push or open PRs without explicit user direction.
- No "Generated with Claude Code" / `Co-Authored-By: Claude` trailers.
- No test-plan checklists or Jira links in PR descriptions.

## Documentation

Documentation uses Docusaurus and lives in `docs/`:

```bash
cd docs
yarn install
yarn start        # Dev server on port 3000 (3001 if 3000 is in use)
```
