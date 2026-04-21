from types import SimpleNamespace

import pytest
from langflow.api.v1 import mcp_utils
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
