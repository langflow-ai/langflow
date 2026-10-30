"""Recovery affordances require a credential replacement or restored background consent."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from langflow.services.connection.oauth import broker
from langflow.services.database.models.connection.model import Connection, ConnectionSecret
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.deps import get_db_service, session_scope
from langflow.services.triggers.constants import CONNECTION_NOT_AUTHORIZED_ERROR
from langflow.services.triggers.listeners import supervisor
from langflow.services.triggers.reconciliation import reconcile_flow_triggers
from lfx.integrations.errors import AuthExpiredError, ConnectionNotAuthorizedError
from sqlalchemy import event

pytestmark = pytest.mark.no_blockbuster

SCOPE = "https://www.googleapis.com/auth/calendar.events.readonly"


def calendar_flow(connection):
    return {
        "nodes": [
            {
                "id": "calendar-source",
                "data": {
                    "type": "ext:google:GoogleOnCalendarTriggerComponent@official",
                    "node": {
                        "template": {
                            "connection": {"value": connection},
                            "calendar_id": {"value": "primary"},
                            "delivery_mode": {"value": "poll"},
                        }
                    },
                },
            }
        ],
        "edges": [],
    }


async def make_rejected_trigger(owner_id, *, consent=False):
    async with session_scope() as session:
        connection = Connection(
            provider_key="google",
            name="recovery",
            display_name="Recovery",
            owner_id=owner_id,
            executing_identity={"identity": "user_delegated"},
            allow_non_interactive=not consent,
        )
        flow = Flow(name="Recovery", user_id=owner_id)
        session.add(connection)
        session.add(flow)
        await session.flush()
        await broker.store_tokens(session, connection, {"version": 1, "access_token": "old-synthetic-token"}, [SCOPE])
        trigger = Trigger(
            flow_id=flow.id,
            user_id=owner_id,
            name="Calendar",
            kind="google.calendar",
            provider="google",
            connection_id=connection.id,
            state="active",
            concurrency_limit=1,
            max_attempts=5,
            node_id="calendar-source",
            provider_state={"cursor": "preserved"},
            config={"connection": "google/recovery", "mechanism_id": "google.calendar_sync_poll"},
        )
        session.add(trigger)
        await session.flush()
        identifiers = connection.id, trigger.id, flow.id
    worker = SimpleNamespace(connection_id=connection.id, triggers=[SimpleNamespace(id=trigger.id)])
    error = (
        ConnectionNotAuthorizedError(provider="google", reason="non-interactive-opt-in-required")
        if consent
        else AuthExpiredError(provider="google")
    )
    await supervisor.ListenerSupervisor()._needs_reconnect(worker, error)
    return identifiers


@pytest.mark.parametrize("metadata_edit", [False, True])
async def test_ready_connection_keeps_reconnect_until_credentials_change(
    client, active_user, logged_in_headers, metadata_edit
):
    connection_id, trigger_id, flow_id = await make_rejected_trigger(active_user.id)
    if metadata_edit:
        response = await client.patch(
            f"api/v1/connections/{connection_id}", headers=logged_in_headers, json={"display_name": "Renamed"}
        )
        assert response.status_code == 200, response.text
        async with session_scope() as session:
            connection = await session.get(Connection, connection_id)
            connection.health = "healthy"
            connection.health_checked_at = datetime.now(timezone.utc)
            connection.updated_at = connection.health_checked_at
            session.add(connection)

    engine = get_db_service().engine.sync_engine
    statements = []

    def record(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement.lower())

    event.listen(engine, "before_cursor_execute", record)
    try:
        for url in (f"api/v1/triggers/{trigger_id}", f"api/v1/triggers?flow_id={flow_id}", "api/v1/triggers"):
            response = await client.get(url, headers=logged_in_headers)
            assert response.status_code == 200, response.text
            result = response.json()
            body = next(row for row in result if row["id"] == str(trigger_id)) if isinstance(result, list) else result
            assert body["reason"] == "needs_reconnect"
            assert "reconnect" in body["allowed_actions"]
            assert "resume" not in body["allowed_actions"]
            assert "old-synthetic-token" not in response.text
    finally:
        event.remove(engine, "before_cursor_execute", record)
    assert not any("encrypted_payload" in statement for statement in statements)
    assert not any(statement.lstrip().startswith(("insert ", "update ", "delete ")) for statement in statements)
    async with session_scope() as session:
        assert (await session.get(Connection, connection_id)).status == "ready"
        assert (await session.get(Trigger, trigger_id)).state == "needs_reconnect"


async def test_same_second_successful_reconnect_offers_resume(client, active_user, logged_in_headers, monkeypatch):
    failed_at = datetime.now(timezone.utc) + timedelta(days=1)
    failed_at = failed_at.replace(microsecond=100000)
    monkeypatch.setattr(supervisor, "_now", lambda: failed_at)
    connection_id, trigger_id, _ = await make_rejected_trigger(active_user.id)

    class ReconnectedTime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ARG003 - datetime protocol
            return failed_at + timedelta(microseconds=1)

    monkeypatch.setattr(broker, "datetime", ReconnectedTime)
    async with session_scope() as session:
        connection = await session.get(Connection, connection_id)
        await broker.store_tokens(session, connection, {"version": 1, "access_token": "new-synthetic-token"}, [SCOPE])

    response = await client.get(f"api/v1/triggers/{trigger_id}", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    assert response.json()["reason"] == "ready_to_resume"
    assert "resume" in response.json()["allowed_actions"]
    assert "reconnect" not in response.json()["allowed_actions"]
    assert "new-synthetic-token" not in response.text


async def test_legacy_generic_denial_is_not_evidence_of_consent_only_failure(client, active_user, logged_in_headers):
    _connection_id, trigger_id, _ = await make_rejected_trigger(active_user.id)
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        trigger.provider_state = {"cursor": "preserved"}
        trigger.last_error = CONNECTION_NOT_AUTHORIZED_ERROR
        trigger.updated_at = datetime.now(timezone.utc)
        session.add(trigger)
    response = await client.get(f"api/v1/triggers/{trigger_id}", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    assert response.json()["reason"] == "needs_reconnect"
    assert "resume" not in response.json()["allowed_actions"]


async def test_legacy_second_precision_failure_does_not_accept_unchanged_credentials(
    client, active_user, logged_in_headers
):
    connection_id, trigger_id, _ = await make_rejected_trigger(active_user.id)
    failed_second = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        trigger.provider_state = {}
        trigger.updated_at = failed_second
        secret = await session.get(ConnectionSecret, connection_id)
        secret.updated_at = failed_second.replace(microsecond=500000)
        session.add(trigger)
        session.add(secret)
    response = await client.get(f"api/v1/triggers/{trigger_id}", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    assert response.json()["reason"] == "needs_reconnect"
    assert "resume" not in response.json()["allowed_actions"]


async def test_restoring_background_consent_offers_resume_without_replacing_token(
    client, active_user, logged_in_headers
):
    connection_id, trigger_id, _ = await make_rejected_trigger(active_user.id, consent=True)
    async with session_scope() as session:
        original_updated_at = (await session.get(ConnectionSecret, connection_id)).updated_at
    denied = await client.get(f"api/v1/triggers/{trigger_id}", headers=logged_in_headers)
    assert denied.status_code == 200, denied.text
    assert denied.json()["reason"] == "consent_required"
    response = await client.patch(
        f"api/v1/connections/{connection_id}", headers=logged_in_headers, json={"allow_non_interactive": True}
    )
    assert response.status_code == 200, response.text
    restored = await client.get(f"api/v1/triggers/{trigger_id}", headers=logged_in_headers)
    assert restored.status_code == 200, restored.text
    assert restored.json()["reason"] == "ready_to_resume"
    assert "resume" in restored.json()["allowed_actions"]
    async with session_scope() as session:
        assert (await session.get(ConnectionSecret, connection_id)).updated_at == original_updated_at


@pytest.mark.parametrize("consent", [False, True])
async def test_successful_repair_survives_trigger_and_flow_edits(client, active_user, logged_in_headers, consent):
    connection_id, trigger_id, flow_id = await make_rejected_trigger(active_user.id, consent=consent)
    async with session_scope() as session:
        connection = await session.get(Connection, connection_id)
        if consent:
            connection.allow_non_interactive = True
            session.add(connection)
        else:
            await broker.store_tokens(session, connection, {"version": 1, "access_token": "replacement"}, [SCOPE])
        failure_state = dict((await session.get(Trigger, trigger_id)).provider_state)
        await supervisor.mark_needs_reconnect(session, trigger_ids=[trigger_id], reason="Repeated failure")
        assert (await session.get(Trigger, trigger_id)).provider_state == failure_state

    patched = await client.patch(
        f"api/v1/triggers/{trigger_id}", headers=logged_in_headers, json={"name": "Renamed calendar"}
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["reason"] == "ready_to_resume"

    async with session_scope() as session:
        await reconcile_flow_triggers(
            session,
            flow_id=flow_id,
            owner_id=active_user.id,
            flow_data=calendar_flow("google/recovery"),
        )
    response = await client.get(f"api/v1/triggers/{trigger_id}", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    assert response.json()["reason"] == "ready_to_resume"
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        assert trigger.last_error is None
        assert trigger.provider_state == failure_state
        assert trigger.provider_state["cursor"] == "preserved"


async def test_rebinding_to_an_existing_ready_connection_does_not_require_reconnecting_it(
    client, active_user, logged_in_headers
):
    async with session_scope() as session:
        replacement = Connection(
            provider_key="google",
            name="replacement",
            display_name="Replacement",
            owner_id=active_user.id,
            executing_identity={"identity": "user_delegated"},
            allow_non_interactive=True,
        )
        session.add(replacement)
        await session.flush()
        await broker.store_tokens(session, replacement, {"version": 1, "access_token": "existing-token"}, [SCOPE])
        replacement_id = replacement.id
    _connection_id, trigger_id, flow_id = await make_rejected_trigger(active_user.id)
    async with session_scope() as session:
        await reconcile_flow_triggers(
            session, flow_id=flow_id, owner_id=active_user.id, flow_data=calendar_flow("google/replacement")
        )
    response = await client.get(f"api/v1/triggers/{trigger_id}", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "paused"
    assert "resume" in response.json()["allowed_actions"]
    assert "reconnect" not in response.json()["allowed_actions"]
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        assert trigger.connection_id == replacement_id
        assert trigger.provider_state == {}
