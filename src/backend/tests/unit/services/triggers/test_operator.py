"""Operator actions preserve owner intent and commit their audit atomically."""

from datetime import datetime, timezone

import pytest
from langflow.services.database.models.auth import AuthzAuditLog
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.database.models.trigger.schemas import TriggerBulkRequest
from langflow.services.deps import get_settings_service, get_trigger_service, session_scope
from langflow.services.triggers import operator
from langflow.services.triggers.constants import AUDIT_ADMIN_PAUSE, AUDIT_ADMIN_RESUME
from sqlmodel import select

pytestmark = pytest.mark.no_blockbuster

SCHEDULE = {"cron": "0 8 * * 1-5", "timezone": "UTC"}


@pytest.mark.parametrize(
    ("initial_state", "admin_action", "owner_action", "expected_state"),
    [
        ("active", "pause", "disable", "paused"),
        ("paused", "resume", "disable", "paused"),
        ("active", "pause", "enable", "active"),
        ("paused", "resume", "enable", "active"),
    ],
)
async def test_owner_action_refreshes_state_after_an_operator_change(
    make_trigger, trigger_owner, initial_state, admin_action, owner_action, expected_state
) -> None:
    trigger_id = await make_trigger(
        config=SCHEDULE,
        state=initial_state,
        admin_paused_at=datetime.now(timezone.utc) if initial_state == "paused" else None,
    )
    service = get_trigger_service()
    request = TriggerBulkRequest(trigger_ids=[trigger_id])
    async with session_scope() as owner_session:
        stale_row = await service.get(owner_session, trigger_id)
        async with session_scope() as admin_session:
            result = await getattr(operator, f"bulk_{admin_action}")(
                admin_session, service, request=request, actor_id=trigger_owner
            )
            assert result.changed == [trigger_id]
        await getattr(service, owner_action)(owner_session, row=stale_row)

    async with session_scope() as session:
        row = await service.get(session, trigger_id)
        assert row.state == expected_state
        assert row.admin_paused_at is None
        result = await operator.bulk_resume(session, service, request=request, actor_id=trigger_owner)
        assert result.unchanged == [trigger_id], "an owner's pause must never be re-armed by the operator"


@pytest.mark.parametrize(("enabled", "durable"), [(False, False), (True, False), (True, True)])
async def test_operator_changes_always_commit_their_audit(make_trigger, trigger_owner, monkeypatch, enabled, durable):
    trigger_id = await make_trigger(config=SCHEDULE)
    settings = get_settings_service().auth_settings
    monkeypatch.setattr(settings, "AUTHZ_AUDIT_ENABLED", enabled)
    monkeypatch.setattr(settings, "AUTHZ_AUDIT_DURABLE", durable)
    request = TriggerBulkRequest(trigger_ids=[trigger_id])
    service = get_trigger_service()
    for action in (operator.bulk_pause, operator.bulk_resume):
        async with session_scope() as session:
            result = await action(session, service, request=request, actor_id=trigger_owner)
            assert result.changed == [trigger_id]
            assert result.failed == []

    async with session_scope() as session:
        logs = (await session.exec(select(AuthzAuditLog).where(AuthzAuditLog.resource_id == trigger_id))).all()
    assert {row.action for row in logs} == {AUDIT_ADMIN_PAUSE, AUDIT_ADMIN_RESUME}
    assert len(logs) == 2
    assert all(row.user_id == trigger_owner for row in logs)


async def test_refused_resume_audits_the_release(make_trigger, trigger_owner, monkeypatch):
    trigger_id = await make_trigger(
        state="paused", admin_paused_at=datetime.now(timezone.utc), config={"cron": "invalid", "timezone": "UTC"}
    )
    settings = get_settings_service().auth_settings
    monkeypatch.setattr(settings, "AUTHZ_AUDIT_ENABLED", True)
    monkeypatch.setattr(settings, "AUTHZ_AUDIT_DURABLE", True)
    async with session_scope() as session:
        result = await operator.bulk_resume(
            session, get_trigger_service(), request=TriggerBulkRequest(trigger_ids=[trigger_id]), actor_id=trigger_owner
        )
        assert [failure.trigger_id for failure in result.failed] == [trigger_id]

    async with session_scope() as session:
        row = await session.get(Trigger, trigger_id)
        assert (row.state, row.admin_paused_at) == ("paused", None)
        logs = (await session.exec(select(AuthzAuditLog).where(AuthzAuditLog.resource_id == trigger_id))).all()
    assert len(logs) == 1
    assert logs[0].user_id == trigger_owner
    assert logs[0].action == AUDIT_ADMIN_RESUME
    assert logs[0].details["outcome"] == "enable_refused"
    assert logs[0].details["reason"] == result.failed[0].detail


@pytest.mark.parametrize("refused_resume", [False, True])
@pytest.mark.parametrize("failure_type", [RuntimeError, ValueError])
async def test_audit_failure_rolls_back_the_change_and_continues(
    make_trigger, trigger_owner, monkeypatch, refused_resume, failure_type
):
    from langflow.services import deps

    broken = await make_trigger(
        state="paused" if refused_resume else "active",
        admin_paused_at=datetime.now(timezone.utc) if refused_resume else None,
        config={"cron": "invalid", "timezone": "UTC"} if refused_resume else SCHEDULE,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    healthy = await make_trigger(
        state="paused" if refused_resume else "active",
        admin_paused_at=datetime.now(timezone.utc) if refused_resume else None,
        config=SCHEDULE,
        created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    authz = deps.get_authorization_service()
    real_stage = authz.stage_audit_events

    def fail_broken_audit(*, session, events):
        if any(isinstance(row, AuthzAuditLog) and row.resource_id == broken for row in session.new):
            msg = "simulated audit storage failure"
            raise failure_type(msg)
        real_stage(session=session, events=events)

    monkeypatch.setattr(authz, "stage_audit_events", fail_broken_audit)
    action = operator.bulk_resume if refused_resume else operator.bulk_pause
    async with session_scope() as session:
        result = await action(
            session,
            get_trigger_service(),
            request=TriggerBulkRequest(trigger_ids=[broken, healthy]),
            actor_id=trigger_owner,
        )
    assert result.changed == [healthy]
    assert [failure.trigger_id for failure in result.failed] == [broken]
    assert "simulated" not in result.failed[0].detail
    async with session_scope() as session:
        row = await session.get(Trigger, broken)
        assert row.state == ("paused" if refused_resume else "active")
        assert (row.admin_paused_at is not None) is refused_resume
        logs = (await session.exec(select(AuthzAuditLog).where(AuthzAuditLog.resource_id == broken))).all()
        assert logs == []
