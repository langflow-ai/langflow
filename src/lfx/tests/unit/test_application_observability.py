from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
from types import SimpleNamespace
from typing import Any

import pytest

from lfx import application_observability as app


class FakeScope:
    def __init__(self, *, recording: bool = True) -> None:
        self.attributes: dict[str, Any] = {}
        self.error_type: str | None = None
        self.recording = recording

    def is_recording(self) -> bool:
        return self.recording

    def record_error(self, error_type: str) -> None:
        self.error_type = error_type

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value


class SpanRecorder:
    def __init__(self, *, recording: bool = True) -> None:
        self.calls: list[dict[str, Any]] = []
        self.recording = recording

    @contextlib.contextmanager
    def span(self, name: str, attributes: dict[str, Any] | None = None, **kwargs):
        scope = FakeScope(recording=self.recording)
        scope.attributes.update(attributes or {})
        call = {"name": name, "scope": scope, **kwargs}
        self.calls.append(call)
        try:
            yield scope
        except asyncio.CancelledError:
            scope.set_attribute("status", "cancelled")
            raise
        except BaseException as exc:
            scope.record_error(type(exc).__name__)
            raise


def _install_recorder(monkeypatch: pytest.MonkeyPatch, *, recording: bool = True) -> SpanRecorder:
    recorder = SpanRecorder(recording=recording)
    monkeypatch.setattr(app._otel, "application_span", recorder.span)
    monkeypatch.setattr(app._otel, "detached_application_span", recorder.span)
    return recorder


def test_all_requested_span_names_are_owned_by_the_facade():
    assert {
        app.AUTH_SPAN,
        app.FLOW_LOAD_SPAN,
        app.GRAPH_EXECUTION_SPAN,
        app.VERTEX_EXECUTION_SPAN,
        app.RESPONSE_SERIALIZE_SPAN,
        app.STREAM_SEND_SPAN,
        app.JOB_ENQUEUE_SPAN,
        app.JOB_DEQUEUE_SPAN,
        app.JOB_QUEUE_WAIT_SPAN,
        app.JOB_EXECUTE_SPAN,
    } == {
        "langflow.request.auth",
        "langflow.flow.load",
        "langflow.graph.execute",
        "langflow.vertex.execute",
        "langflow.response.serialize",
        "langflow.stream.send",
        "langflow.job.enqueue",
        "langflow.job.dequeue",
        "langflow.job.queue_wait",
        "langflow.job.execute",
    }


def test_component_type_registry_is_bounded_and_cached(monkeypatch):
    app._component_types = None
    known = app._known_component_types()
    assert "ChatInput" in known
    assert app.canonical_component_type("ChatInput") == "ChatInput"
    assert app.canonical_component_type("user-controlled-type") == app.UNKNOWN_COMPONENT_TYPE

    monkeypatch.setattr(app, "files", lambda _package: pytest.fail("registry should be cached"))
    assert app._known_component_types() is known


async def test_auth_decorator_preserves_signature_and_records_success_and_safe_error(monkeypatch):
    recorder = _install_recorder(monkeypatch)

    async def dependency(token: str, *, enabled: bool = True) -> str:
        if not enabled:
            message = "secret must not become telemetry"
            raise ValueError(message)
        return token

    observed = app.observe_auth("test")(dependency)
    assert inspect.signature(observed) == inspect.signature(dependency)
    assert await observed("value") == "value"
    with pytest.raises(ValueError, match="secret"):
        await observed("value", enabled=False)

    assert [call["name"] for call in recorder.calls] == [app.AUTH_SPAN, app.AUTH_SPAN]
    assert recorder.calls[0]["scope"].attributes == {
        "langflow.phase": "request.auth",
        "langflow.auth.surface": "test",
    }
    assert recorder.calls[1]["scope"].error_type == "ValueError"
    assert "secret" not in repr(recorder.calls)


