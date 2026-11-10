import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import structlog
from lfx.graph import Graph
from lfx.graph.graph.schema import VertexBuildResult


class CostlyRepresentation:
    def __init__(self, *, raises: bool = False) -> None:
        self.calls = 0
        self.raises = raises

    def __repr__(self) -> str:
        self.calls += 1
        if self.raises:
            msg = "representation failed"
            raise ValueError(msg)
        return f"value-{sum(range(1000))}"


# isolate logging assertions from logger instances cached by earlier tests
@pytest.fixture(params=[logging.INFO, logging.DEBUG], ids=["info", "debug"])
def debug_logs(request, monkeypatch):
    config = structlog.get_config().copy()
    records = []

    def record(_logger, _method, event_dict):
        records.append(event_dict)
        raise structlog.DropEvent

    # Keep the facade's real level filtering; capture_logs would bypass it.
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(request.param),
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.CallsiteParameterAdder({structlog.processors.CallsiteParameter.FUNC_NAME}),
            record,
        ],
        cache_logger_on_first_use=False,
    )
    monkeypatch.setattr("lfx.graph.graph.base.logger", structlog.get_logger())
    try:
        with structlog.contextvars.bound_contextvars(flow_id="flow-logging"):
            yield request.param, records
    finally:
        structlog.configure(**config)


@pytest.fixture
def completed_builds(monkeypatch):
    graph = Graph(flow_id="flow-logging")
    builds = [
        VertexBuildResult(
            result_dict={"output": i},
            params=f"params-{i}",
            valid=True,
            artifacts={"artifact": i},
            vertex=SimpleNamespace(id=f"vertex-{i}", built_result=i, built_object=i),
        )
        for i in range(2)
    ]
    graph.run_manager.vertices_being_run.update(build.vertex.id for build in builds)
    next_vertices = AsyncMock(side_effect=[["next", "shared"], ["shared"]])
    monkeypatch.setattr(graph, "get_next_runnable_vertices", next_vertices)
    monkeypatch.setattr(graph, "get_top_level_vertices", lambda ids: ids)
    persist = AsyncMock()
    emit = AsyncMock()
    monkeypatch.setattr("lfx.graph.graph.base.log_vertex_build", persist)
    monkeypatch.setattr("lfx.graph.utils.emit_vertex_build_event", emit)
    return graph, builds, next_vertices, persist, emit


async def execute_builds(graph, builds):
    async def completed(build):
        return build

    tasks = [asyncio.create_task(completed(build), name=build.vertex.id) for build in builds]
    return await graph._execute_tasks(tasks, asyncio.Lock())


@pytest.mark.parametrize("payload", ["scalar", "nested", "costly"])
async def test_execute_tasks_defers_debug_representations(debug_logs, completed_builds, payload):
    level, records = debug_logs
    graph, builds, next_vertices, persist, emit = completed_builds
    probe = CostlyRepresentation()
    value, text = {
        "scalar": (42, "42"),
        "nested": ({"items": [1, {"text": "hello"}]}, "{'items': [1, {'text': 'hello'}]}"),
        "costly": ({"payload": probe}, "{'payload': value-499500}"),
    }[payload]
    for build in builds:
        build.vertex.built_result = value
        build.vertex.built_object = value

    assert set(await execute_builds(graph, builds)) == {"next", "shared"}
    assert graph.run_manager.vertices_being_run == set()
    assert next_vertices.await_count == len(builds)
    assert probe.calls == (4 if level == logging.DEBUG and payload == "costly" else 0)
    assert records == (
        [
            {
                "event": f"Vertex {build.vertex.id}, result: {text}, object: {text}",
                "level": "debug",
                "flow_id": "flow-logging",
                "func_name": "_execute_tasks",
            }
            for build in builds
        ]
        if level == logging.DEBUG
        else []
    )
    for i, build in enumerate(builds):
        persist.assert_any_await(
            flow_id=graph.flow_id,
            vertex_id=build.vertex.id,
            valid=build.valid,
            params=build.params,
            data=build.result_dict,
            artifacts=build.artifacts,
            job_id=None,
        )
        emit.assert_any_await(
            flow_id=graph.flow_id,
            vertex_id=build.vertex.id,
            valid=build.valid,
            params=build.params,
            data_dict=build.result_dict,
            artifacts_dict=build.artifacts,
            next_vertices_ids=["next", "shared"] if i == 0 else ["shared"],
            top_level_vertices=["next", "shared"] if i == 0 else ["shared"],
            inactivated_vertices=[],
        )
    assert persist.await_count == emit.await_count == len(builds)


@pytest.mark.parametrize("attribute", ["built_result", "built_object"])
async def test_execute_tasks_raising_representation(debug_logs, completed_builds, attribute):
    level, records = debug_logs
    graph, builds, next_vertices, persist, emit = completed_builds
    probe = CostlyRepresentation(raises=True)
    setattr(builds[0].vertex, attribute, probe)

    if level == logging.DEBUG:
        with pytest.raises(ValueError, match=r"^representation failed$"):
            await execute_builds(graph, builds)
        assert probe.calls == 1
        next_vertices.assert_not_awaited()
        emit.assert_not_awaited()
    else:
        assert set(await execute_builds(graph, builds)) == {"next", "shared"}
        assert probe.calls == 0
        assert emit.await_count == len(builds)
    assert persist.await_count == len(builds)
    assert records == []
