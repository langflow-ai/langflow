"""OAuth consent and refresh regressions against the real connection API and DB."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import pytest
from langflow.services.auth import utils as auth_utils
from langflow.services.connection.oauth import providers
from langflow.services.connection.oauth.config import OAuthError
from langflow.services.connection.service import _decrypt_credential_payload, _encrypt_credential_payload
from langflow.services.database.models.connection import ConnectionSecret
from langflow.services.database.models.connection.oauth import ConnectionOAuth
from langflow.services.deps import get_connection_resolver_service, session_scope
from lfx.integrations.errors import AuthExpiredError, ConnectionUnresolvedError, ScopeMissingError
from lfx.integrations.models import ConnectionRef, ConnectionResolutionRequest, CredentialLease
from lfx.services.authorization.base import ExecutionPrincipal

pytestmark = pytest.mark.no_blockbuster


def registration(**kwargs):
    return {
        "provider": "google",
        "client_id": "test-client",
        "client_type": "public",
        "context": "desktop",
        "redirect_uri": "http://localhost/api/v1/connections/oauth/google/callback",
        "scopes": ["calendar.readonly"],
        **kwargs,
    }


@pytest.fixture
def oauth_config(monkeypatch):
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_CONTEXT", "desktop")
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS", json.dumps({"google-work": registration()}))


async def begin(client, headers):
    created = await client.post(
        "/api/v1/connections",
        headers=headers,
        json={
            "provider_key": "google",
            "name": "work",
            "display_name": "Google work",
            "executing_identity": {"identity": "user_delegated"},
            "allow_non_interactive": True,
        },
    )
    assert created.status_code == 201, created.text
    row = created.json()
    started = await client.post(
        f"/api/v1/connections/{row['id']}/oauth/start",
        headers=headers,
        json={"registration_id": "google-work", "scopes": ["calendar.readonly"]},
    )
    assert started.status_code == 200, started.text
    assert "HttpOnly" in started.headers["set-cookie"]
    assert "SameSite=lax" in started.headers["set-cookie"]
    query = parse_qs(urlsplit(started.json()["authorization_url"]).query)
    assert query["code_challenge_method"] == ["S256"]
    assert "client_secret" not in query
    return row, query


def resolution(row):
    return ConnectionResolutionRequest(
        ref=ConnectionRef(provider="google", name="work"),
        principal=ExecutionPrincipal(kind="actor", user_id=row["owner_id"], actor_id=row["owner_id"], interactive=True),
    )


def provider_double(monkeypatch, query, *, reject=False):
    calls = []

    async def request(url, data, **_kwargs):
        calls.append(data)
        if "revoke" in url:
            return {}
        if reject or (
            data.get("grant_type") == "authorization_code"
            and providers.challenge(data["code_verifier"]) != query["code_challenge"][0]
        ):
            msg = "Provider rejected the expired code or mismatched verifier."
            raise OAuthError(msg)
        return {
            "access_token": "access-must-not-leak",
            "refresh_token": "refresh-must-not-leak",
            "expires_in": 3600,
            "scope": "calendar.readonly",
            "token_type": "Bearer",
        }

    monkeypatch.setattr(providers, "_request", request)
    return calls


async def callback(client, query, **kwargs):
    return await client.get(
        "/api/v1/connections/oauth/google/callback",
        params={"state": query["state"][0], "code": "temporary-code", **kwargs},
    )


@pytest.mark.usefixtures("active_user", "oauth_config")
async def test_callback_pkce_storage_replay_and_revoke(client, logged_in_headers, monkeypatch):
    row, query = await begin(client, logged_in_headers)
    calls = provider_double(monkeypatch, query)
    async with session_scope() as session:
        state = await session.get(ConnectionOAuth, UUID(row["id"]))
        assert state.state_digest != query["state"][0]
        assert query["state"][0] not in state.model_dump_json()
        verifier = auth_utils.decrypt_api_key(state.encrypted_verifier)
        assert providers.challenge(verifier) == query["code_challenge"][0]
    cookies = dict(client.cookies)
    completed = await callback(client, query)
    assert completed.status_code == 200, completed.text
    assert completed.headers["cache-control"] == "no-store"
    assert completed.headers["referrer-policy"] == "no-referrer"
    assert all(
        secret not in completed.text for secret in ["access-must-not-leak", "refresh-must-not-leak", "temporary-code"]
    )
    client.cookies.update(cookies)
    assert (await callback(client, query)).status_code == 400
    assert len(calls) == 1
    async with session_scope() as session:
        state = await session.get(ConnectionOAuth, UUID(row["id"]))
        assert state.state_digest is None
        assert state.encrypted_verifier is None
        secret = await session.get(ConnectionSecret, UUID(row["id"]))
        assert "access-must-not-leak" not in secret.encrypted_payload
        assert "refresh-must-not-leak" not in secret.encrypted_payload
    resolver = get_connection_resolver_service()
    token = await resolver.resolve(resolution(row))
    assert token.access_token.get_secret_value() == "access-must-not-leak"
    revoked = await client.post(f"/api/v1/connections/{row['id']}/revoke", headers=logged_in_headers)
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["provider_revocation"] == "revoked"
    assert len(calls) == 2
    assert calls[-1]["token"] == "refresh-must-not-leak"  # noqa: S105 - test fixture
    with pytest.raises(ConnectionUnresolvedError):
        await resolver.resolve(resolution(row))


@pytest.mark.parametrize(
    "failure", ["pkce", "expired_code", "expired_state", "denied", "unconfigured", "wrong_provider"]
)
@pytest.mark.usefixtures("active_user", "oauth_config")
async def test_failed_callback_consumes_state_without_storing_credentials(
    client,
    logged_in_headers,
    monkeypatch,
    failure,
):
    row, query = await begin(client, logged_in_headers)
    calls = provider_double(monkeypatch, query, reject=failure == "expired_code")
    if failure in {"pkce", "expired_state"}:
        async with session_scope() as session:
            state = await session.get(ConnectionOAuth, UUID(row["id"]))
            if failure == "pkce":
                state.encrypted_verifier = auth_utils.encrypt_api_key("incorrect-verifier")
            else:
                state.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            session.add(state)
    if failure == "unconfigured":
        monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS", "{}")
    cookies = dict(client.cookies)
    if failure == "wrong_provider":
        failed = await client.get(
            "/api/v1/connections/oauth/slack/callback", params={"state": query["state"][0], "code": "temporary-code"}
        )
    else:
        failed = await callback(client, query, **({"error": "access_denied"} if failure == "denied" else {}))
    assert failed.status_code == 400
    client.cookies.update(cookies)
    assert (await callback(client, query)).status_code == 400
    assert len(calls) == (1 if failure in {"pkce", "expired_code"} else 0)
    async with session_scope() as session:
        assert await session.get(ConnectionSecret, UUID(row["id"])) is None
        state = await session.get(ConnectionOAuth, UUID(row["id"]))
        assert state.state_digest is None


@pytest.mark.usefixtures("active_user", "oauth_config")
async def test_browser_binding_and_pending_callback_revocation(client, logged_in_headers, monkeypatch):
    row, query = await begin(client, logged_in_headers)
    calls = provider_double(monkeypatch, query)
    cookies = dict(client.cookies)
    client.cookies.clear()
    assert (await callback(client, query)).status_code == 400
    client.cookies.update(cookies)
    # A revoke removes outstanding consent too; the old callback cannot resurrect it.
    revoked = await client.post(f"/api/v1/connections/{row['id']}/revoke", headers=logged_in_headers)
    assert revoked.status_code == 200
    assert (await callback(client, query)).status_code == 400
    assert calls == []


@pytest.mark.usefixtures("active_user", "oauth_config")
async def test_parallel_refresh_and_reactive_refresh_keep_rotated_tokens(client, logged_in_headers, monkeypatch):
    row, query = await begin(client, logged_in_headers)
    provider_double(monkeypatch, query)
    assert (await callback(client, query)).status_code == 200
    async with session_scope() as session:
        secret = await session.get(ConnectionSecret, UUID(row["id"]))
        payload = _decrypt_credential_payload(secret.encrypted_payload)
        payload["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        secret.encrypted_payload = _encrypt_credential_payload(json.dumps(payload))
        session.add(secret)
    calls = []

    async def exchange(_url, data, **_kwargs):
        calls.append(data)
        await asyncio.sleep(0.05)
        return {
            "access_token": f"rotated-{len(calls)}",
            "refresh_token": f"refresh-{len(calls)}",
            "expires_in": 3600,
            "scope": "calendar.readonly",
        }

    monkeypatch.setattr(providers, "_request", exchange)
    resolver = get_connection_resolver_service()
    credentials = await asyncio.gather(resolver.resolve(resolution(row)), resolver.resolve(resolution(row)))
    assert len(calls) == 1
    assert all(c.access_token.get_secret_value() == "rotated-1" for c in credentials)
    leases = [CredentialLease(resolver, resolution(row)) for _ in range(2)]
    await asyncio.gather(*(lease.get_token() for lease in leases))
    tokens = await asyncio.gather(
        *(lease.get_token_after_auth_error(AuthExpiredError(provider="google")) for lease in leases)
    )
    assert tokens == ["rotated-2", "rotated-2"]
    assert len(calls) == 2


@pytest.mark.usefixtures("active_user", "oauth_config")
async def test_start_denies_scope_escalation_and_unknown_registration(client, logged_in_headers):
    row, _ = await begin(client, logged_in_headers)
    for registration_id, scopes in [("unknown", ["calendar.readonly"]), ("google-work", ["gmail.readonly"])]:
        response = await client.post(
            f"/api/v1/connections/{row['id']}/oauth/start",
            headers=logged_in_headers,
            json={"registration_id": registration_id, "scopes": scopes},
        )
        assert response.status_code == 400


@pytest.mark.usefixtures("active_user", "oauth_config")
async def test_concurrent_callbacks_exchange_only_once(client, logged_in_headers, monkeypatch):
    _row, query = await begin(client, logged_in_headers)
    calls = provider_double(monkeypatch, query)
    outcomes = await asyncio.gather(callback(client, query), callback(client, query))
    assert sorted(response.status_code for response in outcomes) == [200, 400]
    assert len(calls) == 1


@pytest.mark.usefixtures("active_user", "oauth_config")
async def test_failed_remote_revocation_still_disables_local_use(client, logged_in_headers, monkeypatch):
    row, query = await begin(client, logged_in_headers)
    provider_double(monkeypatch, query)
    assert (await callback(client, query)).status_code == 200

    async def failing_revoke(*_args, **_kwargs):
        msg = "Provider unavailable"
        raise OAuthError(msg)

    monkeypatch.setattr(providers, "revoke", failing_revoke)
    revoked = await client.post(f"/api/v1/connections/{row['id']}/revoke", headers=logged_in_headers)
    assert revoked.status_code == 200
    assert revoked.json()["provider_revocation"] == "failed"
    with pytest.raises(ConnectionUnresolvedError):
        await get_connection_resolver_service().resolve(resolution(row))


@pytest.mark.usefixtures("active_user", "oauth_config")
async def test_narrowed_refresh_scopes_keep_the_replacement_refresh_token(client, logged_in_headers, monkeypatch):
    row, query = await begin(client, logged_in_headers)
    provider_double(monkeypatch, query)
    assert (await callback(client, query)).status_code == 200

    async def narrowed_response(*_args, **_kwargs):
        return {"access_token": "narrowed", "refresh_token": "new-rotating-refresh", "scope": "", "expires_in": 3600}

    monkeypatch.setattr(providers, "_request", narrowed_response)
    request = resolution(row)
    from dataclasses import replace

    from langflow.services.connection.oauth.broker import digest

    with pytest.raises(ScopeMissingError):
        await get_connection_resolver_service().resolve(
            replace(
                request,
                required_scopes=frozenset({"calendar.readonly"}),
                rejected_token_digest=digest("access-must-not-leak"),
            )
        )
    async with session_scope() as session:
        secret = await session.get(ConnectionSecret, UUID(row["id"]))
        payload = _decrypt_credential_payload(secret.encrypted_payload)
        assert payload["refresh_token"] == "new-rotating-refresh"  # noqa: S105 - test fixture
