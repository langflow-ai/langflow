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


def test_child_of_a_dropped_span_is_promoted_to_a_root(exporter_and_provider):
    """A sub-flow run from inside an agent component, with nothing exported above it.

    The dropped LLM span was its only ancestor, so there is nothing left to hang it from and
    it becomes a root. Previously it kept pointing at the dropped parent and arrived at the
    APM referencing a span that never showed up.
    """
    from opentelemetry.trace import use_span

    exporter, provider = exporter_and_provider
    llm_span = provider.get_tracer("opentelemetry.instrumentation.openai").start_span("openai.chat")
    with use_span(llm_span, end_on_exit=False):
        provider.get_tracer(APPLICATION_TRACER_NAME).start_span("flow.execute").end()
    llm_span.end()

    provider.force_flush()
    finished = exporter.get_finished_spans()
    assert [s.name for s in finished] == ["flow.execute"]
    assert finished[0].parent is None, "should be a root, not pointing at a span that was never exported"


def test_child_of_a_dropped_span_is_reparented_to_its_nearest_exported_ancestor(exporter_and_provider):
    """The case that actually renders as a tree: an exported ancestor exists above the drop.

    request -> openai.chat (dropped) -> flow.execute. The middle span never reaches the APM,
    so flow.execute has to attach to the request or the trace has a hole in it.
    """
    from opentelemetry.trace import use_span

    exporter, provider = exporter_and_provider
    request = provider.get_tracer(APPLICATION_TRACER_NAME).start_span("POST /api/v1/run")
    with use_span(request, end_on_exit=False):
        llm_span = provider.get_tracer("opentelemetry.instrumentation.openai").start_span("openai.chat")
        with use_span(llm_span, end_on_exit=False):
            provider.get_tracer(APPLICATION_TRACER_NAME).start_span("flow.execute").end()
        llm_span.end()
    request.end()

    provider.force_flush()
    by_name = {s.name: s for s in exporter.get_finished_spans()}
    assert sorted(by_name) == ["POST /api/v1/run", "flow.execute"]
    assert by_name["flow.execute"].parent is not None
    assert by_name["flow.execute"].parent.span_id == by_name["POST /api/v1/run"].context.span_id
    # Same trace throughout: this moves a span within its tree, it does not relocate it.
    assert by_name["flow.execute"].context.trace_id == by_name["POST /api/v1/run"].context.trace_id


def test_a_span_under_two_dropped_levels_still_finds_the_exported_ancestor(exporter_and_provider):
    """The walk has to continue past the first dropped parent, not stop at it."""
    from opentelemetry.trace import use_span

    exporter, provider = exporter_and_provider
    request = provider.get_tracer(APPLICATION_TRACER_NAME).start_span("POST /api/v1/run")
    with use_span(request, end_on_exit=False):
        outer = provider.get_tracer("opentelemetry.instrumentation.openai").start_span("openai.chat")
        with use_span(outer, end_on_exit=False):
            inner = provider.get_tracer("opentelemetry.instrumentation.requests").start_span("HTTP POST")
            with use_span(inner, end_on_exit=False):
                provider.get_tracer(APPLICATION_TRACER_NAME).start_span("flow.execute").end()
            inner.end()
        outer.end()
    request.end()

    provider.force_flush()
    by_name = {s.name: s for s in exporter.get_finished_spans()}
    assert sorted(by_name) == ["POST /api/v1/run", "flow.execute"]
    assert by_name["flow.execute"].parent.span_id == by_name["POST /api/v1/run"].context.span_id


def test_a_real_parent_is_left_alone(exporter_and_provider):
    """The control. Nothing was dropped, so nothing should be rewritten."""
    from opentelemetry.trace import use_span

    exporter, provider = exporter_and_provider
    request = provider.get_tracer(APPLICATION_TRACER_NAME).start_span("POST /api/v1/run")
    with use_span(request, end_on_exit=False):
        provider.get_tracer(APPLICATION_TRACER_NAME).start_span("flow.execute").end()
    request.end()

    provider.force_flush()
    by_name = {s.name: s for s in exporter.get_finished_spans()}
    assert by_name["flow.execute"].parent.span_id == by_name["POST /api/v1/run"].context.span_id


@pytest.mark.parametrize(
    "scope",
    [
        "opentelemetry.instrumentation.requests",
        "opentelemetry.instrumentation.urllib3",
        "opentelemetry.instrumentation.httpx",
    ],
)
def test_outbound_http_client_scopes_are_not_allowlisted(scope):
    """The LLM vendor SDKs instrument these globally, so they carry outbound LLM API calls.

    traceloop-sdk calls RequestsInstrumentor().instrument() and the urllib3/httpx equivalents
    with no tracer_provider, which binds them to our global provider. Allowlisting them would
    produce one span per outbound LLM call, carrying the request URL, and provider keys passed
    as query parameters would travel with it. httpx especially: it is the transport the openai
    and anthropic SDKs use. The runtime's own uses pass tracer_provider= explicitly.
    """
    assert scope not in APPLICATION_INSTRUMENTATION_SCOPES


def test_globally_instrumented_requests_does_not_reach_the_apm(exporter_and_provider):
    """Drives the real RequestsInstrumentor the way traceloop-sdk does, against a local server."""
    import http.server
    import socketserver
    import threading

    import requests
    from opentelemetry.instrumentation.requests import RequestsInstrumentor

    exporter, provider = exporter_and_provider

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args):
            pass

    server = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    instrumentor = RequestsInstrumentor()
    was_instrumented = instrumentor.is_instrumented_by_opentelemetry
    if not was_instrumented:
        # No tracer_provider, exactly as traceloop-sdk does it: binds to the global provider.
        instrumentor.instrument(tracer_provider=provider)
    try:
        requests.get(f"http://127.0.0.1:{port}/v1beta/models/gemini:generateContent?key={SENTINEL}", timeout=10)
    finally:
        if not was_instrumented:
            instrumentor.uninstrument()
        server.shutdown()

    assert exported_span_names(exporter, provider) == [], "outbound LLM API call reached the APM"


