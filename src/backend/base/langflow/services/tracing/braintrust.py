"""Braintrust tracer for Langflow.

Implements Langflow's BaseTracer interface to send component-level and
LangChain-level traces to Braintrust.

Dependencies:
- ``braintrust`` (required) -- core SDK for span creation and logging.
- ``braintrust-langchain`` (optional) -- provides deep LangChain tracing
  with token metrics, time-to-first-token, and streaming support.
  Install with ``pip install braintrust-langchain``.

Activation: set the BRAINTRUST_API_KEY environment variable.
Optional: BRAINTRUST_API_URL, BRAINTRUST_PROJECT.
"""

from __future__ import annotations

import os
import types
from typing import TYPE_CHECKING, Any

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from lfx.log.logger import logger
from typing_extensions import override

from langflow.schema.data import Data
from langflow.schema.message import Message
from langflow.services.tracing.base import BaseTracer

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from langchain.callbacks.base import BaseCallbackHandler
    from lfx.graph.vertex.base import Vertex

    from langflow.services.tracing.schema import Log


class BraintrustTracer(BaseTracer):
    """Traces Langflow flow executions to Braintrust.

    This tracer creates a root span for each flow run and child spans for
    each component execution.  Each Langflow component (prompt, model,
    tool, retriever, etc.) is captured as a span with its inputs, outputs,
    metadata, and any errors.

    If ``braintrust-langchain`` is installed, ``get_langchain_callback``
    returns a ``BraintrustCallbackHandler`` that provides deeper tracing
    of LangChain operations (LLM calls with token metrics,
    time-to-first-token, tool usage, retriever queries, etc.).
    """

    flow_id: str

    def __init__(
        self,
        trace_name: str,
        trace_type: str,
        project_name: str,
        trace_id: UUID,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """Initialize the Braintrust tracer.

        Reads configuration from environment variables and sets up a root span
        for the current flow execution.  If ``BRAINTRUST_API_KEY`` is not set
        or the ``braintrust`` package is not installed, the tracer silently
        disables itself (``ready`` returns ``False``).

        Args:
            trace_name: Human-readable name for the trace (e.g. ``"My Flow - abc123"``).
            trace_type: The type of trace (typically ``"chain"``).
            project_name: Langflow project name, used as the Braintrust project
                if ``BRAINTRUST_PROJECT`` is not set.
            trace_id: Unique identifier for this flow execution.
            user_id: Optional Langflow user ID attached as span metadata.
            session_id: Optional Langflow session ID attached as span metadata.
        """
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.trace_id = trace_id
        self.user_id = user_id
        self.session_id = session_id
        self.flow_id = trace_name.split(" - ")[-1]
        self.spans: dict[str, Any] = {}

        config = self._get_config()
        self._ready: bool = self._setup_braintrust(config, project_name) if config else False

    @property
    def ready(self) -> bool:
        """Return whether the tracer is configured and operational."""
        return self._ready

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_braintrust(self, config: dict[str, Any], project_name: str) -> bool:
        """Initialize the Braintrust logger and create the root span.

        Args:
            config: Configuration dict from :meth:`_get_config` containing
                ``api_key`` and optionally ``api_url`` and ``project``.
            project_name: Fallback project name if ``BRAINTRUST_PROJECT`` is
                not set in the environment.

        Returns:
            ``True`` if setup succeeded, ``False`` on import or SDK errors.
        """
        try:
            from braintrust import init_logger

            project = config.pop("project", None) or project_name or "Langflow"
            self._logger = init_logger(
                project=project,
                api_key=config.get("api_key"),
                app_url=config.get("api_url"),
            )

            # Create a root span for this flow execution
            self._root_span = self._logger.start_span(
                name=self.flow_id,
                input={
                    "trace_name": self.trace_name,
                    "trace_type": self.trace_type,
                },
                metadata={
                    "langflow_trace_id": str(self.trace_id),
                    "langflow_trace_name": self.trace_name,
                    "user_id": self.user_id,
                    "session_id": self.session_id,
                    "created_from": "langflow",
                },
            )
        except ImportError:
            logger.exception("Could not import braintrust. Please install it with `pip install braintrust`.")
            return False
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Error setting up Braintrust tracer: {e}")
            return False

        return True

    # ------------------------------------------------------------------
    # BaseTracer interface
    # ------------------------------------------------------------------

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
        """Start a child span for a Langflow component execution.

        Creates a new span under the root flow span.  The span remains open
        until :meth:`end_trace` is called with the same *trace_id*.

        Args:
            trace_id: Unique component identifier (used to correlate with :meth:`end_trace`).
            trace_name: Display name, typically ``"ComponentName (trace_id)"``.
            trace_type: Component type (e.g. ``"llm"``, ``"tool"``, ``"retriever"``).
            inputs: Component input data.
            metadata: Additional metadata to attach to the span.
            vertex: Optional Langflow vertex (unused, kept for interface compatibility).
        """
        if not self._ready:
            return

        name = trace_name.removesuffix(f" ({trace_id})")
        processed_inputs = self._convert_to_loggable(inputs) if inputs else {}
        processed_metadata = self._convert_to_loggable(metadata) if metadata else {}

        processed_metadata["from_langflow_component"] = True
        processed_metadata["component_id"] = trace_id
        if trace_type:
            processed_metadata["trace_type"] = trace_type

        span = self._root_span.start_span(
            name=name,
            input=processed_inputs,
            metadata=processed_metadata,
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
        """End the child span for a component and log its outputs.

        Args:
            trace_id: The component identifier passed to :meth:`add_trace`.
            trace_name: Display name of the component.
            outputs: Component output data.
            error: Exception raised during component execution, if any.
            logs: Additional log entries to attach to the span.
        """
        if not self._ready:
            return

        span = self.spans.pop(trace_id, None)
        if span is None:
            logger.warning(f"Braintrust: no span found for trace_id={trace_id}")
            return

        output: dict[str, Any] = {}
        output |= self._convert_to_loggable(outputs) if outputs else {}
        if logs:
            output["logs"] = [self._convert_to_loggable(log) if isinstance(log, dict) else str(log) for log in logs]

        span.log(
            output=output,
            error=str(error) if error else None,
        )
        span.end()

    @override
    def end(
        self,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        error: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """End the root flow span and log aggregated inputs/outputs.

        Called once when the entire flow execution completes.

        Args:
            inputs: Aggregated flow inputs.
            outputs: Aggregated flow outputs.
            error: Exception raised during flow execution, if any.
            metadata: Additional metadata for the root span.
        """
        if not self._ready:
            return

        self._root_span.log(
            input=self._convert_to_loggable(inputs) if inputs else {},
            output=self._convert_to_loggable(outputs) if outputs else {},
            error=str(error) if error else None,
            metadata=self._convert_to_loggable(metadata) if metadata else {},
        )
        self._root_span.end()

    @override
    def get_langchain_callback(self) -> BaseCallbackHandler | None:
        """Return a LangChain callback handler for deep tracing.

        If ``braintrust-langchain`` is installed, returns a
        ``BraintrustCallbackHandler`` parented to the most recent open
        component span (or the root span if no component span is active).
        This provides token-level metrics, time-to-first-token, and model
        name capture for LLM calls.

        Returns:
            A ``BraintrustCallbackHandler`` instance, or ``None`` if the
            tracer is not ready or ``braintrust-langchain`` is not installed.
        """
        if not self._ready:
            return None

        try:
            from braintrust_langchain import BraintrustCallbackHandler
        except ImportError:
            return None

        # Use the most recent open span as parent so LangChain traces
        # nest under the current Langflow component span.
        parent_span = (
            self.spans[next(reversed(self.spans))]
            if self.spans
            else self._root_span
        )
        return BraintrustCallbackHandler(logger=parent_span)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _convert_to_loggable(self, value: Any) -> Any:
        """Recursively convert Langflow/LangChain types to JSON-serializable values."""
        if isinstance(value, dict):
            return {str(k): self._convert_to_loggable(v) for k, v in value.items() if k is not None}
        if isinstance(value, list):
            return [self._convert_to_loggable(v) for v in value]
        if isinstance(value, Message):
            return value.text
        if isinstance(value, Data):
            return value.get_text()
        if isinstance(value, (BaseMessage, HumanMessage, SystemMessage)):
            return value.content
        if isinstance(value, Document):
            return value.page_content
        if isinstance(value, (types.GeneratorType, types.NoneType)):
            return str(value)
        return value

    @staticmethod
    def _get_config() -> dict[str, Any]:
        """Read Braintrust configuration from environment variables.

        Returns an empty dict if the required BRAINTRUST_API_KEY is not set.
        """
        api_key = os.getenv("BRAINTRUST_API_KEY")
        if not api_key:
            return {}

        config: dict[str, Any] = {"api_key": api_key}

        api_url = os.getenv("BRAINTRUST_API_URL")
        if api_url:
            config["api_url"] = api_url

        project = os.getenv("BRAINTRUST_PROJECT")
        if project:
            config["project"] = project

        return config
