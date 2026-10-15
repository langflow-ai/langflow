"""Slack must verify pasted tokens, health checks, and runtime rejections."""

from hashlib import sha256
from uuid import uuid4

import httpx
import pytest
from langflow.services.connection.service import _encrypt_credential_payload
from langflow.services.database.models.connection import Connection, ConnectionSecret
from langflow.services.deps import get_connection_resolver_service, session_scope
from lfx.integrations.errors import AuthExpiredError
from lfx.integrations.models import ConnectionRef, ConnectionResolutionRequest, CredentialLease
from lfx.services.authorization.base import ExecutionPrincipal

pytestmark = pytest.mark.no_blockbuster

TOKEN = "xoxb-123"  # noqa: S105 - deliberately invalid token from the regression
AUTH_TEST_URL = "https://slack.com/api/auth.test"


def body():
    return {
        "provider_key": "slack",
        "name": "validation",
        "display_name": "Slack validation",
        "executing_identity": {"identity": "bot"},
        "granted_scopes": ["chat:write", "reactions:write"],
        "credentials": {"access_token": TOKEN},
    }


async def legacy_connection(user_id):
    """Seed the pre-validation release behavior, including falsely healthy metadata."""
    import json

    async with session_scope() as session:
        row = Connection(
            owner_id=user_id,
            ownership_mode="user",
            provider_key="slack",
            name="validation",
            display_name="Slack validation",
            status="ready",
            health="healthy",
            granted_scopes=["chat:write", "reactions:write"],
            executing_identity={"identity": "bot"},
        )
        session.add(row)
        await session.flush()
        session.add(
            ConnectionSecret(
                connection_id=row.id,
                encrypted_payload=_encrypt_credential_payload(json.dumps({"version": 1, "access_token": TOKEN})),
            )
        )
        return row.id


@pytest.mark.parametrize("error", ["invalid_auth", "token_revoked", "token_expired", "account_inactive", "not_authed"])
async def test_invalid_pasted_token_is_rejected_without_saving(client, logged_in_headers, respx_mock, error):
    probe = respx_mock.post(AUTH_TEST_URL).respond(200, json={"ok": False, "error": error})
    response = await client.post("api/v1/connections", json=body(), headers=logged_in_headers)
    assert response.status_code == 422, response.text
    assert TOKEN not in response.text
    assert probe.call_count == 1
    rows = await client.get("api/v1/connections?provider=slack", headers=logged_in_headers)
    assert not rows.json()


async def test_pasted_token_uses_provider_scopes(client, logged_in_headers, respx_mock):
    probe = respx_mock.post(AUTH_TEST_URL).respond(
        200,
        json={"ok": True},
        headers={"x-oauth-scopes": "chat:write, channels:read,chat:write"},
    )
    response = await client.post("api/v1/connections", json=body(), headers=logged_in_headers)
    assert response.status_code == 201, response.text
    assert set(response.json()["granted_scopes"]) == {"chat:write", "channels:read"}
    assert probe.calls.last.request.headers["authorization"] == f"Bearer {TOKEN}"
    assert TOKEN not in str(probe.calls.last.request.url)


@pytest.mark.parametrize("endpoint", ["health", "test"])
async def test_health_check_rejects_legacy_token(client, logged_in_headers, active_user, respx_mock, endpoint):
    connection_id = await legacy_connection(active_user.id)
    probe = respx_mock.post(AUTH_TEST_URL).respond(200, json={"ok": False, "error": "token_revoked"})
    response = await client.post(
        f"api/v1/connections/{connection_id}/{endpoint}",
        json={},
        headers=logged_in_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["health"] == "unhealthy"
    assert response.json()["status"] == "expired"
    assert response.json()["health_checked_at"] is not None
    assert probe.call_count == 1
    async with session_scope() as session:
        stored = await session.get(Connection, connection_id)
        assert stored.status == "expired"
        assert stored.health == "unhealthy"


@pytest.mark.parametrize("interactive", [True, False])
async def test_runtime_rejection_persists_expired_health(active_user, interactive):
    connection_id = await legacy_connection(active_user.id)
    if not interactive:
        async with session_scope() as session:
            row = await session.get(Connection, connection_id)
            row.allow_non_interactive = True
            session.add(row)
    lease = CredentialLease(
        get_connection_resolver_service(),
        ConnectionResolutionRequest(
            ref=ConnectionRef(provider="slack", name="validation"),
            principal=ExecutionPrincipal(
                kind="actor" if interactive else "flow_owner", user_id=str(active_user.id), interactive=interactive
            ),
        ),
    )
    assert await lease.get_token() == TOKEN
    with pytest.raises(AuthExpiredError):
        await lease.get_token_after_auth_error(AuthExpiredError(provider="slack"))
    async with session_scope() as session:
        row = await session.get(Connection, connection_id)
        assert row.status == "expired"
        assert row.health == "unhealthy"
        assert row.health_checked_at is not None


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(429, json={"ok": False, "error": "ratelimited"}),
        httpx.Response(503, text=TOKEN),
        httpx.Response(307, headers={"Location": "https://example.com/collect"}),
        httpx.Response(200, text="not JSON"),
        httpx.Response(200, json=[]),
        httpx.Response(200, json={"ok": "true"}),
        httpx.Response(200, json={"ok": False, "error": []}),
        httpx.Response(200, json={"ok": False, "error": TOKEN}),
        httpx.ReadTimeout(TOKEN),
    ],
)
async def test_failed_probe_never_reports_healthy_or_expires_token(
    client,
    logged_in_headers,
    active_user,
    respx_mock,
    response,
):
    connection_id = await legacy_connection(active_user.id)
    probe = respx_mock.post(AUTH_TEST_URL)
    if isinstance(response, Exception):
        probe.mock(side_effect=response)
    else:
        probe.mock(return_value=response)
    checked = await client.post(f"api/v1/connections/{connection_id}/health", headers=logged_in_headers)
    assert checked.status_code == 200, checked.text
    assert checked.json()["health"] == "unhealthy"
    assert checked.json()["status"] == "ready"
    assert TOKEN not in checked.text
    created = await client.post("api/v1/connections", json=body(), headers=logged_in_headers)
    assert created.status_code == 422, created.text
    assert TOKEN not in created.text


