"""StepflowExecutor: bridge between the lfx execution seam and a Stepflow orchestrator.

The lfx ``Executor`` ABC accepts a ``Unit`` (graph + inputs + runtime options) and yields
``StepResult`` items terminated by a ``RunComplete``. This adapter:

1. Translates the Langflow flow into a Stepflow ``Flow`` (preferred input:
   ``runtime_options['langflow_json']``; fallback: ``graph.dump()``/``to_dict()``).
2. Boots a local Stepflow orchestrator (default) or talks to one at ``STEPFLOW_ENDPOINT``,
   stores the translated flow, kicks off a run, and streams status events back as
   ``StepResult`` payloads.
3. Yields a final ``RunComplete`` with whatever the orchestrator considered the run's
   outputs.

The default orchestrator config wires ``/builtin`` to the in-process builtin plugin and
``/langflow`` to a gRPC worker launched as ``python -m langflow_stepflow.worker``. Both
are overridable: pass a prebuilt ``StepflowConfig`` to ``__init__`` if you want a
different topology (e.g. an externally managed worker pool).
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
    """Execute a Langflow flow by translating it to Stepflow and running it via stepflow_py.

    Args:
        endpoint: If set, connect to an already-running orchestrator at this address.
            Otherwise boot a local orchestrator via ``StepflowClient.local`` using
            ``config`` (or the default config below).
        config: Optional ``StepflowConfig`` controlling plugins/routes for local mode.
            If omitted, a default is built that registers the langflow worker.
        worker_command: Command used by the default config to launch the worker.
            Defaults to ``["uv", "run", "--with", "stepflow-py", "python", "-m",
            "langflow_stepflow.worker"]``.
    """

    kind = "stepflow"

    def __init__(
        self,
        *,
        endpoint: str | None = None,
        config: Any = None,
        worker_command: list[str] | None = None,
    ) -> None:
        self._endpoint = endpoint or os.environ.get("STEPFLOW_ENDPOINT")
        self._config = config
        self._worker_command = worker_command

    async def execute(self, unit: Unit) -> AsyncIterator[StepResult | RunComplete]:
        flow_dict = self._translate_to_dict(unit)
        input_payload = unit.inputs[0] if unit.inputs else {}

        if self._endpoint:
            # Remote-orchestrator path. Kept narrow on purpose: the connect/auth surface
            # is still moving upstream, so this hands off to whatever ``connect`` looks
            # like at runtime rather than baking in assumptions.
            from stepflow_py.client import StepflowClient

            async with await StepflowClient.connect(self._endpoint) as client:
                async for item in self._run_through(client, flow_dict, input_payload):
                    yield item
            return

        from stepflow_py.client import StepflowClient

        config = self._config or self._default_config()
        async with StepflowClient.local(config) as client:
            async for item in self._run_through(client, flow_dict, input_payload):
                yield item

    def translate(self, unit: Unit) -> Any:
        """Public translation hook so callers (and tests) can drive the converter alone."""
        return self._translate(unit)

    def _translate(self, unit: Unit) -> Any:
        from langflow_stepflow.translation.translator import LangflowConverter

        langflow_json = unit.runtime_options.get("langflow_json")
        if langflow_json is None:
            langflow_json = self._dump_graph(unit.graph)
        if isinstance(langflow_json, str):
            langflow_json = json.loads(langflow_json)
        return LangflowConverter().convert(langflow_json)

    def _translate_to_dict(self, unit: Unit) -> dict[str, Any]:
        import msgspec

        return msgspec.to_builtins(self._translate(unit))

    async def _run_through(
        self,
        client: Any,
        flow_dict: dict[str, Any],
        input_payload: dict[str, Any],
    ) -> AsyncIterator[StepResult | RunComplete]:
        store_resp = await client.store_flow(flow_dict)
        run_resp = await client.submit(store_resp.flow_id, input_payload)
        run_id = run_resp.summary.run_id

        outputs: list[Any] = []
        async for event in client.status_events(run_id, include_results=True):
            yield StepResult(payload=event)
            if event.HasField("run_completed"):
                outputs.append(event.run_completed)
                break
        yield RunComplete(outputs=outputs)

    def _default_config(self) -> Any:
        from stepflow_py.config import (
            BuiltinPluginConfig,
            GrpcPluginConfig,
            InMemoryStoreConfig,
            RouteRule,
            StepflowConfig,
        )

        command, args = self._worker_invocation()
        return StepflowConfig(
            plugins={
                "builtin": BuiltinPluginConfig(),
                "langflow": GrpcPluginConfig(command=command, args=args, queueName="langflow"),
            },
            routes={
                "/builtin": [RouteRule(plugin="builtin")],
                "/langflow": [RouteRule(plugin="langflow")],
            },
            storageConfig=InMemoryStoreConfig(),
        )

    def _worker_invocation(self) -> tuple[str, list[str]]:
        if self._worker_command:
            return self._worker_command[0], list(self._worker_command[1:])
        return "uv", ["run", "--with", "stepflow-py", "python", "-m", "langflow_stepflow.worker"]

    @staticmethod
    def _dump_graph(graph: Any) -> dict[str, Any]:
        for attr in ("dump", "to_dict", "to_json"):
            fn = getattr(graph, attr, None)
            if callable(fn):
                result = fn()
                return json.loads(result) if isinstance(result, str) else result
        msg = (
            "StepflowExecutor needs a Langflow JSON workflow. Pass it explicitly via "
            "runtime_options['langflow_json'] or expose dump()/to_dict() on the graph."
        )
        raise TypeError(msg)
