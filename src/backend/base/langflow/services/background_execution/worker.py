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


async def _roster_beat(
    *,
    owner: str,
    state: WorkerState,
    current_job_id: Any,
) -> None:
    """Record this worker's presence and what it is doing. Best effort.

    Opens its own short-lived session: the claim loop holds none, and the roster
    write must not join a transaction that a long job would keep open. Failures
    are swallowed because fleet visibility must never break the claim loop, and
    the next beat supersedes a missed one anyway.

    Callers hold ``_roster_writes`` across their read-then-write, so this does
    not take it: an ``asyncio.Lock`` is not reentrant.
    """
    from langflow.services.database.models.worker_registry.crud import heartbeat_worker
    from langflow.services.deps import session_scope

    with contextlib.suppress(Exception):
        async with session_scope() as session:
            await heartbeat_worker(
                session,
                owner=owner,
                state=state,
                current_job_id=current_job_id,
                pid=os.getpid(),
                host=socket.gethostname(),
            )


# Roster beats per online window. The collector counts a worker online for one
# window, so beating three times inside it tolerates the beat's own jitter plus
# a missed beat. Both sides derive from one setting, which is what keeps the
# relationship from depending on two knobs staying in step.
_ROSTER_BEATS_PER_WINDOW = 3.0


async def _roster_loop(
    *,
    owner: str,
    interval_s: float,
    stop_event: asyncio.Event,
    current_job: Callable[[], Any],
    lock: asyncio.Lock,
) -> None:
    """Refresh this worker's presence on an interval, whatever it is doing.

    Transitions beat immediately in the claim loop; this is what keeps a worker
    visible THROUGH a job. That matters because a background job routinely runs
    longer than the window the collector counts as online (the lease TTL), and
    without a beat during the run a worker reads as neither online nor busy for
    exactly as long as it is busy: zero workers on a saturated fleet.
    """
    while not stop_event.is_set():
        try:
            # Same jitter as the watchdog: a fleet started together must not
            # converge into one synchronized write burst every interval.
            await asyncio.wait_for(stop_event.wait(), timeout=interval_s * random.uniform(0.75, 1.25))  # noqa: S311
        except asyncio.TimeoutError:
            # Read and write under one lock. Reading outside it would let a
            # transition's beat be overtaken by this one still carrying the job
            # that just finished, leaving the roster naming a finished job.
            async with lock:
                job_id = current_job()
                state = WorkerState.IDLE if job_id is None else WorkerState.BUSY
                await _roster_beat(owner=owner, state=state, current_job_id=job_id)


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
    roster_enabled: bool = False,
    roster_interval_s: float = 15.0,
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
        roster_enabled: when true (and *owner* is set) this worker registers in
            the durable roster, refreshes it while it lives, and deregisters on
            graceful stop, so the API-side collector can report the fleet.
        roster_interval_s: how often to refresh presence. Not optional
            alongside *registry*: a roster that only beat on transitions would
            drop a worker out of the gauges for exactly as long as it was busy,
            which is what the refresh exists to prevent. Callers derive it from
            the same setting the collector uses as the online window.
    """
    # Startup reconcile: requeue work lost by a previously-crashed worker.
    await backend.requeue_lost(lease_ttl_s=lease_ttl_s)

    roster = roster_enabled and owner is not None
    current_job_id: Any = None
    roster_task: asyncio.Task | None = None
    # Serializes roster writes between the claim loop's transitions and the
    # periodic refresh, so the two cannot land out of order.
    roster_writes = asyncio.Lock()
    if roster:
        from langflow.services.database.models.worker_registry.crud import register_worker
        from langflow.services.deps import session_scope

        # register() writes a fresh IDLE row, so the worker is visible from the
        # moment it boots rather than from its first beat.
        with contextlib.suppress(Exception):
            async with session_scope() as session:
                await register_worker(session, owner=owner, pid=os.getpid(), host=socket.gethostname())
        roster_task = asyncio.create_task(
            _roster_loop(
                owner=owner,
                interval_s=roster_interval_s,
                stop_event=stop_event,
                current_job=lambda: current_job_id,
                lock=roster_writes,
            )
        )

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
                # No roster write here: _roster_loop refreshes presence on its
                # own interval, so the claim poll (every idle_block_ms, 1s by
                # default) does not turn into a write per second per worker.
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
            current_job_id = _coerce_uuid(job_id)
            if roster:
                # A transition, so beat now instead of waiting out the interval:
                # the roster carries which job this worker holds, and that is
                # only useful while it still holds it.
                async with roster_writes:
                    await _roster_beat(owner=owner, state=WorkerState.BUSY, current_job_id=current_job_id)
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
                current_job_id = None
                if roster:
                    # Clear current_job_id as soon as the job is done, however it
                    # ended: a roster still naming a finished job reads as a
                    # worker stuck on it.
                    async with roster_writes:
                        await _roster_beat(owner=owner, state=WorkerState.IDLE, current_job_id=None)
    finally:
        if watchdog_task is not None:
            watchdog_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await watchdog_task
        if roster_task is not None:
            roster_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await roster_task
        if roster:
            # Graceful stop leaves no row behind, so the fleet count drops
            # immediately instead of waiting for this worker to age out.
            from langflow.services.database.models.worker_registry.crud import deregister_worker
            from langflow.services.deps import session_scope

            with contextlib.suppress(Exception):
                async with session_scope() as session:
                    await deregister_worker(session, owner=owner)


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
