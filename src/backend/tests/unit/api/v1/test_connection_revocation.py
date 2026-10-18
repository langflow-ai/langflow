"""Revocation of pasted credentials through the connection API and real database."""

from uuid import UUID

import httpx
import pytest
from langflow.services.database.models.connection import ConnectionSecret
from langflow.services.deps import session_scope

pytestmark = pytest.mark.no_blockbuster


@pytest.mark.parametrize(
    ("token", "identity", "provider_response", "expected"),
    [
        ("xoxb-test-only", "bot", {"ok": True, "revoked": True}, "revoked"),
        ("xoxp-test-only", "user_delegated", {"ok": True, "revoked": True}, "revoked"),
        ("xapp-test-only", "bot", {"ok": False, "error": "not_allowed_token_type"}, "failed"),
        ("xoxb-test-only", "bot", {"ok": False, "error": "invalid_auth"}, "failed"),
        ("xoxb-test-only", "bot", {"ok": True, "revoked": False}, "failed"),
        ("xoxb-test-only", "bot", {"ok": True}, "failed"),
        ("xoxb-test-only", "bot", {"revoked": True}, "failed"),
        ("xoxb-test-only", "bot", {"ok": True, "revoked": "true"}, "failed"),
        ("xoxb-test-only", "bot", None, "failed"),
    ],
)
async def test_revoke_pasted_slack_token(
    client, logged_in_headers, monkeypatch, respx_mock, token, identity, provider_response, expected
):
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_CONTEXT", "self_managed")
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS", "{}")
    # Web API tokens must pass validation before they can be stored and revoked.
    if not token.startswith("xapp-"):
        respx_mock.post("https://slack.com/api/auth.test", headers={"Authorization": f"Bearer {token}"}).respond(
            200, json={"ok": True}
        )
    created = await client.post(
        "/api/v1/connections",
        headers=logged_in_headers,
        json={
            "provider_key": "slack",
            "name": "pasted",
            "display_name": "Pasted Slack token",
            "executing_identity": {"identity": identity},
            "credentials": {"access_token": token},
        },
    )
    assert created.status_code == 201, created.text
    connection_id = created.json()["id"]

    def slack(request):
        assert request.method == "POST"
        assert str(request.url) == "https://slack.com/api/auth.revoke"
        assert request.headers["Authorization"] == f"Bearer {token}"
        assert request.content == b""
        if provider_response is None:
            msg = "Provider timed out"
            raise httpx.ReadTimeout(msg, request=request)
        return httpx.Response(200, json=provider_response)

    revoke_request = respx_mock.post("https://slack.com/api/auth.revoke").mock(side_effect=slack)
    revoked = await client.post(f"/api/v1/connections/{connection_id}/revoke", headers=logged_in_headers)
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["provider_revocation"] == expected
    assert revoked.json()["status"] == "revoked"
    assert revoked.json()["has_credentials"] is False
    assert token not in revoked.text
    assert revoke_request.call_count == 1
    async with session_scope() as session:
        assert await session.get(ConnectionSecret, UUID(connection_id)) is None

    repeated = await client.post(f"/api/v1/connections/{connection_id}/revoke", headers=logged_in_headers)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["provider_revocation"] == "not_applicable"
    assert revoke_request.call_count == 1
