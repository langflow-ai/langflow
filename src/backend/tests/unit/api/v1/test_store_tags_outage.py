"""A Langflow Store outage must not surface as a server fault.

``GET /api/v1/store/tags`` proxies a third-party service. Every route in
``store.py`` funnels an unreachable upstream into a bare ``except Exception`` and
answers ``500``, and the visual editor calls this one on **every** app boot, on
every route. When ``api.langflow.store`` started serving a certificate for
``*.<id>.us-east-1.cs.amazonlightsail.com`` instead of its own hostname, that
turned into a 500 on every page load and wiped the whole Playwright suite, whose
fixture fails any test that sees an unexpected server error.

The store being down is not this server's fault, and tags are a decorative
filter list, so an unreachable upstream degrades to an empty list. Anything else
still reports ``500`` -- a real bug in our own code must stay loud.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import AsyncClient

MODULE = "langflow.api.v1.store"

# The exact error the broken certificate produced, verified against the live host.
SSL_HOSTNAME_MISMATCH = (
    "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: Hostname mismatch, "
    "certificate is not valid for 'api.langflow.store'. (_ssl.c:1032)"
)


def _store_service(side_effect):
    service = AsyncMock()
    service.get_tags = AsyncMock(side_effect=side_effect)
    return service


@pytest.mark.parametrize(
    "upstream_error",
    [
        httpx.ConnectError(SSL_HOSTNAME_MISMATCH),
        httpx.ConnectTimeout("timed out"),
        httpx.ReadTimeout("timed out"),
        httpx.RemoteProtocolError("peer closed connection"),
    ],
    ids=["ssl_hostname_mismatch", "connect_timeout", "read_timeout", "protocol_error"],
)
async def test_should_return_no_tags_when_the_store_is_unreachable(
    client: AsyncClient, logged_in_headers, upstream_error
):
    with patch(f"{MODULE}.get_store_service", return_value=_store_service(upstream_error)):
        response = await client.get("api/v1/store/tags", headers=logged_in_headers)

    assert response.status_code == 200, f"a store outage surfaced as {response.status_code}"
    assert response.json() == []


async def test_should_still_report_an_unexpected_failure_as_a_server_error(client: AsyncClient, logged_in_headers):
    """A bug in our own code must not be silenced by the outage carve-out."""
    with patch(f"{MODULE}.get_store_service", return_value=_store_service(TypeError("boom"))):
        response = await client.get("api/v1/store/tags", headers=logged_in_headers)

    assert response.status_code == 500


async def test_should_return_the_tags_when_the_store_is_reachable(client: AsyncClient, logged_in_headers):
    service = AsyncMock()
    tag_id = "3f8a1c2e-0d4b-4a6f-9c11-7e5b2d8a0f31"
    service.get_tags = AsyncMock(return_value=[{"id": tag_id, "name": "Agents"}])

    with patch(f"{MODULE}.get_store_service", return_value=service):
        response = await client.get("api/v1/store/tags", headers=logged_in_headers)

    assert response.status_code == 200
    assert response.json() == [{"id": tag_id, "name": "Agents"}]
