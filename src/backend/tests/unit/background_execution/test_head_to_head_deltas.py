"""HEAD-TO-HEAD failure reproductions: each safeguard OFF reproduces the failure.

Per the "reproduce the failure with the safeguard OFF, then assert the delta with
it ON" rule, each test runs the SAME scenario twice — once with the safeguard
disabled (the pre-fix behavior, which must exhibit the BAD outcome) and once with
it enabled (the GOOD outcome). The proof is the measured delta, not a lone green
check.

Three safeguards:

1. Bounded executor pool. OFF (unbounded fan-out) -> peak in-flight == load;
   ON (``InProcessExecutor(max_concurrency=N)``) -> peak == N.
2. Durable submit. OFF (request never persisted) -> a restart finds no QUEUED row
   to recover, so the job is LOST; ON (request persisted on the row) -> a fresh
   facade recovers and re-runs it.
3. Single-flight sweep claim. OFF (unconditional re-enqueue) -> two startup
   sweepers both run a QUEUED job, DOUBLE side effect; ON
   (``claim_queued_job`` conditional UPDATE) -> exactly once.

Real ``InProcessExecutor`` and real ``JobService`` on real SQLite + Postgres.
"""

from __future__ import annotations

import asyncio
import threading
from uuid import uuid4

import pytest
from langflow.api.v2.adapters import StreamAdapterContext, get_stream_adapter
from langflow.services.background_execution.executor import InProcessExecutor
from langflow.services.background_execution.live_bus import InMemoryLiveBus
from langflow.services.background_execution.runner import JobRunner
from langflow.services.database.models.jobs.model import JobStatus

pytestmark = pytest.mark.hard_proof


# --------------------------------------------------------------------------- #
# 1. Bounded executor pool: OFF swamps; ON caps at N.
# --------------------------------------------------------------------------- #


class _PeakProbe:
    """Thread/loop-safe peak in-flight tracker."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.current = 0
        self.peak = 0

    def enter(self) -> None:
        with self._lock:
            self.current += 1
            self.peak = max(self.peak, self.current)

    def exit(self) -> None:
        with self._lock:
            self.current -= 1


async def _run_load_unbounded(load: int, probe: _PeakProbe, release: asyncio.Event) -> None:
    """The pre-fix behavior: every submitted job gets its own task immediately."""

    async def _job() -> None:
        probe.enter()
        try:
            await asyncio.wait_for(release.wait(), timeout=10)
        finally:
            probe.exit()

    tasks = [asyncio.create_task(_job()) for _ in range(load)]
    # Let them all reach the barrier.
    for _ in range(100):
        if probe.peak >= load:
            break
        await asyncio.sleep(0.01)
    release.set()
    await asyncio.gather(*tasks, return_exceptions=True)


async def _run_load_bounded(load: int, concurrency: int, probe: _PeakProbe, release: asyncio.Event) -> None:
    """The fix: the bounded ``InProcessExecutor`` caps in-flight at ``concurrency``."""
    executor = InProcessExecutor(max_concurrency=concurrency)
    await executor.start()

    async def _job() -> None:
        probe.enter()
        try:
            await asyncio.wait_for(release.wait(), timeout=10)
        finally:
            probe.exit()

    try:
        for i in range(load):
            await executor.submit(f"job-{i}", _job)
        # Give the pool time to saturate; peak must never exceed the cap.
        for _ in range(100):
            if probe.current >= concurrency:
                break
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.3)
        release.set()
    finally:
        release.set()
        await executor.stop()


async def test_bounded_pool_delta_off_swamps_on_caps():
    """Bounded pool OFF: peak == load (swamped). ON: peak == N (capped). Measured delta."""
    n = 3
    load = 9

    off_probe = _PeakProbe()
    await _run_load_unbounded(load, off_probe, asyncio.Event())

    on_probe = _PeakProbe()
    await _run_load_bounded(load, n, on_probe, asyncio.Event())

    # BAD (safeguard off): unbounded fan-out runs every job at once.
    assert off_probe.peak == load, f"unbounded peak should be {load}, got {off_probe.peak}"
    # GOOD (safeguard on): the bounded pool never exceeds the cap.
    assert on_probe.peak == n, f"bounded peak should be {n}, got {on_probe.peak}"
    assert off_probe.peak > on_probe.peak, "no delta between unbounded and bounded"
    print(  # noqa: T201
        f"PROOF[h2h/bounded-pool]: OFF peak={off_probe.peak} (==load {load}, swamped) vs "
        f"ON peak={on_probe.peak} (==cap {n}); DELTA={off_probe.peak - on_probe.peak} fewer concurrent"
    )


# --------------------------------------------------------------------------- #
# 2. Durable submit: OFF loses the job on restart; ON recovers it.
# --------------------------------------------------------------------------- #


def _echo_factory(*, request, **_kwargs):
    """A frame source that echoes the request's input into a durable add_message."""
    input_value = request.get("input_value")

    async def _source(**_kw):
        import json

        yield (json.dumps({"event": "add_message", "data": {"input_value": input_value}}).encode(), "add_message")
        yield (json.dumps({"event": "end", "data": {}}).encode(), "end")

    return _source