@pytest.mark.parametrize("headers", [{}, {"x-oauth-scopes": "chat:write"}])
async def test_health_check_uses_verified_scope_coverage(client, logged_in_headers, active_user, respx_mock, headers):
    connection_id = await legacy_connection(active_user.id)
    respx_mock.post(AUTH_TEST_URL).respond(200, json={"ok": True}, headers=headers)
    checked = await client.post(
        f"api/v1/connections/{connection_id}/test",
        json={"required_scopes": ["reactions:write"]},
        headers=logged_in_headers,
    )
    assert checked.status_code == 200, checked.text
    assert checked.json()["health"] == "unhealthy"
    assert checked.json()["status"] == "ready"
    assert checked.json()["granted_scopes"] == (["chat:write"] if headers else [])


async def test_stale_runtime_rejection_does_not_expire_replacement(active_user):
    connection_id = await legacy_connection(active_user.id)
    resolved = await get_connection_resolver_service().resolve(
        ConnectionResolutionRequest(
            ref=ConnectionRef(provider="slack", name="validation"),
            principal=ExecutionPrincipal(kind="actor", user_id=str(active_user.id), interactive=True),
            rejected_token_digest=sha256(b"older-token").hexdigest(),
        )
    )
    assert resolved.access_token.get_secret_value() == TOKEN
    async with session_scope() as session:
        row = await session.get(Connection, connection_id)
        assert row.status == "ready"
        assert row.health == "healthy"


async def test_successful_health_check_restores_ready_and_records_verified_scopes(
    client,
    logged_in_headers,
    active_user,
    respx_mock,
):
    connection_id = await legacy_connection(active_user.id)
    async with session_scope() as session:
        row = await session.get(Connection, connection_id)
        row.status = "expired"
        row.health = "unhealthy"
        session.add(row)
    respx_mock.post(AUTH_TEST_URL).respond(200, json={"ok": True}, headers={"x-oauth-scopes": "chat:write"})
    checked = await client.post(f"api/v1/connections/{connection_id}/health", headers=logged_in_headers)
    assert checked.status_code == 200, checked.text
    assert checked.json()["health"] == "healthy"
    assert checked.json()["status"] == "ready"
    assert checked.json()["granted_scopes"] == ["chat:write"]


async def test_http_unauthorized_expires_token(client, logged_in_headers, active_user, respx_mock):
    connection_id = await legacy_connection(active_user.id)
    respx_mock.post(AUTH_TEST_URL).respond(401, text=TOKEN)
    checked = await client.post(f"api/v1/connections/{connection_id}/health", headers=logged_in_headers)
    assert checked.status_code == 200, checked.text
    assert checked.json()["status"] == "expired"
    assert TOKEN not in checked.text


@pytest.mark.respx(assert_all_called=False)
async def test_health_authorizes_before_contacting_slack(active_user, respx_mock):
    connection_id = await legacy_connection(active_user.id)
    probe = respx_mock.post(AUTH_TEST_URL).respond(200, json={"ok": True})
    async with session_scope() as session:
        row = await session.get(Connection, connection_id)
        checked = await get_connection_resolver_service().check_health(
            session,
            row=row,
            principal=ExecutionPrincipal(
                kind="actor", user_id=str(uuid4()), interactive=True, allow_explicit_shares=False
            ),
        )
    assert checked.health == "unhealthy"
    assert not probe.called
