"""Credential destinations, bounded requests, and safe error contracts."""

from dataclasses import replace
from datetime import datetime, timezone

import httpx
import pytest
from lfx.integrations.errors import (
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    IntegrationNetworkError,
    InvalidRequestError,
    ProviderUnavailableError,
    RateLimitedError,
    ResourceNotFoundError,
)
from lfx_gitlab.client import GitLabClient, api_origin, positive_id


@pytest.mark.parametrize("protection_enabled", [True, False])
async def test_default_transport_keeps_redirects_disabled(lease, monkeypatch, protection_enabled):
    from lfx.utils import ssrf_httpx
    from lfx.utils.ssrf_transport import SSRFProtectedTransport

    monkeypatch.setattr(ssrf_httpx, "is_ssrf_protection_enabled", lambda: protection_enabled)
    monkeypatch.setattr(ssrf_httpx, "_validate_and_resolve_strict_url", lambda url: (url, ["172.65.251.78"]))
    async with GitLabClient(lease) as client:
        assert client._client.follow_redirects is False
        assert client._client.trust_env is False
        if protection_enabled:
            assert isinstance(client._client._transport, SSRFProtectedTransport)


async def test_default_transport_dns_failure_is_normalized(lease, monkeypatch):
    from lfx.utils import ssrf_httpx
    from lfx.utils.ssrf_protection import SSRFProtectionError

    def unavailable(_url):
        msg = "private DNS diagnostic"
        raise SSRFProtectionError(msg)

    monkeypatch.setattr(ssrf_httpx, "is_ssrf_protection_enabled", lambda: True)
    monkeypatch.setattr(ssrf_httpx, "_validate_and_resolve_strict_url", unavailable)
    with pytest.raises(IntegrationNetworkError, match=r"could not reach gitlab\.com") as error:
        GitLabClient(lease)
    assert "private DNS diagnostic" not in str(error.value)


@pytest.mark.parametrize(
    "value",
    [
        "http://gitlab.com",
        "https://user:pass@gitlab.com",  # pragma: allowlist secret
        "https://gitlab.com/api/v4",
        "https://127.0.0.1",
        "https://localhost",
        "https://gitlab.com:444",
        "https://gitlab.com?token=x",
        "https://gitlab.com#x",
        "https://gitlab.local",
    ],
)
def test_operator_origin_rejects_unsafe_or_ambiguous_values(monkeypatch, value):
    monkeypatch.setenv("LANGFLOW_GITLAB_ORIGIN", value)
    with pytest.raises((InvalidRequestError, ValueError)):
        api_origin()


@pytest.mark.parametrize("value", [True, 0, -1, "../4", "4/notes", "https://evil", "1?x=2", "01", 1.5])
def test_id_rejects_paths_and_non_integer_values(value):
    with pytest.raises(InvalidRequestError):
        positive_id(value)


@pytest.mark.parametrize(
    "path",
    [
        "https://evil.example/api/v4/projects/1",
        "//evil",
        "/projects/1/../2",
        "/projects/1?x=2",
        "/projects/%31",
        "/projects/1/hooks/2/events",
    ],
)
async def test_client_rejects_arbitrary_paths_before_credentials(lease, path):
    async def fail():
        pytest.fail("Credentials were resolved for a forbidden path")

    lease.get_credential = fail
    async with GitLabClient(lease, transport=httpx.MockTransport(lambda _r: pytest.fail("HTTP"))) as client:
        with pytest.raises(InvalidRequestError):
            await client.request("GET", path)


@pytest.mark.parametrize("fault", ["identity", "origin", "scope", "unverified", "expiry"])
async def test_client_rejects_bad_identity_metadata(lease, fault):
    credential = await lease.get_credential()
    updates = (
        {"identity": "bot"}
        if fault == "identity"
        else {"account": None}
        if fault == "origin"
        else {"granted_scopes": frozenset()}
        if fault == "scope"
        else {"scopes_verified": False}
        if fault == "unverified"
        else {"expires_at": datetime(2000, 1, 1, tzinfo=timezone.utc)}
    )
    lease._credential = replace(credential, **updates)

    async def changed(_request):
        return replace(credential, **updates)

    lease._resolver.resolve = changed
    async with GitLabClient(lease, transport=httpx.MockTransport(lambda _r: pytest.fail("HTTP"))) as client:
        with pytest.raises((ConnectionNotAuthorizedError, AuthExpiredError)):
            await client.request("GET", "/projects/1")


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (301, ProviderUnavailableError),
        (401, AuthExpiredError),
        (403, ConnectionNotAuthorizedError),
        (404, ResourceNotFoundError),
        (429, RateLimitedError),
        (422, InvalidRequestError),
        (503, ProviderUnavailableError),
    ],
)
async def test_errors_never_reflect_provider_secret(lease, status, error):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(
            status,
            json={"error": "test-only-gitlab-token"},
            headers={"location": "https://evil.example", "retry-after": "NaN"},
        )

    async with GitLabClient(lease, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(error) as caught:
            await client.request("GET", "/projects/1")
    assert "test-only-gitlab-token" not in str(caught.value)
    assert len(requests) == 1


async def test_network_failure_redacts_request(lease):
    def handle(request):
        msg = "test-only-gitlab-token"
        raise httpx.ConnectError(msg, request=request)

    async with GitLabClient(lease, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(IntegrationNetworkError) as caught:
            await client.request("GET", "/projects/1")
    assert "test-only-gitlab-token" not in str(caught.value)


@pytest.mark.parametrize("body", [b"null", b"[]bad", b"x" * (2 * 1024 * 1024 + 1)])
async def test_invalid_or_large_response(lease, body):
    async with GitLabClient(
        lease, transport=httpx.MockTransport(lambda _r: httpx.Response(200, content=body))
    ) as client:
        with pytest.raises((ProviderUnavailableError, InvalidRequestError)):
            await client.request("GET", "/projects/1")
