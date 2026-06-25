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

When a ``CapabilityService`` is wired in and not in passthrough mode, ``run()``
asks it to route each run to an executor kind (e.g. an isolated sandbox for
untrusted custom code) and strips capability-only metadata from the runtime
options before they reach the executor.
"""

from __future__ import annotations

from contextlib import aclosing
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from lfx.execution.partitioner import identity_partition
from lfx.execution.types import RunComplete, StepResult
from lfx.services.capability.protocols import RESERVED_CAPABILITY_RUNTIME_OPTION_KEYS

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from lfx.execution.registry import ExecutorRegistry
    from lfx.services.capability import CapabilityService


class Coordinator:
    """Routes graph runs through a registered ``Executor`` of the configured kind."""

    def __init__(
        self,
        *,
        registry: ExecutorRegistry,
        executor_kind: str = "in-process",
        capability_service: CapabilityService | None = None,
    ) -> None:
        self._registry = registry
        self._executor_kind = executor_kind
        self._capability_service = capability_service

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

        If a ``CapabilityService`` is configured and active, each unit is routed
        to the executor kind it selects, and capability-only metadata keys are
        removed from the runtime options before dispatch.

        ``identity_partition`` currently yields exactly one ``Unit``, so this emits a
        single terminal ``RunComplete``. A future partitioner returning multiple units
        would emit one ``RunComplete`` per unit; consumers relying on a single terminal
        envelope (notably ``run_to_completion``) would need updating first.
        """
        options = self._without_capability_metadata(runtime_options)
        units = identity_partition(graph, inputs=inputs, runtime_options=options)
        if self._capability_service is not None and not self._capability_service.is_passthrough:
            decision = self._capability_service.route(
                graph,
                user_id=self._context_value(graph, options, "user_id", "lfx_user_id"),
                flow_id=self._context_value(graph, options, "flow_id", "lfx_flow_id"),
                run_id=self._context_value(graph, options, "run_id", "lfx_run_id"),
                default_executor_kind=self._executor_kind,
                scopes=self._capability_scopes(options),
                runtime_options=options,
            )
            units = [
                replace(
                    unit,
                    executor_kind=decision.executor_kind,
                    runtime_options={
                        **self._without_capability_metadata(unit.runtime_options),
                        **decision.runtime_options,
                    },
                )
                for unit in units
            ]
        for unit in units:
            # Cascade cleanup: if our consumer aclose()s us, we aclose the executor
            # stream, which lets InProcessExecutor's try/finally aclose the underlying
            # graph generator. Without this, the executor stream is abandoned on
            # consumer aclose and only finalizes when CPython gets around to GC.
            executor = self._registry.get(unit.executor_kind or self._executor_kind)
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
        async with aclosing(self.run(graph, inputs=inputs, **runtime_options)) as stream:
            async for item in stream:
                if isinstance(item, RunComplete):
                    return item.outputs
        msg = "Executor stream ended without a RunComplete"
        raise RuntimeError(msg)

    async def stream(
        self,
        graph: Any,
        **runtime_options: Any,
    ) -> AsyncIterator[Any]:
        """Yield ``StepResult.payload`` values only.

        The terminal ``RunComplete`` is intentionally NOT yielded -- this helper
        exists for consumers that process events incrementally and have no use for
        the end-of-run envelope. If you need to know when the run ends, use
        ``run()`` directly.

        Note there is no ``inputs`` parameter here. The in-process executor's
        streaming path reads its inputs from ``runtime_options["initial_inputs"]``,
        not from the seam-level ``inputs`` list (which only the legacy passthrough
        in ``run_to_completion`` consumes). Pass ``initial_inputs=...`` to feed a
        streaming run.
        """
        async with aclosing(self.run(graph, inputs=[], **runtime_options)) as inner:
            async for item in inner:
                if isinstance(item, StepResult):
                    yield item.payload

    @staticmethod
    def _context_value(graph: Any, runtime_options: dict[str, Any], *names: str) -> str | None:
        for name in names:
            value = runtime_options.get(name)
            if value is not None:
                return str(value)
            value = getattr(graph, name, None)
            if value is not None:
                return str(value)
        return None

    @staticmethod
    def _capability_scopes(runtime_options: dict[str, Any]) -> Sequence[str]:
        scopes = runtime_options.get("capability_scopes", runtime_options.get("lfx_capability_scopes", ()))
        if scopes is None:
            return ()
        if isinstance(scopes, str):
            return (scopes,)
        return tuple(scopes)

    @staticmethod
    def _without_capability_metadata(runtime_options: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value for key, value in runtime_options.items() if key not in RESERVED_CAPABILITY_RUNTIME_OPTION_KEYS
        }
