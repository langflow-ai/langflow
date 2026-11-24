"""Regression tests for the Langfuse orphan-generation fix (issue #13429).

When a model runs as the *root* LangChain run — i.e. invoked directly with no
wrapping chain, as reproduced with Ollama — the langfuse v3 ``CallbackHandler``
emitted the LLM generation as a separate, orphan trace: ``parent = None``,
``userId = None``, ``sessionId = None``, and the token usage detached from the
flow trace. The langfuse SDK only applies the constructor ``trace_context`` on
the chain path, so a bare model's generation started a brand-new trace.

``LangFuseTracer.get_langchain_callback`` now returns a handler that re-parents
root LLM runs under the flow's component (or root) span, so the generation
shares the flow ``trace_id`` and stays attributed to the user/session.

The end-to-end test exercises the real langfuse SDK with an in-memory
OpenTelemetry exporter — a pure mock cannot catch this bug because the orphaning
happens inside the SDK's generation path.
"""

import os
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


class TestOtelParentSpanBuilder:
    """``_build_otel_parent_span`` turns the flow ids into an OTel parent span."""

    def test_returns_none_when_ids_missing(self):
        from langflow.services.tracing.langfuse import _build_otel_parent_span

        assert _build_otel_parent_span(None, "b" * 16) is None
        assert _build_otel_parent_span("a" * 32, None) is None
        assert _build_otel_parent_span("", "") is None

    def test_returns_none_for_non_hex_ids(self):
        """Mock span ids (non-hex) degrade gracefully instead of raising."""
        from langflow.services.tracing.langfuse import _build_otel_parent_span

        assert _build_otel_parent_span("not-hex", "child-span-id") is None

    def test_builds_span_context_from_hex_ids(self):
        from langflow.services.tracing.langfuse import _build_otel_parent_span

        trace_id = "a" * 32
        span_id = "b" * 16
        parent = _build_otel_parent_span(trace_id, span_id)

        assert parent is not None
        ctx = parent.get_span_context()
        assert ctx.trace_id == int(trace_id, 16)
        assert ctx.span_id == int(span_id, 16)
        # Sampled so downstream generations are recorded under the flow trace.
        assert ctx.trace_flags.sampled


class _RecordingBase:
    """Stand-in for langfuse's ``CallbackHandler`` that records OTel context.

    Each LLM-start callback records the span context that is *current* at the
    moment the SDK would create the generation span. The re-parenting subclass
    is expected to make the flow's parent span current for root runs only.
    """

    def __init__(self, *, trace_context=None, **kwargs):  # noqa: ARG002
        self.trace_context = trace_context
        self.captured = []

    def _record(self):
        from opentelemetry import trace as otel_trace_api

        self.captured.append(otel_trace_api.get_current_span().get_span_context())

    def on_chat_model_start(self, *args, **kwargs):  # noqa: ARG002
        self._record()

    def on_llm_start(self, *args, **kwargs):  # noqa: ARG002
        self._record()


