"""Langfuse v4 callback regressions for generation attribution (#13429) and component snapshots (#13965)."""

import os
import threading
import uuid
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def langfuse_env_vars():
    """Set fake langfuse credentials for testing."""
    with patch.dict(
        os.environ,
        {
            "LANGFUSE_SECRET_KEY": "sk-lf-test",  # pragma: allowlist secret
            "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
            "LANGFUSE_HOST": "http://localhost:3000",
        },
    ):
        yield


@pytest.fixture(autouse=True)
def reset_langfuse_shared_client():
    """Clear the cached Langfuse client between tests so mocks don't leak."""
    from langflow.services.tracing.langfuse import _reset_shared_client_for_tests

    _reset_shared_client_for_tests()
    yield
    _reset_shared_client_for_tests()


def _build_real_langfuse_client_or_skip(tracer_provider):
    """Construct a real Langfuse client wired to ``tracer_provider``.

    Its network OTLP exporter is replaced with a no-op so the test stays local
    and fast (no connection to a Langfuse server). Skips if the SDK cannot be
    imported on this interpreter (e.g. pydantic/python version mismatch).
    """
    try:
        from langfuse import Langfuse
        from opentelemetry.sdk.trace.export import SpanExportResult
    except Exception as exc:
        pytest.skip(f"langfuse SDK is not importable: {exc}")

    class _NoopOtlpExporter:
        def __init__(self, *args, **kwargs):
            pass

        def export(self, spans):  # noqa: ARG002
            return SpanExportResult.SUCCESS

        def shutdown(self):
            pass

        def force_flush(self, timeout_millis=30000):  # noqa: ARG002
            return True

    with patch("langfuse._client.span_processor.OTLPSpanExporter", _NoopOtlpExporter):
        client = Langfuse(
            public_key="pk-lf-test",
            secret_key="sk-lf-test",  # noqa: S106  # pragma: allowlist secret
            host="http://localhost:3000",
            tracer_provider=tracer_provider,
            tracing_enabled=True,
        )
    # Avoid a network round-trip during tracer setup's health check.
    client.auth_check = lambda: True
    return client


def test_reset_joins_real_client_background_threads():
    from langflow.services.tracing.langfuse import _reset_shared_client_for_tests
    from opentelemetry.sdk.trace import TracerProvider

    previous_threads = set(threading.enumerate())
    provider = TracerProvider()
    client = _build_real_langfuse_client_or_skip(provider)
    workers = set(threading.enumerate()) - previous_threads
    assert workers, "the real SDK should start its exporter and consumer threads"
    try:
        _reset_shared_client_for_tests()
        assert not [worker.name for worker in workers if worker.is_alive()]
    finally:
        client.shutdown()
        provider.shutdown()


@pytest.mark.parametrize("use_global_provider", [False, True], ids=["explicit", "global"])
def test_reset_preserves_application_trace_export(monkeypatch, use_global_provider):
    from langflow.services.tracing.langfuse import _reset_shared_client_for_tests
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    if use_global_provider:
        monkeypatch.setattr("opentelemetry.trace.get_tracer_provider", lambda: provider)
    client = _build_real_langfuse_client_or_skip(None if use_global_provider else provider)
    assert client._resources.tracer_provider is provider
    try:
        tracer = provider.get_tracer("application")
        with tracer.start_as_current_span("before reset"):
            pass
        _reset_shared_client_for_tests()
        with tracer.start_as_current_span("after reset"):
            pass
        assert [span.name for span in exporter.get_finished_spans()] == ["before reset", "after reset"]
    finally:
        client.shutdown()
        provider.shutdown()


