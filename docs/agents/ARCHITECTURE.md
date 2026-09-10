# Architecture Boundaries

Langflow is a runnable base application, a curated distribution, an executor
SDK, standalone extensions, and one frontend. Dependencies point in one
direction. Most "off-narrative" code is a boundary violation. Read this before
adding a new file.

## Package dependency graph (one-way only)

```text
frontend (TS)  ──HTTP──▶  langflow-base (UI/API, services, graph, db, alembic)
                                   │
                                   ▼ may import
                               lfx (executor, primitives, built-in components)
                                   │
                                   ▼ may import
                               langchain-core, pydantic

langflow (curated distribution) ──depends on──▶ langflow-base
             │
             └──depends on──▶ standalone lfx-* extensions ──depends on──▶ lfx
```

### Dependency rules

- **`lfx` MUST NOT import `langflow.*`.** (`langflow-base` installs the
  `langflow` import package.) If LFX code needs a service, define an interface
  inside `lfx` and inject the implementation from the application. Existing
  upward imports are known violations; do not add more.
- **`langflow-base` MAY import `lfx`.** It MUST NOT import vendor-specific component modules from `langflow.components.<vendor>`.
- **Standalone `lfx-*` extensions MAY import the public LFX bundle API.** They
  MUST NOT import application services from `langflow-base`.
- **`langflow` is dependency metadata, not another application layer.** It adds
  the curated extension set to the same `langflow-base` executable and runtime.
- **`frontend` talks to `langflow` only via HTTP/WebSocket.** No shared filesystem state.

## "Where does this code go?" decision tree

Walk top-down. Stop at the first match.

1. Is it framework-agnostic flow execution, base component classes, or `Component` primitives?
   → `src/lfx/src/lfx/` (`base/` for shared primitives, `components/` for built-ins shipped with lfx).
2. Is it a FastAPI route, auth, db model, alembic migration, or a lifecycle-managed singleton?
   → `src/backend/base/langflow/` (`api/`, `services/X/`, `alembic/versions/`).
3. Is it a vendor integration (OpenAI, Pinecone, Notion, …) — a `Component` subclass that wraps a third-party SDK?
   → a standalone package under `src/bundles/<provider>/`, with an `extension.json` manifest. Add it to the curated `langflow` dependencies only when it belongs in the default distribution. Never rename the component class.
4. Is it UI, state, or icons?
   → `src/frontend/src/`. If it consumes a new API field, also update `src/frontend/src/types/`.
5. Is it CLI behavior for `lfx run` / `lfx serve`?
   → `src/lfx/src/lfx/cli/`.
6. Is it a SQLAlchemy/SQLModel model change?
   → `services/database/models/` AND `make alembic-revision message="..."` AND apply with `make alembic-upgrade`.
7. Is it a flow JSON schema change?
   → STOP. Existing saved flows must keep loading. Add a version mapping; do not mutate the existing shape. See [CONTRACTS.md](./CONTRACTS.md).
8. Is it shared by both `lfx` and `langflow-base`?
   → `src/lfx/src/lfx/base/`, never `langflow/base/`.

## Dependency direction — bad/good examples

- **Bad:** `from langflow.services.deps import session_scope` inside `src/lfx/...`.
  **Good:** Define `lfx.interfaces.SessionProvider`, accept it as a constructor arg; `langflow` wires the concrete `session_scope` at startup.
- **Bad:** `from langflow.components.openai import ...` inside `langflow-base` core (`api/`, `services/`, `graph/`).
  **Good:** Components are loaded dynamically via the component registry; core code references `Component` only.
- **Bad:** A new `MyHelperService` that's just functions.
  **Good:** Utility functions go in `langflow/helpers/` or `lfx/utils/`. A service inherits from `services/base.Service` and is registered via `services/factory.py`.

## API change protocol

- **`api/v1/`** is the live, stable surface (~25 routers). Existing v1 endpoints MUST stay backwards-compatible: only additive fields, never rename or remove.
- **`api/v2/`** is the **active redesign surface** (`files`, `mcp`, `registration`, `workflow`) — both are mounted at runtime in `api/router.py`. v2 is **not** "future"; the old cursor rule was wrong.
- Add a new endpoint to v2 only if it (a) replaces a v1 endpoint with a breaking shape change, or (b) belongs to one of the four v2 domains. Otherwise extend v1 additively.
- A breaking change to a v1 endpoint is forbidden. Add a v2 sibling and leave v1 in place.

## Cross-cutting change protocol

A change that touches a request/response shape MUST update three places in the same PR:

1. The pydantic model in `langflow/api/v{1,2}/schemas.py` (or the route's local schema).
2. The TypeScript type in `src/frontend/src/types/` consumed by the affected page/store. There is no OpenAPI generator — the types are hand-maintained, so the frontend silently breaks at runtime if you skip this.
3. If the field is persisted: a new alembic revision (`make alembic-revision message=...`) AND a flow-JSON version mapping if the shape lives inside saved flows.

If you cannot do all three in one PR, do not start.

## Service vs utility vs component

- **Service** (`services/<name>/`): lifecycle-managed singleton, inherits `services.base.Service`, registered through `services/factory.py`, accessed via `services/deps.py`. Use when the thing has state, startup/shutdown, or shared connections (db, cache, queue).
- **Utility** (`helpers/`, `utils/`, or `lfx/utils/`): pure or near-pure functions. Use when there is no shared state and no lifecycle.
- **Component** (`src/lfx/src/lfx/components/<category>/`): user-visible node in the graph, subclass of `Component`, with `display_name`, `inputs`, `outputs`. Use only when the user must wire it on the canvas. Do not add a Component to expose internal plumbing.

## `lfx/base/` vs `langflow/base/`

Both exist. Both have `agents/`, `data/`, `models/`, `prompts/`. New shared primitives go in **`src/lfx/src/lfx/base/`**. The `langflow/base/` tree is legacy; do not add to it.
