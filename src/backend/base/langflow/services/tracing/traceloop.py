from __future__ import annotations

import json
import math
import os
import types
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from lfx.log.logger import logger
from opentelemetry import trace
from opentelemetry.trace import Span, use_span
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from traceloop.sdk import Traceloop
from traceloop.sdk.instruments import Instruments
from typing_extensions import override

from langflow.services.tracing.base import BaseTracer

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from langchain.callbacks.base import BaseCallbackHandler
    from opentelemetry.propagators.textmap import CarrierT
    from opentelemetry.trace import Span

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
        self.child_spans: dict[str, Span] = {}

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
            self.propagator = TraceContextTextMapPropagator()
            self.carrier: CarrierT = {}

            self.root_span = self._tracer.start_span(
                name=trace_name,
                start_time=self._get_current_timestamp(),
            )

            with use_span(self.root_span, end_on_exit=False):
                self.propagator.inject(carrier=self.carrier)

        except Exception:  # noqa: BLE001
            logger.debug("Error setting up Traceloop tracer", exc_info=True)
            self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    def _validate_configuration(self) -> bool:
        api_key = os.getenv("TRACELOOP_API_KEY", "").strip()
        if not api_key:
            return False

        base_url = os.getenv("TRACELOOP_BASE_URL", "https://api.traceloop.com")
        parsed = urlparse(base_url)
        if not parsed.netloc:
            logger.error(f"Invalid TRACELOOP_BASE_URL: {base_url}")
            return False

        return True

    def _convert_to_traceloop_type(self, value):
        """Recursively converts a value to a Traceloop compatible type."""
        from langchain.schema import BaseMessage, Document, HumanMessage, SystemMessage

        from langflow.schema.message import Message

        try:
            if isinstance(value, dict):
                value = {key: self._convert_to_traceloop_type(val) for key, val in value.items()}

            elif isinstance(value, list):
                value = [self._convert_to_traceloop_type(v) for v in value]

            elif isinstance(value, Message):
                value = value.text

            elif isinstance(value, (BaseMessage | HumanMessage | SystemMessage)):
                value = str(value.content) if value.content is not None else ""

            elif isinstance(value, Document):
                value = value.page_content

            elif isinstance(value, (types.GeneratorType | types.NoneType)):
                value = str(value)

            elif isinstance(value, float) and not math.isfinite(value):
                value = "NaN"

        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to convert value {value!r} to traceloop type: {e}")
            return str(value)
        else:
            return value

    def _convert_to_traceloop_dict(self, io_dict: Any) -> dict[str, Any]:
        """Ensure values are OTel-compatible. Dicts stay dicts, lists get JSON-serialized."""
        if isinstance(io_dict, dict):
            return {str(k): self._convert_to_traceloop_type(v) for k, v in io_dict.items()}
        if isinstance(io_dict, list):
            return {"list": json.dumps([self._convert_to_traceloop_type(v) for v in io_dict], default=str)}

        return {"value": self._convert_to_traceloop_type(io_dict)}

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

        span_context = self.propagator.extract(carrier=self.carrier)
        child_span = self._tracer.start_span(
            name=trace_name,
            context=span_context,
            start_time=self._get_current_timestamp(),
        )

        attributes = {
            "trace_id": trace_id,
            "trace_name": trace_name,
            "trace_type": trace_type,
            "inputs": json.dumps(self._convert_to_traceloop_dict(inputs), default=str),
            **self._convert_to_traceloop_dict(metadata or {}),
        }
        if vertex and vertex.id is not None:
            attributes["vertex_id"] = vertex.id

        child_span.set_attributes(attributes)

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

        child_span = self.child_spans.pop(trace_id)

        if outputs:
            child_span.set_attribute("outputs", json.dumps(self._convert_to_traceloop_dict(outputs), default=str))
        if logs:
            child_span.set_attribute("logs", json.dumps(self._convert_to_traceloop_dict(list(logs)), default=str))
        if error:
            child_span.record_exception(error)

        child_span.end()

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

        self.root_span.set_attributes(
            {
                "workflow_name": self.trace_name,
                "workflow_id": str(self.trace_id),
                "outputs": json.dumps(safe_outputs, default=str),
                **safe_metadata,
            }
        )
        if error:
            self.root_span.record_exception(error)

        self.root_span.end()

    @staticmethod
    def _get_current_timestamp() -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1_000_000_000)

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
