"""INT-14 GA: the 60-second refresh skew and rotating-refresh-token reuse rules.

``broker.refresh_if_needed`` refreshes a stored OAuth credential when its expiry
is inside a 60-second skew window, or when the caller reports the provider
rejected exactly the stored access token (``rejected_token_digest``). A token
fresh beyond the skew, or a rejection digest that does not match what is stored,
must never trigger a provider call.

The last two tests cover the other side of the same call: what a refresh means
when it fails before it starts, because *this* process cannot see the OAuth
registration the connection was authorized under.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import pytest
from langflow.services.connection.oauth import providers
from langflow.services.connection.oauth.broker import digest
from langflow.services.connection.service import _decrypt_credential_payload, _encrypt_credential_payload
from langflow.services.database.models.connection import ConnectionSecret
from langflow.services.deps import get_connection_resolver_service, session_scope
from lfx.integrations.errors import AuthExpiredError, ConnectionUnresolvedError
from lfx.integrations.models import ConnectionRef, ConnectionResolutionRequest
from lfx.services.authorization.base import ExecutionPrincipal

pytestmark = pytest.mark.no_blockbuster

STORED_ACCESS_TOKEN = "stored-access-must-not-leak"  # noqa: S105 - test fixture


def _registration() -> dict:
    """A desktop public-client OAuth registration for the fixture connection."""
    return {
        "provider": "google",
        "client_id": "test-client",
        "client_type": "public",
        "context": "desktop",
        "redirect_uri": "http://localhost/api/v1/connections/oauth/google/callback",
        "scopes": ["calendar.readonly"],
    }


@pytest.fixture
def oauth_config(monkeypatch):
    """Point the broker at the fixture registration in the desktop context."""
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_CONTEXT", "desktop")
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS", json.dumps({"google-work": _registration()}))


def _resolution(owner_id: str, **overrides) -> ConnectionResolutionRequest:
    """A resolution request for the fixture connection's owner, with optional overrides."""
    request = ConnectionResolutionRequest(
        ref=ConnectionRef(provider="google", name="work"),
        principal=ExecutionPrincipal(kind="actor", user_id=owner_id, actor_id=owner_id, interactive=True),
    )
    return replace(request, **overrides) if overrides else request


async def _rewrite_stored_payload(connection_id: str, **changes) -> dict:
    """Edit the stored envelope the way token age or rotation would have."""
    async with session_scope() as session:
        secret = await session.get(ConnectionSecret, UUID(connection_id))
        assert secret is not None
        payload = _decrypt_credential_payload(secret.encrypted_payload)
        payload.update(changes)
        secret.encrypted_payload = _encrypt_credential_payload(json.dumps(payload))
        session.add(secret)
        return payload


async def _read_stored_payload(connection_id: str) -> dict:
    """Decrypt the stored credential envelope so the test can assert on what persisted."""
    async with session_scope() as session:
        secret = await session.get(ConnectionSecret, UUID(connection_id))
        assert secret is not None
        return _decrypt_credential_payload(secret.encrypted_payload)


@pytest.fixture
async def authorized_connection(client, logged_in_headers, oauth_config, monkeypatch):  # noqa: ARG001
    """A ready connection whose stored credential the tests then age or reject."""
    created = await client.post(
        "/api/v1/connections",
        headers=logged_in_headers,
        json={
            "provider_key": "google",
            "name": "work",
            "display_name": "Google work",
            "executing_identity": {"identity": "user_delegated"},
        },
    )
    assert created.status_code == 201, created.text
    row = created.json()
    started = await client.post(
        f"/api/v1/connections/{row['id']}/oauth/start",
        headers=logged_in_headers,
        json={"registration_id": "google-work", "scopes": ["calendar.readonly"]},
    )
    assert started.status_code == 200, started.text
    query = parse_qs(urlsplit(started.json()["authorization_url"]).query)

    async def initial_exchange(_url, data, **_kwargs):
        assert data["grant_type"] == "authorization_code"
        return {
            "access_token": STORED_ACCESS_TOKEN,
            "refresh_token": "stored-refresh-token",
            "expires_in": 3600,
            "scope": "calendar.readonly",
            "token_type": "Bearer",
        }

    monkeypatch.setattr(providers, "_request", initial_exchange)
    completed = await client.get(
        "/api/v1/connections/oauth/google/callback",
        params={"state": query["state"][0], "code": "temporary-code"},
    )
    assert completed.status_code == 200, completed.text
    return row


def _recording_refresh(monkeypatch, *, omit_refresh_token: bool = False) -> list[dict]:
    """Stub the provider refresh call and return the list it records requests into."""
    calls: list[dict] = []

    async def refresh(_url, data, **_kwargs):
        calls.append(data)
        assert data["grant_type"] == "refresh_token"
        body = {
            "access_token": f"rotated-{len(calls)}",
            "expires_in": 3600,
            "scope": "calendar.readonly",
        }
        if not omit_refresh_token:
            body["refresh_token"] = f"rotated-refresh-{len(calls)}"
        return body

    monkeypatch.setattr(providers, "_request", refresh)
    return calls