class TestRootGenerationNestsUnderFlowTrace:
    """End-to-end: a root LLM generation shares the flow trace (issue #13429)."""

    @pytest.mark.parametrize("wrapped", [False, True], ids=["bare", "chain"])
    @pytest.mark.parametrize("fails", [False, True], ids=["success", "error"])
    def test_root_llm_generation_shares_flow_trace_and_nests_under_component(self, wrapped, fails):
        pytest.importorskip("langfuse")
        pytest.importorskip("langchain_core")
        import langflow.services.tracing.langfuse as langfuse_module
        from langchain_core.messages import AIMessage, HumanMessage
        from langchain_core.outputs import ChatGeneration, LLMResult
        from langflow.services.tracing.langfuse import LangFuseTracer
        from opentelemetry import context, trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        client = _build_real_langfuse_client_or_skip(provider)

        with (
            patch.object(langfuse_module, "_get_or_create_shared_client", lambda config: client),  # noqa: ARG005
            provider.get_tracer("app").start_as_current_span("request") as request_span,
        ):
            try:
                tracer = LangFuseTracer(
                    trace_name="repro - flow-xyz",
                    trace_type="chain",
                    project_name="proj",
                    trace_id=uuid.uuid4(),
                    user_id="demo-user-13429",
                    session_id="demo-session-13429",
                )
                assert tracer.ready

                # Open a component span, then run a bare chat model as the root
                # LangChain run (parent_run_id=None) — the orphan-trace condition.
                tracer.add_trace("comp-ollama", "Ollama (comp-ollama)", "llm", {"input": "hi"})
                handler = tracer.get_langchain_callback()
                assert handler is not None

                caller_context = context.get_current()
                chain_id = uuid.uuid4() if wrapped else None
                if chain_id:
                    handler.on_chain_start({"name": "chain"}, {"input": "hi"}, run_id=chain_id)
                run_id = uuid.uuid4()
                handler.on_chat_model_start(
                    {"id": ["langchain", "chat_models", "ollama", "ChatOllama"]},
                    [[HumanMessage(content="hi")]],
                    run_id=run_id,
                    parent_run_id=chain_id,
                    invocation_params={},
                )
                # SDK instrumentation inside the model call must see this generation.
                model_span = trace.get_current_span()
                assert model_span.is_recording()
                assert model_span.name == "ChatOllama"
                assert model_span.attributes.get("user.id") == "demo-user-13429"
                if fails:
                    handler.on_llm_error(RuntimeError("model failed"), run_id=run_id, parent_run_id=chain_id)
                else:
                    result = LLMResult(generations=[[ChatGeneration(message=AIMessage(content="ok"))]])
                    handler.on_llm_end(result, run_id=run_id, parent_run_id=chain_id)
                if chain_id:
                    assert trace.get_current_span().attributes.get("user.id") == "demo-user-13429"
                    handler.on_chain_end({"output": "ok"}, run_id=chain_id)
                assert context.get_current() is caller_context
                assert "user.id" not in request_span.attributes
                tracer.end_trace("comp-ollama", "Ollama", outputs={"output": "ok"})
                tracer.end(inputs={"in": "hi"}, outputs={"out": "ok"})
            finally:
                client.shutdown()

        spans = {s.name: s for s in exporter.get_finished_spans()}
        # The flow root span carries the flow *display name*, not its id (LE-2451 / #14865).
        assert "repro" in spans, f"missing flow root span; got {list(spans)}"
        assert "Ollama" in spans, f"missing component span; got {list(spans)}"
        assert "ChatOllama" in spans, f"missing generation span; got {list(spans)}"

        root_span = spans["repro"]
        component_span = spans["Ollama"]
        generation_span = spans["ChatOllama"]

        # Langfuse indexes ``langfuse.trace.name`` for its name search; the id stays in metadata.
        assert root_span.attributes.get("langfuse.trace.name") == "repro"
        assert root_span.attributes.get("langfuse.observation.metadata.flow_id") == "flow-xyz"

        # The generation is recorded as a langfuse generation (carries token usage).
        assert generation_span.attributes.get("langfuse.observation.type") == "generation"
        assert generation_span.attributes.get("user.id") == "demo-user-13429"
        assert generation_span.attributes.get("session.id") == "demo-session-13429"
        assert generation_span.attributes.get("langfuse.trace.name") == "repro"
        assert generation_span.attributes.get("langfuse.trace.metadata.flow_id") == "flow-xyz"

        # Core of #13429: the generation must live in the flow trace, not orphan.
        assert generation_span.context.trace_id == root_span.context.trace_id
        # And nest under the component span (not be a root of its own trace).
        assert generation_span.parent is not None
        if wrapped:
            chain_span = spans["chain"]
            assert generation_span.parent.span_id == chain_span.context.span_id
            assert chain_span.parent.span_id == component_span.context.span_id
        else:
            assert generation_span.parent.span_id == component_span.context.span_id


