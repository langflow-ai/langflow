from __future__ import annotations

import json
import math
import os
import traceback
import types
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from fi_instrumentation.fi_types import FiMimeTypeValues, SpanAttributes
from langchain_core.documents import Document
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from loguru import logger
from opentelemetry.semconv.trace import SpanAttributes as OTELSpanAttributes
from opentelemetry.trace import Span, Status, StatusCode, use_span
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from typing_extensions import override

from langflow.schema.data import Data
from langflow.schema.message import Message
from langflow.services.tracing.base import BaseTracer

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from langchain.callbacks.base import BaseCallbackHandler
    from opentelemetry.propagators.textmap import CarrierT
    from opentelemetry.util.types import AttributeValue

    from langflow.graph.vertex.base import Vertex
    from langflow.services.tracing.schema import Log


class FiTracer(BaseTracer):
    flow_name: str
    flow_id: str
    chat_input_value: str
    chat_output_value: str

    def __init__(
        self,
        trace_name: str,
        trace_type: str,
        project_name: str,
        trace_id: UUID,
        session_id: str | None = None,
    ):
        """Initializes the FiTracer instance and sets up a root span."""
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.project_name = project_name
        self.trace_id = trace_id
        self.flow_name = trace_name.split(" - ")[0]
        self.flow_id = trace_name.split(" - ")[-1]
        self.chat_input_value = ""
        self.chat_output_value = ""
        self.session_id = session_id

        try:
            self._ready = self.setup_fi()
            if not self._ready:
                return

            self.tracer = self.tracer_provider.get_tracer(__name__)
            self.propagator = TraceContextTextMapPropagator()
            self.carrier: dict[Any, CarrierT] = {}

            self.root_span = self.tracer.start_span(
                name=self.flow_id,
                start_time=self._get_current_timestamp(),
            )
            self.root_span.set_attribute(SpanAttributes.SESSION_ID, self.session_id or self.flow_id)
            self.root_span.set_attribute(SpanAttributes.FI_SPAN_KIND, self.trace_type)
            self.root_span.set_attribute("langflow.project.name", self.project_name)
            self.root_span.set_attribute("langflow.flow.name", self.flow_name)
            self.root_span.set_attribute("langflow.flow.id", self.flow_id)

            with use_span(self.root_span, end_on_exit=False):
                self.propagator.inject(carrier=self.carrier)

            self.child_spans: dict[str, Span] = {}

        except Exception:
            logger.opt(exception=True).debug("Error setting up FI tracer")
            self._ready = False

    @property
    def ready(self):
        """Indicates if the tracer is ready for usage."""
        return self._ready

    def setup_fi(self) -> bool:
        """Configures Future AGI specific environment variables and registers the tracer provider."""
        fi_api_key = os.getenv("FI_API_KEY", None)
        fi_secret_key = os.getenv("FI_SECRET_KEY", None)
        session_name = os.getenv("FI_SESSION_NAME", None)
        enable_fi_tracing = bool(fi_api_key and fi_secret_key)

        if not enable_fi_tracing:
            return False

        try:
            from fi_instrumentation import register
            from fi_instrumentation.fi_types import ProjectType

            name_without_space = self.flow_name.replace(" ", "-")
            project_name = self.project_name if name_without_space == "None" else name_without_space
            project_type_str = os.getenv("FI_PROJECT_TYPE", "observe")

            try:
                project_type = ProjectType(project_type_str)
            except ValueError:
                project_type = ProjectType.OBSERVE

            register_params = {
                "project_name": project_name,
                "project_type": project_type,
            }

            if project_type == ProjectType.OBSERVE:
                register_params["session_name"] = session_name
            elif project_type == ProjectType.EXPERIMENT:
                register_params["project_version_name"] = self.flow_name

            tracer_provider = register(**register_params)

            self.tracer_provider = tracer_provider
        except ImportError:
            logger.exception("Could not import traceAI. Please install it with `pip install traceaAI-langchain`.")
            return False

        try:
            from traceai_langchain import LangChainInstrumentor

            LangChainInstrumentor().instrument(tracer_provider=self.tracer_provider)
        except ImportError:
            logger.exception(
                "Could not import LangChainInstrumentor.Please install it with `pip install traceaAI-langchain`."
            )
            return False

        return True

    @override
    def add_trace(
        self,
        trace_id: str,
        trace_name: str,
        trace_type: str,
        inputs: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        vertex: Vertex | None = None,
    ) -> None:
        """Adds a trace span, attaching inputs and metadata as attributes."""
        if not self._ready:
            return

        span_context = self.propagator.extract(carrier=self.carrier)
        child_span = self.tracer.start_span(
            name=trace_name,
            context=span_context,
            start_time=self._get_current_timestamp(),
        )

        if trace_type == "prompt":
            child_span.set_attribute(SpanAttributes.FI_SPAN_KIND, "chain")
        else:
            child_span.set_attribute(SpanAttributes.FI_SPAN_KIND, trace_type)

        processed_inputs = self._convert_to_fi_types(inputs) if inputs else {}
        if processed_inputs:
            child_span.set_attribute(SpanAttributes.RAW_INPUT, self._safe_json_dumps(processed_inputs))
            child_span.set_attribute(SpanAttributes.INPUT_VALUE, self._safe_json_dumps(processed_inputs))
            child_span.set_attribute(SpanAttributes.INPUT_MIME_TYPE, FiMimeTypeValues.JSON.value)

        processed_metadata = self._convert_to_fi_types(metadata) if metadata else {}
        if processed_metadata:
            for key, value in processed_metadata.items():
                child_span.set_attribute(f"{SpanAttributes.METADATA}.{key}", value)

        component_name = trace_id.split("-")[0]
        if component_name == "ChatInput":
            self.chat_input_value = processed_inputs["input_value"]
        elif component_name == "ChatOutput":
            self.chat_output_value = processed_inputs["input_value"]

        self.child_spans[trace_id] = child_span

    @override
    def end_trace(
        self,
        trace_id: str,
        trace_name: str,
        outputs: dict[str, Any] | None = None,
        error: Exception | None = None,
        logs: Sequence[Log | dict] = (),
    ) -> None:
        """Ends a trace span, attaching outputs, errors, and logs as attributes."""
        if not self._ready or trace_id not in self.child_spans:
            return

        child_span = self.child_spans[trace_id]

        processed_outputs = self._convert_to_fi_types(outputs) if outputs else {}
        if processed_outputs:
            child_span.set_attribute(SpanAttributes.RAW_OUTPUT, self._safe_json_dumps(processed_outputs))
            child_span.set_attribute(SpanAttributes.OUTPUT_VALUE, self._safe_json_dumps(processed_outputs))
            child_span.set_attribute(SpanAttributes.OUTPUT_MIME_TYPE, FiMimeTypeValues.JSON.value)

        logs_dicts = [log if isinstance(log, dict) else log.model_dump() for log in logs]
        processed_logs = self._convert_to_fi_types({log.get("name"): log for log in logs_dicts}) if logs else {}
        if processed_logs:
            for key, value in processed_logs.items():
                child_span.set_attribute(f"logs.{key}", value)

        self._set_span_status(child_span, error)
        child_span.end(end_time=self._get_current_timestamp())
        self.child_spans.pop(trace_id)

    @override
    def end(
        self,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        error: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Ends tracing with the specified inputs, outputs, errors, and metadata as attributes."""
        if not self._ready:
            return

        if self.root_span:
            self.root_span.set_attribute(SpanAttributes.RAW_INPUT, self._safe_json_dumps(inputs))
            self.root_span.set_attribute(SpanAttributes.INPUT_VALUE, self.chat_input_value)
            self.root_span.set_attribute(SpanAttributes.INPUT_MIME_TYPE, FiMimeTypeValues.TEXT.value)
            self.root_span.set_attribute(SpanAttributes.RAW_OUTPUT, self._safe_json_dumps(outputs))
            self.root_span.set_attribute(SpanAttributes.OUTPUT_VALUE, self.chat_output_value)
            self.root_span.set_attribute(SpanAttributes.OUTPUT_MIME_TYPE, FiMimeTypeValues.TEXT.value)

            processed_metadata = self._convert_to_fi_types(metadata) if metadata else {}
            if processed_metadata:
                for key, value in processed_metadata.items():
                    self.root_span.set_attribute(f"{SpanAttributes.METADATA}.{key}", value)

            self._set_span_status(self.root_span, error)
            self.root_span.end()

        try:
            from traceai_langchain import LangChainInstrumentor

            LangChainInstrumentor().uninstrument(tracer_provider=self.tracer_provider, skip_dep_check=True)
        except ImportError:
            logger.exception(
                "Could not import LangChainInstrumentor.Please install it with `pip install traceAI-langchain`."
            )

    def _convert_to_fi_types(self, io_dict: dict[str | Any, Any]) -> dict[str, Any]:
        """Converts data types to Future AGI compatible formats."""
        return {str(key): self._convert_to_fi_type(value) for key, value in io_dict.items() if key is not None}

    def _convert_to_fi_type(self, value):
        """Recursively converts a value to a Future AGI compatible type."""
        if isinstance(value, dict):
            value = {key: self._convert_to_fi_type(val) for key, val in value.items()}

        elif isinstance(value, list):
            value = [self._convert_to_fi_type(v) for v in value]

        elif isinstance(value, Message):
            value = value.text

        elif isinstance(value, Data):
            value = value.get_text()

        elif isinstance(value, (BaseMessage | HumanMessage | SystemMessage)):
            value = value.content

        elif isinstance(value, Document):
            value = value.page_content

        elif isinstance(value, (types.GeneratorType | types.NoneType)):
            value = str(value)

        elif isinstance(value, float) and not math.isfinite(value):
            value = "NaN"

        return value

    @staticmethod
    def _error_to_string(error: Exception | None):
        """Converts an error to a string with traceback details."""
        error_message = None
        if error:
            string_stacktrace = traceback.format_exception(error)
            error_message = f"{error.__class__.__name__}: {error}\n\n{string_stacktrace}"
        return error_message

    @staticmethod
    def _get_current_timestamp() -> int:
        """Gets the current UTC timestamp in nanoseconds."""
        return int(datetime.now(timezone.utc).timestamp() * 1_000_000_000)

    @staticmethod
    def _safe_json_dumps(obj: Any, **kwargs: Any) -> str:
        """A convenience wrapper around `json.dumps` that ensures that any object can be safely encoded."""
        return json.dumps(obj, default=str, ensure_ascii=False, **kwargs)

    def _set_span_status(self, current_span: Span, error: Exception | None = None):
        """Sets the status and attributes of the current span based on the presence of an error."""
        if error:
            error_string = self._error_to_string(error)
            current_span.set_status(Status(StatusCode.ERROR, error_string))
            current_span.set_attribute("error.message", error_string)

            current_span.record_exception(error)
            exception_type = error.__class__.__name__
            exception_message = str(error)
            if not exception_message:
                exception_message = repr(error)
            attributes: dict[str, AttributeValue] = {
                OTELSpanAttributes.EXCEPTION_TYPE: exception_type,
                OTELSpanAttributes.EXCEPTION_MESSAGE: exception_message,
                OTELSpanAttributes.EXCEPTION_ESCAPED: False,
                OTELSpanAttributes.EXCEPTION_STACKTRACE: error_string,
            }
            current_span.add_event(name="exception", attributes=attributes)
        else:
            current_span.set_status(Status(StatusCode.OK))

    @override
    def get_langchain_callback(self) -> BaseCallbackHandler | None:
        """Returns the LangChain callback handler if applicable."""
        return None
