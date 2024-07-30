from typing import TYPE_CHECKING, Any, Dict, Optional, cast
from uuid import UUID

import nanoid  # type: ignore
from loguru import logger

from langflow.schema.data import Data
from langflow.services.tracing.base import BaseTracer
from langflow.services.tracing.schema import Log

if TYPE_CHECKING:
    from langwatch.tracer import ContextSpan

    from langflow.graph.vertex.base import Vertex
    from langchain.callbacks.base import BaseCallbackHandler


class LangWatchTracer(BaseTracer):
    flow_id: str

    def __init__(self, trace_name: str, trace_type: str, project_name: str, trace_id: UUID):
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.project_name = project_name
        self.trace_id = trace_id
        self.flow_id = trace_name.split(" - ")[-1]

        try:
            self._ready = self.setup_langwatch()
            if not self._ready:
                return

            self.trace = self._client.trace(
                trace_id=str(self.trace_id),
            )
            self.spans: dict[str, "ContextSpan"] = {}

            name_without_id = " - ".join(trace_name.split(" - ")[0:-1])
            self.trace.root_span.update(
                span_id=f"{self.flow_id}-{nanoid.generate(size=6)}",  # nanoid to make the span_id globally unique, which is required for LangWatch for now
                name=name_without_id,
                type="workflow",
            )
        except Exception as e:
            logger.debug(f"Error setting up LangWatch tracer: {e}")
            self._ready = False

    @property
    def ready(self):
        return self._ready

    def setup_langwatch(self):
        try:
            import langwatch

            self._client = langwatch
        except ImportError:
            logger.error("Could not import langwatch. Please install it with `pip install langwatch`.")
            return False
        return True

    def add_trace(
        self,
        trace_id: str,
        trace_name: str,
        trace_type: str,
        inputs: Dict[str, Any],
        metadata: Dict[str, Any] | None = None,
        vertex: Optional["Vertex"] = None,
    ):
        if not self._ready:
            return
        # If user is not using session_id, then it becomes the same as flow_id, but
        # we don't want to have an infinite thread with all the flow messages
        if "session_id" in inputs and inputs["session_id"] != self.flow_id:
            self.trace.update(metadata=(self.trace.metadata or {}) | {"thread_id": inputs["session_id"]})

        name_without_id = " (".join(trace_name.split(" (")[0:-1])

        previous_nodes = (
            [span for key, span in self.spans.items() for edge in vertex.incoming_edges if key == edge.source_id]
            if vertex and len(vertex.incoming_edges) > 0
            else []
        )

        span = self.trace.span(
            span_id=f"{trace_id}-{nanoid.generate(size=6)}",  # Add a nanoid to make the span_id globally unique, which is required for LangWatch for now
            name=name_without_id,
            type="component",
            parent=(previous_nodes[-1] if len(previous_nodes) > 0 else self.trace.root_span),
            input=self._convert_to_langwatch_types(inputs),
        )
        self.trace.set_current_span(span)
        self.spans[trace_id] = span

    def end_trace(
        self,
        trace_id: str,
        trace_name: str,
        outputs: Dict[str, Any] | None = None,
        error: Exception | None = None,
        logs: list[Log | dict] = [],
    ):
        if not self._ready:
            return
        if self.spans.get(trace_id):
            self.spans[trace_id].end(output=self._convert_to_langwatch_types(outputs), error=error)

    def end(
        self,
        inputs: dict[str, Any],
        outputs: Dict[str, Any],
        error: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        if not self._ready:
            return
        self.trace.root_span.end(
            input=self._convert_to_langwatch_types(inputs),
            output=self._convert_to_langwatch_types(outputs),
            error=error,
        )

        if metadata and "flow_name" in metadata:
            self.trace.update(metadata=(self.trace.metadata or {}) | {"labels": [f"Flow: {metadata['flow_name']}"]})

        if self.trace.api_key or self._client.api_key:
            self.trace.deferred_send_spans()

    def _convert_to_langwatch_types(self, io_dict: Optional[Dict[str, Any]]):
        from langwatch.utils import autoconvert_typed_values

        if io_dict is None:
            return None
        converted = {}
        for key, value in io_dict.items():
            converted[key] = self._convert_to_langwatch_type(value)
        return autoconvert_typed_values(converted)

    def _convert_to_langwatch_type(self, value):
        from langwatch.langchain import langchain_message_to_chat_message, langchain_messages_to_chat_messages

        from langflow.schema.message import BaseMessage, Message

        if isinstance(value, dict):
            for key, _value in value.copy().items():
                _value = self._convert_to_langwatch_type(_value)
                value[key] = _value
        elif isinstance(value, list):
            value = [self._convert_to_langwatch_type(v) for v in value]
        elif isinstance(value, Message):
            if "prompt" in value:
                prompt = value.load_lc_prompt()
                if len(prompt.input_variables) == 0 and all(isinstance(m, BaseMessage) for m in prompt.messages):
                    value = langchain_messages_to_chat_messages([cast(list[BaseMessage], prompt.messages)])
                else:
                    value = cast(dict, value.load_lc_prompt())
            elif value.sender:
                value = langchain_message_to_chat_message(value.to_lc_message())
            else:
                value = cast(dict, value.to_lc_document())
        elif isinstance(value, Data):
            value = cast(dict, value.to_lc_document())
        return value

    def get_langchain_callback(self) -> Optional["BaseCallbackHandler"]:
        if self.trace is None:
            return None

        return self.trace.get_langchain_callback()
