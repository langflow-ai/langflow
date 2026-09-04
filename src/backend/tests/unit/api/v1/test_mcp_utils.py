from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from langflow.api.utils.core import extract_global_variables_from_headers
from langflow.api.v1 import mcp_utils
from langflow.helpers import flow as flow_helpers
from langflow.services.database.models import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from lfx.interface.components import component_cache
from lfx.services.authorization import PUBLIC_ANONYMOUS_ACTOR_ID


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

    # The global server is the editor-plane surface, where an empty list is a normal
    # state; only the project endpoint raises. See test_mcp_failure_reporting.py.
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
async def test_handle_read_resource_project_scope_binds_flow_id_as_uuid(monkeypatch, async_session):
    """A flow UUID parsed from an advertised resource URI must remain UUID-typed in the database query."""
    user = User(username="mcp-resource-reader", password="test-password")  # noqa: S106
    project = Folder(name="MCP Resource Project", user_id=user.id)
    flow = Flow(name="MCP Resource Flow", user_id=user.id, folder_id=project.id)
    other_project = Folder(name="Other MCP Resource Project", user_id=user.id)
    other_flow = Flow(name="Other MCP Resource Flow", user_id=user.id, folder_id=other_project.id)
    async_session.add_all([user, project, flow, other_project, other_flow])
    await async_session.flush()

    file_name = "project-resource.txt"
    storage_service = FakeStorageService(
        {},
        {
            f"{flow.id}/{file_name}": b"project file contents",
            f"{other_flow.id}/{file_name}": b"other project file contents",
        },
    )

    monkeypatch.setattr(mcp_utils, "session_scope", lambda: FakeSessionContext(async_session))
    monkeypatch.setattr(mcp_utils, "get_storage_service", lambda: storage_service)

    token = mcp_utils.current_user_ctx.set(user)
    try:
        uri = f"http://host/api/v1/files/download/{flow.id}/{file_name}"
        result = await mcp_utils.handle_read_resource(uri, project_id=project.id)

        other_uri = f"http://host/api/v1/files/download/{other_flow.id}/{file_name}"
        with pytest.raises(ValueError, match="access denied"):
            await mcp_utils.handle_read_resource(other_uri, project_id=project.id)

        with pytest.raises(ValueError, match="access denied"):
            await mcp_utils.handle_read_resource(uri, project_id="not-a-uuid")
    finally:
        mcp_utils.current_user_ctx.reset(token)

    import base64

    assert base64.b64decode(result) == b"project file contents"


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


def test_public_mcp_session_namespace_is_stable_and_isolated():
    """Namespaces are stable per connection and isolated by connection, project, and flow."""
    project_id = uuid4()
    flow_id = uuid4()
    server = SimpleNamespace(request_context=SimpleNamespace(session=SimpleNamespace(session_id="connection-a")))

    namespace = mcp_utils._public_mcp_session_namespace(server, project_id, flow_id)

    assert mcp_utils._public_mcp_session_namespace(server, project_id, flow_id) == namespace
    assert mcp_utils._public_mcp_session_namespace(server, uuid4(), flow_id) != namespace
    assert mcp_utils._public_mcp_session_namespace(server, project_id, uuid4()) != namespace

    other_server = SimpleNamespace(request_context=SimpleNamespace(session=SimpleNamespace(session_id="connection-b")))
    assert mcp_utils._public_mcp_session_namespace(other_server, project_id, flow_id) != namespace


