from __future__ import annotations

import base64
import json
import os
import threading
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from langchain_core.callbacks.base import BaseCallbackHandler
from lfx.base.models.llm_callback_utils import detect_provider_from_model, extract_llm_model_name
from lfx.log.logger import logger
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from typing_extensions import override

from langflow.services.tracing.base import BaseTracer

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from lfx.graph.vertex.base import Vertex
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.trace import Span

    from langflow.services.tracing.schema import Log

_REGION_HOSTS = {
    "us": "ingestion-us.mixpanel.com",
    "eu": "ingestion-eu.mixpanel.com",
    "in": "ingestion-in.mixpanel.com",
}
_TRACES_PATH = "/v1/ai/otel/traces"
_EXPORT_TIMEOUT_SECONDS = 10
_TRUE_VALUES = {"1", "true", "yes", "on"}


class _SharedProvider:
    lock = threading.Lock()
    provider: TracerProvider | None = None
    key: tuple[str, str] | None = None


def _get_or_create_provider(endpoint: str, project_token: str) -> TracerProvider:
    """Return a process-wide provider that exports only to Mixpanel.

    Isolated from the global provider so Langflow's own spans never reach Mixpanel and the
    application bootstrap keeps the global slot (#13319). Every exporter setting is passed
    explicitly so an operator's OTEL_EXPORTER_OTLP_* variables, meant for their APM, do not apply.
    """
    import requests
    from opentelemetry.exporter.otlp.proto.http import Compression
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    key = (endpoint, project_token)
    with _SharedProvider.lock:
        if _SharedProvider.provider is None or _SharedProvider.key != key:
            if _SharedProvider.provider is not None:
                _SharedProvider.provider.shutdown()
            credentials = base64.b64encode(f"{project_token}:".encode()).decode()
            exporter = OTLPSpanExporter(
                endpoint=endpoint,
                headers={"Authorization": f"Basic {credentials}"},
                timeout=_EXPORT_TIMEOUT_SECONDS,
                compression=Compression.NoCompression,
                session=requests.Session(),
            )
            provider = TracerProvider(resource=Resource(attributes={"service.name": "langflow"}))
            provider.add_span_processor(BatchSpanProcessor(exporter))
            _SharedProvider.provider = provider
            _SharedProvider.key = key
        return _SharedProvider.provider


def _reset_shared_provider_for_tests() -> None:
    with _SharedProvider.lock:
        if _SharedProvider.provider is not None:
            _SharedProvider.provider.shutdown()
        _SharedProvider.provider = None
        _SharedProvider.key = None


def _to_json(value: Any) -> str:
    from langflow.schema.message import Message

    def convert(item: Any) -> Any:
        if isinstance(item, Message):
            return item.text
        if hasattr(item, "content") and hasattr(item, "type"):
            return {"role": item.type, "content": item.content}
        return str(item)

    return json.dumps(value, default=convert)


