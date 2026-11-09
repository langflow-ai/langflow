"""Worker claim loop: reconciles on startup, runs the Runner per claimed id, survives crashes."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from langflow.services.background_execution import worker as worker_module
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


class _RecordingLogger:
    def __init__(self):
        self.exceptions: list[str] = []
        self.errors: list[str] = []

    async def aexception(self, message):
        self.exceptions.append(message)

    async def aerror(self, message):
        self.errors.append(message)


class _AdvancingWaits:
    """Advance the worker's timer waits while leaving the test's timeout real."""

    def __init__(self, stop_event):
        self.stop_event = stop_event
        self.delays: list[float] = []

    def __getattr__(self, name):
        return getattr(asyncio, name)

    async def wait_for(self, awaitable, *, timeout):
        self.delays.append(timeout)
        if self.stop_event.is_set():
            return await awaitable
        awaitable.close()
        await asyncio.sleep(0)
        raise asyncio.TimeoutError


async def test_watchdog_logs_a_failed_pass_and_reconciles_on_the_next_tick(monkeypatch):
    stop_event = asyncio.Event()
    clock = _AdvancingWaits(stop_event)
    recording_logger = _RecordingLogger()
    monkeypatch.setattr(worker_module, "asyncio", clock)
    monkeypatch.setattr(worker_module, "logger", recording_logger)
    monkeypatch.setattr(worker_module, "random", SimpleNamespace(uniform=lambda _low, _high: 1.0))

    class _RecoveringBackend:
        def __init__(self):
            self.calls: list[float] = []
            self.reconciled: list[str] = []

        async def requeue_lost(self, *, lease_ttl_s):
            self.calls.append(lease_ttl_s)
            if len(self.calls) == 1:
                msg = "connection reset during watchdog pass"
                raise ConnectionError(msg)
            self.reconciled.append("orphan")
            stop_event.set()
            return self.reconciled

    backend = _RecoveringBackend()
    await asyncio.wait_for(
        worker_module._watchdog_loop(backend, stop_event=stop_event, lease_ttl_s=45.0, interval_s=15.0),
        timeout=5,
    )

    assert backend.calls == [45.0, 45.0]
    assert backend.reconciled == ["orphan"]
    assert recording_logger.exceptions == ["Worker: lease watchdog pass failed; retrying next tick"]


async def test_unavailable_request_backoff_grows_caps_and_resets_after_a_successful_run(monkeypatch):
    stop_event = asyncio.Event()
    clock = _AdvancingWaits(stop_event)
    recording_logger = _RecordingLogger()
    monkeypatch.setattr(worker_module, "asyncio", clock)
    monkeypatch.setattr(worker_module, "logger", recording_logger)
    monkeypatch.setattr(worker_module, "random", SimpleNamespace(uniform=lambda _low, _high: 1.0))
    failed_ids = [f"bad-{number}" for number in range(7)]
    backend = _FakeBackend([*failed_ids, "recovered", "bad-after-recovery", "done"])

    class _UnavailableThenRecoveredRunner:
        def __init__(self):
            self.completed: list[str] = []

        async def run(self, job_id):
            if job_id.startswith("bad-"):
                raise worker_module.RequestOverridesUnavailableError
            self.completed.append(job_id)
            if job_id == "done":
                stop_event.set()

    runner = _UnavailableThenRecoveredRunner()
    await asyncio.wait_for(run_worker_loop(backend, runner, stop_event=stop_event, idle_block_ms=1000), timeout=5)

    assert runner.completed == ["recovered", "done"]
    assert clock.delays == [2.0, 4.0, 8.0, 16.0, 30.0, 30.0, 30.0, 2.0]
    assert len(recording_logger.errors) == 8
    assert all("LANGFLOW_SECRET_KEY" in message for message in recording_logger.errors)


async def test_stop_interrupts_an_unavailable_request_backoff(monkeypatch):
    stop_event = asyncio.Event()
    failure_logged = asyncio.Event()

    class _FailureLogger(_RecordingLogger):
        async def aerror(self, message):
            await super().aerror(message)
            failure_logged.set()

    class _UnavailableRunner:
        def __init__(self):
            self.ran: list[str] = []

        async def run(self, job_id):
            self.ran.append(job_id)
            raise worker_module.RequestOverridesUnavailableError

    monkeypatch.setattr(worker_module, "logger", _FailureLogger())
    monkeypatch.setattr(worker_module, "random", SimpleNamespace(uniform=lambda _low, _high: 1.0))
    backend = _FakeBackend(["bad-request", "must-not-run"])
    runner = _UnavailableRunner()
    task = asyncio.create_task(run_worker_loop(backend, runner, stop_event=stop_event, idle_block_ms=60_000))
    try:
        await asyncio.wait_for(failure_logged.wait(), timeout=5)
        stop_event.set()
        await asyncio.wait_for(task, timeout=5)
    finally:
        stop_event.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    assert runner.ran == ["bad-request"]
