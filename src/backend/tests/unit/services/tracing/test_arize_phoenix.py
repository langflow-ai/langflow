"""Unit tests for Arize Phoenix tracer and nested agent sub-traces."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from langflow.services.tracing.arize_phoenix import ArizePhoenixTracer
from langflow.services.tracing.phoenix_callback import PhoenixCallbackHandler
from langflow.services.tracing.service import ComponentTraceContext, component_context_var
from openinference.semconv.trace import SpanAttributes
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@pytest.fixture
def in_memory_tracer_provider():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


@pytest.fixture
def phoenix_tracer(in_memory_tracer_provider):
    provider, exporter = in_memory_tracer_provider
    trace_id = uuid4()

    with (
        patch.dict(
            os.environ,
            {
                "PHOENIX_COLLECTOR_ENDPOINT": "http://localhost:6006",
                "ARIZE_PHOENIX_USE_INSTRUMENTOR": "false",
            },
            clear=False,
        ),
        patch.object(ArizePhoenixTracer, "setup_arize_phoenix", return_value=True),
    ):
        tracer = ArizePhoenixTracer(
            trace_name="Test Flow - flow-123",
            trace_type="chain",
            project_name="test-project",
            trace_id=trace_id,
            session_id="session-1",
        )
        tracer.tracer_provider = provider
        tracer.tracer = provider.get_tracer("test")
        tracer.root_span = tracer.tracer.start_span("Langflow")
        tracer.child_spans = {}
        tracer._context_tokens = {}
        tracer._current_component_id = None
        tracer._langchain_instrumentor_enabled = False
        tracer._ready = True
        tracer.propagator = MagicMock()
        tracer.carrier = {}
        yield tracer, exporter


def test_add_trace_parents_to_root_span(phoenix_tracer):
    tracer, exporter = phoenix_tracer
    trace_id = "agent-vertex-1"

    tracer.add_trace(
        trace_id=trace_id,
        trace_name="Agent (agent-vertex-1)",
        trace_type="agent",
        inputs={"input_value": "hello"},
    )

    assert trace_id in tracer.child_spans
    spans = exporter.get_finished_spans()
    assert len(spans) == 0  # component span still open

    tracer.end_trace(trace_id=trace_id, trace_name="Agent (agent-vertex-1)", outputs={"response": "hi"})
    finished = exporter.get_finished_spans()
    assert len(finished) == 1
    assert finished[0].name == "Agent (agent-vertex-1)"
    assert finished[0].parent.span_id == tracer.root_span.get_span_context().span_id


def test_activate_component_span_sets_current_context(phoenix_tracer):
    tracer, _exporter = phoenix_tracer
    trace_id = "agent-vertex-2"

    tracer.add_trace(
        trace_id=trace_id,
        trace_name="Agent",
        trace_type="agent",
        inputs={},
    )
    token = tracer.activate_component_span(trace_id)
    assert token is not None
    current = trace.get_current_span()
    assert current.get_span_context().span_id == tracer.child_spans[trace_id].get_span_context().span_id

    tracer.deactivate_component_span(trace_id)
    current_after = trace.get_current_span()
    assert current_after.get_span_context().span_id != tracer.child_spans[trace_id].get_span_context().span_id


def test_get_langchain_callback_returns_handler_when_component_context_set(phoenix_tracer):
    tracer, _exporter = phoenix_tracer
    trace_id = "agent-vertex-3"

    tracer.add_trace(trace_id=trace_id, trace_name="Agent", trace_type="agent", inputs={})
    tracer.activate_component_span(trace_id)

    component_context_var.set(
        ComponentTraceContext(
            trace_id=trace_id,
            trace_name="Agent",
            trace_type="agent",
            vertex=None,
            inputs={},
        )
    )
    callback = tracer.get_langchain_callback()
    assert callback is not None
    assert isinstance(callback, PhoenixCallbackHandler)
    assert callback.parent_span is tracer.child_spans[trace_id]

    tracer.deactivate_component_span(trace_id)
    component_context_var.set(None)


def test_phoenix_callback_creates_nested_langchain_spans(phoenix_tracer):
    tracer, exporter = phoenix_tracer
    trace_id = "agent-vertex-4"

    tracer.add_trace(trace_id=trace_id, trace_name="Agent", trace_type="agent", inputs={})
    tracer.activate_component_span(trace_id)

    callback = PhoenixCallbackHandler(tracer, parent_span=tracer.child_spans[trace_id])
    run_id = uuid4()
    callback.on_tool_start(
        serialized={"name": "search"},
        input_str="query",
        run_id=run_id,
        parent_run_id=None,
    )
    callback.on_tool_end(output="result", run_id=run_id)

    component_span_id = tracer.child_spans[trace_id].get_span_context().span_id
    tracer.deactivate_component_span(trace_id)
    tracer.end_trace(trace_id=trace_id, trace_name="Agent", outputs={})

    finished = exporter.get_finished_spans()
    tool_spans = [s for s in finished if s.name == "search"]
    assert len(tool_spans) == 1
    assert tool_spans[0].attributes.get(SpanAttributes.OPENINFERENCE_SPAN_KIND) == "tool"
    assert tool_spans[0].parent.span_id == component_span_id


def test_on_agent_action_creates_agent_span(phoenix_tracer):
    tracer, exporter = phoenix_tracer
    trace_id = "agent-vertex-5"

    tracer.add_trace(trace_id=trace_id, trace_name="Agent", trace_type="agent", inputs={})
    tracer.activate_component_span(trace_id)

    from langchain_classic.schema import AgentAction

    callback = PhoenixCallbackHandler(tracer, parent_span=tracer.child_spans[trace_id])
    callback.on_agent_action(
        AgentAction(tool="search", tool_input="weather", log=""),
        run_id=uuid4(),
    )

    tracer.deactivate_component_span(trace_id)
    tracer.end_trace(trace_id=trace_id, trace_name="Agent", outputs={})

    finished = exporter.get_finished_spans()
    action_spans = [s for s in finished if "Agent Action" in s.name]
    assert len(action_spans) == 1
    assert action_spans[0].attributes.get(SpanAttributes.OPENINFERENCE_SPAN_KIND) == "agent"


def test_instrumentor_disabled_by_default_on_setup():
    with (
        patch.dict(os.environ, {"PHOENIX_COLLECTOR_ENDPOINT": "http://localhost:6006"}, clear=False),
        patch("phoenix.otel.TracerProvider") as mock_provider_cls,
    ):
        mock_provider = MagicMock()
        mock_provider_cls.return_value = mock_provider
        tracer = ArizePhoenixTracer(
            trace_name="Flow - id",
            trace_type="chain",
            project_name="p",
            trace_id=uuid4(),
        )
        if tracer._ready:
            assert getattr(tracer, "_langchain_instrumentor_enabled", False) is False
