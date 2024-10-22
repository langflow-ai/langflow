from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from loguru import logger
from typing_extensions import override

from langflow.services.tracing.base import BaseTracer

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from langchain.callbacks.base import BaseCallbackHandler
    from langfuse.client import StatefulSpanClient

    from langflow.graph.vertex.base import Vertex
    from langflow.services.tracing.schema import Log


class LangFuseTracer(BaseTracer):
    flow_id: str

    def __init__(self, trace_name: str, trace_type: str, project_name: str, trace_id: UUID):
        self.project_name = project_name
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.trace_id = trace_id
        self.flow_id = trace_name.split(" - ")[-1]
        self.last_span: StatefulSpanClient | None = None
        self.spans: dict = {}

        config = self._get_config()
        self._ready: bool = self.setup_langfuse(config) if config else False

    @property
    def ready(self):
        return self._ready

    def setup_langfuse(self, config) -> bool:
        try:
            from langfuse import Langfuse
            from langfuse.callback.langchain import LangchainCallbackHandler

            self._client = Langfuse(**config)
            self.trace = self._client.trace(id=str(self.trace_id), name=self.flow_id)

            config |= {
                "trace_name": self.flow_id,
                "stateful_client": self.trace,
                "update_stateful_client": True,
            }
            self._callback = LangchainCallbackHandler(**config)

        except ImportError:
            logger.exception("Could not import langfuse. Please install it with `pip install langfuse`.")
            return False

        except Exception:  # noqa: BLE001
            logger.opt(exception=True).debug("Error setting up LangSmith tracer")
            return False

        return True

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
        start_time = datetime.now(tz=timezone.utc)
        if not self._ready:
            return

        _metadata: dict = {}
        _metadata |= {"trace_type": trace_type} if trace_type else {}
        _metadata |= metadata or {}

        _name = trace_name.removesuffix(f" ({trace_id})")
        content_span = {
            "name": _name,
            "input": inputs,
            "metadata": _metadata,
            "start_time": start_time,
        }

        span = self.last_span.span(**content_span) if self.last_span else self.trace.span(**content_span)

        self.last_span = span
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

        span = self.spans.get(trace_id, None)
        if span:
            _output: dict = {}
            _output |= outputs or {}
            _output |= {"error": str(error)} if error else {}
            _output |= {"logs": list(logs)} if logs else {}
            content = {"output": _output, "end_time": end_time}
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

        self._client.flush()

    def get_langchain_callback(self) -> BaseCallbackHandler | None:
        if not self._ready:
            return None
        return None  # self._callback

    def _get_config(self) -> dict:
        secret_key = os.getenv("LANGFUSE_SECRET_KEY", None)
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY", None)
        host = os.getenv("LANGFUSE_HOST", None)
        if secret_key and public_key and host:
            return {"secret_key": secret_key, "public_key": public_key, "host": host}
        return {}
