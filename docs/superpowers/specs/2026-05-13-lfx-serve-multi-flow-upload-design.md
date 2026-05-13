# lfx serve: Multi-Flow Startup + Dynamic Upload

**Date:** 2026-05-13  
**Status:** Approved

## Summary

Two related additions to `lfx serve`:

1. **Multi-flow startup** — accept a directory or multiple file arguments at startup, loading each `*.json` flow into a single server.
2. **Dynamic upload** — expose `POST /flows/upload/` so callers can register new flows into a running server at runtime (in-memory only, no persistence).

Single uvicorn worker with asyncio concurrency is retained. Multiple OS-level workers are explicitly out of scope — for LLM-based (I/O-bound) flows, a single event loop handles high concurrency.

---

## CLI Interface

The positional argument changes from `str | None` (single path) to `list[str]` (variadic). Three forms are accepted:

```bash
# Single file (unchanged behaviour)
lfx serve my_flow.json

# Directory — non-recursive scan for *.json files
lfx serve ./flows/

# Multiple explicit files
lfx serve flow1.json flow2.json flow3.json

# Existing single-flow options still work
lfx serve --flow-json '{"nodes": [...]}'
cat flow.json | lfx serve --stdin
```

**Validation rules at startup:**
- Exactly one input source must be given: positional paths, `--flow-json`, or `--stdin` (no mixing).
- Directory must contain at least one `*.json` file, otherwise exit with a clear error.
- Every file must exist, parse as valid JSON, and have `graph.prepare()` succeed. If any file fails, the server does not start — no partial loads.

---

## Architecture

### FlowRegistry

A new `FlowRegistry` class in `serve_app.py` owns the mutable set of loaded flows:

```python
class FlowRegistry:
    def __init__(self) -> None:
        self._flows: dict[str, tuple[Graph, FlowMeta]] = {}

    def add(self, graph: Graph, meta: FlowMeta) -> None: ...
    def get(self, flow_id: str) -> tuple[Graph, FlowMeta] | None: ...
    def list_metas(self) -> list[FlowMeta]: ...
    def remove(self, flow_id: str) -> bool: ...  # reserved for future use
```

The registry is stored on `app.state.registry` and passed into `create_multi_serve_app()`.

### create_multi_serve_app() refactor

**Signature change:**
```python
# Before
def create_multi_serve_app(*, root_dir, graphs: dict[str, Graph], metas: dict[str, FlowMeta], verbose_print)

# After
def create_multi_serve_app(*, registry: FlowRegistry, verbose_print) -> FastAPI
```

The per-flow `APIRouter` loop is removed. Four fixed dispatch routes replace it — each one looks up the registry at request time using `{flow_id}` from the URL path.

### Route table

```
GET  /flows                  → list[FlowMeta]           200
GET  /health                 → {status, flow_count}      200
GET  /flows/{flow_id}/info   → FlowMeta                 200 | 404
POST /flows/{flow_id}/run    → RunResponse               200 | 404
POST /flows/{flow_id}/stream → SSE stream                200 | 404
POST /flows/upload/          → UploadFlowResponse        201
```

Static route `/flows/upload/` is registered before `/{flow_id}` so Starlette resolves it without ambiguity.

All endpoints except `GET /health` require `x-api-key` (header or query param).

---

## Upload Endpoint

`POST /flows/upload/` — request and response shapes mirror the Langflow backend `FlowBase` pattern:

`FlowMeta.relative_path` is set to `"<uploaded>"` for dynamically registered flows (no backing file path exists).

```python
class UploadFlowRequest(BaseModel):
    name: str                       # human-readable title (matches FlowBase.name)
    data: dict                      # raw flow JSON — nodes + edges (matches FlowBase.data)
    description: str | None = None  # optional (matches FlowBase.description)

class UploadFlowResponse(BaseModel):
    id: str             # deterministic UUID5 of flow content
    name: str
    description: str | None
    run_url: str        # /flows/{id}/run
```

**Processing steps:**
1. Parse `data` into a `Graph` via `load_flow_from_json`.
2. Call `graph.prepare()` — returns 422 immediately if the graph is malformed.
3. Generate `flow_id` as UUID5 hashed from `json.dumps(data, sort_keys=True)` (deterministic regardless of key order; same namespace UUID as file-path IDs).
4. Call `registry.add(graph, meta)` — if the ID already exists, it is replaced (idempotent re-upload of the same content).
5. Return `UploadFlowResponse` with status 201.

**Error cases:**
- `data` is not a valid flow structure → 422
- `graph.prepare()` raises → 422 with detail
- Duplicate ID (same `data`) → 201, silently replaces

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Unknown `flow_id` on run/info/stream | 404 `{"error": "flow not found", "flow_id": "..."}` |
| Directory with no `*.json` files | Exit 1 before server starts |
| Any file fails to load at startup | Exit 1 listing failed files |
| `graph.prepare()` fails at startup | Exit 1 |
| Upload with invalid flow JSON | 422 |
| Upload with bad graph structure | 422 |

---

## Files Changed

| File | Change |
|------|--------|
| `src/lfx/src/lfx/cli/_running_commands.py` | `script_path: str \| None` → `script_paths: list[str]`; wire multi-flow path |
| `src/lfx/src/lfx/cli/commands.py` | Directory scan + multi-file loading; populate `FlowRegistry`; pass registry to `create_multi_serve_app` |
| `src/lfx/src/lfx/cli/serve_app.py` | Add `FlowRegistry`; refactor `create_multi_serve_app` to dispatch routes; add `UploadFlowRequest/Response`; add `POST /flows/upload/` |

No new modules. All changes are contained within the existing CLI layer.

---

## Testing

**Unit tests** (new/updated in `tests/unit/cli/`):

- `FlowRegistry`: add, get, list, duplicate-ID replacement, remove
- `create_multi_serve_app`: registry-based dispatch returns 404 for unknown flow_id
- `POST /flows/upload/`: valid flow → 201 + registered; invalid JSON → 422; bad graph → 422; duplicate → 201 replaces
- `GET /flows`: returns all registered flows
- Startup loading: directory with multiple `*.json` files loads all; empty directory exits 1; bad file exits 1

**Existing tests** in `test_serve_app.py` and `test_serve.py`: update to use `FlowRegistry` constructor instead of `graphs`/`metas` dicts.

---

## Out of Scope

- Multiple uvicorn workers (OS processes) — async concurrency is sufficient for I/O-bound flows
- Persisting uploaded flows to disk across server restarts
- `DELETE /flows/{flow_id}` — `remove()` is reserved on `FlowRegistry` but no endpoint is added
- Recursive directory scanning
