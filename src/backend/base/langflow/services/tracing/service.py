import os
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict

from langchain.callbacks.tracers.langchain import wait_for_all_tracers
from loguru import logger

from langflow.schema.data import Data
from langflow.services.base import Service
from langflow.services.tracing.schema import Log

if TYPE_CHECKING:
    from langflow.services.monitor.service import MonitorService
    from langflow.services.settings.service import SettingsService


class TracingService(Service):
    name = "tracing_service"

    def __init__(self, settings_service: "SettingsService", monitor_service: "MonitorService"):
        self.settings_service = settings_service
        self.monitor_service = monitor_service
        self.inputs = {}
        self.outputs = {}
        self.outputs_metadata = {}
        self.run_name = None
        self.run_id = None
        self.project_name = None
        self._tracers: dict[str, LangSmithTracer] = {}

    def _reset_io(self):
        self.inputs = {}
        self.outputs = {}

    def initialize_tracers(self):
        self._initialize_langsmith_tracer()

    def _initialize_langsmith_tracer(self):
        project_name = os.getenv("LANGCHAIN_PROJECT", "Langflow")
        self.project_name = project_name
        self._tracers["langsmith"] = LangSmithTracer(
            trace_name=self.run_name,
            trace_type="chain",
            project_name=self.project_name,
            trace_id=self.run_id,
        )

    def set_run_name(self, name: str):
        self.run_name = name

    def set_run_id(self, run_id: str):
        self.run_id = run_id

    def _start_traces(self, trace_name: str, trace_type: str, inputs: Dict[str, Any], metadata: Dict[str, Any] = None):
        for tracer in self._tracers.values():
            if not tracer.ready:
                continue
            try:
                tracer.add_trace(trace_name, trace_type, inputs, metadata)
            except Exception as e:
                logger.error(f"Error starting trace {trace_name}: {e}")

    def _end_traces(self, trace_name: str, error: str | None = None):
        for tracer in self._tracers.values():
            if not tracer.ready:
                continue
            try:
                tracer.end_trace(trace_name=trace_name, outputs=self.outputs, error=error)
            except Exception as e:
                logger.error(f"Error ending trace {trace_name}: {e}")

    def _end_all_traces(self, outputs: dict[str, Any], error: str | None = None):
        for tracer in self._tracers.values():
            if not tracer.ready:
                continue
            tracer.end(outputs=outputs, error=error)

    async def end(self, outputs: dict[str, Any] | None = None, error: str | None = None):
        self._end_all_traces(outputs, error)
        self._reset_io()

    async def add_log(self, trace_name: str, log: Log):
        for tracer in self._tracers.values():
            if not tracer.ready:
                continue
            try:
                tracer.add_log(trace_name, log)
            except Exception as e:
                logger.error(f"Error adding log to trace {trace_name}: {e}")

    @contextmanager
    def trace_context(
        self, trace_name: str, trace_type: str, inputs: Dict[str, Any] = None, metadata: Dict[str, Any] = None
    ):
        self._start_traces(trace_name, trace_type, inputs, metadata)
        try:
            yield self
        except Exception as e:
            tb = traceback.format_exc()
            error_message = f"{e.__class__.__name__}: {e}\n\n{tb}"
            self._end_traces(trace_name, error_message)
            raise e
        finally:
            self._end_traces(trace_name, None)
            self._reset_io()

    def set_outputs(self, outputs: Dict[str, Any], output_metadata: Dict[str, Any] = None):
        self.outputs |= outputs or {}
        self.outputs_metadata |= output_metadata or {}


class LangSmithTracer:
    def __init__(self, trace_name: str, trace_type: str, project_name: str, trace_id: str):
        from langsmith.run_trees import RunTree

        self.trace_name = trace_name
        self.trace_type = trace_type
        self.project_name = project_name
        self.trace_id = trace_id
        self._run_tree = RunTree(
            project_name=self.project_name,
            name=self.trace_name,
            run_type=self.trace_type,
            id=self.trace_id,
        )
        self._children: dict[str, RunTree] = {}
        self._ready = self.setup_langsmith()

    @property
    def ready(self):
        return self._ready

    def setup_langsmith(self):
        try:
            from langsmith import Client

            self._client = Client()
        except ImportError:
            logger.error("Could not import langsmith. Please install it with `pip install langsmith`.")
            return False
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        return True

    def add_trace(self, trace_name: str, trace_type: str, inputs: Dict[str, Any], metadata: Dict[str, Any] = None):
        if not self._ready:
            return
        raw_inputs = {}
        processed_inputs = {}
        if inputs:
            raw_inputs = inputs.copy()
            raw_inputs |= metadata or {}
            processed_inputs = self._convert_to_langchain_types(inputs)
        child = self._run_tree.create_child(
            name=trace_name,
            run_type=trace_type,
            inputs=processed_inputs,
        )
        if metadata:
            child.add_metadata(raw_inputs)
        self._children[trace_name] = child

    def _convert_to_langchain_types(self, io_dict: Dict[str, Any]):
        converted = {}
        for key, value in io_dict.items():
            converted[key] = self._convert_to_langchain_type(value)
        return converted

    def _convert_to_langchain_type(self, value):
        from langflow.schema.message import Message

        if isinstance(value, dict):
            for key, _value in value.copy().items():
                _value = self._convert_to_langchain_type(_value)
                value[key] = _value
        elif isinstance(value, list):
            value = [self._convert_to_langchain_type(v) for v in value]
        elif isinstance(value, Message):
            if "prompt" in value:
                value = value.load_lc_prompt()
            elif value.sender:
                value = value.to_lc_message()
            else:
                value = value.to_lc_document()
        elif isinstance(value, Data):
            value = value.to_lc_document()
        return value

    def end_trace(self, trace_name: str, outputs: Dict[str, Any] = None, error: str = None):
        child = self._children[trace_name]
        raw_outputs = {}
        processed_outputs = {}
        if outputs:
            raw_outputs = outputs
            processed_outputs = self._convert_to_langchain_types(outputs)
        child.add_metadata({"outputs": raw_outputs})
        child.end(outputs=processed_outputs, error=error)
        if error:
            child.patch()
        else:
            child.post()
        self._child_link[trace_name] = child.get_url()

    def add_log(self, trace_name: str, log: Log):
        log_dict = {"name": log.name, "time": datetime.now(timezone.utc).isoformat(), "message": log.message}
        self._children[trace_name].add_event(log_dict)

    def end(self, outputs: Dict[str, Any], error: str | None = None):
        self._run_tree.end(outputs=outputs, error=error)
        self._run_tree.post()
        wait_for_all_tracers()
        self._run_link = self._run_tree.get_url()