@pytest.mark.asyncio
async def test_async_callback_manager_exports_attributed_generation_and_restores_caller():
    from langchain_core.callbacks.manager import AsyncCallbackManager
    from langchain_core.messages import AIMessage, HumanMessage
    from langchain_core.outputs import ChatGeneration, LLMResult
    from langflow.services.tracing.langfuse import LangFuseTracer
    from opentelemetry import context
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    client = _build_real_langfuse_client_or_skip(provider)
    try:
        with patch("langflow.services.tracing.langfuse._get_or_create_shared_client", return_value=client):
            tracer = LangFuseTracer("flow - id", "chain", "project", uuid.uuid4(), user_id="user", session_id="session")
        handler = tracer.get_langchain_callback()
        assert handler is not None
        manager = AsyncCallbackManager([handler])
        before = context.get_current()
        [run] = await manager.on_chat_model_start(
            {"name": "async model"}, [[HumanMessage(content="hi")]], invocation_params={}
        )
        await run.on_llm_end(LLMResult(generations=[[ChatGeneration(message=AIMessage(content="hello"))]]))
        assert context.get_current() is before
        tracer.end({}, {})
        spans = {span.name: span for span in exporter.get_finished_spans()}
        assert spans["async model"].parent.span_id == spans["flow"].context.span_id
        assert spans["async model"].attributes["user.id"] == "user"
        assert spans["async model"].attributes["session.id"] == "session"
    finally:
        client.shutdown()
        provider.shutdown()


class TestFlowNameParsing:
    """``LangFuseTracer`` names the trace after the flow, parsed out of ``trace_name``.

    The graph builds ``trace_name`` as ``f"{flow_name} - {flow_id}"`` (LE-2451 / #14865).
    """

    @staticmethod
    def _make_tracer(trace_name: str):
        pytest.importorskip("langfuse")
        from langflow.services.tracing.langfuse import LangFuseTracer

        with patch("langflow.services.tracing.langfuse._get_or_create_shared_client") as mock_client:
            mock_client.return_value.auth_check.return_value = True
            tracer = LangFuseTracer(
                trace_name=trace_name,
                trace_type="flow",
                project_name="test-project",
                trace_id=uuid.uuid4(),
            )
        assert tracer.ready, "tracer setup failed; the SDK calls below were never made"
        return tracer, mock_client.return_value

    @pytest.mark.parametrize(
        ("trace_name", "expected_name", "expected_flow_id"),
        [
            ("demo flow - flow-xyz", "demo flow", "flow-xyz"),
            # A display name containing the separator must not be truncated.
            ("Customer - Agent - flow-xyz", "Customer - Agent", "flow-xyz"),
        ],
    )
    def test_trace_is_named_after_the_flow(self, trace_name, expected_name, expected_flow_id):
        tracer, client = self._make_tracer(trace_name)

        assert tracer.flow_name == expected_name
        assert tracer.flow_id == expected_flow_id
        assert client.start_observation.call_args.kwargs["name"] == expected_name
        assert client.start_observation.call_args.kwargs["metadata"]["flow_id"] == expected_flow_id

    def test_unnamed_flow_falls_back_to_flow_id(self):
        # An unnamed graph formats its run name as "None - <id>"; the trace must not be called "None".
        tracer, client = self._make_tracer("None - flow-xyz")

        assert tracer.flow_id == "flow-xyz"
        assert client.start_observation.call_args.kwargs["name"] == "flow-xyz"


