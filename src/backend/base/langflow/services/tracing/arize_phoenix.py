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
from openinference.semconv.trace import OpenInferenceMimeTypeValues, SpanAttributes
from opentelemetry.semconv.trace import SpanAttributes as OTELSpanAttributes
from opentelemetry.trace import Span, Status, StatusCode
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


class ArizePhoenixTracer(BaseTracer):
    flow_id: str

    def __init__(self, trace_name: str, trace_type: str, project_name: str, trace_id: UUID):
        """Initializes the ArizePhoenixTracer instance and sets up a root span."""
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.project_name = project_name
        self.trace_id = trace_id
        self.flow_id = trace_name.split(" - ")[-1]

        try:
            self._ready = self.setup_arize_phoenix()
            if not self._ready:
                return

            self.tracer = self.tracer_provider.get_tracer(__name__)
            self.propagator = TraceContextTextMapPropagator()
            self.carrier: dict[Any, CarrierT] = {}

            with self.tracer.start_as_current_span(
                name=self.flow_id,
                start_time=self._get_current_timestamp(),
            ) as root_span:
                root_span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, self.trace_type)
                root_span.set_status(Status(StatusCode.OK))
                self.propagator.inject(carrier=self.carrier)

            self.child_spans: dict[str, Span] = {}

        except Exception:  # noqa: BLE001
            logger.opt(exception=True).debug("Error setting up Arize/Phoenix tracer")
            self._ready = False

    @property
    def ready(self):
        """Indicates if the tracer is ready for usage."""
        return self._ready

    def setup_arize_phoenix(self) -> bool:
        """Configures Arize/Phoenix specific environment variables and registers the tracer provider."""
        arize_phoenix_batch = os.getenv("ARIZE_PHOENIX_BATCH", "False").lower() in {
            "true",
            "t",
            "yes",
            "y",
            "1",
        }

        # Arize Config
        arize_api_key = os.getenv("ARIZE_API_KEY", None)
        arize_space_id = os.getenv("ARIZE_SPACE_ID", None)
        arize_collector_endpoint = os.getenv("ARIZE_COLLECTOR_ENDPOINT", "https://otlp.arize.com")
        enable_arize_tracing = bool(arize_api_key and arize_space_id)
        arize_endpoint = f"{arize_collector_endpoint}/v1"
        arize_headers = {
            "api_key": arize_api_key,
            "space_id": arize_space_id,
            "authorization": f"Bearer {arize_api_key}",
        }

        # Phoenix Config
        phoenix_api_key = os.getenv("PHOENIX_API_KEY", None)
        phoenix_collector_endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "https://app.phoenix.arize.com")
        enable_phoenix_tracing = bool(phoenix_api_key)
        phoenix_endpoint = f"{phoenix_collector_endpoint}/v1/traces"
        phoenix_headers = {
            "api_key": phoenix_api_key,
            "authorization": f"Bearer {phoenix_api_key}",
        }

        if not (enable_arize_tracing or enable_phoenix_tracing):
            return False

        try:
            from phoenix.otel import (
                PROJECT_NAME,
                BatchSpanProcessor,
                GRPCSpanExporter,
                HTTPSpanExporter,
                Resource,
                SimpleSpanProcessor,
                TracerProvider,
            )

            project_name = self.project_name or self.flow_id
            attributes = {PROJECT_NAME: project_name, "model_id": project_name}
            resource = Resource.create(attributes=attributes)
            tracer_provider = TracerProvider(resource=resource, verbose=False)
            span_processor = BatchSpanProcessor if arize_phoenix_batch else SimpleSpanProcessor

            if enable_arize_tracing:
                tracer_provider.add_span_processor(
                    span_processor=span_processor(
                        span_exporter=GRPCSpanExporter(endpoint=arize_endpoint, headers=arize_headers),
                    )
                )

            if enable_phoenix_tracing:
                tracer_provider.add_span_processor(
                    span_processor=span_processor(
                        span_exporter=HTTPSpanExporter(
                            endpoint=phoenix_endpoint,
                            headers=phoenix_headers,
                        ),
                    )
                )

            self.tracer_provider = tracer_provider
        except ImportError:
            logger.exception(
                "Could not import arize-phoenix-otel. Please install it with `pip install arize-phoenix-otel`."
            )
            return False

        try:
            from openinference.instrumentation.langchain import LangChainInstrumentor

            LangChainInstrumentor().instrument(tracer_provider=self.tracer_provider, skip_dep_check=True)
        except ImportError:
            logger.exception(
                "Could not import LangChainInstrumentor."
                "Please install it with `pip install openinference-instrumentation-langchain`."
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
            child_span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "chain")
        else:
            child_span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, trace_type)

        if "session_id" in inputs and len(inputs["session_id"]) > 0 and inputs["session_id"] != self.flow_id:
            child_span.set_attribute(SpanAttributes.SESSION_ID, inputs["session_id"])
        else:
            child_span.set_attribute(SpanAttributes.SESSION_ID, self.flow_id)

        processed_inputs = self._convert_to_arize_phoenix_types(inputs) if inputs else {}
        if processed_inputs:
            child_span.set_attribute(SpanAttributes.INPUT_VALUE, self._safe_json_dumps(processed_inputs))
            child_span.set_attribute(SpanAttributes.INPUT_MIME_TYPE, OpenInferenceMimeTypeValues.JSON.value)

        processed_metadata = self._convert_to_arize_phoenix_types(metadata) if metadata else {}
        if processed_metadata:
            for key, value in processed_metadata.items():
                child_span.set_attribute(f"{SpanAttributes.METADATA}.{key}", value)

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

        processed_outputs = self._convert_to_arize_phoenix_types(outputs) if outputs else {}
        if processed_outputs:
            child_span.set_attribute(SpanAttributes.OUTPUT_VALUE, self._safe_json_dumps(processed_outputs))
            child_span.set_attribute(SpanAttributes.OUTPUT_MIME_TYPE, OpenInferenceMimeTypeValues.JSON.value)

        logs_dicts = [log if isinstance(log, dict) else log.model_dump() for log in logs]
        processed_logs = (
            self._convert_to_arize_phoenix_types({log.get("name"): log for log in logs_dicts}) if logs else {}
        )
        if processed_logs:
            for key, value in processed_logs.items():
                child_span.set_attribute(f"logs.{key}", value)

        if error:
            error_string = self._error_to_string(error)
            child_span.set_status(Status(StatusCode.ERROR, error_string))
            child_span.set_attribute("error.message", error_string)

            if isinstance(error, Exception):
                child_span.record_exception(error)
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
                child_span.add_event(name="exception", attributes=attributes)
        else:
            child_span.set_status(Status(StatusCode.OK))

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

    def _convert_to_arize_phoenix_types(self, io_dict: dict[str | Any, Any]) -> dict[str, Any]:
        """Converts data types to Arize/Phoenix compatible formats."""
        return {
            str(key): self._convert_to_arize_phoenix_type(value) for key, value in io_dict.items() if key is not None
        }

    def _convert_to_arize_phoenix_type(self, value):
        """Recursively converts a value to a Arize/Phoenix compatible type."""
        if isinstance(value, dict):
            value = {key: self._convert_to_arize_phoenix_type(val) for key, val in value.items()}

        elif isinstance(value, list):
            value = [self._convert_to_arize_phoenix_type(v) for v in value]

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

    def _error_to_string(self, error: Exception | None):
        """Converts an error to a string with traceback details."""
        error_message = None
        if error:
            string_stacktrace = traceback.format_exception(error)
            error_message = f"{error.__class__.__name__}: {error}\n\n{string_stacktrace}"
        return error_message

    def _get_current_timestamp(self) -> int:
        """Gets the current UTC timestamp in nanoseconds."""
        return int(datetime.now(timezone.utc).timestamp() * 1_000_000_000)

    def _safe_json_dumps(self, obj: Any, **kwargs: Any) -> str:
        """A convenience wrapper around `json.dumps` that ensures that any object can be safely encoded."""
        return json.dumps(obj, default=str, ensure_ascii=False, **kwargs)

    def get_langchain_callback(self) -> BaseCallbackHandler | None:
        """Returns the LangChain callback handler if applicable."""
        return None