async def _invoke_handle_call_tool(
    monkeypatch,
    arguments: dict,
    *,
    authenticated_caller="user-1",
    project_id=None,
    flow_data=None,
    request_variables: dict[str, str] | None = None,
    expected_error: str | None = None,
) -> AsyncMock:
    """Run handle_call_tool with all external deps stubbed; return the simple_run_flow mock.

    ``authenticated_caller`` is the principal that presented a credential, which the auth
    dependency establishes before the handler runs. It is not the same as the principal the
    flow executes as: a project with ``auth_type="none"`` executes as its owner for an
    anonymous caller, so the handler cannot read ownership off the execution principal.
    """
    # ``user_id`` matches the current user (see ``current_user_ctx`` below) so the
    # owner-override path in ``ensure_flow_permission`` is exercised; ``workspace_id``
    # is read by the same guard. ``data`` feeds the HITL support gate.
    flow = SimpleNamespace(
        id=uuid4(),
        name="my_flow",
        folder_id=project_id,
        user_id="user-1",
        workspace_id=None,
        data=flow_data or {"nodes": [], "edges": []},
    )

    def model_copy(*, update, deep):
        assert deep is True
        copied = vars(flow).copy()
        copied.update(update)
        return SimpleNamespace(**copied)

    flow.model_copy = model_copy

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
    caller_token = mcp_utils.authenticated_caller_ctx.set(authenticated_caller)
    request_variables_token = mcp_utils.current_request_variables_ctx.set(request_variables)
    try:
        if expected_error is None:
            await mcp_utils.handle_call_tool(
                name="my_flow",
                arguments=arguments,
                server=_build_fake_server(),
                project_id=project_id,
            )
        else:
            with pytest.raises(RuntimeError, match=expected_error):
                await mcp_utils.handle_call_tool(
                    name="my_flow",
                    arguments=arguments,
                    server=_build_fake_server(),
                    project_id=project_id,
                )
    finally:
        mcp_utils.current_request_variables_ctx.reset(request_variables_token)
        mcp_utils.authenticated_caller_ctx.reset(caller_token)
        mcp_utils.current_user_ctx.reset(token)

    return simple_run_flow_mock


async def test_handle_call_tool_applies_public_policy_and_scopes_session(monkeypatch):
    project_id = uuid4()
    prepared_data = {"nodes": [{"prepared": True}], "edges": []}
    sanitized_data = {"nodes": [{"sanitized": True}], "edges": []}
    validate = MagicMock()
    prepare = AsyncMock(return_value=prepared_data)
    strip = MagicMock(return_value=sanitized_data)
    monkeypatch.setattr(mcp_utils, "validate_public_flow_no_code_execution", validate)
    monkeypatch.setattr(mcp_utils, "prepare_public_flow_build", prepare)
    monkeypatch.setattr(mcp_utils, "strip_secret_field_values", strip)

    simple_run_flow_mock = await _invoke_handle_call_tool(
        monkeypatch,
        arguments={"input_value": "hello", "session_id": "owner-private"},
        authenticated_caller=None,
        project_id=project_id,
    )

    validate.assert_called_once()
    prepare.assert_awaited_once()
    strip.assert_called_once_with(prepared_data)
    forwarded_flow = simple_run_flow_mock.await_args.kwargs["flow"]
    forwarded_request = simple_run_flow_mock.await_args.kwargs["input_request"]
    forwarded_user = simple_run_flow_mock.await_args.kwargs["api_key_user"]
    assert forwarded_flow.data == sanitized_data
    assert forwarded_request.session_id != "owner-private"
    assert forwarded_request.session_id.endswith(":owner-private")
    assert forwarded_user.id == PUBLIC_ANONYMOUS_ACTOR_ID
    assert forwarded_user.is_superuser is False


