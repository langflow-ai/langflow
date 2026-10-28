import base64
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from langflow.services.tracing import mixpanel as mixpanel_module
from langflow.services.tracing.mixpanel import MixpanelTracer
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

TOKEN = "probe-token"  # noqa: S105


class _Receiver:
    def __init__(self) -> None:
        self.requests: list[dict] = []
        receiver = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                receiver.requests.append({"path": self.path, "headers": dict(self.headers), "body": body})
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.endpoint = f"http://127.0.0.1:{self.server.server_port}/v1/ai/otel/traces"

    def spans(self) -> dict[str, dict]:
        mixpanel_module._SharedProvider.provider.force_flush()
        spans = {}
        for request in self.requests:
            export = ExportTraceServiceRequest.FromString(request["body"])
            for resource_spans in export.resource_spans:
                for scope_spans in resource_spans.scope_spans:
                    for span in scope_spans.spans:
                        attributes = {a.key: _value(a.value) for a in span.attributes}
                        spans[span.name] = {
                            "span_id": span.span_id,
                            "parent_span_id": span.parent_span_id,
                            "status": span.status.code,
                            "attributes": attributes,
                        }
        return spans


def _value(value):
    return getattr(value, value.WhichOneof("value"))


@pytest.fixture
def receiver(monkeypatch):
    mixpanel_module._reset_shared_provider_for_tests()
    server = _Receiver()
    monkeypatch.setenv("MIXPANEL_PROJECT_TOKEN", TOKEN)
    monkeypatch.setenv("MIXPANEL_ENDPOINT", server.endpoint)
    monkeypatch.delenv("MIXPANEL_CAPTURE_CONTENT", raising=False)
    yield server
    mixpanel_module._reset_shared_provider_for_tests()
    server.server.shutdown()


def _make_tracer(**kwargs) -> MixpanelTracer:
    return MixpanelTracer(
        trace_name="Support flow - 1234",
        trace_type="chain",
        project_name="Langflow",
        trace_id=uuid.uuid4(),
        **kwargs,
    )


def _run_flow(tracer: MixpanelTracer) -> None:
    tracer.add_trace("OpenAIModel-abc", "OpenAI", "llm", {"input_value": "SECRET-PROMPT"})
    handler = tracer.get_langchain_callback()
    llm_run, tool_run = uuid.uuid4(), uuid.uuid4()
    handler.on_chat_model_start(
        {},
        [[HumanMessage(content="SECRET-PROMPT")]],
        run_id=llm_run,
        metadata={"ls_provider": "openai", "ls_model_name": "gpt-4o-mini"},
    )
    message = AIMessage(
        content="SECRET-COMPLETION",
        usage_metadata={"input_tokens": 12, "output_tokens": 5, "total_tokens": 17},
    )
    handler.on_llm_end(
        LLMResult(generations=[[ChatGeneration(message=message)]], llm_output={"model_name": "gpt-4o-mini-2024-07-18"}),
        run_id=llm_run,
    )
    handler.on_tool_start({"name": "search"}, "SECRET-ARGS", run_id=tool_run)
    handler.on_tool_end("SECRET-RESULT", run_id=tool_run)
    tracer.end_trace("OpenAIModel-abc", "OpenAI", outputs={"text_output": "SECRET-COMPLETION"})
    tracer.end({}, {"result": "SECRET-COMPLETION"})


