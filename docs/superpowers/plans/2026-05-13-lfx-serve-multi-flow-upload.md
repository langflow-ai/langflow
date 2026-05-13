# lfx serve: Multi-Flow Startup + Dynamic Upload — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `lfx serve` to accept a directory or multiple file arguments at startup and expose `POST /flows/upload/` to register new flows into a running server at runtime.

**Architecture:** Replace the static per-flow `APIRouter` loop in `create_multi_serve_app` with a mutable `FlowRegistry` and four fixed dispatch routes. The CLI arg changes from a single `str | None` to `list[str] | None` to accept multiple paths or a directory. Uploaded flows are loaded, prepared, and inserted into the registry (in-memory only).

**Tech Stack:** FastAPI, Pydantic v2, Typer, uvicorn, `lfx.load.load_flow_from_json`, `lfx.graph.Graph`

---

## File Map

| File | What changes |
|------|-------------|
| `src/lfx/src/lfx/cli/serve_app.py` | Add `FlowRegistry`; add `UploadFlowRequest/Response`; refactor `create_multi_serve_app` to registry-based dispatch; add `POST /flows/upload/` |
| `src/lfx/src/lfx/cli/common.py` | Add `flow_id_from_content()` helper |
| `src/lfx/src/lfx/cli/commands.py` | Add `_load_graph_and_meta`, `build_registry_from_directory`, `build_registry_from_paths`; update `serve_command` signature + body |
| `src/lfx/src/lfx/cli/_running_commands.py` | Change `script_path: str \| None` → `script_paths: list[str] \| None` |
| `src/lfx/tests/unit/cli/test_serve_app.py` | Add `TestFlowRegistry`; update `TestCreateServeApp` and `TestServeAppEndpoints` for new signature + routes; add `TestUploadEndpoint` |
| `src/lfx/tests/unit/cli/test_serve.py` | Update `test_create_multi_serve_app_*` calls to use `FlowRegistry`; add multi-flow loading tests |
| `src/lfx/tests/unit/cli/test_common.py` | Add test for `flow_id_from_content` |

---

## Task 1: Add `FlowRegistry` to `serve_app.py`

**Files:**
- Modify: `src/lfx/src/lfx/cli/serve_app.py`
- Test: `src/lfx/tests/unit/cli/test_serve_app.py`

- [ ] **Step 1: Write the failing tests**

Add a new `TestFlowRegistry` class to `test_serve_app.py` (after the existing imports):

```python
from lfx.cli.serve_app import FlowMeta, FlowRegistry, create_multi_serve_app, verify_api_key


class TestFlowRegistry:
    def _make_meta(self, flow_id: str) -> FlowMeta:
        return FlowMeta(id=flow_id, relative_path=f"{flow_id}.json", title=flow_id, description=None)

    def test_add_and_get(self):
        registry = FlowRegistry()
        graph = MagicMock()
        meta = self._make_meta("flow-1")
        registry.add(graph, meta)
        result = registry.get("flow-1")
        assert result is not None
        assert result[0] is graph
        assert result[1] == meta

    def test_get_missing_returns_none(self):
        assert FlowRegistry().get("nonexistent") is None

    def test_list_metas_empty(self):
        assert FlowRegistry().list_metas() == []

    def test_list_metas_multiple(self):
        registry = FlowRegistry()
        graph = MagicMock()
        registry.add(graph, self._make_meta("a"))
        registry.add(graph, self._make_meta("b"))
        ids = {m.id for m in registry.list_metas()}
        assert ids == {"a", "b"}

    def test_duplicate_add_replaces_graph(self):
        registry = FlowRegistry()
        g1, g2 = MagicMock(), MagicMock()
        meta = self._make_meta("flow-1")
        registry.add(g1, meta)
        registry.add(g2, meta)
        assert registry.get("flow-1")[0] is g2

    def test_len(self):
        registry = FlowRegistry()
        assert len(registry) == 0
        registry.add(MagicMock(), self._make_meta("x"))
        assert len(registry) == 1

    def test_remove_existing(self):
        registry = FlowRegistry()
        meta = self._make_meta("flow-1")
        registry.add(MagicMock(), meta)
        assert registry.remove("flow-1") is True
        assert registry.get("flow-1") is None

    def test_remove_nonexistent(self):
        assert FlowRegistry().remove("ghost") is False
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd src/lfx && uv run pytest tests/unit/cli/test_serve_app.py::TestFlowRegistry -v
```

Expected: `ImportError` or `AttributeError` — `FlowRegistry` doesn't exist yet.

- [ ] **Step 3: Add `FlowRegistry` to `serve_app.py`**

Insert after the `ErrorResponse` class (around line 257) in `serve_app.py`:

```python
class FlowRegistry:
    """Mutable in-process registry of loaded flows."""

    def __init__(self) -> None:
        self._flows: dict[str, tuple[Graph, FlowMeta]] = {}

    def add(self, graph: Graph, meta: FlowMeta) -> None:
        self._flows[meta.id] = (graph, meta)

    def get(self, flow_id: str) -> tuple[Graph, FlowMeta] | None:
        return self._flows.get(flow_id)

    def list_metas(self) -> list[FlowMeta]:
        return [meta for _, meta in self._flows.values()]

    def remove(self, flow_id: str) -> bool:
        if flow_id in self._flows:
            del self._flows[flow_id]
            return True
        return False

    def __len__(self) -> int:
        return len(self._flows)
```

- [ ] **Step 4: Run to verify tests pass**

```bash
cd src/lfx && uv run pytest tests/unit/cli/test_serve_app.py::TestFlowRegistry -v
```

