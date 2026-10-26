"""Default transport construction and safe connection failures."""

import pytest
from lfx.integrations.errors import IntegrationNetworkError
from lfx.utils import ssrf_httpx
from lfx.utils.ssrf_protection import SSRFProtectionError
from lfx.utils.ssrf_transport import SSRFProtectedTransport
from lfx_confluence.client import http_client


@pytest.mark.parametrize("protection_enabled", [True, False])
async def test_default_transport_keeps_redirects_disabled(monkeypatch, protection_enabled):
    monkeypatch.setattr(ssrf_httpx, "is_ssrf_protection_enabled", lambda: protection_enabled)
    monkeypatch.setattr(ssrf_httpx, "_validate_and_resolve_strict_url", lambda url: (url, ["93.184.216.34"]))
    async with http_client() as client:
        assert client.follow_redirects is False
        assert client.trust_env is False
        if protection_enabled:
            assert isinstance(client._transport, SSRFProtectedTransport)
            assert client._transport.pinned_ips == {"api.atlassian.com": ["93.184.216.34"]}


async def test_default_transport_dns_failure_is_normalized(monkeypatch):
    def unavailable(_url):
        msg = "private DNS diagnostic"
        raise SSRFProtectionError(msg)

    monkeypatch.setattr(ssrf_httpx, "_validate_and_resolve_strict_url", unavailable)
    with pytest.raises(IntegrationNetworkError, match=r"could not reach api\.atlassian\.com") as error:
        http_client()
    assert "private DNS diagnostic" not in str(error.value)
