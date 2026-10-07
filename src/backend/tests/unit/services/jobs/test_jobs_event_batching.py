"""Durability, cancellation, and pool usage for batched event appends."""

import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from langflow.services.database.models.jobs.model import JobEvent
from langflow.services.jobs import service as jobs_module
from langflow.services.jobs.service import JobService
from sqlalchemy import event
from sqlalchemy.exc import DataError, IntegrityError, OperationalError, StatementError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

pytestmark = pytest.mark.no_blockbuster


class _EventStore:
    def __init__(self, engine):
        self.engine = engine
        self.checkouts = 0
        self.active_sessions = 0
        self.checkout_started = asyncio.Event()
        self.allow_checkout = asyncio.Event()
        self.allow_checkout.set()
        self.commit_started = asyncio.Event()
        self.allow_commit = asyncio.Event()
        self.allow_commit.set()
        self.fail_commit = False
        self.commit_failures = []
        self.commit_failure = None
        # Unlike commit_failures (a one-shot queue, for simulating transient contention),
        # this fails every flush whose batch contains the marker payload -- a retry of the
        # same bad data must keep failing, the way a real DataError would.
        self.fail_payload_marker = None
        self.fail_payload_exception = None

    @asynccontextmanager
    async def _with_session(self):
        self.checkouts += 1
        store = self

        class _ControlledSession(AsyncSession):
            async def commit(self):
                store.commit_started.set()
                await store.allow_commit.wait()
                await super().commit()

        async with _ControlledSession(self.engine, expire_on_commit=False) as session:
            self.active_sessions += 1
            try:
                self.checkout_started.set()
                await self.allow_checkout.wait()
                if self.fail_commit or self.commit_failures or self.commit_failure is not None:

                    def fail_commit(_session):
                        if self.commit_failures:
                            raise self.commit_failures.pop(0)
                        if self.commit_failure is not None:
                            raise self.commit_failure
                        msg = "injected commit failure"
                        raise RuntimeError(msg)

                    event.listen(session.sync_session, "before_commit", fail_commit)
                if self.fail_payload_marker is not None:

                    def fail_on_marker(flush_session, _ctx, _instances):
                        for obj in flush_session.new:
                            if isinstance(obj, JobEvent) and obj.payload == store.fail_payload_marker:
                                raise store.fail_payload_exception

                    event.listen(session.sync_session, "before_flush", fail_on_marker)
                yield session
            finally:
                self.active_sessions -= 1

    async def events(self):
        async with AsyncSession(self.engine) as session:
            return list((await session.exec(select(JobEvent).order_by(JobEvent.seq))).all())


