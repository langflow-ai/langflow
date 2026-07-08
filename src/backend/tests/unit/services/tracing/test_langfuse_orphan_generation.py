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
        assert "flow-xyz" in spans, f"missing flow root span; got {list(spans)}"
        assert "Ollama" in spans, f"missing component span; got {list(spans)}"
        assert "ChatOllama" in spans, f"missing generation span; got {list(spans)}"

        root_span = spans["flow-xyz"]
        component_span = spans["Ollama"]
        generation_span = spans["ChatOllama"]

        # The generation is recorded as a langfuse generation (carries token usage).
        assert generation_span.attributes.get("langfuse.observation.type") == "generation"

        # Core of #13429: the generation must live in the flow trace, not orphan.
        assert generation_span.context.trace_id == root_span.context.trace_id
        # And nest under the component span (not be a root of its own trace).
        assert generation_span.parent is not None
        assert generation_span.parent.span_id == component_span.context.span_id
