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
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from filelock import FileLock, Timeout
from lfx.log.logger import logger

from langflow.services.background_execution.executor import InProcessExecutor
from langflow.services.background_execution.live_bus import InMemoryLiveBus, LiveFrame
from langflow.services.background_execution.runner import JobRunner
from langflow.services.base import Service
from langflow.services.database.models.jobs.model import JobStatus, JobType, SignalType
from langflow.services.deps import get_job_service
from langflow.services.jobs.exceptions import DuplicateJobError

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

# Durable statuses that mean the run is over. ``events()`` keys off these (not the
# process-local live bus) so a reattach to a finished job replays and returns
# instead of tailing a bus that will never produce another frame.
_TERMINAL_STATUSES = frozenset({JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.TIMED_OUT})


class BackgroundExecutionService(Service):
    name = "background_execution_service"

    def __init__(
        self,
        settings_service: SettingsService,
        *,
        frame_source_factory: FrameSourceFactory | None = None,
        backend: Any | None = None,
    ) -> None:
        self.settings_service = settings_service
        self._settings = settings_service.settings
        self._is_redis = self._settings.background_backend_is_scaled
        # Scaled backend: the redis claim queue + Streams live bus + DB replay.
        # When configured (redis), the API process only enqueues — a separate
        # ``langflow worker`` process drains the queue and runs the JobRunner.
        # Injected in tests; otherwise built lazily here from settings when the
        # scaled backend is configured. In the default (asyncio) path it stays
        # None and the in-process executor below runs jobs inside the API.
        if backend is None and self._is_redis:
            backend = self._build_scaled_backend()
        self._backend = backend
        self._executor = InProcessExecutor(max_concurrency=self._settings.background_max_concurrency)
        self._bus = InMemoryLiveBus()
        # Process-unique owner token stamped on the heartbeat of jobs this API
        # process runs in the default backend. Lets a liveness-aware sweep tell a
        # job this live process is running from a genuinely orphaned one.
        self._owner = f"api:{os.getpid()}:{uuid4().hex[:8]}"
        # Injected in tests; defaulted to the real build loop by the route wiring.
        self._frame_source_factory = frame_source_factory
        self.set_ready()

    @property
    def _scaled(self) -> bool:
        """True when a redis-backed scaled backend is wired behind this facade."""
        return self._backend is not None

    def _build_scaled_backend(self) -> Any:
        """Build the redis-backed scaled backend from settings.

        Reuses the worker's redis-client resolution (URL → host/port/db with the
        cache-redis fallbacks) so the API enqueues to the exact redis a worker
        drains, and ``select_background_backend`` so selection follows
        ``background_backend_is_scaled``. Returns None in the default path.
        """
        from langflow.services.background_execution.factory import select_background_backend
        from langflow.services.background_execution.worker import _build_redis_client
        from langflow.services.deps import get_job_service

        client = _build_redis_client(self._settings)
        return select_background_backend(self._settings, client=client, job_service=get_job_service())

    async def start(self) -> None:
        # Scaled mode: nothing to start in the API process — the worker process
        # owns execution. (No NotImplementedError: the redis backend is wired.)
        if self._scaled:
            return
        await self._executor.start()

    async def stop(self) -> None:
        await self._executor.stop()

    async def teardown(self) -> None:
        await self.stop()
        # Scaled mode: close the redis client this facade built for the backend so
        # the API replica does not leak its background-execution connection pool on
        # shutdown (the worker process closes its own client on teardown). Default
        # mode has no backend, so this is a no-op.
        backend = self._backend
        if backend is not None and hasattr(backend, "teardown"):
            await backend.teardown()

    # ------------------------------------------------------------------ submit

    async def submit(self, *, flow_id: UUID, request: dict[str, Any], user: UserRead) -> UUID:
        # Lazy-start the executor so the facade works whether or not the app
        # lifespan called start() first. start() is idempotent.
        await self.start()
        job_service = get_job_service()
        job_id = uuid4()
        dedupe_key = request.get("idempotency_key")
        try:
            await job_service.create_job(
                job_id=job_id,
                flow_id=flow_id,
                user_id=user.id,
                dedupe_key=dedupe_key,
            )
        except DuplicateJobError:
            # Idempotent retry: a non-terminal job already exists for this key,
            # so return that job_id instead of queuing duplicate work. Falls
            # through to a fresh submit only if the existing row vanished in the
            # race between create_job's check and this lookup.
            existing = await self._existing_job_for_dedupe(dedupe_key, user.id)
            if existing is not None:
                return existing
            raise
        # Persist the submit request on the job row so a QUEUED job that survives
        # a restart is re-enqueued with its ORIGINAL inputs (input_value, tweaks,
        # etc.), not a reconstructed default. The worker / startup sweep read it
        # back via ``_reconstruct_request``.
        #
        # Request-level ``globals`` are REDACTED from the persisted copy: they can
        # carry inline secrets (API keys), and storing them plaintext in the
        # durable ``job`` table (JSONB on Postgres) widens the blast radius of any
        # DB read (backup, ops access, a SQL-injection elsewhere) beyond the
        # live-only handling globals get on the sync path. Tradeoff: a background
        # re-enqueue after a restart drops inline globals — reference STORED global
        # variables by name for background runs rather than passing secrets inline.
        # The live in-memory run below still uses the full ``request``.
        await job_service.update_job_metadata(job_id, {"request": self._redact_request(request)})
        if self._scaled:
            # Scaled mode: hand the QUEUED job id to a worker via the redis claim
            # queue. The DB row stays the system of record; the API does NOT run
            # the flow. The worker hydrates the request from the job row.
            await self._backend.enqueue(str(job_id))
        else:
            await self._enqueue(job_id=job_id, flow_id=flow_id, request=request, user=user)
        return job_id

    @staticmethod
    def _redact_request(request: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of ``request`` with secret-bearing ``globals`` removed.

        Returns a shallow copy so the caller's dict (used for the live run) is not
        mutated. Only ``globals`` is dropped; everything else round-trips for a
        faithful replay. See ``submit`` for the durable-plaintext rationale and
        the inline-globals tradeoff.
        """
        if "globals" not in request:
            return request
        redacted = dict(request)
        redacted.pop("globals", None)
        return redacted

    @staticmethod
    async def _existing_job_for_dedupe(dedupe_key: str | None, user_id: UUID | None) -> UUID | None:
        """Return the active job_id sharing ``dedupe_key`` for this user, if any.

        Mirrors ``create_job``'s non-terminal set (QUEUED / IN_PROGRESS /
        COMPLETED) so a retried POST resolves to the same job a terminal job
        with the same key would not block (allowing a genuine re-run).
        """
        if dedupe_key is None:
            return None
        from sqlmodel import col, select

        from langflow.services.database.models.jobs.model import Job as JobModel
        from langflow.services.deps import session_scope

        async with session_scope() as session:
            stmt = (
                select(JobModel)
                .where(JobModel.dedupe_key == dedupe_key)
                .where(col(JobModel.status).in_([JobStatus.QUEUED, JobStatus.IN_PROGRESS, JobStatus.COMPLETED]))
            )
            if user_id is not None:
                stmt = stmt.where(JobModel.user_id == user_id)
            result = await session.exec(stmt)
            row = result.first()
            return row.job_id if row is not None else None

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
            job_timeout=self._settings.background_job_timeout,
            owner=self._owner,
            heartbeat_interval_s=self._settings.background_heartbeat_interval_s,
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
        job = await self._validate(job_id, user)
        job_service = get_job_service()
        last_seq = self._parse_last_event_id(last_event_id)
        # The durable replay must serialize with the SAME separators the live
        # adapter used (agui = compact, langflow = spaced) so replayed bytes are
        # byte-identical. The protocol is on the persisted submit request.
        protocol = self._job_protocol(job)

        async def read_durable(after_seq: int) -> list[LiveFrame]:
            rows = await job_service.read_events(job_id, after_seq=after_seq)
            return [LiveFrame(seq=r.seq, data=self._row_to_frame(r, protocol=protocol)) for r in rows]

        # Terminal jobs must be answered from the DURABLE log alone. The live bus
        # is process-local: after a restart it is fresh and its ``_closed`` marker
        # is empty, so ``reattach`` would replay durable rows then block forever on
        # ``while True: queue.get()`` waiting for a live tail that will never come.
        # Decide "finished" off the persisted status (the cross-restart source of
        # truth), replay, and return. The same holds cross-replica in scaled mode:
        # a terminal job has nothing live left on the redis Stream.
        if job.status in _TERMINAL_STATUSES:
            for frame in await read_durable(last_seq):
                yield frame.data
            return

        # Scaled mode: any API replica serves reattach by replaying durable
        # job_events (from the DB) then tailing the shared redis Stream. The
        # backend yields durable event rows (carry .seq) and live _StreamFrames
        # (payload is already SSE bytes the worker's RedisStreamLiveBus XADDed).
        if self._scaled:
            async for item in self._backend.events(str(job_id), last_event_id=last_seq):
                seq = getattr(item, "seq", None)
                if seq is not None:
                    # Durable milestone row — re-frame through the SSE formatter
                    # so replayed bytes match live frames (Last-Event-ID resume).
                    yield self._row_to_frame(item, protocol=protocol)
                else:
                    # Live ephemeral frame from the Stream tail — already framed.
                    yield item.payload
            return

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
        # Enforces ownership (raises PermissionError on a cross-user/unknown job).
        await self._validate(job_id, user)
        if self._scaled:
            # Scaled mode: the owning worker runs in another process. backend.stop
            # writes the durable STOP signal — the single source of truth the
            # worker's JobRunner polls at vertex boundaries. There is no pub/sub
            # fast-path (nothing in the worker subscribes to one), so stop latency
            # is one vertex-boundary poll, bounded by the run's durable cadence.
            await self._backend.stop(str(job_id))
            return
        job_service = get_job_service()
        # Always write the durable STOP signal — even when the row currently
        # reads a finished status. An in-flight runner can write its terminal
        # status (COMPLETED/FAILED) in the tiny window after stop_workflow flips
        # the row to CANCELLED but before this fetch; the runner's terminal
        # reconcile keys off this signal to force CANCELLED back over that
        # overwrite. Skipping the signal here is what let a racing FAILED win.
        await job_service.write_signal(job_id, SignalType.STOP)
        # Cancel the in-flight task for promptness; a no-op if it already ended.
        await self._executor.cancel(str(job_id))

    # ----------------------------------------------------------- startup sweep

    async def sweep_orphans_on_startup(self) -> None:
        """Reconcile jobs left mid-flight by a crashed process.

        Single-flight across workers: this runs in the per-worker lifespan on
        every uvicorn/gunicorn boot, so it is guarded by a file lock (the same
        primitive ``main.py`` uses for starter projects). Only ONE booting worker
        runs the IN_PROGRESS reconcile; the others skip it. The reconcile is also
        liveness-aware (``sweep_orphans`` only fails rows whose heartbeat is
        stale/absent), so even without the lock a booting worker can never flip a
        sibling's actively-running, freshly-heartbeated job FAILED.

        ``JobService.sweep_orphans`` does the durable reconcile (FAILED +
        worker_lost + terminal event). QUEUED workflow rows never started, so
        under at-least-once we re-enqueue them onto this worker's executor with a
        reconstructed request. Best-effort per job so one bad row can't block the
        rest. Redis backend reconciles via its own watchdog.
        """
        if self._is_redis:
            return
        await self.start()
        job_service = get_job_service()
        lease_ttl = self._settings.background_lease_ttl_s
        # Single-flight the IN_PROGRESS reconcile: only the worker that wins the
        # lock fails orphans; the others skip (a non-blocking try-acquire). The
        # QUEUED re-enqueue below stays per-worker because each row is lease-claimed
        # atomically (claim_queued_lease), so two workers cannot double-run it.
        lock_file = Path(tempfile.gettempdir()) / "langflow_bg_orphan_sweep.lock"
        lock = FileLock(lock_file, timeout=0)
        try:
            with lock:
                # Fail genuinely-orphaned IN_PROGRESS rows (stale/absent heartbeat).
                await job_service.sweep_orphans(lease_ttl_s=lease_ttl)
        except Timeout:
            # Another worker is running the reconcile; skip ours.
            await logger.adebug("Another worker is sweeping orphans, skipping")
        # Re-enqueue QUEUED workflow rows (at-least-once for not-yet-started work).
        # Each row is LEASE-claimed (single-flight) WITHOUT flipping it to
        # IN_PROGRESS, so two workers booting against the same DB cannot both
        # re-run it (only the claim whose rowcount==1 enqueues), AND a re-enqueue
        # that crashes before the runner starts leaves the row QUEUED and
        # re-runnable on the next boot rather than a stranded IN_PROGRESS the next
        # sweep would fail worker_lost. The runner's execute_with_status performs
        # the real QUEUED->IN_PROGRESS flip once it actually starts emitting.
        for job in await self._queued_workflow_jobs():
            if not await job_service.claim_queued_lease(job.job_id, owner=self._owner, lease_ttl_s=lease_ttl):
                continue
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
        """Rebuild the request dict for a re-enqueued QUEUED job.

        ``submit`` persists the original request body under
        ``job_metadata["request"]`` so re-enqueue replays the ORIGINAL inputs
        (input_value, tweaks, globals, files, partial-run ids, ...). Falls back
        to a minimal default only for legacy rows written before the request was
        persisted, so a pre-existing QUEUED job still re-runs rather than blocks.
        """
        meta = job.job_metadata or {}
        persisted = meta.get("request")
        if isinstance(persisted, dict) and persisted:
            return persisted
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

    @staticmethod
    def _job_protocol(job: Job) -> str:
        """The stream protocol the run used, read off the persisted submit request.

        ``submit`` persists the request (incl. ``stream_protocol``) under
        ``job_metadata['request']``. Replay needs it so it serializes durable
        rows with the SAME separators the live adapter used. Defaults to
        ``langflow`` for legacy rows written before the request was persisted.
        """
        meta = job.job_metadata or {}
        request = meta.get("request")
        if isinstance(request, dict):
            return request.get("stream_protocol") or "langflow"
        return meta.get("stream_protocol") or "langflow"

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
    def _row_to_frame(row: JobEvent, *, protocol: str = "langflow") -> bytes:
        # Re-frame the durable payload through the SAME SSE formatter the live
        # path uses (``format_sse_event(data_str=..., id=str(seq))``) so replayed
        # bytes are byte-compatible with live frames and a client's
        # ``Last-Event-ID`` resume works across the replay/tail boundary. The
        # live path passes the payload's JSON string as ``data_str``; ``seq`` is
        # the durable row seq, matching the live frame's ``id``.
        #
        # The JSON separators must match the LIVE adapter or the replayed bytes
        # are not byte-identical: the ``langflow`` adapter serializes via
        # ``json.dumps`` (default spaced separators) while the ``agui`` adapter
        # serializes via pydantic ``model_dump_json`` (compact separators). Pick
        # the matching separators by protocol so replay == live for both wires.
        from fastapi.sse import format_sse_event

        separators = (",", ":") if protocol == "agui" else None
        return format_sse_event(data_str=json.dumps(row.payload, separators=separators), id=str(row.seq))
