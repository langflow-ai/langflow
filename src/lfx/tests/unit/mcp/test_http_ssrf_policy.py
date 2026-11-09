"""MCP discovery must enforce the destination policy before opening a session."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import httpx
import pytest
from lfx.base.mcp import util
from lfx.services.deps import get_settings_service
from lfx.utils.ssrf_protection import SSRFProtectionError


@pytest.fixture(autouse=True)
def strict_defaults(monkeypatch):
    for variable in (
        "LANGFLOW_SSRF_PROTECTION_ENABLED",
        "LANGFLOW_SSRF_ALLOWED_HOSTS",
        "LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED",
        "LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK",
    ):
        monkeypatch.delenv(variable, raising=False)

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "ssrf_protection_enabled", True)
    monkeypatch.setattr(settings, "connector_ssrf_validation_enabled", True)
    monkeypatch.setattr(settings, "connector_ssrf_allow_loopback", True)
    monkeypatch.setattr(settings, "ssrf_allowed_hosts", [])


@pytest.mark.parametrize("mode", ["Streamable_HTTP", "SSE"])
@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "[::1]", "169.254.169.254", "10.1.2.3"])
async def test_discovery_blocks_private_targets_before_connect(mode, host):
    client = AsyncMock()
    with pytest.raises(SSRFProtectionError):
        await util.update_tools(
            "test-server", {"mode": mode, "url": f"http://{host}:8000/mcp"}, mcp_streamable_http_client=client
        )
    client.connect_to_server.assert_not_called()


async def test_discovery_preserves_explicit_loopback_allowlist(monkeypatch):
    monkeypatch.setattr(get_settings_service().settings, "ssrf_allowed_hosts", ["127.0.0.1"])
    client = AsyncMock()
    client.connect_to_server.return_value = []
    await util.update_tools("local-server", {"url": "http://127.0.0.1:8000/mcp"}, mcp_streamable_http_client=client)
    client.connect_to_server.assert_awaited_once()


@pytest.mark.parametrize("mode", [None, "sse"])
async def test_direct_session_rejects_loopback_before_sdk_connection(monkeypatch, mode):
    streamable = Mock(side_effect=AssertionError("Unexpected outbound connection"))
    sse = Mock(side_effect=AssertionError("Unexpected outbound connection"))
    monkeypatch.setattr("mcp.client.streamable_http.streamablehttp_client", streamable)
    monkeypatch.setattr("mcp.client.sse.sse_client", sse)
    manager = util.MCPSessionManager()
    with pytest.raises(SSRFProtectionError):
        await manager._create_streamable_http_session(
            "blocked", {"url": "http://127.0.0.1:8000/mcp", "headers": {}, "timeout_seconds": 1}, mode
        )
    streamable.assert_not_called()
    sse.assert_not_called()


async def test_pinned_client_bypasses_environment_proxy(monkeypatch):
    import httpx
    from lfx.utils.ssrf_transport import SSRFProtectedTransport

    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9000")
    async with util.create_mcp_http_client_with_ssl_option(pinned_ips={"mcp.example": ["93.184.216.34"]}) as client:
        transport = client._transport_for_url(httpx.URL("https://mcp.example/mcp"))
        assert isinstance(transport, SSRFProtectedTransport)
        network = transport._pool._network_backend
        network._backend = AsyncMock()
        await network.connect_tcp("mcp.example", 443)
        assert network._backend.connect_tcp.await_args.kwargs["host"] == "93.184.216.34"
        assert client.follow_redirects is False


@pytest.mark.parametrize("host", ["127.0.0.1", "169.254.169.254", "10.1.2.3"])
async def test_rejected_connection_does_not_send_cleanup_request(monkeypatch, host):
    delete = AsyncMock()
    monkeypatch.setattr(httpx.AsyncClient, "delete", delete)
    client = util.MCPStreamableHttpClient()
    try:
        with pytest.raises(SSRFProtectionError):
            async with client:
                await client.connect_to_server(f"http://{host}:8000/mcp", headers={"Authorization": "Bearer secret"})
        delete.assert_not_awaited()
    finally:
        await client._get_session_manager().cleanup_all()


@pytest.mark.parametrize("transport", ["streamable_http", "sse"])
@pytest.mark.parametrize("verify_ssl", [True, False])
@pytest.mark.parametrize("reuse_session", [False, True])
async def test_cleanup_uses_the_session_validated_destination_and_transport(
    monkeypatch, transport, verify_ssl, reuse_session
):
    from lfx.utils.ssrf_transport import SSRFProtectedTransport

    session = MagicMock(
        initialize=AsyncMock(return_value=None),
        list_tools=AsyncMock(return_value=SimpleNamespace(tools=[])),
        session_id="server-session",
    )
    session.__aenter__.return_value = session

    @asynccontextmanager
    async def sdk_transport(*_args, **_kwargs):
        yield (Mock(), Mock(), Mock()) if transport == "streamable_http" else (Mock(), Mock())

    resolver = Mock(return_value=("https://mcp.example/mcp", ["93.184.216.34"]))
    monkeypatch.setattr(util, "validate_and_resolve_url", resolver)
    monkeypatch.setattr(util, "ClientSession", Mock(return_value=session))
    monkeypatch.setattr("mcp.client.streamable_http.streamablehttp_client", sdk_transport)
    monkeypatch.setattr("mcp.client.sse.sse_client", sdk_transport)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9000")
    requests = []

    async def capture_delete(http_client, url, **kwargs):
        configured_transport = http_client._transport_for_url(httpx.URL(url))
        requests.append((http_client, configured_transport, url, kwargs))

    monkeypatch.setattr(httpx.AsyncClient, "delete", capture_delete)
    manager = util.MCPSessionManager()
    client = util.MCPStreamableHttpClient()
    monkeypatch.setattr(client, "_get_session_manager", lambda: manager)
    try:
        await client.connect_to_server(
            "https://mcp.example/mcp",
            headers={"Authorization": "Bearer secret"},
            verify_ssl=verify_ssl,
            preferred_transport="sse" if transport == "sse" else None,
        )
        resolver.side_effect = AssertionError("Cleanup must retain the original DNS validation")
        if reuse_session:
            client = util.MCPStreamableHttpClient()
            monkeypatch.setattr(client, "_get_session_manager", lambda: manager)
            await client.connect_to_server(
                "https://mcp.example/mcp",
                headers={"Authorization": "Bearer secret"},
                verify_ssl=verify_ssl,
                preferred_transport="sse" if transport == "sse" else None,
            )
        await client.disconnect()
        assert len(requests) == 1
        http_client, configured_transport, url, kwargs = requests[0]
        assert isinstance(configured_transport, SSRFProtectedTransport)
        assert configured_transport.pinned_ips == {"mcp.example": ["93.184.216.34"]}
        assert configured_transport._pool._ssl_context.check_hostname is verify_ssl
        assert http_client.follow_redirects is False
        assert url == "https://mcp.example/mcp"
        assert kwargs["headers"] == {"authorization": "Bearer secret", "Mcp-Session-Id": "server-session"}
        assert resolver.call_count == 1
    finally:
        await manager.cleanup_all()
