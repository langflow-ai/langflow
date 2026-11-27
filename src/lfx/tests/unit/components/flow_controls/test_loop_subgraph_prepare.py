"""Regression tests for single-prepare loop subgraph execution (#16266)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from lfx.components.flow_controls.loop import LoopComponent
from lfx.components.input_output import ChatOutput
from lfx.components.processing.combine_text import CombineTextComponent
from lfx.components.processing.parser import ParserComponent
from lfx.events.event_manager import create_default_event_manager
from lfx.execution import (
    Coordinator,
    ExecutorRegistry,
    reset_default_coordinator,
    set_default_coordinator,
)
from lfx.execution.executor import Executor
from lfx.execution.types import RunComplete, StepResult
from lfx.graph import Graph
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


def _attach_feedback(loop: LoopComponent, source: Any, source_output: str = "parsed_text") -> None:
    loop._edges.append(
        {
            "source": source.get_id(),
            "target": loop.get_id(),
            "data": {
                "sourceHandle": {
                    "dataType": type(source).__name__,
                    "id": source.get_id(),
                    "name": source_output,
                    "output_types": ["Message"],
                },
                "targetHandle": {
                    "dataType": "LoopComponent",
                    "id": loop.get_id(),
                    "name": "item",
                    "output_types": ["Data", "Message"],
                },
            },
        }
    )
    if source not in loop._components:
        loop._components.append(source)


def _count_subgraph_stages(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    counts = {"prepare": 0, "initialize": 0, "sort_vertices": 0, "_record_snapshot": 0}
    for name in list(counts):
        original = getattr(Graph, name)

        def _make_wrapper(stage: str, fn: Any):
            def _wrapped(self: Graph, *args: Any, **kwargs: Any):
                if getattr(self, "_is_subgraph", False):
                    counts[stage] += 1
                return fn(self, *args, **kwargs)

            return _wrapped

        monkeypatch.setattr(Graph, name, _make_wrapper(name, original))
    return counts


@pytest.mark.asyncio
@pytest.mark.parametrize("n_items", [0, 1, 16])
async def test_loop_prepares_and_initializes_subgraph_once_per_iteration(
    monkeypatch: pytest.MonkeyPatch,
    n_items: int,
) -> None:
    """Default coordinator/executor path runs prepare() and initialize() once per loop item."""
    counts = _count_subgraph_stages(monkeypatch)

    loop = LoopComponent(_id="loop")
    loop.set(data=DataFrame([Data(text=f"Item {i}") for i in range(n_items)]))
    parser = ParserComponent(_id="parser")
    parser.set(input_data=loop.item_output, pattern="Item: {text}", mode="Parser")
    _attach_feedback(loop, parser, "parsed_text")

    done_out = ChatOutput(_id="ChatOutput-done")
    done_out.set(input_value=loop.done_output, should_store_message=False)
    graph = Graph(loop, done_out)

    queue: asyncio.Queue = asyncio.Queue()
    em = create_default_event_manager(queue=queue)
    results = [r async for r in graph.async_start(event_manager=em)]

    assert counts["prepare"] == n_items
    assert counts["initialize"] == n_items
    assert counts["sort_vertices"] == n_items

    loop_result = next(r for r in results if getattr(r, "vertex", None) and r.vertex.id == "loop")
    done_df = loop_result.vertex.results["done"]
    assert len(done_df) == n_items
    assert [row.text for row in done_df.to_data_list()] == [f"Item: Item {i}" for i in range(n_items)]

    # Verify normalized end_vertex events were emitted once per iteration for the parser.
    end_vertex_ids = []
    while not queue.empty():
        _, raw, _ = await queue.get()
        payload = json.loads(raw.decode().strip())
        if payload["event"] == "end_vertex":
            end_vertex_ids.append(payload["data"]["build_data"]["id"])
    assert end_vertex_ids.count("parser") == n_items


@pytest.mark.asyncio
async def test_multi_consumer_fanout_and_chained_body_prepare_once_per_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Item output fanning out to multiple consumers and chained downstream nodes works with one prepare."""
    counts = _count_subgraph_stages(monkeypatch)

    loop = LoopComponent(_id="loop")
    items = [Data(text=f"val-{i}") for i in range(4)]
    loop.set(data=DataFrame(items))

    left = ParserComponent(_id="parser-left")
    left.set(input_data=loop.item_output, pattern="L:{text}", mode="Parser")

    right = ParserComponent(_id="parser-right")
    right.set(input_data=loop.item_output, pattern="R:{text}", mode="Parser")

    combine = CombineTextComponent(_id="combine")
    combine.set(text1=left.parse_combined_text, text2=right.parse_combined_text, delimiter="|")

    sink = ChatOutput(_id="ChatOutput-body")
    sink.set(input_value=combine.combine_texts, should_store_message=False)

    _attach_feedback(loop, sink, "message")
    done_out = ChatOutput(_id="ChatOutput-done")
    done_out.set(input_value=loop.done_output, should_store_message=False)
    graph = Graph(loop, done_out)

    results = [r async for r in graph.async_start()]

    assert counts["prepare"] == 4
    assert counts["initialize"] == 4

    loop_result = next(r for r in results if getattr(r, "vertex", None) and r.vertex.id == "loop")
    done_df = loop_result.vertex.results["done"]
    assert [row.text for row in done_df.to_data_list()] == [f"L:val-{i}|R:val-{i}" for i in range(4)]


