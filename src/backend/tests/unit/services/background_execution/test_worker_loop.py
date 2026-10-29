"""Worker claim loop: reconciles on startup, runs the Runner per claimed id, survives crashes."""

from __future__ import annotations

import asyncio

import pytest
from langflow.services.background_execution.worker import (
    _CLAIM_BACKOFF_CAP_S,
    _claim_backoff_s,
    run_worker_loop,
)


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


class _FlakyBackend:
    """Claim side whose database is briefly unreachable, then recovers."""

    def __init__(self, fail_times, ids, stop_event):
        self._fail_left = fail_times
        self._ids = list(ids)
        self._stop_event = stop_event
        self.reconciled = False
        self.claim_calls = 0

    async def requeue_lost(self, *, lease_ttl_s=45.0):  # noqa: ARG002 - part of the contract
        self.reconciled = True
        return []

    async def claim(self, *, block_ms=1000):  # noqa: ARG002 - part of the claim contract
        self.claim_calls += 1
        if self._fail_left > 0:
            self._fail_left -= 1
            msg = "connection reset by peer"
            raise ConnectionError(msg)
        if self._ids:
            return self._ids.pop(0)
        self._stop_event.set()
        return None


@pytest.mark.usefixtures("client")
async def test_worker_survives_a_database_blip_instead_of_exiting():
    """A failing claim must not end the worker process.

    Every idle worker polls on the same cadence, so an unguarded raise here takes
    the whole fleet down together on one database hiccup.
    """
    stop_event = asyncio.Event()
    backend = _FlakyBackend(fail_times=3, ids=["j1"], stop_event=stop_event)
    runner = _RecordingRunner()

    await run_worker_loop(backend, runner, stop_event=stop_event, idle_block_ms=1)

    assert backend.claim_calls > 3, "the loop must keep polling after a failed claim"
    assert runner.ran == ["j1"], "and must still run the job once the database comes back"


class _StartupFailsBackend:
    """The startup reconcile raises; the worker should still come up."""

    def __init__(self, stop_event):
        self._stop_event = stop_event
        self.claimed = False

    async def requeue_lost(self, *, lease_ttl_s=45.0):  # noqa: ARG002 - part of the contract
        msg = "pool timeout at boot"
        raise TimeoutError(msg)

    async def claim(self, *, block_ms=1000):  # noqa: ARG002 - part of the claim contract
        self.claimed = True
        self._stop_event.set()


@pytest.mark.usefixtures("client")
async def test_worker_boots_when_the_startup_reconcile_fails():
    """Refusing to boot because the reconcile failed helps nobody; the watchdog retries."""
    stop_event = asyncio.Event()
    backend = _StartupFailsBackend(stop_event)

    await run_worker_loop(backend, _RecordingRunner(), stop_event=stop_event, idle_block_ms=1)

    assert backend.claimed, "the worker must reach its claim loop despite a failed startup reconcile"


@pytest.mark.parametrize("failures", [0, 1, 5, 1023, 1024, 10**6])
def test_claim_backoff_stays_finite_however_long_the_database_is_down(failures):
    """A worker that cannot reach the database must keep retrying, not die of OverflowError.

    Capping only the product leaves 2**failures itself to overflow once the
    counter passes 1023, which at the 30s ceiling is a few hours of downtime.
    """
    backoff = _claim_backoff_s(idle_block_ms=1000, failures=failures)

    assert 0.0 < backoff <= _CLAIM_BACKOFF_CAP_S


def test_claim_backoff_grows_then_settles_at_the_cap():
    early = [_claim_backoff_s(idle_block_ms=1000, failures=n) for n in (1, 2, 3)]

    assert early == sorted(early), "backoff must grow while the database is down"
    assert _claim_backoff_s(idle_block_ms=1000, failures=50) == _CLAIM_BACKOFF_CAP_S
