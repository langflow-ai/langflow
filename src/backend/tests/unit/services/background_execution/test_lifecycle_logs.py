"""Structured lifecycle logs: one ``event_type="bg_job"`` line per transition.

Captures REAL structlog output via ``structlog.testing.capture_logs`` (not a
mock — it records the actual event dicts the code emits) while driving a real
job to a terminal state through the runner. The runner uses the real JobService
against the test DB (via the ``client`` fixture) and the real in-memory live bus.

Two structlog quirks make the global ``lfx.log.logger.logger`` invisible to
``capture_logs`` out of the box, so ``_bg_log_capture`` resets them first (all
real structlog machinery, no mocking):

* The wrapper class filters at the configured level (the global logger boots at
  CRITICAL/ERROR), so ``logger.info`` is short-circuited before any processor
  runs. ``configure(log_level="DEBUG")`` lowers the filter so INFO passes.
* The module-level logger is a cached ``BoundLoggerLazyProxy``: at app startup
  ``cache_logger_on_first_use`` was True, so the proxy froze its bound logger
  (and a reference to the then-current processors). ``capture_logs`` swaps the
  configured processors, but the frozen proxy ignores the swap. Deleting the
  cached ``bind`` lets the proxy re-bind against the captured config.
"""

from __future__ import annotations

import contextlib
import json
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from langflow.api.v2.adapters import StreamAdapterContext, get_stream_adapter
from langflow.services.background_execution.live_bus import InMemoryLiveBus
from langflow.services.background_execution.runner import JobRunner
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.deps import get_job_service
from lfx.log.logger import configure, logger
from structlog.testing import capture_logs

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.usefixtures("client")


@contextlib.contextmanager
def _bg_log_capture():
    """Capture the global logger's real output. Yields the captured records list."""
    # Lower the filter so INFO passes; cache off so the proxy re-binds per call.
    configure(log_level="DEBUG", cache=False)
    # Drop the proxy's frozen bind so it re-binds against capture_logs's config.
    logger.__dict__.pop("bind", None)
    with capture_logs() as caps:
        yield caps


def _frame(event_type: str, data: dict) -> tuple[bytes, str]:
    payload = {"event": event_type, "data": data}
    return (json.dumps(payload).encode("utf-8"), event_type)


async def _make_job(flow_id, user_id):
    job_id = uuid4()
    await get_job_service().create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)
    return job_id


def _bg_records(caps: list[dict]) -> list[dict]:
    return [r for r in caps if r.get("event_type") == "bg_job"]


async def test_runner_emits_bg_job_lifecycle_logs(active_user):
    """A real job driven to COMPLETED emits a start and a terminal bg_job log."""
    job_service = get_job_service()
    flow_id = uuid4()
    job_id = await _make_job(flow_id, active_user.id)

    async def source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
        yield _frame("build_start", {})
        yield _frame("end_vertex", {"id": "n1"})
        yield _frame("end", {})

    bus = InMemoryLiveBus()
    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t"))
    runner = JobRunner(job_service=job_service, live_bus=bus, adapter=adapter, frame_source=source)

    with _bg_log_capture() as caps:
        await runner.run(job_id=job_id, source_kwargs={})

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.COMPLETED

    bg = _bg_records(caps)
    # At least the start line and the terminal line.
    assert len(bg) >= 2, f"expected >=2 bg_job records, got {bg}"

    # Every bg_job record carries the core identifiers.
    for rec in bg:
        assert rec["job_id"] == str(job_id)
        assert rec["backend"] in ("default", "scaled")
        assert "status" in rec
        # event_type is the marker key; the message lives on "event" (reserved).
        assert rec["event"].startswith("background job")

    # A start line is present.
    started = [r for r in bg if r.get("status") == "started"]
    assert started, f"expected a started record, got {bg}"

    # The terminal line reports the final status and carries a duration.
    terminal = [r for r in bg if r.get("status") == "completed"]
    assert terminal, f"expected a completed terminal record, got {bg}"
    assert "duration_ms" in terminal[0]
    assert isinstance(terminal[0]["duration_ms"], int)
    # flow_id rides along on the terminal line for per-job forensics.
    assert terminal[0]["flow_id"] == str(flow_id)