@pytest.fixture
async def event_store(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'events.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(JobEvent.__table__.create)
    store = _EventStore(engine)
    monkeypatch.setattr("lfx.services.deps.get_db_service", lambda: store)
    try:
        yield store
    finally:
        await engine.dispose()


async def _finish_tasks(tasks):
    for task in tasks:
        if not task.done():
            task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


async def test_append_waits_for_commit_before_returning(event_store):
    event_store.allow_commit.clear()
    service = JobService()
    job_id = uuid4()
    tasks = [asyncio.create_task(service.append_event(job_id, "event", {})) for _ in range(2)]
    try:
        await asyncio.wait_for(event_store.commit_started.wait(), timeout=2)
        await asyncio.sleep(0)
        assert all(not task.done() for task in tasks), "append returned before the event was committed"
        assert await event_store.events() == []
        event_store.allow_commit.set()
        assert await asyncio.gather(*tasks) == [1, 2]
        assert [row.seq for row in await event_store.events()] == [1, 2]
    finally:
        event_store.allow_commit.set()
        await _finish_tasks(tasks)


async def test_commit_failure_reaches_every_appender(event_store):
    event_store.fail_commit = True
    service = JobService()
    job_id = uuid4()
    results = await asyncio.gather(
        service.append_event(job_id, "first", {}),
        service.append_event(job_id, "second", {}),
        return_exceptions=True,
    )
    assert all(isinstance(result, RuntimeError) for result in results)
    assert all(str(result) == "injected commit failure" for result in results)
    assert await event_store.events() == []


async def test_distinct_jobs_share_one_transaction(event_store):
    service = JobService()
    job_ids = [uuid4() for _ in range(12)]
    seqs = await asyncio.gather(*(service.append_event(job_id, "event", {}) for job_id in job_ids))
    assert seqs == [1] * len(job_ids)
    assert {row.job_id for row in await event_store.events()} == set(job_ids)
    assert event_store.checkouts == 1


async def test_mixed_jobs_preserve_per_job_order(event_store):
    service = JobService()
    job_a, job_b = uuid4(), uuid4()
    requests = [(job_a, 1), (job_b, 1), (job_a, 2), (job_b, 2)]
    seqs = await asyncio.gather(*(service.append_event(job_id, "event", {"i": i}) for job_id, i in requests))
    assert seqs == [1, 1, 2, 2]
    assert all(row.seq == row.payload["i"] for row in await event_store.events())
    assert event_store.checkouts == 1


async def test_cancelled_window_owner_hands_off_to_waiter(event_store, monkeypatch):
    monkeypatch.setattr(jobs_module, "_APPEND_EVENT_BATCH_WINDOW_S", 0.05)
    service = JobService()
    leader = asyncio.create_task(service.append_event(uuid4(), "cancelled", {}))
    await asyncio.sleep(0)
    follower = asyncio.create_task(service.append_event(uuid4(), "survivor", {}))
    await asyncio.sleep(0)
    try:
        leader.cancel()
        with pytest.raises(asyncio.CancelledError):
            await leader
        assert await asyncio.wait_for(follower, timeout=2) == 1
        assert [row.event_type for row in await event_store.events()] == ["survivor"]
    finally:
        await _finish_tasks([leader, follower])


async def test_cancelled_waiter_is_not_written(event_store, monkeypatch):
    monkeypatch.setattr(jobs_module, "_APPEND_EVENT_BATCH_WINDOW_S", 0.05)
    service = JobService()
    leader = asyncio.create_task(service.append_event(uuid4(), "survivor", {}))
    await asyncio.sleep(0)
    follower = asyncio.create_task(service.append_event(uuid4(), "cancelled", {}))
    await asyncio.sleep(0)
    try:
        follower.cancel()
        with pytest.raises(asyncio.CancelledError):
            await follower
        assert await asyncio.wait_for(leader, timeout=2) == 1
        assert [row.event_type for row in await event_store.events()] == ["survivor"]
    finally:
        await _finish_tasks([leader, follower])


async def test_cancelled_flush_owner_does_not_strand_waiter(event_store):
    event_store.allow_checkout.clear()
    service = JobService()
    leader = asyncio.create_task(service.append_event(uuid4(), "leader", {}))
    await asyncio.sleep(0)
    follower = asyncio.create_task(service.append_event(uuid4(), "survivor", {}))
    try:
        await asyncio.wait_for(event_store.checkout_started.wait(), timeout=2)
        leader.cancel()
        await asyncio.sleep(0)
        event_store.allow_checkout.set()
        assert await asyncio.wait_for(follower, timeout=2) == 1
        with pytest.raises(asyncio.CancelledError):
            await leader
        assert any(row.event_type == "survivor" for row in await event_store.events())
        assert event_store.active_sessions == 0
    finally:
        event_store.allow_checkout.set()
        await _finish_tasks([leader, follower])


async def test_cancelled_callers_join_the_active_flush(event_store):
    event_store.allow_checkout.clear()
    service = JobService()
    tasks = [asyncio.create_task(service.append_event(uuid4(), "event", {})) for _ in range(2)]
    try:
        await asyncio.wait_for(event_store.checkout_started.wait(), timeout=2)
        for task in tasks:
            task.cancel()
        await asyncio.sleep(0)
        # Repeated cancellation must also leave the flush joined to a live caller.
        tasks[0].cancel()
        await asyncio.sleep(0)
        assert not tasks[0].done(), "flush owner exited while its database work was still active"
        event_store.allow_checkout.set()
        results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=2)
        assert all(isinstance(result, asyncio.CancelledError) for result in results)
        assert event_store.active_sessions == 0
    finally:
        event_store.allow_checkout.set()
        await _finish_tasks(tasks)


async def test_appends_arriving_during_commit_are_flushed(event_store):
    event_store.allow_commit.clear()
    service = JobService()
    leader = asyncio.create_task(service.append_event(uuid4(), "first", {}))
    follower = None
    try:
        await asyncio.wait_for(event_store.commit_started.wait(), timeout=2)
        follower = asyncio.create_task(service.append_event(uuid4(), "second", {}))
        await asyncio.sleep(0)
        event_store.allow_commit.set()
        assert await asyncio.wait_for(asyncio.gather(leader, follower), timeout=2) == [1, 1]
        assert {row.event_type for row in await event_store.events()} == {"first", "second"}
    finally:
        event_store.allow_commit.set()
        await _finish_tasks([leader, *([follower] if follower is not None else [])])


