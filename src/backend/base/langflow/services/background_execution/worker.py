"""The ``langflow worker`` process: lease-claim jobs off the database and run them.

In the scaled backend the API process only persists QUEUED job rows; this
separate process claims them off the SAME database. On startup it reconciles
orphaned leases (``requeue_lost``), then loops: claim a job id (a poll that
sleeps out its block window so it can observe the stop event), run the runner,
release. The durable job row is the only queue state, so a runner crash leaves
nothing to clean up beyond what the watchdog already reconciles.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import random
import socket
from time import monotonic
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger

from langflow.services.background_execution.db_backend import _coerce_uuid
from langflow.services.background_execution.runner import JobRunner
from langflow.services.database.models.worker_registry.model import WorkerState

if TYPE_CHECKING:
    from collections.abc import Callable

    from lfx.services.settings.base import Settings


class WorkerJobRunner:
    """Run one durable job to terminal state inside a worker process.

    Given only a ``job_id``, this hydrates the persisted request + owner from the
    durable job row (exactly what ``submit`` stored under
    ``job_metadata['request']``), builds the SAME StreamAdapter + frame source the
    API would have used, and drives the SAME ``JobRunner``. Durable milestones
    land in ``job_events``, which any API replica's event tail reads.

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
        # Lazily-built facade instance: request reconstruction is an instance
        # method (it Fernet-decrypts the persisted request overrides), so the
        # worker reuses the facade's implementation instead of duplicating it.
        self._facade: Any = None

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

        if self._facade is None:
            from langflow.services.deps import get_settings_service

            self._facade = BackgroundExecutionService(settings_service=get_settings_service())
        request = self._facade._reconstruct_request(job)  # noqa: SLF001
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
        from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter

        protocol = request.get("stream_protocol", "langflow")
        return get_stream_adapter(
            protocol,
            StreamAdapterContext(
                run_id=str(job_id),
                thread_id=request.get("session_id") or str(flow_id),
                # ``submit`` persists the whole request body, so a worker narrows
                # the replayed stream exactly like the API process does. Legacy
                # rows written before the field existed default to today's
                # behavior. Without this the same run hides graph state in
                # default mode and exposes it in scaled mode.
                expose_graph_state=request.get("expose_graph_state", True),
            ),
        )


async def _watchdog_loop(
    backend: Any,
    *,
    stop_event: asyncio.Event,
    lease_ttl_s: float,
    interval_s: float,
) -> None:
    """Periodically reconcile orphaned leases until *stop_event* is set.

    This is the running watchdog the design calls for: a worker that died
    mid-run leaves a stale-lease IN_PROGRESS row, and under a steady fleet (no
    restarts) nothing else reconciles it. Running ``requeue_lost`` on an
    interval reaps it WITHOUT requiring a new worker process to boot. Each pass
    is best-effort so a transient error never kills the loop. QUEUED rows need
    no recovery pass: the durable row is the queue, so a stale-leased QUEUED
    row is directly re-claimable.
    """
    # Random initial offset so a fleet started together does not scan in
    # lockstep: every worker runs this loop, and without jitter their passes
    # converge into a synchronized full-table read burst every interval.
    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(stop_event.wait(), timeout=random.uniform(0, interval_s))  # noqa: S311
    while not stop_event.is_set():
        with contextlib.suppress(Exception):
            await backend.requeue_lost(lease_ttl_s=lease_ttl_s)
        try:
            # +/-25% jitter so ticks stay spread out instead of re-converging.
            await asyncio.wait_for(stop_event.wait(), timeout=interval_s * random.uniform(0.75, 1.25))  # noqa: S311
        except asyncio.TimeoutError:
            continue


