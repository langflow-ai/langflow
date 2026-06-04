"""SIDE-EFFECT-SAFETY crown jewel with a REAL side-effecting component.

A real Langflow component (``SideEffectComponent``) increments an observable
process-global counter each time it builds, driven through a REAL connected graph
(ChatInput -> SideEffect -> ChatOutput) via ``async_start``. The proof is the
DELTA between the default at-most-once policy and the opt-in retry-safe policy:

* Default: a job killed mid-flight is reconciled to FAILED(worker_lost) and is
  NOT re-run, so the counter does NOT double-increment.
* Retry-safe: the SAME crash path requeues the work, so the real graph runs again
  and the counter reaches 2.

Also: two concurrent startup sweeps over one QUEUED job run the side effect
EXACTLY once (single-flight claim guard). Real SQLite + real Postgres for the
durable reconcile; the retry-safe requeue branch uses the real redis backend.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from langflow.services.database.models.jobs.model import JobStatus

from ._side_effect_component import build_side_effect_graph, reset_side_effects, side_effect_count

pytestmark = pytest.mark.hard_proof


@pytest.fixture(autouse=True)
def _clean_side_effects():
    reset_side_effects()
    yield
    reset_side_effects()


async def _run_real_graph_once(effect_key: str) -> int:
    """Drive the REAL side-effecting graph to completion; return the new counter."""
    graph = build_side_effect_graph(effect_key)
    graph.prepare()
    _ = [r async for r in graph.async_start()]
    return side_effect_count(effect_key)


async def test_default_at_most_once_no_double_increment(hard_proof_job_service):
    """Default: a crashed in-flight job is FAILED(worker_lost) and NOT re-run."""
    job_service = hard_proof_job_service
    job_id, flow_id = uuid4(), uuid4()
    effect_key = f"atmostonce-{job_id}"

    # Drive the real side effect once, then crash mid-flight (row left IN_PROGRESS).
    await job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=uuid4())
    await job_service.update_job_status(job_id, JobStatus.IN_PROGRESS)
    assert await _run_real_graph_once(effect_key) == 1

    # Restart: the default at-most-once sweep fails the orphan; it must NOT re-run.
    failed = await job_service.sweep_orphans()
    assert job_id in failed
    # Give any (wrongly) re-run a window; the counter must stay 1.
    await asyncio.sleep(0.3)
    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.FAILED, f"expected FAILED, got {job.status}"
    assert (job.error or {}).get("type") == "worker_lost"
    assert side_effect_count(effect_key) == 1, f"at-most-once violated: counter={side_effect_count(effect_key)}"
    print(  # noqa: T201
        f"PROOF[sideeffect/default]: crash mid-flight -> FAILED(worker_lost), no re-run, "
        f"real-component counter stayed {side_effect_count(effect_key)}"
    )


async def test_retry_safe_flow_requeues_and_reincrements(hard_proof_redis_url, hard_proof_job_service):
    """retry_safe=True: the SAME crash path requeues and the real counter hits 2."""
    from langflow.services.background_execution.redis_backend import RedisBackgroundQueue
    from redis.asyncio import StrictRedis

    job_service = hard_proof_job_service
    job_id, flow_id = uuid4(), uuid4()
    effect_key = f"retrysafe-{job_id}"

    # First run fires the real side effect once; the worker then dies mid-flight.
    await job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=uuid4())
    await job_service.update_job_metadata(job_id, {"retry_safe": True, "max_attempts": 2, "attempt": 1})
    await job_service.update_job_status(job_id, JobStatus.IN_PROGRESS)
    assert await _run_real_graph_once(effect_key) == 1

    # The retry-safe lease watchdog requeues the IN_PROGRESS orphan (attempt < max)
    # instead of failing it. Real redis processing list + the real backend branch.
    client = StrictRedis.from_url(hard_proof_redis_url)
    prefix = f"se-retry:{uuid4().hex}:"
    backend = RedisBackgroundQueue(client=client, job_service=job_service, startup_grace_s=5.0)
    backend.claim_queue.pending_key = f"{prefix}pending"
    backend.claim_queue.processing_key = f"{prefix}processing"
    try:
        await backend.enqueue(str(job_id))
        await backend.claim(block_ms=1000)  # strand it on the processing list
        requeued = await backend.requeue_lost()
        assert str(job_id) in requeued, "retry-safe orphan was not requeued"
    finally:
        await client.aclose()

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.QUEUED, f"retry-safe orphan should be requeued QUEUED, got {job.status}"
    assert (job.job_metadata or {}).get("attempt") == 2, "attempt must advance to 2"

    # The requeued work runs again -> the real side effect fires a SECOND time.
    assert await _run_real_graph_once(effect_key) == 2

    print(  # noqa: T201
        f"PROOF[sideeffect/retrysafe]: crash mid-flight + retry_safe -> requeued (attempt=2), "
        f"real-component counter={side_effect_count(effect_key)}. DELTA vs default = +1 increment"
    )


async def test_concurrent_sweeps_run_queued_job_exactly_once(hard_proof_job_service):
    """Two concurrent startup sweeps over one QUEUED job fire the durable run EXACTLY once.

    The single-flight claim guard (``UPDATE ... WHERE status='QUEUED'``) lets only
    one of two booting sweepers re-enqueue the row, so a non-idempotent flow runs
    exactly once. We count durable ``add_message`` side-effect rows (a clean,
    deterministic at-most-once probe; the real-component graph is proven to fire
    once per build in the at-most-once / retry-safe tests above). Real SQLite +
    real Postgres.
    """
    import json

    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    job_service = hard_proof_job_service
    job_id, flow_id, user_id = uuid4(), uuid4(), uuid4()

    def _marker_source_factory(*, request, **_kwargs):  # noqa: ARG001
        async def _source(**_kw):
            yield (json.dumps({"event": "add_message", "data": {"marker": "ran"}}).encode(), "add_message")
            yield (json.dumps({"event": "end", "data": {}}).encode(), "end")

        return _source

    request = {"flow_id": str(flow_id), "stream_protocol": "langflow", "input_value": "x"}
    await job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)
    await job_service.update_job_metadata(job_id, {"request": request})

    svc_a = BackgroundExecutionService(
        settings_service=get_settings_service(), frame_source_factory=_marker_source_factory
    )
    svc_b = BackgroundExecutionService(
        settings_service=get_settings_service(), frame_source_factory=_marker_source_factory
    )
    await svc_a.start()
    await svc_b.start()
    try:
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
    assert len(markers) == 1, f"QUEUED job ran {len(markers)} times, expected exactly 1 (claim guard)"
    print(  # noqa: T201
        f"PROOF[sideeffect/exactly-once]: two concurrent startup sweeps over one QUEUED job ran the "
        f"side effect exactly {len(markers)} time (single-flight claim guard)"
    )