@pytest.mark.asyncio
async def test_one_shot_skip_prepare_contract_reprepares_on_repeat_and_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prepared-run handoff is strictly one-shot and invalidated by topology mutations."""
    out = ChatOutput(_id="ChatOutput-only")
    out.set(input_value="hello", should_store_message=False)
    graph = Graph(out, out)

    prepare_calls = 0
    original_prepare = graph.prepare

    def _counting_prepare(*args: Any, **kwargs: Any):
        nonlocal prepare_calls
        prepare_calls += 1
        return original_prepare(*args, **kwargs)

    monkeypatch.setattr(graph, "prepare", _counting_prepare)

    # 1. Matching start_component_id prepare + async_start(skip_prepare=True) consumes handoff once.
    graph.prepare(start_component_id=out.get_id())
    assert prepare_calls == 1
    first_run = [r async for r in graph.async_start(skip_prepare=True)]
    assert len(first_run) > 0
    assert prepare_calls == 1

    # 2. Second async_start(skip_prepare=True) without a new prepare() MUST re-prepare.
    second_run = [r async for r in graph.async_start(skip_prepare=True)]
    assert len(second_run) > 0
    assert prepare_calls == 2

    # 3. Mismatched start_component_id prepare() forces re-prepare even with skip_prepare=True.
    graph.prepare()
    assert prepare_calls == 3
    _ = [r async for r in graph.async_start(skip_prepare=True)]
    assert prepare_calls == 4

    # 4. Direct async_start() (default skip_prepare=False) always prepares even right after prepare().
    graph.prepare(start_component_id=out.get_id())
    assert prepare_calls == 5
    _ = [r async for r in graph.async_start()]
    assert prepare_calls == 6

    # 5. Topology mutation after prepare() invalidates the handoff so skip_prepare=True re-prepares.
    graph.prepare(start_component_id=out.get_id())
    assert prepare_calls == 7
    graph.add_edge({"source": "noop-a", "target": "noop-b", "data": {}})
    # Remove the synthetic edge before running so graph remains valid, keeping mutation invalidated.
    graph._edges.pop()
    _ = [r async for r in graph.async_start(skip_prepare=True)]
    assert prepare_calls == 8


@pytest.mark.asyncio
async def test_custom_executor_receives_prepared_subgraph_and_retains_compatibility() -> None:
    """Custom executors ignoring _skip_prepare still receive an already-prepared iteration subgraph."""
    observed: list[tuple[bool, bool]] = []

    class _CustomExecutor(Executor):
        kind = "in-process"

        async def execute(self, unit):
            observed.append((bool(unit.graph._prepared), bool(unit.runtime_options.get("_skip_prepare"))))
            # Ignore _skip_prepare and invoke async_start() directly as an older custom backend would.
            async for item in unit.graph.async_start(
                user_id=unit.runtime_options.get("user_id"),
                event_manager=unit.runtime_options.get("event_manager"),
            ):
                yield StepResult(payload=item)
            yield RunComplete(outputs=[])

    registry = ExecutorRegistry()
    registry.register(_CustomExecutor())
    set_default_coordinator(Coordinator(registry=registry))
    try:
        loop = LoopComponent(_id="loop")
        loop.set(data=DataFrame([Data(text="alpha"), Data(text="beta")]))
        parser = ParserComponent(_id="parser")
        parser.set(input_data=loop.item_output, pattern="Got {text}", mode="Parser")
        _attach_feedback(loop, parser, "parsed_text")
        done_out = ChatOutput(_id="ChatOutput-done")
        done_out.set(input_value=loop.done_output, should_store_message=False)
        graph = Graph(loop, done_out)

        results = [r async for r in graph.async_start()]
        loop_result = next(r for r in results if getattr(r, "vertex", None) and r.vertex.id == "loop")
        done_df = loop_result.vertex.results["done"]
        assert [row.text for row in done_df.to_data_list()] == ["Got alpha", "Got beta"]
        assert observed == [(True, True), (True, True)]
    finally:
        reset_default_coordinator()


@pytest.mark.asyncio
async def test_cancellation_during_loop_iteration_propagates_cleanly() -> None:
    """Cancelling while a loop iteration stream is active cancels cleanly without hanging."""
    started = asyncio.Event()
    closed = asyncio.Event()

    class _HangingExecutor(Executor):
        kind = "in-process"

        async def execute(self, _unit):
            started.set()
            try:
                await asyncio.Future()
                yield RunComplete(outputs=[])
            finally:
                closed.set()

    registry = ExecutorRegistry()
    registry.register(_HangingExecutor())
    set_default_coordinator(Coordinator(registry=registry))
    try:
        loop = LoopComponent(_id="loop")
        loop.set(data=DataFrame([Data(text="item")]))
        parser = ParserComponent(_id="parser")
        parser.set(input_data=loop.item_output, pattern="{text}", mode="Parser")
        _attach_feedback(loop, parser, "parsed_text")
        done_out = ChatOutput(_id="ChatOutput-done")
        done_out.set(input_value=loop.done_output, should_store_message=False)
        graph = Graph(loop, done_out)

        async def _consume():
            async for _ in graph.async_start():
                pass

        task = asyncio.create_task(_consume())
        await asyncio.wait_for(started.wait(), timeout=2.0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.wait_for(closed.wait(), timeout=2.0)
    finally:
        reset_default_coordinator()
