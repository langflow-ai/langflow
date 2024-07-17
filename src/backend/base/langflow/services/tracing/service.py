import asyncio
import os
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Dict, Optional
from uuid import UUID

from loguru import logger

from langflow.services.base import Service
from langflow.services.tracing.base import BaseTracer
from langflow.services.tracing.schema import Log

if TYPE_CHECKING:
    from langflow.custom.custom_component.component import Component
    from langflow.graph.vertex.base import Vertex
    from langflow.services.monitor.service import MonitorService
    from langflow.services.settings.service import SettingsService


def _get_langsmith_tracer():
    from langflow.services.tracing.langsmith import LangSmithTracer

    return LangSmithTracer


def _get_langwatch_tracer():
    from langflow.services.tracing.langwatch import LangWatchTracer

    return LangWatchTracer


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
        self._tracers: dict[str, BaseTracer] = {}
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
            self._initialize_langwatch_tracer()
        except Exception as e:
            logger.debug(f"Error initializing tracers: {e}")

    def _initialize_langsmith_tracer(self):
        project_name = os.getenv("LANGCHAIN_PROJECT", "Langflow")
        self.project_name = project_name
        langsmith_tracer = _get_langsmith_tracer()
        self._tracers["langsmith"] = langsmith_tracer(
            trace_name=self.run_name,
            trace_type="chain",
            project_name=self.project_name,
            trace_id=self.run_id,
        )

    def _initialize_langwatch_tracer(self):
        if (
            os.getenv("LANGWATCH_API_KEY")
            and "langwatch" not in self._tracers
            or self._tracers["langwatch"].trace_id != self.run_id  # type: ignore
        ):
            langwatch_tracer = _get_langwatch_tracer()
            self._tracers["langwatch"] = langwatch_tracer(
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
        self,
        trace_id: str,
        trace_name: str,
        trace_type: str,
        inputs: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        vertex: Optional["Vertex"] = None,
    ):
        inputs = self._cleanup_inputs(inputs)
        self.inputs[trace_name] = inputs
        self.inputs_metadata[trace_name] = metadata or {}
        for tracer in self._tracers.values():
            if not tracer.ready:  # type: ignore
                continue
            try:
                tracer.add_trace(trace_id, trace_name, trace_type, inputs, metadata, vertex)
            except Exception as e:
                logger.error(f"Error starting trace {trace_name}: {e}")

    def _end_traces(self, trace_id: str, trace_name: str, error: Exception | None = None):
        for tracer in self._tracers.values():
            if not tracer.ready:  # type: ignore
                continue
            try:
                tracer.end_trace(
                    trace_id=trace_id,
                    trace_name=trace_name,
                    outputs=self.outputs[trace_name],
                    error=error,
                    logs=self._logs[trace_name],
                )
            except Exception as e:
                logger.error(f"Error ending trace {trace_name}: {e}")

    def _end_all_traces(self, outputs: dict, error: Exception | None = None):
        for tracer in self._tracers.values():
            if not tracer.ready:  # type: ignore
                continue
            try:
                tracer.end(self.inputs, outputs=self.outputs, error=error, metadata=outputs)
            except Exception as e:
                logger.error(f"Error ending all traces: {e}")

    async def end(self, outputs: dict, error: Exception | None = None):
        self._end_all_traces(outputs, error)
        self._reset_io()
        await self.stop()

    def add_log(self, trace_name: str, log: Log):
        self._logs[trace_name].append(log)

    @asynccontextmanager
    async def trace_context(
        self,
        component: "Component",
        trace_name: str,
        inputs: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ):
        trace_id = trace_name
        if component.vertex:
            trace_id = component.vertex.id
        trace_type = component.trace_type
        self._start_traces(
            trace_id,
            trace_name,
            trace_type,
            self._cleanup_inputs(inputs),
            metadata,
            component.vertex,
        )
        try:
            yield self
        except Exception as e:
            self._end_traces(trace_id, trace_name, e)
            raise e
        finally:
            self._end_traces(trace_id, trace_name, None)
            self._reset_io()

    def set_outputs(
        self,
        trace_name: str,
        outputs: Dict[str, Any],
        output_metadata: Dict[str, Any] | None = None,
    ):
        self.outputs[trace_name] |= outputs or {}
        self.outputs_metadata[trace_name] |= output_metadata or {}

    def _cleanup_inputs(self, inputs: Dict[str, Any]):
        inputs = inputs.copy()
        for key in inputs.keys():
            if "api_key" in key:
                inputs[key] = "*****"  # avoid logging api_keys for security reasons
        return inputs
