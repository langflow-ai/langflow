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
import logging
import os
import sys
from typing import TYPE_CHECKING, Any

from lfx.execution.executor import Executor
from lfx.execution.types import RunComplete, StepResult

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lfx.execution.types import Unit

logger = logging.getLogger(__name__)


def _value_to_python(result_value: Any) -> Any:
    """Convert a protobuf Struct ``Value`` (or already-native value) to a plain object."""
    if result_value is None:
        return None
    if isinstance(result_value, str | int | float | bool | dict | list):
        return result_value
    try:
        from google.protobuf.json_format import MessageToDict

        return MessageToDict(result_value)
    except Exception:  # noqa: BLE001 - any non-Value payload degrades to its repr below
        return result_value


def _coerce_text(output: Any) -> str:
    """Best-effort extraction of a chat message string from a flow output blob."""
    if output is None:
        return ""
    if isinstance(output, str):
        return output
    if isinstance(output, dict):
        for key in ("text", "message", "result"):
            value = output.get(key)
            if isinstance(value, str):
                return value
    return str(output)


def _build_messages(text: str) -> list[Any]:
    """Wrap extracted text in a ChatOutputResponse so text-extraction paths find it."""
    if not text:
        return []
    from lfx.utils.schemas import ChatOutputResponse

    return [ChatOutputResponse(message=text, type="text")]


class StepflowExecutor(Executor):
    """Execute a Langflow flow by translating it to Stepflow and running it via stepflow_py.

    Args:
        endpoint: If set, connect to an already-running orchestrator at this address.
            Otherwise boot a local orchestrator via ``StepflowClient.local`` using
            ``config`` (or the default config below).
        config: Optional ``StepflowConfig`` controlling plugins/routes for local mode.
            If omitted, a default is built that registers the langflow worker.
        worker_command: Command used by the default config to launch the worker.
            Defaults to ``[sys.executable, "-m", "langflow_stepflow.worker"]``.
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
        # The seam delivers inputs in the lfx run-path shape ({INPUT_FIELD_NAME: ...});
        # the translated flow reads $.message / $.session_id, so map before submitting.
        # The original lfx input is preserved separately for RunOutputs.inputs.
        run_input = self._build_run_input(unit, 0)
        original_input = unit.inputs[0] if unit.inputs else {}

        if self._endpoint:
            # Remote-orchestrator path. Kept narrow on purpose: the connect/auth surface
            # is still moving upstream, so this hands off to whatever ``connect`` looks
            # like at runtime rather than baking in assumptions.
            from stepflow_py.client import StepflowClient

            async with await StepflowClient.connect(self._endpoint) as client:
                async for item in self._run_through(client, flow_dict, run_input, original_input):
                    yield item
            return

        from stepflow_py.client import StepflowClient

        config = self._config or self._default_config()
        async with StepflowClient.local(config) as client:
            async for item in self._run_through(client, flow_dict, run_input, original_input):
                yield item

    def _build_run_input(self, unit: Unit, index: int = 0) -> dict[str, Any]:
        """Map an lfx run-path input dict to the Stepflow run input the flow expects.

        The seam delivers inputs as ``[{INPUT_FIELD_NAME: <value>}]`` and carries
        ``session_id`` separately in ``runtime_options`` (set by ``Graph.arun``). The
        translated flow reads ``$.message`` (ChatInput/passthrough) and ``$.session_id``
        (Memory/Agent), so both must be surfaced at the top level of the submitted input.
        """
        from lfx.schema.schema import INPUT_FIELD_NAME

        raw = unit.inputs[index] if unit.inputs and index < len(unit.inputs) else {}
        payload = {key: value for key, value in raw.items() if key != INPUT_FIELD_NAME}
        if INPUT_FIELD_NAME in raw:
            payload["message"] = raw[INPUT_FIELD_NAME]
        # Mirror process.py's effective_session_id semantics: always present, "" when unset.
        payload["session_id"] = unit.runtime_options.get("session_id") or ""
        return payload

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
        run_input: dict[str, Any],
        original_input: dict[str, Any],
    ) -> AsyncIterator[StepResult | RunComplete]:
        store_resp = await client.store_flow(flow_dict)
        run_resp = await client.submit(store_resp.flow_id, run_input)
        run_id = run_resp.summary.run_id

        # Raw events are streamed as StepResult for the event_manager/streaming path; we
        # only need the terminal status here to decide success vs failure.
        status: Any = None
        async for event in client.status_events(run_id, include_results=True):
            yield StepResult(payload=event)
            if event.HasField("run_completed"):
                status = event.run_completed.status
                break

        # A failed/cancelled run must fail loud, like the in-process seam; otherwise the
        # caller can't tell an empty success from a failure.
        self._raise_for_failed_status(status, run_id)

        # The run's output rides on the per-item results, not the status stream: a single
        # submit() run emits no item_completed event, so fetch the results explicitly once
        # the run is terminal (see StepflowClient.submit / get_run_items). get_run_items
        # already returns native dicts (MessageToDict), so each item's "output" is plain.
        items = await client.get_run_items(run_id)
        if len(items) > 1:
            # execute() submits a single input today, so only item 0 is expected. Surface
            # the drop rather than silently swallowing extra items if that ever changes.
            logger.warning(
                "Stepflow run %s produced %d item results; only index 0 is mapped "
                "(multi-item submission is not yet supported).",
                run_id,
                len(items),
            )

        result_value = items[0].get("output") if items else None
        yield RunComplete(outputs=[self._to_run_outputs(result_value, original_input)])

    @staticmethod
    def _raise_for_failed_status(status: Any, run_id: str) -> None:
        """Raise if the run reached a terminal non-success state.

        ``Graph.arun`` is expected to fail loud on a failed run; the stepflow backend must
        match that rather than returning a success-shaped empty ``RunOutputs``. A ``None``
        status (stream ended without a terminal event) is left to the coordinator.
        """
        from stepflow_py.proto import common_pb2

        completed = common_pb2.ExecutionStatus.EXECUTION_STATUS_COMPLETED
        if status is not None and status != completed:
            from langflow_stepflow.exceptions import ExecutionError

            name = common_pb2.ExecutionStatus.Name(status)
            msg = f"Stepflow run {run_id} ended with non-success status: {name}"
            raise ExecutionError(msg)

    @staticmethod
    def _to_run_outputs(result_value: Any, run_input: dict[str, Any]) -> Any:
        """Map a Stepflow item result (protobuf Value) into the lfx RunOutputs contract.

        ``Graph.arun`` returns ``list[RunOutputs]`` and downstream /run serializers read
        ``RunOutputs.outputs[i]`` as ``ResultData``. We surface the run's output value
        under the ChatOutput "message" output so the existing extraction finds it, and keep
        the original lfx input dict on ``RunOutputs.inputs`` (matching _arun_legacy).
        """
        from lfx.graph.schema import ResultData, RunOutputs
        from lfx.schema.schema import OutputValue

        output = _value_to_python(result_value)
        text = _coerce_text(output)
        message = output if isinstance(output, dict | list | str) else text

        result_data = ResultData(
            results={"message": output},
            outputs={"message": OutputValue(message=message, type="text")},
            messages=_build_messages(text),
        )
        return RunOutputs(inputs=run_input, outputs=[result_data])

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
        return sys.executable, ["-m", "langflow_stepflow.worker"]

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
