"""BackgroundExecutionService: the facade over the background-run primitives.

Composes the existing durable store (``JobService``) with the in-process
executor, the in-memory live bus, and the per-job runner. Methods:

* ``submit(flow_id, request, user) -> job_id``
* ``events(job_id, last_event_id, user) -> AsyncIterator[bytes]``
* ``status(job_id, user)`` / ``result(job_id, user)``
* ``stop_job(job_id, user)``

Backend selection follows ``settings.job_queue_type``: ``asyncio`` (default)
uses the in-process executor + in-memory bus implemented here; ``redis``
raises ``NotImplementedError`` until Phase 3 wires the scaled backend behind
these same methods.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from langflow.services.background_execution.executor import InProcessExecutor
from langflow.services.background_execution.live_bus import InMemoryLiveBus, LiveFrame
from langflow.services.background_execution.runner import JobRunner
from langflow.services.base import Service
from langflow.services.database.models.jobs.model import JobStatus, JobType, SignalType
from langflow.services.deps import get_job_service

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from lfx.services.settings.service import SettingsService

    from langflow.services.database.models.jobs.model import Job, JobEvent
    from langflow.services.database.models.user.model import UserRead

# A frame-source factory returns the async-generator callable the runner drives.
# Default wiring (Task 2.7) returns ``_stream_event_frames`` bound to the run's
# adapter + flow; tests inject a scripted generator.
FrameSourceFactory = Callable[..., Any]

# Statuses where the run has genuinely finished, so a STOP is pointless.
# CANCELLED is intentionally excluded: ``stop_workflow`` flips the row to
# CANCELLED before calling ``stop_job``, but the in-flight runner may still be
# racing to COMPLETED — we must still write the STOP signal and cancel the task.
_FINISHED_STATUSES = {
    JobStatus.COMPLETED,
    JobStatus.FAILED,
    JobStatus.TIMED_OUT,
}


class BackgroundExecutionService(Service):
    name = "background_execution_service"

    def __init__(
        self,
        settings_service: SettingsService,
        *,
        frame_source_factory: FrameSourceFactory | None = None,
    ) -> None:
        self.settings_service = settings_service
        self._settings = settings_service.settings
        self._is_redis = self._settings.job_queue_type == "redis"
        self._executor = InProcessExecutor(max_concurrency=self._settings.background_max_concurrency)
        self._bus = InMemoryLiveBus()
        # Injected in tests; defaulted to the real build loop by the route wiring.
        self._frame_source_factory = frame_source_factory
        self.set_ready()

    async def start(self) -> None:
        if self._is_redis:
            # Phase 3 fills this in (redis queue + worker process + streams bus).
            msg = "Redis background backend is not implemented yet (Phase 3)."
            raise NotImplementedError(msg)
        await self._executor.start()

    async def stop(self) -> None:
        await self._executor.stop()

    async def teardown(self) -> None:
        await self.stop()

    # ------------------------------------------------------------------ submit

    async def submit(self, *, flow_id: UUID, request: dict[str, Any], user: UserRead) -> UUID:
        # Lazy-start the executor so the facade works whether or not the app
        # lifespan called start() first. start() is idempotent.
        await self.start()
        job_service = get_job_service()
        job_id = uuid4()
        dedupe_key = request.get("idempotency_key")
        await job_service.create_job(
            job_id=job_id,
            flow_id=flow_id,
            user_id=user.id,
            dedupe_key=dedupe_key,
        )
        await self._enqueue(job_id=job_id, flow_id=flow_id, request=request, user=user)
        return job_id

    async def _enqueue(self, *, job_id: UUID, flow_id: UUID, request: dict[str, Any], user: UserRead | None) -> None:
        """Build a runner for the job and submit it to the in-process executor."""
        job_service = get_job_service()
        adapter = self._build_adapter(request, job_id, flow_id)
        source = self._frame_source_factory(request=request, flow_id=flow_id, user=user, adapter=adapter)
        runner = JobRunner(
            job_service=job_service,
            live_bus=self._bus,
            adapter=adapter,
            frame_source=source,
        )

        async def _coro() -> None:
            # job_id reaches the frame source via source_kwargs so the default
            # build-loop source can tag its memory-base hook with the run's job.
            await runner.run(job_id=job_id, source_kwargs={"job_id": job_id})

        await self._executor.submit(str(job_id), _coro)

    # ------------------------------------------------------------------ events

    async def events(
        self,
        job_id: UUID,
        last_event_id: str | None,
        user: UserRead,
    ) -> AsyncIterator[bytes]:
        await self._validate(job_id, user)
        job_service = get_job_service()
        last_seq = self._parse_last_event_id(last_event_id)

        async def read_durable(after_seq: int) -> list[LiveFrame]:
            rows = await job_service.read_events(job_id, after_seq=after_seq)
            return [LiveFrame(seq=r.seq, data=self._row_to_frame(r)) for r in rows]

        async for frame in self._bus.reattach(str(job_id), last_seq=last_seq, read_durable=read_durable):
            yield frame.data

    # ------------------------------------------------------------------ status

    async def status(self, job_id: UUID, user: UserRead) -> dict[str, Any]:
        job = await self._validate(job_id, user)
        payload: dict[str, Any] = {
            "job_id": str(job.job_id),
            "flow_id": str(job.flow_id),
            "status": job.status,
        }
        # Surface durable result/error additively.
        if job.result is not None:
            payload["result"] = job.result
        if job.error is not None:
            payload["error"] = job.error
        return payload

    async def result(self, job_id: UUID, user: UserRead) -> Any:
        job = await self._validate(job_id, user)
        return job.result

    # -------------------------------------------------------------------- stop

    async def stop_job(self, job_id: UUID, user: UserRead) -> None:
        job = await self._validate(job_id, user)
        if job.status in _FINISHED_STATUSES:
            return
        job_service = get_job_service()
        # Durable STOP so the runner's boundary poll (and its terminal reconcile)
        # sees the stop even if the in-flight task cancel races; then cancel the
        # local task for promptness. Written even when the row is already
        # CANCELLED because the runner may still be mid-flight racing to
        # COMPLETED — the durable STOP is what makes the reconcile win.
        await job_service.write_signal(job_id, SignalType.STOP)
        await self._executor.cancel(str(job_id))

    # ----------------------------------------------------------- startup sweep

    async def sweep_orphans_on_startup(self) -> None:
        """Reconcile jobs left mid-flight by a crashed process.

        ``JobService.sweep_orphans`` does the durable reconcile (it marks
        orphaned IN_PROGRESS rows FAILED with ``{type: worker_lost}`` and writes
        a terminal event). QUEUED workflow rows never started, so under
        at-least-once we re-enqueue them onto this worker's executor with a
        reconstructed request. Best-effort per job so one bad row can't block
        the rest. Redis backend reconciles via its own watchdog (Phase 3).
        """
        if self._is_redis:
            return
        await self.start()
        job_service = get_job_service()
        # Fail orphaned IN_PROGRESS rows (at-most-once for in-flight work).
        await job_service.sweep_orphans()
        # Re-enqueue QUEUED workflow rows (at-least-once for not-yet-started work).
        for job in await self._queued_workflow_jobs():
            request_dict = self._reconstruct_request(job)
            user = self._user_stub(job.user_id)
            with contextlib.suppress(Exception):
                await self._enqueue(
                    job_id=job.job_id,
                    flow_id=job.flow_id,
                    request=request_dict,
                    user=user,
                )

    @staticmethod
    async def _queued_workflow_jobs() -> list[Job]:
        from sqlmodel import select

        from langflow.services.database.models.jobs.model import Job as JobModel
        from langflow.services.deps import session_scope

        async with session_scope() as session:
            stmt = select(JobModel).where(
                JobModel.status == JobStatus.QUEUED,
                JobModel.type == JobType.WORKFLOW,
            )
            result = await session.exec(stmt)
            return list(result.all())

    @staticmethod
    def _reconstruct_request(job: Job) -> dict[str, Any]:
        """Rebuild the minimal request dict for a re-enqueued QUEUED job.

        The original request body is not persisted on the job row, so re-enqueue
        runs with defaults (langflow protocol, no chat input). ``job_metadata``
        may carry the original protocol/session if a future task persists it.
        """
        meta = job.job_metadata or {}
        return {
            "flow_id": str(job.flow_id),
            "mode": "background",
            "stream_protocol": meta.get("stream_protocol", "langflow"),
            "session_id": meta.get("session_id"),
            "input_value": meta.get("input_value", ""),
        }

    @staticmethod
    def _user_stub(user_id: UUID | None) -> UserRead | None:
        """A minimal UserRead carrying only ``id``.

        The default frame source only reads ``user.id`` (to fetch the flow), so
        a partial object is sufficient. Returns None for legacy ownerless jobs.
        """
        if user_id is None:
            return None
        from langflow.services.database.models.user.model import UserRead

        return UserRead.model_construct(id=user_id)

    # ----------------------------------------------------------------- helpers

    async def _validate(self, job_id: UUID, user: UserRead) -> Job:
        job_service = get_job_service()
        try:
            job = await job_service._validate_ownership(job_id, user.id)  # noqa: SLF001
        except ValueError as exc:
            raise PermissionError(str(exc)) from exc
        if job.type != JobType.WORKFLOW:
            msg = f"Job {job_id} is not a workflow job"
            raise PermissionError(msg)
        return job

    def _build_adapter(self, request: dict[str, Any], job_id: UUID, flow_id: UUID):
        from langflow.api.v2.adapters import StreamAdapterContext, get_stream_adapter

        protocol = request.get("stream_protocol", "langflow")
        return get_stream_adapter(
            protocol,
            StreamAdapterContext(
                run_id=str(job_id),
                thread_id=request.get("session_id") or str(flow_id),
            ),
        )

    @staticmethod
    def _parse_last_event_id(last_event_id: str | None) -> int:
        if not last_event_id:
            return 0
        try:
            return int(last_event_id)
        except ValueError:
            return 0

    @staticmethod
    def _row_to_frame(row: JobEvent) -> bytes:
        # Re-frame the durable payload as the same JSON-shaped bytes a live
        # subscriber would receive. ``payload`` is the {"event","data"} object.
        return json.dumps(row.payload).encode("utf-8")
