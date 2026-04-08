# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## Project Overview

Langflow is a visual workflow builder for AI-powered agents. It has a Python/FastAPI backend, React/TypeScript frontend, and a lightweight executor CLI (lfx).

## Prerequisites

- **Python:** 3.10-3.13
- **uv:** >=0.4 (Python package manager)
- **Node.js:** >=20.19.0 (v22.12 LTS recommended)
- **npm:** v10.9+
- **make:** For build coordination

## Common Commands

### Development Setup
```bash
make init              # Install all dependencies + pre-commit hooks
make run_cli           # Build and run Langflow (http://localhost:7860)
make run_clic          # Clean build and run (use when frontend issues occur)
```

### Development Mode (Hot Reload)
```bash
make backend           # FastAPI on port 7860 (terminal 1)
make frontend          # Vite dev server on port 3000 (terminal 2)
```

For component development, enable dynamic loading:
```bash
LFX_DEV=1 make backend                    # Load all components dynamically
LFX_DEV=mistral,openai make backend       # Load only specific modules
```

### Code Quality
```bash
make format_backend    # Format Python (ruff) - run FIRST before lint
make format_frontend   # Format TypeScript (biome)
make format            # Both
make lint              # mypy type checking
```

### Testing
```bash
make unit_tests                    # Backend unit tests (pytest, parallel)
make unit_tests async=false        # Sequential tests
uv run pytest path/to/test.py      # Single test file
uv run pytest path/to/test.py::test_name  # Single test

make test_frontend                 # Jest unit tests
make tests_frontend                # Playwright e2e tests
```

### Database Migrations
```bash
make alembic-revision message="Description"  # Create migration
make alembic-upgrade                         # Apply migrations
make alembic-downgrade                       # Rollback one version
```

## Architecture

### Monorepo Structure
```
src/
├── backend/
│   ├── base/langflow/     # Core backend package (langflow-base)
│   │   ├── api/           # FastAPI routes (v1/, v2/)
│   │   ├── components/    # Built-in Langflow components
│   │   ├── services/      # Service layer (auth, database, cache, etc.)
│   │   ├── graph/         # Flow graph execution engine
│   │   └── custom/        # Custom component framework
│   └── tests/             # Backend tests
├── frontend/              # React/TypeScript UI
│   └── src/
│       ├── components/    # UI components
│       ├── stores/        # Zustand state management
│       └── icons/         # Component icons
└── lfx/                   # Lightweight executor CLI
```

### Key Packages
- **langflow**: Main package with all integrations
- **langflow-base**: Core framework (api, services, graph engine)
- **lfx**: Standalone CLI for running flows (`lfx serve`, `lfx run`)

### Service Layer
Backend services in `src/backend/base/langflow/services/`:
- `auth/` - Authentication
- `database/` - SQLAlchemy models and migrations
- `cache/` - Caching layer
- `storage/` - File storage
- `tracing/` - Observability integrations

## Component Development

Components live in `src/backend/base/langflow/components/`. To add a new component:

1. Create component class inheriting from `Component`
2. Define `display_name`, `description`, `icon`, `inputs`, `outputs`
3. Add to `__init__.py` (alphabetical order)
4. Run with `LFX_DEV=1 make backend` for hot reload

**IMPORTANT:** Changing a component's class name is a breaking change and should never be done. The class name serves as an identifier used to match components in saved flows and to flag them for updates in the UI. Renaming it will break existing flows that use that component.

### Component Structure
```python
from langflow.custom import Component
from langflow.io import MessageTextInput, Output

class MyComponent(Component):
    display_name = "My Component"
    description = "What it does"
    icon = "component-icon"  # Lucide icon name or custom

    inputs = [
        MessageTextInput(name="input_value", display_name="Input"),
    ]
    outputs = [
        Output(display_name="Output", name="output", method="process"),
    ]

    def process(self) -> Message:
        # Component logic
        return Message(text=self.input_value)
```

### Component Testing
Tests go in `src/backend/tests/unit/components/`. Use base classes:
- `ComponentTestBaseWithClient` - Components needing API access
- `ComponentTestBaseWithoutClient` - Pure logic components

Required fixtures: `component_class`, `default_kwargs`, `file_names_mapping`

## Frontend Development

- **React 19** + TypeScript + Vite
- **Zustand** for state management
- **@xyflow/react** for graph visualization
- **Tailwind CSS** for styling

### Custom Icons
1. Create SVG component in `src/frontend/src/icons/YourIcon/`
2. Export with `forwardRef` and `isDark` prop support
3. Add to `lazyIconImports.ts`
4. Set `icon = "YourIcon"` in Python component

## Testing Notes

- `@pytest.mark.api_key_required` - Tests requiring external API keys
- `@pytest.mark.no_blockbuster` - Skip blockbuster plugin
- Database tests may fail in batch but pass individually
- Pre-commit hooks require `uv run git commit`
- Always use `uv run` when running Python commands

### Graph Testing Pattern

Proper Graph tests follow this pattern:
1. Build graph with connected components
2. Connect them via `.set()` calls
3. Call `async_start` and iterate over the results
4. Validate the results

### Testing Best Practices

- Avoid mocking in tests when possible
- Prefer real integrations for more reliable tests

## Version Management
```bash
make patch v=1.5.0  # Update version across all packages
```

This updates: `pyproject.toml`, `src/backend/base/pyproject.toml`, `src/frontend/package.json`

## Pre-commit Workflow

