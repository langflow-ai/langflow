"""Runner suspend mechanics (LE-1442) against a real JobService + live bus.

When a producer pauses for human input, the runner must exit WITHOUT finalizing
to a terminal status: it writes SUSPENDED (no finished_timestamp), appends a
durable ``human_input_required`` event, and leaves result/error untouched.
The scripted frame source emits the pause sentinel the real build path raises.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from langflow.services.background_execution.live_bus import InMemoryLiveBus
from langflow.services.background_execution.runner import HUMAN_INPUT_REQUIRED_EVENT, JobRunner
from langflow.services.database.models.jobs.model import JobStatus
from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter


def _frame(event_type: str, data: dict) -> tuple[bytes, str]:
    return (json.dumps({"event": event_type, "data": data}).encode(), event_type)


def _pause_source(payload: dict):
    async def _source(**_kwargs):
        yield _frame("add_message", {"text": "working…"})
        yield (json.dumps(payload).encode(), HUMAN_INPUT_REQUIRED_EVENT)

    return _source


def _runner(job_service, job_id, source):
    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t"))
    return JobRunner(job_service=job_service, live_bus=InMemoryLiveBus(), adapter=adapter, frame_source=source)


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_runner_suspends_without_terminalizing(real_services_job_service) -> None:
    job_service = real_services_job_service
    job_id, flow_id = uuid4(), uuid4()
    await job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=uuid4())

    payload = {"reason": "human_input_required", "request_id": "req-1", "options": ["approve", "reject"]}
    runner = _runner(job_service, job_id, _pause_source(payload))
    await runner.run(job_id=job_id, source_kwargs={})

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.SUSPENDED
    assert job.result is None
    assert job.error is None
    assert job.finished_timestamp is None


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_suspend_appends_durable_human_input_event(real_services_job_service) -> None:
    job_service = real_services_job_service
    job_id, flow_id = uuid4(), uuid4()
    await job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=uuid4())

    payload = {"reason": "human_input_required", "request_id": "req-2", "options": ["yes", "no"]}
    runner = _runner(job_service, job_id, _pause_source(payload))
    await runner.run(job_id=job_id, source_kwargs={})

    events = await job_service.read_events(job_id, after_seq=0)
    types = [e.event_type for e in events]
    assert HUMAN_INPUT_REQUIRED_EVENT in types
    assert "add_message" in types
    # No terminal event was appended.
    assert not ({"run_cancelled", "run_timed_out", "end"} & set(types))
    human = next(e for e in events if e.event_type == HUMAN_INPUT_REQUIRED_EVENT)
    assert human.payload["request_id"] == "req-2"


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_suspend_records_pending_request_id(real_services_job_service) -> None:
    job_service = real_services_job_service
    job_id, flow_id = uuid4(), uuid4()
    await job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=uuid4())

    payload = {"reason": "human_input_required", "request_id": "req-3"}
    runner = _runner(job_service, job_id, _pause_source(payload))
    await runner.run(job_id=job_id, source_kwargs={})

    job = await job_service.get_job_by_job_id(job_id)
    assert (job.job_metadata or {}).get("pending_request_id") == "req-3"


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_get_pending_human_request_returns_last_payload(real_services_job_service) -> None:
    job_service = real_services_job_service
    job_id, flow_id = uuid4(), uuid4()
    await job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=uuid4())

    payload = {"reason": "human_input_required", "request_id": "req-9", "options": ["a", "b"]}
    runner = _runner(job_service, job_id, _pause_source(payload))
    await runner.run(job_id=job_id, source_kwargs={})

    pending = await job_service.get_pending_human_request(job_id)
    assert pending is not None
    assert pending["request_id"] == "req-9"
    assert pending["options"] == ["a", "b"]


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_get_pending_human_request_none_when_not_suspended(real_services_job_service) -> None:
    job_service = real_services_job_service
    job_id, flow_id = uuid4(), uuid4()
    await job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=uuid4())

    assert await job_service.get_pending_human_request(job_id) is None


class _StubUser:
    def __init__(self, user_id):
        self.id = user_id


async def _suspend_a_job(job_service, *, request_id="req-evt"):
    user_id, flow_id, job_id = uuid4(), uuid4(), uuid4()
    await job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)
    await job_service.update_job_metadata(job_id, {"request": {"stream_protocol": "langflow"}})
    payload = {"reason": "human_input_required", "request_id": request_id, "options": ["x"]}
    await _runner(job_service, job_id, _pause_source(payload)).run(job_id=job_id, source_kwargs={})
    return user_id, job_id


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_events_replays_suspended_job_and_returns(real_services_job_service) -> None:
    """A fresh facade (empty live bus) replays the suspended job's durable rows and RETURNS."""
    import asyncio

    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    job_service = real_services_job_service
    user_id, job_id = await _suspend_a_job(job_service)

    svc = BackgroundExecutionService(settings_service=get_settings_service())
    user = _StubUser(user_id)

    async def _collect() -> list[bytes]:
        return [frame async for frame in svc.events(job_id, None, user)]

    # A hang (live-tail block) is caught by wait_for instead of stalling the suite.
    frames = await asyncio.wait_for(_collect(), timeout=5.0)
    joined = b"".join(frames).decode()
    assert HUMAN_INPUT_REQUIRED_EVENT in joined
    assert "add_message" in joined


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_status_includes_pending_human_request(real_services_job_service) -> None:
    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    job_service = real_services_job_service
    user_id, job_id = await _suspend_a_job(job_service, request_id="req-status")

    svc = BackgroundExecutionService(settings_service=get_settings_service())
    status = await svc.status(job_id, _StubUser(user_id))

    assert status["status"] == JobStatus.SUSPENDED
    assert status["pending_request"]["request_id"] == "req-status"