async def test_handle_call_tool_preserves_request_backed_secret_references_for_public_flow(monkeypatch):
    variable_name = "OPENRAG_INGEST_TOKEN"
    flow_data = {
        "nodes": [
            {
                "id": "openrag",
                "data": {
                    "id": "openrag",
                    "type": "OpenRAG",
                    "node": {
                        "template": {
                            "api_key": {
                                "name": "api_key",
                                "password": True,
                                "load_from_db": True,
                                "value": variable_name,
                            },
                            "headers": {
                                "name": "headers",
                                "type": "table",
                                "table_schema": [
                                    {"name": "key", "type": "str"},
                                    {"name": "value", "type": "str", "load_from_db": True},
                                ],
                                "value": [
                                    {
                                        "key": f"X-Langflow-Global-Var-{variable_name}",
                                        "value": variable_name,
                                        "__load_from_db_fields": {"value": True},
                                    }
                                ],
                            },
                        }
                    },
                },
            }
        ],
        "edges": [],
    }
    monkeypatch.setattr(mcp_utils, "validate_public_flow_no_code_execution", MagicMock())
    monkeypatch.setattr(mcp_utils, "prepare_public_flow_build", AsyncMock(return_value=flow_data))

    simple_run_flow_mock = await _invoke_handle_call_tool(
        monkeypatch,
        arguments={"input_value": "hello"},
        authenticated_caller=None,
        project_id=uuid4(),
        flow_data=flow_data,
        request_variables={variable_name: "request-scoped-secret"},  # pragma: allowlist secret
    )

    forwarded_flow = simple_run_flow_mock.await_args.kwargs["flow"]
    forwarded_template = forwarded_flow.data["nodes"][0]["data"]["node"]["template"]
    assert forwarded_template["api_key"]["value"] == variable_name
    assert forwarded_template["headers"]["value"][0]["value"] == variable_name
    assert simple_run_flow_mock.await_args.kwargs["context"] == {
        "request_variables": {variable_name: "request-scoped-secret"}  # pragma: allowlist secret
    }


async def test_handle_call_tool_keeps_unmatched_public_secret_references_scrubbed(monkeypatch):
    variable_name = "OWNER_ONLY_TOKEN"
    flow_data = {
        "nodes": [
            {
                "id": "private-token",
                "data": {
                    "id": "private-token",
                    "type": "SecretConsumer",
                    "node": {
                        "template": {
                            "api_key": {
                                "name": "api_key",
                                "password": True,
                                "load_from_db": True,
                                "value": variable_name,
                            },
                            "headers": {
                                "name": "headers",
                                "type": "table",
                                "table_schema": [{"name": "value", "type": "str", "load_from_db": True}],
                                "value": [
                                    {
                                        "key": "X-Langflow-Global-Var-OWNER_ONLY_TABLE_TOKEN",
                                        "value": "OWNER_ONLY_TABLE_TOKEN",
                                        "__load_from_db_fields": {"value": True},
                                    },
                                    {
                                        "key": "X-Langflow-Global-Var-LITERAL_TOKEN",
                                        "value": "LITERAL_TOKEN",
                                        "__load_from_db_fields": {"value": False},
                                    },
                                ],
                            },
                        }
                    },
                },
            }
        ],
        "edges": [],
    }
    monkeypatch.setattr(mcp_utils, "validate_public_flow_no_code_execution", MagicMock())
    monkeypatch.setattr(mcp_utils, "prepare_public_flow_build", AsyncMock(return_value=flow_data))

    simple_run_flow_mock = await _invoke_handle_call_tool(
        monkeypatch,
        arguments={"input_value": "hello"},
        authenticated_caller=None,
        project_id=uuid4(),
        flow_data=flow_data,
        request_variables={
            "DIFFERENT_TOKEN": "request-scoped-secret",  # pragma: allowlist secret
            "LITERAL_TOKEN": "must-not-be-used",  # pragma: allowlist secret
        },
    )

    forwarded_flow = simple_run_flow_mock.await_args.kwargs["flow"]
    forwarded_template = forwarded_flow.data["nodes"][0]["data"]["node"]["template"]
    assert forwarded_template["api_key"]["value"] is None
    assert forwarded_template["headers"]["value"][0]["value"] is None
    assert forwarded_template["headers"]["value"][1]["value"] is None


