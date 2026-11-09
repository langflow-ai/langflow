"""Stale workers and watchdog reads must not mutate a newer job lease."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.background_execution.db_backend import DBBackgroundQueue
from langflow.services.database.models.jobs.model import ExecutionSignal, Job, JobEvent, JobStatus, SignalType
from langflow.services.jobs import service as jobs_module
from langflow.services.jobs.exceptions import HUMAN_INPUT_REQUIRED_EVENT, JobNotClaimable
from langflow.services.jobs.service import JobService
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture(params=["sqlite", "postgresql"])
async def lease_database(request, tmp_path, monkeypatch):
    admin = None
    schema = f"leasefencing_{uuid4().hex}"
    if request.param == "sqlite":
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'jobs.db'}")
    else:
        url = os.environ.get("LANGFLOW_TEST_POSTGRES_URL") or os.environ.get("LANGFLOW_TEST_DATABASE_URI")
        if not url:
            pytest.skip("LANGFLOW_TEST_POSTGRES_URL or LANGFLOW_TEST_DATABASE_URI is not set")
        url = url.replace("postgresql://", "postgresql+psycopg://", 1).replace(
            "postgres://", "postgresql+psycopg://", 1
        )
        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(CreateSchema(schema))
        engine = create_async_engine(url, connect_args={"options": f"-csearch_path={schema}"})

    @asynccontextmanager
    async def session_scope():
        async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
            yield session

    monkeypatch.setattr(jobs_module, "session_scope", session_scope)
    try:
        async with engine.begin() as connection:
            for model in (Job, JobEvent, ExecutionSignal):
                await connection.run_sync(model.__table__.create)
        yield JobService()
    finally:
        await engine.dispose()
        if admin is not None:
            async with admin.begin() as connection:
                await connection.execute(DropSchema(schema, cascade=True))
            await admin.dispose()


async def _job(service, *, status=JobStatus.IN_PROGRESS, owner="worker:a", **metadata):
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(job_id, status)
    stale = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    await service.update_job_metadata(job_id, {"owner": owner, "heartbeat_at": stale, **metadata})
    return job_id


async def test_heartbeat_cannot_replace_a_newer_claim(lease_database):
    service = lease_database
    job_id = await _job(service, status=JobStatus.QUEUED)
    assert await service.claim_queued_lease(job_id, owner="worker:b", lease_ttl_s=45)
    assert await service.begin_live_job(job_id, owner="worker:b")
    prior = await service.get_job_by_job_id(job_id)

    assert await service.heartbeat(job_id, owner="worker:a") is False

    current = await service.get_job_by_job_id(job_id)
    assert current.job_metadata == prior.job_metadata
    assert current.lease_heartbeat_at == prior.lease_heartbeat_at
    assert await service.begin_live_job(job_id, owner="worker:a") is False


async def test_heartbeat_loses_when_the_owner_changes_after_its_read(lease_database, monkeypatch):
    service = lease_database
    job_id = await _job(service)
    real_exec = AsyncSession.exec
    change_owner = True

    async def exec_after_reclaim(session, statement, *args, **kwargs):
        nonlocal change_owner
        if change_owner and statement.is_update:
            change_owner = False
            await service.update_job_metadata(job_id, {"owner": "worker:b"})
        return await real_exec(session, statement, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "exec", exec_after_reclaim)

    assert await service.heartbeat(job_id, owner="worker:a") is False

    current = await service.get_job_by_job_id(job_id)
    assert current.job_metadata["owner"] == "worker:b"


@pytest.mark.parametrize("status", [JobStatus.FAILED, JobStatus.COMPLETED, JobStatus.SUSPENDED])
async def test_heartbeat_does_not_renew_finished_or_paused_work(lease_database, status):
    service = lease_database
    job_id = await _job(service, status=status)
    prior = await service.get_job_by_job_id(job_id)

    assert await service.heartbeat(job_id, owner="worker:a") is False

    current = await service.get_job_by_job_id(job_id)
    assert current.job_metadata == prior.job_metadata
    assert current.lease_heartbeat_at == prior.lease_heartbeat_at


async def test_heartbeat_can_initialize_and_renew_an_unowned_local_job(lease_database):
    service = lease_database
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())

    assert await service.heartbeat(job_id, owner="api:a") is True
    assert await service.heartbeat(job_id, owner="api:a") is True

    current = await service.get_job_by_job_id(job_id)
    assert current.job_metadata["owner"] == "api:a"
    assert current.lease_heartbeat_at is not None


@pytest.mark.parametrize("retry_safe", [False, True])
@pytest.mark.parametrize("new_owner", ["worker:a", "worker:b"])
async def test_watchdog_must_not_mutate_a_refreshed_or_reclaimed_lease(
    lease_database, monkeypatch, retry_safe, new_owner
):
    service = lease_database
    job_id = await _job(service, retry_safe=retry_safe, attempt=1, max_attempts=2)
    method_name = "retry_requeue_claim" if retry_safe else "fail_in_progress_job"
    transition = getattr(service, method_name)

    async def refreshed_transition(transition_job_id, **kwargs):
        # Commit a fresh lease after the watchdog read and before its UPDATE.
        if new_owner != "worker:a":
            await service.update_job_metadata(transition_job_id, {"owner": new_owner})
        await service.heartbeat(transition_job_id, owner=new_owner)
        return await transition(transition_job_id, **kwargs)

    monkeypatch.setattr(service, method_name, refreshed_transition)

    assert await DBBackgroundQueue(job_service=service).requeue_lost() == []

    current = await service.get_job_by_job_id(job_id)
    assert current.status == JobStatus.IN_PROGRESS
    assert current.job_metadata["owner"] == new_owner
    assert current.job_metadata["attempt"] == 1
    assert current.error is None
    assert await service.read_events(job_id) == []


async def test_a_late_pause_cannot_reopen_a_terminal_job(lease_database):
    service = lease_database
    job_id = await _job(service)
    assert await service.fail_in_progress_job(job_id, error={"type": "worker_lost"})

    assert await service.suspend_job(job_id, {"pending_request_id": "late"}) is None

    current = await service.get_job_by_job_id(job_id)
    assert current.status == JobStatus.FAILED
    assert current.error == {"type": "worker_lost"}
    assert "pending_request_id" not in current.job_metadata


async def test_pause_requires_the_current_owner_and_writes_no_losing_event(lease_database):
    service = lease_database
    job_id = await _job(service, owner="worker:b")

    assert (
        await service.suspend_job(
            job_id, {"pending_request_id": "late"}, owner="worker:a", event_payload={"request_id": "late"}
        )
        is None
    )

    current = await service.get_job_by_job_id(job_id)
    assert current.status == JobStatus.IN_PROGRESS
    assert "pending_request_id" not in current.job_metadata
    assert await service.read_events(job_id) == []


async def test_pause_loses_when_the_job_finishes_after_its_read(lease_database, monkeypatch):
    service = lease_database
    job_id = await _job(service)
    real_exec = AsyncSession.exec
    finish = True

    async def exec_after_completion(session, statement, *args, **kwargs):
        nonlocal finish
        if finish and statement.is_update:
            finish = False
            await service.update_job_status(job_id, JobStatus.COMPLETED, finished_timestamp=True)
        return await real_exec(session, statement, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "exec", exec_after_completion)

    assert (
        await service.suspend_job(
            job_id, {"pending_request_id": "late"}, owner="worker:a", event_payload={"request_id": "late"}
        )
        is None
    )

    current = await service.get_job_by_job_id(job_id)
    assert current.status == JobStatus.COMPLETED
    assert "pending_request_id" not in current.job_metadata
    assert await service.read_events(job_id) == []


async def test_pause_event_collision_retries_the_entire_transition(lease_database, monkeypatch):
    service = lease_database
    job_id = await _job(service)
    real_flush = AsyncSession.flush
    collision = True

    async def flush_with_collision(session, *args, **kwargs):
        nonlocal collision
        if collision and any(isinstance(row, JobEvent) for row in session.new):
            collision = False
            message = "event sequence collision"
            raise IntegrityError(message, {}, Exception("duplicate sequence"))
        return await real_flush(session, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "flush", flush_with_collision)
    current = await service.suspend_job(
        job_id, {"pending_request_id": "pause"}, owner="worker:a", event_payload={"request_id": "pause"}
    )

    assert collision is False
    assert current.status == JobStatus.SUSPENDED
    assert current.job_metadata["pending_request_id"] == "pause"
    events = await service.read_events(job_id)
    assert [(event.event_type, event.payload) for event in events] == [
        (HUMAN_INPUT_REQUIRED_EVENT, {"request_id": "pause"})
    ]


async def test_claim_loss_while_running_does_not_write_a_terminal_status(lease_database):
    service = lease_database
    job_id = await _job(service)

    async def lose_claim():
        message = "lease renewal lost"
        raise JobNotClaimable(message)

    with pytest.raises(JobNotClaimable):
        await service.execute_with_status(job_id, lose_claim, owner="worker:a", mark_in_progress=False)

    current = await service.get_job_by_job_id(job_id)
    assert current.status == JobStatus.IN_PROGRESS
    assert current.finished_timestamp is None


async def test_cancel_stop_requires_a_pending_stop(lease_database):
    service = lease_database
    job_id = await _job(service)
    await service.write_signal(job_id, SignalType.RESUME)

    assert await service.cancel_job_for_stop(job_id, owner="worker:a") is False

    current = await service.get_job_by_job_id(job_id)
    assert current.status == JobStatus.IN_PROGRESS
    assert [signal.signal_type for signal in await service.unconsumed_signals(job_id)] == [SignalType.RESUME]


@pytest.mark.parametrize("owner", [None, "worker:a"])
async def test_cancel_stop_allows_a_same_owner_late_stop_over_completion(lease_database, owner):
    service = lease_database
    job_id = await _job(service, status=JobStatus.COMPLETED, owner=owner)
    await service.write_signal(job_id, SignalType.STOP)

    assert await service.cancel_job_for_stop(job_id, owner="worker:a") is True

    current = await service.get_job_by_job_id(job_id)
    assert current.status == JobStatus.CANCELLED
    assert current.finished_timestamp is not None
    assert await service.unconsumed_signals(job_id) == []
    assert await service.cancel_job_for_stop(job_id, owner="worker:a") is False


async def test_cancel_stop_does_not_cancel_or_consume_a_newer_owners_stop(lease_database):
    service = lease_database
    job_id = await _job(service, owner="worker:b")
    await service.write_signal(job_id, SignalType.STOP)

    assert await service.cancel_job_for_stop(job_id, owner="worker:a") is False

    current = await service.get_job_by_job_id(job_id)
    assert current.status == JobStatus.IN_PROGRESS
    assert [signal.signal_type for signal in await service.unconsumed_signals(job_id)] == [SignalType.STOP]


async def test_cancel_stop_loses_when_the_owner_changes_after_its_read(lease_database, monkeypatch):
    service = lease_database
    job_id = await _job(service)
    await service.write_signal(job_id, SignalType.STOP)
    real_exec = AsyncSession.exec
    change_owner = True

    async def exec_after_reclaim(session, statement, *args, **kwargs):
        nonlocal change_owner
        if change_owner and statement.is_update:
            change_owner = False
            await service.update_job_metadata(job_id, {"owner": "worker:b"})
        return await real_exec(session, statement, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "exec", exec_after_reclaim)

    assert await service.cancel_job_for_stop(job_id, owner="worker:a") is False

    current = await service.get_job_by_job_id(job_id)
    assert current.status == JobStatus.IN_PROGRESS
    assert current.job_metadata["owner"] == "worker:b"
    assert [signal.signal_type for signal in await service.unconsumed_signals(job_id)] == [SignalType.STOP]


async def test_cancel_stop_rolls_back_status_if_signal_consumption_fails(lease_database, monkeypatch):
    service = lease_database
    job_id = await _job(service)
    await service.write_signal(job_id, SignalType.STOP)
    real_exec = AsyncSession.exec

    async def exec_failing_signal_update(session, statement, *args, **kwargs):
        if statement.is_update and statement.table.name == ExecutionSignal.__tablename__:
            message = "signal consumption failed"
            raise RuntimeError(message)
        return await real_exec(session, statement, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "exec", exec_failing_signal_update)

    with pytest.raises(RuntimeError, match="signal consumption failed"):
        await service.cancel_job_for_stop(job_id, owner="worker:a")

    current = await service.get_job_by_job_id(job_id)
    assert current.status == JobStatus.IN_PROGRESS
    assert current.finished_timestamp is None
    assert [signal.signal_type for signal in await service.unconsumed_signals(job_id)] == [SignalType.STOP]


async def test_cancel_stop_has_one_winner(lease_database):
    service = lease_database
    job_id = await _job(service)
    await service.write_signal(job_id, SignalType.STOP)

    results = await asyncio.gather(*(service.cancel_job_for_stop(job_id, owner="worker:a") for _ in range(6)))

    assert results.count(True) == 1
    assert (await service.get_job_by_job_id(job_id)).status == JobStatus.CANCELLED
    assert await service.unconsumed_signals(job_id) == []


@pytest.mark.parametrize("field", ["result", "error"])
@pytest.mark.parametrize(
    ("status", "owner"),
    [(JobStatus.IN_PROGRESS, "worker:b"), (JobStatus.FAILED, "worker:a"), (JobStatus.COMPLETED, "worker:a")],
)
async def test_live_payload_rejects_reclaimed_or_finished_jobs(lease_database, field, status, owner):
    service = lease_database
    job_id = await _job(service, status=status, owner=owner)
    await getattr(service, f"set_{field}")(job_id, {"existing": "verdict"})

    assert await getattr(service, f"set_live_{field}")(job_id, {"stale": "verdict"}, owner="worker:a") is False

    current = await service.get_job_by_job_id(job_id)
    assert current.status == status
    assert current.job_metadata["owner"] == owner
    assert getattr(current, field) == {"existing": "verdict"}


@pytest.mark.parametrize("field", ["result", "error"])
@pytest.mark.parametrize("owner", [None, "worker:a"])
async def test_live_payload_writes_own_live_job(lease_database, field, owner):
    service = lease_database
    job_id = await _job(service, owner=owner)
    other_field = "error" if field == "result" else "result"
    await getattr(service, f"set_{other_field}")(job_id, {"other": "preserved"})

    assert await getattr(service, f"set_live_{field}")(job_id, {"current": "verdict"}, owner="worker:a") is True

    current = await service.get_job_by_job_id(job_id)
    assert current.status == JobStatus.IN_PROGRESS
    assert getattr(current, field) == {"current": "verdict"}
    assert getattr(current, other_field) == {"other": "preserved"}
