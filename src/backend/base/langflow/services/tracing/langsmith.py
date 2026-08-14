from __future__ import annotations

import os
import threading
import traceback
import types
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from typing_extensions import override

from langflow.schema.data import Data
from langflow.serialization.serialization import serialize
from langflow.services.tracing.base import BaseTracer

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from langchain_core.callbacks.base import BaseCallbackHandler
    from langsmith.run_trees import RunTree
    from lfx.graph.vertex.base import Vertex

    from langflow.services.tracing.schema import Log


# Built once per process. TracerProvider.__init__ registers an atexit shutdown, so building
# one per flow run would leave every provider alive for the life of the process.
_OTEL_PROVIDER: Any = None
_OTEL_PROVIDER_LOCK = threading.Lock()


def _langsmith_otel_provider() -> Any:
    """An isolated provider exporting to LangSmith's OTLP endpoint and nowhere else.

    ``LANGSMITH_TRACING_MODE=otel|hybrid`` makes the client build an OpenTelemetry pipeline,
    and a client constructed without a provider registers its own as the *global* one.
    ``set_tracer_provider`` is one-shot, so whichever side runs first wins: LangSmith either
    swallows the service's own HTTP and flow spans, or application observability cannot
    install at all. That is issue #13319 in a different costume.

    Handing over a bare ``TracerProvider()`` does not work, and the resemblance to
    ``langfuse.py`` is what makes that tempting. The Langfuse SDK calls ``add_span_processor``
    on the provider it is given; LangSmith only takes tracers from it, so a provider with no
    processor silently discards every span and tracing looks healthy while nothing is sent.

    This mirrors the SDK's own ``get_otlp_tracer_provider`` with one deliberate difference: it
    does not honour ``OTEL_EXPORTER_OTLP_ENDPOINT``. That variable points at the operator's
    APM, which is not where a vendor's prompt-bearing traces belong.
    """
    global _OTEL_PROVIDER  # noqa: PLW0603

    with _OTEL_PROVIDER_LOCK:
        if _OTEL_PROVIDER is None:
            from langsmith import utils as ls_utils
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            headers = {"x-api-key": ls_utils.get_api_key(None) or ""}
            project = ls_utils.get_tracer_project()
            if project:
                headers["Langsmith-Project"] = project

            provider = TracerProvider(resource=Resource(attributes={"service.name": "langsmith"}))
            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{ls_utils.get_api_url(None)}/otel", headers=headers))
            )
            _OTEL_PROVIDER = provider

    return _OTEL_PROVIDER


