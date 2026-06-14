from __future__ import annotations

import os
import threading
from collections import OrderedDict
from typing import TYPE_CHECKING, Any
from uuid import UUID

from lfx.log.logger import logger
from typing_extensions import override

from langflow.serialization.serialization import serialize
from langflow.services.tracing.base import BaseTracer

if TYPE_CHECKING:
    from collections.abc import Sequence

    from langchain_core.callbacks.base import BaseCallbackHandler
    from langfuse import Langfuse
    from langfuse._client.span import LangfuseSpan
    from langfuse.types import TraceContext
    from lfx.graph.vertex.base import Vertex

    from langflow.services.tracing.schema import Log


LANGFUSE_FEEDBACK_SCORE_NAME = "user-feedback"


class _SharedClient:
    """Process-wide cached Langfuse client.

    The Langfuse SDK spawns background threads per client instantiation
    (task_manager, prompt_cache, OTel exporters) and never joins them, so
    creating one per flow run leaks threads under load.
    See https://github.com/langflow-ai/langflow/issues/9066.
    """

    lock: threading.Lock = threading.Lock()
    client: Langfuse | None = None
    key: tuple[str, str, str] | None = None


def _get_or_create_shared_client(config: dict) -> Langfuse:
    """Return a process-wide Langfuse client, creating it once per credential set.

    Keyed by (secret_key, public_key, host) so credential rotation produces a
    fresh client rather than reusing a stale one.

    An isolated OpenTelemetry ``TracerProvider`` is passed to ``Langfuse(...)``
    so the SDK does not register itself as the global tracer provider. Without
    this, any library that uses the global provider (notably
    ``FastAPIInstrumentor`` in ``langflow.main``) would emit every HTTP request
    as a span into Langfuse, polluting traces with unrelated routes like health
    checks and flow list calls. See
    https://github.com/langflow-ai/langflow/issues/13319.
    """
    from langfuse import Langfuse
    from opentelemetry.sdk.trace import TracerProvider

    key = (config["secret_key"], config["public_key"], config["host"])
    with _SharedClient.lock:
        if _SharedClient.client is None or _SharedClient.key != key:
            isolated_tracer_provider = TracerProvider()
            _SharedClient.client = Langfuse(**config, tracer_provider=isolated_tracer_provider)
            _SharedClient.key = key
        return _SharedClient.client


def _reset_shared_client_for_tests() -> None:
    """Test-only hook: clear the cached client so each test gets a fresh mock."""
    with _SharedClient.lock:
        _SharedClient.client = None
        _SharedClient.key = None


def normalize_langfuse_trace_id(trace_id: UUID | str | None) -> str | None:
    """Normalize a Langfuse trace identifier to 32-char hex format."""
    if trace_id is None:
        return None
    if isinstance(trace_id, UUID):
        return trace_id.hex
    normalized = str(trace_id).replace("-", "").strip()
    return normalized or None


def feedback_score_id(message_id: UUID | str) -> str:
    """Build a stable Langfuse score id from a message id."""
    if isinstance(message_id, UUID):
        return message_id.hex
    return str(message_id).replace("-", "")


def langfuse_is_configured() -> bool:
    """Whether Langfuse credentials are set in the environment."""
    return bool(LangFuseTracer._get_config())


def _get_langfuse_client():
    """Return the shared, process-wide Langfuse client.

    Callers must gate on `langfuse_is_configured()` being truthy; this raises
    rather than silently no-opping so background-task failures don't
    disappear into the void.
    """
    config = LangFuseTracer._get_config()
    if not config:
        msg = (
            "Langfuse credentials missing — set LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY, "
            "and LANGFUSE_HOST (or LANGFUSE_BASE_URL)."
        )
        raise RuntimeError(msg)
    return _get_or_create_shared_client(config)


