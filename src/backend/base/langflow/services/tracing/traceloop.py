from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

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
        """Initialize the Traceloop tracer.

        Args:
            trace_name: The name of the trace.
            trace_type: The type of the trace.
            project_name: The name of the project.
            trace_id: The ID of the trace.
            user_id: The ID of the user.
            session_id: The ID of the session.
        """
        self.trace_id = trace_id
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.project_name = project_name
        self.user_id = user_id
        self.session_id = session_id

        api_key = os.getenv("TRACELOOP_API_KEY")
        if not api_key or not api_key.strip():
            logger.warning("TRACELOOP_API_KEY not set. Traceloop tracing will not be enabled.")
            self._ready = False
            return
        try:
            Traceloop.init(
                instruments={Instruments.LANGCHAIN},
                app_name=project_name,
                disable_batch=True,
                api_key=api_key,
                api_endpoint=os.getenv("TRACELOOP_BASE_URL", "https://api.traceloop.com"),
            )
            self._ready = True
            self._workflow = None
            self._tracer = trace.get_tracer("langflow")
            logger.info("Traceloop tracer initialized successfully")
        except (ValueError, RuntimeError, OSError) as e:
            logger.error(f"Failed to initialize Traceloop tracer: {e}")
            self._ready = False

    @property
    def ready(self) -> bool:
        """Check if the tracer is ready."""
        return self._ready

    def _start_workflow(self, inputs: dict[str, Any], metadata: dict[str, Any] | None = None):
        return {"trace_id": str(self.trace_id), "inputs": inputs, "metadata": metadata or {}}

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
        """Add a trace to the tracer.

        Args:
            trace_id: The ID of the trace.
            trace_name: The name of the trace.
            trace_type: The type of the trace.
            inputs: The inputs to the trace.
            metadata: The metadata for the trace.
            vertex: The vertex associated with the trace.
        """
        if not self.ready:
            return

        # Start the workflow if it's not already started
        if self._workflow is None:
            self._workflow = self._start_workflow(
                inputs,
                {
                    "project_name": self.project_name,
                    "trace_type": self.trace_type,
                    "user_id": self.user_id,
                    "session_id": self.session_id,
                    **(metadata or {}),
                },
            )

        # Extract model_name and provider from metadata
        model_name = (metadata or {}).get("model_name")
        agent_llm = (metadata or {}).get("agent_llm")
        if not model_name:
            logger.warning(f"model_name not found in metadata for trace {trace_name}")
        if not agent_llm:
            logger.warning(f"agent_llm not found in metadata for trace {trace_name}")

        # Optionally, set as attributes on the workflow dict for later use
        if self._workflow is not None:
            self._workflow["model_name"] = model_name
            self._workflow["agent_llm"] = agent_llm

    @override
    def end_trace(
        self,
        trace_id: str,
        trace_name: str,
        outputs: dict[str, Any] | None = None,
        error: Exception | None = None,
        logs: Sequence[Log | dict] = (),
    ) -> None:
        """End a trace.

        Args:
            trace_id: The ID of the trace.
            trace_name: The name of the trace.
            outputs: The outputs of the trace.
            error: Any error that occurred.
            logs: The logs for the trace.
        """
        if not self.ready:
            return

        # Add span for component completion
        span_name = f"component.{trace_name}"
        with self._tracer.start_as_current_span(span_name) as span:
            if outputs:
                span.set_attributes({"outputs": str(outputs)})
            if error:
                span.record_exception(error)
            if logs:
                span.set_attributes({"logs": str(logs)})

    @override
    def end(
        self,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        error: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """End the trace.

        Args:
            inputs: The inputs to the trace.
            outputs: The outputs of the trace.
            error: Any error that occurred.
            metadata: The metadata for the trace.
        """
        if not self.ready:
            return

        # Add final span for workflow completion
        model_name = (metadata or {}).get("model_name") or ""
        agent_llm = (metadata or {}).get("agent_llm") or ""
        if not model_name:
            logger.warning(f"model_name not found in metadata for trace {self.trace_name}")
        if not agent_llm:
            logger.warning(f"agent_llm not found in metadata for trace {self.trace_name}")
        with self._tracer.start_as_current_span("workflow.end") as span:
            span.set_attributes(
                {
                    "workflow_name": self.trace_name,
                    "workflow_id": str(self.trace_id),
                    "outputs": str(outputs),
                    "model_name": model_name,
                    "agent_llm": agent_llm,
                    **(metadata or {}),
                }
            )
            if error:
                span.record_exception(error)

    @override
    def get_langchain_callback(self) -> BaseCallbackHandler | None:
        """Get the LangChain callback handler.

        Returns:
            The LangChain callback handler.
        """
        if not self.ready:
            return None

        try:
            from traceloop.sdk.instruments.langchain import TraceloopLangChainCallbackHandler

            return TraceloopLangChainCallbackHandler()
        except ImportError:
            logger.warning("Traceloop LangChain callback handler not available")
            return None


# Made with Bob
