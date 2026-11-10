"""Provider continuation URLs never move delegated tokens off the API origin."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from langflow.services.triggers.source_clients import GRAPH_ORIGIN, SourceHTTP
from lfx.integrations.errors import RateLimitedError


class _Lease:
    ref = SimpleNamespace(provider="google")

    async def get_token(self) -> str:
        return "test-token"


async def test_graph_continuation_stays_on_graph_origin() -> None:
    seen: list[str] = []

    def reply(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        assert request.headers["Authorization"] == "Bearer test-token"
        return httpx.Response(200, json={"value": []})

    async with SourceHTTP(_Lease(), origin=GRAPH_ORIGIN, transport=httpx.MockTransport(reply)) as client:
        assert await client.request("GET", "https://graph.microsoft.com/v1.0/me/messages/delta?$deltatoken=opaque") == {
            "value": []
        }
        with pytest.raises(ValueError, match="API origin"):
            await client.request("GET", "https://evil.example/v1.0/me/messages/delta")
    assert len(seen) == 1


async def test_google_quota_403_uses_retry_after() -> None:
    def reply(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={"Retry-After": "17"},
            json={"error": {"errors": [{"reason": "userRateLimitExceeded"}]}},
        )

    async with SourceHTTP(
        _Lease(), origin="https://www.googleapis.com", transport=httpx.MockTransport(reply)
    ) as client:
        with pytest.raises(RateLimitedError) as exc:
            await client.request("GET", "drive/v3/changes")
    assert exc.value.retry_after == 17