Expected: 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/cli/serve_app.py src/lfx/tests/unit/cli/test_serve_app.py
git commit -m "feat(serve): add FlowRegistry for mutable in-process flow management"
```

---

## Task 2: Add `flow_id_from_content` to `common.py`

**Files:**
- Modify: `src/lfx/src/lfx/cli/common.py`
- Test: `src/lfx/tests/unit/cli/test_common.py`

- [ ] **Step 1: Write the failing test**

Add to `test_common.py` after the existing imports (add `flow_id_from_content` to the import list):

```python
from lfx.cli.common import (
    create_verbose_printer,
    execute_graph_with_capture,
    extract_result_data,
    flow_id_from_content,
    flow_id_from_path,
    get_api_key,
    get_best_access_host,
    get_free_port,
    is_port_in_use,
    load_graph_from_path,
)
```

Then add:

```python
class TestFlowIdFromContent:
    def test_deterministic_same_input(self):
        data = {"nodes": [{"id": "n1"}], "edges": []}
        assert flow_id_from_content(data) == flow_id_from_content(data)

    def test_different_content_different_id(self):
        a = {"nodes": [{"id": "n1"}], "edges": []}
        b = {"nodes": [{"id": "n2"}], "edges": []}
        assert flow_id_from_content(a) != flow_id_from_content(b)

    def test_key_order_independent(self):
        a = {"edges": [], "nodes": []}
        b = {"nodes": [], "edges": []}
        assert flow_id_from_content(a) == flow_id_from_content(b)

    def test_returns_uuid_string(self):
        import uuid
        result = flow_id_from_content({"nodes": [], "edges": []})
        uuid.UUID(result)  # raises if not a valid UUID string
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd src/lfx && uv run pytest tests/unit/cli/test_common.py::TestFlowIdFromContent -v
```

Expected: `ImportError` — `flow_id_from_content` doesn't exist yet.

- [ ] **Step 3: Add `flow_id_from_content` to `common.py`**

Add after `flow_id_from_path` (around line 538):

```python
def flow_id_from_content(data: dict) -> str:
    """Generate a deterministic UUID-5 from flow content.

    Uses JSON-serialized content with sorted keys so key-ordering differences
    in the same logical flow map to the same ID.

    Args:
        data: The flow dict (nodes + edges).

    Returns:
        Canonical UUID string (36 chars, including hyphens).
    """
    serialized = json.dumps(data, sort_keys=True)
    return str(uuid.uuid5(_LANGFLOW_NAMESPACE_UUID, serialized))
```

Also add `import json` at the top of `common.py` if not already present (check line 6 — `import json` is already there).

- [ ] **Step 4: Run to verify tests pass**

```bash
cd src/lfx && uv run pytest tests/unit/cli/test_common.py::TestFlowIdFromContent -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/cli/common.py src/lfx/tests/unit/cli/test_common.py
git commit -m "feat(serve): add flow_id_from_content for content-based flow ID generation"
```

---

## Task 3: Refactor `create_multi_serve_app` to registry-based dispatch

**Files:**
- Modify: `src/lfx/src/lfx/cli/serve_app.py`
- Update: `src/lfx/tests/unit/cli/test_serve_app.py`
- Update: `src/lfx/tests/unit/cli/test_serve.py`

This task replaces the `graphs: dict + metas: dict` signature and static per-flow router loop with a `FlowRegistry` + fixed dispatch routes.

- [ ] **Step 1: Update `TestCreateServeApp` tests to use the new signature**

In `test_serve_app.py`, replace the entire `TestCreateServeApp` class:

```python
class TestCreateServeApp:
    """Test FastAPI app creation."""

    @pytest.fixture
    def simple_chat_json(self):
        test_data_dir = Path(__file__).parent.parent.parent / "data"
        json_path = test_data_dir / "simple_chat_no_llm.json"
        with json_path.open() as f:
            return json.load(f)

    @pytest.fixture
    def real_graph(self, simple_chat_json):
        return Graph.from_payload(simple_chat_json, flow_id="00000000-0000-0000-0000-000000000001")

    @pytest.fixture
    def mock_meta(self):
        return FlowMeta(
            id="00000000-0000-0000-0000-000000000001",
            relative_path="test.json",
            title="Test Flow",
            description="A test flow",
        )

    def test_create_multi_serve_app_single_flow(self, real_graph, mock_meta):
        from lfx.cli.serve_app import FlowRegistry
        registry = FlowRegistry()
        registry.add(real_graph, mock_meta)

        app = create_multi_serve_app(registry=registry, verbose_print=Mock())

        routes = [route.path for route in app.routes]
        assert "/health" in routes
        assert "/flows" in routes
        assert "/flows/{flow_id}/run" in routes
        assert "/flows/{flow_id}/info" in routes
        assert "/flows/upload/" in routes

    def test_create_multi_serve_app_multiple_flows(self, real_graph, mock_meta, simple_chat_json):
        from lfx.cli.serve_app import FlowRegistry
        graph2 = Graph.from_payload(simple_chat_json, flow_id="flow-2")
        meta2 = FlowMeta(id="flow-2", relative_path="flow2.json", title="Flow 2", description=None)

        registry = FlowRegistry()
        registry.add(real_graph, mock_meta)
        registry.add(graph2, meta2)

        app = create_multi_serve_app(registry=registry, verbose_print=Mock())

        routes = [route.path for route in app.routes]
        assert "/flows/{flow_id}/run" in routes
        assert "/flows/{flow_id}/info" in routes
        # Single dispatch route covers all flow IDs — no per-flow routes
        assert "/flows/00000000-0000-0000-0000-000000000001/run" not in routes
        assert "/flows/flow-2/run" not in routes
```

- [ ] **Step 2: Update `test_serve.py` tests that call `create_multi_serve_app`**

In `test_serve.py`, replace `test_create_multi_serve_app_single_flow` and `test_create_multi_serve_app_multiple_flows`:

```python
def test_create_multi_serve_app_single_flow(mock_graph, test_flow_meta):
    from lfx.cli.serve_app import FlowRegistry
    registry = FlowRegistry()
    registry.add(mock_graph, test_flow_meta)

    with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}):  # pragma: allowlist secret
        app = create_multi_serve_app(registry=registry, verbose_print=lambda x: None)  # noqa: ARG005
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["flow_count"] == 1

        # No auth → 401
        response = client.post("/flows/test-flow-id/run", json={"input_value": "test"})
        assert response.status_code == 401

        # With auth → 200
        response = client.post(
            "/flows/test-flow-id/run",
            json={"input_value": "test"},
            headers={"x-api-key": "test-key"},
        )
        assert response.status_code == 200


