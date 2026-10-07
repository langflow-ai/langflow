"""OAuth consent and refresh regressions against the real connection API and DB."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient
from langflow.services.auth import utils as auth_utils
from langflow.services.connection.oauth import providers
from langflow.services.connection.oauth.config import OAuthError
from langflow.services.connection.service import _decrypt_credential_payload, _encrypt_credential_payload
from langflow.services.database.models.connection import Connection, ConnectionSecret
from langflow.services.database.models.connection.oauth import ConnectionOAuth
from langflow.services.deps import get_connection_resolver_service, session_scope
from lfx.integrations.errors import (
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    ConnectionUnresolvedError,
    ScopeMissingError,
)
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


async def begin(client, headers, *, allow_non_interactive=True, handoff=False):
    created = await client.post(
        "/api/v1/connections",
        headers=headers,
        json={
            "provider_key": "google",
            "name": "work",
            "display_name": "Google work",
            "executing_identity": {"identity": "user_delegated"},
            "allow_non_interactive": allow_non_interactive,
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
    if handoff:
        return row, started
    query = await consent_query(client, started)
    assert query["code_challenge_method"] == ["S256"]
    assert "client_secret" not in query
    return row, query


async def consent_query(client, started):
    url = started.json()["authorization_url"]
    if urlsplit(url).path.endswith("/browser"):
        uri = urlsplit(url)
        started = await client.get(f"{uri.path}?{uri.query}", follow_redirects=False)
        assert started.status_code == 303, started.text
        url = started.headers["location"]
    assert "HttpOnly" in started.headers["set-cookie"]
    assert "SameSite=lax" in started.headers["set-cookie"]
    return parse_qs(urlsplit(url).query)


@pytest.mark.usefixtures("active_user", "oauth_config")
async def test_desktop_handoff_binds_a_separate_browser(client, logged_in_headers, monkeypatch):
    row, started = await begin(client, logged_in_headers, handoff=True)
    assert "set-cookie" not in started.headers
    handoff_url = started.json()["authorization_url"]
    handoff_query = parse_qs(urlsplit(handoff_url).query)
    assert urlsplit(handoff_url).hostname == "localhost"
    assert urlsplit(handoff_url).path == "/api/v1/connections/oauth/google/browser"
    async with session_scope() as session:
        binding = await session.get(ConnectionOAuth, UUID(row["id"]))
        assert handoff_query["handoff"][0] not in binding.model_dump_json()

    # The system browser shares the API transport, but no WebView cookies or login.
    async with AsyncClient(transport=client._transport, base_url="http://localhost") as system_browser:
        query = await consent_query(system_browser, started)
        assert query["code_challenge_method"] == ["S256"]
        calls = provider_double(monkeypatch, query)
        assert (await callback(client, query)).status_code == 400
        assert (await callback(system_browser, query)).status_code == 200
        assert len(calls) == 1
        replay = await system_browser.get(handoff_url, follow_redirects=False)
        assert replay.status_code == 400
        assert "set-cookie" not in replay.headers


@pytest.mark.usefixtures("active_user", "oauth_config")
async def test_desktop_handoff_is_single_use_before_callback(client, logged_in_headers):
    _row, started = await begin(client, logged_in_headers, handoff=True)
    url = started.json()["authorization_url"]
    results = await asyncio.gather(*(client.get(url, follow_redirects=False) for _ in range(2)))
    assert sorted(result.status_code for result in results) == [303, 400]
    for result in results:
        assert result.headers["cache-control"] == "no-store"
        assert result.headers["referrer-policy"] == "no-referrer"


@pytest.mark.usefixtures("active_user", "oauth_config")
async def test_desktop_handoff_nonce_cannot_replace_the_callback_cookie(client, logged_in_headers):
    from langflow.services.connection.oauth.broker import digest

    _row, started = await begin(client, logged_in_headers, handoff=True)
    query = parse_qs(urlsplit(started.json()["authorization_url"]).query)
    client.cookies.set("lf_connection_oauth_" + digest(query["state"][0])[:24], query["handoff"][0])
    assert (await callback(client, query)).status_code == 400
    client.cookies.clear()
    query = await consent_query(client, started)
    assert (await callback(client, query, error="access_denied")).status_code == 400


@pytest.mark.usefixtures("active_user", "oauth_config")
async def test_desktop_handoff_rechecks_permission(client, logged_in_headers, monkeypatch):
    from fastapi import HTTPException
    from langflow.services.connection.oauth import broker

    _row, started = await begin(client, logged_in_headers, handoff=True)

    async def deny(*_args, **_kwargs):
        raise HTTPException(status_code=403, detail="Connection access revoked")

    monkeypatch.setattr(broker, "ensure_connection_permission", deny)
    result = await client.get(started.json()["authorization_url"], follow_redirects=False)
    assert result.status_code == 403
    assert "set-cookie" not in result.headers
    assert "location" not in result.headers


@pytest.mark.usefixtures("active_user", "oauth_config")
@pytest.mark.parametrize("failure", ["expired", "revoked", "deleted", "superseded", "inactive", "config_changed"])
async def test_desktop_handoff_rejects_invalidated_attempts(client, logged_in_headers, monkeypatch, failure):
    row, started = await begin(client, logged_in_headers, handoff=True)
    if failure == "expired":
        async with session_scope() as session:
            binding = await session.get(ConnectionOAuth, UUID(row["id"]))
            binding.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            session.add(binding)
    elif failure == "revoked":
        assert (
            await client.post(f"/api/v1/connections/{row['id']}/revoke", headers=logged_in_headers)
        ).status_code == 200
    elif failure == "deleted":
        assert (await client.delete(f"/api/v1/connections/{row['id']}", headers=logged_in_headers)).status_code == 204
    elif failure == "superseded":
        assert (
            await client.post(
                f"/api/v1/connections/{row['id']}/oauth/start",
                headers=logged_in_headers,
                json={"registration_id": "google-work", "scopes": ["calendar.readonly"]},
            )
        ).status_code == 200
    elif failure == "inactive":
        from langflow.services.database.models.user.model import User

        async with session_scope() as session:
            user = await session.get(User, UUID(row["owner_id"]))
            user.is_active = False
            session.add(user)
    else:
        monkeypatch.setenv(
            "LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS", json.dumps({"google-work": registration(client_id="changed")})
        )
    result = await client.get(started.json()["authorization_url"], follow_redirects=False)
    assert result.status_code == 400
    assert "set-cookie" not in result.headers
    assert "location" not in result.headers


@pytest.mark.usefixtures("active_user", "oauth_config")
@pytest.mark.parametrize("failure", ["wrong_provider", "wrong_nonce", "duplicate_state", "duplicate_handoff"])
async def test_desktop_handoff_rejects_malformed_requests(client, logged_in_headers, failure):
    _row, started = await begin(client, logged_in_headers, handoff=True)
    url = started.json()["authorization_url"]
    if failure == "wrong_provider":
        url = url.replace("/google/browser", "/microsoft/browser")
    elif failure == "wrong_nonce":
        query = parse_qs(urlsplit(url).query)
        url = url.replace(query["handoff"][0], "x" * 43)
    else:
        field = "state" if failure == "duplicate_state" else "handoff"
        url += f"&{field}=duplicate"
    result = await client.get(url, follow_redirects=False)
    assert result.status_code == 400
    assert "set-cookie" not in result.headers
    assert "location" not in result.headers


@pytest.mark.usefixtures("active_user", "oauth_config")
async def test_web_oauth_keeps_its_original_cookie_flow(client, logged_in_headers, monkeypatch):
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_CONTEXT", "self_managed")
    monkeypatch.setenv(
        "LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS", json.dumps({"google-work": registration(context="self_managed")})
    )
    _row, started = await begin(client, logged_in_headers, handoff=True)
    assert urlsplit(started.json()["authorization_url"]).hostname == "accounts.google.com"
    query = await consent_query(client, started)
    provider_double(monkeypatch, query)
    assert (await callback(client, query)).status_code == 200


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


@pytest.mark.usefixtures("active_user", "oauth_config")
@pytest.mark.parametrize("allow_non_interactive", [False, True])
async def test_reauthorization_clears_an_undecryptable_error(
    client, logged_in_headers, monkeypatch, allow_non_interactive
):
    row, query = await begin(client, logged_in_headers, allow_non_interactive=allow_non_interactive)
    provider_double(monkeypatch, query)
    assert (await callback(client, query)).status_code == 200
    async with session_scope() as session:
        secret = await session.get(ConnectionSecret, UUID(row["id"]))
        stored = await session.get(Connection, UUID(row["id"]))
        stored.executing_identity = {**stored.executing_identity, "account": {"id": "previous-account"}}
        session.add(stored)
        # What a restart under a different secret key leaves behind.
        secret.encrypted_payload = Fernet(Fernet.generate_key()).encrypt(b'{"version":1}').decode()
        session.add(secret)
    broken = (await client.post(f"/api/v1/connections/{row['id']}/health", headers=logged_in_headers)).json()
    assert (broken["status"], broken["status_reason"]) == ("error", "credential-undecryptable")

    restarted = await client.post(
        f"/api/v1/connections/{row['id']}/oauth/start",
        headers=logged_in_headers,
        json={"registration_id": "google-work", "scopes": ["calendar.readonly"]},
    )
    assert restarted.status_code == 200, restarted.text
    requery = await consent_query(client, restarted)
    provider_double(monkeypatch, requery)
    assert (await callback(client, requery)).status_code == 200

    async with session_scope() as session:
        stored = await session.get(Connection, UUID(row["id"]))
        assert (stored.status, stored.status_reason) == ("ready", None)
        assert stored.executing_identity["account"] is None
        assert stored.allow_non_interactive is allow_non_interactive
    token = await get_connection_resolver_service().resolve(resolution(row))
    assert token.access_token.get_secret_value() == "access-must-not-leak"

    unattended = ConnectionResolutionRequest(
        ref=ConnectionRef(provider="google", name="work"),
        principal=ExecutionPrincipal(kind="job_owner", user_id=row["owner_id"], interactive=False),
    )
    if allow_non_interactive:
        token = await get_connection_resolver_service().resolve(unattended)
        assert token.access_token.get_secret_value() == "access-must-not-leak"
    else:
        with pytest.raises(ConnectionNotAuthorizedError):
            await get_connection_resolver_service().resolve(unattended)


@pytest.mark.parametrize("identity", ["bot", "user_delegated"])
async def test_slack_bot_consent_on_a_regular_users_connection(
    client, active_user, logged_in_headers, monkeypatch, identity
):
    assert active_user.is_superuser is False
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_CONTEXT", "self_managed")
    monkeypatch.setenv(
        "LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS",
        json.dumps(
            {
                "slack-bot": registration(
                    provider="slack",
                    profile="bot",
                    context="self_managed",
                    client_type="confidential",
                    client_secret="test-secret",  # noqa: S106 # pragma: allowlist secret - test fixture
                    redirect_uri="http://localhost/api/v1/connections/oauth/slack/callback",
                    scopes=["chat:write"],
                    allowed_tenants=["workspace-123"],
                )
            }
        ),
    )
    created = await client.post(
        "/api/v1/connections",
        headers=logged_in_headers,
        json={
            "provider_key": "slack",
            "name": "work",
            "display_name": "Slack work",
            "executing_identity": {"identity": identity},
        },
    )
    assert created.status_code == 201, created.text
    row = created.json()
    assert row["ownership_mode"] == "user"
    assert row["owner_id"] == str(active_user.id)
    started = await client.post(
        f"/api/v1/connections/{row['id']}/oauth/start",
        headers=logged_in_headers,
        json={"registration_id": "slack-bot", "scopes": ["chat:write"]},
    )
    if identity != "bot":
        assert started.status_code == 400
        assert started.json()["detail"] == "OAuth registration does not match this connection's identity type."
        async with session_scope() as session:
            assert await session.get(ConnectionOAuth, UUID(row["id"])) is None
        return

    assert started.status_code == 200, started.text
    query = parse_qs(urlsplit(started.json()["authorization_url"]).query)
    assert query["scope"] == ["chat:write"]
    assert "user_scope" not in query

    async def exchange(_url, data, **_kwargs):
        assert data["grant_type"] == "authorization_code"
        return {
            "access_token": "bot-token-must-not-leak",
            "token_type": "bot",
            "scope": "chat:write",
            "bot_user_id": "bot-123",
            "team": {"id": "workspace-123"},
        }

    monkeypatch.setattr(providers, "_request", exchange)
    completed = await client.get(
        "/api/v1/connections/oauth/slack/callback",
        params={"state": query["state"][0], "code": "temporary-code"},
    )
    assert completed.status_code == 200, completed.text
    async with session_scope() as session:
        stored = await session.get(Connection, UUID(row["id"]))
        assert stored.status == "ready"
        assert stored.executing_identity["identity"] == "bot"
        assert stored.executing_identity["account"]["id"] == "bot-123"
        assert stored.granted_scopes == ["chat:write"]


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
    visible = await client.get("/api/v1/connections", headers=logged_in_headers)
    assert visible.status_code == 200, visible.text
    updated_row = next(item for item in visible.json() if item["id"] == row["id"])
    assert updated_row["status"] == "error"
    assert updated_row["status_reason"] == {
        "denied": "oauth-denied",
        "expired_state": "oauth-expired",
    }.get(failure, "oauth-failed")
    assert updated_row["updated_at"] != row["updated_at"]


@pytest.mark.usefixtures("active_user", "oauth_config")
async def test_denied_reauthorization_preserves_existing_credential(client, logged_in_headers, monkeypatch):
    row, query = await begin(client, logged_in_headers)
    provider_double(monkeypatch, query)
    assert (await callback(client, query)).status_code == 200
    started = await client.post(
        f"/api/v1/connections/{row['id']}/oauth/start",
        headers=logged_in_headers,
        json={"registration_id": "google-work", "scopes": ["calendar.readonly"]},
    )
    assert started.status_code == 200, started.text
    second_query = await consent_query(client, started)
    assert (await callback(client, second_query, error="access_denied")).status_code == 400

    visible = await client.get("/api/v1/connections", headers=logged_in_headers)
    assert visible.status_code == 200, visible.text
    updated_row = next(item for item in visible.json() if item["id"] == row["id"])
    assert (updated_row["status"], updated_row["status_reason"], updated_row["has_credentials"]) == (
        "ready",
        "oauth-denied",
        True,
    )
    async with session_scope() as session:
        assert await session.get(ConnectionSecret, UUID(row["id"])) is not None


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
