"""A Loop's per-iteration subgraphs must reuse the parent run's trace.

Each iteration runs the loop body in a subgraph that shares the parent's TracingService and run id.
The parent owns the trace lifecycle, so a subgraph must neither start nor end tracers: a started-but-
never-ended TraceContext leaks a worker task, drops the loop-body spans, and leaves trace_context_var
pointing at the orphan so spans built after the Loop are lost too.

These tests use the real TracingService and the real NativeTracer writing to the test database. Only
the optional vendor integrations are disabled.
"""

import asyncio
import contextlib
import json
from collections import Counter
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.traces.model import SpanStatus, SpanTable, TraceTable
from langflow.services.tracing.service import TracingService, trace_context_var
from lfx.graph.flow_builder.builder import build_flow_from_spec
from lfx.graph.graph.base import Graph
from lfx.services.deps import session_scope
from sqlmodel import select

from tests.unit.build_utils import build_flow, create_flow, get_build_events

ITEMS = ["first", "second", "third", "fourth", "fifth"]

LOOP_SPEC = """\
name: Loop Trace
nodes:
  CL: CreateList
  L: LoopComponent
  P: ParserComponent
  TC: TypeConverterComponent
  POST: ParserComponent
  O: ChatOutput
edges:
  CL.list -> L.data
  L.item -> P.input_data
  P.parsed_text -> TC.input_data
  TC.data_output -> L.item
  L.done -> POST.input_data
  POST.parsed_text -> O.input_value
config:
  P.mode: Stringify
  TC.output_type: JSON
  POST.mode: Stringify
"""

NESTED_LOOP_SPEC = """\
name: Nested Loop Trace
nodes:
  CL: CreateList
  OUTER: LoopComponent
  INNER: LoopComponent
  P: ParserComponent
  INNER_TC: TypeConverterComponent
  OUTER_TC: TypeConverterComponent
  POST: ParserComponent
  O: ChatOutput
edges:
  CL.list -> OUTER.data
  OUTER.item -> INNER.data
  INNER.item -> P.input_data
  P.parsed_text -> INNER_TC.input_data
  INNER_TC.data_output -> INNER.item
  INNER.done -> OUTER_TC.input_data
  OUTER_TC.data_output -> OUTER.item
  OUTER.done -> POST.input_data
  POST.parsed_text -> O.input_value
config:
  P.mode: Stringify
  INNER_TC.output_type: JSON
  OUTER_TC.output_type: JSON
  POST.mode: Stringify
"""


class TracerLifecycle:
    """Records the start/end calls and TraceContexts of a real TracingService."""

    def __init__(self, service: TracingService, monkeypatch: pytest.MonkeyPatch) -> None:
        self.service = service
        self.contexts: list = []
        self.end_calls: list[Exception | None] = []
        start, end = service.start_tracers, service.end_tracers

        async def start_tracers(**kwargs):
            await start(**kwargs)
            self.contexts.append(trace_context_var.get())

        async def end_tracers(outputs, error=None):
            self.end_calls.append(error)
            await end(outputs, error)

        monkeypatch.setattr(service, "start_tracers", start_tracers)
        monkeypatch.setattr(service, "end_tracers", end_tracers)


def _pending_trace_workers(contexts: list) -> list[asyncio.Task]:
    """Unfinished worker tasks serving one of the given TraceContexts."""
    pending = []
    for task in asyncio.all_tasks():
        coro = task.get_coro()
        frame = getattr(coro, "cr_frame", None)
        if task.done() or frame is None or not coro.__qualname__.endswith("_trace_worker"):
            continue
        if any(frame.f_locals.get("trace_context") is context for context in contexts):
            pending.append(task)
    return pending


def _node_template(built: dict, node: str) -> dict:
    node_id = built["node_id_map"][node]
    return next(n for n in built["flow"]["data"]["nodes"] if n["id"] == node_id)["data"]["node"]["template"]


def _build(spec: str) -> dict:
    built = build_flow_from_spec(spec)
    assert "flow" in built, built
    _node_template(built, "CL")["texts"]["value"] = ITEMS
    return built


