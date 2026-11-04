"""A revoked pasted Slack token can recover its trigger and dispatch one run."""

from uuid import UUID

import pytest
from langflow.services.deps import session_scope
from langflow.services.triggers import dispatcher
from langflow.services.triggers.listeners.supervisor import ListenerSupervisor, mark_needs_reconnect

from tests.unit.services.triggers import slack_fixtures as fx

pytestmark = pytest.mark.no_blockbuster


@pytest.mark.usefixtures("socket_adapters", "listener_process")
async def test_reconnecting_app_token_resumes_same_trigger_and_dispatches_once(
    client, active_user, logged_in_headers, monkeypatch, respx_mock, slack, fake_background_service
):
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_CONTEXT", "self_managed")
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS", "{}")
    created = await client.post(
        "/api/v1/connections",
        headers=logged_in_headers,
        json={
            "provider_key": "slack",
            "name": "socket_app",
            "display_name": "Slack app token",
            "executing_identity": {"identity": "bot"},
            "allow_non_interactive": True,
            "credentials": {"access_token": "xapp-original-test-only"},
        },
    )
    assert created.status_code == 201, created.text
    connection = created.json()
    connection_id = UUID(connection["id"])
    flow_id = await fx.make_flow(active_user.id)
    trigger_id = await fx.arm(
        flow_id,
        active_user.id,
        connection_id,
        mechanism="slack.socket_mode",
        config={"connection": "slack/socket_app"},
    )
    respx_mock.post("https://slack.com/api/auth.revoke").respond(200, json={"ok": True, "revoked": True})
    revoked = await client.post(f"/api/v1/connections/{connection_id}/revoke", headers=logged_in_headers)
    assert revoked.status_code == 200, revoked.text
    async with session_scope() as session:
        await mark_needs_reconnect(session, trigger_ids=[trigger_id], reason="The Slack connection was revoked.")
    disconnected = await client.get(f"/api/v1/triggers/{trigger_id}", headers=logged_in_headers)
    assert disconnected.status_code == 200, disconnected.text
    assert disconnected.json()["reason"] == "needs_reconnect"
    assert "resume" not in disconnected.json()["allowed_actions"]

    replacement = "xapp-replacement-test-only"
    renewed = await client.post(
        f"/api/v1/connections/{connection_id}/token",
        headers=logged_in_headers,
        json={"credentials": {"access_token": replacement}, "allow_non_interactive": True},
    )
    assert renewed.status_code == 200, renewed.text
    assert renewed.json()["id"] == connection["id"]
    for url in (f"/api/v1/triggers/{trigger_id}", f"/api/v1/triggers?flow_id={flow_id}"):
        response = await client.get(url, headers=logged_in_headers)
        assert response.status_code == 200, response.text
        result = response.json()
        row = next(item for item in result if item["id"] == str(trigger_id)) if isinstance(result, list) else result
        assert row["reason"] == "ready_to_resume"
        assert "resume" in row["allowed_actions"]
        assert "reconnect" not in row["allowed_actions"]
    resumed = await client.post(f"/api/v1/triggers/{trigger_id}/enable", headers=logged_in_headers)
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["state"] == "active"
    assert resumed.json()["connection_id"] == str(connection_id)

    supervisor = ListenerSupervisor(holder="token-reconnect")
    try:
        await supervisor.reconcile()
        [socket] = await slack.wait_for_sockets(1)
        assert slack.authorizations == [f"Bearer {replacement}"]
        message = fx.load("message_channel")
        await socket.deliver(message, envelope_id="reconnected-1")
        await socket.deliver(message, envelope_id="reconnected-2", retry_attempt=1)
        assert await socket.wait_for_ack("reconnected-1")
        assert await socket.wait_for_ack("reconnected-2")
        assert len(await fx.events_for(trigger_id)) == 1
        assert await dispatcher.run_once(owner="token-reconnect") == 1
        assert len(fake_background_service.submits) == 1
        assert fake_background_service.submits[0]["flow_id"] == flow_id
        assert await dispatcher.run_once(owner="token-reconnect") == 0
    finally:
        await supervisor.stop()
