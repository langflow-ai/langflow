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


async def test_submit_redacts_inline_globals_from_persisted_request(hard_proof_job_service):
    """Inline ``globals`` (request-level secrets) must NOT land plaintext on the row.

    ``submit`` persists the request body for faithful replay, but request-level
    ``globals`` can carry inline secrets (API keys). Storing them plaintext in the
    durable ``job`` table widens the blast radius of any DB read (backup, ops
    access, SQL-injection elsewhere). The persisted replay request must omit
    ``globals``; the live in-memory run still has them. Tradeoff: a background
    re-enqueue after a restart drops inline globals — reference stored global
    variables by name for background runs instead of passing secrets inline.
    Real SQLite and Postgres.
    """
    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    job_service = hard_proof_job_service
    flow_id = uuid4()
    secret = f"sk-secret-{uuid4()}"

    svc = BackgroundExecutionService(
        settings_service=get_settings_service(),
        frame_source_factory=_echo_input_factory,
    )
    request = {
        "flow_id": str(flow_id),
        "mode": "background",
        "stream_protocol": "langflow",
        "input_value": "hi",
        "globals": {"OPENAI_API_KEY": secret},
    }
    job_id = await svc.submit(flow_id=flow_id, request=request, user=_StubUser(uuid4()))
    await svc.stop()

    job = await job_service.get_job_by_job_id(job_id)
    persisted = job.job_metadata.get("request") or {}
    # The secret must not appear anywhere in the persisted request blob.
    assert "globals" not in persisted, "inline globals persisted plaintext on the job row"
    assert secret not in json.dumps(job.job_metadata), "inline secret leaked into job_metadata"
    # The caller's original request dict is not mutated as a side effect.
    assert request["globals"] == {"OPENAI_API_KEY": secret}


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


async def test_job_timeout_marks_timed_out(hard_proof_job_service):
    """A run that overruns ``background_job_timeout`` ends TIMED_OUT.

    The runner wraps the drive in ``asyncio.wait_for(timeout=...)``;
    ``execute_with_status`` maps ``asyncio.TimeoutError`` to TIMED_OUT. We use a
    scripted source that sleeps far longer than the short configured timeout, so
    the timeout fires deterministically without any LLM call. The durable log
    must carry a terminal milestone too. Real SQLite and real Postgres.
    """
    import asyncio

    job_service = hard_proof_job_service
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())

    async def slow_source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
        yield _frame("build_start", {})
        # Overrun the configured timeout by a wide margin.
        await asyncio.sleep(30)
        yield _frame("end", {})

    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t"))
    runner = JobRunner(
        job_service=job_service,
        live_bus=InMemoryLiveBus(),
        adapter=adapter,
        frame_source=slow_source,
        job_timeout=0.2,
    )
    await runner.run(job_id=job_id, source_kwargs={})

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.TIMED_OUT


async def test_events_reattach_after_restart_returns_on_terminal_job(hard_proof_job_service):
    """Reattaching to an already-terminal job after a restart MUST NOT hang.

    Models a process restart: a job runs to COMPLETED, persisting durable
    milestones, then the process dies. A brand-new facade (fresh in-memory live
    bus, empty ``_closed`` markers) is created bound to the SAME DB and a client
    reattaches via ``events()``. The facade must consult the DURABLE job status,
    see it is terminal, replay the durable milestones, and RETURN — not block on
    ``while True: queue.get()`` waiting for a live tail that will never come.

    The ``asyncio.wait_for`` guard turns the hang into a test failure rather than
    a hung suite. Proven on real SQLite and real Postgres.
    """
    import asyncio

    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    job_service = hard_proof_job_service
    user_id = uuid4()
    flow_id = uuid4()
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)

    async def source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
        yield _frame("build_start", {})
        yield _frame("end_vertex", {"id": "n1"})
        yield _frame("end", {})

    # Run to terminal on a first bus (the "pre-restart" process).
    bus = InMemoryLiveBus()
    await _runner(job_service, bus, job_id, source).run(job_id=job_id, source_kwargs={})
    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.COMPLETED

    # Restart: a fresh facade with an empty in-memory bus, bound to the same DB.
    restart_svc = BackgroundExecutionService(settings_service=get_settings_service())
    user = _StubUser(user_id)

    async def _collect() -> list[bytes]:
        return [frame async for frame in restart_svc.events(job_id, None, user)]

    # A hang here (the bug) is caught by wait_for instead of stalling the suite.
    frames = await asyncio.wait_for(_collect(), timeout=5.0)

    body = b"".join(frames)
    assert b"build_start" in body
    assert b"end_vertex" in body
    assert b"end" in body