def test_flow_load_decorator_preserves_signature_and_records_only_shape(monkeypatch):
    recorder = _install_recorder(monkeypatch)

    def load(payload: dict, *, instantiate_components: bool = True):
        assert payload["prompt"] == "private"
        assert isinstance(instantiate_components, bool)
        return SimpleNamespace(vertices=[1, 2], edges=[1])

    observed = app.observe_flow_load(load)
    assert inspect.signature(observed) == inspect.signature(load)
    assert len(observed({"prompt": "private"}, instantiate_components=False).vertices) == 2
    attributes = recorder.calls[0]["scope"].attributes
    assert attributes["langflow.graph.vertex_count"] == 2
    assert attributes["langflow.graph.edge_count"] == 1
    assert attributes["langflow.flow.instantiate_components"] is False
    assert "private" not in repr(recorder.calls)


async def test_vertex_decorator_bounds_component_type_and_skips_registry_when_not_recording(monkeypatch):
    class Vertex:
        vertex_type = "workflow-controlled-value"
        is_loop = False

    class Graph:
        def get_vertex(self, _vertex_id):
            return Vertex()

        @app.observe_vertex_execution
        async def build_vertex(self, vertex_id: str, *, value: str = "ok") -> str:
            return f"{vertex_id}:{value}"

    recorder = _install_recorder(monkeypatch)
    monkeypatch.setattr(app, "_known_component_types", lambda: frozenset({"ChatInput"}))
    assert await Graph().build_vertex("node", value="done") == "node:done"
    attributes = recorder.calls[0]["scope"].attributes
    assert attributes["langflow.component.type"] == app.UNKNOWN_COMPONENT_TYPE
    assert "workflow-controlled-value" not in repr(attributes)

    recorder = _install_recorder(monkeypatch, recording=False)
    monkeypatch.setattr(app, "canonical_component_type", lambda _value: pytest.fail("registry should stay cold"))
    assert await Graph().build_vertex("node") == "node:ok"
    assert "langflow.component.type" not in recorder.calls[0]["scope"].attributes


def test_response_serialization_decorator_uses_ambient_protocol(monkeypatch):
    recorder = _install_recorder(monkeypatch)
    monkeypatch.setattr(app._otel, "get_execution_protocol", lambda: "v2")

    @app.observe_response_serialization
    def serialize(value: str) -> str:
        return value.upper()

    assert serialize("ok") == "OK"
    assert recorder.calls[0]["scope"].attributes == {
        "langflow.phase": "response.serialize",
        "protocol": "v2",
    }


@pytest.mark.parametrize("outcome", ["success", "error", "cancel"])
async def test_stream_wrapper_counts_frames_and_preserves_safe_terminal_behavior(monkeypatch, outcome):
    recorder = _install_recorder(monkeypatch)

    async def source():
        yield (b"abc", "event")
        if outcome == "error":
            message = "private frame"
            raise RuntimeError(message)
        if outcome == "cancel":
            raise asyncio.CancelledError
        yield (b"de", "event")

    stream = app.observe_stream_send(
        source(),
        protocol="v2",
        stream_protocol="agui",
        kind="live",
        frame_selector=lambda item: item[0],
    )
    if outcome == "success":
        assert [frame async for frame in stream] == [b"abc", b"de"]
    elif outcome == "error":
        with pytest.raises(RuntimeError, match="private"):
            _ = [frame async for frame in stream]
    else:
        with pytest.raises(asyncio.CancelledError):
            _ = [frame async for frame in stream]

    scope = recorder.calls[0]["scope"]
    assert scope.attributes["langflow.stream.frame_count"] == (2 if outcome == "success" else 1)
    assert scope.attributes["langflow.stream.byte_count"] == (5 if outcome == "success" else 3)
    if outcome == "error":
        assert scope.error_type == "RuntimeError"
    if outcome == "cancel":
        assert scope.attributes["status"] == "cancelled"
    assert "private frame" not in repr(recorder.calls)