class TestRootRunReparentingHandler:
    """The subclass activates the parent span for root LLM runs only."""

    def _make_handler(self, trace_id="a" * 32, span_id="b" * 16, *, with_parent=True):
        from langflow.services.tracing.langfuse import (
            _build_otel_parent_span,
            _root_run_reparenting_handler_cls,
        )

        handler_cls = _root_run_reparenting_handler_cls(_RecordingBase)
        otel_parent = _build_otel_parent_span(trace_id, span_id) if with_parent else None
        handler = handler_cls(
            trace_context={"trace_id": trace_id, "parent_span_id": span_id},
            otel_parent=otel_parent,
        )
        return handler, trace_id, span_id

    def test_activates_parent_for_root_chat_model_run(self):
        handler, trace_id, span_id = self._make_handler()

        handler.on_chat_model_start({}, [], run_id=uuid.uuid4(), parent_run_id=None)

        ctx = handler.captured[-1]
        assert ctx.is_valid
        assert ctx.trace_id == int(trace_id, 16)
        assert ctx.span_id == int(span_id, 16)

    def test_activates_parent_for_root_llm_run(self):
        handler, trace_id, span_id = self._make_handler()

        handler.on_llm_start({}, [], run_id=uuid.uuid4(), parent_run_id=None)

        ctx = handler.captured[-1]
        assert ctx.is_valid
        assert ctx.trace_id == int(trace_id, 16)
        assert ctx.span_id == int(span_id, 16)

    def test_does_not_activate_for_non_root_run(self):
        """A wrapping chain/agent is present (parent_run_id set) → leave untouched.

        The SDK already nests these correctly under the chain span, so the
        handler must not force the flow parent into the OTel context.
        """
        handler, _, _ = self._make_handler()

        handler.on_chat_model_start({}, [], run_id=uuid.uuid4(), parent_run_id=uuid.uuid4())

        ctx = handler.captured[-1]
        # No span was activated → ambient context is the invalid root span.
        assert not ctx.is_valid

    def test_missing_parent_is_safe(self):
        """When the parent span id is not resolvable, root runs simply no-op."""
        handler, _, _ = self._make_handler(with_parent=False)

        handler.on_chat_model_start({}, [], run_id=uuid.uuid4(), parent_run_id=None)

        ctx = handler.captured[-1]
        assert not ctx.is_valid

    def test_handler_is_deepcopy_and_copy_safe(self):
        """Survive ``copy.deepcopy`` / ``copy.copy`` by returning self.

        The handler never recurses into the langfuse client.

        Langflow deep-copies flow/graph state (restore-point snapshots, working-flow
        copies, component build). The real langfuse ``CallbackHandler`` / ``Langfuse``
        client is NOT deep-copyable — its singleton ``LangfuseResourceManager.__new__``
        is keyword-only, so ``copy.deepcopy`` (which calls ``cls.__new__(cls)`` with
        no args) raises ``TypeError: __new__() missing 3 required keyword-only
        arguments``. That surfaced to users as a failed Agent build. A base whose
        deepcopy explodes stands in for that; the subclass must short-circuit it.
        """
        import copy

        from langflow.services.tracing.langfuse import _root_run_reparenting_handler_cls

        class _NonCopyableBase:
            def __init__(self, *, trace_context=None, **kwargs):  # noqa: ARG002
                self.trace_context = trace_context

            def __deepcopy__(self, memo):
                msg = "LangfuseResourceManager.__new__() missing 3 required keyword-only arguments"
                raise TypeError(msg)

            def __copy__(self):
                msg = "LangfuseResourceManager.__new__() missing 3 required keyword-only arguments"
                raise TypeError(msg)

        handler_cls = _root_run_reparenting_handler_cls(_NonCopyableBase)
        handler = handler_cls(trace_context={"trace_id": "a" * 32}, otel_parent=None)

        assert copy.deepcopy(handler) is handler
        assert copy.copy(handler) is handler
        # Deep-copying a container that holds the handler must not raise either.
        assert copy.deepcopy({"callbacks": [handler]})["callbacks"][0] is handler


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


class TestRootGenerationNestsUnderFlowTrace:
    """End-to-end: a root LLM generation shares the flow trace (issue #13429)."""

    def test_root_llm_generation_shares_flow_trace_and_nests_under_component(self):
        pytest.importorskip("langfuse")
        pytest.importorskip("langchain_core")
        import langflow.services.tracing.langfuse as langfuse_module
        from langchain_core.messages import AIMessage, HumanMessage
        from langchain_core.outputs import ChatGeneration, LLMResult
        from langflow.services.tracing.langfuse import LangFuseTracer
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        client = _build_real_langfuse_client_or_skip(provider)

        with patch.object(langfuse_module, "_get_or_create_shared_client", lambda config: client):  # noqa: ARG005
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

                run_id = uuid.uuid4()
                handler.on_chat_model_start(
                    {"id": ["langchain", "chat_models", "ollama", "ChatOllama"]},
                    [[HumanMessage(content="hi")]],
                    run_id=run_id,
                    parent_run_id=None,
                    invocation_params={},
                )
                handler.on_llm_end(
                    LLMResult(generations=[[ChatGeneration(message=AIMessage(content="ok"), generation_info={})]]),
                    run_id=run_id,
                    parent_run_id=None,
                )
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

        # Core of #13429: the generation must live in the flow trace, not orphan.
        assert generation_span.context.trace_id == root_span.context.trace_id
        # And nest under the component span (not be a root of its own trace).
        assert generation_span.parent is not None
        assert generation_span.parent.span_id == component_span.context.span_id


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
        assert client.start_span.call_args.kwargs["name"] == expected_name
        assert client.start_span.call_args.kwargs["metadata"]["flow_id"] == expected_flow_id
        trace_update = client.start_span.return_value.update_trace.call_args.kwargs
        assert trace_update["name"] == expected_name
        assert trace_update["metadata"]["flow_id"] == expected_flow_id

    def test_unnamed_flow_falls_back_to_flow_id(self):
        # An unnamed graph formats its run name as "None - <id>"; the trace must not be called "None".
        tracer, client = self._make_tracer("None - flow-xyz")

        assert tracer.flow_id == "flow-xyz"
        assert client.start_span.call_args.kwargs["name"] == "flow-xyz"
        assert client.start_span.return_value.update_trace.call_args.kwargs["name"] == "flow-xyz"


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

    _RootRunReparentingCallbackHandler.__deepcopy__ must return self so that
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
        mock_client.return_value.start_span.return_value.__enter__ = lambda s: s
        mock_client.return_value.start_span.return_value.__exit__ = lambda *_: None
        mock_client.return_value.start_span.return_value.id = "root-span-id"
        mock_client.return_value.start_span.return_value.update_trace = lambda **_: None

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
    assert copied is handler, "deepcopy of handler should return self (no reconstruction of LangfuseResourceManager)"
