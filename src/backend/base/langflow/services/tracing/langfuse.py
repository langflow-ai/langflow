from __future__ import annotations

import os
from collections import OrderedDict
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from typing_extensions import override

from langflow.serialization.serialization import serialize
from langflow.services.tracing.base import BaseTracer

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from langchain_core.callbacks.base import BaseCallbackHandler
    from langfuse._client.span import LangfuseSpan
    from langfuse.types import TraceContext
    from lfx.graph.vertex.base import Vertex

    from langflow.services.tracing.schema import Log


class LangFuseTracer(BaseTracer):
    """LangFuse tracer implementation using langfuse v4 API.

    The v4 SDK is OpenTelemetry-based: `start_observation` replaces v3's
    `start_span`; trace-level attributes (user_id, session_id, name) propagate
    via `propagate_attributes`, applied per `start_observation` call so the
    OTel context is attached in the same asyncio task that creates the
    observation; trace-level input/output go through `set_trace_io`.

    See: https://langfuse.com/docs/observability/sdk/upgrade-path/python-v3-to-v4
    """

    flow_id: str
    _trace_context: TraceContext

    def __init__(
        self,
        trace_name: str,
        trace_type: str,
        project_name: str,
        trace_id: UUID,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        self.project_name = project_name
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.trace_id = trace_id
        self.user_id = user_id
        self.session_id = session_id
        self.flow_id = trace_name.split(" - ")[-1]
        self.spans: dict[str, LangfuseSpan] = OrderedDict()

        self._propagated_attrs: dict[str, Any] = {"trace_name": self.flow_id}
        if user_id:
            self._propagated_attrs["user_id"] = user_id
        if session_id:
            self._propagated_attrs["session_id"] = session_id

        config = self._get_config()
        self._ready: bool = self._setup_langfuse(config) if config else False

    @property
    def ready(self):
        return self._ready

    def _setup_langfuse(self, config: dict) -> bool:
        """Initialize langfuse client and create root span for the flow.

        v4 differs from v3 in two load-bearing ways:
        - `start_observation` replaces `start_span`.
        - Trace-level attributes (user_id, session_id, name) are not span
          parameters; they propagate via `propagate_attributes`, an OTel
          context manager backed by `contextvars`. `asyncio.create_task`
          snapshots contextvars at task-creation time, so a token attached
          in one task is not visible to tasks created earlier. langflow's
          TracingService dispatches `add_trace` via a worker task that was
          spawned before the tracer is constructed, so we enter
          `propagate_attributes` per `start_observation` call rather than
          holding it open for the tracer's lifetime.
        """
        try:
            from langfuse import Langfuse, propagate_attributes
            from langfuse.types import TraceContext

            self._client = Langfuse(**config)
            self._propagate_attributes = propagate_attributes

            # Health check using public API
            try:
                if not self._client.auth_check():
                    logger.debug("Langfuse authentication failed")
                    return False
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Cannot connect to Langfuse: {e}")
                return False

            # Create a deterministic trace ID from the UUID (32-char hex)
            langfuse_trace_id = Langfuse.create_trace_id(seed=str(self.trace_id))
            # parent_span_id is NotRequired but ty doesn't fully support this yet
            self._trace_context = TraceContext(trace_id=langfuse_trace_id)  # type: ignore[call-arg]

            with self._propagate_attributes(**self._propagated_attrs):
                self._root_span = self._client.start_observation(
                    name=self.flow_id,
                    trace_context=self._trace_context,
                    metadata={"flow_id": self.flow_id, "project_name": self.project_name},
                )

        except ImportError:
            logger.exception("Could not import langfuse. Please install it with `pip install langfuse`.")
            return False

        except Exception as e:  # noqa: BLE001
            logger.debug(f"Error setting up LangFuse tracer: {e}")
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

        # Wrap start_observation in propagate_attributes so the child span
        # gets user.id/session.id/langfuse.trace.name. This call typically
        # runs in a different asyncio task than _setup_langfuse (langflow's
        # TracingService dispatches add_trace via a worker task), and
        # contextvars don't cross task boundaries forward-in-time.
        with self._propagate_attributes(**self._propagated_attrs):
            span = self._root_span.start_observation(
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

        # v4: trace-level input/output via set_trace_io. user_id/session_id/name
        # are propagated per start_observation call, not on a long-lived context,
        # so nothing to detach here.
        self._root_span.set_trace_io(
            input=inputs_ser,
            output=outputs_ser,
        )

        self._root_span.end()

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
