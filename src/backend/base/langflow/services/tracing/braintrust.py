"""Braintrust tracer for Langflow.

Implements Langflow's BaseTracer interface to send component-level
traces to Braintrust.

Only depends on the ``braintrust`` package.

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

    Only depends on the ``braintrust`` package.
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
        return self._ready

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_braintrust(self, config: dict[str, Any], project_name: str) -> bool:
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
        return None

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
