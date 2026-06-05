"""The ``langflow worker`` process: claim jobs off redis and run the JobRunner.

In the scaled backend the API process only enqueues; this separate process
drains the claim queue. On startup it reconciles orphaned leases
(``requeue_lost``), then loops: claim a job id (blocking pop with a timeout so it
can observe the stop event), run the runner, release the lease. A runner crash
still releases the lease so the id does not get stuck on the processing list —
the watchdog reconciles the durable job row separately.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import socket
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger

from langflow.services.background_execution.runner import JobRunner
from langflow.services.database.models.worker_registry.model import WorkerState
from langflow.services.deps import session_scope

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

    from lfx.services.settings.base import Settings

    from langflow.services.background_execution.worker_registry import WorkerRegistryService


class WorkerJobRunner:
    """Run one durable job to terminal state inside a worker process.

    Given only a ``job_id``, this hydrates the persisted request + owner from the
    durable job row (exactly what ``submit`` stored under
    ``job_metadata['request']``), builds the SAME StreamAdapter + frame source the
    API would have used, and drives the SAME ``JobRunner`` — but publishing live
    frames to the redis Streams bus so any API replica can reattach.

    The frame source factory is injected so tests can script a build; production
    passes the v1 build loop (``_default_frame_source_factory``).
    """

    def __init__(
        self,
        *,
        settings: Settings,
        live_bus: Any,
        frame_source_factory: Callable[..., Any] | None = None,
        owner: str | None = None,
    ) -> None:
        self._settings = settings
        self._live_bus = live_bus
        self._frame_source_factory = frame_source_factory
        # Process-unique token the in-flight JobRunner stamps on the heartbeat so
        # the periodic watchdog can tell this live run from a dead worker's.
        self._owner = owner

    def _resolve_frame_source_factory(self) -> Callable[..., Any]:
        if self._frame_source_factory is not None:
            return self._frame_source_factory
        # Default to the v1 build loop binding used by the API path.
        from langflow.api.v2.workflow import _default_frame_source_factory

        return _default_frame_source_factory

    async def run(self, job_id: str) -> None:
        """Hydrate the durable job and drive it to a terminal state."""
        from uuid import UUID

        from langflow.services.background_execution.service import BackgroundExecutionService
        from langflow.services.deps import get_job_service

        job_uuid = job_id if isinstance(job_id, UUID) else UUID(job_id)
        job_service = get_job_service()
        job = await job_service.get_job_by_job_id(job_uuid)
        if job is None:
            await logger.aerror(f"Worker: job {job_id} not found; skipping")
            return

        request = BackgroundExecutionService._reconstruct_request(job)  # noqa: SLF001
        user = BackgroundExecutionService._user_stub(job.user_id)  # noqa: SLF001
        adapter = self._build_adapter(request, job_uuid, job.flow_id)
        factory = self._resolve_frame_source_factory()
        source = factory(request=request, flow_id=job.flow_id, user=user, adapter=adapter)

        runner = JobRunner(
            job_service=job_service,
            live_bus=self._live_bus,
            adapter=adapter,
            frame_source=source,
            job_timeout=self._settings.background_job_timeout,
            owner=self._owner,
            heartbeat_interval_s=self._settings.background_heartbeat_interval_s,
        )
        await runner.run(job_id=job_uuid, source_kwargs={"job_id": job_uuid})

    @staticmethod
    def _build_adapter(request: dict[str, Any], job_id: Any, flow_id: Any) -> Any:
        from langflow.api.v2.adapters import StreamAdapterContext, get_stream_adapter

        protocol = request.get("stream_protocol", "langflow")
        return get_stream_adapter(
            protocol,
            StreamAdapterContext(
                run_id=str(job_id),
                thread_id=request.get("session_id") or str(flow_id),
            ),
        )


async def _watchdog_loop(
    backend: Any,
    job_service: Any,
    *,
    stop_event: asyncio.Event,
    lease_ttl_s: float,
    interval_s: float,
) -> None:
    """Periodically reconcile orphaned leases until *stop_event* is set.

    This is the running watchdog the design calls for: a worker that died
    mid-run leaves a stale-lease id on the processing list, and under a steady
    fleet (no restarts) nothing else reconciles it. Running ``requeue_lost`` on
    an interval reaps it WITHOUT requiring a new worker process to boot. Each
    pass is best-effort so a transient error never kills the loop. When a DB is
    wired (``job_service``), it also re-enqueues QUEUED rows stranded off redis.
    """
    while not stop_event.is_set():
        with contextlib.suppress(Exception):
            await backend.requeue_lost(lease_ttl_s=lease_ttl_s)
            if job_service is not None:
                await _recover_stranded_queued(backend)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_s)
        except asyncio.TimeoutError:
            continue


async def _recover_stranded_queued(backend: Any) -> None:
    """Re-enqueue QUEUED workflow rows that are on neither redis list.

    Covers the API-crash window between persisting a QUEUED row and the LPUSH:
    such a row is invisible to ``requeue_lost`` (it only scans the processing
    list). Each row is claimed atomically so two workers cannot double-enqueue.
    The backend's claim guard only re-pushes ids that truly are not already
    pending/processing.
    """
    recover = getattr(backend, "recover_stranded_queued", None)
    if recover is None:
        return
    await recover()


class _WorkerPresence:
    """Mutable presence state shared between the claim loop and its heartbeat task.

    The claim loop flips ``state`` + ``current_job_id`` event-driven (BUSY on claim,
    IDLE on complete) and writes an immediate registry beat each transition for a
    snappy roster; the periodic ``_registry_heartbeat_loop`` reads this same state
    and refreshes ``last_heartbeat`` on the interval, so the row stays fresh during a
    long job (it runs while ``runner.run`` awaits) and while idle.
    """

    def __init__(self) -> None:
        self.state: WorkerState = WorkerState.IDLE
        self.current_job_id: UUID | None = None


async def _write_registry_heartbeat(
    worker_registry: WorkerRegistryService,
    owner: str,
    presence: _WorkerPresence,
) -> None:
    """Write one registry heartbeat for the current presence. Best-effort.

    Opens a short-lived ``session_scope()`` per call — the same mechanism the loop
    uses for the job heartbeat — because ``WorkerRegistryService`` takes the session
    positionally and never opens its own. A DB hiccup must never kill the loop, so
    the write is guarded.
    """
    try:
        async with session_scope() as session:
            await worker_registry.heartbeat(
                session,
                owner=owner,
                state=presence.state,
                current_job_id=presence.current_job_id,
            )
    except Exception as exc:  # noqa: BLE001
        await logger.adebug(f"Worker registry heartbeat failed for {owner}: {exc}")


async def _registry_heartbeat_loop(
    worker_registry: WorkerRegistryService,
    owner: str,
    presence: _WorkerPresence,
    *,
    interval_s: float,
) -> None:
    """Refresh ``last_heartbeat`` every ``interval_s`` until cancelled.

    Mirrors the runner's ``_start_heartbeat``: it keeps the row fresh during a long
    job (this task runs while the loop is blocked in ``await runner.run``) and during
    idle. Cancelled by the loop's ``finally``.
    """
    while True:
        await asyncio.sleep(interval_s)
        await _write_registry_heartbeat(worker_registry, owner, presence)


async def run_worker_loop(
    backend: Any,
    runner: Any,
    *,
    stop_event: asyncio.Event,
    idle_block_ms: int = 1000,
    job_service: Any = None,
    owner: str | None = None,
    lease_ttl_s: float = 45.0,
    watchdog_interval_s: float | None = None,
    worker_registry: WorkerRegistryService | None = None,
    pid: int | None = None,
    host: str | None = None,
    registry_interval_s: float = 10.0,
) -> None:
    """Claim-and-run loop with a periodic lease watchdog. Returns on *stop_event*.

    Args:
        backend: object exposing requeue_lost(lease_ttl_s=), claim(block_ms=),
            complete(id), and (optionally) recover_stranded_queued().
        runner: object exposing run(job_id).
        stop_event: set by the signal handler for cooperative shutdown.
        idle_block_ms: how long claim() blocks waiting for work each iteration;
            kept short so the loop notices stop_event promptly.
        job_service: durable store; when set, the worker stamps a heartbeat on
            claim (so a just-claimed job's lease is fresh while it starts) and
            the watchdog also recovers QUEUED rows stranded off redis.
        owner: process-unique token stamped on the claim heartbeat.
        lease_ttl_s: lease window the watchdog uses to decide "dead".
        watchdog_interval_s: how often the periodic watchdog runs; None disables
            it (startup-only reconcile, the prior behaviour).
        worker_registry: durable presence roster; when set (with ``owner``) the
            worker registers an IDLE row before the loop, flips it BUSY/IDLE on
            claim/complete, beats ``last_heartbeat`` on ``registry_interval_s``, and
            deregisters in the finally so a cleanly-stopped worker disappears.
        pid: process id stored on the registry row (computed at the entrypoint so
            tests can inject it).
        host: hostname stored on the registry row (computed at the entrypoint).
        registry_interval_s: how often the periodic registry heartbeat refreshes
            ``last_heartbeat`` (idle or busy). Defaults to the settings value.
    """
    # Startup reconcile: requeue work lost by a previously-crashed worker.
    await backend.requeue_lost(lease_ttl_s=lease_ttl_s)
    if job_service is not None:
        with contextlib.suppress(Exception):
            await _recover_stranded_queued(backend)

    # Durable presence: register an IDLE row BEFORE any heartbeat so the
    # recreate-on-missing branch in the service stays dead, then keep it fresh on
    # the interval and flip it event-driven on claim/complete.
    registry_active = worker_registry is not None and owner is not None
    presence = _WorkerPresence()
    if registry_active:
        try:
            async with session_scope() as session:
                await worker_registry.register(
                    session,
                    owner=owner,
                    pid=pid if pid is not None else os.getpid(),
                    host=host if host is not None else socket.gethostname(),
                )
        except Exception as exc:  # noqa: BLE001
            await logger.awarning(f"Worker registry register failed for {owner}; not in roster: {exc}")

    watchdog_task: asyncio.Task | None = None
    if watchdog_interval_s is not None:
        watchdog_task = asyncio.create_task(
            _watchdog_loop(
                backend,
                job_service,
                stop_event=stop_event,
                lease_ttl_s=lease_ttl_s,
                interval_s=watchdog_interval_s,
            )
        )

    registry_heartbeat_task: asyncio.Task | None = None
    if registry_active:
        registry_heartbeat_task = asyncio.create_task(
            _registry_heartbeat_loop(
                worker_registry,
                owner,
                presence,
                interval_s=registry_interval_s,
            )
        )

    try:
        while not stop_event.is_set():
            job_id = await backend.claim(block_ms=idle_block_ms)
            if job_id is None:
                # claim() blocks up to idle_block_ms on a real redis, but a backend
                # that returns None promptly (empty queue, error path, test double)
                # must not hot-spin — yield so the stop signal and other tasks run.
                await asyncio.sleep(0)
                continue
            # Stamp a heartbeat-on-claim so the lease is fresh the moment we own
            # the id: a sibling watchdog must not reap a job we just claimed but
            # have not yet flipped to IN_PROGRESS. Best-effort.
            if job_service is not None and owner is not None:
                with contextlib.suppress(Exception):
                    await job_service.heartbeat(_coerce_uuid(job_id), owner)
            # Flip the roster to BUSY with the claimed id and write an immediate beat
            # so the roster reflects the transition without waiting for the interval.
            if registry_active:
                presence.state = WorkerState.BUSY
                presence.current_job_id = _coerce_uuid(job_id)
                await _write_registry_heartbeat(worker_registry, owner, presence)
            try:
                await runner.run(job_id)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                await logger.aexception(f"Worker: runner failed for job {job_id}: {exc}")
            finally:
                # Always release the lease — the durable job row + watchdog decide
                # whether the work should be retried; a stuck processing-list entry
                # would block reconcile forever.
                await backend.complete(job_id)
                # Back to IDLE on the roster with an immediate beat for a snappy view.
                if registry_active:
                    presence.state = WorkerState.IDLE
                    presence.current_job_id = None
                    await _write_registry_heartbeat(worker_registry, owner, presence)
    finally:
        if watchdog_task is not None:
            watchdog_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await watchdog_task
        if registry_heartbeat_task is not None:
            registry_heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await registry_heartbeat_task
        # Graceful stop deletes the row so the worker disappears from the roster
        # immediately. Runs on the normal stop path AND on a signal-driven stop
        # (the loop reaches this finally either way). Best-effort.
        if registry_active:
            try:
                async with session_scope() as session:
                    await worker_registry.deregister(session, owner=owner)
            except Exception as exc:  # noqa: BLE001
                await logger.awarning(f"Worker registry deregister failed for {owner}; stale row will linger: {exc}")


def _coerce_uuid(job_id: Any) -> Any:
    from uuid import UUID

    if isinstance(job_id, UUID):
        return job_id
    with contextlib.suppress(ValueError, AttributeError, TypeError):
        return UUID(job_id)
    return job_id


def _build_redis_client(settings: Settings) -> Any:
    """Construct a StrictRedis client for the job queue, mirroring RedisJobQueueService.

    URL wins; otherwise host/port fall back to the cache redis settings and the
    job-queue DB (default 1). The worker shares this exact resolution so its
    claim queue + Streams bus point at the same redis the API enqueues to.
    """
    from redis.asyncio import StrictRedis

    if settings.redis_queue_url:
        return StrictRedis.from_url(settings.redis_queue_url)
    host = settings.redis_queue_host or settings.redis_host
    port = settings.redis_queue_port or settings.redis_port
    return StrictRedis(host=host, port=port, db=settings.redis_queue_db)


async def build_worker(*, owner: str | None = None):
    """Construct the redis backend, the WorkerJobRunner, and a teardown callable.

    Reads the live services (settings, jobs, redis client) so the worker process
    shares the same configuration as the API. The runner publishes live frames to
    the redis Streams bus (RedisStreamLiveBus) so any API replica can reattach.
    ``owner`` is the process-unique token the in-flight runner stamps on the job
    heartbeat. Returns ``(backend, runner, teardown)``.
    """
    from langflow.services.background_execution.redis_backend import RedisBackgroundQueue
    from langflow.services.background_execution.redis_live_bus import RedisStreamLiveBus
    from langflow.services.deps import get_job_service, get_settings_service

    settings = get_settings_service().settings
    client = _build_redis_client(settings)
    job_service = get_job_service()

    backend = RedisBackgroundQueue(
        client=client,
        job_service=job_service,
        stream_ttl=settings.redis_queue_ttl,
        startup_grace_s=settings.redis_queue_startup_grace_s,
    )
    live_bus = RedisStreamLiveBus(client, ttl=settings.redis_queue_ttl)
    runner = WorkerJobRunner(settings=settings, live_bus=live_bus, owner=owner)

    async def teardown() -> None:
        await client.aclose()

    return backend, runner, teardown