def _graph(built: dict, flow_id: str) -> Graph:
    return Graph.from_payload(built["flow"], flow_id=flow_id, flow_name="Loop Trace", user_id=str(uuid4()))


def _flow_payload(built: dict) -> str:
    return json.dumps({"name": f"Loop Trace {uuid4()}", "data": built["flow"]["data"]})


def _native_only(service: TracingService, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("langsmith", "langwatch", "langfuse", "arize_phoenix", "opik", "traceloop", "openlayer"):
        monkeypatch.setattr(service, f"_initialize_{name}_tracer", lambda _context: None)
    monkeypatch.setenv("LANGFLOW_NATIVE_TRACING", "true")


@pytest.fixture
def lifecycle(monkeypatch) -> TracerLifecycle:
    service = TracingService(SimpleNamespace(settings=SimpleNamespace(deactivate_tracing=False)))
    _native_only(service, monkeypatch)
    monkeypatch.setattr("lfx.services.deps.get_tracing_service", lambda: service)
    monkeypatch.setattr("lfx.graph.graph.base.get_tracing_service", lambda: service)
    return TracerLifecycle(service, monkeypatch)


@pytest.fixture
def deactivate_tracing(monkeypatch):
    """Overrides the suite-wide autouse fixture: the app under test must trace for real."""
    monkeypatch.setenv("LANGFLOW_DEACTIVATE_TRACING", "false")
    yield
    monkeypatch.undo()


@pytest.fixture
def app_lifecycle(client, monkeypatch) -> TracerLifecycle:  # noqa: ARG001 - the app must be up first
    from lfx.services.deps import get_tracing_service

    service = get_tracing_service()
    assert isinstance(service, TracingService)
    assert not service.deactivated
    _native_only(service, monkeypatch)
    return TracerLifecycle(service, monkeypatch)


@pytest.fixture
def local_db(async_session, monkeypatch):
    @contextlib.asynccontextmanager
    async def local_session_scope():
        try:
            yield async_session
            await async_session.commit()
        except Exception:
            await async_session.rollback()
            raise

    monkeypatch.setattr("lfx.services.deps.session_scope", local_session_scope)
    return async_session


async def _run_in_process(graph: Graph, driver: str) -> None:
    graph.prepare()
    try:
        if driver == "async_start":
            async for _ in graph.async_start(config={"output": {"cache": False}}):
                pass
        else:
            await graph.arun([{}])
    finally:
        await asyncio.gather(*graph._end_trace_tasks)


async def _span_names(session, run_id: str) -> Counter:
    spans = (await session.exec(select(SpanTable).where(SpanTable.trace_id == UUID(run_id)))).all()
    return Counter(span.name for span in spans)


def _display_names(built: dict) -> Counter:
    """The minimum span set: at least one span for every vertex of the flow."""
    return Counter(node["data"]["node"]["display_name"] for node in built["flow"]["data"]["nodes"])


def _assert_single_trace_ended_once(lifecycle: TracerLifecycle) -> None:
    assert len(lifecycle.contexts) == 1, f"start_tracers ran {len(lifecycle.contexts)} times"
    assert len(lifecycle.end_calls) == 1, f"end_tracers ran {len(lifecycle.end_calls)} times"
    assert not any(context.running for context in lifecycle.contexts)
    assert all(context.worker_task is None for context in lifecycle.contexts)
    assert _pending_trace_workers(lifecycle.contexts) == []


async def _graph_for_new_flow(session, spec: str, *, failing_node: str | None = None) -> tuple[dict, Graph]:
    built = _build(spec)
    if failing_node:
        # Loop iterations rebuild body vertices from the node payload, so the failure is set there.
        template = _node_template(built, failing_node)
        template["mode"]["value"] = "Parser"
        template["pattern"]["value"] = "{text!z}"
    flow = Flow(id=uuid4(), name=f"loop-trace-{uuid4()}")
    session.add(flow)
    await session.commit()
    return built, _graph(built, str(flow.id))


@pytest.mark.asyncio
@pytest.mark.parametrize("driver", ["async_start", "arun"])
async def test_should_start_and_end_tracers_once_when_loop_runs_many_iterations(lifecycle, local_db, driver):
    built, graph = await _graph_for_new_flow(local_db, LOOP_SPEC)

    await _run_in_process(graph, driver)

    _assert_single_trace_ended_once(lifecycle)
    assert lifecycle.end_calls == [None]
    traces = (await local_db.exec(select(TraceTable).where(TraceTable.id == UUID(graph._run_id)))).all()
    assert len(traces) == 1
    assert await _span_names(local_db, graph._run_id) >= _display_names(built)


@pytest.mark.asyncio
async def test_should_keep_one_trace_when_loops_are_nested(lifecycle, local_db):
    _, graph = await _graph_for_new_flow(local_db, NESTED_LOOP_SPEC)

    await _run_in_process(graph, "async_start")

    _assert_single_trace_ended_once(lifecycle)
    assert lifecycle.end_calls == [None]
    # The outer body's tail (OUTER_TC) and everything after the outer Loop.
    expected = Counter({"Create List": 1, "Loop": 1, "Type Convert": 1, "Parser": 1, "Chat Output": 1})
    assert await _span_names(local_db, graph._run_id) >= expected


@pytest.mark.asyncio
async def test_should_end_single_trace_with_error_when_loop_iteration_fails(lifecycle, local_db):
    _, graph = await _graph_for_new_flow(local_db, LOOP_SPEC, failing_node="P")

    with pytest.raises(ValueError, match="Error running graph"):
        await _run_in_process(graph, "arun")

    _assert_single_trace_ended_once(lifecycle)
    assert lifecycle.end_calls[0] is not None
    trace = (await local_db.exec(select(TraceTable).where(TraceTable.id == UUID(graph._run_id)))).one()
    assert trace.status == SpanStatus.ERROR


@pytest.mark.asyncio
async def test_should_end_single_trace_once_when_nested_loop_iteration_fails(lifecycle, local_db):
    _, graph = await _graph_for_new_flow(local_db, NESTED_LOOP_SPEC, failing_node="P")

    # Whether the inner-body error surfaces from a nested Loop is not deterministic today (a separate
    # Loop scheduling issue), so this test pins only the trace lifecycle; the error path is covered above.
    with contextlib.suppress(ValueError):
        await _run_in_process(graph, "arun")

    _assert_single_trace_ended_once(lifecycle)


@pytest.mark.asyncio
@pytest.mark.parametrize("entrypoint", ["run", "build"])
async def test_should_persist_loop_body_and_post_loop_spans_through_http(
    client, logged_in_headers, created_api_key, app_lifecycle, entrypoint
):
    built = _build(LOOP_SPEC)
    flow_id = await create_flow(client, _flow_payload(built), logged_in_headers)

    if entrypoint == "run":
        response = await client.post(
            f"api/v1/run/{flow_id}",
            json={"input_value": "", "input_type": "text", "output_type": "text", "tweaks": {}},
            headers={"x-api-key": created_api_key.api_key},
        )
        assert response.status_code == 200, response.text
    else:
        build_response = await build_flow(client, flow_id, logged_in_headers)
        events = await get_build_events(client, build_response["job_id"], logged_in_headers)
        assert events.status_code == 200, events.text
        assert any(json.loads(line).get("event") == "end" for line in events.text.splitlines() if line.strip())

    assert app_lifecycle.contexts, "the run never started a trace"
    run_id = str(app_lifecycle.contexts[0].run_id)
    # Both routes end the trace in a background task after the response is sent.
    for _ in range(300):
        async with session_scope() as session:
            if (await session.exec(select(TraceTable).where(TraceTable.id == UUID(run_id)))).first():
                break
        await asyncio.sleep(0.05)
    else:
        pytest.fail(f"trace {run_id} was not persisted within 15 seconds")

    _assert_single_trace_ended_once(app_lifecycle)
    async with session_scope() as session:
        assert await _span_names(session, run_id) >= _display_names(built)
