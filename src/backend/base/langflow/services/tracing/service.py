from __future__ import annotations

import asyncio
import os
from collections import defaultdict
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from loguru import logger

from langflow.services.base import Service

if TYPE_CHECKING:
    from uuid import UUID

    from langchain.callbacks.base import BaseCallbackHandler

    from langflow.custom.custom_component.component import Component
    from langflow.graph.vertex.base import Vertex
    from langflow.services.settings.service import SettingsService
    from langflow.services.tracing.base import BaseTracer
    from langflow.services.tracing.schema import Log


def _get_langsmith_tracer():
    from langflow.services.tracing.langsmith import LangSmithTracer

    return LangSmithTracer


def _get_langwatch_tracer():
    from langflow.services.tracing.langwatch import LangWatchTracer

    return LangWatchTracer


def _get_langfuse_tracer():
    from langflow.services.tracing.langfuse import LangFuseTracer

    return LangFuseTracer


def _get_arize_phoenix_tracer():
    from langflow.services.tracing.arize_phoenix import ArizePhoenixTracer

    return ArizePhoenixTracer


def _get_opik_tracer():
    from langflow.services.tracing.opik import OpikTracer

    return OpikTracer


trace_context_var: ContextVar[TraceContext | None] = ContextVar("trace_context", default=None)
component_context_var: ContextVar[ComponentTraceContext | None] = ContextVar("component_trace_context", default=None)


class TraceContext:
    def __init__(
        self,
        run_id: UUID | None,
        run_name: str | None,
        project_name: str | None,
        user_id: str | None,
        session_id: str | None,
    ):
        self.run_id: UUID | None = run_id
        self.run_name: str | None = run_name
        self.project_name: str | None = project_name
        self.user_id: str | None = user_id
        self.session_id: str | None = session_id
        self.tracers: dict[str, BaseTracer] = {}
        self.all_inputs: dict[str, dict] = defaultdict(dict)
        self.all_outputs: dict[str, dict] = defaultdict(dict)

        self.traces_queue: asyncio.Queue = asyncio.Queue()
        self.running = False
        self.worker_task: asyncio.Task | None = None


class ComponentTraceContext:
    def __init__(
        self,
        trace_id: str,
        trace_name: str,
        trace_type: str,
        vertex: Vertex | None,
        inputs: dict[str, dict],
        metadata: dict[str, dict] | None = None,
    ):
        self.trace_id: str = trace_id
        self.trace_name: str = trace_name
        self.trace_type: str = trace_type
        self.vertex: Vertex | None = vertex
        self.inputs: dict[str, dict] = inputs
        self.inputs_metadata: dict[str, dict] = metadata or {}
        self.outputs: dict[str, dict] = defaultdict(dict)
        self.outputs_metadata: dict[str, dict] = defaultdict(dict)
        self.logs: dict[str, list[Log | dict[Any, Any]]] = defaultdict(list)


