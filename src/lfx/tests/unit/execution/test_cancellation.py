"""Cancellation and cleanup tests for the execution seam.

The contract suite covers the bare-minimum ``aclose()`` shape via
``test_consumer_cancellation_does_not_hang_or_leak``. This module exercises the
stricter behaviour the seam needs in production: explicit cleanup at the top of
the consumer chain MUST cascade all the way down to the underlying graph iterator.

What we deliberately do NOT test here:

- Implicit GC-based finalization (``async for ... break`` without ``aclosing``,
  ``task.cancel()`` then immediate assert). CPython finalizes abandoned async
  generators on a GC pass; asyncio runs the registered finalizer on event-loop
  shutdown. Neither is observable inside a single test, and asserting either
  would test CPython, not us. Consumers that need deterministic cleanup MUST
  use ``contextlib.aclosing`` or call ``aclose()`` explicitly.
"""

from __future__ import annotations

import asyncio
from contextlib import aclosing

import pytest
from lfx.execution.backends.in_process import InProcessExecutor
from lfx.execution.coordinator import Coordinator
from lfx.execution.registry import ExecutorRegistry
from lfx.execution.types import StepResult, Unit


class _InstrumentedGraph:
    """Minimal graph stub whose ``async_start`` runs forever until closed.

    We track entry, items yielded, and finalizer invocation so tests can assert
    the iterator was properly closed rather than abandoned.
    """

    def __init__(self) -> None:
        self.entered: bool = False
        self.finalized: bool = False
        self.items_yielded: int = 0

    async def async_start(self, **_kwargs):
        self.entered = True
        try:
            for i in range(10_000):
                self.items_yielded += 1
                yield f"item-{i}"
                await asyncio.sleep(0)
        finally:
            self.finalized = True


def _unit(graph: _InstrumentedGraph) -> Unit:
    return Unit(graph=graph, inputs=[], runtime_options={})


@pytest.mark.asyncio
async def test_aclose_on_executor_finalizes_underlying_graph_iteration():
    """``aclose()`` on the executor's generator MUST run the underlying graph's finalizer.

    Without the explicit try/finally inside ``InProcessExecutor.execute``, the inner
    generator is abandoned and the graph's ``finally:`` block (event managers,
    connections, vertex teardown) only runs on a future GC pass.
    """
    graph = _InstrumentedGraph()
    executor = InProcessExecutor()
    stream = executor.execute(_unit(graph))

    first = await anext(stream)
    assert isinstance(first, StepResult)
    assert graph.entered
    assert not graph.finalized

    await stream.aclose()
    assert graph.finalized, "underlying async generator was not finalized on aclose()"


@pytest.mark.asyncio
async def test_aclosing_helper_chains_cleanup_through_executor():
    """``contextlib.aclosing`` MUST trigger the same cascade as explicit ``aclose``."""
    graph = _InstrumentedGraph()
    executor = InProcessExecutor()

    async with aclosing(executor.execute(_unit(graph))) as stream:
        async for _ in stream:
            break

    assert graph.finalized


@pytest.mark.asyncio
async def test_coordinator_run_cascades_aclose_to_executor_and_graph():
    """Cleanup must propagate through every seam layer.

    Consumer aclose -> Coordinator.run -> Executor.execute -> graph.async_start.
    A regression at any layer would leave the graph generator hanging.
    """
    graph = _InstrumentedGraph()
    registry = ExecutorRegistry()
    registry.register(InProcessExecutor())
    coordinator = Coordinator(registry=registry)

    async with aclosing(coordinator.run(graph, inputs=[])) as stream:
        first = await anext(stream)
        assert first is not None

    assert graph.finalized, "Coordinator.run did not cascade aclose to the graph"


@pytest.mark.asyncio
async def test_coordinator_stream_cascades_aclose_to_graph():
    """``Coordinator.stream`` must cascade cleanup the same way ``Coordinator.run`` does."""
    graph = _InstrumentedGraph()
    registry = ExecutorRegistry()
    registry.register(InProcessExecutor())
    coordinator = Coordinator(registry=registry)

    async with aclosing(coordinator.stream(graph)) as stream:
        async for _ in stream:
            break

    assert graph.finalized


@pytest.mark.asyncio
async def test_cleanup_bounded_by_timeout():
    """Finalization must complete within a bounded window even on a slow CI box.

    A regression that swaps in a non-cancellable resource (blocking subprocess
    wait, sync lock) would hang here rather than slow.
    """
    graph = _InstrumentedGraph()
    executor = InProcessExecutor()

    async def drive():
        gen = executor.execute(_unit(graph))
        await anext(gen)
        await gen.aclose()

    await asyncio.wait_for(drive(), timeout=2.0)
    assert graph.finalized


@pytest.mark.asyncio
async def test_exception_in_consumer_still_finalizes_graph():
    """An exception inside the consumer MUST still trigger cleanup via ``aclosing``."""
    graph = _InstrumentedGraph()
    executor = InProcessExecutor()

    class _ConsumerError(RuntimeError):
        pass

    async def consume_then_raise() -> None:
        async with aclosing(executor.execute(_unit(graph))) as stream:
            async for _ in stream:
                msg = "downstream bug"
                raise _ConsumerError(msg)

    with pytest.raises(_ConsumerError):
        await consume_then_raise()

    assert graph.finalized


@pytest.mark.asyncio
async def test_concurrent_consumers_each_clean_up_independently():
    """Concurrent runs on one executor instance must clean up independently.

    Regression guard for any future change that introduces shared cleanup state
    on the executor (which would couple unrelated consumers).
    """
    graph_a = _InstrumentedGraph()
    graph_b = _InstrumentedGraph()
    executor = InProcessExecutor()

    async def drive(graph: _InstrumentedGraph, items_before_stop: int) -> None:
        async with aclosing(executor.execute(_unit(graph))) as stream:
            count = 0
            async for _ in stream:
                count += 1
                if count >= items_before_stop:
                    break

    await asyncio.gather(drive(graph_a, 1), drive(graph_b, 3))

    assert graph_a.finalized
    assert graph_b.finalized
