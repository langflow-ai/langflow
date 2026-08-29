"""Verify the durable background path on real SQLite AND real Postgres.

The Runner + InMemoryLiveBus + facade durable replay all sit on ``JobService``,
whose ``session_scope()`` the ``real_services_job_service`` fixture binds to a real,
migrated DB parametrized over sqlite and postgres. These tests drive the real
Runner with a scripted frame source (legitimate test input, not a mock of our
logic) and assert durable persistence, ordering, terminal state, reattach replay,
and the orphan sweep on BOTH engines.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from langflow.services.background_execution.live_bus import InMemoryLiveBus, LiveFrame
from langflow.services.background_execution.runner import JobRunner
from langflow.services.database.models.jobs.model import JobStatus, SignalType
from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.real_services


def _frame(event_type: str, data: dict) -> tuple[bytes, str]:
    return (json.dumps({"event": event_type, "data": data}).encode("utf-8"), event_type)


def _runner(job_service, bus, job_id, source) -> JobRunner:
    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t"))
    return JobRunner(job_service=job_service, live_bus=bus, adapter=adapter, frame_source=source)


async def test_durable_persistence_and_terminal_state(real_services_job_service):
    job_service = real_services_job_service
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


async def test_reattach_replays_durable_after_completion(real_services_job_service):
    job_service = real_services_job_service
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


async def test_reattach_from_midpoint_has_no_gap(real_services_job_service):
    job_service = real_services_job_service
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


async def test_stop_signal_cancels_run(real_services_job_service):
    job_service = real_services_job_service
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


async def test_sweep_orphans_fails_in_progress(real_services_job_service):
    job_service = real_services_job_service
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())
    await job_service.update_job_status(job_id, JobStatus.IN_PROGRESS)

    failed = await job_service.sweep_orphans()
    assert job_id in failed
    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.FAILED
    assert job.error is not None
    assert job.error.get("type") == "worker_lost"


async def test_redis_fallback_watchdog_reconciles_orphans_without_restart(real_services_job_service):
    """A steady Redis-configured fleet must reap a dead owner's stale job."""
    import asyncio
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace

    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings.model_copy(
        update={
            "job_queue_type": "redis",
            "background_lease_ttl_s": 0.02,
            "background_watchdog_interval_s": 0.01,
        }
    )
    service = BackgroundExecutionService(settings_service=SimpleNamespace(settings=settings))
    await service.start()
    try:
        job_id = uuid4()
        await real_services_job_service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())
        await real_services_job_service.update_job_status(job_id, JobStatus.IN_PROGRESS)
        stale_heartbeat = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
        await real_services_job_service.update_job_metadata(
            job_id,
            {"owner": "dead-replica", "heartbeat_at": stale_heartbeat},
        )

        job = None
        for _ in range(100):
            job = await real_services_job_service.get_job_by_job_id(job_id)
            if job.status == JobStatus.FAILED:
                break
            await asyncio.sleep(0.01)

        assert job is not None
        assert job.status == JobStatus.FAILED
        assert job.error == {"type": "worker_lost"}
        assert job.finished_timestamp is not None
    finally:
        await service.stop()


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


class _RecordingBackend:
    """Scaled-backend stand-in that records durable job ids without running them."""

    def __init__(self) -> None:
        self.enqueued: list[str] = []

    async def enqueue(self, job_id: str) -> None:
        self.enqueued.append(job_id)


def _capture_request_factory(captured: list[dict]):
    """Record the request a fresh worker hydrates without persisting its secrets."""

    def _factory(*, request, **_kwargs):
        captured.append(request)

        async def _source(**_kw):
            yield _frame("end", {})

        return _source

    return _factory


async def test_submit_persists_request_for_faithful_requeue(real_services_job_service):
    """``submit`` persists only replay-safe request fields on job_metadata.request.

    The startup sweep needs the original non-secret inputs, but caller tweaks may
    contain credentials and must live outside the plaintext request in an encrypted
    envelope. Proven on both real SQLite and real Postgres. The executor is stopped
    right after submit so no run interferes with reading the persisted row.
    """
    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    job_service = real_services_job_service
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
    assert persisted == {
        "flow_id": str(flow_id),
        "mode": "background",
        "stream_protocol": "langflow",
        "input_value": original_input,
        "session_id": "thread-restart",
    }
    assert job.job_metadata.get("request_overrides_format") == "fernet-json-v1"
    assert isinstance(job.job_metadata.get("request_overrides"), str)
    hydrated = svc._reconstruct_request(job)
    assert hydrated == request
    # Redaction must not mutate the live request passed to the in-memory run.
    assert request["tweaks"] == {"ChatInput-x": {"foo": "bar"}}