def sync_feedback_score(
    *,
    message_id: UUID | str,
    trace_id: UUID | str | None,
    session_id: str,
    flow_id: UUID | str | None,
    sender: str,
    positive_feedback: bool,
) -> None:
    """Send message feedback to Langfuse as a trace-linked score.

    Callers must gate this on tracing being enabled and Langfuse being
    configured; this function raises rather than silently no-opping so
    background-task failures surface in logs.
    """
    normalized_trace_id = normalize_langfuse_trace_id(trace_id)
    if not normalized_trace_id:
        msg = f"Cannot sync feedback score without a Langfuse trace id (message_id={message_id})."
        raise ValueError(msg)

    client = _get_langfuse_client()
    client.create_score(
        name=LANGFUSE_FEEDBACK_SCORE_NAME,
        value=1.0 if positive_feedback else 0.0,
        trace_id=normalized_trace_id,
        score_id=feedback_score_id(message_id),
        data_type="BOOLEAN",
        comment="positive" if positive_feedback else "negative",
        metadata={
            "message_id": str(message_id),
            "session_id": session_id,
            "flow_id": str(flow_id) if flow_id else None,
            "sender": sender,
        },
    )
    client.flush()


def delete_feedback_score(*, message_id: UUID | str) -> None:
    """Delete the Langfuse feedback score previously synced for a message.

    Used when a user clears their thumbs up/down so Langfuse stays in sync
    with Langflow's UI state. Callers must gate on tracing being enabled
    and Langfuse being configured.
    """
    client = _get_langfuse_client()
    client.api.score.delete(score_id=feedback_score_id(message_id))


