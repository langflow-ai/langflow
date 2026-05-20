"""Base class for OpenTelemetry-based tracers."""

from __future__ import annotations

import json
import math
import types
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from lfx.log.logger import logger
from lfx.schema.data import Data

from langflow.schema.message import Message
from langflow.services.tracing.base import BaseTracer

if TYPE_CHECKING:
    from opentelemetry.propagators.textmap import CarrierT
    from opentelemetry.trace import Span, Tracer


class OTLPTracerBase(BaseTracer):
    """Base class for OpenTelemetry Protocol (OTLP) tracers.

    Provides common functionality for tracers that use OpenTelemetry,
    including span management, type conversion, and timestamp utilities.
    """

    def __init__(self) -> None:
        """Initialize common OTLP tracer attributes."""
        self._ready: bool = False
        self.tracer: Tracer | None = None
        self.root_span: Span | None = None
        self.child_spans: dict[str, Span] = {}
        self.carrier: CarrierT | dict = {}

    @property
    def ready(self) -> bool:
        """Indicates if the tracer is ready for usage."""
        return self._ready

    @staticmethod
    def _get_current_timestamp() -> int:
        """Gets the current UTC timestamp in nanoseconds.

        Returns:
            int: Current timestamp in nanoseconds since epoch.
        """
        return int(datetime.now(timezone.utc).timestamp() * 1_000_000_000)

    @staticmethod
    def _safe_json_dumps(obj: Any, **kwargs: Any) -> str:
        """A convenience wrapper around json.dumps that ensures any object can be safely encoded.

        Args:
            obj: The object to serialize.
            **kwargs: Additional arguments to pass to json.dumps.

        Returns:
            str: JSON string representation of the object.
        """
        return json.dumps(obj, default=str, ensure_ascii=False, **kwargs)

    def _convert_langflow_type(self, value: Any) -> Any:
        """Recursively converts a Langflow value to an OTLP-compatible type.

        Handles conversion of Langflow-specific types like Message and Data,
        as well as LangChain types like BaseMessage and Document.

        Args:
            value: The value to convert.

        Returns:
            Any: The converted value in an OTLP-compatible format.
        """
        try:
            if isinstance(value, dict):
                return {key: self._convert_langflow_type(val) for key, val in value.items()}

            if isinstance(value, list):
                return [self._convert_langflow_type(v) for v in value]

            if isinstance(value, Message):
                return value.text

            if isinstance(value, Data):
                data = value.data
                return self._convert_langflow_type(data) if isinstance(data, (dict, list)) else value.get_text()

            if isinstance(value, (BaseMessage, HumanMessage, SystemMessage)):
                return str(value.content) if value.content is not None else ""

            if isinstance(value, Document):
                return value.page_content

            if isinstance(value, (types.GeneratorType, types.NoneType)):
                return str(value)

            if isinstance(value, float) and not math.isfinite(value):
                return "NaN"
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to convert langflow value of type {type(value).__name__} to otel type: {e}")
            return str(value)
        else:
            return value

    def _convert_to_otlp_dict(self, io_dict: dict[str, Any] | Any) -> dict[str, Any]:
        """Converts a dict to OTLP-compatible format.

        Ensures all keys are strings and all values are OTLP-compatible types.
        Note: returned values may still contain nested dicts/lists. Use
        ``_to_span_attributes`` when values will be passed directly to
        ``Span.set_attribute()``.

        Args:
            io_dict: The dictionary to convert, or other value to wrap in a dict.

        Returns:
            dict[str, Any]: Dictionary with string keys and OTLP-compatible values.
        """
        if isinstance(io_dict, dict):
            return {str(k): self._convert_langflow_type(v) for k, v in io_dict.items() if k is not None}
        if isinstance(io_dict, list):
            return {"list": json.dumps([self._convert_langflow_type(v) for v in io_dict], default=str)}
        return {"value": self._convert_langflow_type(io_dict)}

    def _to_span_attributes(self, data: dict[str, Any] | Any) -> dict[str, str | bool | int | float]:
        """Convert a dict to span-attribute-safe key/value pairs.

        OpenTelemetry span attributes only accept primitive types (str, bool,
        int, float) and homogeneous sequences of primitives.  Any nested
        container (dict or list) is JSON-stringified so that ``set_attribute``
        never receives an unsupported type.

        Args:
            data: The dictionary (or other value) to convert.

        Returns:
            dict: Flat dictionary safe for ``Span.set_attribute()`` calls.
        """
        converted = self._convert_to_otlp_dict(data)
        result: dict[str, str | bool | int | float] = {}
        for key, value in converted.items():
            if isinstance(value, (dict, list)):
                result[key] = json.dumps(value, default=str, ensure_ascii=False)
            else:
                result[key] = value
        return result

    def _enable_http_context_propagation(self, provider: Any) -> None:
        """Enable W3C TraceContext propagation on outgoing HTTP requests.

        Uses reference counting - safe to call multiple times. Each enable()
        must be paired with a disable() call.

        Args:
            provider: The TracerProvider to use for instrumentation.
        """
        from langflow.services.tracing.http_instrumentation import get_http_instrumentation_manager

        get_http_instrumentation_manager().enable(provider)

    def _disable_http_context_propagation(self) -> None:
        """Disable HTTP context propagation (decrements ref count).

        Only actually uninstruments when the reference count reaches zero.
        """
        from langflow.services.tracing.http_instrumentation import get_http_instrumentation_manager

        get_http_instrumentation_manager().disable()

    def close(self) -> None:
        """Flush spans safely before shutdown.

        Subclasses should override this to implement provider-specific flushing.
        """

    def __del__(self) -> None:
        """Ensure tracer provider flushes on object destruction."""
        self.close()
