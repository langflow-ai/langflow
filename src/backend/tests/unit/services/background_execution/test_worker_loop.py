"""Worker claim loop: reconciles on startup, runs the Runner per claimed id, survives crashes."""

from __future__ import annotations

import asyncio

import pytest
from langflow.services.background_execution.worker import run_worker_loop


class _FakeBackend:
    """Real-behavior stand-in for the claim side (not a mock of our code).

    Hands out a fixed list of ids then blocks/returns None, and records the
    startup reconcile call.
    """

    def __init__(self, ids):
        self._ids = list(ids)
        self.reconciled = False

    async def requeue_lost(self, *, lease_ttl_s=45.0):  # noqa: ARG002 - lease_ttl_s is part of the contract
        self.reconciled = True
        return []

    async def claim(self, *, block_ms=1000):  # noqa: ARG002 - block_ms is part of the claim contract
        if self._ids:
            return self._ids.pop(0)
        return None


class _RecordingRunner:
    """Records each run and signals stop_event once it has drained stop_after ids."""

    def __init__(self, stop_event=None, stop_after=None):
        self.ran: list[str] = []
        self._stop_event = stop_event
        self._stop_after = stop_after

    async def run(self, job_id):
        self.ran.append(job_id)
        if self._stop_event is not None and self._stop_after is not None and len(self.ran) >= self._stop_after:
            # Drained the scripted ids — let the loop exit on its next check.
            self._stop_event.set()


@pytest.mark.asyncio
async def test_worker_runs_each_claimed_job():
    backend = _FakeBackend(["j1", "j2"])
    stop_event = asyncio.Event()
    runner = _RecordingRunner(stop_event=stop_event, stop_after=2)

    await run_worker_loop(backend, runner, stop_event=stop_event, idle_block_ms=10)

    assert backend.reconciled is True
    assert runner.ran == ["j1", "j2"]


@pytest.mark.asyncio
async def test_worker_survives_a_runner_crash_and_keeps_claiming():
    backend = _FakeBackend(["boom", "j2"])
    stop_event = asyncio.Event()

    class _BoomThenRecord(_RecordingRunner):
        async def run(self, job_id):
            if job_id == "boom":
                msg = "runner blew up"
                raise RuntimeError(msg)
            await super().run(job_id)

    runner = _BoomThenRecord(stop_event=stop_event, stop_after=1)
    await run_worker_loop(backend, runner, stop_event=stop_event, idle_block_ms=10)

    # A runner crash must not kill the loop: the durable job row + watchdog own
    # the crashed job's fate, and the worker moves on to the next claim.
    assert runner.ran == ["j2"]


class _RosterReadingBackend:
    """Claim side that reads the roster mid-loop, so presence can be observed while it is live.

    The loop deletes the row on graceful stop, so a test that only looks after
    the loop returns can never see what the roster said while the worker was up.
    """

    def __init__(self, stop_event, owner):
        self._stop_event = stop_event
        self._owner = owner
        self.calls = 0
        self.seen = None

    async def requeue_lost(self, *, lease_ttl_s=45.0):  # noqa: ARG002 - part of the contract
        return []

    async def claim(self, *, block_ms=1000):  # noqa: ARG002 - part of the claim contract
        from langflow.services.database.models.worker_registry.model import WorkerRegistry
        from langflow.services.deps import session_scope

        self.calls += 1
        if self.calls >= 2:
            async with session_scope() as session:
                self.seen = await session.get(WorkerRegistry, self._owner)
            self._stop_event.set()


@pytest.mark.usefixtures("client")
async def test_idle_worker_registers_then_deregisters_on_stop():
    """An idle worker is visible as online, and leaves no row behind on graceful stop."""
    from langflow.services.database.models.worker_registry.model import WorkerRegistry, WorkerState
    from langflow.services.deps import session_scope

    owner = "worker:test:idle"
    stop_event = asyncio.Event()
    backend = _RosterReadingBackend(stop_event, owner)
    runner = _RecordingRunner()

    await run_worker_loop(
        backend,
        runner,
        stop_event=stop_event,
        idle_block_ms=10,
        owner=owner,
        roster_enabled=True,
        roster_interval_s=0.0,
    )

    assert backend.seen is not None, "an idle worker must still appear on the roster"
    assert backend.seen.state == WorkerState.IDLE
    assert backend.seen.current_job_id is None
    assert runner.ran == []

    async with session_scope() as session:
        assert await session.get(WorkerRegistry, owner) is None, "graceful stop must drop the row"


@pytest.mark.usefixtures("client")
async def test_busy_worker_names_the_job_it_is_running():
    """While a job runs, the roster says BUSY and carries that job id.

    This is what makes the fleet gauges answer "how many workers are actually
    working", rather than only "how many processes are alive".
    """
    from uuid import uuid4

    from langflow.services.database.models.worker_registry.model import WorkerRegistry, WorkerState
    from langflow.services.deps import session_scope

    owner = "worker:test:busy"
    job_id = uuid4()
    stop_event = asyncio.Event()
    backend = _FakeBackend([str(job_id)])

    class _InspectingRunner:
        """Reads the roster from inside the run, which is the only time BUSY is true."""

        def __init__(self):
            self.ran: list[str] = []
            self.seen = None

        async def run(self, claimed_id):
            self.ran.append(claimed_id)
            async with session_scope() as session:
                self.seen = await session.get(WorkerRegistry, owner)
            stop_event.set()

    runner = _InspectingRunner()

    await run_worker_loop(
        backend,
        runner,
        stop_event=stop_event,
        idle_block_ms=10,
        owner=owner,
        roster_enabled=True,
        roster_interval_s=0.0,
    )

    assert runner.ran == [str(job_id)]
    assert runner.seen is not None
    assert runner.seen.state == WorkerState.BUSY
    assert runner.seen.current_job_id == job_id, "the roster must name the job this worker holds"
