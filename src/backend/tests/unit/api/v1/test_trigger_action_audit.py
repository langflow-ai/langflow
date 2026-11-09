"""Owner actions commit their audit evidence with the trigger or replay row."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from langflow.services.authorization import audit
from langflow.services.database.models.auth import AuthzAuditLog
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from langflow.services.triggers.service import TriggerService
from sqlmodel import select

from tests.unit.services.triggers import test_provider_lifecycle as provider_tests

pytestmark = pytest.mark.no_blockbuster
pilot = provider_tests.pilot


@pytest.fixture
async def audited_trigger(client, logged_in_headers, flow):
    response = await client.post(
        "api/v1/triggers",
        json={"flow_id": str(flow.id), "name": "Audited schedule", "kind": "schedule", "config": {"cron": "0 * * * *"}},
        headers=logged_in_headers,
    )
    assert response.status_code == 201, response.text
    trigger_id = UUID(response.json()["id"])
    async with session_scope() as session:
        event = TriggerEvent(trigger_id=trigger_id, dedupe_key="original", payload={"private": "event-body"})
        session.add(event)
        await session.flush()
        event_id = event.id
    return trigger_id, event_id


async def _mutation_rows(trigger_id):
    async with session_scope() as session:
        rows = (await session.exec(select(AuthzAuditLog).where(AuthzAuditLog.resource_id == trigger_id))).all()
        return [row for row in rows if (row.details or {}).get("event") == "mutation"]


@pytest.mark.parametrize(
    ("endpoint", "action", "status"),
    [("enable", "trigger:resume", 200), ("disable", "trigger:pause", 200), ("replay", "trigger:replay", 202)],
)
@pytest.mark.parametrize("api_key", [False, True], ids=["user", "api-key"])
async def test_owner_mutations_have_durable_actor_attribution(
    client, logged_in_headers, active_user, audited_trigger, endpoint, action, status, api_key
):
    trigger_id, event_id = audited_trigger
    headers = logged_in_headers
    key = None
    if api_key:
        created = await client.post("api/v1/api_key/", json={"name": "trigger-audit"}, headers=headers)
        assert created.status_code == 200, created.text
        key = created.json()
        headers = {"x-api-key": key["api_key"]}
        client.cookies.clear()
    response = await client.post(
        f"api/v1/triggers/{trigger_id}/{endpoint}",
        headers=headers,
        json={"event_id": str(event_id)} if endpoint == "replay" else None,
    )
    assert response.status_code == status, response.text
    rows = await _mutation_rows(trigger_id)
    assert len(rows) == 1
    row = rows[0]
    assert (row.action, row.user_id, row.result, row.resource_type) == (action, active_user.id, "allow", "trigger")
    assert row.actor_type == ("api_key" if api_key else "user")
    assert row.actor_id == (UUID(key["id"]) if key else active_user.id)
    if key:
        assert row.details["api_key_id"] == key["id"]
        assert key["api_key"] not in str(row.details)
    if endpoint == "replay":
        assert row.details["original_event_id"] == str(event_id)
        assert row.details["replay_event_id"] == response.json()["id"]
    assert "event-body" not in str(row.details)
    assert "payload" not in row.details


@pytest.mark.parametrize("endpoint", ["enable", "disable", "replay"])
@pytest.mark.parametrize("failure_point", ["stage", "insert"])
async def test_required_audit_failure_rolls_back_mutation(
    client, logged_in_headers, audited_trigger, monkeypatch, endpoint, failure_point
):
    trigger_id, event_id = audited_trigger

    def fail_audit(**kwargs):
        if kwargs.get("required"):
            message = "database-private-detail"
            raise ValueError(message)
        return False

    from sqlalchemy import event as sqlalchemy_event

    def fail_insert(_mapper, _connection, _target):
        message = "audit insert unavailable"
        raise RuntimeError(message)

    if failure_point == "stage":
        monkeypatch.setattr(audit, "stage_audit_decision", fail_audit)
    else:
        sqlalchemy_event.listen(AuthzAuditLog, "before_insert", fail_insert)
    try:
        with pytest.raises(audit.AuditPersistenceError):
            await client.post(
                f"api/v1/triggers/{trigger_id}/{endpoint}",
                headers=logged_in_headers,
                json={"event_id": str(event_id)} if endpoint == "replay" else None,
            )
    finally:
        if failure_point == "insert":
            sqlalchemy_event.remove(AuthzAuditLog, "before_insert", fail_insert)
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        events = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger_id))).all()
        assert trigger.state == "pending"
        assert [event.id for event in events] == [event_id]
    assert await _mutation_rows(trigger_id) == []


async def test_resume_is_committed_and_audited_before_provider_activation(
    client, logged_in_headers, active_user, flow, pilot, monkeypatch
):
    from langflow.services.triggers import source_runtime

    await provider_tests._connection(active_user.id)
    trigger = await provider_tests._reconcile(flow.id, active_user.id)

    async def fail_activation(trigger_id):
        assert trigger_id == trigger.id
        async with session_scope() as independent:
            persisted = await independent.get(Trigger, trigger_id)
            assert persisted.state == "pending"
            assert persisted.config["mechanism_id"] == "pilot.webhook"
        assert [entry.action for entry in await _mutation_rows(trigger_id)] == ["trigger:resume"]
        message = "provider unavailable"
        raise RuntimeError(message)

    monkeypatch.setattr(source_runtime, "initialize_source", fail_activation)
    with pytest.raises(RuntimeError, match="provider unavailable"):
        await client.post(f"api/v1/triggers/{trigger.id}/enable", headers=logged_in_headers)
    assert [row.action for row in await _mutation_rows(trigger.id)] == ["trigger:resume"]
    assert pilot.provisions == []


async def test_policy_blocked_resume_keeps_safe_403_without_a_success_audit(
    client, logged_in_headers, audited_trigger, monkeypatch
):
    from lfx.integrations.errors import IntegrationPolicyBlockedError

    trigger_id, _event_id = audited_trigger

    async def blocked(_self, _session, *, row):  # noqa: ARG001
        raise IntegrationPolicyBlockedError(provider="example", policy_key="private-policy-key")

    monkeypatch.setattr(TriggerService, "enable", blocked)
    response = await client.post(f"api/v1/triggers/{trigger_id}/enable", headers=logged_in_headers)
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["error_code"] == "policy-blocked"
    assert "private-policy-key" not in response.text
    assert await _mutation_rows(trigger_id) == []


async def test_expired_replay_does_not_write_a_success_mutation(client, logged_in_headers, audited_trigger):
    trigger_id, event_id = audited_trigger
    async with session_scope() as session:
        event = await session.get(TriggerEvent, event_id)
        event.created_at = datetime.now(timezone.utc) - timedelta(days=365)
        session.add(event)
    response = await client.post(
        f"api/v1/triggers/{trigger_id}/replay", json={"event_id": str(event_id)}, headers=logged_in_headers
    )
    assert response.status_code == 409, response.text
    assert await _mutation_rows(trigger_id) == []


async def test_replays_are_queryable_by_action_event_and_thirty_day_window(
    client, logged_in_headers, active_user, audited_trigger
):
    trigger_id, event_id = audited_trigger
    response = await client.post(
        f"api/v1/triggers/{trigger_id}/replay", json={"event_id": str(event_id)}, headers=logged_in_headers
    )
    assert response.status_code == 202, response.text
    replay_event_id = response.json()["id"]
    denied = await client.get("api/v1/authz/audit", headers=logged_in_headers)
    assert denied.status_code == 403
    async with session_scope() as session:
        user = await session.get(User, active_user.id)
        user.is_superuser = True
        session.add(user)
        session.add(
            AuthzAuditLog(
                user_id=active_user.id,
                action="trigger:replay",
                resource_type="trigger",
                resource_id=trigger_id,
                result="allow",
                details={"event": "mutation"},
                timestamp=datetime.now(timezone.utc) - timedelta(days=31),
            )
        )
    response = await client.get(
        "api/v1/authz/audit",
        headers=logged_in_headers,
        params={
            "action": "trigger:replay",
            "event": "mutation",
            "resource_id": str(trigger_id),
            "since": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    row = response.json()["items"][0]
    assert row["user_id"] == str(active_user.id)
    assert row["details"]["replay_event_id"] == replay_event_id


@pytest.mark.parametrize("endpoint", ["enable", "disable", "replay"])
@pytest.mark.parametrize("error_type", [RuntimeError, ValueError])
async def test_required_audit_insert_failure_returns_safe_http_error_and_rolls_back(
    client, logged_in_headers, audited_trigger, endpoint, error_type
):
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import event as sqlalchemy_event

    trigger_id, event_id = audited_trigger
    private_message = "private-audit-database-detail"

    def fail_insert(_mapper, _connection, _target):
        raise error_type(private_message)

    sqlalchemy_event.listen(AuthzAuditLog, "before_insert", fail_insert)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=client._transport.app, raise_app_exceptions=False),
            base_url=client.base_url,
        ) as http_client:
            response = await http_client.post(
                f"api/v1/triggers/{trigger_id}/{endpoint}",
                headers=logged_in_headers,
                json={"event_id": str(event_id)} if endpoint == "replay" else None,
            )
    finally:
        sqlalchemy_event.remove(AuthzAuditLog, "before_insert", fail_insert)
    assert response.status_code == 500, response.text
    assert private_message not in response.text
    assert response.json() == {"message": str(audit.AuditPersistenceError())}
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        events = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger_id))).all()
        assert trigger.state == "pending"
        assert [event.id for event in events] == [event_id]
    assert await _mutation_rows(trigger_id) == []


@pytest.mark.parametrize("error_type", [RuntimeError, ValueError])
async def test_required_resume_commit_failure_returns_safe_http_error_and_rolls_back(
    client, logged_in_headers, audited_trigger, error_type
):
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import event as sqlalchemy_event
    from sqlalchemy.orm import Session

    trigger_id, event_id = audited_trigger
    private_message = "private-audit-commit-detail"

    def fail_commit(_session):
        raise error_type(private_message)

    sqlalchemy_event.listen(Session, "before_commit", fail_commit)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=client._transport.app, raise_app_exceptions=False),
            base_url=client.base_url,
        ) as http_client:
            response = await http_client.post(f"api/v1/triggers/{trigger_id}/enable", headers=logged_in_headers)
    finally:
        sqlalchemy_event.remove(Session, "before_commit", fail_commit)
    assert response.status_code == 500, response.text
    assert private_message not in response.text
    assert response.json() == {"message": str(audit.AuditPersistenceError())}
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        events = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger_id))).all()
        assert trigger.state == "pending"
        assert [event.id for event in events] == [event_id]
    assert await _mutation_rows(trigger_id) == []
