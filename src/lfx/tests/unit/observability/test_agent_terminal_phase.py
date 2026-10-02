"""Actual processor terminal phase outcomes and serialized application metrics privacy."""

import ast
import asyncio
import inspect
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("opentelemetry.sdk.metrics")
pytest.importorskip("opentelemetry.exporter.otlp.proto.common.metrics_encoder")
from lfx.base.agents import events as hooked_events
from lfx.observability import APPLICATION_TRACER_NAME, ApplicationOnlyMetricExporter
from lfx.schema.message import Message
from opentelemetry.exporter.otlp.proto.common.metrics_encoder import encode_metrics
from opentelemetry.sdk.metrics import MeterProvider, TraceBasedExemplarFilter
from opentelemetry.sdk.metrics.export import InMemoryMetricReader, MetricExportResult
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.sampling import ALWAYS_ON

from lfx import observability_phase as phase


@pytest.fixture
def processors():
    source = ast.parse(inspect.getsource(hooked_events))

    class RemoveTiming(ast.NodeTransformer):
        count = 0

        def visit_ImportFrom(self, node):
            return None if node.module == "lfx.observability_phase" else node

        def visit_With(self, node):
            self.generic_visit(node)
            call = node.items[0].context_expr if len(node.items) == 1 else None
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "measure_phase":
                self.count += 1
                return node.body
            return node

    transform = RemoveTiming()
    source = transform.visit(source)
    assert transform.count == 1
    control = ModuleType("terminal_phase_control")
    exec(  # noqa: S102 - compile only inspected repository control source
        compile(ast.fix_missing_locations(source), "<terminal-control>", "exec"), control.__dict__
    )
    return {"control": control, "hooked": hooked_events}


@pytest.fixture
def capture(monkeypatch):
    reader = InMemoryMetricReader()
    provider = MeterProvider(
        resource=Resource({"service.name": "test"}), metric_readers=[reader], exemplar_filter=TraceBasedExemplarFilter()
    )
    monkeypatch.setattr(phase.metrics, "get_meter", provider.get_meter)
    original_instruments = phase._instruments
    original_instruments.cache_clear()
    yield reader
    original_instruments.cache_clear()
    provider.shutdown()