async def test_token_inside_the_sixty_second_skew_is_refreshed(authorized_connection, monkeypatch):
    """A token expiring inside the 60s skew is refreshed before it is handed out."""
    row = authorized_connection
    await _rewrite_stored_payload(
        row["id"], expires_at=(datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()
    )
    calls = _recording_refresh(monkeypatch)

    credential = await get_connection_resolver_service().resolve(_resolution(row["owner_id"]))

    assert len(calls) == 1
    assert calls[0]["refresh_token"] == "stored-refresh-token"  # noqa: S105 - test fixture
    assert credential.access_token.get_secret_value() == "rotated-1"
    assert STORED_ACCESS_TOKEN not in repr(credential)


async def test_token_fresh_beyond_the_skew_is_not_refreshed(authorized_connection, monkeypatch):
    """A token expiring past the skew is used as stored: no needless rotation."""
    row = authorized_connection
    await _rewrite_stored_payload(
        row["id"], expires_at=(datetime.now(timezone.utc) + timedelta(seconds=90)).isoformat()
    )
    calls = _recording_refresh(monkeypatch)

    credential = await get_connection_resolver_service().resolve(_resolution(row["owner_id"]))

    assert calls == []
    assert credential.access_token.get_secret_value() == STORED_ACCESS_TOKEN


async def test_rejected_token_digest_forces_refresh_of_a_fresh_token(authorized_connection, monkeypatch):
    """A provider rejection of the stored token refreshes it even when it looks fresh."""
    row = authorized_connection
    calls = _recording_refresh(monkeypatch)

    credential = await get_connection_resolver_service().resolve(
        _resolution(row["owner_id"], rejected_token_digest=digest(STORED_ACCESS_TOKEN))
    )

    assert len(calls) == 1
    assert credential.access_token.get_secret_value() == "rotated-1"


async def test_mismatched_rejected_token_digest_leaves_a_fresh_token_alone(authorized_connection, monkeypatch):
    """A rejection of some other token generation must not rotate this credential."""
    row = authorized_connection
    calls = _recording_refresh(monkeypatch)

    credential = await get_connection_resolver_service().resolve(
        _resolution(row["owner_id"], rejected_token_digest=digest("a-different-older-generation"))
    )

    assert calls == []
    assert credential.access_token.get_secret_value() == STORED_ACCESS_TOKEN


async def test_refresh_without_a_replacement_keeps_the_stored_refresh_token(authorized_connection, monkeypatch):
    """A provider that omits a new refresh token must not erase the stored one."""
    row = authorized_connection
    await _rewrite_stored_payload(row["id"], expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
    calls = _recording_refresh(monkeypatch, omit_refresh_token=True)

    credential = await get_connection_resolver_service().resolve(_resolution(row["owner_id"]))

    assert len(calls) == 1
    assert credential.access_token.get_secret_value() == "rotated-1"
    stored = await _read_stored_payload(row["id"])
    assert stored["refresh_token"] == "stored-refresh-token"  # noqa: S105 - test fixture
    assert stored["access_token"] == "rotated-1"  # noqa: S105 - test fixture


async def test_expired_oauth_credential_without_a_refresh_token_is_auth_expired(authorized_connection, monkeypatch):
    """An expired token with nothing to refresh from raises auth-expired, carrying no token material."""
    row = authorized_connection
    await _rewrite_stored_payload(
        row["id"],
        expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
        refresh_token=None,
    )
    calls = _recording_refresh(monkeypatch)

    with pytest.raises(AuthExpiredError) as caught:
        await get_connection_resolver_service().resolve(_resolution(row["owner_id"]))

    assert caught.value.code == "auth-expired"
    assert calls == []
    assert STORED_ACCESS_TOKEN not in str(caught.value)
    assert STORED_ACCESS_TOKEN not in repr(vars(caught.value))


async def test_a_process_without_the_registrations_reports_configuration_not_expiry(authorized_connection, monkeypatch):
    """LE-2479 finding 3: the refresh fails locally, so nothing may look revoked.

    A listener deployed with only a database URL and a secret key holds
    OAuth-backed connections it cannot refresh, because refresh happens in that
    process rather than over HTTP to the API. Reporting ``auth-expired`` there
    is what made every affected trigger disarm itself: the consent is intact,
    the provider was never contacted, and only the process's environment is
    wrong.
    """
    row = authorized_connection
    await _rewrite_stored_payload(row["id"], expires_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat())
    calls = _recording_refresh(monkeypatch)
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS", "{}")

    with pytest.raises(ConnectionUnresolvedError) as caught:
        await get_connection_resolver_service().resolve(_resolution(row["owner_id"]))

    assert caught.value.reason == "registration-unavailable"
    assert calls == [], "the refresh must fail before it reaches the provider's token endpoint"


async def test_a_health_check_without_the_registrations_leaves_the_connection_alone(
    authorized_connection, client, logged_in_headers, monkeypatch
):
    """The same failure must not write ``expired`` onto a connection that works.

    An expired connection is one the listener supervisor stops dialling
    altogether, so a health check run on a misconfigured process could disarm
    every trigger on the connection by itself - without an adapter ever failing.
    """
    row = authorized_connection
    await _rewrite_stored_payload(row["id"], expires_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat())
    _recording_refresh(monkeypatch)
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS", "{}")

    checked = await client.post(f"/api/v1/connections/{row['id']}/health", headers=logged_in_headers)

    assert checked.status_code == 200, checked.text
    body = checked.json()
    assert body["status"] == "ready", "the credential is intact; only this process is misconfigured"
    assert body["health"] == "unhealthy"
