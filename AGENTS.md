# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## Project Overview

Langflow is a visual workflow builder for AI-powered agents. It has a Python/FastAPI backend, React/TypeScript frontend, and a lightweight executor CLI (lfx).

## Prerequisites

- **Python:** 3.10-3.14
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
- `authorization/` - Authorization (RBAC) plugin layer — see below
- `database/` - SQLAlchemy models and migrations
- `cache/` - Caching layer
- `storage/` - File storage
- `tracing/` - Observability integrations

### Authorization (RBAC)

Authorization is a pluggable layer separate from authentication:

- **OSS** ships the interface (`BaseAuthorizationService` in `lfx`) + a pass-through implementation (`LangflowAuthorizationService`) + the `authz_*` and `casbin_rule` DB schema + route guards.
- Implementations register via the `lfx.services` entry point `authorization_service` in `lfx.toml` (same pattern as the SSO `auth_service`). A registered plugin reads the `authz_*` admin tables and writes compiled rules to `casbin_rule`.

Default is **off**: `LANGFLOW_AUTHZ_ENABLED=false`. When enabled with only the OSS stub registered, every check returns allow — the stub is a no-op so routes stay wired and audit rows still flow. Real allow/deny requires a registered authorization plugin.

Route guards live in `langflow.services.authorization.guards` (the legacy `langflow.services.authorization.utils` path re-exports them for backward compatibility):
- `ensure_flow_permission(user, FlowAction.*, flow_id=..., flow_user_id=..., workspace_id=..., folder_id=...)` — single-flow CRUD + execute
- `ensure_deployment_permission(user, DeploymentAction.*, deployment_id=..., deployment_user_id=..., workspace_id=..., project_id=...)`
- `ensure_project_permission(user, ProjectAction.*, project_id=..., project_user_id=..., workspace_id=...)`
- `ensure_knowledge_base_permission(user, KnowledgeBaseAction.*, kb_name=..., kb_user_id=...)`
- `ensure_variable_permission(user, VariableAction.*, variable_id=..., variable_user_id=...)`
- `ensure_file_permission(user, FileAction.*, file_id=..., file_user_id=...)`
- `ensure_share_permission(user, ShareAction.*, share_id=..., share_user_id=...)`
- `filter_visible_resources(user, resource_type=..., candidates=..., act=...)` — list-endpoint filter; safe no-op in OSS

The enforcement request shape is `(subject, domain, object, action)`:
- subject = `user:{uuid}`
- domain = `project:{uuid}` → `workspace:{uuid}` → `*` (resolved by `_resolve_flow_domain`; the more specific domain wins so project-scoped grants match directly while workspace-scoped grants still flow down via plugin-side role inheritance)
- object = `flow:{uuid}` / `deployment:{uuid}` / `project:{uuid}` / `flow:*` / etc.
- action = `read` / `write` / `create` / `delete` / `execute` / `deploy`

**Share-aware fetch (Phase 3):** route fetch helpers (`_read_flow`, `get_flow_by_id_or_endpoint_name`, `get_deployment`, project reads in `projects.py`, v2 file fetcher, variable PATCH/DELETE in `variable.py`) branch on `BaseAuthorizationService.supports_cross_user_fetch()`. The OSS pass-through reports `False` so the existing owner-scoped queries are preserved — enabling `LANGFLOW_AUTHZ_ENABLED=true` without a registered plugin cannot widen visibility. Plugins set `SUPPORTS_CROSS_USER_FETCH=True` so resources load by id alone and `ensure_*_permission` decides access; route handlers can convert a plugin-deny `HTTPException(403)` to `HTTPException(404)` via `langflow.services.authorization.fetch.deny_to_404` to preserve UUID privacy.

**Share CRUD API (Phase 3):** `/api/v1/authz/shares` provides POST / GET / PATCH / DELETE on `authz_share` rows. The handler enforces an OSS floor (resource owner or superuser may administer shares for that resource) so the OSS pass-through cannot let a non-owner mint share rows. Each write fires `BaseAuthorizationService.invalidate_user` / `invalidate_all` so a registered enforcer can drop cached policy. Audit rows are written via `audit_decision` with `share:create` / `share:update` / `share:delete` actions.

**Audit query API (Phase 4):** `GET /api/v1/authz/audit` (superuser-only) exposes a paginated, filterable view of `authz_audit_log`. Supports `user_id`, `resource_type`, `resource_id`, `action`, `result`, `since`, `until` filters; page size capped at 200.

**Default role catalog (Phase 4):** the consolidated foundations migration `7c8d9e0f1a2b_authz_foundations` seeds the three built-in `is_system=True` roles (viewer / developer / admin) with `"{resource}:{action}"` permission slugs. OSS does not interpret these — they exist so a registered plugin's policy sync has a stable bootstrap source.

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
