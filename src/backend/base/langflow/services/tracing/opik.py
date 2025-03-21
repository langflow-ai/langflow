from __future__ import annotations

import os
import types
from typing import TYPE_CHECKING, Any

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from loguru import logger
from typing_extensions import override

from langflow.schema.data import Data
from langflow.schema.message import Message
from langflow.services.tracing.base import BaseTracer

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from langchain.callbacks.base import BaseCallbackHandler

    from langflow.graph.vertex.base import Vertex
    from langflow.services.tracing.schema import Log


def get_distributed_trace_headers(trace_id, span_id):
    """Returns headers dictionary to be passed into tracked function on remote node."""
    return {"opik_parent_span_id": span_id, "opik_trace_id": trace_id}


class OpikTracer(BaseTracer):
    flow_id: str

    def __init__(
        self,
        trace_name: str,
        trace_type: str,
        project_name: str,
        trace_id: UUID,
        user_id: str | None = None,
        session_id: str | None = None,
    ):
        self._project_name = project_name
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.opik_trace_id = None
        self.user_id = user_id
        self.session_id = session_id
        self.flow_id = trace_name.split(" - ")[-1]
        self.spans: dict = {}

        config = self._get_config()
        self._ready: bool = self._setup_opik(config, trace_id) if config else False
        self._distributed_headers = None

    @property
    def ready(self):
        return self._ready

    def _setup_opik(self, config: dict, trace_id: UUID) -> bool:
        try:
            from opik import Opik
            from opik.api_objects.trace import TraceData

            self._client = Opik(project_name=self._project_name, _show_misconfiguration_message=False, **config)

            missing_configuration, _ = self._client._config.get_misconfiguration_detection_results()

            if missing_configuration:
                return False

            if not self._check_opik_auth(self._client):
                return False

            # Langflow Trace ID seems to always be random
            metadata = {
                "langflow_trace_id": trace_id,
                "langflow_trace_name": self.trace_name,
                "user_id": self.user_id,
                "created_from": "langflow",
            }
            self.trace = TraceData(
                name=self.flow_id,
                metadata=metadata,
                thread_id=self.session_id,
            )
            self.opik_trace_id = self.trace.id
        except ImportError:
            logger.exception("Could not import opik. Please install it with `pip install opik`.")
            return False

        except Exception as e:  # noqa: BLE001
            logger.exception(f"Error setting up opik tracer: {e}")
            return False

        return True

    def _check_opik_auth(self, opik_client) -> bool:
        try:
            opik_client.auth_check()
        except Exception as e:  # noqa: BLE001
            logger.error(f"Opik auth check failed, OpikTracer will be disabled: {e}")
            return False
        else:
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
        if not self._ready:
            return

        from opik.api_objects.span import SpanData

        name = trace_name.removesuffix(f" ({trace_id})")
        processed_inputs = self._convert_to_opik_types(inputs) if inputs else {}
        processed_metadata = self._convert_to_opik_types(metadata) if metadata else {}

        span = SpanData(
            trace_id=self.opik_trace_id,
            name=name,
            input=processed_inputs,
            metadata=processed_metadata,
            type="general",  # The LLM span will comes from the langchain callback
        )

        self.spans[trace_id] = span
        self._distributed_headers = get_distributed_trace_headers(self.opik_trace_id, span.id)

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

        from opik.decorator.error_info_collector import collect

        span = self.spans.get(trace_id, None)

        if span:
            output: dict = {}
            output |= outputs or {}
            output |= {"logs": list(logs)} if logs else {}
            content = {"output": output, "error_info": collect(error) if error else None}

            span.init_end_time().update(**content)

            self._client.span(**span.__dict__)
        else:
            logger.warning("No corresponding span found")

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

        from opik.decorator.error_info_collector import collect

        self.trace.init_end_time().update(
            input=inputs, output=outputs, error_info=collect(error) if error else None, metadata=metadata
        )

        self._client.trace(**self.trace.__dict__)

        self._client.flush()

    def get_langchain_callback(self) -> BaseCallbackHandler | None:
        if not self._ready:
            return None

        from opik.integrations.langchain import OpikTracer as LangchainOpikTracer

        # Set project name for the langchain integration
        os.environ["OPIK_PROJECT_NAME"] = self._project_name

        return LangchainOpikTracer(distributed_headers=self._distributed_headers)

    def _convert_to_opik_types(self, io_dict: dict[str | Any, Any]) -> dict[str, Any]:
        """Converts data types to Opik compatible formats."""
        return {str(key): self._convert_to_opik_type(value) for key, value in io_dict.items() if key is not None}

    def _convert_to_opik_type(self, value):
        """Recursively converts a value to a Opik compatible type."""
        if isinstance(value, dict):
            value = {key: self._convert_to_opik_type(val) for key, val in value.items()}

        elif isinstance(value, list):
            value = [self._convert_to_opik_type(v) for v in value]

        elif isinstance(value, Message):
            value = value.text

        elif isinstance(value, Data):
            value = value.get_text()

        elif isinstance(value, (BaseMessage | HumanMessage | SystemMessage)):
            value = value.content

        elif isinstance(value, Document):
            value = value.page_content

        elif isinstance(value, (types.GeneratorType | types.NoneType)):
            value = str(value)

        return value

    @staticmethod
    def _get_config() -> dict:
        host = os.getenv("OPIK_URL_OVERRIDE", None)
        api_key = os.getenv("OPIK_API_KEY", None)
        workspace = os.getenv("OPIK_WORKSPACE", None)

        # API Key is mandatory for Opik Cloud and URL is mandatory for Open-Source Opik Server
        if host or api_key:
            return {"host": host, "api_key": api_key, "workspace": workspace}
        return {}
