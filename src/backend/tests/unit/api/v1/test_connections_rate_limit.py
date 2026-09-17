"""Rate limiting on the connections and integrations routers (INT-14).

Both routers sit in front of credential material and outbound provider calls
(OAuth state minting, token exchange on the callback, health/test checks), so
they share the rate-limit service used by /login and the public flow builds.
These tests pin the 429 contract and the per-endpoint counter namespaces.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from langflow.services.deps import get_settings_service
from langflow.services.rate_limit import service as rate_limit_service

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.no_blockbuster

_LIMIT = 2
_CALLBACK_URL = "api/v1/connections/oauth/google/callback"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Keep the process-wide memory limiter's counters out of other tests."""
    if rate_limit_service._limiter is not None:
        rate_limit_service._limiter.reset()
    yield
    if rate_limit_service._limiter is not None:
        rate_limit_service._limiter.reset()


def _enable_rate_limit(monkeypatch: pytest.MonkeyPatch, *, limit: int = _LIMIT) -> None:
    """Turn the limiter on after login; the fixtures run with it disabled."""
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_per_minute", limit)
    if rate_limit_service._limiter is not None:
        rate_limit_service._limiter.reset()


def _assert_limited(response) -> None:
    assert response.status_code == 429, response.text
    assert response.headers["Retry-After"] == "60"
    assert response.json()["detail"] == "Too many requests. Please try again later."


def _create_payload() -> dict:
    return {
        "provider_key": "google_workspace",
        "name": "work",
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


async def _create_connection(client: AsyncClient, headers: dict[str, str]) -> str:
    created = await client.post("api/v1/connections", json=_create_payload(), headers=headers)
    assert created.status_code == 201, created.text
    return created.json()["id"]


@pytest.mark.usefixtures("active_user")
async def test_connection_crud_endpoints_are_rate_limited(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_rate_limit(monkeypatch)
    for _ in range(_LIMIT):
        listed = await client.get("api/v1/connections", headers=logged_in_headers)
        assert listed.status_code == 200, listed.text
    _assert_limited(await client.get("api/v1/connections", headers=logged_in_headers))


@pytest.mark.usefixtures("active_user")
async def test_connection_test_and_health_are_rate_limited(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    # Distinct buckets again: health checks are unaffected. Plain CRUD shares
    # one bucket, and the create above already spent this client's allowance.
    health = await client.post(f"api/v1/connections/{connection_id}/health", headers=logged_in_headers)
    assert health.status_code == 200, health.text
    _assert_limited(await client.get("api/v1/connections", headers=logged_in_headers))


@pytest.mark.usefixtures("active_user")
async def test_integrations_endpoints_are_rate_limited(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_rate_limit(monkeypatch)
    for _ in range(_LIMIT):
        listed = await client.get("api/v1/integrations", headers=logged_in_headers)
        assert listed.status_code == 200, listed.text
    # The catalog and the effective-policy read share one counter namespace.
    _assert_limited(await client.get("api/v1/integrations/policy/effective", headers=logged_in_headers))


async def test_rate_limiting_disabled_allows_bursts(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    if rate_limit_service._limiter is not None:
        rate_limit_service._limiter.reset()
    for _ in range(5):
        response = await client.get(_CALLBACK_URL, params={"state": "c" * 43})
        assert response.status_code == 400, response.text