async def test_handle_call_tool_rejects_public_flow_validation_failure(monkeypatch):
    validate = MagicMock(side_effect=mcp_utils.CustomComponentValidationError("custom code is not allowed"))
    prepare = AsyncMock()
    monkeypatch.setattr(mcp_utils, "validate_public_flow_no_code_execution", validate)
    monkeypatch.setattr(mcp_utils, "prepare_public_flow_build", prepare)

    simple_run_flow_mock = await _invoke_handle_call_tool(
        monkeypatch,
        arguments={"input_value": "hello"},
        authenticated_caller=None,
        project_id=uuid4(),
        expected_error="cannot be executed through a public MCP project",
    )

    validate.assert_called_once()
    prepare.assert_not_awaited()
    simple_run_flow_mock.assert_not_awaited()


async def test_handle_call_tool_rejects_public_flow_prepare_failure(monkeypatch):
    validate = MagicMock()
    prepare = AsyncMock(side_effect=mcp_utils.CustomComponentValidationError("invalid public flow"))
    monkeypatch.setattr(mcp_utils, "validate_public_flow_no_code_execution", validate)
    monkeypatch.setattr(mcp_utils, "prepare_public_flow_build", prepare)

    simple_run_flow_mock = await _invoke_handle_call_tool(
        monkeypatch,
        arguments={"input_value": "hello"},
        authenticated_caller=None,
        project_id=uuid4(),
        expected_error="cannot be executed through a public MCP project",
    )

    validate.assert_called_once()
    prepare.assert_awaited_once()
    simple_run_flow_mock.assert_not_awaited()


async def test_handle_call_tool_preserves_authenticated_mcp_session(monkeypatch):
    prepare = AsyncMock()
    monkeypatch.setattr(mcp_utils, "prepare_public_flow_build", prepare)

    simple_run_flow_mock = await _invoke_handle_call_tool(
        monkeypatch,
        arguments={"input_value": "hello", "session_id": "user-thread"},
        authenticated_caller="user-1",
        project_id=uuid4(),
    )

    prepare.assert_not_awaited()
    forwarded_request = simple_run_flow_mock.await_args.kwargs["input_request"]
    forwarded_user = simple_run_flow_mock.await_args.kwargs["api_key_user"]
    assert forwarded_request.session_id == "user-thread"
    assert forwarded_user.id == "user-1"


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
    assert simple_run_flow_mock.await_args.kwargs["expose_error_details"] is True


@pytest.mark.asyncio
async def test_handle_call_tool_hides_error_details_from_an_anonymous_caller(monkeypatch):
    """A public project runs as its owner, so ownership cannot be read off the executor.

    ``auth_type="none"`` establishes no caller. Comparing the execution principal to the
    flow owner answered yes for everyone and handed anonymous callers the owner's raw
    component errors, so the absence of a caller has to read as anonymous.
    """
    simple_run_flow_mock = await _invoke_handle_call_tool(
        monkeypatch,
        arguments={"input_value": "hello"},
        authenticated_caller=None,
    )

    assert simple_run_flow_mock.await_args.kwargs["expose_error_details"] is False


@pytest.mark.asyncio
async def test_handle_call_tool_hides_error_details_from_a_different_user(monkeypatch):
    """Authenticating as somebody else must not disclose the owner's internals either."""
    simple_run_flow_mock = await _invoke_handle_call_tool(
        monkeypatch,
        arguments={"input_value": "hello"},
        authenticated_caller="user-2",
    )

    assert simple_run_flow_mock.await_args.kwargs["expose_error_details"] is False


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