async def test_job_helpers_own_producer_consumer_attributes_and_failures(monkeypatch):
    recorder = _install_recorder(monkeypatch)
    monkeypatch.setattr(app, "trace", None)

    async def published() -> str:
        return "queued"

    assert await app.observe_job_enqueue(published(), job_id="job-1", backend="scaled") == "queued"

    async def fails() -> None:
        message = "private job data"
        raise LookupError(message)

    observed = app.observe_queued_job("job-2", fails)
    with pytest.raises(LookupError, match="private"):
        await observed()

    assert [call["name"] for call in recorder.calls] == [
        app.JOB_ENQUEUE_SPAN,
        app.JOB_QUEUE_WAIT_SPAN,
        app.JOB_DEQUEUE_SPAN,
        app.JOB_EXECUTE_SPAN,
    ]
    assert recorder.calls[0]["scope"].attributes["messaging.operation.type"] == "send"
    assert recorder.calls[1]["root"] is True
    assert isinstance(recorder.calls[1]["start_time"], int)
    assert recorder.calls[2]["scope"].attributes["messaging.operation.type"] == "receive"
    assert recorder.calls[3]["scope"].error_type == "LookupError"
    assert "private job data" not in repr(recorder.calls)


async def test_in_process_enqueue_captures_origin_and_cancelled_execution(monkeypatch):
    from opentelemetry.trace import SpanContext, TraceFlags

    recorder = _install_recorder(monkeypatch)
    origin = SpanContext(
        trace_id=1,
        span_id=2,
        is_remote=False,
        trace_flags=TraceFlags(1),
    )
    current = SimpleNamespace(get_span_context=lambda: origin)
    monkeypatch.setattr(app.trace, "get_current_span", lambda: current)

    async def cancelled() -> None:
        raise asyncio.CancelledError

    published = None

    async def publish(operation) -> None:
        nonlocal published
        published = operation

    await app.observe_in_process_job_enqueue("job-cancel", cancelled, publish)
    assert published is not None
    with pytest.raises(asyncio.CancelledError):
        await published()

    enqueue, queue_wait, dequeue, execute = recorder.calls
    assert enqueue["name"] == app.JOB_ENQUEUE_SPAN
    assert enqueue["scope"].attributes["langflow.job.backend"] == "in_process"
    assert queue_wait["links"][0].context == origin
    assert queue_wait["start_time"] <= execute.get("start_time", queue_wait["start_time"])
    assert dequeue["links"][0].context == origin
    assert execute["scope"].attributes["langflow.job.status"] == "cancelled"


async def test_no_otel_path_runs_without_loading_component_registry(monkeypatch):
    recorder = _install_recorder(monkeypatch, recording=False)
    monkeypatch.setattr(app, "trace", None)
    monkeypatch.setattr(app, "canonical_component_type", lambda _value: pytest.fail("registry should stay cold"))

    class Vertex:
        vertex_type = "anything"
        is_loop = False

    class Graph:
        def get_vertex(self, _vertex_id):
            return Vertex()

        @app.observe_vertex_execution
        async def build_vertex(self, vertex_id: str) -> str:
            return vertex_id

    assert await Graph().build_vertex("node") == "node"

    async def work() -> None:
        return None

    await app.observe_queued_job("job", work)()
    assert app.application_span_missing_current() is False
    assert recorder.calls


