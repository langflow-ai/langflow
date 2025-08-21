from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from loguru import logger
from opentelemetry import trace
from traceloop.sdk import Traceloop
from traceloop.sdk.instruments import Instruments
from typing_extensions import override

from langflow.services.tracing.base import BaseTracer

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from langchain.callbacks.base import BaseCallbackHandler

    from langflow.graph.vertex.base import Vertex
    from langflow.services.tracing.schema import Log


class TraceloopTracer(BaseTracer):
    """Traceloop tracer for Langflow."""

    def __init__(
        self,
        trace_name: str,
        trace_type: str,
        project_name: str,
        trace_id: UUID,
        user_id: str | None = None,
        session_id: str | None = None,
    ):
        self.trace_id = trace_id
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.project_name = project_name
        self.user_id = user_id
        self.session_id = session_id
        self._span_map: dict[str, trace.Span] = {}  # store spans by trace_name

        if not self._validate_configuration():
            self._ready = False
            return

        api_key = os.getenv("TRACELOOP_API_KEY", "").strip()
        try:
            Traceloop.init(
                block_instruments={Instruments.PYMYSQL},
                app_name=project_name,
                disable_batch=True,
                api_key=api_key,
                api_endpoint=os.getenv("TRACELOOP_BASE_URL", "https://api.traceloop.com"),
            )
            self._ready = True
            self._tracer = trace.get_tracer("langflow")
            logger.info("Traceloop tracer initialized successfully")
        except (ValueError, RuntimeError, OSError) as e:
            logger.error(f"Failed to initialize Traceloop tracer: {e}")
            self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    def _validate_configuration(self) -> bool:
        api_key = os.getenv("TRACELOOP_API_KEY", "").strip()
        if not api_key:
            logger.warning("TRACELOOP_API_KEY not set or empty.")
            return False

        base_url = os.getenv("TRACELOOP_BASE_URL", "https://api.traceloop.com")
        parsed = urlparse(base_url)
        if not parsed.netloc:
            logger.error(f"Invalid TRACELOOP_BASE_URL: {base_url}")
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
        """Start a new span for this trace."""
        if not self.ready:
            return

        span_name = f"component.{trace_name}"
        span = self._tracer.start_span(span_name)
        span.set_attributes(
            {
                "trace_id": trace_id,
                "trace_name": trace_name,
                "trace_type": trace_type,
                "inputs": str(inputs),
                "vertex_id": vertex.id if vertex else None,
                **(metadata or {}),
            }
        )

        # Store the span so end_trace can finish it
        self._span_map[trace_name] = span

    @override
    def end_trace(
        self,
        trace_id: str,
        trace_name: str,
        outputs: dict[str, Any] | None = None,
        error: Exception | None = None,
        logs: Sequence[Log | dict] = (),
    ) -> None:
        """End the span created in add_trace."""
        if not self.ready:
            return

        span = self._span_map.pop(trace_name, None)
        if span is None:
            logger.warning(f"No active span found for {trace_name}")
            return

        if outputs:
            span.set_attributes({"outputs": str(outputs)})
        if logs:
            span.set_attributes({"logs": str(logs)})
        if error:
            span.record_exception(error)

        span.end()  # Properly close span

    @override
    def end(
        self,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        error: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """End workflow-level span."""
        if not self.ready:
            return

        with self._tracer.start_as_current_span("workflow.end") as span:
            span.set_attributes(
                {
                    "workflow_name": self.trace_name,
                    "workflow_id": str(self.trace_id),
                    "outputs": str(outputs),
                    **(metadata or {}),
                }
            )
            if error:
                span.record_exception(error)

    @override
    def get_langchain_callback(self) -> BaseCallbackHandler | None:
        return None  # Implement if needed

    def close(self):
        """Flush pending spans."""
        try:
            provider = trace.get_tracer_provider()
            if hasattr(provider, "force_flush"):
                provider.force_flush(timeout_millis=3000)
        except (ValueError, RuntimeError, OSError) as e:
            logger.warning(f"Error flushing spans: {e}")

    def __del__(self):
        self.close()
