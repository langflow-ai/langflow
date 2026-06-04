"""Hard-proof the durable background path on real SQLite AND real Postgres.

The Runner + InMemoryLiveBus + facade durable replay all sit on ``JobService``,
whose ``session_scope()`` the ``hard_proof_job_service`` fixture binds to a real,
migrated DB parametrized over sqlite and postgres. These tests drive the real
Runner with a scripted frame source (legitimate test input, not a mock of our
logic) and assert durable persistence, ordering, terminal state, reattach replay,
and the orphan sweep on BOTH engines.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from langflow.api.v2.adapters import StreamAdapterContext, get_stream_adapter
from langflow.services.background_execution.live_bus import InMemoryLiveBus, LiveFrame
from langflow.services.background_execution.runner import JobRunner
from langflow.services.database.models.jobs.model import JobStatus, SignalType

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.hard_proof


def _frame(event_type: str, data: dict) -> tuple[bytes, str]:
    return (json.dumps({"event": event_type, "data": data}).encode("utf-8"), event_type)


def _runner(job_service, bus, job_id, source) -> JobRunner:
    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t"))
    return JobRunner(job_service=job_service, live_bus=bus, adapter=adapter, frame_source=source)


async def test_durable_persistence_and_terminal_state(hard_proof_job_service):
    job_service = hard_proof_job_service
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())

    async def source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
        yield _frame("build_start", {})
        yield _frame("token", {"chunk": "x"})  # ephemeral
        yield _frame("end_vertex", {"id": "n1"})
        yield _frame("end", {})

    bus = InMemoryLiveBus()
    await _runner(job_service, bus, job_id, source).run(job_id=job_id, source_kwargs={})

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.COMPLETED
    assert job.result is not None

    events = await job_service.read_events(job_id, after_seq=0)
    types = [e.event_type for e in events]
    assert "token" not in types  # ephemeral not persisted
    assert types == ["build_start", "end_vertex", "end"]
    assert [e.seq for e in events] == [1, 2, 3]  # contiguous, monotonic


async def test_reattach_replays_durable_after_completion(hard_proof_job_service):
    job_service = hard_proof_job_service
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())

    async def source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
        yield _frame("build_start", {})
        yield _frame("end_vertex", {"id": "n1"})
        yield _frame("end", {})

    bus = InMemoryLiveBus()
    await _runner(job_service, bus, job_id, source).run(job_id=job_id, source_kwargs={})

    # Reattach from 0 after completion: durable rows replay in order, no gap.
    async def read_durable(after_seq: int) -> list[LiveFrame]:
        rows = await job_service.read_events(job_id, after_seq=after_seq)
        return [LiveFrame(seq=r.seq, data=json.dumps(r.payload).encode("utf-8")) for r in rows]

    seqs = []
    bodies = b""
    async for frame in bus.reattach(str(job_id), last_seq=0, read_durable=read_durable):
        seqs.append(frame.seq)
        bodies += frame.data
    assert seqs == [1, 2, 3]
    assert b"build_start" in bodies
    assert b"end_vertex" in bodies


async def test_reattach_from_midpoint_has_no_gap(hard_proof_job_service):
    job_service = hard_proof_job_service
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())

    async def source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
        yield _frame("build_start", {})
        yield _frame("end_vertex", {"id": "n1"})
        yield _frame("end", {})

    bus = InMemoryLiveBus()
    await _runner(job_service, bus, job_id, source).run(job_id=job_id, source_kwargs={})

    async def read_durable(after_seq: int) -> list[LiveFrame]:
        rows = await job_service.read_events(job_id, after_seq=after_seq)
        return [LiveFrame(seq=r.seq, data=json.dumps(r.payload).encode("utf-8")) for r in rows]

    # Reattach from last_seq=1: must replay only seq 2,3 (no gap, no overlap).
    seqs = [frame.seq async for frame in bus.reattach(str(job_id), last_seq=1, read_durable=read_durable)]
    assert seqs == [2, 3]


async def test_stop_signal_cancels_run(hard_proof_job_service):
    job_service = hard_proof_job_service
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())
    # A STOP written before the run makes the first boundary poll cancel it.
    await job_service.write_signal(job_id, SignalType.STOP)

    async def source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
        yield _frame("build_start", {})
        yield _frame("end", {})

    bus = InMemoryLiveBus()
    await _runner(job_service, bus, job_id, source).run(job_id=job_id, source_kwargs={})

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.CANCELLED


async def test_sweep_orphans_fails_in_progress(hard_proof_job_service):
    job_service = hard_proof_job_service
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())
    await job_service.update_job_status(job_id, JobStatus.IN_PROGRESS)

    failed = await job_service.sweep_orphans()
    assert job_id in failed
    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.FAILED
    assert job.error is not None
    assert job.error.get("type") == "worker_lost"


def _echo_input_factory(*, request, **_kwargs):
    """Frame source that echoes ``request['input_value']`` into a durable event.

    Proves the re-enqueued QUEUED job replays its ORIGINAL inputs: the input it
    actually runs with shows up in the durable ``job_events`` log, so a restart
    that lost the in-memory request body would surface a different (defaulted)
    value here.
    """
    input_value = request.get("input_value")

    async def _source(**_kw):
        # ``add_message`` is a durable langflow event, so it lands in job_events
        # and survives for the post-run assertion.
        yield _frame("add_message", {"input_value": input_value})
        yield _frame("end", {})

    return _source


async def test_submit_persists_request_for_faithful_requeue(hard_proof_job_service):
    """``submit`` persists the request body on the job row (job_metadata.request).

    This is the durable record the startup sweep reads to replay original inputs.
    Proven on both real SQLite and real Postgres. The executor is stopped right
    after submit so no run interferes with reading the persisted row.
    """
    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    job_service = hard_proof_job_service
    original_input = f"original-input-{uuid4()}"
    flow_id = uuid4()

    svc = BackgroundExecutionService(
        settings_service=get_settings_service(),
        frame_source_factory=_echo_input_factory,
    )
    request = {
        "flow_id": str(flow_id),
        "mode": "background",
        "stream_protocol": "langflow",
        "input_value": original_input,
        "session_id": "thread-restart",
        "tweaks": {"ChatInput-x": {"foo": "bar"}},
    }
    job_id = await svc.submit(flow_id=flow_id, request=request, user=_StubUser(uuid4()))
    await svc.stop()

    job = await job_service.get_job_by_job_id(job_id)
    assert job.job_metadata is not None
    persisted = job.job_metadata.get("request")
    # The whole request round-trips, not just input_value.
    assert persisted == request


async def test_requeued_queued_job_replays_original_input(hard_proof_job_service):
    """A QUEUED job that survives a restart re-runs with its ORIGINAL input.

    Models "queued, never started, then the process died": the durable row is
    QUEUED with the request persisted exactly as ``submit`` writes it (create_job
    + update_job_metadata(request)). A *fresh* facade (empty in-memory state, as
    after a restart) sweeps and re-enqueues, and the run replays the ORIGINAL
    ``input_value`` — visible in the durable ``job_events`` log. On both real
    SQLite and real Postgres.
    """
    import asyncio

    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    job_service = hard_proof_job_service
    original_input = f"original-input-{uuid4()}"
    user_id = uuid4()
    flow_id = uuid4()
    job_id = uuid4()
    request = {
        "flow_id": str(flow_id),
        "mode": "background",
        "stream_protocol": "langflow",
        "input_value": original_input,
        "session_id": "thread-restart",
    }
    # Durable state a restart finds: a QUEUED row carrying the persisted request,
    # written exactly the way ``submit`` writes it.
    await job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)
    await job_service.update_job_metadata(job_id, {"request": request})

    # Restart: a brand-new facade with empty in-memory state sweeps + re-enqueues.
    restart_svc = BackgroundExecutionService(
        settings_service=get_settings_service(),
        frame_source_factory=_echo_input_factory,
    )
    await restart_svc.start()
    try:
        await restart_svc.sweep_orphans_on_startup()
        job = None
        for _ in range(100):
            job = await job_service.get_job_by_job_id(job_id)
            if job.status == JobStatus.COMPLETED:
                break
            await asyncio.sleep(0.05)
        assert job.status == JobStatus.COMPLETED
    finally:
        await restart_svc.stop()

    # The re-enqueued run replayed the ORIGINAL input, not a default.
    events = await job_service.read_events(job_id, after_seq=0)
    echoed = [e.payload.get("data", {}).get("input_value") for e in events if e.event_type == "add_message"]
    assert echoed == [original_input]


class _StubUser:
    """Minimal user carrying only ``id`` (all the facade submit path reads)."""

    def __init__(self, user_id):
        self.id = user_id