async def test_runner_tags_bg_job_logs_with_worker_owner(active_user):
    """A runner with an owner stamps ``worker`` on both the started and terminal lines."""
    job_service = get_job_service()
    flow_id = uuid4()
    job_id = await _make_job(flow_id, active_user.id)
    owner = "worker:4242:deadbeef"

    async def source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
        yield _frame("build_start", {})
        yield _frame("end", {})

    bus = InMemoryLiveBus()
    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t"))
    runner = JobRunner(job_service=job_service, live_bus=bus, adapter=adapter, frame_source=source, owner=owner)

    with _bg_log_capture() as caps:
        await runner.run(job_id=job_id, source_kwargs={})

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.COMPLETED

    bg = _bg_records(caps)
    started = [r for r in bg if r.get("status") == "started"]
    terminal = [r for r in bg if r.get("status") == "completed"]
    assert started, f"expected a started record, got {bg}"
    assert terminal, f"expected a completed terminal record, got {bg}"
    assert started[0]["worker"] == owner
    assert terminal[0]["worker"] == owner


async def test_runner_omits_worker_on_default_backend(active_user):
    """With no owner (in-process default backend), no bg_job line carries a worker key."""
    job_service = get_job_service()
    flow_id = uuid4()
    job_id = await _make_job(flow_id, active_user.id)

    async def source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
        yield _frame("build_start", {})
        yield _frame("end", {})

    bus = InMemoryLiveBus()
    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t"))
    runner = JobRunner(job_service=job_service, live_bus=bus, adapter=adapter, frame_source=source)

    with _bg_log_capture() as caps:
        await runner.run(job_id=job_id, source_kwargs={})

    bg = _bg_records(caps)
    assert bg, "expected at least one bg_job record"
    for rec in bg:
        assert "worker" not in rec, f"unexpected worker key on default backend: {rec}"


async def test_runner_emits_bg_job_failed_log_with_reason(active_user):
    """A job that errors emits a terminal bg_job log with reason=error."""
    job_service = get_job_service()
    job_id = await _make_job(uuid4(), active_user.id)

    async def source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
        yield _frame("error", {"error": "kaboom"})

    bus = InMemoryLiveBus()
    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t"))
    runner = JobRunner(job_service=job_service, live_bus=bus, adapter=adapter, frame_source=source)

    with _bg_log_capture() as caps:
        await runner.run(job_id=job_id, source_kwargs={})

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.FAILED

    bg = _bg_records(caps)
    terminal = [r for r in bg if r.get("status") == "failed"]
    assert terminal, f"expected a failed terminal record, got {bg}"
    assert terminal[0]["reason"] == "error"
    assert "duration_ms" in terminal[0]


async def test_sweep_orphans_emits_worker_lost_log(active_user):
    """A reconciled orphan emits a bg_job worker_lost log line."""
    job_service = get_job_service()
    flow_id = uuid4()
    job_id = await _make_job(flow_id, active_user.id)
    # Flip to IN_PROGRESS with no heartbeat so the lease is stale -> orphan.
    await job_service.update_job_status(job_id, JobStatus.IN_PROGRESS)

    with _bg_log_capture() as caps:
        reconciled = await job_service.sweep_orphans(lease_ttl_s=0.0)

    assert job_id in reconciled

    bg = _bg_records(caps)
    worker_lost = [r for r in bg if r.get("reason") == "worker_lost"]
    assert worker_lost, f"expected a worker_lost record, got {bg}"
    rec = worker_lost[0]
    assert rec["job_id"] == str(job_id)
    assert rec["status"] == "failed"
    assert rec["backend"] in ("default", "scaled")
    assert rec["event"] == "background job worker_lost"
