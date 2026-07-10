"""The agentic MCP server must be reachable over HTTP, not only stdio.

Community ask: call the Langflow Assistant from external MCP clients
(Cursor, Claude, Codex) against a RUNNING Langflow server, without spawning
a local ``python -m langflow.agentic.mcp`` process.

These tests pin the ``/api/v1/agentic/mcp`` streamable-http endpoint:
gated on ``agentic_experience`` (404 when off), authenticated with the same
dependency as the other MCP HTTP endpoints, and the authenticated user is
always injected as ``user_id`` so a caller can never impersonate another
user (the stdio tools trust the caller-supplied ``user_id``; HTTP must not).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

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
    async def test_should_list_the_agentic_tools_without_user_id_in_any_schema(self):
        from langflow.api.v1.agentic_mcp import handle_list_tools

        tools = await handle_list_tools()
        tool_names = {tool.name for tool in tools}

        assert "run_assistant" in tool_names
        for tool in tools:
            properties = (tool.inputSchema or {}).get("properties", {})
            assert "user_id" not in properties, f"{tool.name} must not expose user_id over HTTP"
            assert "user_id" not in (tool.inputSchema or {}).get("required", [])

    async def test_should_override_caller_supplied_user_id_with_the_authenticated_user(self):
        from langflow.api.v1 import agentic_mcp

        authenticated_user = SimpleNamespace(id=uuid4())
        token = agentic_mcp.current_agentic_mcp_user_ctx.set(authenticated_user)
        try:
            with patch.object(
                agentic_mcp.agentic_mcp, "call_tool", new_callable=AsyncMock, return_value=[]
            ) as call_tool:
                await agentic_mcp.handle_call_tool(
                    "run_assistant",
                    {"instruction": "build a flow", "user_id": str(uuid4())},
                )
        finally:
            agentic_mcp.current_agentic_mcp_user_ctx.reset(token)

        forwarded = call_tool.await_args.args[1]
        assert forwarded["user_id"] == str(authenticated_user.id)

    async def test_should_not_add_user_id_to_tools_that_do_not_accept_it(self):
        from langflow.api.v1 import agentic_mcp

        token = agentic_mcp.current_agentic_mcp_user_ctx.set(SimpleNamespace(id=uuid4()))
        try:
            with patch.object(
                agentic_mcp.agentic_mcp, "call_tool", new_callable=AsyncMock, return_value=[]
            ) as call_tool:
                await agentic_mcp.handle_call_tool("list_all_tags", {})
        finally:
            agentic_mcp.current_agentic_mcp_user_ctx.reset(token)

        assert "user_id" not in call_tool.await_args.args[1]

    async def test_should_fail_when_no_authenticated_user_is_in_context(self):
        from langflow.api.v1 import agentic_mcp

        with pytest.raises(ValueError, match="Authenticated user"):
            await agentic_mcp.handle_call_tool("run_assistant", {"instruction": "hi"})
