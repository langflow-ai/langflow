from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langflow.api.utils.core import extract_global_variables_from_headers
from langflow.api.v1 import mcp_utils
from langflow.helpers import flow as flow_helpers
from lfx.interface.components import component_cache


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class FakeSession:
    def __init__(self, flows, user_files):
        self._flows = flows
        self._user_files = user_files

    async def exec(self, stmt):
        entity = stmt.column_descriptions[0].get("entity") if stmt.column_descriptions else None
        entity_name = getattr(entity, "__name__", None)
        if entity_name == "Flow":
            return FakeResult(self._flows)
        if entity_name == "File":
            return FakeResult(self._user_files)
        return FakeResult([])


class FakeSessionContext:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeStorageService:
    def __init__(self, files_by_flow, file_bytes: dict[str, bytes] | None = None):
        self._files_by_flow = files_by_flow
        self._file_bytes = file_bytes or {}

    async def list_files(self, flow_id: str):
        return self._files_by_flow.get(flow_id, [])

    async def get_file(self, flow_id: str, file_name: str) -> bytes:
        key = f"{flow_id}/{file_name}"
        if key not in self._file_bytes:
            msg = f"File {file_name} not found in flow {flow_id}"
            raise FileNotFoundError(msg)
        return self._file_bytes[key]


@pytest.mark.asyncio
async def test_handle_list_resources_includes_flow_and_user_files(monkeypatch):
    user_id = "user-123"
    flow_id = "flow-456"

    flows = [SimpleNamespace(id=flow_id, name="Flow Node")]
    user_files = [
        SimpleNamespace(
            name="summary.pdf",
            path=f"{user_id}/uploaded-summary.pdf",
            provider="File Manager",
        )
    ]

    fake_session = FakeSession(flows=flows, user_files=user_files)
    storage_service = FakeStorageService({flow_id: ["flow-doc.docx"]})

    monkeypatch.setattr(mcp_utils, "session_scope", lambda: FakeSessionContext(fake_session))
    monkeypatch.setattr(mcp_utils, "get_storage_service", lambda: storage_service)
    monkeypatch.setattr(
        mcp_utils,
        "get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(host="localhost", port=4000)),
    )

    token = mcp_utils.current_user_ctx.set(SimpleNamespace(id=user_id))
    try:
        resources = await mcp_utils.handle_list_resources()
    finally:
        mcp_utils.current_user_ctx.reset(token)

    uris = {str(resource.uri) for resource in resources}
    assert f"http://localhost:4000/api/v1/files/download/{flow_id}/flow-doc.docx" in uris
    assert f"http://localhost:4000/api/v1/files/download/{user_id}/uploaded-summary.pdf" in uris


@pytest.mark.asyncio
async def test_handle_list_tools_skips_blocked_custom_flows(monkeypatch):
    blocked_flow = SimpleNamespace(
        id="flow-1",
        user_id="user-1",
        name="Blocked Flow",
        description="Contains custom code",
        data={
            "nodes": [
                {
                    "id": "node-1",
                    "data": {
                        "id": "node-1",
                        "type": "TotallyCustom",
                        "node": {
                            "display_name": "Blocked Node",
                            "template": {
                                "code": {"value": "print('blocked')"},
                            },
                        },
                    },
                }
            ],
            "edges": [],
        },
    )
    fake_session = FakeSession(flows=[blocked_flow], user_files=[])

    monkeypatch.setattr(mcp_utils, "session_scope", lambda: FakeSessionContext(fake_session))
    monkeypatch.setattr(
        "lfx.services.deps.get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(allow_custom_components=False)),
    )
    monkeypatch.setattr(component_cache, "type_to_current_hash", {"ChatInput": "known-hash"})
    monkeypatch.setattr(component_cache, "all_types_dict", None)

    token = mcp_utils.current_user_ctx.set(SimpleNamespace(id="user-1"))
    try:
        tools = await mcp_utils.handle_list_tools()
    finally:
        mcp_utils.current_user_ctx.reset(token)

    assert tools == []