def test_exports_flow_component_llm_and_tool_spans_to_mixpanel(receiver):
    tracer = _make_tracer(user_id="api-key-owner", session_id="session-1", tracing_user_id="end-user-42")
    assert tracer.ready

    _run_flow(tracer)
    spans = receiver.spans()

    request = receiver.requests[0]
    assert request["path"] == "/v1/ai/otel/traces"
    assert request["headers"]["Content-Type"] == "application/x-protobuf"
    assert request["headers"]["Authorization"] == f"Basic {base64.b64encode(f'{TOKEN}:'.encode()).decode()}"

    root, component = spans["Support flow - 1234"], spans["OpenAI"]
    llm, tool = spans["chat gpt-4o-mini"], spans["execute_tool search"]
    assert root["parent_span_id"] == b""
    assert component["parent_span_id"] == root["span_id"]
    assert llm["parent_span_id"] == component["span_id"]
    assert tool["parent_span_id"] == component["span_id"]

    for span in spans.values():
        assert span["attributes"]["user.id"] == "end-user-42"
        assert span["attributes"]["session.id"] == "session-1"
        assert span["attributes"]["langflow.user_id"] == "api-key-owner"

    assert llm["attributes"]["gen_ai.operation.name"] == "chat"
    assert llm["attributes"]["gen_ai.provider.name"] == "openai"
    assert llm["attributes"]["gen_ai.request.model"] == "gpt-4o-mini"
    assert llm["attributes"]["gen_ai.response.model"] == "gpt-4o-mini-2024-07-18"
    assert llm["attributes"]["gen_ai.usage.input_tokens"] == 12
    assert llm["attributes"]["gen_ai.usage.output_tokens"] == 5
    assert tool["attributes"]["gen_ai.tool.name"] == "search"


def test_prompts_and_completions_stay_local_by_default(receiver):
    _run_flow(_make_tracer(tracing_user_id="end-user-42"))

    assert receiver.spans()
    exported = b"".join(request["body"] for request in receiver.requests)
    assert exported
    assert b"SECRET" not in exported


def test_capture_content_exports_prompts_and_completions(receiver, monkeypatch):
    monkeypatch.setenv("MIXPANEL_CAPTURE_CONTENT", "true")
    _run_flow(_make_tracer(tracing_user_id="end-user-42"))
    spans = receiver.spans()

    llm = spans["chat gpt-4o-mini"]["attributes"]
    assert "SECRET-PROMPT" in llm["gen_ai.input.messages"]
    assert "SECRET-COMPLETION" in llm["gen_ai.output.messages"]
    tool = spans["execute_tool search"]["attributes"]
    assert tool["gen_ai.tool.call.arguments"] == "SECRET-ARGS"
    assert "SECRET-RESULT" in tool["gen_ai.tool.call.result"]
    assert "SECRET-PROMPT" in spans["OpenAI"]["attributes"]["langflow.inputs"]


def test_authenticated_user_is_not_used_as_the_mixpanel_user(receiver):
    _run_flow(_make_tracer(user_id="api-key-owner"))
    spans = receiver.spans()

    assert spans
    for span in spans.values():
        assert "user.id" not in span["attributes"]
        assert span["attributes"]["langflow.user_id"] == "api-key-owner"


def test_failed_llm_call_and_unfinished_runs_still_end_their_spans(receiver):
    tracer = _make_tracer(tracing_user_id="end-user-42")
    tracer.add_trace("Agent-1", "Agent", "agent", {})
    handler = tracer.get_langchain_callback()
    failed, unfinished = uuid.uuid4(), uuid.uuid4()
    handler.on_chat_model_start({}, [[HumanMessage(content="hi")]], run_id=failed, metadata={"ls_model_name": "m1"})
    handler.on_llm_error(RuntimeError("rate limited"), run_id=failed)
    handler.on_chat_model_start({}, [[HumanMessage(content="hi")]], run_id=unfinished, metadata={"ls_model_name": "m2"})
    tracer.end_trace("Agent-1", "Agent")
    tracer.end({}, {})
    spans = receiver.spans()

    assert spans["chat m1"]["status"] == 2
    assert "chat m2" in spans
    assert spans["chat m2"]["parent_span_id"] == spans["Agent"]["span_id"]


