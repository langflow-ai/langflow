# User-Facing Contracts

These are the surfaces users depend on. Breaking them silently is the most common way an agent ships work that "doesn't connect to the story." Read this before changing anything below.

## The contract surface

| # | Contract | Source of truth | Rule |
|---|----------|-----------------|------|
| 1 | Component class `name` attribute | `class XComponent: name = "X"` | NEVER rename. Used to match nodes in saved flow JSON. |
| 2 | Component class identifier (Python class name) | `class XComponent` | NEVER rename. Combined with `name` for resolution. |
| 3 | Component file path + module | `src/lfx/src/lfx/components/<cat>/<file>.py` | Renames are breaking. The supported workflow is to add the new component alongside the old one and set `legacy = True` + `replacement = ["<category>.<NewClassName>"]` on the old class. Update every component's `file_names_mapping` in tests for past `SUPPORTED_VERSIONS` (`src/backend/tests/constants.py`). Regenerate starter projects and rebuild the component index. |
| 4 | Input `name=` and `Output(name=...)` on every component | The component file itself | NEVER rename or remove. Saved flows reference these as keys. Adding new optional inputs is safe; removing or renaming breaks every saved flow that used them. |
| 5 | Output order and `Output.types` | Component `outputs = [...]` list | Reordering changes default selection in old flows. Tightening a type is a breaking change; widening is safe. |
| 6 | Default values for inputs | `default=` / `value=` in input spec | Changing a default silently changes behavior for users who relied on the default. Treat as a breaking change unless the old default was a bug. |
| 7 | Flow JSON schema | `src/backend/base/langflow/initial_setup/starter_projects/*.json` (canonical examples) | Top-level `data.nodes[*].data.node` shape and `data.edges` shape are public. New fields must be optional with defaults. |
| 8 | Public REST API | `docs/docs/API-Reference/api-flows-run.mdx`, `api-build.mdx`, `api-files.mdx`, `api-projects.mdx`, `api-logs.mdx`, `api-monitor.mdx`, `api-users.mdx`. Endpoints with `include_in_schema=False` are internal. | Documented endpoints are stable. `POST /api/v1/run/{flow_id_or_name}` and `POST /api/v1/webhook/{flow_id_or_name}` are user contracts — payload shape and status codes are frozen. |
| 9 | MCP tool exposure | `src/backend/base/langflow/api/v1/mcp.py`, `mcp_projects.py`. Tool-mode toggled by `Output.tool_mode` / outputs named `component_as_tool`. | Removing `tool_mode=True` from an existing component output, or changing its name, breaks every Agent flow using it as a tool. |
| 10 | `Message` / `Data` / `DataFrame` schema | `src/lfx/src/lfx/schema/message.py` (`text`, `sender`, `sender_name`, `session_id`, `flow_id`, `timestamp`, `properties`, `content_blocks`, `category`, `files`, `error`, `edit`, `duration`, `session_metadata`) | Inter-component wire format. Add fields with defaults only. Renaming or retyping any listed field breaks every running flow. |
| 11 | Environment variables | `LANGFLOW_*` (server) defined in `src/backend/base/langflow/services/settings/base.py` and `feature_flags.py`. `LFX_*` (executor) defined in `src/lfx/src/lfx/services/settings/base.py`, except a few read directly via `os.getenv` (e.g., `LFX_DEV` in `src/lfx/src/lfx/interface/components.py`). | Public deployment contract. Renaming requires deprecation cycle reading both names. |
| 12 | Database schema | `src/backend/base/langflow/services/database/models/` + `alembic/versions/`. | NEVER edit a model without `make alembic-revision`. Never edit a past migration. Custom-component Python source is stored in user DBs — refactoring an import path used by `from langflow.X import Y` breaks loading those rows. |
| 13 | Starter project JSON | `src/backend/base/langflow/initial_setup/starter_projects/*.json` | Each references real components by `name`/`type`. Renaming a component, removing an input, or changing an output type breaks loading. After ANY component change, re-load the affected starter project. |
| 14 | Webhook payload shape | `POST /api/v1/webhook/{flow_id_or_name}` | External systems POST here. Response status (202 Accepted) and the `dict` body shape are frozen. |
| 15 | Component index | `src/lfx/src/lfx/_assets/component_index.json` | Generated artifact consumed by the frontend. Any field/output addition requires regeneration; CI enforces this on label add. |

## Before-you-change matrix

| If you are about to... | Check / update |
|---|---|
| Rename a component file | Add the new file alongside; set `legacy = True` + `replacement = [...]` on the old class; update every test's `file_names_mapping`; grep `starter_projects/*.json` for the old type |
| Rename an input `name=` | Don't. Add a new input alongside and deprecate the old via `legacy=True` on the component if necessary; grep `starter_projects/*.json` for the old name |
| Add or rename an output | Regenerate starter projects; rebuild component index |
| Change a default value | Treat as breaking. Grep starter projects + tests for reliance |
| Remove `tool_mode=True` from an output | Search agent flows / starter projects using it as a tool; this is a user-visible regression |
| Add a `Message` field | Must be `Optional` with default; never reorder existing |
| Add a REST endpoint | If user-facing, add to `docs/docs/API-Reference/`; if internal, set `include_in_schema=False` |
| Modify a DB model | `make alembic-revision message="..."`; never edit past revisions |
| Change a `LANGFLOW_*` / `LFX_*` env var | Read old name as fallback for at least one minor version; document in release notes |
| Change a request/response schema | Update pydantic schema + `src/frontend/src/types/` + alembic if persisted, all in one PR |

## Breaking changes that look harmless

These all look like cleanup. They are user-visible regressions.

- **Renaming `input_value` → `text`** on a component: 100% of saved flows referencing that input lose their wiring.
- **Reordering `outputs = [a, b]` to `[b, a]`**: old flows with the default selection now route from the wrong output.
- **Tightening `Output(types=["Message", "Data"])` → `["Message"]`**: edges that resolved as `Data` go invalid on load.
- **Changing a `default="gpt-4o-mini"` to `default="gpt-5"`**: silently re-bills users.
- **Moving `langflow/components/foo/bar.py` → `langflow/components/foo2/bar.py`**: custom components stored in user DBs that `from langflow.components.foo.bar import ...` fail on next load. `file_names_mapping` test passes because it only validates listed historical versions, not user code.
- **Dropping `tool_mode=True` from a vector store's `as_dataframe`**: every Agent that called it as a tool now sees the tool disappear.
- **Adding a required field to `Message`**: every queued message in a running deployment fails to deserialize on next read.
- **Renaming a starter project file**: deep links from docs and tutorials 404.

## Why this matters

Langflow flows are **persisted user artifacts** running in production. The system that loads them is forgiving by design: it tolerates new fields, falls back on missing ones, applies type migrations on load. That tolerance is paid for by every contract in the table above. Break one and the system can no longer route around it — the flow stops working.

Treat this file as a checklist. If your change touches any row, the corresponding rule applies; no exceptions without an explicit deprecation plan.
