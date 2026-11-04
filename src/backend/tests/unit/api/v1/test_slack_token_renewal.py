"""Pasted Slack tokens reconnect the existing connection without OAuth."""

from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import pytest
from langflow.services.connection.oauth import providers
from langflow.services.connection.service import _decrypt_credential_payload
from langflow.services.database.models.connection import Connection, ConnectionSecret
from langflow.services.database.models.connection.oauth import ConnectionOAuth
from langflow.services.deps import session_scope

from tests.unit.services.triggers import slack_fixtures as fx

pytestmark = pytest.mark.no_blockbuster


@pytest.fixture(autouse=True)
def manual_slack_context(monkeypatch):
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_CONTEXT", "self_managed")
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS", "{}")


async def create_connection(client, headers, token):
    response = await client.post(
        "/api/v1/connections",
        headers=headers,
        json={
            "provider_key": "slack",
            "name": "pasted",
            "display_name": "Pasted Slack token",
            "executing_identity": {"identity": "bot"},
            "allow_non_interactive": True,
            "credentials": {"access_token": token},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize("prefix", ["xapp-", "xoxb-"])
@pytest.mark.parametrize("revoke_first", [False, True])
async def test_manual_renewal_preserves_connection(client, logged_in_headers, respx_mock, prefix, revoke_first):
    if prefix == "xoxb-":
        respx_mock.post("https://slack.com/api/auth.test").respond(
            200, json={"ok": True}, headers={"x-oauth-scopes": "chat:write,channels:read"}
        )
    original = await create_connection(client, logged_in_headers, f"{prefix}original-test-only")
    url = f"/api/v1/connections/{original['id']}"
    if revoke_first:
        respx_mock.post("https://slack.com/api/auth.revoke").respond(200, json={"ok": True, "revoked": True})
        revoked = await client.post(f"{url}/revoke", headers=logged_in_headers)
        assert revoked.status_code == 200, revoked.text
        assert revoked.json()["has_credentials"] is False
    replacement = f"{prefix}replacement-test-only"

    response = await client.post(
        f"{url}/token",
        headers=logged_in_headers,
        json={"credentials": {"access_token": replacement}, "allow_non_interactive": True},
    )

    assert response.status_code == 200, response.text
    renewed = response.json()
    for field in (
        "id",
        "owner_id",
        "provider_key",
        "name",
        "display_name",
        "ownership_mode",
        "executing_identity",
        "created_at",
    ):
        assert renewed[field] == original[field]
    assert renewed["status"] == "ready"
    assert renewed["status_reason"] is None
    assert renewed["has_credentials"] is True
    assert renewed["allow_non_interactive"] is True
    expected_scopes = ["connections:write"] if prefix == "xapp-" else ["channels:read", "chat:write"]
    assert renewed["granted_scopes"] == expected_scopes
    assert replacement not in response.text
    assert "credentials" not in renewed
    async with session_scope() as session:
        secret = await session.get(ConnectionSecret, UUID(original["id"]))
        assert replacement not in secret.encrypted_payload
        assert _decrypt_credential_payload(secret.encrypted_payload)["access_token"] == replacement


async def test_rejected_renewal_keeps_existing_credential(client, logged_in_headers, respx_mock, monkeypatch):
    probe = respx_mock.post("https://slack.com/api/auth.test").respond(200, json={"ok": True})
    original = await create_connection(client, logged_in_headers, "xoxb-original-test-only")
    connection_id = UUID(original["id"])
    await start_consent(client, logged_in_headers, connection_id, monkeypatch)
    async with session_scope() as session:
        binding_before = (await session.get(ConnectionOAuth, connection_id)).model_dump()
        encrypted_before = (await session.get(ConnectionSecret, connection_id)).encrypted_payload
    probe.respond(200, json={"ok": False, "error": "invalid_auth"})

    response = await client.post(
        f"/api/v1/connections/{connection_id}/token",
        headers=logged_in_headers,
        json={"credentials": {"access_token": "xoxb-rejected-test-only"}, "allow_non_interactive": False},
    )

    assert response.status_code == 422, response.text
    assert "Slack rejected this token" in response.json()["detail"]
    assert "xoxb-rejected-test-only" not in response.text
    async with session_scope() as session:
        assert (await session.get(ConnectionSecret, connection_id)).encrypted_payload == encrypted_before
        row = await session.get(Connection, connection_id)
        assert row.status == "ready"
        assert row.allow_non_interactive is True
        assert (await session.get(ConnectionOAuth, connection_id)).model_dump() == binding_before


async def test_hosted_cannot_renew_app_token(client, logged_in_headers, respx_mock, monkeypatch):
    original = await create_connection(client, logged_in_headers, "xapp-original-test-only")
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_CONTEXT", "hosted")

    response = await client.post(
        f"/api/v1/connections/{original['id']}/token",
        headers=logged_in_headers,
        json={"credentials": {"access_token": "xapp-replacement-test-only"}},
    )

    assert response.status_code == 422, response.text
    assert "hosted Langflow does not offer" in response.json()["detail"]
    assert not respx_mock.calls
    async with session_scope() as session:
        secret = await session.get(ConnectionSecret, UUID(original["id"]))
        assert _decrypt_credential_payload(secret.encrypted_payload)["access_token"] == "xapp-original-test-only"  # noqa: S105


async def start_consent(client, headers, connection_id, monkeypatch):
    fx.use_registrations(monkeypatch)
    started = await client.post(
        f"/api/v1/connections/{connection_id}/oauth/start",
        headers=headers,
        json={"registration_id": fx.REGISTRATION_ID, "scopes": ["chat:write"]},
    )
    assert started.status_code == 200, started.text
    return parse_qs(urlsplit(started.json()["authorization_url"]).query)["state"][0]


@pytest.mark.parametrize("denied", [False, True])
async def test_manual_renewal_supersedes_pending_oauth(client, logged_in_headers, respx_mock, monkeypatch, denied):
    respx_mock.post("https://slack.com/api/auth.test").respond(200, json={"ok": True})
    original = await create_connection(client, logged_in_headers, "xoxb-original-test-only")
    connection_id = UUID(original["id"])
    state = await start_consent(client, logged_in_headers, connection_id, monkeypatch)
    exchange = AsyncMock(return_value=({"version": 1, "access_token": "old-consent-test-only"}, ["chat:write"], None))
    monkeypatch.setattr(providers, "exchange", exchange)
    replacement = "xapp-replacement-test-only"
    renewed = await client.post(
        f"/api/v1/connections/{connection_id}/token",
        headers=logged_in_headers,
        json={"credentials": {"access_token": replacement}, "allow_non_interactive": True},
    )
    assert renewed.status_code == 200, renewed.text

    callback = await client.get(
        "/api/v1/connections/oauth/slack/callback",
        params={"state": state, **({"error": "access_denied"} if denied else {"code": "old-consent-code"})},
    )

    assert callback.status_code == 400, callback.text
    exchange.assert_not_awaited()
    async with session_scope() as session:
        row = await session.get(Connection, connection_id)
        assert row.status == "ready"
        assert row.status_reason is None
        secret = await session.get(ConnectionSecret, connection_id)
        assert _decrypt_credential_payload(secret.encrypted_payload)["access_token"] == replacement
        assert await session.get(ConnectionOAuth, connection_id) is None
