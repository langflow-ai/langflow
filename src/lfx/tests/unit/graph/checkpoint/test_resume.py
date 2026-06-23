"""resume_from_checkpoint mechanics (LE-1440).

The resumed graph must continue from the exact pause point: identity restored,
built vertices NOT re-executed, and the next runnable layer recomputed from
already-built predecessors instead of a full re-sort.
"""

from __future__ import annotations

from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph import Graph
from lfx.graph.checkpoint.store import InMemoryCheckpointStore


async def _paused_checkpoint():
    chat_input = ChatInput(_id="chat_input", input_value="hello")
    chat_input.set(should_store_message=False)
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=chat_input.message_response, should_store_message=False)
    graph = Graph(chat_input, chat_output)
    graph.session_id = "sess-1"
    graph.set_run_id()
    graph.checkpointing_enabled = True
    graph.job_id = "job-1"
    await graph.astep()
    return graph, graph.build_checkpoint()


async def test_resume_restores_identity_and_state():
    original, checkpoint = await _paused_checkpoint()
    resumed = Graph.resume_from_checkpoint(checkpoint)
    assert str(resumed.run_id) == str(original.run_id)
    assert resumed.session_id == "sess-1"
    assert resumed.job_id == "job-1"
    assert resumed.resumed_from_checkpoint is True
    assert resumed._call_order == original._call_order
    assert resumed.get_vertex("chat_input").built is True


async def test_resume_recomputes_next_runnable_layer_from_built_predecessors():
    _, checkpoint = await _paused_checkpoint()
    resumed = Graph.resume_from_checkpoint(checkpoint)
    assert resumed.resume_first_layer() == ["chat_output"]


async def test_resumed_process_completes_without_rerunning_built_vertices():
    _, checkpoint = await _paused_checkpoint()
    store = InMemoryCheckpointStore()
    resumed = Graph.resume_from_checkpoint(checkpoint, checkpoint_store=store)
    # Mutate the restored result: if process() re-ran chat_input the marker
    # would be recomputed back to "hello", proving a re-execution.
    restored_input = resumed.get_vertex("chat_input")
    restored_input.results["message"].text = "hello-restored"
    restored_input.built_object["message"].text = "hello-restored"
    await resumed.process(fallback_to_env_vars=False)
    output_vertex = resumed.get_vertex("chat_output")
    assert output_vertex.built is True
    assert output_vertex.results["message"].text == "hello-restored"
    assert resumed._call_order.count("chat_input") == 1


async def test_resume_restores_vertex_results():
    original, checkpoint = await _paused_checkpoint()
    original_results = original.get_vertex("chat_input").results
    resumed = Graph.resume_from_checkpoint(checkpoint)
    restored_results = resumed.get_vertex("chat_input").results
    assert set(restored_results) == set(original_results)


async def test_resume_keeps_inactivated_branch_stopped():
    from lfx.graph.vertex.base import VertexStates

    graph, _ = await _paused_checkpoint()
    # Simulate a ConditionalRouter having stopped the chat_output branch before the pause.
    graph.inactivated_vertices = {"chat_output"}
    graph.get_vertex("chat_output").state = VertexStates.INACTIVE
    checkpoint = graph.build_checkpoint()

    resumed = Graph.resume_from_checkpoint(checkpoint)
    # The inactivated state survives resume and the dead branch is NOT queued to run again.
    assert resumed.inactivated_vertices == {"chat_output"}
    assert resumed.get_vertex("chat_output").state == VertexStates.INACTIVE
    assert "chat_output" not in resumed.resume_first_layer()


async def test_resume_does_not_reconsume_restored_built_output_vertex():
    chat_input = ChatInput(_id="chat_input", input_value="hello")
    chat_input.set(should_store_message=False)
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=chat_input.message_response, should_store_message=False)
    graph = Graph(chat_input, chat_output)
    graph.set_run_id()
    # Build BOTH vertices so chat_output (which has consume_async_generator) is checkpointed as built.
    await graph.process(fallback_to_env_vars=False)
    checkpoint = graph.build_checkpoint()

    resumed = Graph.resume_from_checkpoint(checkpoint)
    assert "chat_output" in resumed.checkpoint_restored_built_ids
    # Without the guard the output-collection loop re-consumes chat_output's exhausted generator and
    # raises TypeError from stream(); arun must complete cleanly instead of re-consuming it.
    await resumed.arun([{}], fallback_to_env_vars=False)


async def test_resume_flags_only_opaque_dropped_producers():
    _, checkpoint = await _paused_checkpoint()
    # A built producer whose live output (Tool/model) was opaque-dropped is stored with built_object
    # None; one whose output round-tripped keeps a value. Only the former must be flagged for re-run.
    checkpoint.vertex_results["chat_input"].built = True
    checkpoint.vertex_results["chat_input"].built_object = None

    resumed = Graph.resume_from_checkpoint(checkpoint)

    assert "chat_input" in resumed.checkpoint_opaque_dropped_ids
    assert "chat_output" not in resumed.checkpoint_opaque_dropped_ids


async def test_resume_restores_cycle_vertices_from_graph():
    _, checkpoint = await _paused_checkpoint()
    resumed = Graph.resume_from_checkpoint(checkpoint)
    # cycle_vertices is dropped by to_dict/from_dict; resume must repopulate it from the rebuilt
    # graph so a looped flow still schedules its loop vertex (here both are empty, but the
    # restored manager must mirror the graph rather than an independently-empty set).
    assert resumed.run_manager.cycle_vertices == set(resumed.cycle_vertices)
