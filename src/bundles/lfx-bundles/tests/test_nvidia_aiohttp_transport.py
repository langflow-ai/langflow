import ssl
from unittest.mock import AsyncMock

import aiohttp
import pytest
from lfx.utils.ssrf_protection import SSRFProtectionError
from lfx_bundles.nvidia._transport import pin_aiohttp_session


@pytest.mark.parametrize(
    ("base_url", "host_header", "server_name", "ips", "port"),
    [
        (
            "https://exämple.test:8443/v1",
            "xn--exmple-cua.test:8443",
            "xn--exmple-cua.test",
            ["2001:db8::12", "192.0.2.12"],
            8443,
        ),
        ("https://[2001:db8::11]/v1", "[2001:db8::11]", "2001:db8::11", ["2001:db8::11"], 443),
    ],
)
async def test_pinned_connection_keeps_tls_and_host(monkeypatch, base_url, host_header, server_name, ips, port):
    tls_context = ssl.create_default_context()
    connector = aiohttp.TCPConnector(ssl=tls_context)
    timeout = aiohttp.ClientTimeout(sock_read=29)
    connect = AsyncMock(side_effect=RuntimeError("captured connection"))
    resolve = AsyncMock(side_effect=AssertionError("unexpected DNS lookup"))
    monkeypatch.setattr(connector, "_wrap_create_connection", connect)
    monkeypatch.setattr(connector, "_resolve_host", resolve)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        pin_aiohttp_session(session, base_url, ips)
        with pytest.raises(RuntimeError, match="captured connection"):
            await session.post(f"{base_url}/chat/completions")

    resolve.assert_not_awaited()
    connection = connect.await_args.kwargs
    assert [info[-1][:2] for info in connection["addr_infos"]] == [(ip, port) for ip in ips]
    assert connection["req"].headers["Host"] == host_header
    assert connection["server_hostname"] == server_name
    assert connection["ssl"] is tls_context
    assert connection["timeout"] is timeout


async def test_only_explicitly_trusted_origin_uses_sdk_resolver(monkeypatch):
    base_url = "https://provider.test/v1"
    connector = aiohttp.TCPConnector()
    resolve = AsyncMock(side_effect=RuntimeError("captured DNS lookup"))
    monkeypatch.setattr(connector, "_resolve_host", resolve)

    async with aiohttp.ClientSession(connector=connector) as session:
        pin_aiohttp_session(session, base_url, ["192.0.2.15"], trusted_origins=("https://polling.test",))
        with pytest.raises(SSRFProtectionError):
            await session.get("https://unknown.test/v1/models")
        with pytest.raises(SSRFProtectionError, match="proxy"):
            await session.get(base_url, proxy="http://proxy.test")
        resolve.assert_not_awaited()

        with pytest.raises(RuntimeError, match="captured DNS lookup"):
            await session.get("https://polling.test/status")
        assert resolve.await_args.args[:2] == ("polling.test", 443)
