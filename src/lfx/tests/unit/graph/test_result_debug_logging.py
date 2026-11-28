"""Graph result logging defers representations until the real logger admits DEBUG."""

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
import structlog
from lfx.graph import Graph
from lfx.graph.graph import base as graph_module
from lfx.graph.graph.schema import VertexBuildResult
from structlog.testing import ReturnLogger


class ObservedValue:
    """Observe costly, side-effecting, and failing string/repr conversions."""

    def __init__(self, label="value", *, raises=False):
        self.label = label
        self.calls = 0
        self.raises = raises

    def __str__(self):
        """Render the value while recording whether logging requested it."""
        self.calls += 1
        if self.raises:
            message = "result representation failed"
            raise RuntimeError(message)
        return self.label + str(sum(range(100)))

    __repr__ = __str__


def result_logger(level, events):
    """Use structlog's real filtering and async positional interpolation locally."""

    def collect(_logger, _method, event_dict):
        """Capture the emitted record after interpolation and context merging."""
        events.append(dict(event_dict))
        return event_dict

    return structlog.wrap_logger(
        ReturnLogger(),
        processors=[structlog.contextvars.merge_contextvars, collect],
        wrapper_class=structlog.make_filtering_bound_logger(level),
    ).bind(run_id="logging-test")


def execution_harness(monkeypatch, result, built_object):
    """Isolate completed-task handling while observing unchanged persistence/events."""
    graph = Graph(flow_id=str(uuid4()))
    vertex = SimpleNamespace(id="vertex-1", built_result=result, built_object=built_object)
    completed = VertexBuildResult(result_dict={"ok": True}, params="{}", valid=True, artifacts={}, vertex=vertex)
    record = AsyncMock()
    emit = AsyncMock()
    following = AsyncMock(return_value=["next-vertex"])
    remove = Mock()
    monkeypatch.setattr(graph, "_record_vertex_build_result", record)
    monkeypatch.setattr(graph, "_emit_vertex_build_result", emit)
    monkeypatch.setattr(graph, "get_next_runnable_vertices", following)
    monkeypatch.setattr(graph.run_manager, "remove_vertex_from_runnables", remove)
    return graph, completed, record, emit, following, remove


async def execute_completed(graph, result):
    """Feed an actual completed asyncio task into the real graph method."""

    async def complete():
        """Return the already-built result without serializing its values."""
        return result

    task = asyncio.create_task(complete(), name="vertex-1 completed")
    return await graph._execute_tasks([task], asyncio.Lock())


@pytest.mark.parametrize("level", [logging.INFO, logging.DEBUG])
@pytest.mark.parametrize("shape", ["scalar", "nested", "observed", "dataframe"])
async def test_result_logging_respects_level_text_context_and_execution(monkeypatch, level, shape):
    """Disabled logs skip conversion; enabled logs preserve text, context and normal work."""
    events = []
    logger = result_logger(level, events)
    monkeypatch.setattr(graph_module, "logger", logger)
    result_probe = ObservedValue("result-")
    object_probe = ObservedValue("object-")
    dataframe_reprs = []
    if shape == "dataframe":
        import pandas as pd

        original_repr = pd.DataFrame.__repr__

        def counted_repr(frame):
            """Count the actual pandas formatter, retaining its complete output."""
            dataframe_reprs.append(frame)
            return original_repr(frame)

        result = pd.DataFrame({"number": [1, 2], "text": ["value", "50%"]})
        built_object = result
        monkeypatch.setattr(pd.DataFrame, "__repr__", counted_repr)
    elif shape == "scalar":
        result, built_object = 42, "literal %s and 50%"
    elif shape == "nested":
        result, built_object = {"nested": [result_probe]}, {"object": object_probe}
    else:
        result, built_object = result_probe, object_probe
    graph, completed, record, emit, following, remove = execution_harness(monkeypatch, result, built_object)
    with structlog.contextvars.bound_contextvars(correlation_id="request-context"):
        assert await execute_completed(graph, completed) == ["next-vertex"]
    record.assert_awaited_once_with(completed)
    emit.assert_awaited_once_with(completed, ["next-vertex"])
    following.assert_awaited_once()
    remove.assert_called_once_with("vertex-1")
    assert completed.result_dict == {"ok": True}
    assert completed.artifacts == {}
    if level == logging.INFO:
        assert events == []
        assert result_probe.calls == object_probe.calls == 0
        assert dataframe_reprs == []
    else:
        assert len(events) == 1
        # Compare the previous f-string text only after checking the actual calls.
        if shape in {"nested", "observed"}:
            assert result_probe.calls == object_probe.calls == 1
        if shape == "dataframe":
            assert len(dataframe_reprs) == 2
        assert events[0]["event"] == f"Vertex vertex-1, result: {result}, object: {built_object}"
        assert events[0]["run_id"] == "logging-test"
        assert events[0]["correlation_id"] == "request-context"


@pytest.mark.parametrize("level", [logging.INFO, logging.DEBUG])
async def test_raising_representation_only_affects_enabled_debug(monkeypatch, level):
    """INFO intentionally stops invoking repr side effects; DEBUG keeps its failure boundary."""
    events = []
    monkeypatch.setattr(graph_module, "logger", result_logger(level, events))
    value = ObservedValue(raises=True)
    graph, completed, record, emit, following, remove = execution_harness(monkeypatch, value, "object")
    if level == logging.DEBUG:
        with pytest.raises(RuntimeError, match="result representation failed"):
            await execute_completed(graph, completed)
        assert value.calls == 1
        following.assert_not_awaited()
        emit.assert_not_awaited()
    else:
        assert await execute_completed(graph, completed) == ["next-vertex"]
        assert value.calls == 0
        emit.assert_awaited_once()
    record.assert_awaited_once_with(completed)
    remove.assert_called_once_with("vertex-1")
    assert events == []


async def test_debug_records_preserve_completed_task_input_order(monkeypatch):
    """A faster later task cannot reorder enabled result logs."""
    events = []
    monkeypatch.setattr(graph_module, "logger", result_logger(logging.DEBUG, events))
    graph = Graph()
    monkeypatch.setattr(graph, "get_next_runnable_vertices", AsyncMock(return_value=[]))

    async def complete(vertex_id, delay):
        """Complete in reverse order while retaining gather's input order."""
        await asyncio.sleep(delay)
        vertex = SimpleNamespace(id=vertex_id, built_result="result", built_object="object")
        return VertexBuildResult(result_dict={}, params="{}", valid=True, artifacts={}, vertex=vertex)

    tasks = [
        asyncio.create_task(complete("first", 0.01), name="first"),
        asyncio.create_task(complete("second", 0), name="second"),
    ]
    assert await graph._execute_tasks(tasks, asyncio.Lock()) == []
    assert [event["event"] for event in events] == [
        "Vertex first, result: result, object: object",
        "Vertex second, result: result, object: object",
    ]
