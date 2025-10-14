from __future__ import annotations

import os
from collections import OrderedDict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from typing_extensions import override

from langflow.serialization.serialization import serialize
from langflow.services.tracing.base import BaseTracer

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from langchain.callbacks.base import BaseCallbackHandler
    from lfx.graph.vertex.base import Vertex

    from langflow.services.tracing.schema import Log

from threading import Lock


class LangFuseTracer(BaseTracer):
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
        self.project_name = project_name
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.trace_id = trace_id
        self.user_id = user_id
        self.session_id = session_id
        self.flow_id = trace_name.split(" - ")[-1]
        self.spans: dict = OrderedDict()  # spans that are not ended

        config = self._get_config()
        self._ready: bool = self.setup_langfuse(config) if config else False

    @property
    def ready(self):
        return self._ready

    def setup_langfuse(self, config) -> bool:
        try:
            from langfuse import Langfuse

            self._client = Langfuse(**config)
            try:
                from langfuse.api.core.request_options import RequestOptions

                self._client.client.health.health(request_options=RequestOptions(timeout_in_seconds=1))
            except Exception as e:  # noqa: BLE001
                logger.debug(f"can not connect to Langfuse: {e}")
                return False
            self.trace = self._client.trace(
                id=str(self.trace_id),
                name=self.flow_id,
                user_id=self.user_id,
                session_id=self.session_id,
            )

        except ImportError:
            logger.exception("Could not import langfuse. Please install it with `pip install langfuse`.")
            return False

        except Exception as e:  # noqa: BLE001
            logger.debug(f"Error setting up LangSmith tracer: {e}")
            return False

        return True

    @override
    def add_trace(
        self,
        trace_id: str,  # actualy component id
        trace_name: str,
        trace_type: str,
        inputs: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        vertex: Vertex | None = None,
    ) -> None:
        start_time = datetime.now(tz=timezone.utc)
        if not self._ready:
            return

        metadata_: dict = {"from_langflow_component": True, "component_id": trace_id}
        metadata_ |= {"trace_type": trace_type} if trace_type else {}
        metadata_ |= metadata or {}

        name = trace_name.removesuffix(f" ({trace_id})")
        content_span = {
            "name": name,
            "input": inputs,
            "metadata": metadata_,
            "start_time": start_time,
        }

        # if two component is built concurrently, will use wrong last span. just flatten now, maybe fix in future.
        # if len(self.spans) > 0:
        #     last_span = next(reversed(self.spans))
        #     span = self.spans[last_span].span(**content_span)
        # else:
        span = self.trace.span(**serialize(content_span))

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
        end_time = datetime.now(tz=timezone.utc)
        if not self._ready:
            return

        span = self.spans.pop(trace_id, None)
        if span:
            output: dict = {}
            output |= outputs or {}
            output |= {"error": str(error)} if error else {}
            output |= {"logs": list(logs)} if logs else {}
            content = serialize({"output": output, "end_time": end_time})
            span.update(**content)

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
        content_update = {
            "input": inputs,
            "output": outputs,
            "metadata": metadata,
        }
        self.trace.update(**serialize(content_update))

    def get_langchain_callback(self) -> BaseCallbackHandler | None:
        """Get langchain callback for tracing.

        Note: Langfuse callbacks have an architectural issue with agent tool execution.
        The callback's internal run tracking doesn't properly handle agent tool calls
        because the agent's run_id is cleaned up before tools execute. We wrap the
        callback to auto-create missing parent spans on-demand.
        """
        if not self._ready:
            return None

        # Get the base callback
        if len(self.spans) > 0:
            current_span = self.spans[next(reversed(self.spans))]
            base_callback = current_span.get_langchain_handler()
        else:
            base_callback = self.trace.get_langchain_handler()

        return _create_dummy_parent(base_callback)

    @staticmethod
    def _get_config() -> dict:
        secret_key = os.getenv("LANGFUSE_SECRET_KEY", None)
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY", None)
        host = os.getenv("LANGFUSE_HOST", None)
        if secret_key and public_key and host:
            return {"secret_key": secret_key, "public_key": public_key, "host": host}
        return {}


def _create_dummy_parent(base_callback):
    """Create a callback wrapper that ensures parent runs exist for tool execution."""
    instance_lock = Lock()

    class DummyParent(type(base_callback)):
        def on_tool_start(self, serialized, input_str, *, run_id, parent_run_id=None, **kwargs):
            if parent_run_id and parent_run_id not in self.runs:
                with instance_lock:
                    if parent_run_id not in self.runs:
                        logger.debug("Langfuse: Auto-creating missing parent span")
                        self.runs[parent_run_id] = self.trace.span(
                            name="Agent Execution", metadata={"auto_created": True}
                        )
            return super().on_tool_start(serialized, input_str, run_id=run_id, parent_run_id=parent_run_id, **kwargs)

    wrapped = DummyParent.__new__(DummyParent)
    wrapped.__dict__.update(base_callback.__dict__)
    return wrapped