def test_create_multi_serve_app_multiple_flows(mock_graph, test_flow_meta):
    from lfx.cli.serve_app import FlowRegistry
    meta2 = FlowMeta(id="flow-2", relative_path="flow2.json", title="Flow 2", description="Second flow")
    registry = FlowRegistry()
    registry.add(mock_graph, test_flow_meta)
    registry.add(mock_graph, meta2)

    with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}):  # pragma: allowlist secret
        app = create_multi_serve_app(registry=registry, verbose_print=lambda x: None)  # noqa: ARG005
        client = TestClient(app)

        response = client.get("/flows")
        assert response.status_code == 200
        flows = response.json()
        assert len(flows) == 2
        assert any(f["id"] == "test-flow-id" for f in flows)
        assert any(f["id"] == "flow-2" for f in flows)

        response = client.get("/flows/test-flow-id/info", headers={"x-api-key": "test-key"})
        assert response.status_code == 200
        assert response.json()["id"] == "test-flow-id"


def test_create_multi_serve_app_unknown_flow_id_returns_404(mock_graph, test_flow_meta):
    from lfx.cli.serve_app import FlowRegistry
    registry = FlowRegistry()
    registry.add(mock_graph, test_flow_meta)

    with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}):  # pragma: allowlist secret
        app = create_multi_serve_app(registry=registry, verbose_print=lambda x: None)  # noqa: ARG005
        client = TestClient(app)

        response = client.get("/flows/does-not-exist/info", headers={"x-api-key": "test-key"})
        assert response.status_code == 404

        response = client.post(
            "/flows/does-not-exist/run",
            json={"input_value": "test"},
            headers={"x-api-key": "test-key"},
        )
        assert response.status_code == 404
```

- [ ] **Step 3: Run to verify tests fail (expected — old signature still in place)**

```bash
cd src/lfx && uv run pytest tests/unit/cli/test_serve_app.py::TestCreateServeApp tests/unit/cli/test_serve.py::test_create_multi_serve_app_single_flow tests/unit/cli/test_serve.py::test_create_multi_serve_app_multiple_flows tests/unit/cli/test_serve.py::test_create_multi_serve_app_unknown_flow_id_returns_404 -v
```

Expected: `TypeError` — unexpected keyword argument `registry`.

- [ ] **Step 4: Refactor `create_multi_serve_app` in `serve_app.py`**

Add these imports at the top of `serve_app.py` (after existing imports):

```python
import json