class LangSmithTracer(BaseTracer):
    def __init__(self, trace_name: str, trace_type: str, project_name: str, trace_id: UUID):
        try:
            self._ready = self.setup_langsmith()
            if not self._ready:
                return
            self.trace_name = trace_name
            self.trace_type = trace_type
            self.project_name = project_name
            self.trace_id = trace_id
            from langsmith import get_current_run_tree
            from langsmith.run_helpers import trace

            self._run_tree: RunTree | None = None
            self._children: dict[str, RunTree] = {}
            self._children_traces: dict[str, trace] = {}
            self._child_link: dict[str, str] = {}
            parent = get_current_run_tree()
            if parent is not None and (parent.id == trace_id or parent.name == trace_name):
                # duplicate init of LangSmithTracer with same trace_id\\trace_name, using current run tree
                self._run_tree = parent
            else:
                self._trace = trace(
                    project_name=self.project_name,
                    name=self.trace_name,
                    run_type=self.get_run_type(self.trace_type),
                    run_id=self.trace_id if parent is None else None,
                    parent=parent,
                )
                self._run_tree = self._trace.__enter__()
            self._run_tree.add_event({"name": "Start", "time": datetime.now(timezone.utc).isoformat()})
            self._run_tree.post()
        except Exception as ex:  # noqa: BLE001
            logger.warning(f"Error setting up LangSmith tracer: {ex}")
            self._ready = False

    @property
    def ready(self):
        return self._ready

    def get_run_type(self, run_type: str) -> str:
        from typing import get_args

        from langsmith import client

        valid_run_types = set(get_args(client.RUN_TYPE_T))
        if run_type not in valid_run_types:
            logger.warning("Run type %s is not valid. Using default run type 'chain'.", run_type)
            return "chain"
        return run_type

    def setup_langsmith(self) -> bool:
        if os.getenv("LANGCHAIN_API_KEY") is None:
            return False
        try:
            from langsmith.client import _resolve_tracing_mode
            from langsmith.run_trees import get_cached_client

            client_kwargs: dict[str, Any] = {}
            if _resolve_tracing_mode(None) in ("otel", "hybrid"):
                client_kwargs["otel_tracer_provider"] = _langsmith_otel_provider()

            # get_cached_client honours these kwargs only while its module-level client is
            # unset, so this holds when we are the first LangSmith user in the process. It is
            # the same function langchain calls, so seeding it here replaces a redundant
            # second client rather than adding one. Anything that builds the client before us
            # (a LangChainTracer, a RunTree) gets the SDK's default global-provider behaviour.
            self._client = get_cached_client(**client_kwargs)
        except ImportError:
            logger.exception("Could not import langsmith. Please install it with `pip install langsmith`.")
            return False
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        return True

    def add_trace(
        self,
        trace_id: str,
        trace_name: str,
        trace_type: str,
        inputs: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        vertex: Vertex | None = None,  # noqa: ARG002
    ) -> None:
        if not self._ready or not self._run_tree:
            return
        processed_inputs = {}
        if inputs:
            processed_inputs = self._convert_to_langchain_types(inputs)

        from langsmith.run_helpers import trace

        child_trace = trace(
            name=trace_name,
            run_type=self.get_run_type(trace_type),
            parent=self._run_tree,
            inputs=processed_inputs,
            metadata=self._convert_to_langchain_types(metadata) if metadata else None,
        )
        child = child_trace.__enter__()
        child.post()
        self._children[trace_id] = child
        self._children_traces[trace_id] = child_trace

    def _convert_to_langchain_types(self, io_dict: dict[str, Any]):
        converted = {}
        for key, value in io_dict.items():
            converted[key] = self._convert_to_langchain_type(value)
        return converted

    def _convert_to_langchain_type(self, value):
        from langflow.schema.message import Message

        if isinstance(value, dict):
            value = {key: self._convert_to_langchain_type(val) for key, val in value.items()}
        elif isinstance(value, list):
            value = [self._convert_to_langchain_type(v) for v in value]
        elif isinstance(value, Message):
            if "prompt" in value:
                value = value.load_lc_prompt()
            elif value.sender:
                value = value.to_lc_message()
            else:
                value = value.to_lc_document()
        elif isinstance(value, Data):
            value = value.to_lc_document()
        elif isinstance(value, types.GeneratorType):
            # generator is not serializable, also we can't consume it
            value = str(value)
        return value

    def end_trace(
        self,
        trace_id: str,
        trace_name: str,  # noqa: ARG002
        outputs: dict[str, Any] | None = None,
        error: Exception | None = None,
        logs: Sequence[Log | dict] = (),
    ):
        if not self._ready or not self._run_tree:
            return
        if trace_id not in self._children:
            logger.warning(f"Trace {trace_id} not found in children traces")
            return
        child = self._children[trace_id]
        raw_outputs = {}
        processed_outputs = {}
        if outputs:
            raw_outputs = outputs
            processed_outputs = self._convert_to_langchain_types(outputs)
        if logs:
            logs_dicts = [log if isinstance(log, dict) else log.model_dump() for log in logs]
            child.add_metadata(self._convert_to_langchain_types({"logs": {log.get("name"): log for log in logs_dicts}}))
        child.add_metadata(self._convert_to_langchain_types({"outputs": raw_outputs}))
        child.end(outputs=processed_outputs, error=self._error_to_string(error))
        self._children_traces[trace_id].__exit__(None, None, None)
        self._child_link[trace_id] = child.get_url()

    @staticmethod
    def _error_to_string(error: Exception | None):
        error_message = None
        if error:
            string_stacktrace = traceback.format_exception(error)
            error_message = f"{error.__class__.__name__}: {error}\n\n{string_stacktrace}"
        return error_message

    def end(
        self,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        error: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self._ready or not self._run_tree:
            return
        self._run_tree.add_metadata({"inputs": serialize(inputs)})
        if metadata:
            self._run_tree.add_metadata(serialize(metadata))
        self._run_tree.end(outputs=serialize(outputs), error=self._error_to_string(error))
        self._run_tree.patch()
        self._run_link = self._run_tree.get_url()
        if getattr(self, "_trace", None):
            self._trace.__exit__()

    @property
    def run_link(self):
        if not self._ready or not self._run_tree:
            return None
        return self._run_tree.get_url()

    @override
    def get_langchain_callback(self) -> BaseCallbackHandler | None:
        return None
