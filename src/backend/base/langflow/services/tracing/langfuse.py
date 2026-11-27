from __future__ import annotations

import contextlib
import contextvars
import hashlib
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass
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
LANGFUSE_MAX_ATTRIBUTE_LENGTH = 200
_LANGFUSE_PROPAGATION_CONTEXT_KEYS = {
    "user_id": "langfuse.propagated.user_id",
    "session_id": "langfuse.propagated.session_id",
    "metadata": "langfuse.propagated.metadata",
    "trace_name": "langfuse.propagated.trace_name",
}


def _normalize_vendor_session_id(session_id: str | None) -> str | None:
    """Keep Langflow session IDs intact while making oversized vendor values valid."""
    if session_id is None or (session_id.isascii() and len(session_id) <= LANGFUSE_MAX_ATTRIBUTE_LENGTH):
        return session_id
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    return f"langflow-session-{digest}"


def _context_without_langfuse_attributes(context: Any) -> Any:
    """Copy an OTel context without inherited Langfuse propagation values."""
    from opentelemetry import baggage

    clean_context = context.copy()
    for key in list(clean_context):
        if isinstance(key, str) and key.startswith("langfuse.propagated."):
            del clean_context[key]
    inherited_baggage = baggage.get_all(context=clean_context)
    clean_context = baggage.clear(context=clean_context)
    for key, value in inherited_baggage.items():
        if not key.startswith("langfuse_"):
            clean_context = baggage.set_baggage(key, value, context=clean_context)
    return clean_context


@dataclass
class _CallbackPropagationScope:
    """One callback observation's active propagation context."""

    observation: Any
    context_token: Any = None


@dataclass
class _CallbackPropagationState:
    """Callback scopes owned by one execution context."""

    owner: Any
    caller_context: Any
    scopes: dict[UUID, _CallbackPropagationScope]
    active_run_id: UUID | None = None


