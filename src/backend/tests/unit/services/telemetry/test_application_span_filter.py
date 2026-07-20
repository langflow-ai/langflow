"""LLM trace content must never reach the operator's APM.

Langflow installs a global tracer provider, so the LLM tracing integrations end up
exporting through it. The export path filters to application instrumentation only; these
tests pin that boundary from the APM side, without touching the vendor integrations.
"""

import pytest
from langflow.services.telemetry.opentelemetry import (
    APPLICATION_INSTRUMENTATION_SCOPES,
    APPLICATION_TRACER_NAME,
    ApplicationOnlySpanProcessor,
)
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

SENTINEL = "SENTINEL-PROMPT-TEXT-MUST-NOT-BE-EXPORTED"

# These ship in the same opentelemetry.instrumentation.* namespace as the application
# instrumentation and carry prompt/completion text.
LLM_SCOPES = [
    "opentelemetry.instrumentation.openai",
    "opentelemetry.instrumentation.anthropic",
    "opentelemetry.instrumentation.langchain",
    "opentelemetry.instrumentation.bedrock",
    "opentelemetry.instrumentation.llamaindex",
    # The LLM tracer integrations take their tracer under the bare "langflow" name.
    "langflow",
]


@pytest.fixture
def exporter_and_provider():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(ApplicationOnlySpanProcessor(exporter))
    yield exporter, provider
    provider.shutdown()


def exported_span_names(exporter, provider):
    provider.force_flush()
    return [span.name for span in exporter.get_finished_spans()]


@pytest.mark.parametrize("scope", LLM_SCOPES)
def test_llm_scopes_are_not_exported(scope, exporter_and_provider):
    exporter, provider = exporter_and_provider
    span = provider.get_tracer(scope).start_span("chat")
    span.set_attribute("gen_ai.prompt.0.content", SENTINEL)
    span.end()

    assert exported_span_names(exporter, provider) == []


@pytest.mark.parametrize("scope", sorted(APPLICATION_INSTRUMENTATION_SCOPES))
def test_application_scopes_are_exported(scope, exporter_and_provider):
    exporter, provider = exporter_and_provider
    provider.get_tracer(scope).start_span("GET /api/v1/flows").end()

    assert exported_span_names(exporter, provider) == ["GET /api/v1/flows"]


def test_application_and_llm_spans_together_export_only_the_application_span(exporter_and_provider):
    """The realistic case: a traced request that also runs an LLM component."""
    exporter, provider = exporter_and_provider

    server_span = provider.get_tracer("opentelemetry.instrumentation.fastapi").start_span("POST /api/v1/run")
    flow_span = provider.get_tracer(APPLICATION_TRACER_NAME).start_span("flow")
    llm_span = provider.get_tracer("opentelemetry.instrumentation.openai").start_span("openai.chat")
    llm_span.set_attribute("gen_ai.prompt.0.content", SENTINEL)
    llm_span.set_attribute("gen_ai.completion.0.content", SENTINEL)
    llm_span.end()
    flow_span.end()
    server_span.end()

    provider.force_flush()
    finished = exporter.get_finished_spans()
    assert sorted(s.name for s in finished) == ["POST /api/v1/run", "flow"]
    assert SENTINEL not in str([dict(s.attributes or {}) for s in finished])


def test_child_of_a_dropped_span_is_still_exported_and_orphaned(exporter_and_provider):
    """Pins a known consequence rather than asserting it is desirable.

    An outbound call made inside an LLM component still reaches the APM, but its parent
    does not, so the trace renders with a gap. Documented in ApplicationOnlySpanProcessor.
    """
    from opentelemetry.trace import use_span

    exporter, provider = exporter_and_provider
    llm_span = provider.get_tracer("opentelemetry.instrumentation.openai").start_span("openai.chat")
    with use_span(llm_span, end_on_exit=False):
        provider.get_tracer("opentelemetry.instrumentation.httpx").start_span("POST api.openai.com").end()
    llm_span.end()

    provider.force_flush()
    finished = exporter.get_finished_spans()
    assert [s.name for s in finished] == ["POST api.openai.com"]
    exported_ids = {s.context.span_id for s in finished}
    assert finished[0].parent is not None
    assert finished[0].parent.span_id not in exported_ids, "parent should be absent, not silently re-parented"


def test_llm_tracer_name_is_not_allowlisted():
    """The vendor integrations use the bare "langflow" tracer name; ours must differ."""
    assert "langflow" not in APPLICATION_INSTRUMENTATION_SCOPES
    assert APPLICATION_TRACER_NAME in APPLICATION_INSTRUMENTATION_SCOPES