async def test_handle_call_tool_forwards_only_advertised_input_fields(monkeypatch):
    """Advertised MCP arguments must reach only the input nodes that expose them."""

    class _FakeNode:
        def __init__(self, node_id, *, is_input, template):
            self.id = node_id
            self.is_input = is_input
            self.data = {"node": {"template": template}}

    class _FakeGraph:
        def __init__(self):
            self.vertices = [
                _FakeNode(
                    "input-a",
                    is_input=True,
                    template={
                        "input_value": {"show": True, "advanced": False},
                        "backend_token": {"show": True, "advanced": False, "api_editable": True},
                        "enabled": {"show": True, "advanced": False, "api_editable": True},
                        "hidden": {"show": False, "advanced": False, "api_editable": True},
                        "advanced": {"show": True, "advanced": True, "api_editable": True},
                    },
                ),
                _FakeNode(
                    "input-b",
                    is_input=True,
                    template={
                        "backend_token": {"show": True, "advanced": False, "api_editable": True},
                        "backend_url": {"show": True, "advanced": False, "api_editable": True},
                    },
                ),
                _FakeNode(
                    "downstream",
                    is_input=False,
                    template={"backend_url": {"show": True, "advanced": False, "api_editable": True}},
                ),
            ]

        @classmethod
        def from_payload(cls, _flow_data):
            return cls()

    import lfx.graph.graph.base as graph_base_module

    monkeypatch.setattr(graph_base_module, "Graph", _FakeGraph)

    simple_run_flow_mock = await _invoke_handle_call_tool(
        monkeypatch,
        arguments={
            "input_value": "test request",
            "session_id": "thread-1",
            "backend_token": "example-token",
            "backend_url": "https://backend.example.com",
            "enabled": False,
            "hidden": "must-not-forward",
            "advanced": "must-not-forward",
            "unknown": "must-not-forward",
        },
    )

    forwarded_request = simple_run_flow_mock.await_args.kwargs["input_request"]
    assert forwarded_request.input_value == "test request"
    assert forwarded_request.session_id == "thread-1"
    assert forwarded_request.tweaks is not None
    assert forwarded_request.tweaks.root == {
        "input-a": {"backend_token": "example-token", "enabled": False},
        "input-b": {
            "backend_token": "example-token",
            "backend_url": "https://backend.example.com",
        },
    }


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
                        "api_editable": True,
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


def test_json_schema_from_flow_only_advertises_api_exposed_fields(monkeypatch):
    """MCP tools/list must honor each input field's API exposure toggle."""

    class _FakeNode:
        is_input = True
        data = {
            "node": {
                "template": {
                    "exposed": {
                        "show": True,
                        "advanced": False,
                        "api_editable": True,
                        "type": "str",
                        "required": True,
                    },
                    "not_exposed": {
                        "show": True,
                        "advanced": False,
                        "api_editable": False,
                        "type": "str",
                        "required": True,
                    },
                    "legacy_without_exposure_flag": {
                        "show": True,
                        "advanced": False,
                        "type": "str",
                    },
                    "off_node": {
                        "show": True,
                        "advanced": True,
                        "api_editable": True,
                        "type": "str",
                    },
                }
            }
        }

    class _FakeGraph:
        vertices = [_FakeNode()]

        @classmethod
        def from_payload(cls, _flow_data):
            return cls()

    import lfx.graph.graph.base as graph_base_module

    monkeypatch.setattr(graph_base_module, "Graph", _FakeGraph)

    schema = flow_helpers.json_schema_from_flow(SimpleNamespace(data={"nodes": [], "edges": []}))

    assert set(schema["properties"]) == {"exposed", "session_id"}
    assert schema["required"] == ["exposed"]


def _patch_graph_with_input_nodes(monkeypatch, templates):
    """Stand a fake graph whose input vertices carry ``templates`` (a list of node templates)."""

    class _FakeNode:
        def __init__(self, node_id, template):
            self.id = node_id
            self.is_input = True
            self.data = {"node": {"template": template}}

    class _FakeGraph:
        vertices = [_FakeNode(f"input-{index}", template) for index, template in enumerate(templates)]

        @classmethod
        def from_payload(cls, _flow_data):
            return cls()

    import lfx.graph.graph.base as graph_base_module

    monkeypatch.setattr(graph_base_module, "Graph", _FakeGraph)


