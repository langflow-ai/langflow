"""Coordinator: graph in, streaming step results out.

The ``Coordinator`` is the single dispatch point between callers and executors. It
looks up the registered ``Executor`` for the configured ``kind``, partitions the
input graph into ``Unit`` value objects, and forwards each unit's event stream.

Callers pick the view they want:

- ``run()``: full seam stream (``StepResult`` + terminal ``RunComplete``). Use when
  you need the terminal signal -- e.g. ``run_to_completion``.
- ``stream()``: payloads only. Drops the terminal ``RunComplete`` silently because
  every existing payload-consumer in the codebase (``flow_executor``, the CLI,
  ``Loop``, ``run/base``) processes events incrementally and has no use for the
  terminal envelope.
- ``run_to_completion()``: drains the stream and returns ``RunComplete.outputs``.
  Practically useful only with the in-process executor's legacy passthrough; see
  the docstring on ``RunComplete.outputs`` for the full semantics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.execution.partitioner import identity_partition
from lfx.execution.types import RunComplete, StepResult

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lfx.execution.registry import ExecutorRegistry


class Coordinator:
    """Routes graph runs through a registered ``Executor`` of the configured kind."""

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
        """Stream the seam-typed event sequence for ``graph``.

        Yields the executor's ``StepResult`` items in order followed by the
        terminal ``RunComplete``. If you only need payloads, use ``stream()``;
        if you only need the final ``outputs`` list, use ``run_to_completion()``.

        ``runtime_options`` are forwarded as-is into ``Unit.runtime_options``;
        consult the active executor's documentation for which keys it honors.
        """
        units = identity_partition(graph, inputs=inputs, runtime_options=runtime_options)
        executor = self._registry.get(self._executor_kind)
        for unit in units:
            # Cascade cleanup: if our consumer aclose()s us, we aclose the executor
            # stream, which lets InProcessExecutor's try/finally aclose the underlying
            # graph generator. Without this, the executor stream is abandoned on
            # consumer aclose and only finalizes when CPython gets around to GC.
            inner = executor.execute(unit)
            try:
                async for item in inner:
                    yield item
            finally:
                aclose = getattr(inner, "aclose", None)
                if aclose is not None:
                    await aclose()

    async def run_to_completion(
        self,
        graph: Any,
        *,
        inputs: list[dict[str, Any]],
        **runtime_options: Any,
    ) -> list[Any]:
        """Drain the stream and return ``RunComplete.outputs``.

        Raises ``RuntimeError`` if the executor's stream ends without a terminal
        ``RunComplete`` -- a contract violation that every executor must avoid.

        See ``RunComplete.outputs`` for the per-executor semantics of the returned
        list. In particular, the in-process executor's streaming path returns an
        empty list here; callers that want final outputs from the streaming path
        should use ``stream()`` and collect what they need from payloads.
        """
        async for item in self.run(graph, inputs=inputs, **runtime_options):
            if isinstance(item, RunComplete):
                return item.outputs
        msg = "Executor stream ended without a RunComplete"
        raise RuntimeError(msg)

    async def stream(
        self,
        graph: Any,
        *,
        inputs: list[dict[str, Any]] | None = None,
        **runtime_options: Any,
    ) -> AsyncIterator[Any]:
        """Yield ``StepResult.payload`` values only.

        The terminal ``RunComplete`` is intentionally NOT yielded -- this helper
        exists for consumers that process events incrementally and have no use for
        the end-of-run envelope. If you need to know when the run ends, use
        ``run()`` directly.
        """
        inner = self.run(graph, inputs=inputs or [], **runtime_options)
        try:
            async for item in inner:
                if isinstance(item, StepResult):
                    yield item.payload
        finally:
            await inner.aclose()
