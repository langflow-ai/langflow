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
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger

from langflow.services.background_execution.runner import JobRunner

if TYPE_CHECKING:
    from collections.abc import Callable

    from lfx.services.settings.base import Settings


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
    ) -> None:
        self._settings = settings
        self._live_bus = live_bus
        self._frame_source_factory = frame_source_factory

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


async def run_worker_loop(
    backend: Any,
    runner: Any,
    *,
    stop_event: asyncio.Event,
    idle_block_ms: int = 1000,
) -> None:
    """Claim-and-run loop. Returns when *stop_event* is set.

    Args:
        backend: object exposing requeue_lost(), claim(block_ms=), complete(id).
        runner: object exposing run(job_id).
        stop_event: set by the signal handler for cooperative shutdown.
        idle_block_ms: how long claim() blocks waiting for work each iteration;
            kept short so the loop notices stop_event promptly.
    """
    # Startup reconcile: requeue work lost by a previously-crashed worker.
    await backend.requeue_lost()

    while not stop_event.is_set():
        job_id = await backend.claim(block_ms=idle_block_ms)
        if job_id is None:
            # claim() blocks up to idle_block_ms on a real redis, but a backend
            # that returns None promptly (empty queue, error path, test double)
            # must not hot-spin — yield so the stop signal and other tasks run.
            await asyncio.sleep(0)
            continue
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


async def build_worker():
    """Construct the redis backend, the WorkerJobRunner, and a teardown callable.

    Reads the live services (settings, jobs, redis client) so the worker process
    shares the same configuration as the API. The runner publishes live frames to
    the redis Streams bus (RedisStreamLiveBus) so any API replica can reattach.
    Returns ``(backend, runner, teardown)``.
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
    runner = WorkerJobRunner(settings=settings, live_bus=live_bus)

    async def teardown() -> None:
        await client.aclose()

    return backend, runner, teardown
