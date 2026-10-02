"""Queued absence must not inherit a previous job or ended request."""

from __future__ import annotations

import asyncio
import contextlib

import pytest

pytest.importorskip("opentelemetry.sdk.trace")
pytest.importorskip("opentelemetry.sdk.trace.export.in_memory_span_exporter")
pytest.importorskip("opentelemetry.exporter.otlp.proto.common.trace_encoder")

import lfx.graph.graph.base as graphmod
import lfx.observability as obs
from lfx.graph.exceptions import GraphPausedException
from lfx.graph.graph.base import Graph
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON

SENTINEL = "synthetic-private-body-sql-url-sentinel"


@pytest.fixture
def telemetry(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider(sampler=ALWAYS_ON)
    provider.add_span_processor(obs.ApplicationOnlySpanProcessor(exporter, schedule_delay_millis=100000))
    monkeypatch.setattr(trace, "get_tracer", lambda name, *_args, **_kwargs: provider.get_tracer(name))
    tracer = provider.get_tracer(obs.APPLICATION_TRACER_NAME)
    yield provider, tracer, exporter
    provider.shutdown()


def flows(t):
    provider, _tracer, exporter = t
    provider.force_flush()
    return [s for s in exporter.get_finished_spans() if s.name == "flow.execute"]


def link(t):
    origin = t[1].start_span("queued.origin")
    origin.end()
    return trace.Link(origin.get_span_context())


def stale(t):
    span = t[1].start_span("earlier.request")
    span.end()
    return span


def run():
    with Graph(flow_id="test-flow").flow_execution_span():
        pass


def assert_root(span):
    assert span.parent is None
    assert not span.links


def test_sequential_jobs_and_nested_explicit_none_clear_inherited_link(telemetry):
    carrier = link(telemetry)
    old = stale(telemetry)
    with trace.use_span(old, end_on_exit=False):
        with obs.queued_trace_link(carrier):
            run()
            with obs.queued_trace_link(None):
                assert obs.is_queued_trace_context()
                assert obs.get_queued_trace_link() is None
                run()
            assert obs.get_queued_trace_link() is carrier
            run()
        assert not obs.is_queued_trace_context()
        run()
    a, b, c, d = flows(telemetry)
    assert [item.context.span_id for item in a.links] == [carrier.context.span_id]
    assert_root(b)
    assert [item.context.span_id for item in c.links] == [carrier.context.span_id]
    assert [item.context.span_id for item in d.links] == [old.get_span_context().span_id]
    assert all(s.parent is None for s in (a, c, d))


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        {},
        {"otel_traceparent": ""},
        {"otel_traceparent": "invalid"},
        {"otel_traceparent": 123},
        {"otel_traceparent": "00-" + "0" * 32 + "-" + "0" * 16 + "-01"},
    ],
)
def test_missing_invalid_carrier_is_explicit_unlinked_root(telemetry, metadata):
    carrier = obs.extract_trace_link(metadata)
    assert carrier is None
    with trace.use_span(stale(telemetry), end_on_exit=False), obs.queued_trace_link(carrier):
        run()
    result = flows(telemetry)
    assert len(result) == 1
    assert_root(result[0])


@pytest.mark.parametrize("queued", ["absent", "valid", "outside"])
def test_live_parent_wins_unchanged(telemetry, queued):
    q = link(telemetry)
    with telemetry[1].start_as_current_span(
        "live.request", record_exception=False, set_status_on_exception=False
    ) as parent:
        manager = (
            contextlib.nullcontext() if queued == "outside" else obs.queued_trace_link(q if queued == "valid" else None)
        )
        with manager:
            run()
    result = flows(telemetry)
    assert len(result) == 1
    assert result[0].parent.span_id == parent.get_span_context().span_id
    assert not result[0].links


def test_valid_carrier_wins_over_ended_parent(telemetry):
    q = link(telemetry)
    old = stale(telemetry)
    with trace.use_span(old, end_on_exit=False), obs.queued_trace_link(q):
        run()
    result = flows(telemetry)
    assert len(result) == 1
    assert result[0].parent is None
    assert [item.context.span_id for item in result[0].links] == [q.context.span_id]


