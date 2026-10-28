"""MCP discovery must enforce the destination policy before opening a session."""

from unittest.mock import AsyncMock, Mock

import pytest
from lfx.base.mcp import util
from lfx.services.deps import get_settings_service
from lfx.utils.ssrf_protection import SSRFProtectionError


@pytest.fixture(autouse=True)
def strict_defaults(monkeypatch):
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
