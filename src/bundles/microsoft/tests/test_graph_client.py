"""Contract tests for the shared Microsoft Graph client."""

from __future__ import annotations

import httpx
import pytest
from lfx.integrations.errors import (
    ActionUnsupportedError,
    AuthExpiredError,
    ProviderUnavailableError,
    RateLimitedError,
    ScopeMissingError,
    normalize_integration_error,
)
from lfx.integrations.models import ConnectionRef, ConnectionResolutionRequest, CredentialLease
from lfx.services.authorization.base import ExecutionPrincipal
from lfx_microsoft.graph import (
    USER_AGENT,
    GraphClient,
    drive_children_path,
    drive_item_path,
    drive_root,
    odata_params,
    prefer_header,
)
from microsoft_testkit import (
    RecordingResolver,
    TransportRecorder,
    credential,
    graph_error,
    graph_fixture,
    json_response,
)


def lease_for(resolver: RecordingResolver) -> CredentialLease:
    request = ConnectionResolutionRequest(
        ref=ConnectionRef(provider="microsoft", name="work"),
        principal=ExecutionPrincipal(kind="actor", user_id="user-1", interactive=True),
    )
    return CredentialLease(resolver, request)


async def test_bearer_and_user_agent_come_from_the_lease() -> None:
    resolver = RecordingResolver([credential("token-a")])
    recorder = TransportRecorder(lambda _request: json_response({"value": []}))
    async with GraphClient(lease_for(resolver), transport=recorder.transport) as client:
        await client.get_json("/me/messages")
    assert recorder.last.headers["authorization"] == "Bearer token-a"
    assert recorder.last.headers["user-agent"] == USER_AGENT


async def test_401_triggers_exactly_one_reactive_reauthorization() -> None:
    resolver = RecordingResolver([credential("stale"), credential("fresh")])
    responses = [
        graph_error("InvalidAuthenticationToken", 401),
        json_response({"value": []}),
    ]
    recorder = TransportRecorder(lambda _request: responses.pop(0))
    async with GraphClient(lease_for(resolver), transport=recorder.transport) as client:
        await client.get_json("/me/messages")
    assert [request.headers["authorization"] for request in recorder.requests] == [
        "Bearer stale",
        "Bearer fresh",
    ]
    assert resolver.calls == 2


async def test_persistent_401_raises_auth_expired_after_one_retry() -> None:
    resolver = RecordingResolver([credential("stale"), credential("also-stale")])
    recorder = TransportRecorder(lambda _request: graph_error("InvalidAuthenticationToken", 401))
    async with GraphClient(lease_for(resolver), transport=recorder.transport) as client:
        with pytest.raises(AuthExpiredError):
            await client.get_json("/me/messages")
    assert len(recorder.requests) == 2
    assert resolver.calls == 2


async def test_403_access_denied_maps_to_scope_missing() -> None:
    resolver = RecordingResolver([credential()])
    recorder = TransportRecorder(lambda _request: graph_error("ErrorAccessDenied", 403))
    async with GraphClient(lease_for(resolver), transport=recorder.transport) as client:
        with pytest.raises(ScopeMissingError):
            await client.get_json("/me/messages")
    assert len(recorder.requests) == 1


async def test_429_carries_retry_after() -> None:
    resolver = RecordingResolver([credential()])
    recorder = TransportRecorder(
        lambda _request: graph_error("activityLimitReached", 429, headers={"Retry-After": "17"})
    )
    async with GraphClient(lease_for(resolver), transport=recorder.transport) as client:
        with pytest.raises(RateLimitedError) as excinfo:
            await client.get_json("/me/messages")
    assert excinfo.value.retry_after == 17.0
    assert excinfo.value.retryable is True


async def test_404_maps_to_action_unsupported() -> None:
    resolver = RecordingResolver([credential()])
    recorder = TransportRecorder(lambda _request: graph_error("itemNotFound", 404))
    async with GraphClient(lease_for(resolver), transport=recorder.transport) as client:
        with pytest.raises(ActionUnsupportedError):
            await client.get_json("/me/drive/items/missing")


async def test_transport_failure_maps_to_provider_unavailable() -> None:
    message = "no route to host"

    def _boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(message, request=request)

    resolver = RecordingResolver([credential()])
    recorder = TransportRecorder(_boom)
    async with GraphClient(lease_for(resolver), transport=recorder.transport) as client:
        with pytest.raises(ProviderUnavailableError):
            await client.get_json("/me/messages")


async def test_paginate_follows_next_link_and_honours_the_limit() -> None:
    pages = [graph_fixture("messages_page1"), graph_fixture("messages_page2")]
    recorder = TransportRecorder(lambda _request: json_response(pages.pop(0)))
    resolver = RecordingResolver([credential()])
    async with GraphClient(lease_for(resolver), transport=recorder.transport) as client:
        items, next_link = await client.paginate("/me/messages", params={"$top": 3}, limit=3)
    assert [item["id"] for item in items] == [
        "AAMkAGI2TG93AAA=",
        "AAMkAGI2TG94AAA=",
        "AAMkAGI2TG95AAA=",
    ]
    assert next_link is None
    assert str(recorder.requests[1].url) == "https://graph.microsoft.com/v1.0/me/messages?%24skip=2"


