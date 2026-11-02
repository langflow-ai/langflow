"""The per-flow writer gate: writers past the limit wait in the process, before any database session."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from langflow.services.flow_multiplayer import config, writes


@pytest.fixture
def writers_per_flow(monkeypatch):
    def set_value(value: str | None) -> None:
        if value is None:
            monkeypatch.delenv(config.WRITERS_PER_FLOW_ENV, raising=False)
        else:
            monkeypatch.setenv(config.WRITERS_PER_FLOW_ENV, value)
        config.reset_for_tests()

    yield set_value
    monkeypatch.delenv(config.WRITERS_PER_FLOW_ENV, raising=False)
    config.reset_for_tests()


async def _peak_inside(flow_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """Run one writer per item through the gate; return the most writers inside at once, per flow."""
    inside: dict[uuid.UUID, int] = dict.fromkeys(flow_ids, 0)
    peak: dict[uuid.UUID, int] = dict.fromkeys(flow_ids, 0)

    async def writer(flow_id: uuid.UUID) -> None:
        async with writes.flow_gate(flow_id):
            inside[flow_id] += 1
            peak[flow_id] = max(peak[flow_id], inside[flow_id])
            await asyncio.sleep(0.01)
            inside[flow_id] -= 1

    await asyncio.gather(*(writer(f) for f in flow_ids))
    return peak


async def test_default_admits_one_writer_per_flow_and_other_flows_in_parallel(writers_per_flow):
    writers_per_flow(None)
    a, b = uuid.uuid4(), uuid.uuid4()
    peak = await _peak_inside([a] * 5 + [b] * 5)
    assert peak == {a: 1, b: 1}
    assert writes._gates == {}  # no gate left once its writers are gone


async def test_limit_is_configurable_and_zero_means_no_limit(writers_per_flow):
    flow = uuid.uuid4()
    writers_per_flow("2")
    assert (await _peak_inside([flow] * 6))[flow] == 2
    writers_per_flow("0")
    assert (await _peak_inside([flow] * 6))[flow] == 6


async def test_a_cancelled_waiter_leaves_the_gate_usable(writers_per_flow):
    writers_per_flow("1")
    flow = uuid.uuid4()
    entered = asyncio.Event()
    release = asyncio.Event()

    async def holder() -> None:
        async with writes.flow_gate(flow):
            entered.set()
            await release.wait()

    async def waiter() -> None:
        async with writes.flow_gate(flow):
            pass

    held = asyncio.create_task(holder())
    await entered.wait()
    waiting = asyncio.create_task(waiter())
    await asyncio.sleep(0.01)
    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting
    release.set()
    await held
    assert writes._gates == {}
    assert (await _peak_inside([flow] * 3))[flow] == 1


def test_negative_limit_is_refused(writers_per_flow):
    writers_per_flow("-1")
    with pytest.raises(ValueError, match="LANGFLOW_FLOW_WRITERS_PER_FLOW"):
        config.writers_per_flow()