class TestExtractGlobalVariablesFromHeaders:
    """Unit tests for ``extract_global_variables_from_headers``.

    Covers the MCP auth-header propagation fix (issue #12529): ``x-api-key``
    and ``authorization`` should be captured under their lowercase names when
    (and only when) ``include_auth_headers=True`` is passed. The default
    behavior must remain backwards-compatible for non-MCP routes, where
    ``x-api-key`` is Langflow's own auth key and must not leak into the graph
    context.
    """

    def test_langflow_global_var_prefix_still_extracted(self):
        """Regression guard: ``X-LANGFLOW-GLOBAL-VAR-*`` extraction is preserved."""
        headers = {
            "X-LANGFLOW-GLOBAL-VAR-API-KEY": "secret-value",
            "X-LANGFLOW-GLOBAL-VAR-DB-URL": "postgres://host/db",
            "Content-Type": "application/json",
        }

        result = extract_global_variables_from_headers(headers)

        assert result == {"API-KEY": "secret-value", "DB-URL": "postgres://host/db"}

    def test_auth_headers_not_extracted_by_default(self):
        """Non-MCP call sites: ``x-api-key`` / ``authorization`` must not leak through."""
        headers = {
            "x-api-key": "langflow-auth-key",
            "authorization": "Bearer token",
            "X-LANGFLOW-GLOBAL-VAR-MY-VAR": "value",
        }

        result = extract_global_variables_from_headers(headers)

        assert "x-api-key" not in result
        assert "authorization" not in result
        assert result == {"MY-VAR": "value"}

    def test_auth_headers_extracted_under_lowercase_when_opted_in(self):
        """MCP call sites: lowercase auth headers are captured when opted in."""
        headers = {
            "x-api-key": "api-key-value",
            "authorization": "Bearer jwt-token",
        }

        result = extract_global_variables_from_headers(headers, include_auth_headers=True)

        assert result == {"x-api-key": "api-key-value", "authorization": "Bearer jwt-token"}

    def test_auth_header_matching_is_case_insensitive(self):
        """Headers with mixed or uppercase casing still match (e.g. ``X-Api-Key``, ``AUTHORIZATION``)."""
        headers = {
            "X-Api-Key": "mixed-case-value",
            "AUTHORIZATION": "Bearer UPPER",
        }

        result = extract_global_variables_from_headers(headers, include_auth_headers=True)

        assert result == {"x-api-key": "mixed-case-value", "authorization": "Bearer UPPER"}

    def test_both_categories_extracted_together(self):
        """``X-LANGFLOW-GLOBAL-VAR-*`` and auth headers coexist when opted in."""
        headers = {
            "X-LANGFLOW-GLOBAL-VAR-API-KEY": "global-secret",
            "x-api-key": "incoming-mcp-key",
            "Authorization": "Bearer mcp-token",
            "Content-Type": "application/json",
        }

        result = extract_global_variables_from_headers(headers, include_auth_headers=True)

        assert result == {
            "API-KEY": "global-secret",
            "x-api-key": "incoming-mcp-key",
            "authorization": "Bearer mcp-token",
        }


# ============================================================================
# PVR0754098 regression tests — MCP path traversal and cross-user disclosure.
# ============================================================================


@pytest.mark.asyncio
async def test_handle_list_resources_requires_current_user(monkeypatch):
    """Without a user context, the global server must not enumerate any flows."""
    flows = [SimpleNamespace(id="flow-attacker-saw", name="Leaked Flow")]
    fake_session = FakeSession(flows=flows, user_files=[])
    storage_service = FakeStorageService({"flow-attacker-saw": ["leaked.txt"]})

    monkeypatch.setattr(mcp_utils, "session_scope", lambda: FakeSessionContext(fake_session))
    monkeypatch.setattr(mcp_utils, "get_storage_service", lambda: storage_service)
    monkeypatch.setattr(
        mcp_utils,
        "get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(host="localhost", port=4000)),
    )

    # Intentionally no user context set.
    resources = await mcp_utils.handle_list_resources()
    assert resources == []