async def test_submit_redacts_inline_overrides_from_persisted_request(real_services_job_service):
    """Inline ``globals`` and ``tweaks`` must NOT land plaintext on the row.

    Both request shapes can carry API keys. Storing either plaintext in the durable
    ``job`` table widens the blast radius of any DB read (backup, ops access, a
    SQL-injection elsewhere). The persisted plaintext request must omit both while
    authenticated decryption restores them for replay. Real SQLite and Postgres.
    """
    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    job_service = real_services_job_service
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
        "tweaks": {"LanguageModelComponent-x": {"api_key": secret}},
    }
    job_id = await svc.submit(flow_id=flow_id, request=request, user=_StubUser(uuid4()))
    await svc.stop()

    job = await job_service.get_job_by_job_id(job_id)
    persisted = job.job_metadata.get("request") or {}
    # Neither secret-bearing override shape may appear in the persisted blob.
    assert "globals" not in persisted, "inline globals persisted plaintext on the job row"
    assert "tweaks" not in persisted, "inline tweaks persisted plaintext on the job row"
    assert secret not in json.dumps(job.job_metadata), "inline secret leaked into job_metadata"
    assert svc._reconstruct_request(job) == request
    # The caller's original request dict is not mutated as a side effect.
    assert request["globals"] == {"OPENAI_API_KEY": secret}
    assert request["tweaks"] == {"LanguageModelComponent-x": {"api_key": secret}}


async def test_submit_writes_request_and_encrypted_overrides_atomically(real_services_job_service, monkeypatch):
    """Submit must not expose a QUEUED row before its durable replay payload exists."""
    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    job_service = real_services_job_service
    backend = _RecordingBackend()
    flow_id = uuid4()

    async def _unexpected_metadata_update(*_args, **_kwargs):
        pytest.fail("submit persisted replay metadata in a second transaction")

    monkeypatch.setattr(job_service, "update_job_metadata", _unexpected_metadata_update)
    svc = BackgroundExecutionService(
        settings_service=get_settings_service(),
        frame_source_factory=_echo_input_factory,
        backend=backend,
    )
    request = {
        "flow_id": str(flow_id),
        "mode": "background",
        "stream_protocol": "langflow",
        "input_value": "atomic",
        "tweaks": {"LanguageModelComponent-x": {"api_key": "secret-atomic"}},  # pragma: allowlist secret
    }
    job_id = await svc.submit(flow_id=flow_id, request=request, user=_StubUser(uuid4()))

    assert backend.enqueued == [str(job_id)]
    job = await job_service.get_job_by_job_id(job_id)
    assert job.job_metadata.get("request") == {
        "flow_id": str(flow_id),
        "mode": "background",
        "stream_protocol": "langflow",
        "input_value": "atomic",
    }
    assert "secret-atomic" not in json.dumps(job.job_metadata)


@pytest.mark.parametrize(
    ("field", "invalid_case"),
    [
        ("tweaks", "nan"),
        ("tweaks", "infinity"),
        ("tweaks", "non-string-key"),
        ("tweaks", "unsupported-value"),
        ("tweaks", "cycle"),
        ("tweaks", "too-deep"),
        ("tweaks", "lone-surrogate"),
        ("tweaks", "lone-surrogate-key"),
        ("tweaks", "oversized-integer"),
        ("tweaks", "top-level-shape"),
        ("globals", "top-level-shape"),
    ],
)
async def test_submit_rejects_invalid_override_grammar_before_creating_job(
    real_services_job_service,
    field,
    invalid_case,
):
    """Caller validation failures identify the field and never persist a job."""
    from langflow.services.background_execution.service import (
        BackgroundExecutionService,
        InvalidRequestOverridesError,
    )
    from langflow.services.deps import get_settings_service

    if invalid_case == "nan":
        invalid_value = {"Node-x": {"value": float("nan")}}
    elif invalid_case == "infinity":
        invalid_value = {"Node-x": {"value": float("inf")}}
    elif invalid_case == "non-string-key":
        invalid_value = {"Node-x": {1: "value"}}
    elif invalid_case == "unsupported-value":
        invalid_value = {"Node-x": {"value": object()}}
    elif invalid_case == "cycle":
        cyclic: dict = {}
        cyclic["self"] = cyclic
        invalid_value = {"Node-x": cyclic}
    elif invalid_case == "too-deep":
        nested: object = "leaf"
        for _ in range(66):
            nested = [nested]
        invalid_value = {"Node-x": {"value": nested}}
    elif invalid_case == "lone-surrogate":
        invalid_value = {"Node-x": {"value": "\ud800"}}
    elif invalid_case == "lone-surrogate-key":
        invalid_value = {"Node-x": {"\ud800": "value"}}
    elif invalid_case == "oversized-integer":
        invalid_value = {"Node-x": {"value": 10**5000}}
    else:
        invalid_value = ["not-a-mapping"]

    job_service = real_services_job_service
    flow_id, user_id = uuid4(), uuid4()
    service = BackgroundExecutionService(
        settings_service=get_settings_service(),
        frame_source_factory=_echo_input_factory,
        backend=_RecordingBackend(),
    )
    request = {
        "flow_id": str(flow_id),
        "mode": "background",
        "stream_protocol": "langflow",
        "input_value": "invalid-overrides",
        field: invalid_value,
    }

    with pytest.raises(InvalidRequestOverridesError) as exc_info:
        await service.submit(flow_id=flow_id, request=request, user=_StubUser(user_id))

    assert exc_info.value.field == field
    assert await job_service.get_jobs_by_flow_id(flow_id, user_id) == []