1. Run `make format_backend` (FIRST - saves time on lint fixes)
2. Run `make format_frontend`
3. Run `make lint`
4. Run `make unit_tests`
5. Commit changes (use `uv run git commit` if pre-commit hooks are enabled)

## Pull Request Guidelines

- Follow [semantic commit conventions](https://www.conventionalcommits.org/)
- Reference any issues fixed (e.g., `Fixes #1234`)
- Ensure all tests pass before submitting

## Documentation

Documentation uses Docusaurus and lives in `docs/`:
```bash
cd docs
yarn install
yarn start        # Dev server on port 3000 (prompts for 3001 if 3000 is in use)
```

## Local Setup with Colima (Verified)

This section documents a tested Colima-based local run for Langflow built from this repository source code (not the prebuilt `langflowai/langflow` image).

### Prerequisites

- Colima installed on macOS
- Internet access to pull base images and dependencies
- Host port `7860` available

### Start Colima

Use a stable resource profile and enable VM network addressing:

```bash
colima start --cpu 4 --memory 8 --disk 100 --runtime containerd --network-address
```

Verify:

```bash
colima status
colima list
```

Expected: runtime `containerd` and an address like `192.168.64.2`.

### Build Langflow image from local repository sources

```bash
colima ssh -- sudo -n nerdctl build -t local-langflow-src -f "/Users/vasidmi/Documents/Github/bitmanager/langflow/docker/build_and_push.Dockerfile" "/Users/vasidmi/Documents/Github/bitmanager/langflow"
```

### Run Langflow from the locally built image

```bash
colima ssh -- bash -lc 'sudo -n nerdctl rm -f langflow-local-src >/dev/null 2>&1 || true; sudo -n nerdctl run -d --name langflow-local-src -p 7860:7860 local-langflow-src:latest'
```

Check container:

```bash
colima ssh -- sudo -n nerdctl ps --filter name=langflow-local-src
```

### Verify Access

```bash
curl -sS -o /tmp/langflow_src_localhost.html -w "%{http_code}" http://127.0.0.1:7860/
curl -sS -o /tmp/langflow_src_ip.html -w "%{http_code}" http://192.168.64.2:7860/
```

Expected HTTP status code: `200`.

Open in browser:

- `http://localhost:7860`
- `http://192.168.64.2:7860`

### Logs and Recovery

```bash
colima ssh -- sudo -n nerdctl logs --tail 120 langflow-local-src
```

If runtime becomes unstable:

```bash
colima stop
colima start --cpu 4 --memory 8 --disk 100 --runtime containerd --network-address
```

Then rerun the build and run commands.

### Stop and Cleanup

```bash
colima ssh -- sudo -n nerdctl rm -f langflow-local-src
colima stop
```

## Local Setup with Colima (Backend-only + Local Frontend, Verified)

This section documents a tested flow where backend + database run in Colima containers, while frontend runs locally on the host in dev mode.

### Build backend-only image from local source

```bash
colima ssh -- sudo -n nerdctl build -t local-langflow-backend-src -f "/Users/vasidmi/Documents/Github/bitmanager/langflow/docker/build_and_push_backend.Dockerfile" "/Users/vasidmi/Documents/Github/bitmanager/langflow"
```

### Start backend database and backend-only API

Create an isolated network and start PostgreSQL:

```bash
colima ssh -- bash -lc 'sudo -n nerdctl network create langflow-backend-dev >/dev/null 2>&1 || true'
colima ssh -- bash -lc 'sudo -n nerdctl rm -f langflow-postgres-local langflow-backend-local >/dev/null 2>&1 || true'
colima ssh -- bash -lc 'sudo -n nerdctl run -d --name langflow-postgres-local --network langflow-backend-dev -e POSTGRES_USER=langflow -e POSTGRES_PASSWORD=langflow -e POSTGRES_DB=langflow -p 5433:5432 pgvector/pgvector:pg16'
```

Start backend-only Langflow and connect it to PostgreSQL:

```bash
colima ssh -- bash -lc 'sudo -n nerdctl run -d --name langflow-backend-local --network langflow-backend-dev -p 7860:7860 -e LANGFLOW_DATABASE_URL=postgresql://langflow:langflow@langflow-postgres-local:5432/langflow -e LANGFLOW_SUPERUSER=langflow -e LANGFLOW_SUPERUSER_PASSWORD=langflow local-langflow-backend-src:latest'
```

### Verify backend API

```bash
colima ssh -- sudo -n nerdctl ps --filter name=langflow-backend-local --filter name=langflow-postgres-local
curl -sS -o /tmp/langflow_backend_health.json -w "%{http_code}" http://127.0.0.1:7860/health
```

Expected health status code: `200`.

### Run frontend locally (host machine)

From repository root:

```bash
VITE_PROXY_TARGET=http://localhost:7860 make frontend
```

This starts Vite on port `3000` and proxies API/health calls to backend on port `7860`.

Alternative direct command:

```bash
VITE_PROXY_TARGET=http://localhost:7860 npm --prefix src/frontend start
```

If your frontend stack uses Bun instead of npm, run the equivalent dev command (for example `VITE_PROXY_TARGET=http://localhost:7860 bun dev`).

### Backend-only logs and cleanup

```bash
colima ssh -- sudo -n nerdctl logs --tail 120 langflow-backend-local
colima ssh -- sudo -n nerdctl rm -f langflow-backend-local langflow-postgres-local
```



