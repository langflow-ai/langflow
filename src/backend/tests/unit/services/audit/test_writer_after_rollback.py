"""Failure and denial events: their own transaction, bounded, and never a second error."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import pytest
from langflow.services.audit import writer
from langflow.services.audit.details import AuditContractError
from langflow.services.audit.vocabulary import AuditErrorCode, AuditEventType, AuditResult
from langflow.services.audit.writer import MAX_CONCURRENT_INDEPENDENT_WRITES, record_audit_event_after_rollback
from langflow.services.database.models.audit_event.model import AuditEvent
from langflow.services.deps import session_scope
from sqlalchemy.exc import OperationalError
from sqlmodel import col, select

from .conftest import project_patch_draft


def _failed_draft(**overrides):
    values = {
        "result": AuditResult.FAILED,
        "error_code": AuditErrorCode.PROJECT_NAME_CONFLICT,
        "details": {"schema_version": 1, "attempted_fields": ["name"]},
    }
    values.update(overrides)
    return project_patch_draft(**values)


async def _events_for(resource_ids) -> list[AuditEvent]:
    async with session_scope() as session:
        statement = select(AuditEvent).where(col(AuditEvent.resource_id).in_(list(resource_ids)))
        return list((await session.exec(statement)).all())


@pytest.mark.usefixtures("client", "audit_enabled")
async def test_a_failure_is_persisted_in_its_own_transaction():
    draft = _failed_draft()

    assert await record_audit_event_after_rollback(draft) is True

    [event] = await _events_for([draft.resource_id])
    assert (event.event_type, event.result, event.error_code) == ("action", "failed", "PROJECT_NAME_CONFLICT")
    assert event.details == {"schema_version": 1, "attempted_fields": ["name"]}


@pytest.mark.usefixtures("client", "audit_disabled")
async def test_nothing_is_written_when_auditing_is_off():
    draft = _failed_draft()

    assert await record_audit_event_after_rollback(draft) is False
    assert await _events_for([draft.resource_id]) == []


@pytest.mark.usefixtures("client", "audit_enabled")
async def test_a_storage_outage_is_logged_and_never_raised_into_the_denied_caller(monkeypatch):
    @asynccontextmanager
    async def unavailable():
        msg = "database is unavailable"
        raise OperationalError(msg, None, Exception(msg))
        yield

    monkeypatch.setattr(writer, "session_scope", unavailable)
    denial = project_patch_draft(
        event_type=AuditEventType.AUTHZ,
        result=AuditResult.DENY,
        error_code=AuditErrorCode.PERMISSION_DENIED,
        details={"schema_version": 1},
    )

    assert await record_audit_event_after_rollback(denial) is False


@pytest.mark.usefixtures("client", "audit_enabled")
async def test_an_excluded_failure_is_not_written(excluded_events):
    excluded_events("project:write")
    draft = _failed_draft()

    assert await record_audit_event_after_rollback(draft) is False

    assert await _events_for([draft.resource_id]) == []


@pytest.mark.usefixtures("client", "audit_enabled")
async def test_excluding_an_action_also_drops_its_denials(excluded_events):
    excluded_events("project:*")
    denial = _failed_draft(
        event_type=AuditEventType.AUTHZ,
        result=AuditResult.DENY,
        error_code=AuditErrorCode.PERMISSION_DENIED,
        details={"schema_version": 1},
    )

    assert await record_audit_event_after_rollback(denial) is False

    assert await _events_for([denial.resource_id]) == []


@pytest.mark.usefixtures("client", "audit_enabled")
async def test_an_excluded_failure_opens_no_connection(monkeypatch, excluded_events):
    excluded_events("project:write")
    opened: list[bool] = []
    real_scope = writer.session_scope

    @asynccontextmanager
    async def recording_scope():
        opened.append(True)
        async with real_scope() as session:
            yield session

    monkeypatch.setattr(writer, "session_scope", recording_scope)

    assert await record_audit_event_after_rollback(_failed_draft()) is False
    assert opened == []


@pytest.mark.usefixtures("client", "audit_enabled")
async def test_a_failure_of_an_action_that_is_not_excluded_is_still_written(excluded_events):
    excluded_events("project:delete,flow:*")
    draft = _failed_draft()

    assert await record_audit_event_after_rollback(draft) is True

    assert len(await _events_for([draft.resource_id])) == 1


@pytest.mark.usefixtures("client", "audit_enabled")
async def test_a_contract_violation_surfaces_before_any_write():
    with pytest.raises(AuditContractError):
        await record_audit_event_after_rollback(_failed_draft(error_code=None))


@pytest.mark.usefixtures("client", "audit_enabled")
async def test_a_burst_of_failures_is_fully_persisted_through_a_bounded_number_of_connections(monkeypatch):
    in_flight = peak = 0
    real_scope = writer.session_scope

    @asynccontextmanager
    async def counting_scope():
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        try:
            async with real_scope() as session:
                yield session
        finally:
            in_flight -= 1

    monkeypatch.setattr(writer, "session_scope", counting_scope)
    drafts = [_failed_draft() for _ in range(40)]

    outcomes = await asyncio.gather(*(record_audit_event_after_rollback(draft) for draft in drafts))

    assert all(outcomes)
    assert peak <= MAX_CONCURRENT_INDEPENDENT_WRITES
    assert len(await _events_for([draft.resource_id for draft in drafts])) == 40


def _capture_outcomes(monkeypatch) -> list[str]:
    """The writer logs through structlog, which caplog does not see."""
    logged: list[str] = []

    async def _record(message, *args):  # noqa: ARG001
        logged.append(" ".join(str(arg) for arg in args))

    monkeypatch.setattr(writer.logger, "aerror", _record)
    return logged


@pytest.mark.usefixtures("client", "audit_enabled")
async def test_a_write_that_times_out_is_reported_as_unknown(monkeypatch):
    """The COMMIT may have landed, so the row may exist: not a certain loss."""

    @asynccontextmanager
    async def never_finishes():
        await asyncio.sleep(3600)
        yield

    monkeypatch.setattr(writer, "session_scope", never_finishes)
    monkeypatch.setattr(writer, "INDEPENDENT_WRITE_TIMEOUT_SECONDS", 0.01)
    logged = _capture_outcomes(monkeypatch)

    assert await record_audit_event_after_rollback(_failed_draft()) is False

    assert logged and logged[0].startswith("unknown ")
    assert logged[0].endswith("TimeoutError")


@pytest.mark.usefixtures("client", "audit_enabled")
async def test_waiting_for_a_slot_is_bounded_and_reported_as_not_persisted(monkeypatch):
    """A failing request cannot inherit the whole queue's write budget."""
    held = asyncio.Semaphore(0)

    @asynccontextmanager
    async def blocked():
        await held.acquire()
        yield

    monkeypatch.setattr(writer, "session_scope", blocked)
    # Only the queue is short: the holders must keep their slots while the
    # fifth request waits, or it would be served instead of timing out.
    monkeypatch.setattr(writer, "INDEPENDENT_WRITE_QUEUE_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(writer, "INDEPENDENT_WRITE_TIMEOUT_SECONDS", 30.0)
    logged = _capture_outcomes(monkeypatch)

    # Fill every slot, then ask for one more than the queue can serve.
    holders = [
        asyncio.create_task(record_audit_event_after_rollback(_failed_draft()))
        for _ in range(MAX_CONCURRENT_INDEPENDENT_WRITES)
    ]
    await asyncio.sleep(0.01)
    queued = await record_audit_event_after_rollback(_failed_draft())

    assert queued is False
    assert any(entry.startswith("not_persisted ") and entry.endswith("QueueTimeout") for entry in logged)
    for _ in holders:
        held.release()
    await asyncio.gather(*holders)