class TestGraphRunNamesTraceAfterFlow:
    """A real multi-component graph run names the Langfuse trace after the flow (LE-2451 / #14865).

    Drives the real graph engine and the real ``TracingService`` so the run name reaches
    ``LangFuseTracer`` exactly as in production (``f"{flow_name} - {flow_id}"``), then inspects
    the spans the langfuse SDK exports.
    """

    @staticmethod
    def _build_graph(flow_name: str, flow_id: str):
        from lfx.components.input_output import ChatInput, ChatOutput, TextInputComponent, TextOutputComponent
        from lfx.components.processing import CombineTextComponent
        from lfx.graph.graph.base import Graph

        chat_in = ChatInput(_id="chat-in")
        chat_in.set(input_value="hello", should_store_message=False, session_id="session-le2451")
        text_in = TextInputComponent(_id="text-in")
        text_in.set(input_value="from text input")
        combine = CombineTextComponent(_id="combine")
        combine.set(text1=chat_in.message_response, text2=text_in.text_response, delimiter=" | ")
        text_out = TextOutputComponent(_id="text-out")
        text_out.set(input_value=combine.combine_texts)
        chat_out = ChatOutput(_id="chat-out")
        chat_out.set(input_value=text_out.text_response, should_store_message=False, session_id="session-le2451")
        return Graph(start=chat_in, end=chat_out, flow_id=flow_id, flow_name=flow_name, user_id="user-le2451")

    @pytest.mark.asyncio
    async def test_five_component_graph_run(self):
        pytest.importorskip("langfuse")
        import asyncio
        import contextlib
        from unittest.mock import MagicMock

        import langflow.services.tracing.langfuse as langfuse_module
        from langflow.services.tracing.base import BaseTracer
        from langflow.services.tracing.langfuse import LangFuseTracer
        from langflow.services.tracing.service import TracingService
        from lfx.services.settings.base import Settings
        from lfx.services.settings.service import SettingsService
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

        class _InertTracer(BaseTracer):
            """Stands in for every non-Langfuse provider so only Langfuse is exercised."""

            def __init__(self, *args, **kwargs):
                pass

            @property
            def ready(self):
                return False

            def add_trace(self, *args, **kwargs):
                pass

            def end_trace(self, *args, **kwargs):
                pass

            def end(self, *args, **kwargs):
                pass

            def get_langchain_callback(self):
                return None

        flow_id = str(uuid.uuid4())
        flow_name = "Customer - Agent"

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        client = _build_real_langfuse_client_or_skip(provider)

        settings = Settings()
        settings.deactivate_tracing = False
        service = TracingService(SettingsService(settings, MagicMock()))

        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch.object(langfuse_module, "_get_or_create_shared_client", lambda config: client)  # noqa: ARG005
            )
            stack.enter_context(
                patch("langflow.services.tracing.service._get_langfuse_tracer", return_value=LangFuseTracer)
            )
            # Components resolve the tracing service lazily through lfx deps.
            stack.enter_context(patch("lfx.services.deps.get_tracing_service", return_value=service))
            for name in ("langsmith", "langwatch", "arize_phoenix", "opik", "traceloop", "native", "openlayer"):
                stack.enter_context(
                    patch(f"langflow.services.tracing.service._get_{name}_tracer", return_value=_InertTracer)
                )
            try:
                graph = self._build_graph(flow_name, flow_id)
                graph._tracing_service = service
                graph._tracing_service_initialized = True
                graph.session_id = "session-le2451"
                graph.prepare()
                ran = [result.vertex.id async for result in graph.async_start() if hasattr(result, "vertex")]
                # The graph ends the trace in a background task; wait for it before reading spans.
                await asyncio.gather(*graph._end_trace_tasks)
            finally:
                client.shutdown()

        assert ran == ["chat-in", "text-in", "combine", "text-out", "chat-out"]

        spans = exporter.get_finished_spans()
        exported_ids = {s.context.span_id for s in spans}
        roots = [s for s in spans if s.parent is None or s.parent.span_id not in exported_ids]
        assert [s.name for s in roots] == [flow_name], f"unexpected root spans; got {[s.name for s in spans]}"
        root = roots[0]

        assert root.attributes.get("langfuse.trace.name") == flow_name
        assert root.attributes.get("langfuse.observation.metadata.flow_id") == flow_id
        assert root.attributes.get("langfuse.trace.metadata.flow_id") == flow_id

        children = [s for s in spans if s is not root]
        assert {s.name for s in children} == {"Chat Input", "Text Input", "Combine Text", "Text Output", "Chat Output"}
        assert all(s.parent.span_id == root.context.span_id for s in children)
        assert len({s.context.trace_id for s in spans}) == 1


def test_handler_deepcopy_returns_self(monkeypatch):
    """Regression test for https://github.com/langflow-ai/langflow/issues/13965.

    The callback handler's __deepcopy__ must return self so that
    deepcopy(component) in component_tool.py never triggers
    LangfuseResourceManager.__new__() with missing credential kwargs.
    """
    import copy

    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://localhost:3000")

    from langflow.services.tracing.langfuse import LangFuseTracer

    with patch("langflow.services.tracing.langfuse._get_or_create_shared_client") as mock_client:
        mock_client.return_value.auth_check.return_value = True
        mock_client.return_value.start_observation.return_value.__enter__ = lambda s: s
        mock_client.return_value.start_observation.return_value.__exit__ = lambda *_: None
        mock_client.return_value.start_observation.return_value.id = "root-span-id"

        tracer = LangFuseTracer(
            trace_name="test-flow - abc",
            trace_type="flow",
            project_name="test",
            trace_id=uuid.uuid4(),
        )

    handler = tracer.get_langchain_callback()
    assert handler is not None, "Expected a callback handler when Langfuse is configured"

    # The key assertion: deepcopy must not raise and must return the same instance.
    copied = copy.deepcopy(handler)
    assert copy.copy(handler) is handler
    assert copied is handler, "deepcopy of handler should return self (no reconstruction of LangfuseResourceManager)"
