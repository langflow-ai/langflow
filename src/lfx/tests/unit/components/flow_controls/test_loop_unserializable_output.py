"""Regression test for issue #12591: Loop + vector DB fails to build.

A vector-store component inside a Loop body (e.g. Chroma) can surface objects
that FastAPI's ``jsonable_encoder`` cannot serialize — most notably a
``threading.Lock`` held by the underlying client. The Loop runs its body in an
isolated subgraph and streams an ``on_end_vertex`` event for every completed
inner vertex; that event payload was serialized with a raw ``jsonable_encoder``
call, whose last-resort fallback raises
``ValueError([TypeError("'_thread.lock' object is not iterable"),
TypeError('vars() argument must have __dict__ attribute')])``.

The exception propagated out of the subgraph and surfaced to the user as
``Error building Component Loop: [TypeError(...), TypeError(...)]``, breaking the
whole flow. This test drives a real Loop graph whose body emits a lock-bearing
``Data`` and asserts the build completes instead of crashing.
"""

import asyncio
import json
import threading

import pytest
from lfx.components.flow_controls.loop import LoopComponent
from lfx.custom.custom_component.component import Component
from lfx.events.event_manager import create_default_event_manager
from lfx.graph import Graph
from lfx.io import HandleInput, Output
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


class _LockEmittingComponent(Component):
    """Loop-body node that emits a ``Data`` whose payload carries a lock.

    Stands in for a vector-DB component (Chroma/Astra/…) whose output or
    metadata references a client object holding a non-serializable
    ``threading.Lock``.
    """

    display_name = "Lock Emitter"
    name = "LockEmitter"

    inputs = [HandleInput(name="input_value", display_name="In", input_types=["Data", "Message"])]
    outputs = [Output(display_name="Out", name="out", method="build_out")]

    def build_out(self) -> Data:
        result = Data(data={"text": "result", "vector_store": threading.Lock()})
        # Components surface their last output as ``status``; this is what feeds
        # the build artifacts/events that get serialized for the UI.
        self.status = result
        return result


def _attach_loop_feedback(loop: LoopComponent, source: Component) -> None:
    """Wire ``source.out`` back into ``loop.item`` in the frontend edge shape.

    Mirrors the helper used by the other loop graph tests: the loop feedback
    edge has to be appended in the frontend-compatible shape and the source
    component registered so ``Graph()`` walks to it.
    """
    loop._edges.append(
        {
            "source": source.get_id(),
            "target": loop.get_id(),
            "data": {
                "sourceHandle": {
                    "dataType": source.name,
                    "id": source.get_id(),
                    "name": "out",
                    "output_types": ["Data"],
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


@pytest.mark.asyncio
async def test_loop_with_unserializable_body_output_builds():
    """Loop body that emits a lock-bearing Data must not crash the build (#12591)."""
    loop = LoopComponent(_id="loop")
    rows = [Data(text=f"Row {i}") for i in range(3)]
    loop.set(data=DataFrame(rows))

    body = _LockEmittingComponent(_id="LockEmitter-body")
    body.set(input_value=loop.item_output)
    _attach_loop_feedback(loop, body)

    # A downstream consumer on `done` so done_output runs (classic Loop topology).
    done_sink = LoopComponent(_id="loop-done-sink")
    done_sink.set(data=loop.done_output)

    graph = Graph(loop, done_sink)
    queue: asyncio.Queue = asyncio.Queue()
    event_manager = create_default_event_manager(queue=queue)

    # Pre-fix this raised ComponentBuildError("Error building Component Loop: "
    # "[TypeError(\"'_thread.lock' object is not iterable\"), ...]").
    results = [result async for result in graph.async_start(event_manager=event_manager)]

    loop_result = next(r for r in results if getattr(r, "vertex", None) and r.vertex.id == "loop")
    assert loop_result.valid, "Loop vertex should build successfully despite unserializable body output"

    # The inner body vertex's end event was emitted (not dropped) once per row,
    # with the unserializable lock degraded to a string instead of crashing.
    end_vertex_events = []
    while not queue.empty():
        _, raw, _ = await queue.get()
        payload = json.loads(raw.decode("utf-8").strip())
        if payload["event"] == "end_vertex":
            end_vertex_events.append(payload["data"])

    body_runs = [e for e in end_vertex_events if e.get("build_data", {}).get("id") == "LockEmitter-body"]
    assert len(body_runs) == len(rows), f"Expected {len(rows)} body iterations, got {len(body_runs)}"