async def test_submit_crypto_unavailable_creates_no_job(real_services_job_service, monkeypatch):
    """Server-side encryption failure is retryable and precedes durable creation."""
    from langflow.services.background_execution.service import (
        BackgroundExecutionService,
        RequestOverridesUnavailableError,
    )
    from langflow.services.deps import get_settings_service

    def _unavailable_fernet(_settings_service):
        raise RuntimeError

    monkeypatch.setattr("langflow.services.auth.utils.get_fernet", _unavailable_fernet)
    job_service = real_services_job_service
    flow_id, user_id = uuid4(), uuid4()
    service = BackgroundExecutionService(
        settings_service=get_settings_service(),
        frame_source_factory=_echo_input_factory,
        backend=_RecordingBackend(),
    )
    request = {
        "flow_id": str(flow_id),
        "mode": "background",
        "stream_protocol": "langflow",
        "input_value": "crypto-unavailable",
        "tweaks": {"Node-x": {"api_key": "never-persisted"}},  # pragma: allowlist secret
    }

    with pytest.raises(RequestOverridesUnavailableError):
        await service.submit(flow_id=flow_id, request=request, user=_StubUser(user_id))

    assert await job_service.get_jobs_by_flow_id(flow_id, user_id) == []


async def test_submit_serialization_resource_unavailable_creates_no_job(real_services_job_service, monkeypatch):
    """Transient JSON serialization resource failures use the retryable server error."""
    from types import SimpleNamespace

    from langflow.services.background_execution import service as background_service
    from langflow.services.background_execution.service import (
        BackgroundExecutionService,
        RequestOverridesUnavailableError,
    )
    from langflow.services.deps import get_settings_service

    def _unavailable_dumps(*_args, **_kwargs):
        raise MemoryError

    monkeypatch.setattr(
        background_service,
        "json",
        SimpleNamespace(dumps=_unavailable_dumps, loads=json.loads),
    )
    job_service = real_services_job_service
    flow_id, user_id = uuid4(), uuid4()
    service = BackgroundExecutionService(
        settings_service=get_settings_service(),
        frame_source_factory=_echo_input_factory,
        backend=_RecordingBackend(),
    )
    request = {
        "flow_id": str(flow_id),
        "mode": "background",
        "stream_protocol": "langflow",
        "tweaks": {"Node-x": {"value": "retry-after-resource-recovery"}},
    }

    with pytest.raises(RequestOverridesUnavailableError):
        await service.submit(flow_id=flow_id, request=request, user=_StubUser(user_id))

    assert await job_service.get_jobs_by_flow_id(flow_id, user_id) == []


@pytest.mark.parametrize("new_owner", ["old-owner", "new-owner"])
async def test_release_queued_lease_never_clears_an_updated_claim(real_services_job_service, new_owner):
    """A stale recovery cannot release a claim whose owner or heartbeat advanced."""
    from datetime import datetime, timezone

    job_service = real_services_job_service
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())
    old_heartbeat = datetime.now(timezone.utc).isoformat()
    assert await job_service.claim_queued_lease(
        job_id,
        owner="old-owner",
        lease_ttl_s=0,
        heartbeat_at=old_heartbeat,
    )
    new_heartbeat = datetime.now(timezone.utc).isoformat()
    await job_service.update_job_metadata(job_id, {"owner": new_owner, "heartbeat_at": new_heartbeat})

    released = await job_service.release_queued_lease(
        job_id,
        owner="old-owner",
        heartbeat_at=old_heartbeat,
    )

    assert released is False
    job = await job_service.get_job_by_job_id(job_id)
    assert (job.job_metadata or {}).get("owner") == new_owner
    assert (job.job_metadata or {}).get("heartbeat_at") == new_heartbeat
    await job_service.update_job_status(job_id, JobStatus.CANCELLED, finished_timestamp=True)


async def test_fail_queued_job_never_terminalizes_a_replaced_claim(real_services_job_service):
    """A stale recovery cannot fail a QUEUED row after another owner replaces its claim."""
    from datetime import datetime, timezone

    job_service = real_services_job_service
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())
    old_heartbeat = datetime.now(timezone.utc).isoformat()
    assert await job_service.claim_queued_lease(
        job_id,
        owner="old-owner",
        lease_ttl_s=0,
        heartbeat_at=old_heartbeat,
    )
    new_heartbeat = datetime.now(timezone.utc).isoformat()
    await job_service.update_job_metadata(job_id, {"owner": "new-owner", "heartbeat_at": new_heartbeat})

    failed = await job_service.fail_queued_job(
        job_id,
        owner="old-owner",
        heartbeat_at=old_heartbeat,
        error={"type": "request_overrides_unavailable"},
        event_type="run_failed",
    )

    assert failed is False
    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.QUEUED
    assert job.error is None
    assert (job.job_metadata or {}).get("owner") == "new-owner"
    assert (job.job_metadata or {}).get("heartbeat_at") == new_heartbeat
    assert await job_service.read_events(job_id, after_seq=0) == []
    await job_service.update_job_status(job_id, JobStatus.CANCELLED, finished_timestamp=True)