def test_completion_models_tool_errors_and_open_components_are_recorded(receiver, monkeypatch):
    from langchain_core.outputs import Generation
    from langflow.schema.message import Message

    monkeypatch.setenv("MIXPANEL_CAPTURE_CONTENT", "1")
    tracer = _make_tracer(tracing_user_id="end-user-42")
    tracer.add_trace("LLM-1", "Legacy LLM", "llm", {"prompt": Message(text="message prompt")})
    handler = tracer.get_langchain_callback()
    completion, tool = uuid.uuid4(), uuid.uuid4()
    handler.on_llm_start({}, ["complete this"], run_id=completion, invocation_params={"model": "claude-2"})
    handler.on_llm_end(LLMResult(generations=[[Generation(text="done")]]), run_id=completion)
    handler.on_tool_start({}, "args", run_id=tool)
    handler.on_tool_error(ValueError("bad args"), run_id=tool)
    handler.on_llm_end(LLMResult(generations=[]), run_id=uuid.uuid4())
    tracer.end_trace("LLM-1", "Legacy LLM", logs=[{"message": "step"}])
    tracer.add_trace("Output-1", "Chat Output", "output", {})
    tracer.end({}, {})
    spans = receiver.spans()

    completion_span = spans["text_completion claude-2"]["attributes"]
    assert completion_span["gen_ai.provider.name"] == "anthropic"
    assert "gen_ai.usage.input_tokens" not in completion_span
    assert spans["execute_tool tool"]["status"] == 2
    assert "message prompt" in spans["Legacy LLM"]["attributes"]["langflow.inputs"]
    assert "step" in spans["Legacy LLM"]["attributes"]["langflow.logs"]
    assert "Chat Output" in spans


def test_a_new_project_token_exports_with_the_new_credentials(receiver, monkeypatch):
    _run_flow(_make_tracer(tracing_user_id="end-user-42"))
    assert receiver.spans()
    monkeypatch.setenv("MIXPANEL_PROJECT_TOKEN", "rotated-token")
    receiver.requests.clear()

    _run_flow(_make_tracer(tracing_user_id="end-user-42"))

    assert receiver.spans()
    expected = f"Basic {base64.b64encode(b'rotated-token:').decode()}"
    assert all(request["headers"]["Authorization"] == expected for request in receiver.requests)


def test_disabled_tracer_ignores_lifecycle_calls(monkeypatch):
    monkeypatch.delenv("MIXPANEL_PROJECT_TOKEN", raising=False)
    tracer = _make_tracer()

    tracer.add_trace("c", "c", "chain", {})
    tracer.end_trace("c", "c")
    tracer.end({}, {})

    assert tracer.spans == {}


def test_operator_otlp_settings_do_not_reach_mixpanel(receiver, monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "x-apm-key=apm-secret")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://127.0.0.1:9/v1/traces")
    _run_flow(_make_tracer(tracing_user_id="end-user-42"))

    assert receiver.spans()
    assert all("x-apm-key" not in request["headers"] for request in receiver.requests)


@pytest.mark.parametrize(
    ("region", "endpoint"),
    [
        (None, "https://ingestion-us.mixpanel.com/v1/ai/otel/traces"),
        ("eu", "https://ingestion-eu.mixpanel.com/v1/ai/otel/traces"),
        ("IN", "https://ingestion-in.mixpanel.com/v1/ai/otel/traces"),
    ],
)
def test_region_selects_the_ingestion_host(monkeypatch, region, endpoint):
    monkeypatch.setenv("MIXPANEL_PROJECT_TOKEN", TOKEN)
    monkeypatch.delenv("MIXPANEL_ENDPOINT", raising=False)
    if region:
        monkeypatch.setenv("MIXPANEL_REGION", region)
    else:
        monkeypatch.delenv("MIXPANEL_REGION", raising=False)

    assert MixpanelTracer._get_config() == (endpoint, TOKEN)


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"MIXPANEL_PROJECT_TOKEN": TOKEN, "MIXPANEL_REGION": "mars"},
        {"MIXPANEL_PROJECT_TOKEN": TOKEN, "MIXPANEL_ENDPOINT": "not-a-url"},
    ],
)
def test_tracer_stays_off_without_a_valid_configuration(monkeypatch, env):
    for name in ("MIXPANEL_PROJECT_TOKEN", "MIXPANEL_REGION", "MIXPANEL_ENDPOINT"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    tracer = _make_tracer(tracing_user_id="end-user-42")

    assert tracer.ready is False
    assert tracer.get_langchain_callback() is None
