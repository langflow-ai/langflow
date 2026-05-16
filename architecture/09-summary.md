# 9. Mental Model — One-Sentence Summary of Each Layer

| Layer | Role | Entry file |
|---|---|---|
| **Frontend** | Draws graph, manages canvas state, streams results | `src/frontend/src/App.tsx` |
| **API (v1/v2)** | Auth'd HTTP/SSE wrapper around services | `src/backend/base/langflow/api/router.py` |
| **Services** | Stateful singletons (DB, cache, auth, tracing…) | `src/backend/base/langflow/services/deps.py` |
| **LFX Graph engine** | Compiles & runs the flow | `src/lfx/src/lfx/graph/graph/base.py` |
| **Component registry** | 200+ plug-in Python classes the engine can instantiate | `src/lfx/src/lfx/components/` |
| **Persistence** | SQLModel + Alembic | `src/backend/base/langflow/services/database/` |
| **SDK / MCP** | Programmatic + agent-protocol access to the same flows | `src/sdk`, `api/.../mcp_router` |

## The recurring pattern

A `Flow` is a row in the DB whose `data` column is a JSON graph. The engine hydrates that JSON into a `Graph` of `Vertex` objects, each wrapping a `Component` instance. Execution is a topological walk emitting SSE events that the React canvas re-renders live.

## Where to start reading

To learn the codebase fastest, open these in order:

1. **`src/lfx/src/lfx/graph/graph/base.py`** — the core. Read `Graph.from_payload`, `initialize_run`, `async_start`.
2. **`src/backend/base/langflow/api/v1/chat.py`** — how HTTP meets the core. Read the streaming response and the `build_graph_from_db` call.
3. **`src/backend/base/langflow/services/deps.py`** — the DI registry. See which `ServiceType`s exist and how they're requested.
4. **`src/frontend/src/stores/flowStore.ts`** — how the UI mirrors the graph. See how SSE events mutate the canvas.

After those four files the rest of the codebase tends to follow predictable patterns: every router file is thin, every service is a singleton, every component is a class with `inputs`/`outputs`, and every UI feature has its own Zustand store.

## Cross-cutting concerns to know

- **Streaming everywhere** — most run endpoints are SSE, both for user-facing chat and for canvas updates during builds.
- **Two faces to every flow** — the same flow is reachable via REST (`/api/v1/run/...`), via MCP (each flow can be exposed as a tool), and via SDK (Python). One source of truth, three transports.
- **Components are the extension point** — adding a new integration almost always means writing a single Python class under `src/lfx/src/lfx/components/<category>/` plus an icon under `src/frontend/src/icons/`.
- **Class names are identifiers** — never rename a component class; saved flows reference it by name.