def test_graph_composite_real_sdk_preserves_current_link_error_and_cancel_semantics(monkeypatch):
    from opentelemetry import trace as otel_trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer(app._otel.APPLICATION_TRACER_NAME)
    monkeypatch.setattr(
        app,
        "trace",
        SimpleNamespace(
            get_tracer=provider.get_tracer,
            get_current_span=otel_trace.get_current_span,
            set_span_in_context=otel_trace.set_span_in_context,
            use_span=otel_trace.use_span,
            Status=otel_trace.Status,
            StatusCode=otel_trace.StatusCode,
        ),
    )
    monkeypatch.setattr(app._otel, "get_queued_trace_link", lambda: None)
    monkeypatch.setattr(app._otel, "get_execution_protocol", lambda: "v2")
    monkeypatch.setattr(app._otel, "get_execution_client", lambda: "sdk")

    class PausedError(Exception):
        pass

    def observed(run_id):
        return app.observe_graph_execution(
            is_subgraph=False,
            make_current=True,
            identifiers=lambda: {"flow_id": "flow", "run_id": run_id, "session_id": None},
            paused_exception=PausedError,
        )

    with tracer.start_as_current_span("caller.current") as caller:
        current_caller = caller.get_span_context().span_id
        with observed("current"), tracer.start_as_current_span("child.current"):
            pass

    with tracer.start_as_current_span("caller.link") as caller:
        linked_caller = caller.get_span_context().span_id
    with otel_trace.use_span(caller, end_on_exit=False), observed("linked"):
        pass

    message = "private graph payload"
    with pytest.raises(ValueError, match="private"), observed("error"):
        raise ValueError(message)

    with pytest.raises(asyncio.CancelledError), observed("cancel"):
        raise asyncio.CancelledError

    with pytest.raises(PausedError), observed("paused"):
        raise PausedError

    with observed("recorded") as observation:
        observation.record_error("LookupError")

    with app.observe_graph_execution(
        is_subgraph=True,
        make_current=True,
        identifiers=dict,
        paused_exception=PausedError,
    ):
        pass

    spans = [
        {
            "name": span.name,
            "span_id": span.context.span_id,
            "parent": span.parent.span_id if span.parent else None,
            "links": [link.context.span_id for link in span.links],
            "attributes": dict(span.attributes or {}),
            "status": span.status.status_code.name,
            "events": [{"name": event.name, "attributes": dict(event.attributes or {})} for event in span.events],
        }
        for span in exporter.get_finished_spans()
    ]

    def run_span(run_id: str, name: str) -> dict:
        return next(span for span in spans if span["name"] == name and span["attributes"].get("run_id") == run_id)

    current_flow = run_span("current", app.LEGACY_FLOW_EXECUTION_SPAN)
    current_graph = run_span("current", app.GRAPH_EXECUTION_SPAN)
    child = next(span for span in spans if span["name"] == "child.current")
    assert current_flow["parent"] == current_caller
    assert current_graph["parent"] == current_flow["span_id"]
    assert child["parent"] == current_graph["span_id"]
    assert current_graph["attributes"]["protocol"] == "v2"
    assert current_graph["attributes"]["client"] == "sdk"

    linked_flow = run_span("linked", app.LEGACY_FLOW_EXECUTION_SPAN)
    linked_graph = run_span("linked", app.GRAPH_EXECUTION_SPAN)
    assert linked_flow["parent"] is None
    assert linked_flow["links"] == [linked_caller]
    assert linked_graph["parent"] == linked_flow["span_id"]

    for name in (app.LEGACY_FLOW_EXECUTION_SPAN, app.GRAPH_EXECUTION_SPAN):
        error = run_span("error", name)
        assert error["status"] == "ERROR"
        assert error["attributes"]["error.type"] == "ValueError"
        assert error["events"] == [{"name": "exception", "attributes": {"exception.type": "ValueError"}}]

        cancelled = run_span("cancel", name)
        assert cancelled["status"] == "UNSET"
        assert cancelled["attributes"]["status"] == "cancelled"
        assert cancelled["events"] == []

    assert run_span("paused", app.GRAPH_EXECUTION_SPAN)["attributes"]["status"] == "paused"
    recorded = run_span("recorded", app.GRAPH_EXECUTION_SPAN)
    assert recorded["status"] == "ERROR"
    assert recorded["attributes"]["error.type"] == "LookupError"

    assert "private graph payload" not in json.dumps(spans)
