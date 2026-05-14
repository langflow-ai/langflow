# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## Project Overview

Langflow is a visual workflow builder for AI-powered agents. It has a Python/FastAPI backend, React/TypeScript frontend, and a lightweight executor CLI (lfx).

## Contributor Guardrail Skills

Author-time skills under `.agents/skills/` (the cross-tool [Agent Skills](https://agentskills.io/) convention — read by Claude Code, Codex CLI, Gemini CLI, Copilot, and others) auto-fire when contributors edit specific surfaces. They surface the engineering practices an experienced contributor would apply by reflex — tests, formatting, identifier stability, the consult-a-maintainer expectation on user-visible changes. Most are advisory; the breaking-change gate halts work until explicit agreement is confirmed.

- `langflow-component-edit` — components under `src/backend/base/langflow/components/`.
- `langflow-ux-change` — user-visible changes under `src/frontend/` or to component `display_name`/`description`/`icon`.
- `langflow-starter-project-edit` — starter projects under `src/backend/base/langflow/initial_setup/starter_projects/`.
- `langflow-issue-or-spec` — drafting GitHub issues, RFCs, design docs.
- `langflow-breaking-change-gate` — gates renames/removals of identifiers, public exports, API routes, schema fields, migrations, and CLI commands.

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

**IMPORTANT:** Database migrations are permanent once shipped. Once a migration has run on user databases it cannot be edited or removed. Any new or modified migration requires maintainer agreement before merge — both the schema shape (is this the right column/table forever?) and the rollback story.

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

**IMPORTANT:** A component's class name, input `name=` fields, output `name=` fields, and output `method=` fields are all identifiers stored in users' saved flow files. Renaming or removing any of them is a breaking change and requires maintainer agreement before merge. Editing `display_name`, `description`, or `icon` is fine — those are not identifiers.

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

**IMPORTANT:** User-visible UI, copy, icon, or component-metadata changes are product decisions. Consult a maintainer or decision-maker before shipping them, not after. Run and update Playwright tests (`make tests_frontend`) when behavior changes.

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
- When running tests inside a sub-package (e.g. `langflow-base`, `lfx`), sync that package's dev group first: `uv sync --group dev --package langflow-base`. The default `uv sync` only resolves the top-level workspace and may leave dev-only test deps (e.g. `fakeredis`) uninstalled.

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

Pre-commit hooks run ruff and biome automatically on `git commit`, so manual
formatting is not required. To avoid an extra commit cycle when you have many
changes:

1. Run `make format_backend` once before staging - fixes most ruff issues up front.
2. Run `uv run git commit` (the `uv run` ensures pre-commit finds the right Python).
3. If you touched backend code, run `make unit_tests` locally for faster feedback than CI.

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
