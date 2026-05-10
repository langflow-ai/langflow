"""StepflowExecutor: bridge between the lfx execution seam and a Stepflow orchestrator.

The lfx ``Executor`` ABC accepts a ``Unit`` (graph + inputs + runtime options) and yields
``StepResult`` items terminated by a ``RunComplete``. This adapter:

1. Pulls a Langflow JSON workflow out of the unit (preferred path: caller passes the
   original JSON via ``runtime_options['langflow_json']``; fallback: re-serialize the
   in-memory ``lfx.Graph`` via ``graph.dump()`` if available).
2. Translates it to a Stepflow ``Flow`` using ``LangflowConverter``.
3. Submits the flow to a configured Stepflow orchestrator and streams step events back.

Submission is gated on configuration. If neither ``STEPFLOW_ENDPOINT`` is set nor an
explicit submitter is wired in, ``execute()`` raises so we don't silently lie about
running anything. Translation still works without a live orchestrator, which is what
the smoke test exercises.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

from lfx.execution.executor import Executor
from lfx.execution.types import RunComplete, StepResult

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lfx.execution.types import Unit


class StepflowExecutor(Executor):
    """Execute a Langflow graph by translating it to Stepflow and dispatching to an orchestrator.

    This is the wiring layer; it deliberately does not import ``stepflow_py`` at module
    import time so that environments without Stepflow installed can still load the
    package, list executors, and read settings.
    """

    kind = "stepflow"

    def __init__(self, *, endpoint: str | None = None) -> None:
        self._endpoint = endpoint or os.environ.get("STEPFLOW_ENDPOINT")

    async def execute(self, unit: Unit) -> AsyncIterator[StepResult | RunComplete]:
        flow = self._translate(unit)

        if not self._endpoint:
            msg = (
                "StepflowExecutor: no orchestrator endpoint configured. Set STEPFLOW_ENDPOINT or "
                "construct StepflowExecutor(endpoint=...). Translation succeeded; submission was skipped."
            )
            raise RuntimeError(msg)

        async for event in self._submit(flow, unit):
            yield event

    def translate(self, unit: Unit) -> Any:
        """Public translation hook so callers (and tests) can drive the converter without dispatching."""
        return self._translate(unit)

    def _translate(self, unit: Unit) -> Any:
        from langflow_stepflow.translation.translator import LangflowConverter

        langflow_json = unit.runtime_options.get("langflow_json")
        if langflow_json is None:
            langflow_json = self._dump_graph(unit.graph)

        if isinstance(langflow_json, str):
            langflow_json = json.loads(langflow_json)

        return LangflowConverter().convert(langflow_json)

    @staticmethod
    def _dump_graph(graph: Any) -> dict[str, Any]:
        # lfx graphs originated from JSON; most graph builders expose a ``dump`` method
        # that yields the same shape ``LangflowConverter`` expects. If a particular
        # graph implementation does not, callers can pre-serialize and pass via
        # runtime_options['langflow_json'] instead.
        for attr in ("dump", "to_dict", "to_json"):
            fn = getattr(graph, attr, None)
            if callable(fn):
                result = fn()
                if isinstance(result, str):
                    return json.loads(result)
                return result
        msg = (
            "StepflowExecutor needs a Langflow JSON workflow. Pass it explicitly via "
            "runtime_options['langflow_json'] or expose a dump()/to_dict() on the graph."
        )
        raise TypeError(msg)

    async def _submit(self, flow: Any, unit: Unit) -> AsyncIterator[StepResult | RunComplete]:
        # Real submission against a Stepflow orchestrator goes here. Kept narrow on
        # purpose: the surface area we need from stepflow_py is "submit a Flow, get an
        # async stream of step events". The exact API is in flux upstream; this MVP
        # leaves the call point obvious and isolated.
        from stepflow_py.client import OrchestratorClient  # noqa: PLC0415  -- lazy import

        client = OrchestratorClient(self._endpoint)
        outputs: list[Any] = []
        async for event in client.run_flow(flow, inputs=unit.inputs):
            yield StepResult(payload=event)
            if getattr(event, "is_terminal", False):
                outputs.append(event)
        yield RunComplete(outputs=outputs)
