"""The Langflow MCP toolkit must be reachable over HTTP, not only stdio.

Community ask: call the Langflow Assistant from external MCP clients
(Cursor, Claude, Codex) against a RUNNING Langflow server, without spawning
a local stdio process.

These tests pin the ``/api/v1/agentic/mcp`` streamable-http endpoint:
authenticated with the same dependency as the other MCP HTTP endpoints, and
delegating to the single lfx toolkit (``lfx.mcp.server``) with the caller's own
credentials bound to the loopback REST client — so authorization happens at the
API on every tool call, and ``login`` (a credential-forwarding surface) is not
exposed.

The mount is NOT gated on ``agentic_experience``: its tools are REST calls the
API already authorizes, and the ``lfx-mcp`` stdio bridge serves the same toolkit
ungated, so gating the mount would only make HTTP weaker than stdio for no gain.
The gate applies per-tool to ``run_assistant``, the only tool that reaches the
assistant's code-generating endpoints.
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


@pytest.fixture
def agentic_disabled(client):  # noqa: ARG001 — the app (and its settings service) must exist first
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    original = settings.agentic_experience
    settings.agentic_experience = False
    yield
    settings.agentic_experience = original


@pytest.mark.usefixtures("agentic_disabled")
class TestAgenticMcpToolkitStaysReachableWhenAssistantIsOff:
    """The toolkit is REST-backed and ungated on stdio; HTTP must not be weaker."""

    async def test_should_answer_health_check_when_the_assistant_is_disabled(self, client: AsyncClient):
        response = await client.head("api/v1/agentic/mcp")
        assert response.status_code == status.HTTP_200_OK

    async def test_should_dispatch_an_authenticated_post_when_the_assistant_is_disabled(
        self, client: AsyncClient, logged_in_headers, mock_agentic_streamable_manager
    ):
        response = await client.post("api/v1/agentic/mcp", headers=logged_in_headers, json={"type": "test"})
        assert response.status_code == status.HTTP_200_OK
        mock_agentic_streamable_manager.handle_request.assert_called_once()

    async def test_should_still_require_authentication_when_the_assistant_is_disabled(self, client: AsyncClient):
        response = await client.post("api/v1/agentic/mcp", json={"type": "test"})
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


@pytest.mark.usefixtures("agentic_disabled")
class TestRunAssistantIsGatedPerTool:
    async def test_should_hide_run_assistant_while_the_assistant_is_disabled(self):
        from langflow.api.v1.agentic_mcp import handle_list_tools

        tool_names = {tool.name for tool in await handle_list_tools()}

        assert "run_assistant" not in tool_names

    async def test_should_keep_the_authoring_tools_while_the_assistant_is_disabled(self):
        from langflow.api.v1.agentic_mcp import handle_list_tools

        tool_names = {tool.name for tool in await handle_list_tools()}

        assert {"create_flow", "connect_components", "run_flow", "update_flow_from_spec"} <= tool_names

    async def test_should_refuse_run_assistant_with_an_explanatory_error(self):
        from langflow.api.v1 import agentic_mcp

        with pytest.raises(ValueError, match="LANGFLOW_AGENTIC_EXPERIENCE"):
            await agentic_mcp.handle_call_tool("run_assistant", {"instruction": "build a flow"})


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


class TestAgenticMcpReleasesItsDbSession:
    """The auth dependency's session must be released before the tool call runs.

    FastAPI holds a yield-dependency's session open for the whole request. Every tool here
    issues a loopback REST call needing its own connection, so holding this one across the
    dispatch deadlocks the mount until SQLite's busy_timeout (30s) aborts it -- measured at
    30.02s before the fix, 0.03s after. Asserting the ORDER of the two calls is what pins the
    invariant; reproducing the deadlock itself would take a live server and 30 seconds a run.
    """

    async def test_should_close_the_session_before_dispatching_to_the_transport(self):
        from langflow.api.v1 import agentic_mcp

        calls: list[str] = []
        db = AsyncMock()
        db.close = AsyncMock(side_effect=lambda: calls.append("session_closed"))
        manager = AsyncMock()
        manager.handle_request = AsyncMock(side_effect=lambda *_a: calls.append("dispatched"))

        class FakeRequest:
            base_url = "http://testserver/"
            headers = {"x-api-key": "key-1"}
            scope: dict = {}
            receive = None
            _send = None

        with (
            patch(f"{MODULE}._streamable_http.start", new_callable=AsyncMock),
            patch(f"{MODULE}._streamable_http.get_manager", return_value=manager),
        ):
            await agentic_mcp.handle_agentic_streamable_http(FakeRequest(), current_user=object(), db=db)

        assert calls == ["session_closed", "dispatched"]


@pytest.mark.usefixtures("agentic_enabled")
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
