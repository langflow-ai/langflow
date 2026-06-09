"""Generic OpenTelemetry tracer using standard OTLP configuration via environment variables.

OpenTelemetry GenAI Semantic Conventions
----------------------------------------
This tracer does NOT implement the OpenTelemetry GenAI semantic conventions
(https://opentelemetry.io/docs/specs/semconv/gen-ai/). Those conventions define
attributes like ``gen_ai.request.model``, ``gen_ai.usage.input_tokens``, and
``gen_ai.operation.name`` for instrumenting LLM API calls.

This tracer operates at the workflow orchestration level, tracing Langflow
component execution rather than individual LLM calls. The LLM-specific details
(model name, token counts, request parameters) are encapsulated within
components and not directly accessible at trace time.

Attributes emitted use the ``langflow.*`` namespace for workflow context.
"""

from __future__ import annotations

import json
import os
import threading
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from opentelemetry.trace import use_span
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from typing_extensions import override

from langflow.services.tracing.otlp_base import OTLPTracerBase

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from langchain.callbacks.base import BaseCallbackHandler
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.trace import Tracer

    from langflow.graph.vertex.base import Vertex
    from langflow.services.tracing.schema import Log


# ---------------------------------------------------------------------------
# Module-level shared provider singleton
# ---------------------------------------------------------------------------

_provider_lock = threading.Lock()
_shared_provider: TracerProvider | None = None
_shared_tracer: Tracer | None = None


def _validate_otlp_env() -> bool:
    """Check whether OTLP tracing is configured via environment variables.

    Returns:
        True if at least one endpoint env var is set and the SDK is not disabled.
    """
    if os.getenv("OTEL_SDK_DISABLED", "").strip().lower() == "true":
        logger.debug("OTLP tracer disabled via OTEL_SDK_DISABLED=true")
        return False

    traces_endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    generic_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not traces_endpoint and not generic_endpoint:
        logger.debug(
            "OTLP tracer not configured: neither OTEL_EXPORTER_OTLP_TRACES_ENDPOINT "
            "nor OTEL_EXPORTER_OTLP_ENDPOINT is set"
        )
        return False

    return True


def _create_exporter():
    """Resolve the OTLP span exporter from installed entry points.

    Reads ``OTEL_EXPORTER_OTLP_TRACES_PROTOCOL`` first (trace-specific
    override), falling back to ``OTEL_EXPORTER_OTLP_PROTOCOL`` (generic),
    then defaulting to ``http/protobuf``.  Only ``grpc`` and
    ``http/protobuf`` are supported trace protocols in the OpenTelemetry
    Python SDK.

    Falls back to the HTTP/protobuf exporter when no matching entry point
    is found (e.g. only one transport package is installed).
    """
    import importlib.metadata

    protocol = os.getenv(
        "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL",
        os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf"),
    )
    ep_name_map = {
        "grpc": "otlp_proto_grpc",
        "http/protobuf": "otlp_proto_http",
    }
    entry_point_name = ep_name_map.get(protocol, "otlp_proto_http")

    eps = importlib.metadata.entry_points()
    if hasattr(eps, "select"):
        matches = list(eps.select(group="opentelemetry_traces_exporter", name=entry_point_name))
    else:
        matches = [ep for ep in eps.get("opentelemetry_traces_exporter", []) if ep.name == entry_point_name]

    if matches:
        exporter_class = matches[0].load()
    else:
        logger.warning(
            "No entry point '%s' found for opentelemetry_traces_exporter, falling back to http/protobuf exporter",
            entry_point_name,
        )
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter as FallbackExporter,
        )

        exporter_class = FallbackExporter

    # OTLPSpanExporter() auto-reads OTEL_EXPORTER_OTLP_* env vars
    return exporter_class()


def _get_shared_provider(project_name: str) -> tuple[TracerProvider, Tracer]:
    """Return the shared TracerProvider and Tracer, creating them on first call.

    Thread-safe via module-level lock.  The provider is created once and
    reused across all graph runs, avoiding per-run ``BatchSpanProcessor``
    thread allocation.

    Args:
        project_name: Langflow project name added as a resource attribute.

    Returns:
        Tuple of (TracerProvider, Tracer).
    """
    global _shared_provider, _shared_tracer  # noqa: PLW0603

    if _shared_tracer is not None:
        return _shared_provider, _shared_tracer

    with _provider_lock:
        # Double-checked locking
        if _shared_tracer is not None:
            return _shared_provider, _shared_tracer

        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider as _TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        span_exporter = _create_exporter()

        # Resource.create() auto-merges OTEL_SERVICE_NAME, OTEL_RESOURCE_ATTRIBUTES,
        # and SDK metadata with any explicit attributes we pass.
        resource = Resource.create({"langflow.project_name": project_name})

        provider = _TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(span_exporter))

        _shared_provider = provider
        _shared_tracer = provider.get_tracer(__name__)

        return _shared_provider, _shared_tracer


def shutdown_otlp_provider() -> None:
    """Shutdown the shared OTLP TracerProvider, flushing pending spans.

    Safe to call multiple times or when no provider has been created.
    Should be called at process/service shutdown.
    """
    global _shared_provider, _shared_tracer  # noqa: PLW0603

    with _provider_lock:
        if _shared_provider is not None:
            try:
                _shared_provider.shutdown()
            except (ValueError, RuntimeError, OSError) as e:
                logger.warning(f"Error shutting down OTLP tracer provider: {e}")
            finally:
                _shared_provider = None
                _shared_tracer = None


def _reset_shared_provider() -> None:
    """Reset the shared provider without calling shutdown.

    Intended for tests only — allows re-creation with different env vars.
    """
    global _shared_provider, _shared_tracer  # noqa: PLW0603

    with _provider_lock:
        _shared_provider = None
        _shared_tracer = None


