"""BOUNDED-CONCURRENCY real service.

Submit N+k jobs to the real ``InProcessExecutor`` configured for max concurrency
N. A barrier holds every started job so the peak in-flight count is observable;
the executor must never run more than N at once, the extra k stay queued, and the
whole backlog drains to completion once the barrier releases. Every wait is
bounded so a regression fails loudly.
"""

from __future__ import annotations

import asyncio
import threading

import pytest
from langflow.services.background_execution.executor import InProcessExecutor

pytestmark = pytest.mark.real_services


class _Probe:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.current = 0
        self.peak = 0
        self.completed = 0

    def enter(self) -> None:
        with self._lock:
            self.current += 1
            self.peak = max(self.peak, self.current)

    def exit(self, *, completed: bool) -> None:
        with self._lock:
            self.current -= 1
            if completed:
                self.completed += 1


async def test_executor_never_exceeds_max_concurrency_and_drains():
    """N+k submitted at cap N: peak == N, k wait, then the whole backlog drains."""
    n = 3
    k = 2
    probe = _Probe()
    release = asyncio.Event()

    async def _slow_job() -> None:
        probe.enter()
        completed = False
        try:
            # Hold the slot until the test confirms the cap, so the peak is real.
            await asyncio.wait_for(release.wait(), timeout=10)
            completed = True
        finally:
            probe.exit(completed=completed)

    executor = InProcessExecutor(max_concurrency=n)
    await executor.start()
    try:
        for i in range(n + k):
            await executor.submit(f"job-{i}", _slow_job)

        # Let the pool saturate. Peak must reach exactly N, never N+1. Bounded
        # poll (a fixed iteration budget, not an open-ended wait) so a regression
        # fails loudly instead of hanging.
        for _ in range(500):  # ~5s budget
            if probe.current >= n:
                break
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.3)  # would expose any over-admission
        assert probe.peak == n, f"executor ran {probe.peak} concurrently, cap was {n}"
        assert probe.current == n, f"{probe.current} in-flight, expected exactly the cap {n}"

        # Release: the backlog of k waiting jobs drains and everything finishes.
        release.set()

        for _ in range(500):  # ~10s budget
            if probe.completed >= n + k:
                break
            await asyncio.sleep(0.02)
        assert probe.completed == n + k, f"only {probe.completed}/{n + k} jobs drained"
        # The cap held across the whole run, even as the backlog drained.
        assert probe.peak == n, f"cap breached during drain: peak={probe.peak}"
        print(  # noqa: T201
            f"PROOF[concurrency]: submitted {n + k} at cap {n} -> peak in-flight={probe.peak} "
            f"(never {n + 1}); all {probe.completed} drained after the barrier released"
        )
    finally:
        release.set()
        await executor.stop()
