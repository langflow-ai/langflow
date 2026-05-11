"""In-process executor: wraps today's graph runner."""

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

        if opts.get("_use_arun_legacy") and hasattr(graph, "_arun_legacy"):
            legacy_kwargs = {k: v for k, v in opts.items() if not k.startswith("_")}
            outputs = await graph._arun_legacy(inputs=unit.inputs, **legacy_kwargs)  # noqa: SLF001
            yield RunComplete(outputs=list(outputs))
            return

        # Hold a reference to the inner async iterator so we can guarantee
        # finalization on consumer cancellation. ``async for`` does NOT call
        # ``aclose()`` on its iterator when the loop is interrupted by an exception
        # (e.g. ``GeneratorExit`` from this generator being closed). Without the
        # explicit try/finally below, the inner generator's ``finally:`` block --
        # which is where event managers, connections, or vertex finalizers run --
        # would only execute on GC, leaking resources for an unpredictable window.
        inner = graph.async_start(
            inputs=opts.get("initial_inputs"),
            max_iterations=opts.get("max_iterations"),
            config=opts.get("config"),
            event_manager=opts.get("event_manager"),
            reset_output_values=opts.get("reset_output_values", True),
            fallback_to_env_vars=opts.get("fallback_to_env_vars", False),
        )
        try:
            async for result in inner:
                yield StepResult(payload=result)
                if isinstance(result, Finish):
                    break

            yield RunComplete(outputs=[])
        finally:
            # ``aclose`` is a no-op if the generator already completed. Async
            # iterables that aren't generators (test stubs, custom iterators) may
            # not implement aclose, so guard with hasattr.
            aclose = getattr(inner, "aclose", None)
            if aclose is not None:
                await aclose()