@pytest.mark.asyncio
async def test_handle_read_resource_rejects_path_traversal(monkeypatch):
    """Encoded ../ sequences must be rejected before reaching storage."""
    own_flow = SimpleNamespace(id="flow-own", user_id="user-bob", folder_id=None)
    fake_session = FakeSession(flows=[own_flow], user_files=[])
    storage_service = FakeStorageService({}, {"flow-own/legit.txt": b"ok"})

    monkeypatch.setattr(mcp_utils, "session_scope", lambda: FakeSessionContext(fake_session))
    monkeypatch.setattr(mcp_utils, "get_storage_service", lambda: storage_service)

    token = mcp_utils.current_user_ctx.set(SimpleNamespace(id="user-bob"))
    try:
        uri = "http://host/api/v1/files/download/flow-own/..%2F..%2F..%2Fetc%2Fpasswd"
        with pytest.raises(ValueError, match="Invalid filename"):
            await mcp_utils.handle_read_resource(uri)
    finally:
        mcp_utils.current_user_ctx.reset(token)


@pytest.mark.asyncio
async def test_handle_read_resource_denies_other_users_flow(monkeypatch):
    """Bob must not be able to read a flow owned by Alice, even with a valid filename."""
    # Session returns nothing for the ownership query — i.e. the flow does not belong to bob.
    fake_session = FakeSession(flows=[], user_files=[])
    storage_service = FakeStorageService({}, {"flow-alice/secret.txt": b"alice-secret"})

    monkeypatch.setattr(mcp_utils, "session_scope", lambda: FakeSessionContext(fake_session))
    monkeypatch.setattr(mcp_utils, "get_storage_service", lambda: storage_service)

    token = mcp_utils.current_user_ctx.set(SimpleNamespace(id="user-bob"))
    try:
        uri = "http://host/api/v1/files/download/flow-alice/secret.txt"
        with pytest.raises(ValueError, match="access denied"):
            await mcp_utils.handle_read_resource(uri)
    finally:
        mcp_utils.current_user_ctx.reset(token)


@pytest.mark.asyncio
async def test_handle_read_resource_allows_user_level_bucket(monkeypatch):
    """A user reading from their own user-level bucket (not a flow id) is allowed."""
    # No flow match returned; namespace equals current_user.id so access is allowed.
    fake_session = FakeSession(flows=[], user_files=[])
    storage_service = FakeStorageService({}, {"user-bob/my-file.txt": b"mine"})

    monkeypatch.setattr(mcp_utils, "session_scope", lambda: FakeSessionContext(fake_session))
    monkeypatch.setattr(mcp_utils, "get_storage_service", lambda: storage_service)

    token = mcp_utils.current_user_ctx.set(SimpleNamespace(id="user-bob"))
    try:
        uri = "http://host/api/v1/files/download/user-bob/my-file.txt"
        result = await mcp_utils.handle_read_resource(uri)
    finally:
        mcp_utils.current_user_ctx.reset(token)

    # handle_read_resource returns base64-encoded bytes.
    import base64

    assert base64.b64decode(result) == b"mine"


@pytest.mark.asyncio
async def test_handle_read_resource_denies_user_bucket_under_project_scope(monkeypatch):
    """User-level bucket access must not leak through a project-scoped server."""
    fake_session = FakeSession(flows=[], user_files=[])
    storage_service = FakeStorageService({}, {"user-bob/my-file.txt": b"mine"})

    monkeypatch.setattr(mcp_utils, "session_scope", lambda: FakeSessionContext(fake_session))
    monkeypatch.setattr(mcp_utils, "get_storage_service", lambda: storage_service)

    token = mcp_utils.current_user_ctx.set(SimpleNamespace(id="user-bob"))
    try:
        uri = "http://host/api/v1/files/download/user-bob/my-file.txt"
        with pytest.raises(ValueError, match="access denied"):
            await mcp_utils.handle_read_resource(uri, project_id="project-xyz")
    finally:
        mcp_utils.current_user_ctx.reset(token)


