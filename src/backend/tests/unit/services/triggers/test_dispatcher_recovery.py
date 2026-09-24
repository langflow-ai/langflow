"""Committed jobs survive interrupted trigger submission and bounded scans."""

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.database.models.jobs.model import Job, JobStatus, JobType
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.triggers import dispatcher, ledger
from sqlmodel import select

pytestmark = pytest.mark.no_blockbuster


@pytest.mark.parametrize("failure", [RuntimeError, asyncio.CancelledError])
async def test_trigger_recovers_the_committed_job_after_interrupted_submit(make_trigger, monkeypatch, failure):
    trigger_id = await make_trigger(max_attempts=1)
    async with session_scope() as session:
        event, _ = await ledger.append_event(session, trigger_id=trigger_id, dedupe_key="crash-window")
        event_id = event.id
    service = BackgroundExecutionService(get_settings_service())

    async def no_start():
        pass

    async def fail_dispatch(*_args, **_kwargs):
        message = "crash after durable job creation"
        raise failure(message)

    monkeypatch.setattr(service, "start", no_start)
    # The facade hands a submitted job to its backend; failing there is the
    # crash-after-durable-creation window this test recreates.
    monkeypatch.setattr(service._backend, "dispatch", fail_dispatch)
    monkeypatch.setattr(dispatcher, "_ensure_frame_source", lambda: None)
    monkeypatch.setattr("langflow.services.deps.get_background_execution_service", lambda: service)
    if failure is asyncio.CancelledError:
        with pytest.raises(asyncio.CancelledError):
            await dispatcher.run_once(owner="doomed")
        async with session_scope() as session:
            event = await session.get(TriggerEvent, event_id)
            assert event.state == "claimed"
            event.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            session.add(event)
        async with session_scope() as session:
            assert await dispatcher.sweep_expired_claims(session) == 1
    else:
        assert await dispatcher.run_once(owner="doomed") == 1
    async with session_scope() as session:
        event = await session.get(TriggerEvent, event_id)
        jobs = (
            await session.exec(select(Job).where(Job.flow_id == (await session.get(Trigger, trigger_id)).flow_id))
        ).all()
        assert len(jobs) == 1
        assert event.job_id == jobs[0].job_id == uuid5(NAMESPACE_URL, f"langflow:trigger-event:{event_id}")
        assert event.state == "dispatched"
        assert event.attempt == 0
    assert await dispatcher.run_once(owner="survivor") == 0


async def test_trigger_recovery_recognizes_a_legacy_attempt_key(make_trigger):
    trigger_id = await make_trigger(max_attempts=1)
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        event = TriggerEvent(
            trigger_id=trigger_id,
            dedupe_key="legacy",
            state="claimed",
            attempt=0,
            lease_owner="old-process",
            lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        session.add(event)
        await session.flush()
        job = Job(
            job_id=uuid4(),
            flow_id=trigger.flow_id,
            user_id=trigger.user_id,
            type=JobType.WORKFLOW,
            status=JobStatus.COMPLETED,
            dedupe_key=f"trg:{event.id}:0",
        )
        session.add(job)
        event_id, job_id = event.id, job.job_id
    async with session_scope() as session:
        assert await dispatcher.sweep_expired_claims(session) == 1
        assert await dispatcher.reconcile_dispatched(session) == 1
        event = await session.get(TriggerEvent, event_id)
        assert event.state == "completed"
        assert event.job_id == job_id
        assert event.attempt == 0


async def test_capped_triggers_are_excluded_before_the_claim_limit(make_trigger):
    now = datetime.now(timezone.utc)
    for _index in range(25):
        trigger_id = await make_trigger()
        async with session_scope() as session:
            session.add(TriggerEvent(trigger_id=trigger_id, dedupe_key="in-flight", state="dispatched"))
            await ledger.append_event(
                session, trigger_id=trigger_id, dedupe_key="waiting", available_at=now - timedelta(minutes=1)
            )
    eligible = await make_trigger()
    async with session_scope() as session:
        event, _ = await ledger.append_event(session, trigger_id=eligible, dedupe_key="ready", available_at=now)
        event_id = event.id
    async with session_scope() as session:
        claimed = await dispatcher.claim_batch(session, owner="fair", limit=25, lease_ttl_s=60)
        assert [event.id for event in claimed] == [event_id]


async def test_terminal_jobs_are_selected_before_the_reconciliation_limit(make_trigger):
    trigger_id = await make_trigger()
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        for index in range(201):
            job = Job(
                job_id=uuid4(),
                flow_id=trigger.flow_id,
                user_id=trigger.user_id,
                status=JobStatus.SUSPENDED if index < 200 else JobStatus.COMPLETED,
            )
            session.add(job)
            event = TriggerEvent(
                trigger_id=trigger_id, dedupe_key=f"job:{index}", state="dispatched", job_id=job.job_id
            )
            session.add(event)
        completed_id = event.id
    async with session_scope() as session:
        assert await dispatcher.reconcile_dispatched(session) == 1
        assert (await session.get(TriggerEvent, completed_id)).state == "completed"


async def test_concurrent_claimers_respect_one_shared_capacity_limit(make_trigger):
    trigger_id = await make_trigger(concurrency_limit=1)
    async with session_scope() as session:
        for index in range(6):
            await ledger.append_event(session, trigger_id=trigger_id, dedupe_key=f"claim:{index}")

    async def claim(owner):
        async with session_scope() as session:
            return await dispatcher.claim_batch(session, owner=owner, limit=4, lease_ttl_s=60)

    batches = await asyncio.gather(claim("a"), claim("b"), claim("c"))
    assert sum(map(len, batches)) == 1


async def test_overlapping_dispatchers_cannot_insert_two_jobs_for_one_event(make_trigger, monkeypatch):
    trigger_id = await make_trigger()
    async with session_scope() as session:
        event, _ = await ledger.append_event(session, trigger_id=trigger_id, dedupe_key="overlap")
        event.state = "claimed"
        event.lease_owner = "replica"
        session.add(event)
        event_id = event.id
    service = BackgroundExecutionService(get_settings_service())

    async def no_start():
        pass

    enqueues = []

    async def dispatch(job_id, **_kwargs):
        enqueues.append(job_id)

    monkeypatch.setattr(service, "start", no_start)
    monkeypatch.setattr(service._backend, "dispatch", dispatch)
    monkeypatch.setattr(dispatcher, "_ensure_frame_source", lambda: None)
    monkeypatch.setattr("langflow.services.deps.get_background_execution_service", lambda: service)

    async def submit():
        async with session_scope() as session:
            await dispatcher.dispatch_event(session, await session.get(TriggerEvent, event_id))

    await asyncio.gather(submit(), submit())
    async with session_scope() as session:
        event = await session.get(TriggerEvent, event_id)
        jobs = (await session.exec(select(Job).where(Job.dedupe_key == f"trg:{event_id}"))).all()
        assert len(jobs) == 1
        assert event.job_id == jobs[0].job_id
        assert event.state == "dispatched"
        assert service._reconstruct_request(jobs[0])["execution_family"] == "trigger_listener"
    assert enqueues == [event.job_id]
