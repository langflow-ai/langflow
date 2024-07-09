import asyncio
import os
import traceback
import types
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional
from uuid import UUID

from loguru import logger

from langflow.schema.data import Data
from langflow.services.base import Service
from langflow.services.tracing.base import BaseTracer
from langflow.services.tracing.schema import Log

if TYPE_CHECKING:
    from langflow.services.monitor.service import MonitorService
    from langflow.services.settings.service import SettingsService


class TracingService(Service):
    name = "tracing_service"

    def __init__(self, settings_service: "SettingsService", monitor_service: "MonitorService"):
        self.settings_service = settings_service
        self.monitor_service = monitor_service
        self.inputs: dict[str, dict] = defaultdict(dict)
        self.inputs_metadata: dict[str, dict] = defaultdict(dict)
        self.outputs: dict[str, dict] = defaultdict(dict)
        self.outputs_metadata: dict[str, dict] = defaultdict(dict)
        self.run_name: str | None = None
        self.run_id: UUID | None = None
        self.project_name = None
        self._tracers: dict[str, LangSmithTracer] = {}
        self._logs: dict[str, list[Log | dict[Any, Any]]] = defaultdict(list)
        self.logs_queue: asyncio.Queue = asyncio.Queue()
        self.running = False
        self.worker_task = None

    async def log_worker(self):
        while self.running or not self.logs_queue.empty():
            log_func, args = await self.logs_queue.get()
            try:
                await log_func(*args)
            except Exception as e:
                logger.error(f"Error processing log: {e}")
            finally:
                self.logs_queue.task_done()

    async def start(self):
        if self.running:
            return
        try:
            self.running = True
            self.worker_task = asyncio.create_task(self.log_worker())
        except Exception as e:
            logger.error(f"Error starting tracing service: {e}")

    async def flush(self):
        try:
            await self.logs_queue.join()
        except Exception as e:
            logger.error(f"Error flushing logs: {e}")

    async def stop(self):
        try:
            self.running = False
            await self.flush()
            # check the qeue is empty
            if not self.logs_queue.empty():
                await self.logs_queue.join()
            if self.worker_task:
                self.worker_task.cancel()
                self.worker_task = None

        except Exception as e:
            logger.error(f"Error stopping tracing service: {e}")

    def _reset_io(self):
        self.inputs = defaultdict(dict)
        self.inputs_metadata = defaultdict(dict)
        self.outputs = defaultdict(dict)
        self.outputs_metadata = defaultdict(dict)

    async def initialize_tracers(self):
        try:
            await self.start()
            self._initialize_langsmith_tracer()
        except Exception as e:
            logger.debug(f"Error initializing tracers: {e}")

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

    def set_run_id(self, run_id: UUID):
        self.run_id = run_id

    def _start_traces(
        self, trace_name: str, trace_type: str, inputs: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None
    ):
        self.inputs[trace_name] = inputs
        self.inputs_metadata[trace_name] = metadata or {}
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
                tracer.end_trace(
                    trace_name=trace_name, outputs=self.outputs[trace_name], error=error, logs=self._logs[trace_name]
                )
            except Exception as e:
                logger.error(f"Error ending trace {trace_name}: {e}")

    def _end_all_traces(self, outputs: dict, error: str | None = None):
        for tracer in self._tracers.values():
            if not tracer.ready:
                continue
            try:
                tracer.end(self.inputs, outputs=self.outputs, error=error, metadata=outputs)
            except Exception as e:
                logger.error(f"Error ending all traces: {e}")

    async def end(self, outputs: dict, error: str | None = None):
        self._end_all_traces(outputs, error)
        self._reset_io()
        await self.stop()

    def add_log(self, trace_name: str, log: Log):
        self._logs[trace_name].append(log)

    @asynccontextmanager
    async def trace_context(
        self,
        trace_name: str,
        trace_type: str,
        inputs: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
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

    def set_outputs(self, trace_name: str, outputs: Dict[str, Any], output_metadata: Dict[str, Any] | None = None):
        self.outputs[trace_name] |= outputs or {}
        self.outputs_metadata[trace_name] |= output_metadata or {}


class LangSmithTracer(BaseTracer):
    def __init__(self, trace_name: str, trace_type: str, project_name: str, trace_id: UUID):
        from langsmith.run_trees import RunTree

        self.trace_name = trace_name
        self.trace_type = trace_type
        self.project_name = project_name
        self.trace_id = trace_id
        try:
            self._run_tree = RunTree(
                project_name=self.project_name,
                name=self.trace_name,
                run_type=self.trace_type,
                id=self.trace_id,
            )
            self._run_tree.add_event({"name": "Start", "time": datetime.now(timezone.utc).isoformat()})
            self._children: dict[str, RunTree] = {}
            self._ready = self.setup_langsmith()
        except Exception as e:
            logger.debug(f"Error setting up LangSmith tracer: {e}")
            self._ready = False

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

    def add_trace(
        self, trace_name: str, trace_type: str, inputs: Dict[str, Any], metadata: Dict[str, Any] | None = None
    ):
        if not self._ready:
            return
        processed_inputs = {}
        if inputs:
            processed_inputs = self._convert_to_langchain_types(inputs)
        child = self._run_tree.create_child(
            name=trace_name,
            run_type=trace_type,  # type: ignore[arg-type]
            inputs=processed_inputs,
        )
        if metadata:
            child.add_metadata(self._convert_to_langchain_types(metadata))
        self._children[trace_name] = child
        self._child_link: dict[str, str] = {}

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
        elif isinstance(value, types.GeneratorType):
            # generator is not serializable, also we can't consume it
            value = str(value)
        return value

    def end_trace(
        self,
        trace_name: str,
        outputs: Dict[str, Any] | None = None,
        error: str | None = None,
        logs: list[Log | dict] = [],
    ):
        child = self._children[trace_name]
        raw_outputs = {}
        processed_outputs = {}
        if outputs:
            raw_outputs = outputs
            processed_outputs = self._convert_to_langchain_types(outputs)
        if logs:
            child.add_metadata(self._convert_to_langchain_types({"logs": {log.get("name"): log for log in logs}}))
        child.add_metadata(self._convert_to_langchain_types({"outputs": raw_outputs}))
        child.end(outputs=processed_outputs, error=error)
        if error:
            child.patch()
        else:
            child.post()
        self._child_link[trace_name] = child.get_url()

    def end(
        self,
        inputs: dict[str, Any],
        outputs: Dict[str, Any],
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self._run_tree.add_metadata({"inputs": inputs})
        if metadata:
            self._run_tree.add_metadata(metadata)
        self._run_tree.end(outputs=outputs, error=error)
        self._run_tree.post()
        self._run_link = self._run_tree.get_url()
