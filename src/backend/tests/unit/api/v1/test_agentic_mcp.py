"""The Langflow MCP toolkit must be reachable over HTTP, not only stdio.

Community ask: call the Langflow Assistant from external MCP clients
(Cursor, Claude, Codex) against a RUNNING Langflow server, without spawning
a local stdio process.

These tests pin the ``/api/v1/agentic/mcp`` streamable-http endpoint:
gated on ``agentic_experience`` (404 when off), authenticated with the same
dependency as the other MCP HTTP endpoints, and delegating to the single
lfx toolkit (``lfx.mcp.server``) with the caller's own credentials bound to
the loopback REST client — so authorization happens at the API on every tool
call, and ``login`` (a credential-forwarding surface) is not exposed.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient

MODULE = "langflow.api.v1.agentic_mcp"

pytestmark = pytest.mark.asyncio


@pytest.fixture
def agentic_enabled(client):  # noqa: ARG001 — the app (and its settings service) must exist first
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    original = settings.agentic_experience
    settings.agentic_experience = True
    yield
    settings.agentic_experience = original


@pytest.fixture
async def mock_agentic_streamable_manager():
    manager = AsyncMock()

    async def fake_handle_request(_scope, _receive, send):
        await send({"type": "http.response.start", "status": status.HTTP_200_OK, "headers": []})
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    manager.handle_request = AsyncMock(side_effect=fake_handle_request)
    with (
        patch(f"{MODULE}._streamable_http.start", new_callable=AsyncMock),
        patch(f"{MODULE}._streamable_http.get_manager", return_value=manager),
    ):
        yield manager


class TestAgenticMcpFeatureGate:
    async def test_should_return_404_when_agentic_experience_is_disabled(self, client: AsyncClient, logged_in_headers):
        response = await client.post("api/v1/agentic/mcp", headers=logged_in_headers, json={"type": "test"})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_should_return_404_on_health_check_when_disabled(self, client: AsyncClient):
        response = await client.head("api/v1/agentic/mcp")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.usefixtures("agentic_enabled")
class TestAgenticMcpAuthentication:
    async def test_should_reject_unauthenticated_post(self, client: AsyncClient):
        response = await client.post("api/v1/agentic/mcp", json={"type": "test"})
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    async def test_should_reject_invalid_bearer_token(self, client: AsyncClient):
        response = await client.post(
            "api/v1/agentic/mcp",
            headers={"Authorization": "Bearer invalid_token"},
            json={"type": "test"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_should_answer_health_check_when_enabled(self, client: AsyncClient):
        response = await client.head("api/v1/agentic/mcp")
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.usefixtures("agentic_enabled")
class TestAgenticMcpTransportDispatch:
    async def test_should_dispatch_authenticated_post_to_the_session_manager(
        self, client: AsyncClient, logged_in_headers, mock_agentic_streamable_manager
    ):
        response = await client.post("api/v1/agentic/mcp", headers=logged_in_headers, json={"type": "test"})
        assert response.status_code == status.HTTP_200_OK
        mock_agentic_streamable_manager.handle_request.assert_called_once()

    async def test_should_return_500_when_the_transport_fails(
        self, client: AsyncClient, logged_in_headers, mock_agentic_streamable_manager
    ):
        mock_agentic_streamable_manager.handle_request.side_effect = Exception("boom")
        response = await client.post("api/v1/agentic/mcp", headers=logged_in_headers, json={"type": "test"})
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestAgenticMcpToolDelegation:
    async def test_should_list_the_lfx_toolkit_including_run_assistant(self):
        from langflow.api.v1.agentic_mcp import handle_list_tools

        tools = await handle_list_tools()
        tool_names = {tool.name for tool in tools}

        assert "run_assistant" in tool_names
        assert "create_flow" in tool_names
        assert "connect_components" in tool_names
        for tool in tools:
            properties = (tool.inputSchema or {}).get("properties", {})
            assert "user_id" not in properties, f"{tool.name} must not expose user_id over HTTP"

    async def test_should_not_expose_login_over_http(self):
        from langflow.api.v1 import agentic_mcp

        tools = await agentic_mcp.handle_list_tools()
        assert "login" not in {tool.name for tool in tools}

        with pytest.raises(ValueError, match="not available over HTTP"):
            await agentic_mcp.handle_call_tool("login", {"username": "u", "password": "p"})

    async def test_should_delegate_with_the_callers_loopback_client_bound(self):
        from langflow.api.v1 import agentic_mcp
        from lfx.mcp import server as lfx_server

        loopback = AsyncMock()
        seen: dict[str, object] = {}

        async def spy_call_tool(name, arguments):
            seen["client"] = lfx_server._get_client()
            seen["name"] = name
            seen["arguments"] = arguments
            return []

        token = agentic_mcp.current_loopback_client_ctx.set(loopback)
        try:
            with patch.object(agentic_mcp.lfx_mcp, "call_tool", side_effect=spy_call_tool):
                await agentic_mcp.handle_call_tool("list_flows", {"query": "x"})
        finally:
            agentic_mcp.current_loopback_client_ctx.reset(token)

        assert seen["client"] is loopback
        assert seen["name"] == "list_flows"
        assert seen["arguments"] == {"query": "x"}

    async def test_should_fail_when_no_client_is_in_context(self):
        from langflow.api.v1 import agentic_mcp

        with pytest.raises(ValueError, match="Authenticated client"):
            await agentic_mcp.handle_call_tool("list_flows", {})

    async def test_loopback_client_carries_the_callers_headers(self):
        from langflow.api.v1.agentic_mcp import _loopback_client

        class FakeRequest:
            base_url = "http://localhost:7860/"
            headers = {"Authorization": "Bearer tok-123", "x-api-key": "key-456"}

        client = _loopback_client(FakeRequest())
        assert client.server_url == "http://localhost:7860"
        assert client.access_token == "tok-123"  # noqa: S105
        assert client.api_key == "key-456"
