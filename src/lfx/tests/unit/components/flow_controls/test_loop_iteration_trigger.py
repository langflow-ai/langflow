"""Regression tests for the Loop iteration trigger.

Cover the scenario where only the Loop's `item` output has a downstream
consumer and `done` is not connected. Before the fix, the Loop component
put its iteration logic inside `done_output`. With `_should_process_output`
on this branch only running outputs whose name is in the vertex's outgoing
edge source names, `done` would never execute in this topology, and the
loop body never ran. The fix moves the iteration into a shared idempotent
helper that both `item_output` and `done_output` invoke, so whichever
output is consumed triggers the loop.
"""

import asyncio
import json

import pytest
from lfx.components.flow_controls.loop import LoopComponent
from lfx.components.input_output import ChatOutput
from lfx.events.event_manager import create_default_event_manager
from lfx.graph import Graph
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


def _attach_feedback(loop: LoopComponent, source: ChatOutput) -> None:
    """Wire a loop feedback edge from `source.message` to `loop.item`.

    `loop.set(item=source.message_response)` is the "right" way but is
    rejected by edge validation here because the loop target handle's
    declared types don't include Message unless the frontend-style
    `output_types` list is used. This helper appends the edge in the
    frontend-compatible shape AND registers the source component with
    the loop so `Graph()` picks it up via its recursive component walk.
    """
    loop._edges.append(
        {
            "source": source.get_id(),
            "target": loop.get_id(),
            "data": {
                "sourceHandle": {
                    "dataType": "ChatOutput",
                    "id": source.get_id(),
                    "name": "message",
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
    # Register the source so Graph().add_component walks to it when it
    # recurses through loop._components.
    if source not in loop._components:
        loop._components.append(source)


def _build_item_only_topology(row_count: int = 3):
    """Item-only topology: DataFrame -> Loop.item -> ChatOutput -> feedback.

    Nothing is connected to `Loop.done`. The ChatOutput vertex id starts
    with "ChatOutput-" so the graph identifies it as a ChatOutput
    interface component (base_name is derived from the id prefix).
    """
    loop = LoopComponent(_id="loop")
    rows = [Data(text=f"Row {i}") for i in range(row_count)]
    loop.set(data=DataFrame(rows))

    chat_output = ChatOutput(_id="ChatOutput-sink")
    chat_output.set(input_value=loop.item_output, should_store_message=False)

    _attach_feedback(loop, chat_output)

    return Graph(loop, chat_output), loop, chat_output


async def _drain(queue: asyncio.Queue) -> dict[str, list[dict]]:
    """Drain an event queue into a dict keyed by event type."""
    by_type: dict[str, list[dict]] = {}
    while not queue.empty():
        _, raw, _ = await queue.get()
        payload = json.loads(raw.decode().strip())
        by_type.setdefault(payload["event"], []).append(payload["data"])
    return by_type


@pytest.mark.asyncio
async def test_item_only_topology_dispatches_each_row_to_chatoutput():
    """Each row must reach ChatOutput in the loop body when only item is wired."""
    graph, _, _ = _build_item_only_topology(row_count=3)

    queue: asyncio.Queue = asyncio.Queue()
    em = create_default_event_manager(queue=queue)
    results = [r async for r in graph.async_start(event_manager=em)]

    events = await _drain(queue)
    chat_output_runs = [
        d for d in events.get("end_vertex", []) if d.get("build_data", {}).get("id") == "ChatOutput-sink"
    ]
    # 3 rows -> 3 subgraph iterations -> 3 ChatOutput builds.
    assert len(chat_output_runs) == 3, f"ChatOutput should have been built once per row, got {len(chat_output_runs)}"

    # Item inspector surfaces the dispatched inputs wrapped in a Data
    # envelope so the outer item edge remains compatible with Data-typed
    # consumers in the loop body.
    loop_result = next(r for r in results if getattr(r, "vertex", None) and r.vertex.id == "loop")
    item = loop_result.result_dict.outputs["item"]
    assert item["message"]["count"] == 3
    assert [row["text"] for row in item["message"]["items"]] == ["Row 0", "Row 1", "Row 2"]


@pytest.mark.asyncio
async def test_classic_topology_both_outputs_connected_runs_subgraph_once():
    """Both `item` and `done` connected. Subgraph must run once per row, not twice.

    This is the LoopTest.json shape: Loop.item feeds a body that loops back,
    and Loop.done produces the aggregated DataFrame for a downstream sink.
    Without `_iterate`'s idempotency guard, item_output and done_output
    would each trigger execute_loop_body, doubling the iterations.

    The downstream `done` consumer is another LoopComponent, which accepts
    DataFrame input without formatting it (avoids the tabulate dependency
    that ChatOutput would pull in when converting a DataFrame to Markdown).
    """
    loop = LoopComponent(_id="loop")
    loop.set(data=DataFrame([Data(text=f"Row {i}") for i in range(3)]))

    # Loop body: Loop.item -> ChatOutput (body sink) -> feedback to Loop.item
    body_sink = ChatOutput(_id="ChatOutput-body")
    body_sink.set(input_value=loop.item_output, should_store_message=False)
    _attach_feedback(loop, body_sink)

    # Done consumer: a second Loop whose `data` input accepts DataFrame.
    # We never drive it to actually iterate (no body, no feedback); we
    # only need it to be a downstream consumer so `done` is in the outer
    # Loop's outgoing edge source names and done_output runs.
    done_sink = LoopComponent(_id="loop-done-sink")
    done_sink.set(data=loop.done_output)

    graph = Graph(loop, done_sink)
    queue: asyncio.Queue = asyncio.Queue()
    em = create_default_event_manager(queue=queue)
    [r async for r in graph.async_start(event_manager=em)]

    events = await _drain(queue)
    body_runs = [d for d in events.get("end_vertex", []) if d.get("build_data", {}).get("id") == "ChatOutput-body"]
    # If iteration ran twice (once per output), we'd see 6 builds.
    assert len(body_runs) == 3, f"Expected 3 body builds (one per row), got {len(body_runs)}"


@pytest.mark.asyncio
async def test_empty_data_list_skips_subgraph():
    """An empty input must short-circuit without executing the body."""
    loop = LoopComponent(_id="loop")
    loop.set(data=DataFrame([]))

    chat_output = ChatOutput(_id="ChatOutput-sink")
    chat_output.set(input_value=loop.item_output, should_store_message=False)
    _attach_feedback(loop, chat_output)

    graph = Graph(loop, chat_output)
    queue: asyncio.Queue = asyncio.Queue()
    em = create_default_event_manager(queue=queue)
    [r async for r in graph.async_start(event_manager=em)]

    events = await _drain(queue)
    body_runs = [d for d in events.get("end_vertex", []) if d.get("build_data", {}).get("id") == "ChatOutput-sink"]
    assert body_runs == []
    # The iteration guard was set and an empty aggregate cached, so a
    # follow-up _iterate call stays a no-op.
    assert loop.ctx.get("loop_iterated") is True
    assert loop.ctx.get("loop_aggregated") == []


@pytest.mark.asyncio
async def test_iterate_caches_and_re_raises_errors():
    """A failed iteration must cache the exception and re-raise on re-entry.

    We trigger a real failure by feeding the Loop invalid input
    (`self.data` is None). `_iterate` calls `initialize_data` which
    validates the input and raises `TypeError`. The cached exception is
    then re-raised verbatim on subsequent `_iterate` calls instead of
    silently returning an empty list or retrying the validation.
    """
    loop = LoopComponent(_id="loop")
    # initialize_data's validator raises TypeError for non-DataFrame/Data inputs.
    loop.set(data="not a dataframe")

    # No vertex/graph is needed for this direct invocation path, but
    # _iterate does reach into self.ctx. Give it a minimal graph so ctx
    # is available.
    chat_output = ChatOutput(_id="ChatOutput-sink")
    chat_output.set(input_value=loop.item_output, should_store_message=False)
    _attach_feedback(loop, chat_output)
    Graph(loop, chat_output)

    with pytest.raises(TypeError) as first:
        await loop._iterate()

    with pytest.raises(TypeError) as second:
        await loop._iterate()

    # Same exception object cached and re-raised, not a fresh validation pass.
    assert first.value is second.value


@pytest.mark.asyncio
async def test_ctx_isolation_across_runs():
    """Each async_start over the same topology must iterate the full input.

    ctx lives per-run, so the `_iterated` guard must not leak and suppress
    the second run. This locks in the per-run isolation claim in
    `_iterate`'s docstring.
    """
    counts = []
    for _ in range(2):
        graph, _, _ = _build_item_only_topology(row_count=3)
        queue: asyncio.Queue = asyncio.Queue()
        em = create_default_event_manager(queue=queue)
        [r async for r in graph.async_start(event_manager=em)]
        events = await _drain(queue)
        counts.append(
            sum(1 for d in events.get("end_vertex", []) if d.get("build_data", {}).get("id") == "ChatOutput-sink")
        )

    assert counts == [3, 3], f"Each run should build ChatOutput 3 times, got {counts}"


@pytest.mark.asyncio
async def test_iterate_writes_summary_logs():
    """_iterate produces a Start and a Complete log with row counts.

    Logs are attributed to the first output that triggers `_iterate`
    (here `item_output`), so the Logs tab on the Loop node shows the
    run summary against the `item` output.
    """
    graph, loop, _ = _build_item_only_topology(row_count=3)
    [r async for r in graph.async_start()]

    item_logs = loop._output_logs.get("item", [])
    messages = [(log.name, log.message) for log in item_logs]
    assert ("Start", "Starting loop over 3 item(s)") in messages, messages
    assert any(name == "Complete" and "Completed 3 iteration(s)" in msg for name, msg in messages), messages