from lfx.cli.common import execute_graph_with_capture, extract_result_data, flow_id_from_content, get_api_key
```

Replace the entire `create_multi_serve_app` function (lines 353–555) with:

```python
def create_multi_serve_app(
    *,
    registry: FlowRegistry,
    verbose_print: Callable[[str], None],  # noqa: ARG001
) -> FastAPI:
    """Create a FastAPI app exposing LFX flows via a mutable registry.

    Routes dispatch to ``registry`` at request time, so flows added after
    startup (via ``POST /flows/upload/``) are immediately reachable.
    """
    app = FastAPI(
        title=f"LFX Multi-Flow Server ({len(registry)})",
        description=(
            "Hosts LFX graphs under the `/flows/{{id}}` prefix. "
            "Use `/flows` to list available IDs then POST your input to `/flows/{{id}}/run`. "
            "Use `POST /flows/upload/` to register new flows at runtime."
        ),
        version="1.0.0",
    )
    app.state.registry = registry

    # ------------------------------------------------------------------
    # Global endpoints
    # ------------------------------------------------------------------

    @app.get("/flows", response_model=list[FlowMeta], tags=["info"], summary="List available flows")
    async def list_flows():
        return registry.list_metas()

    @app.get("/health", tags=["info"], summary="Global health check")
    async def global_health():
        return {"status": "healthy", "flow_count": len(registry)}

    # ------------------------------------------------------------------
    # Upload endpoint — registered BEFORE /{flow_id} to avoid shadowing
    # ------------------------------------------------------------------

    @app.post(
        "/flows/upload/",
        response_model=UploadFlowResponse,
        status_code=201,
        tags=["upload"],
        summary="Upload and register a new flow",
        dependencies=[Depends(verify_api_key)],
    )
    async def upload_flow(body: UploadFlowRequest) -> UploadFlowResponse:
        try:
            graph = load_flow_from_json(body.data)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=422, detail=f"Invalid flow data: {exc}") from exc

        try:
            graph.prepare()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=422, detail=f"Flow preparation failed: {exc}") from exc

        flow_id = flow_id_from_content(body.data)
        meta = FlowMeta(
            id=flow_id,
            relative_path="<uploaded>",
            title=body.name,
            description=body.description,
        )
        registry.add(graph, meta)
        return UploadFlowResponse(
            id=flow_id,
            name=body.name,
            description=body.description,
            run_url=f"/flows/{flow_id}/run",
        )

    # ------------------------------------------------------------------
    # Per-flow dispatch routes
    # ------------------------------------------------------------------

    def _get_flow_or_404(flow_id: str) -> tuple[Graph, FlowMeta]:
        result = registry.get(flow_id)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "flow not found", "flow_id": flow_id},
            )
        return result

    @app.get(
        "/flows/{flow_id}/info",
        response_model=FlowMeta,
        tags=["flows"],
        summary="Flow metadata",
        dependencies=[Depends(verify_api_key)],
    )
    async def flow_info(flow_id: str) -> FlowMeta:
        _, meta = _get_flow_or_404(flow_id)
        return meta

    @app.post(
        "/flows/{flow_id}/run",
        response_model=RunResponse,
        responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
        tags=["flows"],
        summary="Execute flow",
        dependencies=[Depends(verify_api_key)],
    )
    async def run_flow(flow_id: str, request: RunRequest) -> RunResponse:
        graph, _ = _get_flow_or_404(flow_id)
        try:
            validate_flow_for_current_settings(graph)
            graph_copy = deepcopy(graph)
            results, logs = await execute_graph_with_capture(
                graph_copy, request.input_value, session_id=request.session_id
            )
            result_data = extract_result_data(results, logs)

            if not result_data.get("success", True):
                error_message = result_data.get("result", result_data.get("text", "No response generated"))
                return RunResponse(
                    result=error_message,
                    success=False,
                    logs=logs or f"Flow execution completed but no valid result was produced.\nResult data: {result_data}",
                    type="error",
                    component=result_data.get("component", ""),
                )
            return RunResponse(
                result=result_data.get("result", result_data.get("text", "")),
                success=result_data.get("success", True),
                logs=logs,
                type=result_data.get("type", "message"),
                component=result_data.get("component", ""),
            )
        except Exception as exc:  # noqa: BLE001
            import traceback
            error_traceback = traceback.format_exc()
            error_message = f"Flow execution failed: {exc!s}"
            logger.error(f"Error running flow {flow_id}: {exc}")
            logger.debug(f"Full traceback for flow {flow_id}:\n{error_traceback}")
            return RunResponse(
                result=error_message,
                success=False,
                logs=f"ERROR: {error_message}\n\nFull traceback:\n{error_traceback}",
                type="error",
                component="",
            )

    @app.post(
        "/flows/{flow_id}/stream",
        response_model=None,
        tags=["flows"],
        summary="Stream flow execution",
        dependencies=[Depends(verify_api_key)],
    )
    async def stream_flow(flow_id: str, request: StreamRequest) -> StreamingResponse:
        graph, meta = _get_flow_or_404(flow_id)
        try:
            validate_flow_for_current_settings(graph)
            from lfx.events.event_manager import create_stream_tokens_event_manager

            asyncio_queue: asyncio.Queue = asyncio.Queue()
            asyncio_queue_client_consumed: asyncio.Queue = asyncio.Queue()
            event_manager = create_stream_tokens_event_manager(queue=asyncio_queue)

            main_task = asyncio.create_task(
                run_flow_generator_for_serve(
                    graph=graph,
                    input_request=request,
                    flow_id=flow_id,
                    event_manager=event_manager,
                    client_consumed_queue=asyncio_queue_client_consumed,
                )
            )

            async def on_disconnect() -> None:
                logger.debug(f"Client disconnected from flow {flow_id}, closing tasks")
                main_task.cancel()

            return StreamingResponse(
                consume_and_yield(asyncio_queue, asyncio_queue_client_consumed),
                background=on_disconnect,
                media_type="text/event-stream",
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Error setting up streaming for flow {flow_id}: {exc}")
            error_message = f"Failed to start streaming: {exc!s}"

            async def error_stream():
                yield f'data: {{"error": "{error_message}", "success": false}}\n\n'

            return StreamingResponse(error_stream(), media_type="text/event-stream")

    return app
```

Also add these new model classes before `create_multi_serve_app` in `serve_app.py` (after `ErrorResponse`):

```python
class UploadFlowRequest(BaseModel):
    name: str = Field(..., description="Human-readable name for the flow (matches FlowBase.name)")
    data: dict = Field(..., description="Raw flow JSON — nodes and edges (matches FlowBase.data)")
    description: str | None = Field(default=None, description="Optional flow description")


class UploadFlowResponse(BaseModel):
    id: str = Field(..., description="Deterministic UUID5 of flow content")
    name: str
    description: str | None
    run_url: str = Field(..., description="Endpoint to POST run requests, e.g. /flows/{id}/run")
```

Add the missing import at the top of `serve_app.py`:

```python
from lfx.cli.common import execute_graph_with_capture, extract_result_data, flow_id_from_content, get_api_key
from lfx.load import load_flow_from_json
```

- [ ] **Step 5: Run to verify updated tests pass**

```bash
cd src/lfx && uv run pytest tests/unit/cli/test_serve_app.py::TestCreateServeApp tests/unit/cli/test_serve.py::test_create_multi_serve_app_single_flow tests/unit/cli/test_serve.py::test_create_multi_serve_app_multiple_flows tests/unit/cli/test_serve.py::test_create_multi_serve_app_unknown_flow_id_returns_404 -v
```

Expected: all PASS.

- [ ] **Step 6: Run the full serve test suite to check for regressions**

```bash
cd src/lfx && uv run pytest tests/unit/cli/test_serve_app.py tests/unit/cli/test_serve.py -v
```

Fix any failures before proceeding (they will be tests still using the old `graphs=`/`metas=` kwargs).

- [ ] **Step 7: Commit**

```bash
git add src/lfx/src/lfx/cli/serve_app.py src/lfx/tests/unit/cli/test_serve_app.py src/lfx/tests/unit/cli/test_serve.py
git commit -m "feat(serve): refactor create_multi_serve_app to registry-based dispatch routes"
```

---

## Task 4: Add `POST /flows/upload/` tests

**Files:**
- Test: `src/lfx/tests/unit/cli/test_serve_app.py`

The upload endpoint code was already added in Task 3. This task adds the tests.

- [ ] **Step 1: Write upload endpoint tests**

Add `TestUploadEndpoint` class to `test_serve_app.py`:

```python
class TestUploadEndpoint:
    """Tests for POST /flows/upload/."""

    @pytest.fixture
    def app_with_empty_registry(self):
        from lfx.cli.serve_app import FlowRegistry
        registry = FlowRegistry()
        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}):  # pragma: allowlist secret
            return create_multi_serve_app(registry=registry, verbose_print=lambda x: None)  # noqa: ARG005

    @pytest.fixture
    def valid_flow_data(self):
        test_data_dir = Path(__file__).parent.parent.parent / "data"
        json_path = test_data_dir / "simple_chat_no_llm.json"
        with json_path.open() as f:
            return json.load(f)

    def test_upload_valid_flow(self, app_with_empty_registry, valid_flow_data):
        client = TestClient(app_with_empty_registry)
        response = client.post(
            "/flows/upload/",
            json={"name": "My Uploaded Flow", "data": valid_flow_data},
            headers={"x-api-key": "test-key"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "My Uploaded Flow"
        assert body["run_url"].startswith("/flows/")
        assert body["run_url"].endswith("/run")
        assert "id" in body

    def test_upload_requires_auth(self, app_with_empty_registry, valid_flow_data):
        client = TestClient(app_with_empty_registry)
        response = client.post(
            "/flows/upload/",
            json={"name": "Flow", "data": valid_flow_data},
        )
        assert response.status_code == 401

    def test_upload_invalid_flow_data_returns_422(self, app_with_empty_registry):
        client = TestClient(app_with_empty_registry)
        with patch("lfx.cli.serve_app.load_flow_from_json", side_effect=ValueError("bad flow")):
            response = client.post(
                "/flows/upload/",
                json={"name": "Bad Flow", "data": {"nodes": [], "edges": []}},
                headers={"x-api-key": "test-key"},
            )
        assert response.status_code == 422
        assert "bad flow" in response.json()["detail"]

    def test_upload_prepare_failure_returns_422(self, app_with_empty_registry):
        client = TestClient(app_with_empty_registry)
        mock_graph = MagicMock()
        mock_graph.prepare.side_effect = RuntimeError("prepare failed")
        with patch("lfx.cli.serve_app.load_flow_from_json", return_value=mock_graph):
            response = client.post(
                "/flows/upload/",
                json={"name": "Bad Flow", "data": {"nodes": [], "edges": []}},
                headers={"x-api-key": "test-key"},
            )
        assert response.status_code == 422
        assert "prepare failed" in response.json()["detail"]

    def test_upload_flow_is_immediately_runnable(self, app_with_empty_registry, valid_flow_data):
        client = TestClient(app_with_empty_registry)
        # Upload it
        upload_resp = client.post(
            "/flows/upload/",
            json={"name": "Runnable Flow", "data": valid_flow_data},
            headers={"x-api-key": "test-key"},
        )
        assert upload_resp.status_code == 201
        flow_id = upload_resp.json()["id"]

        # Confirm it appears in /flows listing
        list_resp = client.get("/flows")
        assert any(f["id"] == flow_id for f in list_resp.json())

    def test_upload_idempotent_same_data(self, app_with_empty_registry, valid_flow_data):
        client = TestClient(app_with_empty_registry)
        r1 = client.post(
            "/flows/upload/",
            json={"name": "Flow A", "data": valid_flow_data},
            headers={"x-api-key": "test-key"},
        )
        r2 = client.post(
            "/flows/upload/",
            json={"name": "Flow B", "data": valid_flow_data},
            headers={"x-api-key": "test-key"},
        )
        assert r1.status_code == 201
        assert r2.status_code == 201
        # Same data → same ID; listing should still have exactly one entry with that ID
        assert r1.json()["id"] == r2.json()["id"]
        flows = client.get("/flows").json()
        ids = [f["id"] for f in flows]
        assert ids.count(r1.json()["id"]) == 1

    def test_upload_with_description(self, app_with_empty_registry, valid_flow_data):
        client = TestClient(app_with_empty_registry)
        response = client.post(
            "/flows/upload/",
            json={"name": "Flow", "data": valid_flow_data, "description": "my desc"},
            headers={"x-api-key": "test-key"},
        )
        assert response.status_code == 201
        assert response.json()["description"] == "my desc"
```

- [ ] **Step 2: Run the upload tests**

```bash
cd src/lfx && uv run pytest tests/unit/cli/test_serve_app.py::TestUploadEndpoint -v
```

Expected: all PASS (the implementation was added in Task 3).

- [ ] **Step 3: Commit**

```bash
git add src/lfx/tests/unit/cli/test_serve_app.py
git commit -m "test(serve): add upload endpoint tests"
```

---

## Task 5: Add multi-flow loading helpers to `commands.py`

**Files:**
- Modify: `src/lfx/src/lfx/cli/commands.py`
- Test: `src/lfx/tests/unit/cli/test_serve.py`

- [ ] **Step 1: Write failing tests**

Add to `test_serve.py`:

```python
import asyncio
from lfx.cli.serve_app import FlowRegistry


class TestBuildRegistryFromDirectory:
    def test_loads_all_json_files(self, tmp_path):
        from lfx.cli.commands import build_registry_from_directory

        flow_data = {"nodes": [], "edges": []}
        (tmp_path / "a.json").write_text(json.dumps(flow_data))
        (tmp_path / "b.json").write_text(json.dumps(flow_data))

        mock_graph = MagicMock()
        mock_graph.prepare = MagicMock()
        mock_graph.flow_id = None

        with patch("lfx.cli.commands.load_graph_from_path", return_value=mock_graph):
            registry = asyncio.get_event_loop().run_until_complete(
                build_registry_from_directory(tmp_path, lambda x: None, check_variables=False)
            )

        assert len(registry) == 2

    def test_empty_directory_raises(self, tmp_path):
        from lfx.cli.commands import build_registry_from_directory

        with pytest.raises(ValueError, match="No .json files found"):
            asyncio.get_event_loop().run_until_complete(
                build_registry_from_directory(tmp_path, lambda x: None, check_variables=False)
            )

    def test_non_json_files_ignored(self, tmp_path):
        from lfx.cli.commands import build_registry_from_directory

        (tmp_path / "notes.txt").write_text("ignore me")
        flow_data = {"nodes": [], "edges": []}
        (tmp_path / "flow.json").write_text(json.dumps(flow_data))

        mock_graph = MagicMock()
        mock_graph.prepare = MagicMock()
        mock_graph.flow_id = None

        with patch("lfx.cli.commands.load_graph_from_path", return_value=mock_graph):
            registry = asyncio.get_event_loop().run_until_complete(
                build_registry_from_directory(tmp_path, lambda x: None, check_variables=False)
            )

        assert len(registry) == 1

    def test_failed_file_raises_with_filename(self, tmp_path):
        from lfx.cli.commands import build_registry_from_directory

        (tmp_path / "bad.json").write_text('{"nodes": [], "edges": []}')

        with patch("lfx.cli.commands.load_graph_from_path", side_effect=ValueError("corrupt")):
            with pytest.raises(ValueError, match="bad.json"):
                asyncio.get_event_loop().run_until_complete(
                    build_registry_from_directory(tmp_path, lambda x: None, check_variables=False)
                )


class TestBuildRegistryFromPaths:
    def test_loads_explicit_paths(self, tmp_path):
        from lfx.cli.commands import build_registry_from_paths

        flow_data = {"nodes": [], "edges": []}
        p1 = tmp_path / "flow1.json"
        p2 = tmp_path / "flow2.json"
        p1.write_text(json.dumps(flow_data))
        p2.write_text(json.dumps(flow_data))

        mock_graph = MagicMock()
        mock_graph.prepare = MagicMock()
        mock_graph.flow_id = None

        with patch("lfx.cli.commands.load_graph_from_path", return_value=mock_graph):
            registry = asyncio.get_event_loop().run_until_complete(
                build_registry_from_paths([p1, p2], lambda x: None, check_variables=False)
            )

        assert len(registry) == 2

    def test_failed_path_raises_with_filename(self, tmp_path):
        from lfx.cli.commands import build_registry_from_paths

        p = tmp_path / "bad.json"
        p.write_text('{"nodes": [], "edges": []}')

        with patch("lfx.cli.commands.load_graph_from_path", side_effect=ValueError("oops")):
            with pytest.raises(ValueError, match="bad.json"):
                asyncio.get_event_loop().run_until_complete(
                    build_registry_from_paths([p], lambda x: None, check_variables=False)
                )
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd src/lfx && uv run pytest tests/unit/cli/test_serve.py::TestBuildRegistryFromDirectory tests/unit/cli/test_serve.py::TestBuildRegistryFromPaths -v
```

Expected: `ImportError` — helpers don't exist yet.

- [ ] **Step 3: Add helpers to `commands.py`**

Add these imports at the top of `commands.py` (the `from lfx.cli.serve_app import ...` line):

```python
from lfx.cli.serve_app import FlowMeta, FlowRegistry, create_multi_serve_app
```

Then add these three async helpers after `serve_command` (before the end of the module):

```python
async def _load_graph_and_meta(
    path: Path,
    root_dir: Path,
    verbose_print,
    *,
    check_variables: bool,
) -> tuple:
    """Load and prepare one graph, returning (graph, FlowMeta)."""
    graph = await load_graph_from_path(path, path.suffix, verbose_print, verbose=False)
    graph.prepare()
    if check_variables:
        from lfx.cli.validation import validate_global_variables_for_env

        errors = validate_global_variables_for_env(graph)
        if errors:
            msg = f"Global variable validation failed for {path.name}: {'; '.join(errors)}"
            raise ValueError(msg)
    flow_id = flow_id_from_path(path, root_dir)
    graph.flow_id = flow_id
    meta = FlowMeta(
        id=flow_id,
        relative_path=str(path.relative_to(root_dir)),
        title=path.stem,
        description=None,
    )
    return graph, meta


async def build_registry_from_directory(
    dir_path: Path,
    verbose_print,
    *,
    check_variables: bool,
) -> FlowRegistry:
    """Build a FlowRegistry by scanning *dir_path* for ``*.json`` files (non-recursive)."""
    json_files = sorted(dir_path.glob("*.json"))
    if not json_files:
        msg = f"No .json files found in directory: {dir_path}"
        raise ValueError(msg)

    registry = FlowRegistry()
    errors: list[str] = []
    for path in json_files:
        try:
            graph, meta = await _load_graph_and_meta(path, dir_path, verbose_print, check_variables=check_variables)
            registry.add(graph, meta)
            verbose_print(f"✓ Loaded flow '{meta.title}' (id={meta.id})")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path.name}: {exc}")

    if errors:
        msg = "Failed to load flows:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ValueError(msg)

    return registry


async def build_registry_from_paths(
    paths: list[Path],
    verbose_print,
    *,
    check_variables: bool,
) -> FlowRegistry:
    """Build a FlowRegistry from an explicit list of ``*.json`` paths."""
    registry = FlowRegistry()
    errors: list[str] = []
    for path in paths:
        try:
            graph, meta = await _load_graph_and_meta(path, path.parent, verbose_print, check_variables=check_variables)
            registry.add(graph, meta)
            verbose_print(f"✓ Loaded flow '{meta.title}' (id={meta.id})")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path.name}: {exc}")

    if errors:
        msg = "Failed to load flows:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ValueError(msg)

    return registry
