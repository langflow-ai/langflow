import asyncio
import os
import traceback
import types
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional, cast
from uuid import UUID

from loguru import logger

from langflow.schema.data import Data
from langflow.services.base import Service
from langflow.services.tracing.base import BaseTracer
from langflow.services.tracing.schema import Log

if TYPE_CHECKING:
    from langflow.services.monitor.service import MonitorService
    from langflow.services.settings.service import SettingsService
    from langflow.custom.custom_component.component import Component
    from langflow.graph.vertex.base import Vertex
    from langwatch.tracer import ContextSpan
    from langwatch.types import SpanTypes


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
        self._tracers["langsmith"] = LangSmithTracer(
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
            self._tracers["langwatch"] = LangWatchTracer(
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
        self,
        trace_id: str,
        trace_name: str,
        trace_type: str,
        inputs: Dict[str, Any],
        metadata: Dict[str, Any] | None = None,
        vertex: Optional["Vertex"] = None,
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
        trace_id: str,
        trace_name: str,
        outputs: Dict[str, Any] | None = None,
        error: Exception | None = None,
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
        child.end(outputs=processed_outputs, error=self._error_to_string(error))
        if error:
            child.patch()
        else:
            child.post()
        self._child_link[trace_name] = child.get_url()

    def _error_to_string(self, error: Optional[Exception]):
        error_message = None
        if error:
            string_stacktrace = traceback.format_exception(error)
            error_message = f"{error.__class__.__name__}: {error}\n\n{string_stacktrace}"
        return error_message

    def end(
        self,
        inputs: dict[str, Any],
        outputs: Dict[str, Any],
        error: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self._run_tree.add_metadata({"inputs": inputs})
        if metadata:
            self._run_tree.add_metadata(metadata)
        self._run_tree.end(outputs=outputs, error=self._error_to_string(error))
        self._run_tree.post()
        self._run_link = self._run_tree.get_url()


class LangWatchTracer(BaseTracer):
    flow_id: str

    def __init__(self, trace_name: str, trace_type: str, project_name: str, trace_id: UUID):
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.project_name = project_name
        self.trace_id = trace_id
        self.flow_id = trace_name.split(" - ")[-1]

        try:
            self._ready = self.setup_langwatch()

            # import after setting up langwatch so we are sure to be available
            import nanoid  # type: ignore

            self.trace = self._client.trace(
                trace_id=str(self.trace_id),
            )
            self.spans: dict[str, "ContextSpan"] = {}

            name_without_id = " - ".join(trace_name.split(" - ")[0:-1])
            self.trace.root_span.update(
                span_id=f"{self.flow_id}-{nanoid.generate(size=6)}",  # nanoid to make the span_id globally unique, which is required for LangWatch for now
                name=name_without_id,
                type=self._convert_trace_type(trace_type),
            )
        except Exception as e:
            logger.debug(f"Error setting up LangWatch tracer: {e}")
            self._ready = False

    @property
    def ready(self):
        return self._ready

    def setup_langwatch(self):
        try:
            import langwatch

            self._client = langwatch
        except ImportError:
            logger.error("Could not import langwatch. Please install it with `pip install langwatch`.")
            return False
        return True

    def _convert_trace_type(self, trace_type: str):
        trace_type_: "SpanTypes" = (
            cast("SpanTypes", trace_type)
            if trace_type in ["span", "llm", "chain", "tool", "agent", "guardrail", "rag"]
            else "span"
        )
        return trace_type_

    def add_trace(
        self,
        trace_id: str,
        trace_name: str,
        trace_type: str,
        inputs: Dict[str, Any],
        metadata: Dict[str, Any] | None = None,
        vertex: Optional["Vertex"] = None,
    ):
        import nanoid

        # If user is not using session_id, then it becomes the same as flow_id, but
        # we don't want to have an infinite thread with all the flow messages
        if "session_id" in inputs and inputs["session_id"] != self.flow_id:
            self.trace.update(metadata=(self.trace.metadata or {}) | {"thread_id": inputs["session_id"]})

        name_without_id = " (".join(trace_name.split(" (")[0:-1])

        trace_type_ = self._convert_trace_type(trace_type)
        self.spans[trace_id] = self.trace.span(
            span_id=f"{trace_id}-{nanoid.generate(size=6)}",  # Add a nanoid to make the span_id globally unique, which is required for LangWatch for now
            name=name_without_id,
            type=trace_type_,
            parent=(
                [span for key, span in self.spans.items() for edge in vertex.incoming_edges if key == edge.source_id][
                    -1
                ]
                if vertex and len(vertex.incoming_edges) > 0
                else self.trace.root_span
            ),
            input=self._convert_to_langwatch_types(inputs),
        )

        if trace_type_ == "llm" and "model_name" in inputs:
            self.spans[trace_id].update(model=inputs["model_name"])

    def end_trace(
        self,
        trace_id: str,
        trace_name: str,
        outputs: Dict[str, Any] | None = None,
        error: Exception | None = None,
        logs: list[Log | dict] = [],
    ):
        if self.spans.get(trace_id):
            # Workaround for when model is used just as a component not actually called as an LLM,
            # to prevent LangWatch from calculating the cost based on it when it was in fact never called
            if (
                self.spans[trace_id].type == "llm"
                and outputs
                and "model_output" in outputs
                and "text_output" not in outputs
            ):
                self.spans[trace_id].update(metrics={"prompt_tokens": 0, "completion_tokens": 0})

            self.spans[trace_id].end(output=self._convert_to_langwatch_types(outputs), error=error)

    def end(
        self,
        inputs: dict[str, Any],
        outputs: Dict[str, Any],
        error: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.trace.root_span.end(
            input=self._convert_to_langwatch_types(inputs),
            output=self._convert_to_langwatch_types(outputs),
            error=error,
        )

        if metadata and "flow_name" in metadata:
            self.trace.update(metadata=(self.trace.metadata or {}) | {"labels": [f"Flow: {metadata['flow_name']}"]})
        self.trace.deferred_send_spans()

    def _convert_to_langwatch_types(self, io_dict: Optional[Dict[str, Any]]):
        from langwatch.utils import autoconvert_typed_values

        if io_dict is None:
            return None
        converted = {}
        for key, value in io_dict.items():
            converted[key] = self._convert_to_langwatch_type(value)
        return autoconvert_typed_values(converted)

    def _convert_to_langwatch_type(self, value):
        from langflow.schema.message import Message, BaseMessage
        from langwatch.langchain import (
            langchain_messages_to_chat_messages,
            langchain_message_to_chat_message,
        )

        if isinstance(value, dict):
            for key, _value in value.copy().items():
                _value = self._convert_to_langwatch_type(_value)
                value[key] = _value
        elif isinstance(value, list):
            value = [self._convert_to_langwatch_type(v) for v in value]
        elif isinstance(value, Message):
            if "prompt" in value:
                prompt = value.load_lc_prompt()
                if len(prompt.input_variables) == 0 and all(isinstance(m, BaseMessage) for m in prompt.messages):
                    value = langchain_messages_to_chat_messages([cast(list[BaseMessage], prompt.messages)])
                else:
                    value = cast(dict, value.load_lc_prompt())
            elif value.sender:
                value = langchain_message_to_chat_message(value.to_lc_message())
            else:
                value = cast(dict, value.to_lc_document())
        elif isinstance(value, Data):
            value = cast(dict, value.to_lc_document())
        return value