async def _roster_beat(registry: Any, *, owner: str, state: WorkerState, current_job_id: Any) -> None:
    """Record this worker's presence and what it is doing. Best effort.

    Opens its own short-lived session: the claim loop holds none, and the roster
    write must not join a transaction that a long job would keep open. Failures
    are swallowed because fleet visibility must never break the claim loop, and
    the next beat supersedes a missed one anyway.
    """
    from langflow.services.deps import session_scope

    with contextlib.suppress(Exception):
        async with session_scope() as session:
            await registry.heartbeat(session, owner=owner, state=state, current_job_id=current_job_id)


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
    registry: Any = None,
    roster_interval_s: float | None = None,
) -> None:
    """Claim-and-run loop with a periodic lease watchdog. Returns on *stop_event*.

    Args:
        backend: object exposing requeue_lost(lease_ttl_s=) and claim(block_ms=).
        runner: object exposing run(job_id).
        stop_event: set by the signal handler for cooperative shutdown.
        idle_block_ms: how long claim() blocks waiting for work each iteration;
            kept short so the loop notices stop_event promptly.
        job_service: durable store; when set, the worker stamps a heartbeat on
            claim (so a just-claimed job's lease is fresh while it starts).
        owner: process-unique token stamped on the claim heartbeat.
        lease_ttl_s: lease window the watchdog uses to decide "dead".
        watchdog_interval_s: how often the periodic watchdog runs; None disables
            it (startup-only reconcile, the prior behaviour).
        registry: worker roster store; when set (with *owner*) this worker
            registers, beats while it lives, and deregisters on graceful stop,
            so the API-side collector can report the fleet.
        roster_interval_s: how often to beat while idle. Transitions between
            idle and busy always beat immediately, so this only bounds how long
            a steady state goes unrefreshed; it must stay below the roster's
            freshness window or a live idle worker would read as offline.
    """
    # Startup reconcile: requeue work lost by a previously-crashed worker.
    await backend.requeue_lost(lease_ttl_s=lease_ttl_s)

    roster = registry if (registry is not None and owner is not None) else None
    if roster is not None:
        from langflow.services.deps import session_scope

        with contextlib.suppress(Exception):
            async with session_scope() as session:
                await roster.register(session, owner=owner, pid=os.getpid(), host=socket.gethostname())
    # Force the first idle beat rather than waiting out an interval, so a worker
    # that starts into an empty queue still shows up as online promptly.
    last_beat = None

    watchdog_task: asyncio.Task | None = None
    if watchdog_interval_s is not None:
        watchdog_task = asyncio.create_task(
            _watchdog_loop(
                backend,
                stop_event=stop_event,
                lease_ttl_s=lease_ttl_s,
                interval_s=watchdog_interval_s,
            )
        )

    try:
        while not stop_event.is_set():
            job_id = await backend.claim(block_ms=idle_block_ms)
            if job_id is None:
                # Idle: refresh presence on the interval. Throttled because the
                # claim poll returns every idle_block_ms (1s by default) and the
                # roster does not need a write per second per worker.
                due = last_beat is None or monotonic() - last_beat >= (roster_interval_s or 0)
                if roster is not None and roster_interval_s is not None and due:
                    await _roster_beat(roster, owner=owner, state=WorkerState.IDLE, current_job_id=None)
                    last_beat = monotonic()
                # claim() sleeps out its block window on an empty queue, but a
                # backend that returns None promptly (error path, test double)
                # must not hot-spin — yield so the stop signal and other tasks run.
                await asyncio.sleep(0)
                continue
            # Stamp a heartbeat-on-claim so the lease is fresh the moment we own
            # the id: a sibling watchdog must not reap a job we just claimed but
            # have not yet flipped to IN_PROGRESS. Best-effort.
            if job_service is not None and owner is not None:
                with contextlib.suppress(Exception):
                    await job_service.heartbeat(_coerce_uuid(job_id), owner)
            if roster is not None:
                # A transition, so beat now instead of waiting out the interval:
                # the roster carries which job this worker holds, and that is
                # only useful while it still holds it.
                await _roster_beat(roster, owner=owner, state=WorkerState.BUSY, current_job_id=_coerce_uuid(job_id))
                last_beat = monotonic()
            try:
                await runner.run(job_id)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                # The durable job row + watchdog decide whether the work should
                # be retried; there is no separate lease to release — the row's
                # status and heartbeat are the only queue state.
                await logger.aexception(f"Worker: runner failed for job {job_id}: {exc}")
            finally:
                if roster is not None:
                    # Clear current_job_id as soon as the job is done, however it
                    # ended: a roster still naming a finished job reads as a
                    # worker stuck on it.
                    await _roster_beat(roster, owner=owner, state=WorkerState.IDLE, current_job_id=None)
                    last_beat = monotonic()
    finally:
        if watchdog_task is not None:
            watchdog_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await watchdog_task
        if roster is not None:
            # Graceful stop leaves no row behind, so the fleet count drops
            # immediately instead of waiting for this worker to age out.
            from langflow.services.deps import session_scope

            with contextlib.suppress(Exception):
                async with session_scope() as session:
                    await roster.deregister(session, owner=owner)


async def build_worker(*, owner: str | None = None):
    """Construct the DB backend, the WorkerJobRunner, and a teardown callable.

    Reads the live services (settings, jobs) so the worker process shares the
    same database as the API. Cross-replica visibility needs no live bus: every
    durable milestone lands in ``job_events``, which any API replica's event
    tail polls. The runner still publishes to an in-process bus so its close
    semantics (and any in-process subscriber) keep working. ``owner`` is the
    process-unique token the in-flight runner stamps on the job heartbeat.
    Returns ``(backend, runner, teardown)``.
    """
    from langflow.services.background_execution.db_backend import DBBackgroundQueue
    from langflow.services.background_execution.live_bus import InMemoryLiveBus
    from langflow.services.deps import get_job_service, get_settings_service

    settings = get_settings_service().settings
    job_service = get_job_service()

    backend = DBBackgroundQueue(
        job_service=job_service,
        owner=owner,
        lease_ttl_s=settings.background_lease_ttl_s,
        poll_interval_s=settings.background_poll_interval_s,
        claim_candidates=settings.background_claim_candidates,
    )
    runner = WorkerJobRunner(settings=settings, live_bus=InMemoryLiveBus(), owner=owner)

    async def teardown() -> None:
        """Nothing to close: the worker holds no broker connection."""

    return backend, runner, teardown
