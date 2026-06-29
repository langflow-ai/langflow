"""Worker claim loop: reconciles on startup, runs the Runner per claimed id, then completes."""

from __future__ import annotations

import asyncio

import pytest
from langflow.services.background_execution.worker import run_worker_loop


class _FakeBackend:
    """Real-behavior stand-in for the claim queue side (not a mock of our code).

    Hands out a fixed list of ids then blocks/returns None, records completes,
    and records the startup reconcile call.
    """

    def __init__(self, ids):
        self._ids = list(ids)
        self.completed: list[str] = []
        self.reconciled = False

    async def requeue_lost(self, *, lease_ttl_s=45.0):  # noqa: ARG002 - lease_ttl_s is part of the contract
        self.reconciled = True
        return []

    async def claim(self, *, block_ms=1000):  # noqa: ARG002 - block_ms is part of the claim contract
        if self._ids:
            return self._ids.pop(0)
        return None

    async def complete(self, job_id):
        self.completed.append(job_id)


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
async def test_worker_runs_each_claimed_job_then_completes():
    backend = _FakeBackend(["j1", "j2"])
    stop_event = asyncio.Event()
    runner = _RecordingRunner(stop_event=stop_event, stop_after=2)

    await run_worker_loop(backend, runner, stop_event=stop_event, idle_block_ms=10)

    assert backend.reconciled is True
    assert runner.ran == ["j1", "j2"]
    assert backend.completed == ["j1", "j2"]


@pytest.mark.asyncio
async def test_worker_completes_even_when_runner_raises():
    backend = _FakeBackend(["boom"])
    stop_event = asyncio.Event()

    class _Boom:
        async def run(self, job_id):  # noqa: ARG002 - job_id matches the runner contract
            msg = "runner blew up"
            raise RuntimeError(msg)

    async def stop_soon():
        await asyncio.sleep(0.2)
        stop_event.set()

    driver = asyncio.create_task(stop_soon())
    await run_worker_loop(backend, _Boom(), stop_event=stop_event, idle_block_ms=10)
    await driver

    # A runner crash must still release the lease so the watchdog can reconcile,
    # not leave the id stuck on the processing list forever.
    assert backend.completed == ["boom"]