class TracingService(Service):
    """Tracing service.

    To trace a graph run:
        1. start_tracers: start a trace for a graph run
        2. with trace_component: start a sub-trace for a component build, three methods are available:
            - add_log
            - set_outputs
            - get_langchain_callbacks
        3. end_tracers: end the trace for a graph run

    check context var in public methods.
    """

    name = "tracing_service"

    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service
        self.deactivated = self.settings_service.settings.deactivate_tracing

    async def _trace_worker(self, trace_context: TraceContext) -> None:
        while trace_context.running or not trace_context.traces_queue.empty():
            trace_func, args = await trace_context.traces_queue.get()
            try:
                trace_func(*args)
            except Exception:  # noqa: BLE001
                logger.exception("Error processing trace_func")
            finally:
                trace_context.traces_queue.task_done()

    async def _start(self, trace_context: TraceContext) -> None:
        if trace_context.running or self.deactivated:
            return
        try:
            trace_context.running = True
            trace_context.worker_task = asyncio.create_task(self._trace_worker(trace_context))
        except Exception:  # noqa: BLE001
            logger.exception("Error starting tracing service")

    def _initialize_langsmith_tracer(self, trace_context: TraceContext) -> None:
        langsmith_tracer = _get_langsmith_tracer()
        trace_context.tracers["langsmith"] = langsmith_tracer(
            trace_name=trace_context.run_name,
            trace_type="chain",
            project_name=trace_context.project_name,
            trace_id=trace_context.run_id,
        )

    def _initialize_langwatch_tracer(self, trace_context: TraceContext) -> None:
        if self.deactivated:
            return
        if (
            "langwatch" not in trace_context.tracers
            or trace_context.tracers["langwatch"].trace_id != trace_context.run_id
        ):
            langwatch_tracer = _get_langwatch_tracer()
            trace_context.tracers["langwatch"] = langwatch_tracer(
                trace_name=trace_context.run_name,
                trace_type="chain",
                project_name=trace_context.project_name,
                trace_id=trace_context.run_id,
            )

    def _initialize_langfuse_tracer(self, trace_context: TraceContext) -> None:
        if self.deactivated:
            return
        langfuse_tracer = _get_langfuse_tracer()
        trace_context.tracers["langfuse"] = langfuse_tracer(
            trace_name=trace_context.run_name,
            trace_type="chain",
            project_name=trace_context.project_name,
            trace_id=trace_context.run_id,
            user_id=trace_context.user_id,
            session_id=trace_context.session_id,
        )

    def _initialize_arize_phoenix_tracer(self, trace_context: TraceContext) -> None:
        if self.deactivated:
            return
        arize_phoenix_tracer = _get_arize_phoenix_tracer()
        trace_context.tracers["arize_phoenix"] = arize_phoenix_tracer(
            trace_name=trace_context.run_name,
            trace_type="chain",
            project_name=trace_context.project_name,
            trace_id=trace_context.run_id,
        )

    def _initialize_opik_tracer(self, trace_context: TraceContext) -> None:
        if self.deactivated:
            return
        opik_tracer = _get_opik_tracer()
        trace_context.tracers["opik"] = opik_tracer(
            trace_name=trace_context.run_name,
            trace_type="chain",
            project_name=trace_context.project_name,
            trace_id=trace_context.run_id,
            user_id=trace_context.user_id,
            session_id=trace_context.session_id,
        )

    async def start_tracers(
        self,
        run_id: UUID,
        run_name: str,
        user_id: str | None,
        session_id: str | None,
        project_name: str | None = None,
    ) -> None:
        """Start a trace for a graph run.

        - create a trace context
        - start a worker for this trace context
        - initialize the tracers
        """
        if self.deactivated:
            return
        try:
            project_name = project_name or os.getenv("LANGCHAIN_PROJECT", "Langflow")
            trace_context = TraceContext(run_id, run_name, project_name, user_id, session_id)
            trace_context_var.set(trace_context)
            await self._start(trace_context)
            self._initialize_langsmith_tracer(trace_context)
            self._initialize_langwatch_tracer(trace_context)
            self._initialize_langfuse_tracer(trace_context)
            self._initialize_arize_phoenix_tracer(trace_context)
            self._initialize_opik_tracer(trace_context)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Error initializing tracers: {e}")

    async def _stop(self, trace_context: TraceContext) -> None:
        try:
            trace_context.running = False
            # check the qeue is empty
            if not trace_context.traces_queue.empty():
                await trace_context.traces_queue.join()
            if trace_context.worker_task:
                trace_context.worker_task.cancel()
                trace_context.worker_task = None

        except Exception:  # noqa: BLE001
            logger.exception("Error stopping tracing service")

    def _end_all_tracers(self, trace_context: TraceContext, outputs: dict, error: Exception | None = None) -> None:
        for tracer in trace_context.tracers.values():
            if tracer.ready:
                try:
                    # why all_inputs and all_outputs? why metadata=outputs?
                    tracer.end(
                        trace_context.all_inputs,
                        outputs=trace_context.all_outputs,
                        error=error,
                        metadata=outputs,
                    )
                except Exception:  # noqa: BLE001
                    logger.error("Error ending all traces")

    async def end_tracers(self, outputs: dict, error: Exception | None = None) -> None:
        """End the trace for a graph run.

        - stop worker for current trace_context
        - call end for all the tracers
        """
        if self.deactivated:
            return
        trace_context = trace_context_var.get()
        if trace_context is None:
            return
        await self._stop(trace_context)
        self._end_all_tracers(trace_context, outputs, error)

    @staticmethod
    def _cleanup_inputs(inputs: dict[str, Any]):
        inputs = inputs.copy()
        for key in inputs:
            if "api_key" in key:
                inputs[key] = "*****"  # avoid logging api_keys for security reasons
        return inputs

    def _start_component_traces(
        self,
        component_trace_context: ComponentTraceContext,
        trace_context: TraceContext,
    ) -> None:
        inputs = self._cleanup_inputs(component_trace_context.inputs)
        component_trace_context.inputs = inputs
        component_trace_context.inputs_metadata = component_trace_context.inputs_metadata or {}
        for tracer in trace_context.tracers.values():
            if not tracer.ready:
                continue
            try:
                tracer.add_trace(
                    component_trace_context.trace_id,
                    component_trace_context.trace_name,
                    component_trace_context.trace_type,
                    inputs,
                    component_trace_context.inputs_metadata,
                    component_trace_context.vertex,
                )
            except Exception:  # noqa: BLE001
                logger.exception(f"Error starting trace {component_trace_context.trace_name}")

    def _end_component_traces(
        self,
        component_trace_context: ComponentTraceContext,
        trace_context: TraceContext,
        error: Exception | None = None,
    ) -> None:
        for tracer in trace_context.tracers.values():
            if tracer.ready:
                try:
                    tracer.end_trace(
                        trace_id=component_trace_context.trace_id,
                        trace_name=component_trace_context.trace_name,
                        outputs=trace_context.all_outputs[component_trace_context.trace_name],
                        error=error,
                        logs=component_trace_context.logs[component_trace_context.trace_name],
                    )
                except Exception:  # noqa: BLE001
                    logger.exception(f"Error ending trace {component_trace_context.trace_name}")

    @asynccontextmanager
    async def trace_component(
        self,
        component: Component,
        trace_name: str,
        inputs: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ):
        """Trace a component.

        @param component: the component to trace
        @param trace_name: component name + component id
        @param inputs: the inputs to the component
        @param metadata: the metadata to the component
        """
        if self.deactivated:
            yield self
            return
        trace_id = trace_name
        if component._vertex:
            trace_id = component._vertex.id
        trace_type = component.trace_type
        component_trace_context = ComponentTraceContext(
            trace_id, trace_name, trace_type, component._vertex, inputs, metadata
        )
        component_context_var.set(component_trace_context)
        trace_context = trace_context_var.get()
        if trace_context is None:
            msg = "called trace_component but no trace context found"
            raise RuntimeError(msg)
        trace_context.all_inputs[trace_name] |= inputs or {}
        await trace_context.traces_queue.put((self._start_component_traces, (component_trace_context, trace_context)))
        try:
            yield self
        except Exception as e:
            await trace_context.traces_queue.put(
                (self._end_component_traces, (component_trace_context, trace_context, e))
            )
            raise
        else:
            await trace_context.traces_queue.put(
                (self._end_component_traces, (component_trace_context, trace_context, None))
            )

    @property
    def project_name(self):
        if self.deactivated:
            return os.getenv("LANGCHAIN_PROJECT", "Langflow")
        trace_context = trace_context_var.get()
        if trace_context is None:
            msg = "called project_name but no trace context found"
            raise RuntimeError(msg)
        return trace_context.project_name

    def add_log(self, trace_name: str, log: Log) -> None:
        """Add a log to the current component trace context."""
        if self.deactivated:
            return
        component_context = component_context_var.get()
        if component_context is None:
            msg = "called add_log but no component context found"
            raise RuntimeError(msg)
        component_context.logs[trace_name].append(log)

    def set_outputs(
        self,
        trace_name: str,
        outputs: dict[str, Any],
        output_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Set the outputs for the current component trace context."""
        if self.deactivated:
            return
        component_context = component_context_var.get()
        if component_context is None:
            msg = "called set_outputs but no component context found"
            raise RuntimeError(msg)
        component_context.outputs[trace_name] |= outputs or {}
        component_context.outputs_metadata[trace_name] |= output_metadata or {}
        trace_context = trace_context_var.get()
        if trace_context is None:
            msg = "called set_outputs but no trace context found"
            raise RuntimeError(msg)
        trace_context.all_outputs[trace_name] |= outputs or {}

    def get_tracer(self, tracer_name: str) -> BaseTracer | None:
        trace_context = trace_context_var.get()
        if trace_context is None:
            msg = "called get_tracer but no trace context found"
            raise RuntimeError(msg)
        return trace_context.tracers.get(tracer_name)

    def get_langchain_callbacks(self) -> list[BaseCallbackHandler]:
        if self.deactivated:
            return []
        callbacks = []
        trace_context = trace_context_var.get()
        if trace_context is None:
            msg = "called get_langchain_callbacks but no trace context found"
            raise RuntimeError(msg)
        for tracer in trace_context.tracers.values():
            if not tracer.ready:  # type: ignore[truthy-function]
                continue
            langchain_callback = tracer.get_langchain_callback()
            if langchain_callback:
                callbacks.append(langchain_callback)
        return callbacks