```

Also update the existing `from lfx.cli.common import ...` line in `commands.py` to include `flow_id_from_path`:

```python
from lfx.cli.common import (
    create_verbose_printer,
    flow_id_from_path,
    get_api_key,
    get_best_access_host,
    get_free_port,
    is_port_in_use,
    load_graph_from_path,
)
```

- [ ] **Step 4: Run to verify tests pass**

```bash
cd src/lfx && uv run pytest tests/unit/cli/test_serve.py::TestBuildRegistryFromDirectory tests/unit/cli/test_serve.py::TestBuildRegistryFromPaths -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/cli/commands.py src/lfx/tests/unit/cli/test_serve.py
git commit -m "feat(serve): add build_registry_from_directory and build_registry_from_paths helpers"
```

---

## Task 6: Update CLI arg and `serve_command` to wire everything together

**Files:**
- Modify: `src/lfx/src/lfx/cli/_running_commands.py`
- Modify: `src/lfx/src/lfx/cli/commands.py`
- Test: `src/lfx/tests/unit/cli/test_serve.py`

- [ ] **Step 1: Write failing tests for multi-path CLI wiring**

Add to `test_serve.py`:

```python
class TestServeCommandMultiFlow:
    def test_serve_command_with_directory(self, tmp_path):
        from lfx.cli.commands import serve_command

        flow_data = {"nodes": [], "edges": []}
        (tmp_path / "flow1.json").write_text(json.dumps(flow_data))
        (tmp_path / "flow2.json").write_text(json.dumps(flow_data))

        mock_graph = MagicMock()
        mock_graph.prepare = MagicMock()
        mock_graph.flow_id = None
        mock_graph.nodes = {}
        mock_graph.edges = []

        with (
            patch("lfx.cli.commands.load_graph_from_path", return_value=mock_graph),
            patch("lfx.cli.commands.uvicorn.Server.serve", new=AsyncMock(return_value=None)),
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),  # pragma: allowlist secret
        ):
            import typer
            from typer.testing import CliRunner

            app = typer.Typer()
            app.command()(serve_command)
            runner = CliRunner()
            result = runner.invoke(app, [str(tmp_path)])

        assert result.exit_code == 0, result.output

    def test_serve_command_with_multiple_files(self, tmp_path):
        from lfx.cli.commands import serve_command

        flow_data = {"nodes": [], "edges": []}
        p1 = tmp_path / "flow1.json"
        p2 = tmp_path / "flow2.json"
        p1.write_text(json.dumps(flow_data))
        p2.write_text(json.dumps(flow_data))

        mock_graph = MagicMock()
        mock_graph.prepare = MagicMock()
        mock_graph.flow_id = None
        mock_graph.nodes = {}
        mock_graph.edges = []

        with (
            patch("lfx.cli.commands.load_graph_from_path", return_value=mock_graph),
            patch("lfx.cli.commands.uvicorn.Server.serve", new=AsyncMock(return_value=None)),
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),  # pragma: allowlist secret
        ):
            import typer
            from typer.testing import CliRunner

            app = typer.Typer()
            app.command()(serve_command)
            runner = CliRunner()
            result = runner.invoke(app, [str(p1), str(p2)])

        assert result.exit_code == 0, result.output

    def test_serve_command_empty_directory_exits_nonzero(self, tmp_path):
        from lfx.cli.commands import serve_command

        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}):  # pragma: allowlist secret
            import typer
            from typer.testing import CliRunner

            app = typer.Typer()
            app.command()(serve_command)
            runner = CliRunner()
            result = runner.invoke(app, [str(tmp_path)])

        assert result.exit_code != 0
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd src/lfx && uv run pytest tests/unit/cli/test_serve.py::TestServeCommandMultiFlow -v
```

Expected: `TypeError` — `serve_command` still takes `script_path: str | None`.

- [ ] **Step 3: Update `_running_commands.py` — change the CLI argument**

Replace the `serve_command_wrapper` function's first argument and its delegation:

```python
@app.command(name="serve", help="Serve a flow as an API", no_args_is_help=True, rich_help_panel="Running")
def serve_command_wrapper(
    script_paths: list[str] | None = typer.Argument(
        default=None,
        help=(
            "Path(s) to JSON flow file(s) (.json) or a directory containing .json files. "
            "Optional when using --flow-json or --stdin."
        ),
    ),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind the server to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind the server to"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show diagnostic output and execution details"),
    env_file: str | None = typer.Option(
        None,
        "--env-file",
        help="Path to the .env file containing environment variables",
    ),
    log_level: str = typer.Option(
        "warning",
        "--log-level",
        help="Logging level. One of: debug, info, warning, error, critical",
    ),
    flow_json: str | None = typer.Option(
        None,
        "--flow-json",
        help="Inline JSON flow content as a string (alternative to script_paths)",
    ),
    *,
    stdin: bool = typer.Option(
        False,
        "--stdin",
        help="Read JSON flow content from stdin (alternative to script_paths)",
    ),
    check_variables: bool = typer.Option(
        True,
        "--check-variables/--no-check-variables",
        help="Check global variables for environment compatibility",
    ),
) -> None:
    """Serve LFX flows as a web API (lazy-loaded)."""
    from pathlib import Path

    from lfx.cli.commands import serve_command

    env_file_path = Path(env_file) if env_file else None

    serve_command(
        script_paths=script_paths,
        host=host,
        port=port,
        verbose=verbose,
        env_file=env_file_path,
        log_level=log_level,
        flow_json=flow_json,
        stdin=stdin,
        check_variables=check_variables,
    )
