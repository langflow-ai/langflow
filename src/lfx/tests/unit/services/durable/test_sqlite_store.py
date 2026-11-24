"""SqliteDurableJobStore — the single-node durable substrate for lfx serve (LE-1695).

Real-integration tests: every test runs against a real SQLite file in tmp_path (no
mocks), because durability across process boundaries is the point — a fresh store
instance opened on the same file must see everything a previous instance wrote.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from lfx.services.durable.models import JobStatus, JobType, SignalType
from lfx.services.durable.sqlite_store import SqliteDurableJobStore


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "durable jobs — teste.db"


@pytest.fixture
def store(db_path):
    return SqliteDurableJobStore(db_path)


def _ids():
    return str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())


class TestJobLifecycle:
    async def test_should_persist_and_return_a_created_job(self, store):
        job_id, flow_id, user_id = _ids()

        await store.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)
        job = await store.get_job(job_id)

        assert job is not None
        assert job.job_id == job_id
        assert job.flow_id == flow_id
        assert job.user_id == user_id
        assert job.status == JobStatus.QUEUED
        assert job.job_type == JobType.WORKFLOW

    async def test_should_survive_a_process_restart(self, store, db_path):
        job_id, flow_id, user_id = _ids()
        await store.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)

        reopened = SqliteDurableJobStore(db_path)
        job = await reopened.get_job(job_id)

        assert job is not None
        assert job.status == JobStatus.QUEUED

    async def test_should_return_none_for_unknown_job(self, store):
        assert await store.get_job(str(uuid.uuid4())) is None

    async def test_should_reject_duplicate_job_id(self, store):
        job_id, flow_id, user_id = _ids()
        await store.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)

        with pytest.raises(ValueError, match="already exists"):
            await store.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)


class TestJobStateTransitions:
    async def test_should_update_status(self, store):
        job_id, flow_id, user_id = _ids()
        await store.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)

        await store.update_status(job_id, JobStatus.SUSPENDED)

        assert (await store.get_job(job_id)).status == JobStatus.SUSPENDED

    async def test_should_store_result_and_mark_completed(self, store):
        job_id, flow_id, user_id = _ids()
        await store.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)

        await store.set_result(job_id, {"outputs": [1, 2]})
        job = await store.get_job(job_id)

        assert job.status == JobStatus.COMPLETED
        assert job.result == {"outputs": [1, 2]}

    async def test_should_store_error_and_mark_failed(self, store):
        job_id, flow_id, user_id = _ids()
        await store.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)

        await store.set_error(job_id, {"type": "boom", "detail": "x"})
        job = await store.get_job(job_id)

        assert job.status == JobStatus.FAILED
        assert job.error == {"type": "boom", "detail": "x"}

    async def test_should_merge_metadata_not_replace_it(self, store):
        job_id, flow_id, user_id = _ids()
        await store.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)

        await store.update_metadata(job_id, {"request": {"session_id": "s1"}})
        await store.update_metadata(job_id, {"card_message_id": "m1"})
        job = await store.get_job(job_id)

        assert job.job_metadata == {"request": {"session_id": "s1"}, "card_message_id": "m1"}

    async def test_should_round_trip_hostile_metadata_strings(self, store):
        # Parameterized queries only: quotes / SQL fragments must survive verbatim.
        job_id, flow_id, user_id = _ids()
        await store.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)
        hostile = {"note": "Robert'); DROP TABLE jobs;--", "emoji": "aprovação ✅"}

        await store.update_metadata(job_id, hostile)

        assert (await store.get_job(job_id)).job_metadata == hostile
        assert await store.get_job(job_id) is not None


class TestEventLog:
    async def test_should_append_with_monotonic_per_job_seq(self, store):
        job_id, flow_id, user_id = _ids()
        await store.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)

        first = await store.append_event(job_id, "add_message", {"text": "a"})
        second = await store.append_event(job_id, "add_message", {"text": "b"})

        assert (first, second) == (1, 2)

    async def test_should_scope_seq_per_job(self, store):
        a, flow_id, user_id = _ids()
        b = str(uuid.uuid4())
        await store.create_job(job_id=a, flow_id=flow_id, user_id=user_id)
        await store.create_job(job_id=b, flow_id=flow_id, user_id=user_id)

        await store.append_event(a, "e", {})
        seq_b = await store.append_event(b, "e", {})

        assert seq_b == 1

    async def test_should_read_events_after_seq_in_order(self, store):
        job_id, flow_id, user_id = _ids()
        await store.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)
        for i in range(5):
            await store.append_event(job_id, "e", {"i": i})

        events = await store.read_events(job_id, after_seq=2)

        assert [e.seq for e in events] == [3, 4, 5]
        assert [e.payload["i"] for e in events] == [2, 3, 4]

    async def test_should_keep_seq_gap_free_under_concurrent_appends(self, store):
        job_id, flow_id, user_id = _ids()
        await store.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)

        seqs = await asyncio.gather(*(store.append_event(job_id, "e", {"i": i}) for i in range(25)))

        assert sorted(seqs) == list(range(1, 26))


class TestSignals:
    async def test_should_deliver_written_signal_once(self, store):
        job_id, flow_id, user_id = _ids()
        await store.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)

        await store.write_signal(job_id, SignalType.RESUME, {"decision": {"action_id": "approve"}})
        pending = await store.unconsumed_signals(job_id)
        assert len(pending) == 1
        assert pending[0].signal_type == SignalType.RESUME
        assert pending[0].data == {"decision": {"action_id": "approve"}}

        consumed = await store.consume_signals(job_id, SignalType.RESUME)

        assert consumed == 1
        assert await store.unconsumed_signals(job_id) == []


class TestSingleFlightClaims:
    async def test_should_grant_suspended_resume_claim_to_exactly_one_caller(self, store):
        job_id, flow_id, user_id = _ids()
        await store.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)
        await store.update_status(job_id, JobStatus.SUSPENDED)

        wins = await asyncio.gather(*(store.claim_suspended_for_resume(job_id) for _ in range(8)))

        assert wins.count(True) == 1
        assert (await store.get_job(job_id)).status == JobStatus.IN_PROGRESS

    async def test_should_reject_resume_claim_when_not_suspended(self, store):
        job_id, flow_id, user_id = _ids()
        await store.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)

        assert await store.claim_suspended_for_resume(job_id) is False

    async def test_should_list_queued_workflow_job_ids(self, store):
        queued, flow_id, user_id = _ids()
        running = str(uuid.uuid4())
        await store.create_job(job_id=queued, flow_id=flow_id, user_id=user_id)
        await store.create_job(job_id=running, flow_id=flow_id, user_id=user_id)
        await store.update_status(running, JobStatus.IN_PROGRESS)

        assert await store.queued_workflow_job_ids() == [queued]