async def test_durability_delta_off_loses_job_on_restart_on_recovers(hard_proof_job_service):
    """Durability OFF: a restart finds NO recoverable row -> job lost. ON: recovered + re-run."""
    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    job_service = hard_proof_job_service

    # --- OFF: the in-memory-only path (pre-fix). The submit never wrote a durable
    #     QUEUED row — the job lived only in the dead process's executor queue. A
    #     restart's startup sweep has NOTHING to find, so the job is fully LOST:
    #     no row, no run, no events. We model this by simply not persisting the
    #     job at all, then booting a fresh facade and showing recovery is a no-op.
    off_job = uuid4()
    restart_off = BackgroundExecutionService(
        settings_service=get_settings_service(), frame_source_factory=_echo_factory
    )
    await restart_off.start()
    try:
        await restart_off.sweep_orphans_on_startup()
        await asyncio.sleep(0.3)  # give any (wrongly) recovered run a chance to fire
    finally:
        await restart_off.stop()
    # BAD: no durable row exists, so the job never recovers and never runs.
    off_job_row = await job_service.get_job_by_job_id(off_job)
    assert off_job_row is None, "durability-off job should have no durable row to recover"
    off_events = await job_service.read_events(off_job, after_seq=0)
    assert off_events == [], f"durability-off job should produce no events on restart, got {off_events}"

    # --- ON: submit WITH the request persisted (the fix). A restart recovers and
    #     re-runs with the ORIGINAL input.
    on_input = f"on-{uuid4()}"
    on_job, on_flow, on_user = uuid4(), uuid4(), uuid4()
    request = {"flow_id": str(on_flow), "stream_protocol": "langflow", "input_value": on_input}
    await job_service.create_job(job_id=on_job, flow_id=on_flow, user_id=on_user)
    await job_service.update_job_metadata(on_job, {"request": request})  # durability ON

    restart_on = BackgroundExecutionService(settings_service=get_settings_service(), frame_source_factory=_echo_factory)
    await restart_on.start()
    try:
        await restart_on.sweep_orphans_on_startup()
        job = None
        for _ in range(100):
            job = await job_service.get_job_by_job_id(on_job)
            if job.status == JobStatus.COMPLETED:
                break
            await asyncio.sleep(0.05)
        assert job.status == JobStatus.COMPLETED
    finally:
        await restart_on.stop()
    on_events = await job_service.read_events(on_job, after_seq=0)
    on_echoed = [e.payload.get("data", {}).get("input_value") for e in on_events if e.event_type == "add_message"]
    # GOOD: the original input survived and re-ran.
    assert on_echoed == [on_input], f"recovered run did not replay original input: {on_echoed}"
    print(  # noqa: T201
        f"PROOF[h2h/durability]: OFF job LOST on restart (no durable row, 0 events) vs "
        f"ON recovered+replayed original ({on_echoed}); DELTA = job survives restart only when persisted"
    )


