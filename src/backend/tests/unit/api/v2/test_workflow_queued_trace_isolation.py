"""Use the real stream driver to separate queued absence from ordinary callers."""

from __future__ import annotations

import asyncio
import contextlib
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

pytest.importorskip("opentelemetry.sdk.trace")
pytest.importorskip("opentelemetry.sdk.trace.export.in_memory_span_exporter")

import lfx.observability as obs
from fastapi import BackgroundTasks
from langflow.api.v2 import workflow_execution as wf_exec
from langflow.services import deps
from lfx.graph.graph.base import Graph
from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter
from lfx.workflow.converters import ParsedWorkflowRun
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON


@pytest.fixture
def telemetry(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider(sampler=ALWAYS_ON)
    provider.add_span_processor(obs.ApplicationOnlySpanProcessor(exporter, schedule_delay_millis=100000))
    monkeypatch.setattr(trace, "get_tracer", lambda name, *_args, **_kwargs: provider.get_tracer(name))
    monkeypatch.setattr(deps, "get_telemetry_service", lambda: None)
    monkeypatch.setattr(
        wf_exec, "scoped_model_provider_policy_for_flow", lambda *_args, **_kwargs: contextlib.nullcontext()
    )
    yield provider, provider.get_tracer(obs.APPLICATION_TRACER_NAME), exporter
    provider.shutdown()


def _ended_span(telemetry):
    span = telemetry[1].start_span("earlier.request")
    span.end()
    return span


def _carrier(telemetry):
    origin = telemetry[1].start_span("origin.request")
    with trace.use_span(origin, end_on_exit=False):
        carrier = obs.inject_trace_carrier()
    origin.end()
    return carrier, origin.get_span_context().span_id


def _frames(job_id):
    return wf_exec._stream_event_frames(
        adapter=get_stream_adapter(
            "langflow", StreamAdapterContext(run_id="synthetic-run", thread_id="synthetic-thread")
        ),
        flow_id=uuid4(),
        flow_name="synthetic-flow",
        background_tasks=BackgroundTasks(),
        parsed=ParsedWorkflowRun(flow_id=str(uuid4()), input_value="", mode="stream"),
        current_user=SimpleNamespace(id=uuid4()),
        run_id="synthetic-run",
        job_id=job_id,
        protocol="langflow",
        execution_family="workflow_v2",
        execution_timeout=None,
    )


@pytest.mark.parametrize("kind", ["ordinary", "missing", "invalid", "valid", "lookup-error"])
async def test_actual_driver_queue_intent_and_ended_parent_fallback(monkeypatch, telemetry, kind):
    stale = _ended_span(telemetry)
    carrier, wanted_id = _carrier(telemetry)
    metadata = carrier if kind == "valid" else {obs.JOB_TRACE_CARRIER_KEY: "invalid"} if kind == "invalid" else None
    lookup = AsyncMock(
        return_value=SimpleNamespace(job_metadata=metadata),
        side_effect=RuntimeError("synthetic lookup failure") if kind == "lookup-error" else None,
    )
    monkeypatch.setattr(wf_exec, "get_job_service", lambda: SimpleNamespace(get_job_by_job_id=lookup))
    previous = obs.extract_trace_link(carrier)
    observed = []

    async def generate(**kwargs):
        observed.append((obs.is_queued_trace_context(), obs.get_queued_trace_link()))
        with Graph(flow_id="synthetic-flow").flow_execution_span():
            pass
        await kwargs["event_manager"].queue.put((None, None, time.time()))

    monkeypatch.setattr(wf_exec, "generate_flow_events", generate)
    manager = contextlib.nullcontext() if kind == "ordinary" else obs.queued_trace_link(previous)
    job_id = None if kind == "ordinary" else uuid4()
    with trace.use_span(stale, end_on_exit=False), manager:
        async for _frame, _kind in _frames(job_id):
            pass
        assert obs.get_queued_trace_link() is (None if kind == "ordinary" else previous)
    assert not obs.is_queued_trace_context()
    telemetry[0].force_flush()
    spans = [s for s in telemetry[2].get_finished_spans() if s.name == "flow.execute"]
    assert len(spans) == 1
    assert spans[0].parent is None
    if kind == "ordinary":
        lookup.assert_not_awaited()
        assert observed == [(False, None)]
        assert [item.context.span_id for item in spans[0].links] == [stale.get_span_context().span_id]
    elif kind == "valid":
        lookup.assert_awaited_once_with(job_id)
        assert observed[0][0]
        assert [item.context.span_id for item in spans[0].links] == [wanted_id]
    else:
        lookup.assert_awaited_once_with(job_id)
        assert observed == [(True, None)]
        assert not spans[0].links


@pytest.mark.parametrize("carrier_kind", ["missing", "valid"])
async def test_actual_driver_preserves_live_parent(monkeypatch, telemetry, carrier_kind):
    carrier, _origin = _carrier(telemetry)
    lookup = AsyncMock(return_value=SimpleNamespace(job_metadata=carrier if carrier_kind == "valid" else None))
    monkeypatch.setattr(wf_exec, "get_job_service", lambda: SimpleNamespace(get_job_by_job_id=lookup))

    async def generate(**kwargs):
        with Graph(flow_id="synthetic-flow").flow_execution_span():
            pass
        await kwargs["event_manager"].queue.put((None, None, time.time()))

    monkeypatch.setattr(wf_exec, "generate_flow_events", generate)
    with telemetry[1].start_as_current_span("live.request") as parent:
        async for _frame, _kind in _frames(uuid4()):
            pass
    telemetry[0].force_flush()
    spans = [s for s in telemetry[2].get_finished_spans() if s.name == "flow.execute"]
    assert len(spans) == 1
    assert spans[0].parent.span_id == parent.get_span_context().span_id
    assert not spans[0].links
    assert not obs.is_queued_trace_context()


async def test_lookup_cancellation_propagates_and_restores_inherited_context(monkeypatch, telemetry):
    carrier, _origin = _carrier(telemetry)
    previous = obs.extract_trace_link(carrier)
    entered = asyncio.Event()
    reset_seen = []

    async def lookup(_job_id):
        try:
            entered.set()
            await asyncio.Event().wait()
        finally:
            reset_seen.append(obs.get_queued_trace_link() is previous)

    monkeypatch.setattr(wf_exec, "get_job_service", lambda: SimpleNamespace(get_job_by_job_id=lookup))
    generate = AsyncMock()
    monkeypatch.setattr(wf_exec, "generate_flow_events", generate)

    async def consume():
        async for _frame, _kind in _frames(uuid4()):
            pass

    with obs.queued_trace_link(previous):
        task = asyncio.create_task(consume())
        await asyncio.wait_for(entered.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2)
        assert obs.get_queued_trace_link() is previous
    assert reset_seen == [True]
    assert not obs.is_queued_trace_context()
    generate.assert_not_awaited()
    telemetry[0].force_flush()
    assert not [s for s in telemetry[2].get_finished_spans() if s.name == "flow.execute"]
