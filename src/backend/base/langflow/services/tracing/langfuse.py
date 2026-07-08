from __future__ import annotations

import os
import threading
from collections import OrderedDict
from functools import cache
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


def _build_otel_parent_span(trace_id: str | None, parent_span_id: str | None):
    """Build a non-recording OpenTelemetry span pointing at an existing Langfuse span.

    Mirrors the SDK's private ``Langfuse._create_remote_parent_span`` using only
    public values we already hold — the flow ``trace_id`` and the parent span id.
    The returned span is suitable for ``opentelemetry.trace.use_span(...)`` so a
    subsequently created span nests under it and inherits the same trace id.

    Returns ``None`` when either id is missing or not valid hex (e.g. under unit
    tests that use mock span ids) so callers degrade to the SDK's default behavior
    instead of raising.
    """
    if not trace_id or not parent_span_id:
        return None

    from opentelemetry import trace as otel_trace_api

    try:
        int_trace_id = int(trace_id, 16)
        int_span_id = int(parent_span_id, 16)
    except (TypeError, ValueError):
        return None

    span_context = otel_trace_api.SpanContext(
        trace_id=int_trace_id,
        span_id=int_span_id,
        is_remote=False,
        trace_flags=otel_trace_api.TraceFlags(0x01),  # mark span as sampled
    )
    return otel_trace_api.NonRecordingSpan(span_context)


@cache
def _root_run_reparenting_handler_cls(base_cls: type) -> type:
    """Build a langfuse ``CallbackHandler`` subclass that re-parents root LLM runs.

    Why this exists
    ---------------
    The langfuse v3 LangChain ``CallbackHandler`` only applies its constructor
    ``trace_context`` on the chain path (``on_chain_start``). When a model runs as
    the *root* LangChain run — e.g. a bare Ollama / chat-model call with no wrapping
    chain — the generation path calls ``start_observation`` without that
    ``trace_context``. With no active OpenTelemetry span in context, the generation
    starts a brand-new root trace, orphaned from the flow trace and therefore
    missing ``userId`` / ``sessionId`` and its token-usage metrics.
    See https://github.com/langflow-ai/langflow/issues/13429.

    The fix
    -------
    For root LLM runs we activate the flow's component (or root) span as the current
    OpenTelemetry span while the SDK creates the generation span. The generation then
    inherits the flow ``trace_id`` and nests under that span, restoring user/session
    attribution. The handler sets ``run_inline = True``, so these callbacks execute
    synchronously inside the model invocation and the activation reliably wraps span
    creation. Non-root runs (wrapping chain/agent present) are left untouched — the
    SDK already nests those correctly under the chain span.

    Cached per ``base_cls`` so repeated callbacks reuse a single class object.
    """
    from opentelemetry import trace as otel_trace_api

    class _RootRunReparentingCallbackHandler(base_cls):  # type: ignore[misc, valid-type]
        def __init__(self, *, otel_parent: Any = None, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self._otel_parent = otel_parent

        def _reparent(self, method_name: str, args: tuple, kwargs: dict, parent_run_id: UUID | None):
            bound = getattr(super(), method_name)
            if parent_run_id is None and self._otel_parent is not None:
                # end_on_exit/record_exception False so the parent span is never
                # mutated or closed by activating it as the current context.
                with otel_trace_api.use_span(
                    self._otel_parent,
                    end_on_exit=False,
                    record_exception=False,
                    set_status_on_exception=False,
                ):
                    return bound(*args, parent_run_id=parent_run_id, **kwargs)
            return bound(*args, parent_run_id=parent_run_id, **kwargs)

        def on_chat_model_start(self, *args: Any, parent_run_id: UUID | None = None, **kwargs: Any) -> Any:
            return self._reparent("on_chat_model_start", args, kwargs, parent_run_id)

        def on_llm_start(self, *args: Any, parent_run_id: UUID | None = None, **kwargs: Any) -> Any:
            return self._reparent("on_llm_start", args, kwargs, parent_run_id)

    return _RootRunReparentingCallbackHandler


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

            # Nest LangChain work under the most recent open component span when
            # there is one, else under the flow root span. Both share the flow
            # trace_id, so generations stay attributed to the flow's user/session.
            parent_span = next(reversed(self.spans.values())) if self.spans else self._root_span
            trace_ctx: TraceContext = {
                "trace_id": self._trace_context["trace_id"],
                "parent_span_id": parent_span.id,
            }

            # ``trace_context`` alone keeps chain/agent runs nested (the SDK honors
            # it on the chain path). ``otel_parent`` additionally re-parents *root*
            # LLM runs (a bare model with no wrapping chain), which the SDK would
            # otherwise emit as an orphan trace with no user/session and detached
            # token usage. See https://github.com/langflow-ai/langflow/issues/13429.
            otel_parent = _build_otel_parent_span(self._trace_context["trace_id"], parent_span.id)
            handler_cls = _root_run_reparenting_handler_cls(CallbackHandler)
            handler = handler_cls(trace_context=trace_ctx, otel_parent=otel_parent)

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