async def test_events_replay_frames_are_sse_framed(hard_proof_job_service):
    """Durable replay must emit SSE-framed bytes byte-compatible with live frames.

    Live frames are pre-SSE-framed with a ``data:`` line followed by an ``id:``
    line. A reattach to a terminal job replays durable rows; those replayed bytes
    must be the SAME wire shape so a client's ``Last-Event-ID`` resume works and
    the frames are not a different (bare-JSON) format. We assert each replayed
    frame starts with ``data:`` and carries ``id: <seq>``. Real SQLite and real
    Postgres.
    """
    import asyncio

    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    job_service = hard_proof_job_service
    user_id = uuid4()
    flow_id = uuid4()
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)

    async def source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
        yield _frame("build_start", {})
        yield _frame("end_vertex", {"id": "n1"})
        yield _frame("end", {})

    bus = InMemoryLiveBus()
    await _runner(job_service, bus, job_id, source).run(job_id=job_id, source_kwargs={})

    svc = BackgroundExecutionService(settings_service=get_settings_service())
    user = _StubUser(user_id)

    async def _collect() -> list[bytes]:
        return [frame async for frame in svc.events(job_id, None, user)]

    frames = await asyncio.wait_for(_collect(), timeout=5.0)
    assert len(frames) == 3
    for seq, frame in enumerate(frames, start=1):
        assert frame.startswith(b"data:"), f"replayed frame not SSE-framed: {frame!r}"
        assert f"id: {seq}".encode() in frame, f"replayed frame missing id: {frame!r}"


async def test_executor_stop_applies_terminal_reconcile(hard_proof_job_service):
    """``executor.stop()`` lets an in-flight stopped job's reconcile land.

    Drives the REAL runner on the executor. The job blocks mid-run; a STOP signal
    is written, then ``executor.stop()`` tears the pool down. stop() cancels and
    gathers the in-flight task so the runner's shielded terminal reconcile applies
    BEFORE it returns, and the durable row reads CANCELLED. The job swallows its
    cancellation (user-stop path): stop() cancels the job task directly and
    gathers it rather than waiting on the worker's absorbed-cancel ``await``,
    which leaves the worker in cancellation limbo and stalls teardown. The
    ``wait_for`` budget plus pytest-timeout turn that stall into a failure. Real
    SQLite and Postgres.
    """
    import asyncio

    from langflow.services.background_execution.executor import InProcessExecutor

    job_service = hard_proof_job_service
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())

    started = asyncio.Event()
    release = asyncio.Event()

    async def blocking_source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
        yield _frame("build_start", {})
        started.set()
        await release.wait()  # block until cancelled
        yield _frame("end", {})  # unreachable

    bus = InMemoryLiveBus()
    runner = _runner(job_service, bus, job_id, blocking_source)
    executor = InProcessExecutor(max_concurrency=1)
    await executor.start()

    async def _coro() -> None:
        await runner.run(job_id=job_id, source_kwargs={})

    await executor.submit(str(job_id), _coro)
    await asyncio.wait_for(started.wait(), timeout=5.0)

    await job_service.write_signal(job_id, SignalType.STOP)
    # The fixed stop() (cancel+gather job tasks first) returns in well under a
    # second. The original ordering (await workers first) leaves the worker in
    # cancellation limbo behind the job's swallowed cancel and only unblocks once
    # the reconcile's DB writes drain through lock backoff (many seconds), so a
    # tight budget here reliably distinguishes the two.
    await asyncio.wait_for(executor.stop(), timeout=5.0)

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.CANCELLED


async def test_stop_poll_only_on_durable_frames(hard_proof_job_service):
    """The runner polls the STOP signal only on DURABLE frames, not every token.

    Polling ``unconsumed_signals`` (a DB read) on every ephemeral token is wasted
    work — a stop is only honored at vertex/milestone boundaries anyway. We count
    real ``unconsumed_signals`` DB calls (a thin instrumented subclass that still
    hits the real DB) while driving a source with many ephemeral tokens and a few
    durable frames, and assert the poll count tracks the durable frames, not the
    token flood. Real SQLite and Postgres.
    """
    job_service = hard_proof_job_service
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())

    class _CountingJobService(type(job_service)):
        poll_count = 0

        async def unconsumed_signals(self, jid):
            type(self).poll_count += 1
            return await super().unconsumed_signals(jid)

    counting = _CountingJobService()

    n_tokens = 20
    n_durable = 3  # build_start, end_vertex, end

    async def source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
        yield _frame("build_start", {})
        for i in range(n_tokens):
            yield _frame("token", {"chunk": str(i)})  # ephemeral
        yield _frame("end_vertex", {"id": "n1"})
        yield _frame("end", {})

    bus = InMemoryLiveBus()
    await _runner(counting, bus, job_id, source).run(job_id=job_id, source_kwargs={})

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.COMPLETED
    # Polls must not scale with the token flood. Allow the durable-frame polls
    # plus the runner's final post-loop / reconcile checks, but never one-per-token.
    assert _CountingJobService.poll_count <= n_durable + 3, (
        f"stop polled {_CountingJobService.poll_count} times for {n_tokens} tokens (per-token poll)"
    )