def data_points(reader):
    data = reader.get_metrics_data()
    if data is None:
        return []
    return [
        (scope.scope.name, metric.name, point)
        for resource in data.resource_metrics
        for scope in resource.scope_metrics
        for metric in scope.metrics
        for point in metric.data.data_points
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("ending", ["normal", "early_complete", "pause", "error"])
async def test_both_processor_callbacks_match_control_without_duplicate_terminal_metrics(capture, processors, ending):
    from langchain_classic.schema import AgentFinish
    from lfx.schema.message import Message
    from lfx.schema.properties import Usage

    usage = Usage(input_tokens=3, output_tokens=4, total_tokens=7)

    async def perform(*, observe):
        snapshots = []

        async def events():
            if ending == "error":
                failure_text = "private failure"
                raise RuntimeError(failure_text)
            if ending == "early_complete":
                yield {
                    "event": "on_chain_end",
                    "data": {"output": AgentFinish(return_values={"output": "answer"}, log="")},
                }

        async def callback(*, message, **_kwargs):
            message.id = "test-id"
            snapshots.append((message.properties.state, message.text, message.properties.usage))
            return message

        async def pending():
            return {"action_requests": []} if ending == "pause" else None

        stream = events()
        processor = processors["hooked" if observe else "control"]
        message = Message(text="answer")
        message.properties.usage = usage
        try:
            result = await processor.process_agent_events(stream, message, callback, get_pending_interrupt=pending)
        except (processor.AgentPausedError, processor.ExceptionWithMessageError) as error:
            return snapshots, type(error).__name__
        else:
            return snapshots, (result.text, result.properties.usage)
        finally:
            await stream.aclose()

    control = await perform(observe=False)
    observed = await perform(observe=True)
    assert control == observed
    points = data_points(capture)
    if ending in {"error", "pause"}:
        assert points == []
    else:
        assert len(points) == 1
        assert points[0][2].count == 1
        assert points[0][2].attributes["outcome"] == "ok"


@pytest.mark.asyncio
async def test_cancelled_processor_closes_source_without_successful_final_metric(capture, processors):
    from lfx.schema.message import Message

    entered = asyncio.Event()
    closed = []

    async def events():
        try:
            entered.set()
            await asyncio.Event().wait()
            yield {"event": "unused"}
        finally:
            closed.append(True)

    async def callback(**kwargs):
        return kwargs["message"]

    stream = events()
    processor = processors["hooked"]

    async def run():
        try:
            await processor.process_agent_events(stream, Message(text="answer"), callback)
        finally:
            await stream.aclose()

    task = asyncio.create_task(run())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed == [True]
    assert data_points(capture) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("ending", ["error", "cancel"])
async def test_failed_terminal_callback_never_records_success(capture, processors, ending):
    from lfx.schema.message import Message

    entered = asyncio.Event()

    async def events():
        for event in ():
            yield event

    async def callback(*, message, **_kwargs):
        if message.properties.state == "complete":
            entered.set()
            if ending == "error":
                failure_text = "private final persistence failure"
                raise RuntimeError(failure_text)
            await asyncio.Event().wait()
        return message

    stream = events()
    processor = processors["hooked"]

    async def run():
        try:
            await processor.process_agent_events(stream, Message(text="answer"), callback)
        finally:
            await stream.aclose()

    task = asyncio.create_task(run())
    await entered.wait()
    if ending == "cancel":
        task.cancel()
    with pytest.raises(asyncio.CancelledError if ending == "cancel" else processor.ExceptionWithMessageError):
        await task
    points = data_points(capture)
    assert len(points) == 1
    assert points[0][2].attributes["outcome"] == ("cancelled" if ending == "cancel" else "error")


async def empty_events():
    for event in ():
        yield event


async def callback(*, message, **_kwargs):
    message.id = "owned-test-id"
    return message


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", ["pending", "usage"])
async def test_preterminal_getter_failure_never_emits_terminal_record(capture, processors, boundary):
    failure = RuntimeError("owned getter failure")
    for processor in processors.values():
        if (
            boundary == "usage"
            and "get_final_usage" not in inspect.signature(processor.process_agent_events).parameters
        ):
            pytest.skip("normalcff has no final usage getter")

        async def pending():
            raise failure

        def usage():
            raise failure

        kwargs = {"get_pending_interrupt": pending} if boundary == "pending" else {"get_final_usage": usage}
        with pytest.raises(processor.ExceptionWithMessageError) as caught:
            await processor.process_agent_events(empty_events(), Message(text="answer"), callback, **kwargs)
        assert caught.value.__cause__ is failure
    assert data_points(capture) == []


@pytest.mark.asyncio
async def test_failure_after_terminal_return_does_not_change_callback_outcome(capture, processors, monkeypatch):
    failure = RuntimeError("later message construction failed")
    create = AsyncMock(side_effect=failure)
    monkeypatch.setattr(Message, "create", create)
    for processor in processors.values():
        with pytest.raises(RuntimeError, match="later message construction failed") as caught:
            await processor.process_agent_events(empty_events(), Message(text="answer"), callback)
        assert caught.value is failure
    points = data_points(capture)
    assert len(points) == 1
    assert points[0][2].count == 1
    assert points[0][2].attributes == {"phase": "final_send", "outcome": "ok"}
    assert create.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("availability", ["absent", "sdk_failure"])
async def test_missing_or_failing_telemetry_preserves_real_processor(capture, processors, monkeypatch, availability):
    phase._instruments.cache_clear()
    if availability == "absent":
        monkeypatch.setattr(phase, "metrics", None)
    else:

        def fail():
            failure_text = "owned SDK failure"
            raise RuntimeError(failure_text)

        monkeypatch.setattr(phase, "_instruments", fail)
    results = []
    for processor in processors.values():
        message = await processor.process_agent_events(empty_events(), Message(text="answer"), callback)
        results.append((message.text, message.id, message.properties.state))
    assert results[0] == results[1]
    assert data_points(capture) == []


@pytest.mark.asyncio
async def test_actual_otlp_metrics_export_has_no_message_or_flow_payload(capture, processors):
    sentinel = "PROMPT-SQL-URL-OUTPUT-SENTINEL"
    tracer_provider = TracerProvider(resource=Resource({"service.name": "test"}), sampler=ALWAYS_ON)
    tracer = tracer_provider.get_tracer(APPLICATION_TRACER_NAME)
    try:
        with tracer.start_as_current_span(
            "flow.execute", record_exception=False, set_status_on_exception=False
        ) as span:
            span.set_attribute("flow_id", "FLOW-SENTINEL")
            span.set_attribute("session_id", "SESSION-SENTINEL")
            span.set_attribute("test_payload", sentinel)
            await processors["hooked"].process_agent_events(empty_events(), Message(text=sentinel), callback)
            span_context = span.get_span_context()
        forwarded = []
        exporter = SimpleNamespace(
            _preferred_temporality=None,
            _preferred_aggregation=None,
            export=lambda data, *_a, **_k: forwarded.append(data) or MetricExportResult.SUCCESS,
        )
        assert ApplicationOnlyMetricExporter(exporter).export(capture.get_metrics_data()) is MetricExportResult.SUCCESS
        assert len(forwarded) == 1
        payload = encode_metrics(forwarded[0])
        wire = payload.SerializeToString()
        assert all(
            value.encode() not in wire for value in (sentinel, "FLOW-SENTINEL", "SESSION-SENTINEL", "owned-test-id")
        )
        exemplars = []
        for resource in forwarded[0].resource_metrics:
            for scope in resource.scope_metrics:
                assert scope.scope.name == "langflow"
                for metric in scope.metrics:
                    assert metric.name == "langflow.agent.phase.duration"
                    assert metric.unit == "s"
                    for point in metric.data.data_points:
                        assert point.attributes == {"phase": "final_send", "outcome": "ok"}
                        assert tuple(point.explicit_bounds) == phase.WALL_BUCKETS_SECONDS
                        exemplars.extend(point.exemplars)
        assert exemplars
        assert all(x.trace_id == span_context.trace_id and x.span_id == span_context.span_id for x in exemplars)
        assert all(not x.filtered_attributes for x in exemplars)
    finally:
        tracer_provider.shutdown()