def test_json_schema_from_flow_keeps_visible_fields_when_flow_declares_no_allowlist(monkeypatch):
    """A flow that toggled nothing has declared no allowlist and keeps its previous contract.

    ``api_editable`` defaults to False and has no backfill, so gating on it without this fallback
    empties the advertised schema of every flow nobody hand-prepared -- templates included.
    """
    _patch_graph_with_input_nodes(
        monkeypatch,
        [
            {
                "input_value": {"show": True, "advanced": False, "type": "str", "required": True},
                "sender_name": {"show": True, "advanced": False, "type": "str"},
                "opt_out": {"show": True, "advanced": False, "api_editable": False, "type": "str"},
                "hidden": {"show": False, "advanced": False, "type": "str"},
                "off_node": {"show": True, "advanced": True, "type": "str"},
            }
        ],
    )

    schema = flow_helpers.json_schema_from_flow(SimpleNamespace(data={"nodes": [], "edges": []}))

    assert set(schema["properties"]) == {"input_value", "sender_name", "opt_out", "session_id"}
    assert schema["required"] == ["input_value"]


def test_json_schema_from_flow_always_advertises_input_value(monkeypatch):
    """``input_value`` stays advertised even under an allowlist, because the runtime still takes it.

    ``handle_call_tool`` pops ``input_value`` before the tweak filter and forwards it directly, so
    dropping it from the schema would publish a contract narrower than the one served -- a caller
    obeying the schema would run the flow with no message.
    """
    _patch_graph_with_input_nodes(
        monkeypatch,
        [
            {
                "input_value": {"show": True, "advanced": False, "type": "str"},
                "sender_name": {"show": True, "advanced": False, "api_editable": True, "type": "str"},
                "session_ttl": {"show": True, "advanced": False, "type": "int"},
            }
        ],
    )

    schema = flow_helpers.json_schema_from_flow(SimpleNamespace(data={"nodes": [], "edges": []}))

    assert set(schema["properties"]) == {"input_value", "sender_name", "session_id"}


def test_json_schema_from_flow_allowlist_is_scoped_to_a_single_flow(monkeypatch):
    """One input node's toggle closes the whole flow, not just that node."""
    _patch_graph_with_input_nodes(
        monkeypatch,
        [
            {"greeting": {"show": True, "advanced": False, "api_editable": True, "type": "str"}},
            {"untoggled": {"show": True, "advanced": False, "type": "str"}},
        ],
    )

    schema = flow_helpers.json_schema_from_flow(SimpleNamespace(data={"nodes": [], "edges": []}))

    assert set(schema["properties"]) == {"greeting", "session_id"}


def test_get_flow_input_tweaks_matches_the_advertised_schema(monkeypatch):
    """The call-time filter must accept exactly what ``tools/list`` advertised."""
    template = {
        "sender_name": {"show": True, "advanced": False, "type": "str"},
        "hidden": {"show": False, "advanced": False, "type": "str"},
    }
    _patch_graph_with_input_nodes(monkeypatch, [template])
    flow = SimpleNamespace(data={"nodes": [], "edges": []})

    # No toggle anywhere: permissive, so the visible field is forwarded.
    assert flow_helpers.get_flow_input_tweaks(flow, {"sender_name": "ada", "hidden": "no"}) == {
        "input-0": {"sender_name": "ada"}
    }

    # Once the flow declares an allowlist, an untoggled field is refused at both ends.
    _patch_graph_with_input_nodes(
        monkeypatch,
        [{**template, "greeting": {"show": True, "advanced": False, "api_editable": True, "type": "str"}}],
    )
    assert flow_helpers.get_flow_input_tweaks(flow, {"sender_name": "ada", "greeting": "hi"}) == {
        "input-0": {"greeting": "hi"}
    }


