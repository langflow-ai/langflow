"""Unit tests for the lfx serve build admission controller."""

from __future__ import annotations

import asyncio

import pytest
from lfx.cli.admission import (
    BUILD_SLOTS_IN_USE,
    BUILD_SLOTS_LIMIT,
    AdmissionTimeout,
    BuildAdmissionConfig,
    BuildAdmissionController,
)

pytestmark = pytest.mark.asyncio


def _in_use(profile: str) -> float:
    return BUILD_SLOTS_IN_USE.labels(profile=profile)._value.get()


def _limit(profile: str) -> float:
    return BUILD_SLOTS_LIMIT.labels(profile=profile)._value.get()


def _make(profile: str, *, limit: int, timeout: float = 0.1) -> BuildAdmissionController:
    return BuildAdmissionController(BuildAdmissionConfig(limit=limit, timeout=timeout, profile=profile))


async def test_from_env_defaults(monkeypatch):
    for var in (
        "LANGFLOW_BUILD_CONCURRENCY_LIMIT",
        "LANGFLOW_BUILD_ADMISSION_TIMEOUT_SECONDS",
        "LANGFLOW_BUILD_PROFILE_LABEL",
    ):
        monkeypatch.delenv(var, raising=False)
    cfg = BuildAdmissionConfig.from_env()
    assert cfg.limit == 0
    assert cfg.timeout == 5.0
    assert cfg.profile == "unknown"


async def test_from_env_reads_vars(monkeypatch):
    monkeypatch.setenv("LANGFLOW_BUILD_CONCURRENCY_LIMIT", "7")
    monkeypatch.setenv("LANGFLOW_BUILD_ADMISSION_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("LANGFLOW_BUILD_PROFILE_LABEL", "editor")
    cfg = BuildAdmissionConfig.from_env()
    assert cfg == BuildAdmissionConfig(limit=7, timeout=2.5, profile="editor")


async def test_limit_gauge_set_at_construction():
    _make("t-limitgauge", limit=4)
    assert _limit("t-limitgauge") == 4
    assert _in_use("t-limitgauge") == 0


async def test_profile_label_flows_to_both_gauges():
    _make("t-profile", limit=3)
    assert _limit("t-profile") == 3
    assert _in_use("t-profile") == 0  # series exists for this profile


async def test_disabled_is_unbounded():
    c = _make("t-disabled", limit=0)
    # Many concurrent holders, none block; limit gauge is 0.
    async with c.slot(), c.slot(), c.slot():
        assert _in_use("t-disabled") == 3
    assert _in_use("t-disabled") == 0
    assert _limit("t-disabled") == 0


async def test_kplus1_times_out_and_is_not_counted():
    c = _make("t-429", limit=2, timeout=0.05)
    await c.acquire()
    await c.acquire()  # K=2 held
    assert _in_use("t-429") == 2
    with pytest.raises(AdmissionTimeout) as ei:
        await c.acquire()  # (K+1)th waits then times out
    assert ei.value.retry_after == 1  # ceil(0.05) floored to >=1
    assert _in_use("t-429") == 2  # 429'd request NOT counted
    c.release()
    c.release()
    assert _in_use("t-429") == 0


async def test_waiter_proceeds_when_slot_frees():
    c = _make("t-wait", limit=1, timeout=5.0)
    await c.acquire()
    proceeded = asyncio.Event()

    async def waiter():
        await c.acquire()
        proceeded.set()

    task = asyncio.create_task(waiter())
    await asyncio.sleep(0.05)
    assert not proceeded.is_set()  # blocked while slot held
    c.release()  # free the slot
    await asyncio.wait_for(proceeded.wait(), timeout=1.0)
    assert _in_use("t-wait") == 1
    c.release()
    await task
    assert _in_use("t-wait") == 0


async def test_slot_releases_on_success_and_exception():
    c = _make("t-paths", limit=1, timeout=1.0)
    async with c.slot():
        assert _in_use("t-paths") == 1
    assert _in_use("t-paths") == 0

    async def _raise_in_slot() -> None:
        msg = "boom"
        async with c.slot():
            assert _in_use("t-paths") == 1
            raise ValueError(msg)

    with pytest.raises(ValueError, match="boom"):
        await _raise_in_slot()
    assert _in_use("t-paths") == 0  # released despite exception


async def test_slot_releases_on_cancellation():
    c = _make("t-cancel", limit=1, timeout=1.0)
    started = asyncio.Event()

    async def holder():
        async with c.slot():
            started.set()
            await asyncio.sleep(10)

    task = asyncio.create_task(holder())
    await asyncio.wait_for(started.wait(), timeout=1.0)
    assert _in_use("t-cancel") == 1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert _in_use("t-cancel") == 0  # released on cancellation


async def test_in_use_never_exceeds_limit_under_burst():
    c = _make("t-burst", limit=3, timeout=5.0)
    peak = 0
    lock = asyncio.Lock()

    async def worker():
        nonlocal peak
        async with c.slot():
            async with lock:
                peak = max(peak, _in_use("t-burst"))
            await asyncio.sleep(0.02)

    await asyncio.gather(*(worker() for _ in range(30)))
    assert peak <= 3
    assert _in_use("t-burst") == 0


async def test_timeout_does_not_leak_permit_or_slot():
    """A timed-out acquire must not leak a semaphore permit or increment in_use.

    The shielded-task acquire in BuildAdmissionController.acquire() ensures that
    if the underlying semaphore.acquire() grabs a permit at the exact instant of
    a wait_for timeout cancellation, that permit is returned via _discard_acquire
    before AdmissionTimeout is raised. This test verifies the net result:
    - in_use stays correct throughout
    - the semaphore is not exhausted (a subsequent acquire can succeed)
    """
    c = _make("t-noleak", limit=1, timeout=0.05)
    await c.acquire()  # hold the only slot
    with pytest.raises(AdmissionTimeout):
        await c.acquire()  # times out
    assert _in_use("t-noleak") == 1  # the timed-out attempt left no trace
    c.release()  # free the original
    assert _in_use("t-noleak") == 0
    # The semaphore must not have leaked a permit: exactly one slot is available again.
    await c.acquire()
    assert _in_use("t-noleak") == 1
    with pytest.raises(AdmissionTimeout):
        await c.acquire()  # still correctly bounded at 1
    c.release()
    assert _in_use("t-noleak") == 0
