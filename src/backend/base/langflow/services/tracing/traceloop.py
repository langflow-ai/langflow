from __future__ import annotations

import json
import math
import os
import traceback
import types
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from loguru import logger
from opentelemetry.semconv.trace import SpanAttributes as OTELSpanAttributes
from opentelemetry.trace import Span, SpanKind, Status, StatusCode, use_span
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

# Map trace_type to valid OpenTelemetry span kinds
trace_type_mapping = {
    "llm": SpanKind.CLIENT,
    "embedding": SpanKind.CLIENT,
    "chain": SpanKind.INTERNAL,
    "agent": SpanKind.INTERNAL,
    "tool": SpanKind.CLIENT,
    "retriever": SpanKind.CLIENT,
    "prompt": SpanKind.INTERNAL,
}


class TraceloopTracer(BaseTracer):
    flow_name: str
    flow_id: str
    chat_input_value: str
    chat_output_value: str

    def __init__(
        self, trace_name: str, trace_type: str, project_name: str, trace_id: UUID, session_id: str | None = None
    ):
        """Initializes the TraceloopTracer instance and sets up a root span."""
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.project_name = project_name
        self.trace_id = trace_id
        self.flow_name = trace_name.split(" - ")[0]
        self.flow_id = trace_name.split(" - ")[-1]
        self.chat_input_value = ""
        self.chat_output_value = ""
        self.session_id = session_id

        otel_span_kind = trace_type_mapping.get(self.trace_type, SpanKind.INTERNAL)

        try:
            self._ready = self.setup_traceloop()
            if not self._ready:
                return

            self.tracer = self.tracer_provider.get_tracer(__name__)
            self.propagator = TraceContextTextMapPropagator()
            self.carrier: dict[Any, CarrierT] = {}

            self.root_span = self.tracer.start_span(
                name=self.flow_id,
                start_time=self._get_current_timestamp(),
            )

            self.root_span.set_attribute("session.id", self.session_id or self.flow_id)
            self.root_span.set_attribute("span.kind", otel_span_kind.name.lower())
            self.root_span.set_attribute("langflow.project.name", self.project_name)
            self.root_span.set_attribute("langflow.flow.name", self.flow_name)
            self.root_span.set_attribute("langflow.flow.id", self.flow_id)

            with use_span(self.root_span, end_on_exit=False):
                self.propagator.inject(carrier=self.carrier)

            self.child_spans: dict[str, Span] = {}

        except Exception:  # noqa: BLE001
            logger.opt(exception=True).debug("Error setting up Traceloop tracer")
            self._ready = False

    @property
    def ready(self):
        """Indicates if the tracer is ready for usage."""
        return self._ready

    def setup_traceloop(self) -> bool:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter as _GRPCSpanExporter,
            )
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter as _HTTPSpanExporter,
            )
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

            project_name = "LANGFLOW"
            resource_attributes = {
                "service.name": os.getenv("OTEL_SERVICE_NAME", "langflow-application"),
                "project_name": project_name,
                "model_id": project_name,
            }
            resource = Resource(attributes=resource_attributes)
            tracer_provider = TracerProvider(resource=resource)

            # Traceloop
            traceloop_api_key = os.getenv("TRACELOOP_API_KEY")
            if traceloop_api_key:
                traceloop_endpoint = "https://api.traceloop.com/v1/traces"
                traceloop_headers = {
                    "Authorization": f"Bearer {traceloop_api_key}",
                }
                tracer_provider.add_span_processor(
                    BatchSpanProcessor(_HTTPSpanExporter(endpoint=traceloop_endpoint, headers=traceloop_headers))
                )

            # Instana
            instana_baseurl = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
            instana_headers = os.getenv("OTEL_EXPORTER_OTLP_HEADERS")
            if instana_baseurl and instana_headers:
                tracer_provider.add_span_processor(
                    SimpleSpanProcessor(_GRPCSpanExporter(endpoint=instana_baseurl, headers=instana_headers))
                )

            self.tracer_provider = tracer_provider

        except ImportError:
            logger.exception(
                "Failed to set up Traceloop/Instana OpenTelemetry instrumentation."
                "Install them using `pip install opentelemetry-sdk opentelemetry-exporter-otlp`."
            )
            return False

        try:
            from opentelemetry.instrumentation.langchain import LangchainInstrumentor

            LangchainInstrumentor().instrument(tracer_provider=self.tracer_provider, skip_dep_check=True)
        except ImportError:
            logger.exception(
                "Could not import LangChainInstrumentor."
                "Please install it with `pip install opentelemetry-instrumentation-langchain`."
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
        # Keep reference so we can finish it later
        self.child_spans[trace_id] = child_span

        # Map trace types to OpenTelemetry span kinds
        if trace_type == "prompt":
            child_span.set_attribute("span.kind", SpanKind.INTERNAL)
        else:
            otel_span_kind = trace_type_mapping.get(trace_type, SpanKind.INTERNAL)
            child_span.set_attribute("span.kind", otel_span_kind.name.lower())

        processed_inputs = self._convert_to_traceloop_types(inputs) if inputs else {}
        if processed_inputs:
            # OpenTelemetry doesn't have a standard INPUT_VALUE, so use custom attributes
            child_span.set_attribute("input.value", self._safe_json_dumps(processed_inputs))
            child_span.set_attribute("input.mime_type", "application/json")

        processed_metadata = self._convert_to_traceloop_types(metadata) if metadata else {}
        if processed_metadata:
            for key, value in processed_metadata.items():
                # Use custom metadata attributes
                child_span.set_attribute(f"metadata.{key}", value)

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

        processed_outputs = self._convert_to_traceloop_types(outputs) if outputs else {}
        if processed_outputs:
            child_span.set_attribute("output.value", self._safe_json_dumps(processed_outputs))
            child_span.set_attribute("output.mime_type", "application/json")

        logs_dicts = [log if isinstance(log, dict) else log.model_dump() for log in logs]
        processed_logs = self._convert_to_traceloop_types({log.get("name"): log for log in logs_dicts}) if logs else {}
        if processed_logs:
            child_span.set_attribute("logs", self._safe_json_dumps(processed_logs))

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
            self.root_span.set_attribute("input.value", self.chat_input_value)
            self.root_span.set_attribute("input.mime_type", "text/plain")
            self.root_span.set_attribute("output.value", self.chat_output_value)
            self.root_span.set_attribute("output.mime_type", "text/plain")

            processed_metadata = self._convert_to_traceloop_types(metadata) if metadata else {}
            if processed_metadata:
                for key, value in processed_metadata.items():
                    self.root_span.set_attribute(f"metadata.{key}", value)

            self._set_span_status(self.root_span, error)
            self.root_span.end()

        try:
            from opentelemetry.instrumentation.langchain import LangchainInstrumentor

            LangchainInstrumentor().uninstrument(tracer_provider=self.tracer_provider, skip_dep_check=True)
        except ImportError:
            logger.exception(
                "Could not import LangchainInstrumentor."
                "Please install it with `pip install opentelemetry-instrumentation-langchain`."
            )

    def _convert_to_traceloop_types(self, io_dict: dict[str | Any, Any]) -> dict[str, Any]:
        """Converts data types to Traceloop compatible formats."""
        return {str(key): self._convert_to_traceloop_type(value) for key, value in io_dict.items() if key is not None}

    def _convert_to_traceloop_type(self, value):
        """Recursively converts a value to a Traceloop compatible type."""
        if isinstance(value, dict):
            value = {key: self._convert_to_traceloop_type(val) for key, val in value.items()}

        elif isinstance(value, list):
            value = [self._convert_to_traceloop_type(v) for v in value]

        elif isinstance(value, Message):
            value = value.text

        elif isinstance(value, Data):
            value = value.get_text()

        elif isinstance(value, (BaseMessage | HumanMessage | SystemMessage)):
            value = value.content

        elif isinstance(value, Document):
            value = value.page_content

        elif isinstance(value, types.GeneratorType | type(None)):
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

            if isinstance(error, Exception):
                current_span.record_exception(error)
            else:
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
