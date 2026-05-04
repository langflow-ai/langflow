"""Coordinator: graph in, streaming step results out."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.execution.partitioner import identity_partition
from lfx.execution.types import RunComplete

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lfx.execution.registry import ExecutorRegistry
    from lfx.execution.types import StepResult


class Coordinator:
    def __init__(
        self,
        *,
        registry: ExecutorRegistry,
        executor_kind: str = "in-process",
    ) -> None:
        self._registry = registry
        self._executor_kind = executor_kind

    async def run(
        self,
        graph: Any,
        *,
        inputs: list[dict[str, Any]],
        **runtime_options: Any,
    ) -> AsyncIterator[StepResult | RunComplete]:
        units = identity_partition(graph, inputs=inputs, runtime_options=runtime_options)
        executor = self._registry.get(self._executor_kind)
        for unit in units:
            async for item in executor.execute(unit):
                yield item

    async def run_to_completion(
        self,
        graph: Any,
        *,
        inputs: list[dict[str, Any]],
        **runtime_options: Any,
    ) -> list[Any]:
        async for item in self.run(graph, inputs=inputs, **runtime_options):
            if isinstance(item, RunComplete):
                return item.outputs
        msg = "Executor stream ended without a RunComplete"
        raise RuntimeError(msg)
