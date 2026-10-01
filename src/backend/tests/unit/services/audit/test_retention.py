"""Retention deletes by age alone, and the sweep never runs where auditing is off."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from langflow.services.audit.retention import AuditEventCleanupWorker, purge_expired_audit_events
from langflow.services.audit.writer import build_audit_event
from langflow.services.database.models.audit_event.model import AuditEvent
from langflow.services.deps import get_settings_service
from sqlmodel import select

from .conftest import project_patch_draft

NOW = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)


async def _event_aged(session, days: float) -> AuditEvent:
    event = build_audit_event(project_patch_draft())
    event.timestamp = NOW - timedelta(days=days)
    session.add(event)
    await session.commit()
    return event


async def test_events_past_the_window_are_deleted_and_the_rest_survive(audit_session):
    await _event_aged(audit_session, 91)
    await _event_aged(audit_session, 400)
    boundary = await _event_aged(audit_session, 89.99)
    fresh = await _event_aged(audit_session, 0)

    deleted = await purge_expired_audit_events(audit_session, retention_days=90, now=NOW)
    await audit_session.commit()

    survivors = {event.id for event in (await audit_session.exec(select(AuditEvent))).all()}
    assert deleted == 2
    assert survivors == {boundary.id, fresh.id}


async def test_a_zero_window_keeps_everything(audit_session):
    await _event_aged(audit_session, 10_000)

    assert await purge_expired_audit_events(audit_session, retention_days=0, now=NOW) == 0
    assert len((await audit_session.exec(select(AuditEvent))).all()) == 1


async def test_the_sweep_still_runs_when_production_is_off(audit_disabled):  # noqa: ARG001
    """Rows written before the switch was turned off must keep ageing out."""
    worker = AuditEventCleanupWorker(interval=0.01)

    await worker.start()
    try:
        assert worker._task is not None
    finally:
        await worker.stop()

    assert worker._task is None


async def test_the_sweep_is_not_scheduled_when_retention_is_disabled(audit_enabled):  # noqa: ARG001
    settings = get_settings_service().settings
    original = settings.audit_retention_days
    settings.audit_retention_days = 0
    try:
        worker = AuditEventCleanupWorker(interval=0.01)
        await worker.start()
        assert worker._task is None
    finally:
        settings.audit_retention_days = original


async def test_the_sweep_runs_and_stops_cleanly_when_enabled(audit_enabled):  # noqa: ARG001
    worker = AuditEventCleanupWorker(interval=3600)

    await worker.start()
    try:
        assert worker._task is not None
        assert not worker._task.done()
    finally:
        await worker.stop()

    assert worker._task is None