def _stop_then_pause_source(payload: dict):
    async def _source(**_kwargs):
        yield _frame("add_message", {"text": "working…"})
        yield (json.dumps(payload).encode(), HUMAN_INPUT_REQUIRED_EVENT)

    return _source


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_stop_beats_pause_in_drive(real_services_job_service) -> None:
    """A STOP pending when the pause frame arrives wins: the run ends CANCELLED, not SUSPENDED."""
    from langflow.services.database.models.jobs.model import SignalType

    job_service = real_services_job_service
    job_id, flow_id = uuid4(), uuid4()
    await job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=uuid4())
    await job_service.write_signal(job_id, SignalType.STOP)  # stop already requested before the pause

    payload = {"reason": "human_input_required", "request_id": "req-sp"}
    runner = _runner(job_service, job_id, _stop_then_pause_source(payload))
    await runner.run(job_id=job_id, source_kwargs={})

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.CANCELLED


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_stop_while_suspended_cancels_and_cleans_up(real_services_job_service) -> None:
    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.database.models.jobs.model import SignalType
    from langflow.services.deps import get_settings_service

    job_service = real_services_job_service
    user_id, job_id = await _suspend_a_job(job_service, request_id="req-stopsusp")
    await job_service.save_checkpoint(job_id, "graph", '{"checkpoint":"data"}')

    svc = BackgroundExecutionService(settings_service=get_settings_service())
    await svc.stop_job(job_id, _StubUser(user_id))

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.CANCELLED
    assert job.finished_timestamp is not None
    assert await job_service.load_checkpoint(job_id, "graph") is None  # checkpoint deleted
    assert (job.job_metadata or {}).get("pending_request_id") is None  # request cleared
    events = await job_service.read_events(job_id, after_seq=0)
    assert "run_cancelled" in [e.event_type for e in events]
    unconsumed = await job_service.unconsumed_signals(job_id)
    assert not [s for s in unconsumed if s.signal_type == SignalType.STOP]  # no STOP left on a resumable row


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_suspended_job_survives_orphan_sweep(real_services_job_service) -> None:
    """The startup sweep only reconciles IN_PROGRESS rows, so SUSPENDED is left alone."""
    job_service = real_services_job_service
    _user_id, job_id = await _suspend_a_job(job_service, request_id="req-sweep")

    reconciled = await job_service.sweep_orphans(lease_ttl_s=0.0)  # everything stale

    assert job_id not in reconciled
    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.SUSPENDED


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_pause_signal_left_unconsumed(real_services_job_service) -> None:
    """A polled PAUSE signal is a seam for a future API button — the runner must not consume it."""
    from langflow.services.database.models.jobs.model import SignalType

    job_service = real_services_job_service
    job_id, flow_id = uuid4(), uuid4()
    await job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=uuid4())
    await job_service.write_signal(job_id, SignalType.PAUSE)

    payload = {"reason": "human_input_required", "request_id": "req-pause"}
    await _runner(job_service, job_id, _pause_source(payload)).run(job_id=job_id, source_kwargs={})

    unconsumed = await job_service.unconsumed_signals(job_id)
    assert [s.signal_type for s in unconsumed] == [SignalType.PAUSE]


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_heartbeat_stopped_before_suspend_preserves_request_id(real_services_job_service) -> None:
    """With the heartbeat running, suspend still records the request id (no clobber race)."""
    job_service = real_services_job_service
    job_id, flow_id = uuid4(), uuid4()
    await job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=uuid4())

    payload = {"reason": "human_input_required", "request_id": "req-hb"}
    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t"))
    runner = JobRunner(
        job_service=job_service,
        live_bus=InMemoryLiveBus(),
        adapter=adapter,
        frame_source=_pause_source(payload),
        owner="worker-1",
        heartbeat_interval_s=0.01,  # beat aggressively to expose a clobber race
    )
    await runner.run(job_id=job_id, source_kwargs={})

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.SUSPENDED
    assert (job.job_metadata or {}).get("pending_request_id") == "req-hb"
