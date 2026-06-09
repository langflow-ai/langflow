from __future__ import annotations

import os
import threading
import traceback
import uuid
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from openinference.semconv.trace import OpenInferenceMimeTypeValues, SpanAttributes
from opentelemetry.semconv.trace import SpanAttributes as OTELSpanAttributes
from opentelemetry.trace import Span, Status, StatusCode, use_span
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from typing_extensions import override

from langflow.services.tracing.otlp_base import OTLPTracerBase

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from langchain_core.callbacks.base import BaseCallbackHandler
    from lfx.graph.vertex.base import Vertex
    from opentelemetry.util.types import AttributeValue

    from langflow.services.tracing.schema import Log


# ---------------------------------------------------------------------------
# Module-level shared provider singleton
# ---------------------------------------------------------------------------

_arize_lock = threading.Lock()
_shared_provider = None
_shared_tracer = None
_instrumentor_applied = False


def _get_arize_shared_provider(flow_name: str, project_name: str):
    """Return the shared Arize/Phoenix TracerProvider and Tracer.

    Created on first call and reused for all subsequent graph runs to
    avoid per-run BatchSpanProcessor thread accumulation.

    Args:
        flow_name: Flow name (used for project naming on first init only).
        project_name: Langflow project name.

    Returns:
        Tuple of (TracerProvider, Tracer) or (None, None) if not configured.
    """
    global _shared_provider, _shared_tracer, _instrumentor_applied  # noqa: PLW0603

    if _shared_tracer is not None:
        return _shared_provider, _shared_tracer

    with _arize_lock:
        if _shared_tracer is not None:
            return _shared_provider, _shared_tracer

        provider = _create_arize_provider(flow_name, project_name)
        if provider is None:
            return None, None

        _shared_provider = provider
        _shared_tracer = provider.get_tracer(__name__)

        # Instrument LangChain once with the shared provider
        if not _instrumentor_applied:
            try:
                from openinference.instrumentation.langchain import LangChainInstrumentor

                LangChainInstrumentor().instrument(tracer_provider=_shared_provider, skip_dep_check=True)
                _instrumentor_applied = True
            except ImportError:
                logger.exception(
                    "[Arize/Phoenix] Could not import LangChainInstrumentor."
                    "Please install it with `pip install openinference-instrumentation-langchain`."
                )
                _shared_provider = None
                _shared_tracer = None
                return None, None

        return _shared_provider, _shared_tracer


def _create_arize_provider(flow_name: str, project_name: str):
    """Create the TracerProvider with Arize and/or Phoenix exporters.

    Returns:
        TracerProvider or None if tracing is not configured.
    """
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
    phoenix_auth_disabled = "localhost" in phoenix_collector_endpoint or "127.0.0.1" in phoenix_collector_endpoint
    enable_phoenix_tracing = bool(phoenix_api_key) or phoenix_auth_disabled
    phoenix_endpoint = f"{phoenix_collector_endpoint}/v1/traces"
    phoenix_headers = (
        {
            "api_key": phoenix_api_key,
            "authorization": f"Bearer {phoenix_api_key}",
        }
        if phoenix_api_key
        else {}
    )

    if not (enable_arize_tracing or enable_phoenix_tracing):
        return None

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

        name_without_space = flow_name.replace(" ", "-")
        resolved_project = project_name if name_without_space == "None" else name_without_space
        attributes = {PROJECT_NAME: resolved_project, "model_id": resolved_project}
        resource = Resource.create(attributes=attributes)
        provider = TracerProvider(resource=resource, verbose=False)
        span_processor = BatchSpanProcessor if arize_phoenix_batch else SimpleSpanProcessor

        if enable_arize_tracing:
            provider.add_span_processor(
                span_processor=span_processor(
                    span_exporter=GRPCSpanExporter(endpoint=arize_endpoint, headers=arize_headers),
                )
            )

        if enable_phoenix_tracing:
            provider.add_span_processor(
                span_processor=span_processor(
                    span_exporter=HTTPSpanExporter(
                        endpoint=phoenix_endpoint,
                        headers=phoenix_headers,
                    ),
                )
            )

    except ImportError:
        logger.exception(
            "[Arize/Phoenix] Could not import Arize Phoenix OTEL packages."
            "Please install it with `pip install arize-phoenix-otel`."
        )
        return None

    return provider


def shutdown_arize_provider() -> None:
    """Shutdown the shared Arize/Phoenix TracerProvider, flushing pending spans.

    Safe to call multiple times or when no provider has been created.
    Should be called at process/service shutdown.
    """
    global _shared_provider, _shared_tracer, _instrumentor_applied  # noqa: PLW0603

    with _arize_lock:
        if _instrumentor_applied:
            try:
                from openinference.instrumentation.langchain import LangChainInstrumentor

                LangChainInstrumentor().uninstrument(skip_dep_check=True)
            except Exception:  # noqa: BLE001
                logger.debug("[Arize/Phoenix] Error uninstrumenting LangChain", exc_info=True)
            _instrumentor_applied = False

        if _shared_provider is not None:
            try:
                _shared_provider.shutdown()
            except (ValueError, RuntimeError, OSError) as e:
                logger.warning(f"[Arize/Phoenix] Error shutting down tracer provider: {e}")
            finally:
                _shared_provider = None
                _shared_tracer = None


def _reset_arize_provider() -> None:
    """Reset the shared provider without calling shutdown. For tests only."""
    global _shared_provider, _shared_tracer, _instrumentor_applied  # noqa: PLW0603

    with _arize_lock:
        _shared_provider = None
        _shared_tracer = None
        _instrumentor_applied = False


