import os
from typing import TYPE_CHECKING, Any, Dict, Optional
from uuid import UUID
from datetime import datetime

from loguru import logger

from langflow.services.tracing.base import BaseTracer
from langflow.services.tracing.schema import Log

if TYPE_CHECKING:
    from langflow.graph.vertex.base import Vertex
    from langchain.callbacks.base import BaseCallbackHandler


class LangFuseTracer(BaseTracer):
    flow_id: str

    def __init__(self, trace_name: str, trace_type: str, project_name: str, trace_id: UUID):
        self.project_name = project_name
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.trace_id = trace_id
        self.flow_id = trace_name.split(" - ")[-1]
        self.last_span = None
        self.spans: dict = {}
        self._ready: bool = self.setup_langfuse()

    @property
    def ready(self):
        return self._ready

    def setup_langfuse(self) -> bool:
        try:
            from langfuse import Langfuse
            from langfuse.callback.langchain import LangchainCallbackHandler

            config = self._get_config()
            if not all(config.values()):
                raise ValueError("Missing Langfuse configuration")

            self._client = Langfuse(**config)
            self.trace = self._client.trace(id=str(self.trace_id), name=self.flow_id)

            config |= {
                "trace_name": self.flow_id,
                "stateful_client": self.trace,
                "update_stateful_client": True,
            }
            self._callback = LangchainCallbackHandler(**config)

        except ImportError:
            logger.error("Could not import langfuse. Please install it with `pip install langfuse`.")
            return False

        except Exception as e:
            logger.debug(f"Error setting up LangSmith tracer: {e}")
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
        start_time = datetime.utcnow()
        if not self._ready:
            return

        _metadata: dict = {}
        _metadata |= {"trace_type": trace_type} if trace_type else {}
        _metadata |= metadata if metadata else {}

        _name = trace_name.removesuffix(f" ({trace_id})")
        content_span = {
            "name": _name,
            "input": inputs,
            "metadata": _metadata,
            "start_time": start_time,
        }

        if self.last_span:
            span = self.last_span.span(**content_span)
        else:
            span = self.trace.span(**content_span)

        self.last_span = span
        self.spans[trace_id] = span

    def end_trace(
        self,
        trace_id: str,
        trace_name: str,
        outputs: Dict[str, Any] | None = None,
        error: Exception | None = None,
        logs: list[Log | dict] = [],
    ):
        end_time = datetime.utcnow()
        if not self._ready:
            return

        span = self.spans.get(trace_id, None)
        if span:
            _output: dict = {}
            _output |= outputs if outputs else {}
            _output |= {"error": str(error)} if error else {}
            _output |= {"logs": logs} if logs else {}
            content = {"output": _output, "end_time": end_time}
            span.update(**content)

    def end(
        self,
        inputs: dict[str, Any],
        outputs: Dict[str, Any],
        error: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        if not self._ready:
            return

        self._client.flush()

    def get_langchain_callback(self) -> Optional["BaseCallbackHandler"]:
        if not self._ready:
            return None
        return None  # self._callback

    def _get_config(self):
        secret_key = os.getenv("LANGFUSE_SECRET_KEY", None)
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY", None)
        host = os.getenv("LANGFUSE_HOST", None)
        return {"secret_key": secret_key, "public_key": public_key, "host": host}
