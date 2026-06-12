"""Graph pause/checkpoint mechanics (LE-1440).

Real ChatInput→ChatOutput graphs (no mocks): the probe is an injected seam by
design, so supplying a scripted probe is legitimate test input.
"""

from __future__ import annotations

import asyncio

import pytest
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph import Graph
from lfx.graph.checkpoint.store import InMemoryCheckpointStore
from lfx.graph.exceptions import GraphPausedException


def _graph(store=None, probe=None, job_id="job-1") -> Graph:
    chat_input = ChatInput(_id="chat_input")
    chat_input.set(should_store_message=False)
    chat_output = ChatOutput(input_value="test", _id="chat_output")
    chat_output.set(sender_name=chat_input.message_response)
    graph = Graph(chat_input, chat_output)
    graph.session_id = "sess-1"
    graph.set_run_id()
    if store is not None:
        graph.checkpointing_enabled = True
        graph.checkpoint_store = store
    if probe is not None:
        graph.pause_probe = probe
    graph.job_id = job_id
    return graph


async def test_process_raises_graph_paused_when_probe_says_pause():
    store = InMemoryCheckpointStore()

    async def probe(_job_id: str) -> str:
        return "pause"

    graph = _graph(store=store, probe=probe)
    with pytest.raises(GraphPausedException) as excinfo:
        await graph.process(fallback_to_env_vars=False)

    checkpoint = await store.load(excinfo.value.checkpoint_id)
    assert checkpoint is not None
    assert checkpoint.run_id == str(graph.run_id)
    assert checkpoint.job_id == "job-1"
    by_run = await store.load_by_run_id(str(graph.run_id))
    assert by_run is not None
    assert by_run.checkpoint_id == checkpoint.checkpoint_id


async def test_standalone_default_probe_never_pauses():
    store = InMemoryCheckpointStore()
    graph = _graph(store=store, probe=None)
    result = await graph.process(fallback_to_env_vars=False)
    assert result is graph
    assert graph.pause_requested is False


async def test_probe_cancel_raises_cancelled_error():
    async def probe(_job_id: str) -> str:
        return "cancel"

    graph = _graph(store=InMemoryCheckpointStore(), probe=probe)
    with pytest.raises(asyncio.CancelledError):
        await graph.process(fallback_to_env_vars=False)


async def test_checkpointing_disabled_ignores_pause_request():
    graph = _graph(store=None, probe=None)
    graph.request_pause(reason="human_input_required")
    result = await graph.process(fallback_to_env_vars=False)
    assert result is graph


async def test_request_pause_sets_flag_and_info():
    graph = _graph(store=InMemoryCheckpointStore())
    graph.request_pause(reason="human_input_required", data={"options": ["a"]})
    assert graph.pause_requested is True
    assert graph.pause_info == {"reason": "human_input_required", "data": {"options": ["a"]}}


async def test_checkpoint_builder_fails_fast_on_opaque_built_object():
    store = InMemoryCheckpointStore()
    graph = _graph(store=store)
    await graph.process(fallback_to_env_vars=False)

    class OpaqueHandle:
        pass

    vertex = graph.get_vertex("chat_input")
    vertex.built = True
    vertex.built_object = OpaqueHandle()
    with pytest.raises(TypeError, match="chat_input"):
        graph.build_checkpoint()


async def test_checkpoint_captures_execution_state_after_partial_run():
    store = InMemoryCheckpointStore()
    graph = _graph(store=store)
    await graph.astep()
    checkpoint = graph.build_checkpoint()
    assert "chat_input" in checkpoint.call_order
    assert checkpoint.vertex_results["chat_input"].built is True
    assert checkpoint.flow_payload
    assert checkpoint.session_id == "sess-1"
