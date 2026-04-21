from types import SimpleNamespace

import pytest
from langflow.api.utils.core import extract_global_variables_from_headers
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