class MixpanelTracer(BaseTracer):
    """Sends flow, component, LLM, and tool spans to Mixpanel Agent Intelligence over OTLP."""

    def __init__(
        self,
        trace_name: str,
        trace_type: str,
        project_name: str,
        trace_id: UUID,
        user_id: str | None = None,
        session_id: str | None = None,
        tracing_user_id: str | None = None,
    ) -> None:
        self.trace_id = trace_id
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.project_name = project_name
        self.user_id = user_id
        self.session_id = session_id
        self.tracing_user_id = tracing_user_id
        self.spans: dict[str, Span] = {}
        self._runs: dict[UUID, tuple[Span, str | None]] = {}
        self._runs_lock = threading.Lock()
        self._ready = False

        config = self._get_config()
        if config is None:
            return
        endpoint, project_token = config
        self.capture_content = os.getenv("MIXPANEL_CAPTURE_CONTENT", "").strip().lower() in _TRUE_VALUES

        # Mixpanel keys every event on user.id, so it carries only the caller-supplied end user.
        # The authenticated Langflow user is often an API-key owner shared by every end user.
        self.common_attributes: dict[str, str] = {"langflow.project_name": project_name}
        if tracing_user_id:
            self.common_attributes["user.id"] = tracing_user_id
        if session_id:
            self.common_attributes["session.id"] = session_id
        if user_id:
            self.common_attributes["langflow.user_id"] = str(user_id)

        try:
            self._tracer = _get_or_create_provider(endpoint, project_token).get_tracer("langflow")
            self.root_span = self._tracer.start_span(
                name=trace_name,
                attributes={
                    **self.common_attributes,
                    "langflow.trace_id": str(trace_id),
                    "langflow.trace_type": trace_type,
                },
            )
        except Exception:  # noqa: BLE001
            logger.debug("Error setting up Mixpanel tracer", exc_info=True)
            return
        self._ready = True

    @property
    def ready(self) -> bool:
        return self._ready

    @staticmethod
    def _get_config() -> tuple[str, str] | None:
        project_token = os.getenv("MIXPANEL_PROJECT_TOKEN", "").strip()
        if not project_token:
            return None

        endpoint = os.getenv("MIXPANEL_ENDPOINT", "").strip()
        if endpoint:
            if not urlparse(endpoint).netloc:
                logger.error(f"Invalid MIXPANEL_ENDPOINT: {endpoint}")
                return None
            return endpoint, project_token

        region = os.getenv("MIXPANEL_REGION", "").strip().lower() or "us"
        host = _REGION_HOSTS.get(region)
        if host is None:
            logger.error(f"Invalid MIXPANEL_REGION: {region}. Expected one of: us, eu, in")
            return None
        return f"https://{host}{_TRACES_PATH}", project_token

    def _start_span(self, name: str, parent: Span, attributes: dict[str, Any]) -> Span:
        return self._tracer.start_span(
            name=name,
            context=trace.set_span_in_context(parent),
            attributes={**self.common_attributes, **attributes},
        )

    @staticmethod
    def _end_span(span: Span, error: BaseException | None = None) -> None:
        if error is not None:
            span.record_exception(error)
            span.set_status(Status(StatusCode.ERROR, str(error)))
        span.end()

    def start_run(
        self,
        run_id: UUID,
        parent_run_id: UUID | None,
        component_id: str | None,
        name: str,
        attributes: dict[str, Any],
    ) -> None:
        with self._runs_lock:
            parent_run = self._runs.get(parent_run_id) if parent_run_id else None
            if parent_run:
                parent = parent_run[0]
            elif component_id:
                # add_trace is queued, so a model can start before its component span exists.
                if component_id not in self.spans:
                    self.spans[component_id] = self._start_span(component_id, self.root_span, {})
                parent = self.spans[component_id]
            else:
                parent = self.root_span
            self._runs[run_id] = (self._start_span(name, parent, attributes), component_id)

    def end_run(
        self, run_id: UUID, attributes: dict[str, Any] | None = None, error: BaseException | None = None
    ) -> None:
        with self._runs_lock:
            run = self._runs.pop(run_id, None)
        if run is None:
            return
        span = run[0]
        if attributes:
            span.set_attributes(attributes)
        self._end_span(span, error)

    def _end_open_runs(self, component_id: str | None = None) -> None:
        with self._runs_lock:
            run_ids = [rid for rid, (_, cid) in self._runs.items() if component_id is None or cid == component_id]
        for run_id in run_ids:
            self.end_run(run_id)

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
        attributes = {"langflow.component.id": trace_id, "langflow.component.type": trace_type}
        if self.capture_content:
            attributes["langflow.inputs"] = _to_json(inputs)
        with self._runs_lock:
            span = self.spans.get(trace_id)
            if span is None:
                self.spans[trace_id] = self._start_span(trace_name, self.root_span, attributes)
                return
        span.update_name(trace_name)
        span.set_attributes({**self.common_attributes, **attributes})

    @override
    def end_trace(
        self,
        trace_id: str,
        trace_name: str,
        outputs: dict[str, Any] | None = None,
        error: Exception | None = None,
        logs: Sequence[Log | dict] = (),
    ) -> None:
        if not self._ready or trace_id not in self.spans:
            return
        self._end_open_runs(trace_id)
        span = self.spans.pop(trace_id)
        if self.capture_content:
            if outputs:
                span.set_attribute("langflow.outputs", _to_json(outputs))
            if logs:
                span.set_attribute("langflow.logs", _to_json(list(logs)))
        self._end_span(span, error)

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
        self._end_open_runs()
        for trace_id in list(self.spans):
            self._end_span(self.spans.pop(trace_id))
        if self.capture_content:
            self.root_span.set_attribute("langflow.inputs", _to_json(inputs))
            self.root_span.set_attribute("langflow.outputs", _to_json(outputs))
        self._end_span(self.root_span, error)

    @override
    def get_langchain_callback(self) -> BaseCallbackHandler | None:
        if not self._ready:
            return None
        from langflow.services.tracing.service import component_context_var

        component_context = component_context_var.get(None)
        component_id = component_context.trace_id if component_context else None
        return MixpanelCallbackHandler(self, component_id)