# ---------------------------------------------------------------------------
# Per-run tracer
# ---------------------------------------------------------------------------


class ArizePhoenixTracer(OTLPTracerBase):
    """Arize/Phoenix tracer using OpenTelemetry.

    The TracerProvider and span processors are shared across all graph runs
    to avoid per-run thread accumulation. Each ArizePhoenixTracer instance
    creates only its own root span and child spans.
    """

    flow_name: str
    flow_id: str
    chat_input_value: str
    chat_output_value: str

    def __init__(
        self, trace_name: str, trace_type: str, project_name: str, trace_id: UUID, session_id: str | None = None
    ):
        super().__init__()
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.project_name = project_name
        self.trace_id = trace_id
        self.session_id = session_id
        self.flow_name = trace_name.split(" - ", maxsplit=1)[0]
        self.flow_id = trace_name.rsplit(" - ", maxsplit=1)[-1]
        self.chat_input_value = ""
        self.chat_output_value = ""

        try:
            provider, tracer = _get_arize_shared_provider(self.flow_name, self.project_name)
            if provider is None or tracer is None:
                self._ready = False
                return

            self.tracer = tracer
            self._enable_http_context_propagation(provider)
            self.propagator = TraceContextTextMapPropagator()
            self.carrier = {}

            self.root_span = self.tracer.start_span(
                name="Langflow",
                start_time=self._get_current_timestamp(),
            )
            # Per-run correlation ID set directly on root span
            self.root_span.set_attribute("langflow.correlation_id", str(uuid.uuid4()))
            self.root_span.set_attribute(SpanAttributes.SESSION_ID, self.session_id or self.flow_id)
            self.root_span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, self.trace_type)
            self.root_span.set_attribute("langflow.trace_name", self.trace_name)
            self.root_span.set_attribute("langflow.trace_type", self.trace_type)
            self.root_span.set_attribute("langflow.project_name", self.project_name)
            self.root_span.set_attribute("langflow.trace_id", str(self.trace_id))
            self.root_span.set_attribute("langflow.session_id", str(self.session_id))
            self.root_span.set_attribute("langflow.flow_name", self.flow_name)
            self.root_span.set_attribute("langflow.flow_id", self.flow_id)

            with use_span(self.root_span, end_on_exit=False):
                self.propagator.inject(carrier=self.carrier)

            self._ready = True

        except Exception as e:  # noqa: BLE001
            logger.error("[Arize/Phoenix] Error Setting Up Tracer: %s", str(e), exc_info=True)
            self._ready = False

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
        if not self._ready or self.tracer is None:
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

        processed_inputs = self._convert_to_otlp_dict(inputs) if inputs else {}
        if processed_inputs:
            child_span.set_attribute(SpanAttributes.INPUT_VALUE, self._safe_json_dumps(processed_inputs))
            child_span.set_attribute(SpanAttributes.INPUT_MIME_TYPE, OpenInferenceMimeTypeValues.JSON.value)

        processed_metadata = self._convert_to_otlp_dict(metadata) if metadata else {}
        if processed_metadata:
            for key, value in processed_metadata.items():
                child_span.set_attribute(f"{SpanAttributes.METADATA}.{key}", value)

        if vertex and vertex.id is not None:
            child_span.set_attribute("vertex_id", vertex.id)

        component_name = trace_id.split("-", maxsplit=1)[0]
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
        if not self._ready or trace_id not in self.child_spans:
            return

        child_span = self.child_spans[trace_id]

        processed_outputs = self._convert_to_otlp_dict(outputs) if outputs else {}
        if processed_outputs:
            child_span.set_attribute(SpanAttributes.OUTPUT_VALUE, self._safe_json_dumps(processed_outputs))
            child_span.set_attribute(SpanAttributes.OUTPUT_MIME_TYPE, OpenInferenceMimeTypeValues.JSON.value)

        logs_dicts = [log if isinstance(log, dict) else log.model_dump() for log in logs]
        processed_logs = self._convert_to_otlp_dict({log.get("name"): log for log in logs_dicts}) if logs else {}
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
        if not self._ready:
            return

        if self.root_span:
            self.root_span.set_attribute(SpanAttributes.INPUT_VALUE, self.chat_input_value)
            self.root_span.set_attribute(SpanAttributes.INPUT_MIME_TYPE, OpenInferenceMimeTypeValues.TEXT.value)
            self.root_span.set_attribute(SpanAttributes.OUTPUT_VALUE, self.chat_output_value)
            self.root_span.set_attribute(SpanAttributes.OUTPUT_MIME_TYPE, OpenInferenceMimeTypeValues.TEXT.value)

            processed_metadata = self._convert_to_otlp_dict(metadata) if metadata else {}
            if processed_metadata:
                for key, value in processed_metadata.items():
                    self.root_span.set_attribute(f"{SpanAttributes.METADATA}.{key}", value)

            self._set_span_status(self.root_span, error)
            self.root_span.end(end_time=self._get_current_timestamp())

        self._disable_http_context_propagation()

    @staticmethod
    def _error_to_string(error: Exception | None):
        error_message = None
        if error:
            string_stacktrace = traceback.format_exception(error)
            error_message = f"{error.__class__.__name__}: {error}\n\n{string_stacktrace}"
        return error_message

    def _set_span_status(self, current_span: Span, error: Exception | None = None):
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
        return None
