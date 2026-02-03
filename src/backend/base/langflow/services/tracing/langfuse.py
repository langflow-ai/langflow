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
    from lfx.graph.vertex.base import Vertex

    from langflow.services.tracing.schema import Log


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

            # v3 requires 32-char hex trace_id (W3C Trace Context format)
            trace_id_hex = str(self.trace_id).replace("-", "")
            logger.debug(f"[Langfuse] Setting up tracer with trace_id_hex={trace_id_hex}, flow_id={self.flow_id}")

            # In v3, create a root span that serves as the trace
            # Use langfuse_ prefixed metadata for trace-level attributes
            metadata: dict[str, Any] = {}
            if self.user_id:
                metadata["langfuse_user_id"] = self.user_id
            if self.session_id:
                metadata["langfuse_session_id"] = self.session_id

            self.trace = self._client.start_span(
                name=self.flow_id,
                trace_context={"trace_id": trace_id_hex},
                metadata=metadata if metadata else None,
            )

            # Explicitly set trace-level attributes including name
            self.trace.update_trace(
                name=self.flow_id,
                user_id=self.user_id,
                session_id=self.session_id,
            )
            logger.debug(f"[Langfuse] Root span created successfully, trace_id={self.trace.trace_id}")

        except ImportError:
            logger.exception("Could not import langfuse. Please install it with `pip install langfuse`.")
            return False

        except Exception as e:  # noqa: BLE001
            logger.debug(f"Error setting up Langfuse tracer: {e}")
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
        if not self._ready:
            return

        metadata_: dict = {"from_langflow_component": True, "component_id": trace_id}
        metadata_ |= {"trace_type": trace_type} if trace_type else {}
        metadata_ |= metadata or {}

        name = trace_name.removesuffix(f" ({trace_id})")
        # v3: start_time is automatically set when span is created
        content_span = {
            "name": name,
            "input": inputs,
            "metadata": metadata_,
        }

        # if two component is built concurrently, will use wrong last span. just flatten now, maybe fix in future.
        # if len(self.spans) > 0:
        #     last_span = next(reversed(self.spans))
        #     span = self.spans[last_span].start_span(**content_span)
        # else:
        # v3 uses start_span() instead of span()
        span = self.trace.start_span(**serialize(content_span))

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
            # v3: update output then explicitly end the span (end sets end_time automatically)
            content = serialize({"output": output})
            span.update(**content)
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
        content_update = {
            "input": inputs,
            "output": outputs,
            "metadata": metadata,
        }
        self.trace.update(**serialize(content_update))
        # v3: explicitly end the root span
        self.trace.end()

    def get_langchain_callback(self) -> BaseCallbackHandler | None:
        if not self._ready:
            return None

        from langfuse.langchain import CallbackHandler

        # v3 requires 32-char hex trace_id (W3C Trace Context format)
        trace_id_hex = str(self.trace_id).replace("-", "")

        return CallbackHandler(
            trace_context={"trace_id": trace_id_hex},
        )

    @staticmethod
    def _get_config() -> dict:
        secret_key = os.getenv("LANGFUSE_SECRET_KEY", None)
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY", None)
        host = os.getenv("LANGFUSE_HOST", None)
        if secret_key and public_key and host:
            return {"secret_key": secret_key, "public_key": public_key, "host": host}
        return {}
