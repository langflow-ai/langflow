from types import SimpleNamespace

import pytest
from langflow.api.v1 import mcp_utils
from lfx.interface.components import component_cache


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


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
    def __init__(self, files_by_flow):
        self._files_by_flow = files_by_flow

    async def list_files(self, flow_id: str):
        return self._files_by_flow.get(flow_id, [])


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

    tools = await mcp_utils.handle_list_tools()

    assert tools == []