async def test_fail_queued_job_retries_event_sequence_collision_atomically(real_services_job_service, monkeypatch):
    """A colliding event insert rolls back the status CAS before retrying the whole transaction."""
    from datetime import datetime, timezone

    from langflow.services.database.models.jobs.model import JobEvent
    from langflow.services.jobs import service as jobs_service_module
    from sqlalchemy.exc import IntegrityError

    job_service = real_services_job_service
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())
    heartbeat = datetime.now(timezone.utc).isoformat()
    assert await job_service.claim_queued_lease(
        job_id,
        owner="recovery-owner",
        lease_ttl_s=0,
        heartbeat_at=heartbeat,
    )
    await job_service.append_event(job_id, "queued", {})

    calls = 0

    class _CollidingJobEvent:
        job_id = JobEvent.job_id
        seq = JobEvent.seq

        def __new__(cls, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                collision = "forced event sequence collision"
                raise IntegrityError(collision, None, RuntimeError())
            return JobEvent(*args, **kwargs)

    monkeypatch.setattr(jobs_service_module, "JobEvent", _CollidingJobEvent)

    failed = await job_service.fail_queued_job(
        job_id,
        owner="recovery-owner",
        heartbeat_at=heartbeat,
        error={"type": "request_overrides_unavailable"},
        event_type="run_failed",
    )
    monkeypatch.setattr(jobs_service_module, "JobEvent", JobEvent)

    assert failed is True
    assert calls == 2
    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.FAILED
    assert job.error == {"type": "request_overrides_unavailable"}
    assert [(event.seq, event.event_type) for event in await job_service.read_events(job_id, after_seq=0)] == [
        (1, "queued"),
        (2, "run_failed"),
    ]


async def test_restart_and_scaled_hydration_restore_encrypted_overrides(real_services_job_service):
    """A job-id-only handoff and a fresh startup both replay the original overrides."""
    import asyncio

    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    job_service = real_services_job_service
    backend = _RecordingBackend()
    flow_id = uuid4()
    request = {
        "flow_id": str(flow_id),
        "mode": "background",
        "stream_protocol": "langflow",
        "input_value": "restart-with-overrides",
        "globals": {"MODEL_API_KEY": "restart-secret"},  # pragma: allowlist secret
        "tweaks": {  # pragma: allowlist secret
            "LanguageModelComponent-x": {  # pragma: allowlist secret
                "api_key": "restart-secret",  # pragma: allowlist secret
                "temperature": 0.2,
            }
        },
    }
    submitter = BackgroundExecutionService(
        settings_service=get_settings_service(),
        frame_source_factory=_echo_input_factory,
        backend=backend,
    )
    job_id = await submitter.submit(flow_id=flow_id, request=request, user=_StubUser(uuid4()))
    assert backend.enqueued == [str(job_id)]

    job = await job_service.get_job_by_job_id(job_id)
    # This is the worker/scaled hydration seam: only the queued job id crosses the bus.
    assert submitter._reconstruct_request(job) == request

    captured: list[dict] = []
    restart = BackgroundExecutionService(
        settings_service=get_settings_service(),
        frame_source_factory=_capture_request_factory(captured),
    )
    await restart.start()
    try:
        await restart.sweep_orphans_on_startup()
        for _ in range(100):
            recovered = await job_service.get_job_by_job_id(job_id)
            if recovered.status == JobStatus.COMPLETED:
                break
            await asyncio.sleep(0.05)
    finally:
        await restart.stop()

    # The shared real-services DB may contain other QUEUED fixtures; this target
    # must still hydrate exactly once with its full authenticated request.
    assert captured.count(request) == 1
    assert recovered.status == JobStatus.COMPLETED


@pytest.mark.parametrize("damage", ["missing", "null"])
async def test_startup_terminalizes_unavailable_encrypted_overrides(real_services_job_service, damage):
    """Malformed marker/ciphertext pairs terminalize without running downgraded."""
    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    job_service = real_services_job_service
    backend = _RecordingBackend()
    flow_id = uuid4()
    settings_service = get_settings_service()
    submitter = BackgroundExecutionService(
        settings_service=settings_service,
        frame_source_factory=_echo_input_factory,
        backend=backend,
    )
    job_id = await submitter.submit(
        flow_id=flow_id,
        request={
            "flow_id": str(flow_id),
            "mode": "background",
            "stream_protocol": "langflow",
            "input_value": "must-not-run",
            "tweaks": {  # pragma: allowlist secret
                "LanguageModelComponent-x": {"api_key": "tamper-secret"}  # pragma: allowlist secret
            },
        },
        user=_StubUser(uuid4()),
    )
    job = await job_service.get_job_by_job_id(job_id)
    metadata = dict(job.job_metadata)
    if damage == "missing":
        metadata.pop("request_overrides")
    elif damage == "null":
        metadata["request_overrides"] = None
    await job_service.update_job_metadata(job_id, metadata, replace=True)

    ran: list[dict] = []
    restart = BackgroundExecutionService(
        settings_service=settings_service,
        frame_source_factory=_capture_request_factory(ran),
    )
    await restart.sweep_orphans_on_startup()
    await restart.stop()

    failed = await job_service.get_job_by_job_id(job_id)
    assert ran == []
    assert failed.status == JobStatus.FAILED
    assert failed.error == {"type": "request_overrides_unavailable"}
    assert "tamper-secret" not in json.dumps(failed.error)
    events = await job_service.read_events(job_id, after_seq=0)
    assert [(event.event_type, event.payload) for event in events] == [
        ("run_failed", {"type": "request_overrides_unavailable"})
    ]


@pytest.mark.parametrize("failure", ["wrong-key", "auth-failure"])
async def test_startup_keeps_ambiguous_crypto_failures_queued_and_replays_after_recovery(
    real_services_job_service,
    failure,
):
    """Unreadable Fernet tokens remain retryable because key loss and tampering are indistinguishable."""
    import asyncio

    from cryptography.fernet import Fernet
    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service
    from pydantic import SecretStr

    job_service = real_services_job_service
    settings_service = get_settings_service()
    backend = _RecordingBackend()
    flow_id, user_id = uuid4(), uuid4()
    request = {
        "flow_id": str(flow_id),
        "mode": "background",
        "stream_protocol": "langflow",
        "input_value": f"recover-{failure}",
        "tweaks": {"Node-x": {"api_key": "recoverable-secret"}},  # pragma: allowlist secret
    }
    submitter = BackgroundExecutionService(
        settings_service=settings_service,
        frame_source_factory=_echo_input_factory,
        backend=backend,
    )
    job_id = await submitter.submit(flow_id=flow_id, request=request, user=_StubUser(user_id))
    original = await job_service.get_job_by_job_id(job_id)
    original_metadata = dict(original.job_metadata)

    recovery_settings = settings_service
    if failure == "wrong-key":
        wrong_auth = settings_service.auth_settings.model_copy(
            update={"SECRET_KEY": SecretStr(Fernet.generate_key().decode())}
        )
        recovery_settings = SimpleNamespace(settings=settings_service.settings, auth_settings=wrong_auth)
    else:
        damaged = dict(original_metadata)
        token = damaged["request_overrides"]
        damaged["request_overrides"] = f"{token[:-1]}{'A' if token[-1] != 'A' else 'B'}"
        await job_service.update_job_metadata(job_id, damaged, replace=True)

    ran: list[dict] = []
    unavailable = BackgroundExecutionService(
        settings_service=recovery_settings,
        frame_source_factory=_capture_request_factory(ran),
    )
    await unavailable.sweep_orphans_on_startup()
    await unavailable.stop()

    queued = await job_service.get_job_by_job_id(job_id)
    assert ran == []
    assert queued.status == JobStatus.QUEUED
    assert queued.error is None
    assert (queued.job_metadata or {}).get("owner") is None
    assert (queued.job_metadata or {}).get("heartbeat_at") is None
    assert await job_service.read_events(job_id, after_seq=0) == []

    if failure == "auth-failure":
        await job_service.update_job_metadata(job_id, original_metadata, replace=True)

    captured: list[dict] = []
    restored = BackgroundExecutionService(
        settings_service=settings_service,
        frame_source_factory=_capture_request_factory(captured),
    )
    await restored.start()
    try:
        await restored.sweep_orphans_on_startup()
        for _ in range(100):
            replayed = await job_service.get_job_by_job_id(job_id)
            if replayed.status == JobStatus.COMPLETED:
                break
            await asyncio.sleep(0.05)
    finally:
        await restored.stop()

    assert replayed.status == JobStatus.COMPLETED
    assert captured.count(request) == 1


async def test_startup_terminalizes_authenticated_malformed_override_payload(real_services_job_service):
    """Authenticated payload corruption is distinct from ambiguous Fernet authentication failure."""
    from langflow.services.auth.utils import get_fernet
    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    job_service = real_services_job_service
    settings_service = get_settings_service()
    flow_id, user_id = uuid4(), uuid4()
    submitter = BackgroundExecutionService(
        settings_service=settings_service,
        frame_source_factory=_echo_input_factory,
        backend=_RecordingBackend(),
    )
    job_id = await submitter.submit(
        flow_id=flow_id,
        request={
            "flow_id": str(flow_id),
            "mode": "background",
            "stream_protocol": "langflow",
            "input_value": "authenticated-corruption",
            "tweaks": {"Node-x": {"api_key": "corrupt-secret"}},  # pragma: allowlist secret
        },
        user=_StubUser(user_id),
    )
    job = await job_service.get_job_by_job_id(job_id)
    metadata = dict(job.job_metadata)
    malformed = {
        "version": 1,
        "job_id": str(job_id),
        "flow_id": str(flow_id),
        "overrides": {"tweaks": ["not-a-mapping"]},
    }
    metadata["request_overrides"] = get_fernet(settings_service).encrypt(json.dumps(malformed).encode()).decode()
    await job_service.update_job_metadata(job_id, metadata, replace=True)

    ran: list[dict] = []
    restart = BackgroundExecutionService(
        settings_service=settings_service,
        frame_source_factory=_capture_request_factory(ran),
    )
    await restart.sweep_orphans_on_startup()
    await restart.stop()

    failed = await job_service.get_job_by_job_id(job_id)
    assert ran == []
    assert failed.status == JobStatus.FAILED
    assert failed.error == {"type": "request_overrides_unavailable"}


async def test_startup_terminalizes_non_ascii_override_ciphertext(real_services_job_service):
    """A non-ASCII Fernet token is structural corruption, not an ambiguous authentication failure."""
    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    job_service = real_services_job_service
    settings_service = get_settings_service()
    flow_id, user_id = uuid4(), uuid4()
    submitter = BackgroundExecutionService(
        settings_service=settings_service,
        frame_source_factory=_echo_input_factory,
        backend=_RecordingBackend(),
    )
    job_id = await submitter.submit(
        flow_id=flow_id,
        request={
            "flow_id": str(flow_id),
            "mode": "background",
            "stream_protocol": "langflow",
            "tweaks": {"Node-x": {"value": "never-run"}},
        },
        user=_StubUser(user_id),
    )
    job = await job_service.get_job_by_job_id(job_id)
    metadata = dict(job.job_metadata)
    metadata["request_overrides"] = "not-a-fernet-token-\N{SNOWMAN}"
    await job_service.update_job_metadata(job_id, metadata, replace=True)

    ran: list[dict] = []
    restart = BackgroundExecutionService(
        settings_service=settings_service,
        frame_source_factory=_capture_request_factory(ran),
    )
    await restart.sweep_orphans_on_startup()
    await restart.stop()

    failed = await job_service.get_job_by_job_id(job_id)
    assert all(captured.get("flow_id") != str(flow_id) for captured in ran)
    assert failed.status == JobStatus.FAILED
    assert failed.error == {"type": "request_overrides_unavailable"}
    assert [(event.event_type, event.payload) for event in await job_service.read_events(job_id, after_seq=0)] == [
        ("run_failed", {"type": "request_overrides_unavailable"})
    ]


async def test_startup_terminalizes_authenticated_unparseable_override_payload(real_services_job_service):
    """Authenticated JSON parser-limit failures cannot abort the startup sweep or retain its lease."""
    from langflow.services.auth.utils import get_fernet
    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    job_service = real_services_job_service
    settings_service = get_settings_service()
    flow_id, job_id = uuid4(), uuid4()
    plaintext = (
        '{"version":1,"job_id":"'
        + str(job_id)
        + '","flow_id":"'
        + str(flow_id)
        + '","overrides":{"tweaks":{"Node-x":{"value":'
        + "9" * 5000
        + "}}}}"
    )
    ciphertext = get_fernet(settings_service).encrypt(plaintext.encode()).decode()
    await job_service.create_job(
        job_id=job_id,
        flow_id=flow_id,
        user_id=uuid4(),
        initial_metadata={
            "request": {
                "flow_id": str(flow_id),
                "mode": "background",
                "stream_protocol": "langflow",
            },
            "request_overrides_format": "fernet-json-v1",
            "request_overrides": ciphertext,
        },
    )

    restart = BackgroundExecutionService(settings_service=settings_service, frame_source_factory=_echo_input_factory)
    await restart.sweep_orphans_on_startup()
    await restart.stop()

    failed = await job_service.get_job_by_job_id(job_id)
    assert failed.status == JobStatus.FAILED
    assert failed.error == {"type": "request_overrides_unavailable"}
    assert failed.finished_timestamp is not None
    assert [(event.event_type, event.payload) for event in await job_service.read_events(job_id, after_seq=0)] == [
        ("run_failed", {"type": "request_overrides_unavailable"})
    ]


async def test_startup_releases_lease_for_transient_authenticated_parser_failure(
    real_services_job_service, monkeypatch
):
    """Transient parser resource failures keep an authenticated job queued for retry."""
    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    job_service = real_services_job_service
    settings_service = get_settings_service()
    flow_id, user_id = uuid4(), uuid4()
    submitter = BackgroundExecutionService(
        settings_service=settings_service,
        frame_source_factory=_echo_input_factory,
        backend=_RecordingBackend(),
    )
    job_id = await submitter.submit(
        flow_id=flow_id,
        request={
            "flow_id": str(flow_id),
            "mode": "background",
            "stream_protocol": "langflow",
            "tweaks": {"Node-x": {"value": "retry-after-resource-recovery"}},
        },
        user=_StubUser(user_id),
    )
    monkeypatch.setattr(
        "langflow.services.background_execution.service.json.loads",
        lambda _plaintext: (_ for _ in ()).throw(MemoryError),
    )

    ran: list[dict] = []
    restart = BackgroundExecutionService(
        settings_service=settings_service,
        frame_source_factory=_capture_request_factory(ran),
    )
    await restart.sweep_orphans_on_startup()
    await restart.stop()

    queued = await job_service.get_job_by_job_id(job_id)
    assert ran == []
    assert queued.status == JobStatus.QUEUED
    assert queued.error is None
    assert queued.finished_timestamp is None
    assert (queued.job_metadata or {}).get("owner") is None
    assert (queued.job_metadata or {}).get("heartbeat_at") is None
    assert await job_service.read_events(job_id, after_seq=0) == []


async def test_wrong_key_cross_job_and_null_envelopes_fail_closed(real_services_job_service):
    """Worker hydration rejects wrong-key, cross-job, and nulled ciphertext."""
    from cryptography.fernet import Fernet
    from langflow.services.background_execution.service import (
        BackgroundExecutionService,
        RequestOverridesUnavailableError,
    )
    from langflow.services.deps import get_settings_service
    from pydantic import SecretStr

    job_service = real_services_job_service
    backend = _RecordingBackend()
    settings_service = get_settings_service()
    flow_id = uuid4()
    submitter = BackgroundExecutionService(
        settings_service=settings_service,
        frame_source_factory=_echo_input_factory,
        backend=backend,
    )
    job_id = await submitter.submit(
        flow_id=flow_id,
        request={
            "flow_id": str(flow_id),
            "mode": "background",
            "stream_protocol": "langflow",
            "input_value": "bound",
            "tweaks": {"Node-x": {"api_key": "bound-secret"}},  # pragma: allowlist secret
        },
        user=_StubUser(uuid4()),
    )
    job = await job_service.get_job_by_job_id(job_id)

    wrong_auth = settings_service.auth_settings.model_copy(
        update={"SECRET_KEY": SecretStr(Fernet.generate_key().decode())}
    )
    wrong_key_service = BackgroundExecutionService(
        settings_service=SimpleNamespace(settings=settings_service.settings, auth_settings=wrong_auth),
        frame_source_factory=_echo_input_factory,
    )
    with pytest.raises(RequestOverridesUnavailableError, match="Background request overrides are unavailable"):
        wrong_key_service._reconstruct_request(job)

    other_job_id = uuid4()
    await job_service.create_job(
        job_id=other_job_id,
        flow_id=uuid4(),
        user_id=uuid4(),
        initial_metadata=job.job_metadata,
    )
    other_job = await job_service.get_job_by_job_id(other_job_id)
    with pytest.raises(RequestOverridesUnavailableError, match="Background request overrides are unavailable"):
        submitter._reconstruct_request(other_job)

    null_metadata = dict(job.job_metadata)
    null_metadata["request_overrides"] = None
    await job_service.update_job_metadata(job_id, null_metadata, replace=True)
    null_job = await job_service.get_job_by_job_id(job_id)
    with pytest.raises(RequestOverridesUnavailableError, match="Background request overrides are unavailable"):
        submitter._reconstruct_request(null_job)


async def test_no_overrides_and_safe_legacy_rows_remain_replayable(real_services_job_service):
    """New empty envelopes and old rows without overrides preserve compatibility."""
    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    job_service = real_services_job_service
    backend = _RecordingBackend()
    flow_id = uuid4()
    request = {
        "flow_id": str(flow_id),
        "mode": "background",
        "stream_protocol": "langflow",
        "input_value": "no-overrides",
        # API model defaults: these must not create an envelope for an ordinary run.
        "globals": {},
        "tweaks": {},
    }
    svc = BackgroundExecutionService(
        settings_service=get_settings_service(), frame_source_factory=_echo_input_factory, backend=backend
    )
    job_id = await svc.submit(flow_id=flow_id, request=request, user=_StubUser(uuid4()))
    job = await job_service.get_job_by_job_id(job_id)
    assert "request_overrides_format" not in job.job_metadata
    assert "request_overrides" not in job.job_metadata
    safe_request = {key: value for key, value in request.items() if key not in {"globals", "tweaks"}}
    assert svc._reconstruct_request(job) == safe_request

    legacy_id = uuid4()
    legacy_request = {**safe_request, "globals": {}, "tweaks": {}}
    await job_service.create_job(
        job_id=legacy_id,
        flow_id=flow_id,
        user_id=uuid4(),
        initial_metadata={"request": legacy_request},
    )
    legacy = await job_service.get_job_by_job_id(legacy_id)
    assert svc._reconstruct_request(legacy) == safe_request


async def test_legacy_empty_overrides_restart_safely(real_services_job_service):
    """A queued pre-fix v2 row with empty override defaults remains recoverable."""
    import asyncio

    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    job_service = real_services_job_service
    flow_id, job_id = uuid4(), uuid4()
    safe_request = {
        "flow_id": str(flow_id),
        "mode": "background",
        "stream_protocol": "langflow",
        "input_value": "legacy-empty-restart",
    }
    await job_service.create_job(
        job_id=job_id,
        flow_id=flow_id,
        user_id=uuid4(),
        initial_metadata={"request": {**safe_request, "globals": {}, "tweaks": {}}},
    )

    captured: list[dict] = []
    restart = BackgroundExecutionService(
        settings_service=get_settings_service(),
        frame_source_factory=_capture_request_factory(captured),
    )
    await restart.start()
    try:
        await restart.sweep_orphans_on_startup()
        for _ in range(100):
            recovered = await job_service.get_job_by_job_id(job_id)
            if recovered.status in {JobStatus.COMPLETED, JobStatus.FAILED}:
                break
            await asyncio.sleep(0.05)
    finally:
        await restart.stop()

    assert captured.count(safe_request) == 1
    assert recovered.status == JobStatus.COMPLETED


async def test_legacy_plaintext_overrides_are_not_replayed(real_services_job_service):
    """A pre-fix plaintext override row cannot bypass the encrypted envelope contract."""
    from langflow.services.background_execution.service import (
        BackgroundExecutionService,
        RequestOverridesUnavailableError,
    )
    from langflow.services.deps import get_settings_service

    flow_id = uuid4()
    job_id = uuid4()
    request = {
        "flow_id": str(flow_id),
        "mode": "background",
        "stream_protocol": "langflow",
        "input_value": "legacy",
        "tweaks": {"Node-x": {"api_key": "legacy-plaintext-secret"}},  # pragma: allowlist secret
    }
    await real_services_job_service.create_job(
        job_id=job_id,
        flow_id=flow_id,
        user_id=uuid4(),
        initial_metadata={"request": request},
    )
    svc = BackgroundExecutionService(settings_service=get_settings_service(), frame_source_factory=_echo_input_factory)
    job = await real_services_job_service.get_job_by_job_id(job_id)
    with pytest.raises(RequestOverridesUnavailableError, match="Background request overrides are unavailable"):
        svc._reconstruct_request(job)


async def test_requeued_queued_job_replays_original_input(real_services_job_service):
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

    job_service = real_services_job_service
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


async def test_job_timeout_marks_timed_out(real_services_job_service):
    """A run that overruns ``background_job_timeout`` ends TIMED_OUT.

    The runner wraps the drive in ``asyncio.wait_for(timeout=...)``;
    ``execute_with_status`` maps ``asyncio.TimeoutError`` to TIMED_OUT. We use a
    scripted source that sleeps far longer than the short configured timeout, so
    the timeout fires deterministically without any LLM call. The durable log
    must carry a terminal milestone too. Real SQLite and real Postgres.
    """
    import asyncio

    job_service = real_services_job_service
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


async def test_events_reattach_after_restart_returns_on_terminal_job(real_services_job_service):
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

    job_service = real_services_job_service
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


async def test_events_replay_frames_are_sse_framed(real_services_job_service):
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

    job_service = real_services_job_service
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


async def test_executor_stop_applies_terminal_reconcile(real_services_job_service):
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

    job_service = real_services_job_service
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


async def test_stop_poll_only_on_durable_frames(real_services_job_service):
    """The runner polls the STOP signal only on DURABLE frames, not every token.

    Polling ``unconsumed_signals`` (a DB read) on every ephemeral token is wasted
    work — a stop is only honored at vertex/milestone boundaries anyway. We count
    real ``unconsumed_signals`` DB calls (a thin instrumented subclass that still
    hits the real DB) while driving a source with many ephemeral tokens and a few
    durable frames, and assert the poll count tracks the durable frames, not the
    token flood. Real SQLite and Postgres.
    """
    job_service = real_services_job_service
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


async def test_stop_signal_is_marked_consumed(real_services_job_service):
    """When the runner acts on a STOP, the signal row is stamped ``consumed_at``.

    Otherwise the execution_signals table grows unbounded and, worse, a
    re-enqueued job self-cancels off the stale STOP. We assert two things:
    (1) after a stopped run the STOP row has ``consumed_at`` set, and
    (2) a fresh run of the SAME job_id afterwards does NOT instantly cancel —
    it completes, because the stale STOP was consumed. Real SQLite and Postgres.
    """
    job_service = real_services_job_service
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


async def test_concurrent_sweep_runs_queued_job_exactly_once(real_services_job_service):
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

    job_service = real_services_job_service
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