def test_llm_tracer_name_is_not_allowlisted():
    """The vendor integrations use the bare "langflow" tracer name; ours must differ."""
    assert "langflow" not in APPLICATION_INSTRUMENTATION_SCOPES
    assert APPLICATION_TRACER_NAME in APPLICATION_INSTRUMENTATION_SCOPES


def test_a_remote_parent_is_never_rewritten():
    """The safety case. An unknown parent is not evidence of a drop.

    A parent from another process is absent from this processor's map for the same reason a
    dropped one is: it was never seen at on_start. Treating absence as a drop would detach
    every distributed trace from its caller and re-root it here, replacing a correct
    cross-process link with an invented local one.
    """
    from opentelemetry import trace as otel_trace
    from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(ApplicationOnlySpanProcessor(exporter))

    remote = SpanContext(
        trace_id=0x1234567890ABCDEF1234567890ABCDEF,
        span_id=0x1122334455667788,
        is_remote=True,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )
    context = otel_trace.set_span_in_context(NonRecordingSpan(remote))
    provider.get_tracer(APPLICATION_TRACER_NAME).start_span("flow.execute", context=context).end()

    provider.force_flush()
    exported = exporter.get_finished_spans()
    assert len(exported) == 1
    assert exported[0].parent is not None, "a remote parent must survive; it is not an orphan"
    assert exported[0].parent.span_id == remote.span_id
    provider.shutdown()


def test_a_remote_parent_above_a_dropped_span_is_preserved():
    """A dropped local span must not sever an incoming distributed trace."""
    from opentelemetry import trace as otel_trace
    from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags, use_span

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(ApplicationOnlySpanProcessor(exporter))

    remote = SpanContext(
        trace_id=0x1234567890ABCDEF1234567890ABCDEF,
        span_id=0x1122334455667788,
        is_remote=True,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )
    context = otel_trace.set_span_in_context(NonRecordingSpan(remote))
    dropped = provider.get_tracer("opentelemetry.instrumentation.openai").start_span("openai.chat", context=context)
    with use_span(dropped, end_on_exit=False):
        provider.get_tracer(APPLICATION_TRACER_NAME).start_span("flow.execute").end()
    dropped.end()

    provider.force_flush()
    exported = exporter.get_finished_spans()
    assert len(exported) == 1
    assert exported[0].parent is not None
    assert exported[0].parent.span_id == remote.span_id
    assert exported[0].context.trace_id == remote.trace_id
    provider.shutdown()


def test_the_lineage_map_does_not_grow_across_runs():
    """Entries are removed as spans end, including the dropped ones.

    The map is the only state this processor keeps, so an entry that outlives its span is a
    leak in a long-running server.
    """
    from opentelemetry.trace import use_span

    exporter = InMemorySpanExporter()
    processor = ApplicationOnlySpanProcessor(exporter)
    provider = TracerProvider()
    provider.add_span_processor(processor)

    for _ in range(25):
        request = provider.get_tracer(APPLICATION_TRACER_NAME).start_span("POST /api/v1/run")
        with use_span(request, end_on_exit=False):
            llm = provider.get_tracer("opentelemetry.instrumentation.openai").start_span("openai.chat")
            with use_span(llm, end_on_exit=False):
                provider.get_tracer(APPLICATION_TRACER_NAME).start_span("flow.execute").end()
            llm.end()
        request.end()

    provider.force_flush()
    assert processor._lineage == {}, f"{len(processor._lineage)} entries left behind"
    provider.shutdown()


def test_a_failure_while_reparenting_does_not_break_the_run():
    """Telemetry must not raise into the code that ended the span.

    The SDK does not catch exceptions from a span processor: it lets them out of
    ``Span.end()`` and into the caller. Re-parenting reaches into SDK internals, so if a
    future release changes them, the failure has to stay inside the processor. The span is
    still exported, with whatever parent it already had.

    Corrupts the processor's own lineage map rather than patching the SDK, so the failure is
    raised by the real code path under test.
    """
    from opentelemetry.trace import use_span

    exporter = InMemorySpanExporter()
    processor = ApplicationOnlySpanProcessor(exporter)
    provider = TracerProvider()
    provider.add_span_processor(processor)

    request = provider.get_tracer(APPLICATION_TRACER_NAME).start_span("POST /api/v1/run")
    with use_span(request, end_on_exit=False):
        llm = provider.get_tracer("opentelemetry.instrumentation.openai").start_span("openai.chat")
        with use_span(llm, end_on_exit=False):
            child = provider.get_tracer(APPLICATION_TRACER_NAME).start_span("flow.execute")
            # The walk unpacks each entry as (exported, parent_id, context). A short tuple
            # raises there, which is what a changed SDK looks like from inside this code.
            # It has to be falsy in position 0 too, or the caller returns before the walk.
            processor._lineage[llm.get_span_context().span_id] = (False,)
            child.end()  # must not raise
        llm.end()
    request.end()

    provider.force_flush()
    exported = [s for s in exporter.get_finished_spans() if s.name == "flow.execute"]
    assert len(exported) == 1, "the span must still be exported when re-parenting fails"
    provider.shutdown()