# ---------------------------------------------------------------------------
# Per-run tracer
# ---------------------------------------------------------------------------


class OTLPTracer(OTLPTracerBase):
    """Generic OpenTelemetry tracer using standard OTLP configuration.

    This tracer uses the standard OpenTelemetry SDK and automatically discovers
    configuration from standard environment variables:

    - OTEL_EXPORTER_OTLP_ENDPOINT or OTEL_EXPORTER_OTLP_TRACES_ENDPOINT
    - OTEL_EXPORTER_OTLP_HEADERS or OTEL_EXPORTER_OTLP_TRACES_HEADERS
    - OTEL_EXPORTER_OTLP_PROTOCOL (http/protobuf or grpc)
    - OTEL_SERVICE_NAME
    - OTEL_RESOURCE_ATTRIBUTES

    The TracerProvider and BatchSpanProcessor are shared across all graph
    runs to avoid per-run thread allocation.  Each OTLPTracer instance
    creates only its own root span and child spans.
    """

    def __init__(
        self,
        trace_name: str,
        trace_type: str,
        project_name: str,
        trace_id: UUID,
        user_id: str | None = None,
        session_id: str | None = None,
    ):
        """Initialize the OTLP tracer for a single graph run.

        Args:
            trace_name: Name of the trace
            trace_type: Type of trace (e.g., "chain")
            project_name: Name of the project
            trace_id: Unique identifier for the trace
            user_id: Optional user identifier
            session_id: Optional session identifier
        """
        super().__init__()
        self.trace_id = trace_id
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.project_name = project_name
        self.user_id = user_id
        self.session_id = session_id

        if not _validate_otlp_env():
            self._ready = False
            return

        try:
            self._setup_spans()
        except Exception:  # noqa: BLE001
            logger.debug("Error setting up OTLP tracer", exc_info=True)
            self._ready = False

    def _setup_spans(self) -> None:
        """Create root span and propagation carrier using the shared provider."""
        _provider, tracer = _get_shared_provider(self.project_name)
        self.tracer = tracer
        self.propagator = TraceContextTextMapPropagator()
        self.carrier = {}

        # Create root span
        self.root_span = self.tracer.start_span(
            name=self.trace_name,
            start_time=self._get_current_timestamp(),
        )

        # Set Langflow workflow attributes (see module docstring for rationale)
        self.root_span.set_attribute("langflow.trace_id", str(self.trace_id))
        self.root_span.set_attribute("langflow.trace_name", self.trace_name)
        self.root_span.set_attribute("langflow.trace_type", self.trace_type)
        self.root_span.set_attribute("langflow.project_name", self.project_name)

        if self.user_id:
            self.root_span.set_attribute("langflow.user_id", str(self.user_id))
        if self.session_id:
            self.root_span.set_attribute("langflow.session_id", str(self.session_id))

        # Inject context for propagation
        with use_span(self.root_span, end_on_exit=False):
            self.propagator.inject(carrier=self.carrier)

        self._ready = True

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
        """Add a child trace span.

        Args:
            trace_id: Unique identifier for this trace
            trace_name: Name of the trace
            trace_type: Type of trace
            inputs: Input data
            metadata: Optional metadata
            vertex: Optional vertex information
        """
        if not self.ready or self.tracer is None:
            return

        span_context = self.propagator.extract(carrier=self.carrier)
        child_span = self.tracer.start_span(
            name=trace_name,
            context=span_context,
            start_time=self._get_current_timestamp(),
        )

        # Set attributes
        child_span.set_attribute("trace_id", trace_id)
        child_span.set_attribute("trace_name", trace_name)
        child_span.set_attribute("trace_type", trace_type)
        child_span.set_attribute("inputs", json.dumps(self._convert_to_otlp_dict(inputs), default=str))

        if metadata:
            for key, value in self._to_span_attributes(metadata).items():
                child_span.set_attribute(f"metadata.{key}", value)

        if vertex and vertex.id is not None:
            child_span.set_attribute("vertex_id", vertex.id)

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
        """End a child trace span.

        Args:
            trace_id: Unique identifier for the trace
            trace_name: Name of the trace
            outputs: Optional output data
            error: Optional error that occurred
            logs: Optional log entries
        """
        if not self._ready or trace_id not in self.child_spans:
            return

        child_span = self.child_spans.pop(trace_id)

        if outputs:
            child_span.set_attribute("outputs", json.dumps(self._convert_to_otlp_dict(outputs), default=str))

        if logs:
            child_span.set_attribute("logs", json.dumps(self._convert_to_otlp_dict(list(logs)), default=str))

        if error:
            child_span.record_exception(error)

        child_span.end(end_time=self._get_current_timestamp())

    @override
    def end(
        self,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        error: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """End the root trace.

        Args:
            inputs: Input data for the entire trace
            outputs: Output data for the entire trace
            error: Optional error that occurred
            metadata: Optional metadata
        """
        if not self.ready or self.root_span is None:
            return

        safe_outputs = self._convert_to_otlp_dict(outputs)

        self.root_span.set_attribute("outputs", json.dumps(safe_outputs, default=str))

        for key, value in self._to_span_attributes(metadata or {}).items():
            self.root_span.set_attribute(f"metadata.{key}", value)

        if error:
            self.root_span.record_exception(error)

        self.root_span.end(end_time=self._get_current_timestamp())

    @override
    def get_langchain_callback(self) -> BaseCallbackHandler | None:
        """Get LangChain callback handler.

        Returns:
            None: This tracer does not provide a LangChain callback
        """
        return None
