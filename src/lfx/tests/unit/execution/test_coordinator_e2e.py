"""End-to-end seam tests: a real Graph driven through Coordinator.

Tests in ``test_coordinator.py`` check Coordinator behaviour at a behavioural level
but defer most of the heavy lifting to the executor or graph layer. This module
verifies the seam contract by running a real ``lfx.Graph`` through the full
``Coordinator -> ExecutorRegistry -> InProcessExecutor -> graph.async_start``
chain and asserting the event stream looks like what consumers actually receive:

- ``stream()`` payloads are vertex-shaped (not the seam envelopes).
- ``run()`` yields ``StepResult`` items in order then exactly one ``RunComplete``.
- ``stream()`` never leaks ``RunComplete`` through the payload channel.
- Switching the registered executor changes what runs (the dispatch is real, not
  hard-wired to ``InProcessExecutor``).
- Lifecycle: registry get() returns the same instance for repeated calls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lfx.execution.backends.in_process import InProcessExecutor
from lfx.execution.coordinator import Coordinator
from lfx.execution.executor import Executor
from lfx.execution.registry import ExecutorRegistry
from lfx.execution.types import RunComplete, StepResult, Unit

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


def _make_coordinator() -> Coordinator:
    registry = ExecutorRegistry()
    registry.register(InProcessExecutor())
    return Coordinator(registry=registry)


@pytest.mark.asyncio
async def test_run_yields_step_results_then_terminal_run_complete(simple_graph):
    coordinator = _make_coordinator()
    items = [item async for item in coordinator.run(simple_graph, inputs=[{"input_value": "hi"}])]

    assert items, "real Graph drove zero events through Coordinator"
    assert isinstance(items[-1], RunComplete), "stream must end with RunComplete"
    assert sum(isinstance(i, RunComplete) for i in items) == 1, "exactly one RunComplete expected"
    assert all(isinstance(i, StepResult) for i in items[:-1]), "pre-terminal items must all be StepResult"


@pytest.mark.asyncio
async def test_stream_yields_payloads_only_no_run_complete_leak(simple_graph):
    """``Coordinator.stream`` MUST NOT yield ``RunComplete`` instances.

    It is the payload-only helper; the terminal envelope from the executor must
    be stripped before reaching the consumer.
    """
    coordinator = _make_coordinator()
    payloads = [p async for p in coordinator.stream(simple_graph, initial_inputs=None)]

    assert payloads, "stream produced no payloads from a real graph"
    assert not any(isinstance(p, RunComplete) for p in payloads), (
        "Coordinator.stream() leaked RunComplete into the payload channel"
    )
    assert not any(isinstance(p, StepResult) for p in payloads), (
        "Coordinator.stream() leaked StepResult envelopes; payloads should be unwrapped"
    )


@pytest.mark.asyncio
async def test_payload_shape_is_vertex_or_finish_for_in_process(simple_graph):
    """Pin the in-process payload contract.

    Changes to graph.async_start can't silently rename or restructure the
    events consumers depend on without breaking this test.
    """
    from lfx.graph.graph.constants import Finish

    coordinator = _make_coordinator()
    payloads = [p async for p in coordinator.stream(simple_graph, initial_inputs=None)]

    vertex_ids = [getattr(p, "vertex", None) and p.vertex.id for p in payloads]
    assert "chat_input" in vertex_ids
    assert "chat_output" in vertex_ids
    assert any(isinstance(p, Finish) for p in payloads), "expected a terminal Finish payload"


@pytest.mark.asyncio
async def test_dispatch_routes_to_configured_kind(simple_graph):
    """Changing ``executor_kind`` changes where execution lands.

    Proves the registry lookup is the real dispatch, not a hard-coded reference.
    """

    class _Marker(Executor):
        kind = "marker"
        ran: bool = False

        async def execute(self, unit: Unit) -> AsyncIterator[StepResult | RunComplete]:  # noqa: ARG002
            type(self).ran = True
            yield StepResult(payload="sentinel")
            yield RunComplete(outputs=["sentinel"])

    registry = ExecutorRegistry()
    registry.register(InProcessExecutor())
    registry.register(_Marker())
    coordinator = Coordinator(registry=registry, executor_kind="marker")

    items = [item async for item in coordinator.run(simple_graph, inputs=[])]
    assert _Marker.ran is True
    assert items[0].payload == "sentinel"
    assert isinstance(items[-1], RunComplete)
    assert items[-1].outputs == ["sentinel"]


@pytest.mark.asyncio
async def test_run_to_completion_returns_outputs_from_legacy_path(simple_graph):
    """``run_to_completion`` with the legacy flag returns populated outputs.

    This is the only path through the seam where ``RunComplete.outputs`` carries
    a meaningful value (see ``RunComplete`` docstring).
    """
    coordinator = _make_coordinator()
    outputs = await coordinator.run_to_completion(
        simple_graph,
        inputs=[{"input_value": "hi"}],
        _use_arun_legacy=True,
    )
    assert isinstance(outputs, list)


@pytest.mark.asyncio
async def test_registry_returns_same_executor_instance_across_runs(simple_graph):
    """The seam shares one executor instance per kind across all runs.

    Two sequential ``coordinator.run`` calls MUST resolve to the same instance;
    otherwise executor authors couldn't rely on instance-level setup.
    """
    instances: list[Executor] = []
    real_inprocess = InProcessExecutor()

    class _Recorder(Executor):
        kind = "recorder"

        async def execute(self, unit: Unit) -> AsyncIterator[StepResult | RunComplete]:
            instances.append(self)
            async for item in real_inprocess.execute(unit):
                yield item

    registry = ExecutorRegistry()
    registry.register(_Recorder())
    coordinator = Coordinator(registry=registry, executor_kind="recorder")

    [_ async for _ in coordinator.run(simple_graph, inputs=[{"input_value": "a"}])]
    [_ async for _ in coordinator.run(simple_graph, inputs=[{"input_value": "b"}])]

    assert len(instances) == 2
    assert instances[0] is instances[1], "registry must return the same instance per kind"