```

- [ ] **Step 4: Update `serve_command` in `commands.py`**

Replace the function signature and body. The new `serve_command` handles three input paths: `--flow-json`, `--stdin`, and `script_paths` (file(s) or directory). Replace the function definition:

```python
@partial(syncify, raise_sync_error=False)
async def serve_command(
    script_paths: list[str] | None = None,
    host: str = "127.0.0.1",
    port: int = 8000,
    verbose: bool = False,  # noqa: FBT001, FBT003
    env_file: Path | None = None,
    log_level: str = "warning",
    flow_json: str | None = None,
    *,
    stdin: bool = False,  # noqa: FBT003
    check_variables: bool = True,  # noqa: FBT003
) -> None:
    """Serve LFX flows as a web API."""
    from lfx.log.logger import configure, logger

    configure(log_level=log_level)
    verbose_print = create_verbose_printer(verbose=verbose)

    # Validate exactly one input source
    has_paths = bool(script_paths)
    input_sources = [has_paths, flow_json is not None, stdin]
    if sum(input_sources) != 1:
        if sum(input_sources) == 0:
            typer.echo("Error: Must provide either path(s)/directory, --flow-json, or --stdin", err=True)
        else:
            typer.echo("Error: Cannot combine path(s), --flow-json, and --stdin. Choose exactly one.", err=True)
        raise typer.Exit(1)

    if env_file:
        if not env_file.exists():
            typer.echo(f"Error: Environment file '{env_file}' does not exist.", err=True)
            raise typer.Exit(1)
        verbose_print(f"Loading environment variables from: {env_file}")
        load_dotenv(env_file)

    try:
        api_key = get_api_key()
        verbose_print("✓ LANGFLOW_API_KEY is configured")
    except ValueError as e:
        typer.echo(f"✗ {e}", err=True)
        typer.echo("Set the LANGFLOW_API_KEY environment variable before serving.", err=True)
        raise typer.Exit(1) from e

    valid_log_levels = {"debug", "info", "warning", "error", "critical"}
    if log_level.lower() not in valid_log_levels:
        typer.echo(f"Error: Invalid log level '{log_level}'. Must be one of: {', '.join(sorted(valid_log_levels))}", err=True)
        raise typer.Exit(1)

    os.environ["LANGFLOW_PRETTY_LOGS"] = "false"
    configure(log_level=log_level)

    temp_file_to_cleanup: str | None = None

    try:
        # ----------------------------------------------------------------
        # Build the FlowRegistry from the input source
        # ----------------------------------------------------------------
        if flow_json is not None:
            try:
                json_data = json.loads(flow_json)
            except json.JSONDecodeError as e:
                typer.echo(f"Error: Invalid JSON content: {e}", err=True)
                raise typer.Exit(1) from e
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
                json.dump(json_data, tmp, indent=2)
                temp_file_to_cleanup = tmp.name
            paths = [Path(temp_file_to_cleanup)]
            source_display = "inline JSON"

        elif stdin:
            stdin_content = sys.stdin.read().strip()
            if not stdin_content:
                typer.echo("Error: No content received from stdin", err=True)
                raise typer.Exit(1)
            try:
                json_data = json.loads(stdin_content)
            except json.JSONDecodeError as e:
                typer.echo(f"Error: Invalid JSON content from stdin: {e}", err=True)
                raise typer.Exit(1) from e
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
                json.dump(json_data, tmp, indent=2)
                temp_file_to_cleanup = tmp.name
            paths = [Path(temp_file_to_cleanup)]
            source_display = "stdin"

        else:
            # script_paths is a non-empty list here (validated above)
            resolved = [Path(p).resolve() for p in script_paths]  # type: ignore[union-attr]

            # Check for non-existent paths before any loading
            missing = [p for p in resolved if not p.exists()]
            if missing:
                for m in missing:
                    typer.echo(f"Error: Path '{m}' does not exist.", err=True)
                raise typer.Exit(1)

            if len(resolved) == 1 and resolved[0].is_dir():
                # Directory mode
                dir_path = resolved[0]
                source_display = str(dir_path)
                try:
                    registry = await build_registry_from_directory(
                        dir_path, verbose_print, check_variables=check_variables
                    )
                except ValueError as e:
                    typer.echo(f"Error: {e}", err=True)
                    raise typer.Exit(1) from e
                verbose_print(f"✓ Loaded {len(registry)} flow(s) from directory {dir_path}")
                # Skip the path-based loading below
                paths = []
                source_display = str(dir_path)
            else:
                # One or more explicit file paths
                non_json = [p for p in resolved if p.suffix != ".json"]
                if non_json:
                    for p in non_json:
                        typer.echo(f"Error: '{p}' is not a .json file.", err=True)
                    raise typer.Exit(1)
                paths = resolved
                source_display = ", ".join(p.name for p in paths)

        # Load from paths (single file via --flow-json/--stdin, or multiple explicit files)
        if paths:
            try:
                registry = await build_registry_from_paths(
                    paths, verbose_print, check_variables=check_variables
                )
            except ValueError as e:
                typer.echo(f"Error: {e}", err=True)
                raise typer.Exit(1) from e

        # ----------------------------------------------------------------
        # Start the server
        # ----------------------------------------------------------------
        if is_port_in_use(port, host):
            port = get_free_port(port)
            verbose_print(f"Port in use; using {port} instead")

        serve_app = create_multi_serve_app(registry=registry, verbose_print=verbose_print)
        verbose_print("🚀 Starting server...")

        protocol = "http"
        access_host = get_best_access_host(host)
        masked_key = f"{api_key[:API_KEY_MASK_LENGTH]}..." if len(api_key) > API_KEY_MASK_LENGTH else "***"

        console.print()
        console.print(
            Panel.fit(
                f"[bold green]🎯 LFX Server Started![/bold green]\n\n"
                f"[bold]Source:[/bold] {source_display}\n"
                f"[bold]Flows:[/bold] {len(registry)}\n"
                f"[bold]Server:[/bold] {protocol}://{access_host}:{port}\n"
                f"[bold]API Key:[/bold] {masked_key}\n\n"
                f"[dim]List flows:[/dim]\n"
                f"[blue]{protocol}://{access_host}:{port}/flows[/blue]\n\n"
                f"[dim]Upload new flow:[/dim]\n"
                f"[blue]POST {protocol}://{access_host}:{port}/flows/upload/[/blue]\n\n"
                f"[dim]Run a flow:[/dim]\n"
                f"[blue]POST {protocol}://{access_host}:{port}/flows/{{flow_id}}/run[/blue]",
                title="[bold blue]LFX Server[/bold blue]",
                border_style="blue",
            )
        )
        console.print()

        try:
            config = uvicorn.Config(serve_app, host=host, port=port, log_level=log_level)
            server = uvicorn.Server(config)
            await server.serve()
        except KeyboardInterrupt:
            verbose_print("\n👋 Server stopped")
            raise typer.Exit(0) from None
        except Exception as e:
            verbose_print(f"✗ Failed to start server: {e}")
            raise typer.Exit(1) from e

    finally:
        if temp_file_to_cleanup:
            try:
                Path(temp_file_to_cleanup).unlink()
            except OSError:
                pass
