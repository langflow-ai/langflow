from __future__ import annotations

import json
import math
import os
import types
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
        self._span_map: dict[str, trace.Span] = {}

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

    def _convert_to_traceloop_type(self, value: Any) -> str | int | float | bool | None:
        """Convert any value into an OTel/Traceloop-compatible type (primitive or JSON string)."""
        from langchain.schema import BaseMessage, Document, HumanMessage, SystemMessage

        from langflow.schema.message import Message

        try:
            if isinstance(value, Message):
                return value.text
            if isinstance(value, BaseMessage | HumanMessage | SystemMessage):
                return value.content
            if isinstance(value, Document):
                return value.page_content
            if isinstance(value, types.GeneratorType):
                return str(value)
            if value is None:
                return None
            if isinstance(value, float) and not math.isfinite(value):
                return "NaN"
            if isinstance(value, str | bool | int | float):
                return value

            # fallback: JSON serialize (dicts, lists, custom objects)
            return json.dumps(value, default=str)
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to convert value {value!r} to traceloop type: {e}")
            return str(value)

    def _convert_to_traceloop_dict(self, io_dict: dict[str, Any]) -> dict[str, Any]:
        """Ensure all values in dict are OTel-compatible."""
        return {str(k): self._convert_to_traceloop_type(v) for k, v in (io_dict or {}).items()}

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
        if not self.ready:
            return

        span_name = f"component.{trace_name}"
        span = self._tracer.start_span(span_name)

        safe_inputs = self._convert_to_traceloop_dict(inputs)
        safe_metadata = self._convert_to_traceloop_dict(metadata or {})

        span.set_attributes(
            {
                "trace_id": trace_id,
                "trace_name": trace_name,
                "trace_type": trace_type,
                "inputs": json.dumps(safe_inputs, default=str),
                "vertex_id": vertex.id if vertex else None,
                **safe_metadata,
            }
        )

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
        if not self.ready:
            return

        span = self._span_map.pop(trace_name, None)
        if span is None:
            logger.warning(f"No active span found for {trace_name}")
            return

        if outputs:
            span.set_attributes({"outputs": json.dumps(self._convert_to_traceloop_dict(outputs), default=str)})
        if logs:
            span.set_attributes({"logs": json.dumps(self._convert_to_traceloop_type(logs), default=str)})
        if error:
            span.record_exception(error)

        span.end()

    @override
    def end(
        self,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        error: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self.ready:
            return

        safe_outputs = self._convert_to_traceloop_dict(outputs)
        safe_metadata = self._convert_to_traceloop_dict(metadata or {})

        with self._tracer.start_as_current_span("workflow.end") as span:
            span.set_attributes(
                {
                    "workflow_name": self.trace_name,
                    "workflow_id": str(self.trace_id),
                    "outputs": json.dumps(safe_outputs, default=str),
                    **safe_metadata,
                }
            )
            if error:
                span.record_exception(error)

    @override
    def get_langchain_callback(self) -> BaseCallbackHandler | None:
        return None

    def close(self):
        try:
            provider = trace.get_tracer_provider()
            if hasattr(provider, "force_flush"):
                provider.force_flush(timeout_millis=3000)
        except (ValueError, RuntimeError, OSError) as e:
            logger.warning(f"Error flushing spans: {e}")

    def __del__(self):
        self.close()
