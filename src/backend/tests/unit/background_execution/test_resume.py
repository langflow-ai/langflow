"""Resume-by-re-enqueue (LE-1446) against a real JobService + facade.

Slice 1 — the service-layer ``resume_job``: validate SUSPENDED, atomic single-flight
flip, write a RESUME signal carrying the human decision, re-enqueue. Staleness and
non-SUSPENDED resumes are rejected before any signal/re-enqueue.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from langflow.api.v2.adapters import StreamAdapterContext, get_stream_adapter
from langflow.services.background_execution.live_bus import InMemoryLiveBus
from langflow.services.background_execution.runner import HUMAN_INPUT_REQUIRED_EVENT, JobRunner
from langflow.services.database.models.jobs.model import JobStatus, SignalType


def _frame(event_type: str, data: dict) -> tuple[bytes, str]:
    return (json.dumps({"event": event_type, "data": data}).encode(), event_type)


def _pause_source(payload: dict):
    async def _source(**_kwargs):
        yield _frame("add_message", {"text": "working…"})
        yield (json.dumps(payload).encode(), HUMAN_INPUT_REQUIRED_EVENT)

    return _source


def _noop_factory(**_kwargs):
    async def _source(**_kw):
        yield _frame("end", {})

    return _source


class _StubUser:
    def __init__(self, user_id):
        self.id = user_id


def _runner(job_service, job_id, source):
    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t"))
    return JobRunner(job_service=job_service, live_bus=InMemoryLiveBus(), adapter=adapter, frame_source=source)


async def _suspend_a_job(job_service, *, request_id="req-1"):
    user_id, flow_id, job_id = uuid4(), uuid4(), uuid4()
    await job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)
    await job_service.update_job_metadata(job_id, {"request": {"flow_id": str(flow_id), "stream_protocol": "langflow"}})
    payload = {"reason": "human_input_required", "request_id": request_id, "options": ["approve", "reject"]}
    await _runner(job_service, job_id, _pause_source(payload)).run(job_id=job_id, source_kwargs={})
    return user_id, job_id


async def _facade():
    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    svc = BackgroundExecutionService(settings_service=get_settings_service(), frame_source_factory=_noop_factory)
    await svc.start()
    return svc


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_resume_job_writes_resume_signal_with_decision(real_services_job_service) -> None:
    job_service = real_services_job_service
    user_id, job_id = await _suspend_a_job(job_service, request_id="req-a")

    svc = await _facade()
    try:
        decision = {"choice": "approve", "note": "looks good"}
        accepted = await svc.resume_job(job_id, _StubUser(user_id), request_id="req-a", decision=decision)
        assert accepted is True
    finally:
        await svc.stop()

    signals = await job_service.unconsumed_signals(job_id)
    resume = [s for s in signals if s.signal_type == SignalType.RESUME]
    assert len(resume) == 1
    assert resume[0].data["decision"] == decision
    assert resume[0].data["request_id"] == "req-a"


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_resume_flips_out_of_suspended(real_services_job_service) -> None:
    job_service = real_services_job_service
    user_id, job_id = await _suspend_a_job(job_service, request_id="req-b")

    svc = await _facade()
    try:
        await svc.resume_job(job_id, _StubUser(user_id), request_id="req-b", decision={"choice": "x"})
    finally:
        await svc.stop()

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status != JobStatus.SUSPENDED


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_second_resume_for_same_request_is_rejected(real_services_job_service) -> None:
    job_service = real_services_job_service
    user_id, job_id = await _suspend_a_job(job_service, request_id="req-c")

    svc = await _facade()
    try:
        first = await svc.resume_job(job_id, _StubUser(user_id), request_id="req-c", decision={"choice": "a"})
        second = await svc.resume_job(job_id, _StubUser(user_id), request_id="req-c", decision={"choice": "b"})
        assert first is True
        assert second is False  # no longer SUSPENDED → rejected
    finally:
        await svc.stop()

    signals = await job_service.unconsumed_signals(job_id)
    assert len([s for s in signals if s.signal_type == SignalType.RESUME]) == 1  # only one RESUME row


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_stale_request_id_is_rejected(real_services_job_service) -> None:
    job_service = real_services_job_service
    user_id, job_id = await _suspend_a_job(job_service, request_id="req-real")

    svc = await _facade()
    try:
        accepted = await svc.resume_job(job_id, _StubUser(user_id), request_id="req-WRONG", decision={"choice": "a"})
        assert accepted is False
    finally:
        await svc.stop()

    signals = await job_service.unconsumed_signals(job_id)
    assert not [s for s in signals if s.signal_type == SignalType.RESUME]  # no signal written for a stale id
    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.SUSPENDED  # untouched


# --------------------------------------------------------------------------- #
# Slice 3 — runner RESUME consume + checkpoint load + injected resume hook.
# --------------------------------------------------------------------------- #


def _durable_store(job_service):
    from langflow.services.checkpoint.store import JobScopedCheckpointStore

    return JobScopedCheckpointStore(job_service)


def _graph_checkpoint(job_id):
    from lfx.graph.checkpoint.schema import GraphCheckpoint

    return GraphCheckpoint(
        run_id=str(job_id),
        job_id=str(job_id),
        flow_id="flow-1",
        session_id="sess-1",
        flow_payload={"nodes": [], "edges": []},
        vertices_to_run={"a"},
    )


def _post_resume_source():
    async def _source(**_kwargs):
        yield _frame("add_message", {"text": "resumed"})
        yield _frame("end", {})

    return _source


def _resume_runner(job_service, job_id, *, resume_hook, store, source=None):
    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t"))
    return JobRunner(
        job_service=job_service,
        live_bus=InMemoryLiveBus(),
        adapter=adapter,
        frame_source=source or _post_resume_source(),
        resume_hook=resume_hook,
        checkpoint_store=store,
    )


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_runner_consumes_resume_and_hands_checkpoint_and_decision_to_hook(real_services_job_service) -> None:
    from langflow.services.database.models.jobs.model import SignalType

    job_service = real_services_job_service
    job_id, flow_id = uuid4(), uuid4()
    await job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=uuid4())
    store = _durable_store(job_service)
    await store.save(_graph_checkpoint(job_id))
    decision = {"choice": "approve"}
    await job_service.write_signal(job_id, SignalType.RESUME, {"decision": decision, "request_id": "req-h"})

    received: list[tuple] = []

    async def hook(checkpoint, decision_arg):
        received.append((checkpoint, decision_arg))

    await _resume_runner(job_service, job_id, resume_hook=hook, store=store).run(job_id=job_id, source_kwargs={})

    assert len(received) == 1
    checkpoint, decision_arg = received[0]
    assert checkpoint is not None
    assert str(checkpoint.job_id) == str(job_id)  # loaded by job_id (run_id carries it)
    assert decision_arg == decision


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_resume_signal_consumed_exactly_once(real_services_job_service) -> None:
    from langflow.services.database.models.jobs.model import SignalType

    job_service = real_services_job_service
    job_id, flow_id = uuid4(), uuid4()
    await job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=uuid4())
    store = _durable_store(job_service)
    await store.save(_graph_checkpoint(job_id))
    await job_service.write_signal(job_id, SignalType.RESUME, {"decision": {"x": 1}, "request_id": "req-once"})

    async def hook(_checkpoint, _decision):
        pass

    await _resume_runner(job_service, job_id, resume_hook=hook, store=store).run(job_id=job_id, source_kwargs={})

    unconsumed = await job_service.unconsumed_signals(job_id)
    assert not [s for s in unconsumed if s.signal_type == SignalType.RESUME]


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_fresh_run_does_not_call_resume_hook(real_services_job_service) -> None:
    job_service = real_services_job_service
    job_id, flow_id = uuid4(), uuid4()
    await job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=uuid4())
    store = _durable_store(job_service)

    called = []

    async def hook(_checkpoint, _decision):
        called.append(1)

    await _resume_runner(job_service, job_id, resume_hook=hook, store=store).run(job_id=job_id, source_kwargs={})

    assert called == []


# --------------------------------------------------------------------------- #
# Slice 4 — same-stream seq continuation + no orphan-sweep double-run.
# --------------------------------------------------------------------------- #


def _resumed_add_message_factory(**_kwargs):
    async def _source(**_kw):
        yield _frame("add_message", {"text": "post-resume"})
        yield _frame("end", {})

    return _source


async def _facade_with(factory):
    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    svc = BackgroundExecutionService(settings_service=get_settings_service(), frame_source_factory=factory)
    await svc.start()
    return svc


async def _wait_for_seq_gt(job_service, job_id, threshold, *, attempts=100):
    import asyncio

    for _ in range(attempts):
        events = await job_service.read_events(job_id, after_seq=0)
        if events and max(e.seq for e in events) > threshold:
            return events
        await asyncio.sleep(0.05)
    return await job_service.read_events(job_id, after_seq=0)


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_resume_continues_same_event_stream(real_services_job_service) -> None:
    """Post-resume frames extend the same (job_id, seq) sequence: strictly greater, no reset."""
    job_service = real_services_job_service
    user_id, job_id = await _suspend_a_job(job_service, request_id="req-seq")
    pre = await job_service.read_events(job_id, after_seq=0)
    pre_max = max(e.seq for e in pre)

    svc = await _facade_with(_resumed_add_message_factory)
    try:
        await svc.resume_job(job_id, _StubUser(user_id), request_id="req-seq", decision={"choice": "go"})
        events = await _wait_for_seq_gt(job_service, job_id, pre_max)
    finally:
        await svc.stop()

    seqs = sorted(e.seq for e in events)
    assert seqs == list(range(1, len(seqs) + 1))  # gap-free, no reset
    assert max(seqs) > pre_max  # post-resume frames strictly extend the stream
    post = [e for e in events if e.seq > pre_max and e.event_type == "add_message"]
    assert post
    assert post[0].payload["data"]["text"] == "post-resume"


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_resume_does_not_leave_a_queued_row_for_the_sweep(real_services_job_service) -> None:
    """Resume flips SUSPENDED->IN_PROGRESS, so the startup QUEUED re-enqueue can't double-run it."""
    job_service = real_services_job_service
    user_id, job_id = await _suspend_a_job(job_service, request_id="req-nosweep")

    svc = await _facade_with(_noop_factory)
    try:
        await svc.resume_job(job_id, _StubUser(user_id), request_id="req-nosweep", decision={"choice": "go"})
        # The sweep only re-enqueues QUEUED workflow rows; a resumed row must not appear there.
        queued_ids = await job_service.queued_workflow_job_ids()
        assert job_id not in queued_ids
    finally:
        await svc.stop()