```

Also update `commands.py` imports to include the new helpers:

```python
from lfx.cli.commands import (  # self-references removed — just ensure these are in the module
    build_registry_from_directory,
    build_registry_from_paths,
)
```

These are defined in the same file, so no additional import line is needed.

- [ ] **Step 5: Run to verify new tests pass**

```bash
cd src/lfx && uv run pytest tests/unit/cli/test_serve.py::TestServeCommandMultiFlow -v
```

Expected: all PASS.

- [ ] **Step 6: Run full test suite for the serve module**

```bash
cd src/lfx && uv run pytest tests/unit/cli/test_serve_app.py tests/unit/cli/test_serve.py tests/unit/cli/test_common.py -v
```

Fix any remaining failures.

- [ ] **Step 7: Commit**

```bash
git add src/lfx/src/lfx/cli/_running_commands.py src/lfx/src/lfx/cli/commands.py src/lfx/tests/unit/cli/test_serve.py
git commit -m "feat(serve): accept directory and multiple file paths at startup; wire registry to serve_command"
```

---

## Self-Review Checklist

- [x] **Spec coverage:**
  - Multi-flow startup (directory) → Task 5/6 `build_registry_from_directory`
  - Multi-flow startup (multiple files) → Task 5/6 `build_registry_from_paths`
  - `POST /flows/upload/` → Task 3/4
  - `FlowMeta.relative_path = "<uploaded>"` for uploads → Task 3, `upload_flow` handler
  - UUID5 from `json.dumps(data, sort_keys=True)` → Task 2 `flow_id_from_content`
  - Auth on upload endpoint → Task 4 `test_upload_requires_auth`
  - 404 for unknown `flow_id` → Task 3 routes + Task 3 tests
  - Empty directory exits 1 → Task 6 `test_serve_command_empty_directory_exits_nonzero`
  - Bad file at startup exits 1 → Task 5 `test_failed_file_raises_with_filename`

- [x] **Type consistency:** `FlowRegistry` methods match usage throughout — `add(graph, meta)`, `get(flow_id)`, `list_metas()`, `__len__()`.

- [x] **No placeholders:** All code blocks are complete.
