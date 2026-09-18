"""Default backend: run background jobs inside the API process.

The facade used to special-case "no backend" with ``if self._scaled:`` branches;
this class is that default path as a first-class ``BackgroundBackend``, so the
facade makes the same polymorphic calls in both modes and a future broker
backend slots in without threading a new boolean through every method.

Execution rides the facade-owned ``InProcessExecutor`` and ``InMemoryLiveBus``
(constructed once per facade and shared with this backend), so behavior is
byte-identical to the old inline path: ``dispatch`` builds the same JobRunner,
``stop`` writes the same durable STOP signal before cancelling the local task,
and ``tail`` is the same bus reattach with durable replay.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from langflow.services.background_execution.db_backend import _TAIL_END_STATUSES
from langflow.services.background_execution.runner import JobRunner
from langflow.services.database.models.jobs.model import SignalType

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable
    from uuid import UUID


class InProcessBackend:
    """Run jobs on the API's own executor; live events ride the in-memory bus."""

    # The API process runs the jobs itself: startup orphan recovery must
    # re-enqueue QUEUED rows here, unlike scaled mode where workers claim them.
    external_workers = False

    def __init__(
        self,
        *,
        executor: Any,
        bus: Any,
        settings: Any,
        owner: str | None,
        get_frame_source_factory: Callable[[], Any],
    ) -> None:
        self._executor = executor
        self._bus = bus
        self._settings = settings
        self._owner = owner
        # Read through a getter: the v2 routes late-bind the facade's
        # frame_source_factory after service construction.
        self._get_frame_source_factory = get_frame_source_factory

    async def start(self) -> None:
        await self._executor.start()

    async def teardown(self) -> None:
        await self._executor.stop()

    # ------------------------------------------------------------------ queue

    async def enqueue(self, job_id: str) -> None:
        """No-op: in-process work is dispatched with the full request via ``dispatch``."""

    async def claim(self, *, block_ms: int = 1000) -> str | None:
        """In-process jobs are never claimed; sleep out the window like an empty queue."""
        await asyncio.sleep(max(block_ms, 0) / 1000.0)
        return None

    async def dispatch(self, job_id: UUID, *, flow_id: UUID, request: dict[str, Any], user: Any) -> None:
        """Build a runner for the job and submit it to the in-process executor."""
        from langflow.services.deps import get_job_service

        job_service = get_job_service()
        adapter = self._build_adapter(request, job_id, flow_id)
        source = self._get_frame_source_factory()(request=request, flow_id=flow_id, user=user, adapter=adapter)
        runner = JobRunner(
            job_service=job_service,
            live_bus=self._bus,
            adapter=adapter,
            frame_source=source,
            job_timeout=self._settings.background_job_timeout,
            owner=self._owner,
            heartbeat_interval_s=self._settings.background_heartbeat_interval_s,
            input_deadline_s=self._settings.background_input_deadline_s,
        )

        async def _coro() -> None:
            # job_id reaches the frame source via source_kwargs so the default
            # build-loop source can tag its memory-base hook with the run's job.
            await runner.run(job_id=job_id, source_kwargs={"job_id": job_id})

        await self._executor.submit(str(job_id), _coro)

    async def hand_back(self, job_id: UUID, *, flow_id: UUID, request: dict[str, Any], user: Any, owner: str) -> bool:  # noqa: ARG002
        """Resume hand-off: in-process mode re-runs the job right here."""
        await self.dispatch(job_id, flow_id=flow_id, request=request, user=user)
        return True

    # ---------------------------------------------------------------- control

    async def stop(self, job_id: str) -> None:
        """Durable STOP first (survives restarts), then cancel the local task."""
        from uuid import UUID

        from langflow.services.deps import get_job_service

        await get_job_service().write_signal(UUID(job_id), SignalType.STOP)
        await self._executor.cancel(job_id)

    async def requeue_lost(self, *, lease_ttl_s: float = 45.0) -> list[str]:  # noqa: ARG002
        """No worker fleet to reconcile: the startup sweep owns orphan recovery."""
        return []

    # ------------------------------------------------------------- event tail

    async def tail(self, job_id: str, *, last_seq: int, frame_row: Callable[[Any], bytes]) -> AsyncIterator[bytes]:
        """Replay durable rows then follow the live in-memory bus."""
        from uuid import UUID

        from langflow.services.background_execution.live_bus import LiveFrame
        from langflow.services.deps import get_job_service

        job_service = get_job_service()
        durable_id = UUID(job_id)

        async def read_durable(after_seq: int) -> list[LiveFrame]:
            rows = await job_service.read_events(durable_id, after_seq=after_seq)
            return [LiveFrame(seq=r.seq, data=frame_row(r)) for r in rows]

        async def _is_done() -> bool:
            # SUSPENDED ends the tail too: a run that connected while IN_PROGRESS
            # and then suspended has no live tail to wait on.
            current = await job_service.get_job_by_job_id(durable_id)
            return current is not None and current.status in _TAIL_END_STATUSES

        async for frame in self._bus.reattach(job_id, last_seq=last_seq, read_durable=read_durable, is_done=_is_done):
            yield frame.data

    @staticmethod
    def _build_adapter(request: dict[str, Any], job_id: Any, flow_id: Any) -> Any:
        from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter

        protocol = request.get("stream_protocol", "langflow")
        return get_stream_adapter(
            protocol,
            StreamAdapterContext(
                run_id=str(job_id),
                thread_id=request.get("session_id") or str(flow_id),
            ),
        )
