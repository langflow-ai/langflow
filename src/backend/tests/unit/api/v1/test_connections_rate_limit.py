"""Rate limiting on the connections and integrations routers (INT-14).

Both routers sit in front of credential material and outbound provider calls
(OAuth state minting, token exchange on the callback, health/test checks), so
they share the rate-limit service used by /login and the public flow builds.
These tests pin the 429 contract and the per-endpoint counter namespaces.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from langflow.api.v1 import connections as connections_module
from langflow.services.deps import get_settings_service
from langflow.services.rate_limit import service as rate_limit_service

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.no_blockbuster

_LIMIT = 2
_CALLBACK_URL = "api/v1/connections/oauth/google/callback"
# usePendingConnectionPoll refetches the listing every 2000ms: 30 reads a minute.
_POLLS_PER_MINUTE = 30


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Keep the process-wide memory limiter's counters out of other tests."""
    if rate_limit_service._limiter is not None:
        rate_limit_service._limiter.reset()
    yield
    if rate_limit_service._limiter is not None:
        rate_limit_service._limiter.reset()


def _enable_rate_limit(monkeypatch: pytest.MonkeyPatch, *, limit: int = _LIMIT, read_limit: int | None = None) -> None:
    """Turn the limiter on after login; the fixtures run with it disabled.

    `read_limit` sizes the metadata-read bucket, which is deliberately far more
    generous than the write budget in production; it defaults to `limit` here so
    a case that does not care about the split reads as one allowance.
    """
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_per_minute", limit)
    monkeypatch.setattr(
        settings, "connection_metadata_rate_limit_per_minute", limit if read_limit is None else read_limit
    )
    if rate_limit_service._limiter is not None:
        rate_limit_service._limiter.reset()


def _assert_limited(response) -> None:
    """Pin the throttled response: 429, a Retry-After, and the shared detail message."""
    assert response.status_code == 429, response.text
    assert response.headers["Retry-After"] == "60"
    assert response.json()["detail"] == "Too many requests. Please try again later."


def _create_payload(name: str = "work") -> dict:
    """Body for a connection create; the name is the per-provider handle."""
    return {
        "provider_key": "google_workspace",
        "name": name,
        "display_name": "Work Google",
        "ownership_mode": "user",
        "granted_scopes": ["calendar.readonly"],
        "executing_identity": {
            "identity": "user_delegated",
            "account": {"id": "account-123", "display": "Work", "tenant_id": "tenant-123"},
        },
        "credentials": {
            "access_token": "access-token-do-not-return",
            "token_type": "Bearer",
        },
    }


async def _create_connection(client: AsyncClient, headers: dict[str, str], name: str = "work") -> str:
    """Create a connection and return its id. Callers that need the limiter off do this first."""
    created = await client.post("api/v1/connections", json=_create_payload(name), headers=headers)
    assert created.status_code == 201, created.text
    return created.json()["id"]