async def test_database_cancellation_settles_every_appender(event_store):
    event_store.commit_failures = [asyncio.CancelledError()]
    service = JobService()
    tasks = [asyncio.create_task(service.append_event(uuid4(), "event", {})) for _ in range(2)]
    try:
        results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=2)
        assert all(isinstance(result, asyncio.CancelledError) for result in results)
        assert await event_store.events() == []
        assert event_store.active_sessions == 0
    finally:
        await _finish_tasks(tasks)


@pytest.mark.parametrize("error_type", [IntegrityError, OperationalError])
async def test_commit_contention_retries_without_acknowledging_failed_writes(event_store, error_type):
    event_store.commit_failures = [error_type("INSERT", {}, Exception("database is locked"))]
    service = JobService()
    job_id = uuid4()
    seqs = await asyncio.gather(service.append_event(job_id, "first", {}), service.append_event(job_id, "second", {}))
    assert seqs == [1, 2]
    assert [row.seq for row in await event_store.events()] == [1, 2]
    assert event_store.checkouts == 2


async def test_non_contention_database_error_reaches_every_appender(event_store):
    event_store.commit_failure = OperationalError("INSERT", {}, Exception("connection unavailable"))
    service = JobService()
    results = await asyncio.gather(
        service.append_event(uuid4(), "first", {}),
        service.append_event(uuid4(), "second", {}),
        return_exceptions=True,
    )
    assert all(isinstance(result, OperationalError) for result in results)
    assert await event_store.events() == []


async def test_exhausted_contention_reaches_every_appender(event_store, monkeypatch):
    monkeypatch.setattr(jobs_module, "_APPEND_EVENT_MAX_RETRIES", 2)
    event_store.commit_failure = OperationalError("INSERT", {}, Exception("database is locked"))
    service = JobService()
    results = await asyncio.gather(
        service.append_event(uuid4(), "first", {}),
        service.append_event(uuid4(), "second", {}),
        return_exceptions=True,
    )
    assert all(isinstance(result, RuntimeError) for result in results)
    assert all("exhausted 2 retries" in str(result) for result in results)
    assert await event_store.events() == []


async def test_independent_service_writers_preserve_gap_free_order(event_store):
    services = [JobService() for _ in range(3)]
    job_id = uuid4()
    seqs = await asyncio.gather(
        *(
            service.append_event(job_id, "event", {"writer": writer, "i": i})
            for writer, service in enumerate(services)
            for i in range(12)
        )
    )
    assert sorted(seqs) == list(range(1, 37))
    assert [row.seq for row in await event_store.events()] == list(range(1, 37))


async def test_invalid_event_does_not_fail_another_job(event_store):
    service = JobService()
    bad_job, healthy_job = uuid4(), uuid4()
    results = await asyncio.gather(
        service.append_event(bad_job, "invalid", {"value": object()}),
        service.append_event(healthy_job, "healthy", {"value": "persisted"}),
        return_exceptions=True,
    )
    assert isinstance(results[0], StatementError)
    assert results[1] == 1
    events = await event_store.events()
    assert len(events) == 1
    assert events[0].job_id == healthy_job
    assert events[0].payload == {"value": "persisted"}


async def test_data_error_does_not_fail_another_job(event_store):
    """A DataError (e.g. Postgres rejecting a NUL byte) must isolate like a StatementError.

    Regression test: DataError is also a DBAPIError, so it used to fall through to the
    "poison every job in the batch" branch instead of being split and retried per job.
    """
    bad_payload = {"value": "contains-a-nul-\x00-byte"}
    event_store.fail_payload_marker = bad_payload
    event_store.fail_payload_exception = DataError("INSERT", {}, Exception("unsupported Unicode escape sequence"))
    service = JobService()
    bad_job, healthy_job = uuid4(), uuid4()
    results = await asyncio.gather(
        service.append_event(bad_job, "invalid", bad_payload),
        service.append_event(healthy_job, "healthy", {"value": "persisted"}),
        return_exceptions=True,
    )
    assert isinstance(results[0], DataError)
    assert results[1] == 1
    events = await event_store.events()
    assert len(events) == 1
    assert events[0].job_id == healthy_job
    assert events[0].payload == {"value": "persisted"}