@pytest.mark.asyncio
async def test_handle_list_resources_project_scoped_excludes_user_bucket(monkeypatch):
    """A project-scoped resources/list must not leak user-bucket files unrelated to the project."""
    user_id = "user-bob"
    project_flow = SimpleNamespace(id="flow-in-project", name="Project Flow")

    # If the implementation incorrectly includes user-bucket files, this one would show up.
    user_files = [
        SimpleNamespace(
            name="unrelated.pdf",
            path=f"{user_id}/unrelated.pdf",
            provider="File Manager",
        )
    ]

    fake_session = FakeSession(flows=[project_flow], user_files=user_files)
    storage_service = FakeStorageService({"flow-in-project": ["project-doc.txt"]})

    monkeypatch.setattr(mcp_utils, "session_scope", lambda: FakeSessionContext(fake_session))
    monkeypatch.setattr(mcp_utils, "get_storage_service", lambda: storage_service)
    monkeypatch.setattr(
        mcp_utils,
        "get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(host="localhost", port=4000)),
    )

    token = mcp_utils.current_user_ctx.set(SimpleNamespace(id=user_id))
    try:
        resources = await mcp_utils.handle_list_resources(project_id="project-xyz")
    finally:
        mcp_utils.current_user_ctx.reset(token)

    uris = {str(resource.uri) for resource in resources}
    assert "http://localhost:4000/api/v1/files/download/flow-in-project/project-doc.txt" in uris
    # User-bucket file must not leak through a project-scoped server.
    assert not any("unrelated.pdf" in uri for uri in uris)


@pytest.mark.asyncio
async def test_handle_list_tools_requires_current_user_on_global_server(monkeypatch):
    """Global list_tools must refuse to enumerate flows without a user context."""
    flows = [SimpleNamespace(id="flow-leak", user_id="someone-else", name="Leaked", description=None, data={})]
    fake_session = FakeSession(flows=flows, user_files=[])

    monkeypatch.setattr(mcp_utils, "session_scope", lambda: FakeSessionContext(fake_session))

    # No user context set — must return empty.
    tools = await mcp_utils.handle_list_tools()
    assert tools == []


# ============================================================================
# session_id propagation — MCP clients must be able to persist chat history.
# ============================================================================


def _build_fake_server() -> SimpleNamespace:
    """Build a minimal MCP server stub with progress notifications disabled."""
    return SimpleNamespace(
        request_context=SimpleNamespace(
            meta=SimpleNamespace(progressToken=None),
            session=SimpleNamespace(send_progress_notification=AsyncMock()),
        )
    )


async def _invoke_handle_call_tool(monkeypatch, arguments: dict) -> AsyncMock:
    """Run handle_call_tool with all external deps stubbed; return the simple_run_flow mock."""
    flow = SimpleNamespace(id="flow-id-1", name="my_flow", folder_id=None)

    async def fake_get_flow_snake_case(*_args, **_kwargs):
        return flow

    run_response = SimpleNamespace(outputs=[])
    simple_run_flow_mock = AsyncMock(return_value=run_response)

    monkeypatch.setattr(mcp_utils, "get_flow_snake_case", fake_get_flow_snake_case)
    monkeypatch.setattr(mcp_utils, "simple_run_flow", simple_run_flow_mock)
    monkeypatch.setattr(mcp_utils, "with_db_session", lambda operation: operation(SimpleNamespace()))
    # Force progress notifications off so the test does not exercise that path.
    mcp_utils.get_mcp_config().enable_progress_notifications = False

    token = mcp_utils.current_user_ctx.set(SimpleNamespace(id="user-1"))
    try:
        await mcp_utils.handle_call_tool(
            name="my_flow",
            arguments=arguments,
            server=_build_fake_server(),
        )
    finally:
        mcp_utils.current_user_ctx.reset(token)

    return simple_run_flow_mock


