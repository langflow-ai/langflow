"""In-process executor — wraps today's graph runner."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.execution.executor import Executor
from lfx.execution.types import RunComplete, StepResult
from lfx.graph.graph.constants import Finish

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lfx.execution.types import Unit


class InProcessExecutor(Executor):
    kind = "in-process"

    async def execute(self, unit: Unit) -> AsyncIterator[StepResult | RunComplete]:
        graph = unit.graph
        opts = unit.runtime_options

        legacy = getattr(graph, "_arun_legacy", None)
        if legacy is not None and unit.inputs and isinstance(unit.inputs[0], dict):
            outputs = await legacy(inputs=unit.inputs, **opts)
            yield RunComplete(outputs=list(outputs))
            return

        async for result in graph.async_start(
            inputs=opts.get("initial_inputs"),
            max_iterations=opts.get("max_iterations"),
            config=opts.get("config"),
            event_manager=opts.get("event_manager"),
            reset_output_values=opts.get("reset_output_values", True),
        ):
            yield StepResult(payload=result)
            if isinstance(result, Finish):
                break

        outputs_filter = opts.get("outputs") or []
        final = []
        for vertex in graph.vertices:
            if not vertex.built:
                continue
            if (not outputs_filter and vertex.is_output) or (
                vertex.display_name in outputs_filter or vertex.id in outputs_filter
            ):
                final.append(vertex.result)
        yield RunComplete(outputs=final)