class MixpanelCallbackHandler(BaseCallbackHandler):
    """Records LangChain LLM and tool runs as OpenTelemetry GenAI spans under the component span."""

    def __init__(self, tracer: MixpanelTracer, component_id: str | None) -> None:
        self._tracer = tracer
        self._component_id = component_id

    def _start_model_run(
        self,
        operation: str,
        run_id: UUID,
        parent_run_id: UUID | None,
        metadata: dict[str, Any] | None,
        kwargs: dict[str, Any],
        input_messages: Any,
    ) -> None:
        metadata = metadata or {}
        model = metadata.get("ls_model_name") or extract_llm_model_name(kwargs)
        provider = metadata.get("ls_provider") or detect_provider_from_model(model)
        attributes: dict[str, Any] = {"gen_ai.operation.name": operation}
        if model:
            attributes["gen_ai.request.model"] = model
        if provider:
            attributes["gen_ai.provider.name"] = provider
        if self._tracer.capture_content:
            attributes["gen_ai.input.messages"] = _to_json(input_messages)
        name = f"{operation} {model}" if model else operation
        self._tracer.start_run(run_id, parent_run_id, self._component_id, name, attributes)

    @override
    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self._start_model_run("chat", run_id, parent_run_id, metadata, kwargs, messages)

    @override
    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self._start_model_run("text_completion", run_id, parent_run_id, metadata, kwargs, prompts)

    @override
    def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> None:
        from lfx.schema.token_usage import extract_usage_from_llm_result

        attributes: dict[str, Any] = {}
        usage = extract_usage_from_llm_result(response)
        if usage is not None:
            if usage.input_tokens is not None:
                attributes["gen_ai.usage.input_tokens"] = usage.input_tokens
            if usage.output_tokens is not None:
                attributes["gen_ai.usage.output_tokens"] = usage.output_tokens
        response_model = (getattr(response, "llm_output", None) or {}).get("model_name")
        if response_model:
            attributes["gen_ai.response.model"] = response_model
        if self._tracer.capture_content:
            texts = [gen.text for generations in response.generations for gen in generations]
            attributes["gen_ai.output.messages"] = _to_json(texts)
        self._tracer.end_run(run_id, attributes)

    @override
    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._tracer.end_run(run_id, error=error)

    @override
    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        tool_name = (serialized or {}).get("name") or "tool"
        attributes: dict[str, Any] = {"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": tool_name}
        if self._tracer.capture_content:
            attributes["gen_ai.tool.call.arguments"] = input_str
        self._tracer.start_run(run_id, parent_run_id, self._component_id, f"execute_tool {tool_name}", attributes)

    @override
    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        attributes = {"gen_ai.tool.call.result": _to_json(output)} if self._tracer.capture_content else None
        self._tracer.end_run(run_id, attributes)

    @override
    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._tracer.end_run(run_id, error=error)