@pytest.mark.asyncio
async def test_handle_call_tool_uses_provided_session_id(monkeypatch):
    """When the MCP client supplies session_id, it must be forwarded to simple_run_flow."""
    simple_run_flow_mock = await _invoke_handle_call_tool(
        monkeypatch,
        arguments={"input_value": "hello", "session_id": "user-1-thread-7"},
    )

    simple_run_flow_mock.assert_awaited_once()
    forwarded_request = simple_run_flow_mock.await_args.kwargs["input_request"]
    assert forwarded_request.session_id == "user-1-thread-7"
    assert forwarded_request.input_value == "hello"


@pytest.mark.asyncio
async def test_handle_call_tool_generates_session_id_when_omitted(monkeypatch):
    """When session_id is absent or blank, a non-empty fallback id must be generated."""
    from uuid import UUID

    simple_run_flow_mock = await _invoke_handle_call_tool(
        monkeypatch,
        arguments={"input_value": "hello"},
    )

    forwarded_request = simple_run_flow_mock.await_args.kwargs["input_request"]
    # Fallback must be a valid UUID-shaped string.
    UUID(forwarded_request.session_id)


@pytest.mark.asyncio
async def test_handle_call_tool_falls_back_when_session_id_blank(monkeypatch):
    """Empty-string session_id must trigger the UUID fallback, not pass through."""
    from uuid import UUID

    simple_run_flow_mock = await _invoke_handle_call_tool(
        monkeypatch,
        arguments={"input_value": "hello", "session_id": ""},
    )

    forwarded_request = simple_run_flow_mock.await_args.kwargs["input_request"]
    UUID(forwarded_request.session_id)
    assert forwarded_request.session_id != ""


def test_json_schema_from_flow_includes_optional_session_id(monkeypatch):
    """json_schema_from_flow must advertise session_id so MCP clients can supply it."""

    class _FakeGraph:
        def __init__(self):
            self.vertices = []  # No input nodes — exercises the empty-properties path.

        @classmethod
        def from_payload(cls, _flow_data):
            return cls()

    # Patch the lazy import inside json_schema_from_flow.
    import lfx.graph.graph.base as graph_base_module

    monkeypatch.setattr(graph_base_module, "Graph", _FakeGraph)

    flow = SimpleNamespace(data={"nodes": [], "edges": []})
    schema = flow_helpers.json_schema_from_flow(flow)

    assert schema["type"] == "object"
    assert "session_id" in schema["properties"]
    assert schema["properties"]["session_id"]["type"] == "string"
    # session_id must be optional so existing MCP clients keep working.
    assert "session_id" not in schema["required"]


def test_json_schema_from_flow_preserves_flow_defined_session_id(monkeypatch):
    """If a flow already defines a session_id input, do not overwrite it."""
    custom_session_id_property = {
        "type": "string",
        "description": "Flow-defined session id with custom semantics.",
    }

    class _FakeNode:
        is_input = True
        data = {
            "node": {
                "template": {
                    "session_id": {
                        "show": True,
                        "advanced": False,
                        "type": "str",
                        "info": custom_session_id_property["description"],
                        "required": True,
                    }
                }
            }
        }

    class _FakeGraph:
        def __init__(self):
            self.vertices = [_FakeNode()]

        @classmethod
        def from_payload(cls, _flow_data):
            return cls()

    import lfx.graph.graph.base as graph_base_module

    monkeypatch.setattr(graph_base_module, "Graph", _FakeGraph)

    flow = SimpleNamespace(data={"nodes": [], "edges": []})
    schema = flow_helpers.json_schema_from_flow(flow)

    # The flow's own definition wins — the reserved injection must not clobber it.
    assert schema["properties"]["session_id"]["description"] == custom_session_id_property["description"]
    assert "session_id" in schema["required"]