async def test_stop_signal_is_marked_consumed(hard_proof_job_service):
    """When the runner acts on a STOP, the signal row is stamped ``consumed_at``.

    Otherwise the execution_signals table grows unbounded and, worse, a
    re-enqueued job self-cancels off the stale STOP. We assert two things:
    (1) after a stopped run the STOP row has ``consumed_at`` set, and
    (2) a fresh run of the SAME job_id afterwards does NOT instantly cancel —
    it completes, because the stale STOP was consumed. Real SQLite and Postgres.
    """
    job_service = hard_proof_job_service
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())
    await job_service.write_signal(job_id, SignalType.STOP)

    async def source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
        yield _frame("build_start", {})
        yield _frame("end", {})

    bus = InMemoryLiveBus()
    await _runner(job_service, bus, job_id, source).run(job_id=job_id, source_kwargs={})

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.CANCELLED

    # The STOP signal must now be consumed (no unconsumed rows remain).
    remaining = await job_service.unconsumed_signals(job_id)
    assert remaining == [], "STOP signal was not stamped consumed_at"

    # Re-enqueue path: bring the row back to QUEUED and re-run. A stale STOP would
    # instantly cancel it; since it was consumed, the fresh run completes.
    await job_service.update_job_status(job_id, JobStatus.QUEUED)

    async def source2(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
        yield _frame("build_start", {})
        yield _frame("end", {})

    bus2 = InMemoryLiveBus()
    await _runner(job_service, bus2, job_id, source2).run(job_id=job_id, source_kwargs={})

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.COMPLETED, "re-run self-cancelled off a stale STOP"


def _side_effect_factory(*, request, **_kwargs):  # noqa: ARG001
    """Frame source that emits exactly one durable ``add_message`` side effect.

    Counting the durable ``add_message`` rows for the job is an exactly-once
    probe: if two sweepers both re-enqueue the same QUEUED job, the run fires
    twice and two rows land; a single-flight claim leaves exactly one.
    """

    async def _source(**_kw):
        yield _frame("add_message", {"marker": "ran"})
        yield _frame("end", {})

    return _source


async def test_concurrent_sweep_runs_queued_job_exactly_once(hard_proof_job_service):
    """Two startup sweepers sharing one DB must run a QUEUED job EXACTLY once.

    Models two uvicorn workers booting against the same database, each calling
    ``sweep_orphans_on_startup`` concurrently on the same QUEUED row. Without a
    single-flight claim both re-enqueue the row and the non-idempotent flow runs
    twice (two durable side-effect rows). The per-row conditional claim
    (UPDATE ... WHERE status='QUEUED') lets exactly one sweeper win, so the side
    effect happens exactly once. Real SQLite and real Postgres.
    """
    import asyncio

    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    job_service = hard_proof_job_service
    user_id = uuid4()
    flow_id = uuid4()
    job_id = uuid4()
    request = {
        "flow_id": str(flow_id),
        "mode": "background",
        "stream_protocol": "langflow",
        "input_value": "x",
        "session_id": "thread-restart",
    }
    await job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)
    await job_service.update_job_metadata(job_id, {"request": request})

    svc_a = BackgroundExecutionService(
        settings_service=get_settings_service(), frame_source_factory=_side_effect_factory
    )
    svc_b = BackgroundExecutionService(
        settings_service=get_settings_service(), frame_source_factory=_side_effect_factory
    )
    await svc_a.start()
    await svc_b.start()
    try:
        # Both sweep at once: only one may claim and run the QUEUED row.
        await asyncio.gather(svc_a.sweep_orphans_on_startup(), svc_b.sweep_orphans_on_startup())

        job = None
        for _ in range(100):
            job = await job_service.get_job_by_job_id(job_id)
            if job.status == JobStatus.COMPLETED:
                break
            await asyncio.sleep(0.05)
        assert job.status == JobStatus.COMPLETED
    finally:
        await svc_a.stop()
        await svc_b.stop()

    events = await job_service.read_events(job_id, after_seq=0)
    markers = [e for e in events if e.event_type == "add_message"]
    assert len(markers) == 1, f"QUEUED job ran {len(markers)} times, expected exactly 1"


class _StubUser:
    """Minimal user carrying only ``id`` (all the facade submit path reads)."""

    def __init__(self, user_id):
        self.id = user_id