@pytest.mark.usefixtures("active_user")
async def test_connection_metadata_reads_are_rate_limited(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The metadata-read bucket admits its allowance and then throttles."""
    _enable_rate_limit(monkeypatch)
    for _ in range(_LIMIT):
        listed = await client.get("api/v1/connections", headers=logged_in_headers)
        assert listed.status_code == 200, listed.text
    _assert_limited(await client.get("api/v1/connections", headers=logged_in_headers))


@pytest.mark.usefixtures("active_user")
async def test_shipped_defaults_admit_a_full_minute_of_the_pending_oauth_poll(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The connections UI polls the listing every 2s while a consent is pending.

    `usePendingConnectionPoll` refetches `GET /connections` on a 2000ms interval
    with `retry: false`, so 30 reads land per minute and a single 429 ends the
    poll for good: the row never flips to authorized and the user is left at a
    stale screen. On the login budget (5/minute) that happened about ten seconds
    into every consent — well before a human finishes authorizing at the
    provider — which is why the read bucket is sized separately. This runs at
    the *shipped* defaults, so lowering them re-breaks the flow here.
    """
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    if rate_limit_service._limiter is not None:
        rate_limit_service._limiter.reset()
    assert settings.connection_metadata_rate_limit_per_minute >= _POLLS_PER_MINUTE

    for poll in range(_POLLS_PER_MINUTE):
        polled = await client.get("api/v1/connections", headers=logged_in_headers)
        assert polled.status_code == 200, f"poll {poll + 1} of {_POLLS_PER_MINUTE}: {polled.text}"


@pytest.mark.parametrize("route", ["create", "update", "revoke", "delete"])
@pytest.mark.usefixtures("active_user")
async def test_every_mutating_crud_route_admits_then_limits(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    route: str,
) -> None:
    """Each mutating CRUD route admits its allowance and then answers 429.

    `test_every_connections_route_checks_the_rate_limit` proves the call is
    present in the source; this proves the call is reached and enforced on the
    write paths, which are the ones that change credential state. Every request
    below targets a distinct connection so nothing but the limiter can change
    the status code between the admitted calls and the rejected one.
    """
    # Fixtures run with the limiter disabled, so the setup rows are free.
    prepared = [
        await _create_connection(client, logged_in_headers, name=f"prepared_{index}") for index in range(_LIMIT + 1)
    ]
    _enable_rate_limit(monkeypatch)

    async def call(index: int):
        """Issue the route under test against the index-th prepared target."""
        if route == "create":
            return await client.post(
                "api/v1/connections", json=_create_payload(f"fresh_{index}"), headers=logged_in_headers
            )
        if route == "update":
            return await client.patch(
                f"api/v1/connections/{prepared[index]}",
                json={"display_name": f"Renamed {index}"},
                headers=logged_in_headers,
            )
        if route == "revoke":
            return await client.post(f"api/v1/connections/{prepared[index]}/revoke", headers=logged_in_headers)
        return await client.delete(f"api/v1/connections/{prepared[index]}", headers=logged_in_headers)

    admitted = {"create": 201, "update": 200, "revoke": 200, "delete": 204}[route]
    for index in range(_LIMIT):
        response = await call(index)
        assert response.status_code == admitted, response.text
    _assert_limited(await call(_LIMIT))


@pytest.mark.usefixtures("active_user")
async def test_mutating_routes_share_one_write_bucket(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every write shares one budget, so a burst cannot be laundered through another verb."""
    connection_id = await _create_connection(client, logged_in_headers)
    _enable_rate_limit(monkeypatch, limit=1)

    renamed = await client.patch(
        f"api/v1/connections/{connection_id}",
        json={"display_name": "Renamed"},
        headers=logged_in_headers,
    )
    assert renamed.status_code == 200, renamed.text

    # The single allowance is now spent for every write route in the namespace.
    _assert_limited(await client.post("api/v1/connections", json=_create_payload("second"), headers=logged_in_headers))
    _assert_limited(await client.post(f"api/v1/connections/{connection_id}/revoke", headers=logged_in_headers))
    _assert_limited(await client.delete(f"api/v1/connections/{connection_id}", headers=logged_in_headers))

    # ...while the metadata reads and the dedicated health bucket are untouched,
    # so the rejections above are the write counter rather than a limiter-wide
    # stop — and a write burst can never throttle the pending-consent poll.
    listed = await client.get("api/v1/connections", headers=logged_in_headers)
    assert listed.status_code == 200, listed.text
    health = await client.post(f"api/v1/connections/{connection_id}/health", headers=logged_in_headers)
    assert health.status_code == 200, health.text


@pytest.mark.usefixtures("active_user")
async def test_exhausted_read_bucket_does_not_block_writes(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The split holds in both directions: a polling tab must not lock the owner out of a rename."""
    connection_id = await _create_connection(client, logged_in_headers)
    _enable_rate_limit(monkeypatch, limit=_LIMIT, read_limit=1)

    listed = await client.get("api/v1/connections", headers=logged_in_headers)
    assert listed.status_code == 200, listed.text
    _assert_limited(await client.get("api/v1/connections", headers=logged_in_headers))

    renamed = await client.patch(
        f"api/v1/connections/{connection_id}",
        json={"display_name": "Renamed"},
        headers=logged_in_headers,
    )
    assert renamed.status_code == 200, renamed.text


@pytest.mark.usefixtures("active_user")
async def test_connection_test_and_health_are_rate_limited(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test and health each own a bucket: both make outbound provider calls."""
    _enable_rate_limit(monkeypatch)
    connection_id = await _create_connection(client, logged_in_headers)

    for _ in range(_LIMIT):
        tested = await client.post(
            f"api/v1/connections/{connection_id}/test",
            json={"required_scopes": []},
            headers=logged_in_headers,
        )
        assert tested.status_code == 200, tested.text
    _assert_limited(
        await client.post(
            f"api/v1/connections/{connection_id}/test",
            json={"required_scopes": []},
            headers=logged_in_headers,
        )
    )

    for _ in range(_LIMIT):
        health = await client.post(f"api/v1/connections/{connection_id}/health", headers=logged_in_headers)
        assert health.status_code == 200, health.text
    _assert_limited(await client.post(f"api/v1/connections/{connection_id}/health", headers=logged_in_headers))


@pytest.mark.usefixtures("active_user")
async def test_oauth_start_is_rate_limited(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Minting OAuth state is throttled before the registration is even resolved."""
    _enable_rate_limit(monkeypatch)
    connection_id = await _create_connection(client, logged_in_headers)
    url = f"api/v1/connections/{connection_id}/oauth/start"
    body = {"registration_id": "unknown", "scopes": ["calendar.readonly"]}

    for _ in range(_LIMIT):
        # The limiter admits the request; the unknown registration fails after.
        started = await client.post(url, json=body, headers=logged_in_headers)
        assert started.status_code == 400, started.text
    _assert_limited(await client.post(url, json=body, headers=logged_in_headers))


async def test_oauth_callback_is_rate_limited(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The callback is unauthenticated: state replaces login, so the IP budget is the throttle."""
    _enable_rate_limit(monkeypatch)
    params = {"state": "a" * 43, "code": "provider-code"}
    for _ in range(_LIMIT):
        response = await client.get(_CALLBACK_URL, params=params)
        assert response.status_code == 400, response.text
    _assert_limited(await client.get(_CALLBACK_URL, params=params))


@pytest.mark.usefixtures("active_user")
async def test_oauth_callback_budget_does_not_consume_oauth_start(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Callback spam must not block a user from starting a consent flow, and vice versa."""
    _enable_rate_limit(monkeypatch, limit=1)
    connection_id = await _create_connection(client, logged_in_headers)

    callback = await client.get(_CALLBACK_URL, params={"state": "b" * 43})
    assert callback.status_code == 400, callback.text
    _assert_limited(await client.get(_CALLBACK_URL, params={"state": "b" * 43}))

    started = await client.post(
        f"api/v1/connections/{connection_id}/oauth/start",
        json={"registration_id": "unknown", "scopes": ["calendar.readonly"]},
        headers=logged_in_headers,
    )
    assert started.status_code == 400, started.text
    _assert_limited(
        await client.post(
            f"api/v1/connections/{connection_id}/oauth/start",
            json={"registration_id": "unknown", "scopes": ["calendar.readonly"]},
            headers=logged_in_headers,
        )
    )

    # Distinct buckets again: health checks are unaffected. The writes share one
    # bucket, and the create above already spent this client's allowance.
    health = await client.post(f"api/v1/connections/{connection_id}/health", headers=logged_in_headers)
    assert health.status_code == 200, health.text
    _assert_limited(await client.post("api/v1/connections", json=_create_payload("another"), headers=logged_in_headers))


@pytest.mark.usefixtures("active_user")
async def test_integrations_endpoints_are_rate_limited(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The integrations catalog and the effective-policy read share one bucket."""
    _enable_rate_limit(monkeypatch)
    for _ in range(_LIMIT):
        listed = await client.get("api/v1/integrations", headers=logged_in_headers)
        assert listed.status_code == 200, listed.text
    # The catalog and the effective-policy read share one counter namespace.
    _assert_limited(await client.get("api/v1/integrations/policy/effective", headers=logged_in_headers))


async def test_rate_limiting_disabled_allows_bursts(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """With the limiter off, no endpoint throttles: the gate is settings-driven."""
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    if rate_limit_service._limiter is not None:
        rate_limit_service._limiter.reset()
    for _ in range(5):
        response = await client.get(_CALLBACK_URL, params={"state": "c" * 43})
        assert response.status_code == 400, response.text


@pytest.mark.usefixtures("active_user")
async def test_oauth_registration_listing_is_rate_limited(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The registration listing rides the metadata-read bucket, not the write budget."""
    _enable_rate_limit(monkeypatch)
    url = "api/v1/connections/oauth/registrations"
    for _ in range(_LIMIT):
        listed = await client.get(url, headers=logged_in_headers)
        assert listed.status_code == 200, listed.text
    _assert_limited(await client.get(url, headers=logged_in_headers))
    # Same bucket as the connection listing, which is also a metadata read.
    _assert_limited(await client.get("api/v1/connections", headers=logged_in_headers))
    # The write budget is untouched: a throttled picker must not block a rename.
    connection_id = await _create_connection(client, logged_in_headers, name="writable")
    renamed = await client.patch(
        f"api/v1/connections/{connection_id}",
        json={"display_name": "Renamed"},
        headers=logged_in_headers,
    )
    assert renamed.status_code == 200, renamed.text


def test_every_connections_route_checks_the_rate_limit() -> None:
    """A new route must not ship unlimited: INT-14-01 covered the whole router."""
    source = Path(connections_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    unlimited = [
        node.name
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef)
        and any(
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and isinstance(decorator.func.value, ast.Name)
            and decorator.func.value.id == "router"
            for decorator in node.decorator_list
        )
        and not any(
            isinstance(call.func, ast.Name) and call.func.id == "check_rate_limit"
            for call in ast.walk(node)
            if isinstance(call, ast.Call)
        )
    ]
    assert unlimited == [], f"connections routes without a rate-limit check: {unlimited}"