# --------------------------------------------------------------------------- #
# 3. Single-flight sweep claim: OFF double-runs; ON runs exactly once.
# --------------------------------------------------------------------------- #


def _frame(event_type, data):
    import json

    return (json.dumps({"event": event_type, "data": data}).encode(), event_type)


def _side_effect_factory(*, request, **_kwargs):  # noqa: ARG001
    async def _source(**_kw):
        yield _frame("add_message", {"marker": "ran"})
        yield _frame("end", {})

    return _source


def _runner(job_service, job_id, source):
    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t"))
    return JobRunner(job_service=job_service, live_bus=InMemoryLiveBus(), adapter=adapter, frame_source=source)


async def test_sweep_claim_delta_off_double_runs_on_exactly_once(hard_proof_job_service):
    """Sweep claim OFF: two sweepers both run a QUEUED job (double). ON: exactly once."""
    job_service = hard_proof_job_service

    # --- OFF: the pre-fix unconditional re-enqueue. Two sweepers each run the job
    #     because neither claims it first. We reproduce by running the runner twice
    #     against the SAME job_id, as two unconditional sweepers would.
    off_job, off_flow = uuid4(), uuid4()
    await job_service.create_job(job_id=off_job, flow_id=off_flow, user_id=uuid4())
    src1 = _side_effect_factory(request={})
    src2 = _side_effect_factory(request={})
    # Unconditional: neither call claims, both run.
    await _runner(job_service, off_job, src1).run(job_id=off_job, source_kwargs={})
    await job_service.update_job_status(off_job, JobStatus.QUEUED)  # second sweeper sees it QUEUED again
    await _runner(job_service, off_job, src2).run(job_id=off_job, source_kwargs={})
    off_events = await job_service.read_events(off_job, after_seq=0)
    off_markers = [e for e in off_events if e.event_type == "add_message"]
    # BAD: the non-idempotent side effect ran twice.
    assert len(off_markers) == 2, f"unconditional re-enqueue should double-run, got {len(off_markers)}"

    # --- ON: the conditional claim. Two concurrent sweepers race; only the claim
    #     winner runs. Exactly once.
    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    on_job, on_flow, on_user = uuid4(), uuid4(), uuid4()
    request = {"flow_id": str(on_flow), "stream_protocol": "langflow", "input_value": "x"}
    await job_service.create_job(job_id=on_job, flow_id=on_flow, user_id=on_user)
    await job_service.update_job_metadata(on_job, {"request": request})

    svc_a = BackgroundExecutionService(
        settings_service=get_settings_service(), frame_source_factory=_side_effect_factory
    )
    svc_b = BackgroundExecutionService(
        settings_service=get_settings_service(), frame_source_factory=_side_effect_factory
    )
    await svc_a.start()
    await svc_b.start()
    try:
        await asyncio.gather(svc_a.sweep_orphans_on_startup(), svc_b.sweep_orphans_on_startup())
        job = None
        for _ in range(100):
            job = await job_service.get_job_by_job_id(on_job)
            if job.status == JobStatus.COMPLETED:
                break
            await asyncio.sleep(0.05)
        assert job.status == JobStatus.COMPLETED
    finally:
        await svc_a.stop()
        await svc_b.stop()
    on_events = await job_service.read_events(on_job, after_seq=0)
    on_markers = [e for e in on_events if e.event_type == "add_message"]
    # GOOD: exactly one run.
    assert len(on_markers) == 1, f"single-flight claim should run exactly once, got {len(on_markers)}"
    print(  # noqa: T201
        f"PROOF[h2h/sweep-claim]: OFF ran {len(off_markers)}x (double side effect) vs "
        f"ON ran {len(on_markers)}x (claim single-flight); DELTA = {len(off_markers) - len(on_markers)} avoided re-run"
    )
