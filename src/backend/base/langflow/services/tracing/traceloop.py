from __future__ import annotations

import json
import math
import os
import threading
import types
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from lfx.log.logger import logger
from lfx.observability import APPLICATION_INSTRUMENTATION_SCOPES
from opentelemetry import trace
from opentelemetry.sdk.trace import SpanProcessor
from opentelemetry.trace import Span, use_span
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from traceloop.sdk import Traceloop
from traceloop.sdk.instruments import Instruments
from typing_extensions import override

from langflow.services.tracing.base import BaseTracer

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from uuid import UUID

    from langchain_core.callbacks.base import BaseCallbackHandler
    from opentelemetry.propagators.textmap import CarrierT
    from opentelemetry.trace import Span

    from langflow.graph.vertex.base import Vertex
    from langflow.services.tracing.schema import Log


# ---------------------------------------------------------------------------------------------
# Keeping the service's own telemetry out of Traceloop's exporter.
#
# The SDK takes no tracer provider. It adopts whichever provider is global and attaches its
# exporter to that, so its exporter sees every span on that provider -- including the service's
# own HTTP and flow spans. ``instrument_fastapi_app`` runs unconditionally at startup, so those
# HTTP spans exist in every install, whether or not an APM is configured. Without a filter they
# are shipped to the vendor along with the LLM traces the operator actually asked for.
# ---------------------------------------------------------------------------------------------

# Traceloop.init is not reentrant (TracerWrapper is a singleton built in __new__) and the hook
# below is on a module attribute, so concurrent flow runs are serialised through this.
_INIT_LOCK = threading.Lock()

# Set once the filter has been observed to install. Only the init that actually builds the
# SDK's pipeline runs the factory; later ones are no-ops and must not be read as a failure.
_boundary_installed = False


class _ApplicationScopeFilter(SpanProcessor):
    """Delegates to a Traceloop processor, minus the spans that belong to the operator's APM.

    Everything the application allowlist does not claim is passed through, so the vendor keeps
    its own LLM spans and anything else it instruments. The default falls towards the vendor
    deliberately: the allowlist is the set we know the APM exports, and dropping only that is
    what makes this safe to wrap around a pipeline whose contents we do not control.

    Note that ``APPLICATION_INSTRUMENTATION_SCOPES`` is therefore load-bearing in two
    directions. Adding a scope to it enriches the APM *and* removes that scope from every
    Traceloop trace.
    """

    def __init__(self, wrapped: SpanProcessor) -> None:
        self._wrapped = wrapped
        self._dropped_scopes: set[str] = set()

    @override
    def on_start(self, span, parent_context=None) -> None:
        self._wrapped.on_start(span, parent_context)

    @override
    def on_end(self, span) -> None:
        scope = span.instrumentation_scope.name if span.instrumentation_scope else ""
        if scope not in APPLICATION_INSTRUMENTATION_SCOPES:
            self._wrapped.on_end(span)
            return
        if scope not in self._dropped_scopes:
            self._dropped_scopes.add(scope)
            logger.debug(f"Not sending {scope!r} spans to Traceloop; that is application telemetry.")

    @override
    def shutdown(self) -> None:
        self._wrapped.shutdown()

    @override
    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self._wrapped.force_flush(timeout_millis)


@contextmanager
def _application_telemetry_withheld() -> Iterator[None]:
    """Wrap the SDK's span processor factory for the duration of ``Traceloop.init``.

    The factory is the hook because it is the one place every export path goes through. The
    provider is not: patching ``add_span_processor`` only covers the case where a provider
    already exists, and misses the far more common one where no APM is configured, the global
    provider is still a proxy, and the SDK creates and registers its own concrete provider that
    the proxy then resolves onto. The provider is also shared, so a processor another
    integration registered during ``init`` would be wrapped and have this boundary applied
    backwards.

    Passing ``processor=`` to ``init`` is the other obvious hook and is worse: it turns off the
    SDK's metrics, drops the ``TRACELOOP_HEADERS`` auth the Instana integration depends on,
    makes ``disable_batch`` inert and skips prompt sync. Wrapping the factory leaves all of that
    alone, because from ``init``'s point of view no processor was supplied.

    Fails closed. ``traceloop-sdk`` is depended on across a wide range, and if a release stops
    routing through this factory the filter stops applying with no other symptom. A silent leak
    is the one failure mode an export boundary must not have, so an init that builds the SDK's
    pipeline without installing the filter raises instead of exporting unfiltered.

    Serialised because flows run concurrently and the hook is on a module attribute: two tracers
    initialising at once would otherwise have the first one's restore run while the second is
    still inside init, leaving that run's processor unwrapped.
    """
    global _boundary_installed  # noqa: PLW0603
    from traceloop.sdk.tracing import tracing as traceloop_tracing

    with _INIT_LOCK:
        original = traceloop_tracing.get_default_span_processor
        installed: list[_ApplicationScopeFilter] = []

        def get_default_span_processor(*args, **kwargs) -> SpanProcessor:
            span_processor = _ApplicationScopeFilter(original(*args, **kwargs))
            installed.append(span_processor)
            return span_processor

        traceloop_tracing.get_default_span_processor = get_default_span_processor
        try:
            yield
        finally:
            traceloop_tracing.get_default_span_processor = original

        if installed:
            _boundary_installed = True
        elif not _boundary_installed:
            msg = (
                "Traceloop was initialised without the filter that keeps Langflow's own "
                "telemetry out of its exporter, so the integration has been disabled rather "
                "than shipping the service's HTTP and flow spans to the vendor. This means the "
                "installed traceloop-sdk no longer builds its exporter through "
                "get_default_span_processor; pin traceloop-sdk to a version that does."
            )
            logger.error(msg)
            raise RuntimeError(msg)


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
        api_endpoint = os.getenv("TRACELOOP_BASE_URL", "https://api.traceloop.com")
        try:
            with _application_telemetry_withheld():
                Traceloop.init(
                    block_instruments={Instruments.PYMYSQL},
                    app_name=project_name,
                    disable_batch=True,
                    api_key=api_key,
                    api_endpoint=api_endpoint,
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
        from langchain_core.documents import Document
        from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

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