def test_json_schema_from_flow_maps_structured_and_list_field_types(monkeypatch):
    """MCP input schemas must describe the JSON values accepted by exposed fields."""

    class _FakeNode:
        is_input = True
        data = {
            "node": {
                "template": {
                    "metadata": {
                        "show": True,
                        "advanced": False,
                        "api_editable": True,
                        "type": "dict",
                    },
                    "nested": {
                        "show": True,
                        "advanced": False,
                        "api_editable": True,
                        "type": "NestedDict",
                    },
                    "steps": {
                        "show": True,
                        "advanced": False,
                        "api_editable": True,
                        "type": "sortableList",
                    },
                    "rows": {
                        "show": True,
                        "advanced": False,
                        "api_editable": True,
                        "type": "table",
                        "list": True,
                    },
                    "actions": {
                        "show": True,
                        "advanced": False,
                        "api_editable": True,
                        "type": "actionPicker",
                        "list": True,
                    },
                    "tools": {
                        "show": True,
                        "advanced": False,
                        "api_editable": True,
                        "type": "tools",
                        "is_list": True,
                    },
                    "models": {
                        "show": True,
                        "advanced": False,
                        "api_editable": True,
                        "type": "model",
                        "list": False,
                    },
                    "tags": {
                        "show": True,
                        "advanced": False,
                        "api_editable": True,
                        "type": "str",
                        "list": True,
                    },
                }
            }
        }

    class _FakeGraph:
        vertices = [_FakeNode()]

        @classmethod
        def from_payload(cls, _flow_data):
            return cls()

    import lfx.graph.graph.base as graph_base_module

    monkeypatch.setattr(graph_base_module, "Graph", _FakeGraph)

    schema = flow_helpers.json_schema_from_flow(SimpleNamespace(data={"nodes": [], "edges": []}))
    properties = schema["properties"]

    assert properties["metadata"]["type"] == "object"
    assert properties["nested"]["type"] == "object"
    assert properties["steps"]["type"] == "array"
    assert properties["steps"]["items"] == {"type": "object"}
    assert properties["rows"]["type"] == "array"
    assert properties["rows"]["items"] == {"type": "object"}
    assert properties["actions"]["type"] == "array"
    assert properties["actions"]["items"] == {"type": "string"}
    assert properties["tools"]["type"] == "array"
    assert properties["tools"]["items"] == {"type": "object"}
    assert properties["models"]["type"] == "array"
    assert properties["models"]["items"] == {"type": "object"}
    assert properties["tags"]["type"] == "array"
    assert properties["tags"]["items"] == {"type": "string"}


@pytest.mark.asyncio
async def test_handle_call_tool_blocks_hitl_flow(monkeypatch):
    """A HITL flow invoked as an MCP tool must raise so the MCP result is isError, pointing to the v2 API."""
    hitl_flow = SimpleNamespace(
        id="flow-hitl",
        name="HITL Tools",
        folder_id=None,
        # Owner of the flow (matches current_user_ctx below) so ensure_flow_permission's
        # owner-override path passes and the run reaches the HITL support gate.
        user_id="user-1",
        workspace_id=None,
        data={
            "nodes": [
                {
                    "id": "url",
                    "data": {
                        "id": "url",
                        "type": "URLComponent",
                        "node": {
                            "template": {
                                "tools_metadata": {
                                    "value": [{"name": "fetch", "approval_actions": ["approve", "reject"]}]
                                }
                            }
                        },
                    },
                }
            ],
            "edges": [],
        },
    )

    async def fake_get_flow(*_args, **_kwargs):
        return hitl_flow

    async def fake_with_db_session(operation):
        return await operation(object())

    monkeypatch.setattr(mcp_utils, "get_flow_snake_case", fake_get_flow)
    monkeypatch.setattr(mcp_utils, "with_db_session", fake_with_db_session)
    monkeypatch.setattr(mcp_utils, "get_mcp_config", lambda: SimpleNamespace(enable_progress_notifications=False))

    token = mcp_utils.current_user_ctx.set(SimpleNamespace(id="user-1"))
    try:
        with pytest.raises(RuntimeError, match="Human-in-the-Loop"):
            await mcp_utils.handle_call_tool("hitl_tools", {"input_value": "hi"}, server=SimpleNamespace())
    finally:
        mcp_utils.current_user_ctx.reset(token)