def test_valid_metadata_extract_and_no_current_parent(telemetry):
    origin = telemetry[1].start_span("origin")
    with trace.use_span(origin, end_on_exit=False):
        carrier = obs.inject_trace_carrier()
    origin.end()
    q = obs.extract_trace_link(carrier)
    assert q is not None
    with obs.queued_trace_link(q):
        run()
    result = flows(telemetry)
    assert len(result) == 1
    assert result[0].parent is None
    assert result[0].links[0].context.span_id == origin.get_span_context().span_id


@pytest.mark.parametrize("error_kind", ["error", "cancel", "pause"])
def test_exception_cancel_pause_token_reset_status_and_privacy(telemetry, error_kind):
    q = link(telemetry)
    old = stale(telemetry)
    error = (
        ValueError(SENTINEL)
        if error_kind == "error"
        else asyncio.CancelledError(SENTINEL)
        if error_kind == "cancel"
        else GraphPausedException(checkpoint_id="synthetic-checkpoint", reason=SENTINEL)
    )
    before = trace.get_current_span()
    with trace.use_span(old, end_on_exit=False), obs.queued_trace_link(q):
        with (
            pytest.raises(type(error)) as caught,
            obs.queued_trace_link(None),
            Graph(flow_id="test-flow").flow_execution_span(),
        ):
            raise error
        assert caught.value is error
        assert obs.get_queued_trace_link() is q
        assert trace.get_current_span() is old
    assert not obs.is_queued_trace_context()
    assert trace.get_current_span() is before
    result = flows(telemetry)
    assert len(result) == 1
    assert_root(result[0])
    expected = {"error": "error", "cancel": "cancelled", "pause": "paused"}[error_kind]
    assert result[0].attributes["status"] == expected
    assert result[0].status.status_code.name == ("ERROR" if error_kind == "error" else "UNSET")
    assert not result[0].events
    assert SENTINEL.encode() not in encode_spans(result).SerializeToString()


@pytest.mark.asyncio
async def test_copied_task_context_none_is_local_and_resets_on_cancellation(telemetry):
    q = link(telemetry)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def worker():
        assert obs.get_queued_trace_link() is q
        try:
            with obs.queued_trace_link(None), Graph(flow_id="test-flow").flow_execution_span():
                entered.set()
                await release.wait()
        finally:
            assert obs.get_queued_trace_link() is q

    with obs.queued_trace_link(q):
        task = asyncio.create_task(worker())
        await entered.wait()
        assert obs.get_queued_trace_link() is q
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert obs.get_queued_trace_link() is q
    assert not obs.is_queued_trace_context()
    result = flows(telemetry)
    assert len(result) == 1
    assert_root(result[0])
    assert result[0].attributes["status"] == "cancelled"


def test_no_sdk_context_reset_without_spans(telemetry, monkeypatch):
    monkeypatch.setattr(graphmod, "otel_trace", None)
    monkeypatch.setattr(obs, "_OTEL_AVAILABLE", False)
    assert obs.extract_trace_link({"otel_traceparent": SENTINEL}) is None
    with obs.queued_trace_link(None):
        assert obs.is_queued_trace_context()
        run()
    assert not obs.is_queued_trace_context()
    assert flows(telemetry) == []


def test_regression_absent_job_does_not_link_to_stale_ended_request(telemetry):
    with trace.use_span(stale(telemetry), end_on_exit=False), obs.queued_trace_link(None):
        run()
    result = flows(telemetry)
    assert len(result) == 1
    assert_root(result[0])


def test_regression_absent_job_does_not_inherit_old_queued_link(telemetry):
    previous = link(telemetry)
    with obs.queued_trace_link(previous), obs.queued_trace_link(None):
        run()
    result = flows(telemetry)
    assert len(result) == 1
    assert_root(result[0])