async def test_paginate_stops_at_the_limit_and_returns_the_unfollowed_link() -> None:
    recorder = TransportRecorder(lambda _request: json_response(graph_fixture("messages_page1")))
    resolver = RecordingResolver([credential()])
    async with GraphClient(lease_for(resolver), transport=recorder.transport) as client:
        items, next_link = await client.paginate("/me/messages", limit=2)
    assert len(items) == 2
    assert next_link == "https://graph.microsoft.com/v1.0/me/messages?%24skip=2"
    assert len(recorder.requests) == 1


async def test_download_follows_the_302_without_the_bearer_header() -> None:
    download_url = "https://contoso-my.sharepoint.com/personal/_layouts/15/download.aspx?SECRET=preauth"

    def _handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "graph.microsoft.com":
            return httpx.Response(302, headers={"Location": download_url})
        return httpx.Response(200, content=b"hello from onedrive")

    recorder = TransportRecorder(_handler)
    resolver = RecordingResolver([credential()])
    async with GraphClient(lease_for(resolver), transport=recorder.transport) as client:
        content = await client.download("/me/drive/items/item-1/content")

    assert content == b"hello from onedrive"
    assert "authorization" in recorder.requests[0].headers
    assert "authorization" not in recorder.requests[1].headers
    assert str(recorder.requests[1].url) == download_url


async def test_download_truncates_at_max_bytes() -> None:
    recorder = TransportRecorder(lambda _request: httpx.Response(200, content=b"0123456789"))
    resolver = RecordingResolver([credential()])
    async with GraphClient(lease_for(resolver), transport=recorder.transport) as client:
        content = await client.download("/me/drive/items/item-1/content", max_bytes=4)
    assert content == b"0123"


async def test_download_stops_reading_the_redirect_body_at_max_bytes() -> None:
    """``max_bytes`` bounds memory: the stream is abandoned, not trimmed after the fact."""
    download_url = "https://contoso-my.sharepoint.com/_layouts/15/download.aspx?SECRET=preauth"
    served: list[int] = []

    async def _chunks():
        for index in range(100):
            served.append(index)
            yield b"x" * 1024

    def _handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "graph.microsoft.com":
            return httpx.Response(302, headers={"Location": download_url})
        return httpx.Response(200, content=_chunks())

    recorder = TransportRecorder(_handler)
    resolver = RecordingResolver([credential()])
    async with GraphClient(lease_for(resolver), transport=recorder.transport) as client:
        content = await client.download("/me/drive/items/item-1/content", max_bytes=2048)

    assert len(content) == 2048
    # Three chunks at most: the third is what trips the cap. The remaining 97
    # were never pulled off the wire.
    assert len(served) <= 3


async def test_download_refuses_a_non_https_redirect_target() -> None:
    """A redirect is a header on a response we then fetch; only absolute TLS URLs are followed."""
    recorder = TransportRecorder(
        lambda _request: httpx.Response(302, headers={"Location": "http://169.254.169.254/latest/meta-data/"})
    )
    resolver = RecordingResolver([credential()])
    async with GraphClient(lease_for(resolver), transport=recorder.transport) as client:
        with pytest.raises(ProviderUnavailableError):
            await client.download("/me/drive/items/item-1/content")

    # Only the Graph call happened; the redirect target was never dialled.
    assert len(recorder.requests) == 1


def test_registered_normalizer_is_used_by_the_shared_vocabulary() -> None:
    request = httpx.Request("GET", "https://graph.microsoft.com/v1.0/me/messages")
    response = httpx.Response(403, json={"error": {"code": "ErrorAccessDenied"}}, request=request)
    error = normalize_integration_error(
        httpx.HTTPStatusError("denied", request=request, response=response),
        provider="microsoft",
    )
    assert isinstance(error, ScopeMissingError)
    assert error.code == "scope-missing"


def test_odata_params_clamps_top_and_quotes_search() -> None:
    params = odata_params(top=5000, select=["id", " subject "], search="budget", order_by="name asc")
    assert params["$top"] == 999
    assert params["$select"] == "id,subject"
    assert params["$search"] == '"budget"'
    assert params["$orderby"] == "name asc"


def test_prefer_header_composes_timezone_and_body_type() -> None:
    assert prefer_header(None) == {}
    assert prefer_header("UTC") == {"Prefer": 'outlook.timezone="UTC"'}
    assert prefer_header("UTC", body_as_text=True) == {
        "Prefer": 'outlook.timezone="UTC", outlook.body-content-type=text'
    }


def test_drive_path_helpers_cover_the_three_scopes() -> None:
    assert drive_root() == "/me/drive"
    assert drive_root("b!drive") == "/drives/b!drive"
    assert drive_root("", "site-1") == "/sites/site-1/drive"
    # A drive id wins over a site id.
    assert drive_root("b!drive", "site-1") == "/drives/b!drive"
    assert drive_children_path("/me/drive") == "/me/drive/root/children"
    assert drive_children_path("/me/drive", "item-1") == "/me/drive/items/item-1/children"
    assert drive_children_path("/me/drive", "", "/Reports/2026") == "/me/drive/root:/Reports/2026:/children"
    assert drive_item_path("/me/drive", "item-1", suffix="/content") == "/me/drive/items/item-1/content"
    assert drive_item_path("/me/drive", "", "notes.txt", suffix="/content") == "/me/drive/root:/notes.txt:/content"