def _normalize_boundary_messages(value: Any) -> Any:
    """Replace Langflow messages with their text while preserving container shape."""
    from lfx.schema.message import Message

    if isinstance(value, Message):
        return value.get_text()
    if isinstance(value, dict):
        return {key: _normalize_boundary_messages(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_normalize_boundary_messages(item) for item in value]
    return value


def _serialize_component_boundary(component_output: Any) -> Any:
    """Collapse a sole component output and normalize Langflow messages to text."""
    value = (
        next(iter(component_output.values()))
        if isinstance(component_output, dict) and len(component_output) == 1
        else component_output
    )
    return serialize(_normalize_boundary_messages(value))


def _trace_boundary_value(
    component_values: dict[str, Any],
    boundary_traces: dict[str, str],
    *,
    fallback_component_values: dict[str, Any] | None = None,
    prefer_fallback_trace_ids: set[str] | None = None,
) -> tuple[bool, Any]:
    """Return marked graph-boundary outputs in deterministic component-id order."""
    values = []
    prefer_fallback_trace_ids = prefer_fallback_trace_ids or set()
    for trace_id, trace_name in sorted(boundary_traces.items()):
        sources = (
            (fallback_component_values, component_values)
            if trace_id in prefer_fallback_trace_ids
            else (component_values, fallback_component_values)
        )
        for source in sources:
            if source is None or trace_name not in source:
                continue
            component_value = source[trace_name]
            if isinstance(component_value, dict) and not component_value:
                continue
            values.append(_serialize_component_boundary(component_value))
            break

    if not values:
        return False, None
    return True, values[0] if len(boundary_traces) == 1 else values


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
    """Test-only hook: stop background workers before clearing the cached client.

    Also clears the langfuse SDK's own process-global resource-manager registry
    (keyed by public_key); without it a prior test's client leaks into the next —
    e.g. a real-SDK test resolves to a stale manager with no in-memory exporter.
    """
    with _SharedClient.lock:
        _SharedClient.client = None
        _SharedClient.key = None
    with contextlib.suppress(Exception):
        from langfuse._client.resource_manager import LangfuseResourceManager
        from langfuse._client.span_processor import LangfuseSpanProcessor

        for resources in tuple(LangfuseResourceManager._instances.values()):
            resources.shutdown()
            resources.prompt_cache._task_manager.shutdown()
            if resources.tracer_provider is not None:
                # The SDK can adopt an application provider, so detach only its own processors.
                multiprocessor = resources.tracer_provider._active_span_processor
                with multiprocessor._lock:
                    processors = multiprocessor._span_processors
                    owned = tuple(processor for processor in processors if isinstance(processor, LangfuseSpanProcessor))
                    multiprocessor._span_processors = tuple(
                        processor for processor in processors if processor not in owned
                    )
                for processor in owned:
                    processor.shutdown()
        LangfuseResourceManager._instances.clear()


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
    and Langfuse being configured. Langfuse v4 moved the legacy score-delete
    endpoint under ``client.api.legacy.score_v1``.
    """
    client = _get_langfuse_client()
    legacy_api = getattr(getattr(client.api, "legacy", None), "score_v1", None)
    score_api = legacy_api or getattr(client.api, "score", None)
    delete_score = getattr(score_api, "delete", None)
    if delete_score is None:
        logger.warning(
            "Langfuse does not support deleting feedback scores in this SDK; leaving score {} unchanged",
            feedback_score_id(message_id),
        )
        return
    delete_score(score_id=feedback_score_id(message_id))


@cache
def _langchain_handler_cls(base_cls: type) -> type:
    """Add flow attributes to the observations activated by the Langfuse v4 handler."""

    class _FlowCallbackHandler(base_cls):  # type: ignore[misc, valid-type]
        def __init__(self, *, trace_attributes: dict[str, Any], **kwargs: Any) -> None:
            super().__init__(**kwargs)
            # Langflow owns a lexical invocation scope around model calls. Keep
            # callbacks inline so the model task inherits active attribution;
            # the lexical scope, not callback completion, restores the caller.
            self.run_inline = True
            self._trace_attributes = trace_attributes
            self._attribute_state: contextvars.ContextVar[_CallbackPropagationState | None] = contextvars.ContextVar(
                "langflow_langfuse_callback_state", default=None
            )
            self._states_by_run: dict[UUID, _CallbackPropagationState] = {}

        def __deepcopy__(self, memo: dict[int, Any]) -> Any:
            # Component snapshots must reuse the callback and its SDK client (#13965).
            memo[id(self)] = self
            return self

        def __copy__(self) -> Any:
            return self

        @contextlib.contextmanager
        def langflow_invocation_scope(self):
            """Keep this handler's Langfuse attributes active for one invocation."""
            from langfuse import propagate_attributes
            from opentelemetry import context, trace

            clean_context = _context_without_langfuse_attributes(context.get_current())
            clean_context = trace.set_span_in_context(trace.INVALID_SPAN, clean_context)
            token = context.attach(clean_context)
            try:
                with propagate_attributes(**self._trace_attributes):
                    yield
            finally:
                context.detach(token)

        @staticmethod
        def _execution_owner() -> Any:
            try:
                import asyncio

                return asyncio.current_task()
            except RuntimeError:
                return threading.get_ident()

        def _state(self) -> _CallbackPropagationState:
            state = self._attribute_state.get()
            owner = self._execution_owner()
            if state is None or state.owner != owner:
                from opentelemetry import context

                state = _CallbackPropagationState(owner, context.get_current(), {})
                self._attribute_state.set(state)
            return state

        def _deactivate_attribute_scope(self) -> None:
            state = self._state()
            if state.active_run_id is None:
                return
            scope = state.scopes[state.active_run_id]
            if scope.context_token is not None:
                from opentelemetry import context

                # AsyncCallbackManager may run start/end in different copied
                # contextvars contexts. Detach only in the owning context; the
                # lexical invocation scope owns caller-task restoration.
                with contextlib.suppress(Exception):
                    context.detach(scope.context_token)
                scope.context_token = None
            state.active_run_id = None

        def _activate_attribute_scope(self, run_id: UUID) -> None:
            from opentelemetry import context, trace

            state = self._state()
            scope = state.scopes[run_id]
            base_context = _context_without_langfuse_attributes(state.caller_context)
            observation_span = getattr(scope.observation, "_otel_span", None)
            if observation_span is not None:
                base_context = trace.set_span_in_context(observation_span, base_context)
            for key in ("user_id", "session_id", "trace_name"):
                value = self._trace_attributes.get(key)
                if value is not None:
                    base_context = context.set_value(
                        _LANGFUSE_PROPAGATION_CONTEXT_KEYS[key], value, context=base_context
                    )
            metadata = self._trace_attributes.get("metadata")
            if metadata:
                base_context = context.set_value(
                    _LANGFUSE_PROPAGATION_CONTEXT_KEYS["metadata"], metadata, context=base_context
                )
            if observation_span is not None and observation_span.is_recording():
                if (user_id := self._trace_attributes.get("user_id")) is not None:
                    observation_span.set_attribute("user.id", user_id)
                if (session_id := self._trace_attributes.get("session_id")) is not None:
                    observation_span.set_attribute("session.id", session_id)
                if (trace_name := self._trace_attributes.get("trace_name")) is not None:
                    observation_span.set_attribute("langfuse.trace.name", trace_name)
                for key, value in (metadata or {}).items():
                    observation_span.set_attribute(f"langfuse.observation.metadata.{key}", str(value))
            scope.context_token = context.attach(base_context)
            state.active_run_id = run_id

        def _attach_observation(self, run_id: UUID, observation: Any) -> None:
            state = self._state()
            # Keep one SDK propagation token active at a time. LangChain can
            # complete sibling runs out of order, for which nested SDK tokens
            # cannot be detached safely.
            self._deactivate_attribute_scope()
            super()._attach_observation(run_id, observation)
            state.scopes[run_id] = _CallbackPropagationScope(observation=observation)
            self._states_by_run[run_id] = state
            self._activate_attribute_scope(run_id)

        def _detach_observation(self, run_id: UUID) -> Any:
            # Deactivate before the base handler detaches its observation token;
            # this keeps the SDK token and attribute scope paired.
            state = self._states_by_run.pop(run_id, None) or self._state()
            if state.owner == self._execution_owner():
                self._deactivate_attribute_scope()
            result = super()._detach_observation(run_id)
            state.scopes.pop(run_id, None)
            if state.scopes and state.owner == self._execution_owner():
                self._activate_attribute_scope(next(reversed(state.scopes)))
            elif state.owner == self._execution_owner():
                self._attribute_state.set(None)
            return result

    return _FlowCallbackHandler


class LangFuseTracer(BaseTracer):
    """LangFuse tracer implementation using the Langfuse v4 API.

    The v4 API uses OpenTelemetry-based observations instead of the v2 trace/span pattern.
    See: https://langfuse.com/docs/observability/sdk/upgrade-path
    """

    flow_id: str
    flow_name: str
    flow_display_name: str
    _trace_context: TraceContext
    langfuse_trace_id: str | None
    _trace_metadata: dict[str, str]

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
        # ``user_id`` stays the authenticated user (drives ``trace.userId``); ``tracing_user_id`` is
        # stamped into metadata as ``langflow.tracing_user_id`` instead of overriding it (#9505).
        self.user_id = user_id
        self.tracing_user_id = tracing_user_id
        self.session_id = session_id
        # ``trace_name`` arrives as ``f"{flow_name} - {flow_id}"`` (lfx graph/base.py). Split from the
        # right so a display name that itself contains " - " survives intact.
        self.flow_name, _, self.flow_id = trace_name.rpartition(" - ")
        # The graph formats a missing flow name as the literal "None". Detect it like the LangWatch and
        # Arize tracers do, but fall back to the flow id (not the project name) so the trace stays
        # uniquely identifiable.
        self.flow_display_name = self.flow_name if self.flow_name and self.flow_name != "None" else self.flow_id
        self.spans: dict[str, LangfuseSpan] = OrderedDict()
        self._input_trace_names: dict[str, str] = {}
        self._output_trace_names: dict[str, str] = {}
        self.langfuse_trace_id = None
        self._trace_metadata = {}

        config = self._get_config()
        self._ready: bool = self._setup_langfuse(config) if config else False

    @property
    def ready(self):
        return self._ready

    def _setup_langfuse(self, config: dict) -> bool:
        """Initialize langfuse client and create root span for the flow.

        Uses the Langfuse v4 observation API with trace_context
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

            # Create a deterministic trace ID from the UUID (Langfuse requires 32-char hex)
            langfuse_trace_id = Langfuse.create_trace_id(seed=str(self.trace_id))
            self.langfuse_trace_id = langfuse_trace_id
            # parent_span_id is NotRequired but ty doesn't fully support this yet
            self._trace_context = TraceContext(trace_id=langfuse_trace_id)  # type: ignore[call-arg]

            # Langfuse v4 propagates trace-level attributes while observations
            # are created. Keep the metadata string-valued as required by the
            # SDK so every child observation receives the same attributes.
            self._trace_metadata = {"flow_id": self.flow_id, "project_name": self.project_name}
            if self.tracing_user_id and self.tracing_user_id != self.user_id:
                self._trace_metadata["langflow.tracing_user_id"] = self.tracing_user_id

            # Create the root observation for the flow. This also creates the
            # trace implicitly, and replaces the removed ``update_trace`` calls.
            # It is named after the flow so traces can be found by name in
            # Langfuse; the id stays in metadata.
            with self._observation_attributes():
                self._root_span = self._client.start_observation(
                    name=self.flow_display_name,
                    as_type="span",
                    trace_context=self._trace_context,
                    metadata=self._trace_metadata,
                )

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

        if vertex is not None:
            if vertex.is_input:
                self._input_trace_names[trace_id] = trace_name
            if vertex.is_output:
                self._output_trace_names[trace_id] = trace_name

        # Create a child observation under the root observation. Re-enter the
        # propagation context for each observation because flow callbacks may
        # run in different async contexts.
        with self._observation_attributes():
            span = self._root_span.start_observation(
                name=name,
                as_type="span",
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

        # Keep the evaluator-facing graph-boundary contract that the v3
        # integration exposed through ``update_trace``. In v4 the root
        # observation is the trace-level record, so write the selected
        # boundary values directly to it instead of dropping that distinction.
        inputs_ser = serialize(inputs)
        outputs_ser = serialize(outputs)
        metadata_ser = serialize(metadata) if metadata else None

        dual_role_trace_ids = self._input_trace_names.keys() & self._output_trace_names.keys()
        input_found, trace_input = _trace_boundary_value(
            outputs,
            self._input_trace_names,
            fallback_component_values=inputs,
            prefer_fallback_trace_ids=dual_role_trace_ids,
        )
        if not input_found:
            trace_input = inputs_ser

        output_found, trace_output = _trace_boundary_value(outputs, self._output_trace_names)
        if not output_found:
            trace_output = outputs_ser

        # Langfuse v4 no longer exposes a separate ``update_trace`` API; the
        # root observation is the trace-level record.
        self._root_span.update(
            input={"input": trace_input},
            output={"output": trace_output},
            metadata=metadata_ser,
        )
        self._root_span.set_trace_io(input={"input": trace_input}, output={"output": trace_output})

        # End the root span
        self._root_span.end()

        # Flush buffered events so they are delivered before the flow finishes.
        # Best-effort: if the upstream is unreachable we still want flow end to
        # complete without raising.
        try:
            self._client.flush()
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Error flushing Langfuse client: {e}")

    def _attributes(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "session_id": _normalize_vendor_session_id(self.session_id),
            "metadata": self._trace_metadata,
            "trace_name": self.flow_display_name,
        }

    @contextlib.contextmanager
    def _observation_attributes(self):
        from langfuse import propagate_attributes
        from opentelemetry import context, trace

        # Start from a copy without inherited Langfuse attributes. The SDK
        # merges metadata and ignores None values, so entering directly from an
        # ambient flow can otherwise leak its user/session into this flow.
        clean_context = _context_without_langfuse_attributes(context.get_current())
        clean_context = trace.set_span_in_context(trace.INVALID_SPAN, clean_context)
        context_token = context.attach(clean_context)
        try:
            # Explicit trace_context parents on the observation keep the flow
            # linked while the invalid active span prevents caller-span mutation.
            with propagate_attributes(**self._attributes()):
                yield
        finally:
            context.detach(context_token)

    @contextlib.contextmanager
    def langflow_invocation_scope(self):
        """Keep Langfuse attributes active for one caller-owned model invocation."""
        from langfuse import propagate_attributes
        from opentelemetry import context, trace

        clean_context = _context_without_langfuse_attributes(context.get_current())
        clean_context = trace.set_span_in_context(trace.INVALID_SPAN, clean_context)
        token = context.attach(clean_context)
        try:
            with propagate_attributes(**self._attributes()):
                yield
        finally:
            context.detach(token)

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

            # Langfuse v4 honors the explicit parent for bare LLMs and wrapped chains.
            handler = _langchain_handler_cls(CallbackHandler)(
                trace_context=trace_ctx, trace_attributes=self._attributes()
            )

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
