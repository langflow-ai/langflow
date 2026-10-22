"""Exercise the real GitHub transport at identity, retry, and size boundaries."""

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
from lfx_github.client import GitHubClient, bounded_text, positive_id, repository_path


async def test_fixed_origin_identity_probe_and_request(lease):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, json={"id": 7})

    async with GitHubClient(lease, transport=httpx.MockTransport(handle)) as client:
        assert await client.request("GET", repository_path("org/repo")) == {"id": 7}
    assert [str(call.url) for call in calls] == [
        "https://api.github.com/installation/repositories?per_page=1",
        "https://api.github.com/repos/org/repo",
    ]
    assert all(call.headers["authorization"] == "Bearer test-installation-1" for call in calls)
    assert calls[-1].headers["x-github-api-version"] == "2022-11-28"


async def test_pat_rejected_by_installation_endpoint_before_mutation(lease):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(403, json={"message": "private provider text"})

    async with GitHubClient(lease, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ConnectionNotAuthorizedError) as error:
            await client.request("POST", "/repos/org/repo/issues", body={"title": "one"})
    assert len(calls) == 1
    assert "private provider text" not in str(error.value)


async def test_refresh_rechecks_installation_identity_before_write(lease):
    calls = []

    def handle(request):
        calls.append((request.url.path, request.headers["authorization"]))
        if request.url.path.endswith("/issues") and request.headers["authorization"].endswith("-1"):
            return httpx.Response(401)
        return httpx.Response(200, json={"id": 2})

    async with GitHubClient(lease, transport=httpx.MockTransport(handle)) as client:
        assert await client.request("POST", "/repos/org/repo/issues", body={"title": "one"}) == {"id": 2}
    assert calls == [
        ("/installation/repositories", "Bearer test-installation-1"),
        ("/repos/org/repo/issues", "Bearer test-installation-1"),
        ("/installation/repositories", "Bearer test-installation-2"),
        ("/repos/org/repo/issues", "Bearer test-installation-2"),
    ]


async def test_second_rejection_stops_refresh(lease):
    async with GitHubClient(lease, transport=httpx.MockTransport(lambda _request: httpx.Response(401))) as client:
        with pytest.raises(AuthExpiredError):
            await client.request("GET", "/repos/org/repo")
    assert lease._resolver.calls == 2


@pytest.mark.parametrize(
    ("status", "headers", "error"),
    [
        (429, {"Retry-After": "13"}, RateLimitedError),
        (403, {"x-ratelimit-remaining": "0"}, RateLimitedError),
        (403, {}, ConnectionNotAuthorizedError),
        (404, {}, ResourceNotFoundError),
        (422, {}, InvalidRequestError),
        (503, {}, ProviderUnavailableError),
        (302, {"location": "https://evil.example"}, ProviderUnavailableError),
    ],
)
async def test_error_statuses_do_not_repeat_writes(lease, status, headers, error):
    calls = []

    def handle(request):
        calls.append(request)
        return (
            httpx.Response(200, json={})
            if request.url.path.startswith("/installation/")
            else httpx.Response(status, headers=headers, json={"token": "must-stay-private"})
        )

    async with GitHubClient(lease, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(error) as raised:
            await client.request("POST", "/repos/org/repo/issues", body={"title": "one"})
    assert len(calls) == 2
    assert "must-stay-private" not in str(raised.value)
    if status == 429:
        assert raised.value.retry_after == 13


async def test_timeout_does_not_retry_mutation(lease):
    calls = []

    def handle(request):
        calls.append(request)
        if request.url.path.startswith("/installation/"):
            return httpx.Response(200, json={})
        msg = "secret provider detail"
        raise httpx.ReadTimeout(msg)

    async with GitHubClient(lease, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(IntegrationNetworkError) as error:
            await client.request("POST", "/repos/org/repo/issues", body={"title": "one"})
    assert len(calls) == 2
    assert "secret provider detail" not in str(error.value)


async def test_request_and_response_size_limits(lease):
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, content=b"x" * (2 * 1024 * 1024 + 1)))
    async with GitHubClient(lease, transport=transport) as client:
        with pytest.raises(InvalidRequestError, match="64 KiB"):
            await client._request("POST", "/repos/org/repo/issues", body={"body": "x" * 70000})
        with pytest.raises(InvalidRequestError, match="2 MiB"):
            await client._request("GET", "/repos/org/repo")


@pytest.mark.parametrize(
    "value",
    [
        "https://github.com/o/r",
        "o/r/../../",
        "o/..",
        "o/r?q=x",
        "o/r#frag",
        "o/r%2f..",
        "o/r\\x",
        "o/r/",
        "o/r@host",
        "o/",
        "a:b/c",
    ],
)
def test_repository_rejects_url_and_path_injection(value):
    with pytest.raises(InvalidRequestError):
        repository_path(value)


@pytest.mark.parametrize("value", [0, -1, True, "2/../../", "01", "1.0", 1.5, None, 2**63])
def test_number_rejects_noncanonical_values(value):
    with pytest.raises(InvalidRequestError):
        positive_id(value)


@pytest.mark.parametrize("value", ["x" * 60001, "\ud800", 4, None])
def test_text_bounds(value):
    with pytest.raises(InvalidRequestError):
        bounded_text(value)


async def test_arbitrary_paths_never_reach_transport(lease):
    async with GitHubClient(
        lease, transport=httpx.MockTransport(lambda _request: pytest.fail("unexpected network"))
    ) as client:
        for path in ["https://evil.example/", "/repos/org/repo/../hooks", "//evil.example", "/repos/org/repo?x"]:
            with pytest.raises(InvalidRequestError):
                await client._request("GET", path)


async def test_temporary_clone_credentials_never_enter_component_results(lease):
    response = {
        "id": 80,
        "temp_clone_token": "provider-issued-private",
        "nested": {"access_token": "private", "safe": True},
    }
    async with GitHubClient(
        lease, transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=response))
    ) as client:
        result = await client.request("GET", "/repos/org/repo")
    assert result == {"id": 80, "nested": {"safe": True}}