class LangFuseTracer(BaseTracer):
    """LangFuse tracer implementation using langfuse v3 API.

    The v3 API uses OpenTelemetry-based spans instead of the v2 trace/span pattern.
    See: https://langfuse.com/docs/observability/sdk/upgrade-path
    """

    flow_id: str
    _trace_context: TraceContext
    langfuse_trace_id: str | None

    def __init__(
        self,
        trace_name: str,
        trace_type: str,
        project_name: str,
        trace_id: UUID,
        user_id: str | None = None,
        session_id: str | None = None,
        tracing_user_id: str | None = None,
    ) -> None:
        self.project_name = project_name
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.trace_id = trace_id
        # ``user_id`` remains the authenticated Langflow user and drives
        # ``trace.userId`` unchanged from pre-#9505 behavior. ``tracing_user_id``
        # is an optional caller-supplied label; when set, it is stamped into
        # trace metadata as ``langflow.tracing_user_id`` so consumers can still
        # access the override without redefining ``trace.userId``.
        self.user_id = user_id
        self.tracing_user_id = tracing_user_id
        self.session_id = session_id
        self.flow_id = trace_name.split(" - ")[-1]
        self.spans: dict[str, LangfuseSpan] = OrderedDict()
        self.langfuse_trace_id = None

        config = self._get_config()
        self._ready: bool = self._setup_langfuse(config) if config else False

    @property
    def ready(self):
        return self._ready

    def _setup_langfuse(self, config: dict) -> bool:
        """Initialize langfuse client and create root span for the flow.

        Uses langfuse v3 API which requires creating spans with trace_context
        instead of using the removed trace() method.

        Setup failures are logged at WARNING level so users see why traces
        are missing rather than silently getting a no-op tracer. The Langfuse
        v3 SDK uses ``pydantic.v1.BaseModel`` internally, which only supports
        Python 3.14 starting with ``pydantic>=2.13``; on older pydantic
        versions, importing langfuse raises ``pydantic.v1.errors.ConfigError``
        on Python 3.14, which the broad exception handler below previously
        swallowed at debug level. See
        https://github.com/langflow-ai/langflow/issues/13317.
        """
        try:
            from langfuse import Langfuse
            from langfuse.types import TraceContext

            self._client = _get_or_create_shared_client(config)

            # Health check using public API
            try:
                if not self._client.auth_check():
                    logger.warning("Langfuse authentication failed; check LANGFUSE_SECRET_KEY and LANGFUSE_PUBLIC_KEY.")
                    return False
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Cannot connect to Langfuse at {config.get('host')!r}: {e}")
                return False

            # Create a deterministic trace ID from the UUID (v3 requires 32-char hex)
            langfuse_trace_id = Langfuse.create_trace_id(seed=str(self.trace_id))
            self.langfuse_trace_id = langfuse_trace_id
            # parent_span_id is NotRequired but ty doesn't fully support this yet
            self._trace_context = TraceContext(trace_id=langfuse_trace_id)  # type: ignore[call-arg]

            # Create root span for the flow - this also creates the trace implicitly
            self._root_span = self._client.start_span(
                name=self.flow_id,
                trace_context=self._trace_context,
                metadata={"flow_id": self.flow_id, "project_name": self.project_name},
            )

            # ``trace.userId`` stays the authenticated Langflow user so existing
            # Langfuse consumers keep getting the same identity. When a caller
            # provides an override via ``tracing_user_id``, stamp it under
            # ``langflow.tracing_user_id`` so it is still recoverable from trace
            # metadata without changing the meaning of ``trace.userId``.
            trace_kwargs: dict[str, Any] = {
                "name": self.flow_id,
                "user_id": self.user_id,
                "session_id": self.session_id,
            }
            if self.tracing_user_id and self.tracing_user_id != self.user_id:
                trace_kwargs["metadata"] = {"langflow.tracing_user_id": self.tracing_user_id}
            self._root_span.update_trace(**trace_kwargs)

        except ImportError:
            logger.exception("Could not import langfuse. Please install it with `pip install langfuse`.")
            return False

        except Exception:  # noqa: BLE001
            # logger.exception emits at ERROR level with full traceback so users
            # see the real cause (e.g. pydantic.v1 incompatibility on Python
            # 3.14 with pydantic<2.13) instead of silently getting no traces.
            logger.exception("Error setting up LangFuse tracer")
            return False

        return True

    @override
    def add_trace(
        self,
        trace_id: str,  # actually component id
        trace_name: str,
        trace_type: str,
        inputs: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        vertex: Vertex | None = None,
    ) -> None:
        if not self._ready:
            return

        metadata_: dict = {"from_langflow_component": True, "component_id": trace_id}
        metadata_ |= {"trace_type": trace_type} if trace_type else {}
        metadata_ |= metadata or {}

        name = trace_name.removesuffix(f" ({trace_id})")

        # Create child span under the root span
        span = self._root_span.start_span(
            name=name,
            input=serialize(inputs),
            metadata=serialize(metadata_),
        )

        self.spans[trace_id] = span

    @override
    def end_trace(
        self,
        trace_id: str,
        trace_name: str,
        outputs: dict[str, Any] | None = None,
        error: Exception | None = None,
        logs: Sequence[Log | dict] = (),
    ) -> None:
        if not self._ready:
            return

        span = self.spans.pop(trace_id, None)
        if span:
            output: dict = {}
            output |= outputs or {}
            output |= {"error": str(error)} if error else {}
            output |= {"logs": list(logs)} if logs else {}

            # Update span with output and end it
            span.update(output=serialize(output))
            span.end()

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

        # Serialize once and reuse to avoid duplicate work
        inputs_ser = serialize(inputs)
        outputs_ser = serialize(outputs)
        metadata_ser = serialize(metadata) if metadata else None

        # Update the root span with final input/output
        self._root_span.update(
            input=inputs_ser,
            output=outputs_ser,
            metadata=metadata_ser,
        )

        # Update trace-level data
        self._root_span.update_trace(
            input=inputs_ser,
            output=outputs_ser,
            metadata=metadata_ser,
        )

        # End the root span
        self._root_span.end()

        # Flush buffered events so they are delivered before the flow finishes.
        # Best-effort: if the upstream is unreachable we still want flow end to
        # complete without raising.
        try:
            self._client.flush()
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Error flushing Langfuse client: {e}")

    def get_langchain_callback(self) -> BaseCallbackHandler | None:
        if not self._ready:
            return None

        try:
            from langfuse.langchain import CallbackHandler

            # Get the current span's context for proper nesting
            if self.spans:
                # Use the most recent span as parent
                current_span = next(reversed(self.spans.values()))
                # Create callback with parent context
                trace_ctx: TraceContext = {
                    "trace_id": self._trace_context["trace_id"],
                    "parent_span_id": current_span.id,
                }
                handler = CallbackHandler(trace_context=trace_ctx)
            else:
                # Fall back to root trace context
                handler = CallbackHandler(trace_context=self._trace_context)

        except (ImportError, ValueError, TypeError) as e:
            logger.debug(f"Error creating LangChain callback handler: {e}")
            return None
        else:
            return handler

    @staticmethod
    def _get_config() -> dict:
        secret_key = os.getenv("LANGFUSE_SECRET_KEY", None)
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY", None)
        host = os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST")
        if secret_key and public_key and host:
            return {"secret_key": secret_key, "public_key": public_key, "host": host}
        return {}
