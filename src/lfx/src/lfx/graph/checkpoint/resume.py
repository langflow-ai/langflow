"""Restores a Graph from a GraphCheckpoint and recomputes the resume layer (LE-1440)."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from lfx.graph.checkpoint.schema import deserialize_value
from lfx.graph.graph.runnable_vertices_manager import RunnableVerticesManager
from lfx.log.logger import logger

if TYPE_CHECKING:
    from lfx.graph.checkpoint.schema import GraphCheckpoint
    from lfx.graph.checkpoint.store import CheckpointStore
    from lfx.graph.graph.base import Graph


def compute_resume_layer(graph: Graph) -> list[str]:
    """Next runnable vertex ids: unbuilt, non-inactivated vertices whose predecessors are all built.

    Recomputed from restored per-vertex state instead of a full re-sort, so already-built vertices
    are never queued (and never re-executed) on resume. Inactivated vertices (a branch a
    ConditionalRouter stopped before the pause) are excluded so resume doesn't revive a dead branch.
    """
    inactivated = graph.inactivated_vertices | graph.conditionally_excluded_vertices | graph._orphaned_tool_vertex_ids()  # noqa: SLF001
    built_ids = {vertex.id for vertex in graph.vertices if vertex.built}
    layer = [
        vertex.id
        for vertex in graph.vertices
        if not vertex.built
        and vertex.id not in inactivated
        and all(pred in built_ids for pred in graph.predecessor_map.get(vertex.id, []))
    ]
    return sorted(layer)


def _restore_run_manager(graph: Graph, checkpoint: GraphCheckpoint) -> None:
    run_predecessors: defaultdict[str, list[str]] = defaultdict(list)
    run_predecessors.update({k: list(v) for k, v in checkpoint.run_predecessors.items()})
    run_map: defaultdict[str, list[str]] = defaultdict(list)
    run_map.update({k: list(v) for k, v in checkpoint.run_map.items()})
    manager = RunnableVerticesManager.from_dict(
        {
            "run_map": run_map,
            "run_predecessors": run_predecessors,
            "vertices_to_run": set(checkpoint.vertices_to_run),
            # Vertices interrupted mid-build re-run on resume: back to the runnable pool, not in-flight.
            "vertices_being_run": set(),
            "ran_at_least_once": set(checkpoint.ran_at_least_once),
        }
    )
    manager.vertices_to_run.update(checkpoint.vertices_being_run)
    # from_dict omits cycle_vertices; without this a resumed Loop flow never schedules its loop vertex and hangs.
    manager.cycle_vertices = set(graph.cycle_vertices)
    graph.run_manager = manager


def _restore_or_none(wire: dict[str, Any] | None, vertex_id: str, field: str, unrestorable: set[str]) -> Any:
    """``deserialize_value``, but a payload that no longer restores degrades to None.

    Why: a checkpoint written by an affected install can hold a model dump that does not validate
    back (langchain-core >= 1.6.1 dumps ``BaseTool.func``/``coroutine`` to their repr). Raising
    would strand those already-persisted runs forever -- the only escape is starting a brand-new
    run -- so drop the value instead and let the vertex re-derive it, exactly as for an opaque one.

    The vertex id is recorded in ``unrestorable`` so the caller flags it opaque-dropped, exactly as
    for a failed ``built_object``. A None left by a *failure* is not a restored None: leaving the
    vertex marked built would serve that None to a consumer (``get_result`` reads ``built_result``
    whenever ``use_result`` is set) instead of re-running the producer that regenerates it.
    """
    try:
        return deserialize_value(wire)
    except Exception:  # noqa: BLE001
        logger.warning("checkpoint: vertex %s has unrestorable %s; it will re-run on resume", vertex_id, field)
        unrestorable.add(vertex_id)
        return None


def _restore_vertices(graph: Graph, checkpoint: GraphCheckpoint) -> set[str]:
    """Restore per-vertex state, returning the ids whose built state could not be fully restored."""
    from lfx.graph.vertex.base import VertexStates

    unrestorable: set[str] = set()
    for vertex_id, vertex_data in checkpoint.vertex_results.items():
        try:
            vertex = graph.get_vertex(vertex_id)
        except ValueError:
            continue
        vertex.built = vertex_data.built
        # Restore ACTIVE/INACTIVE so a branch a ConditionalRouter stopped stays stopped on resume.
        if vertex_data.state in VertexStates.__members__:
            vertex.state = VertexStates[vertex_data.state]
        vertex.results = {
            k: _restore_or_none(v, vertex_id, "result", unrestorable) for k, v in vertex_data.results.items()
        }
        vertex.artifacts = {
            k: _restore_or_none(v, vertex_id, "artifact", unrestorable) for k, v in vertex_data.artifacts.items()
        }
        if vertex_data.built_object is not None:
            try:
                vertex.built_object = deserialize_value(vertex_data.built_object)
            except Exception:  # noqa: BLE001
                # Leave the fresh vertex's UnbuiltObject in place; the caller marks it opaque-dropped.
                logger.warning(
                    "checkpoint: vertex %s has unrestorable built_object; it will re-run on resume", vertex_id
                )
                unrestorable.add(vertex_id)
        if vertex_data.built_result is not None:
            vertex.built_result = _restore_or_none(vertex_data.built_result, vertex_id, "built_result", unrestorable)
    return unrestorable


def _unbuild_needed_dropped_producers(graph: Graph) -> None:
    """Un-build only the opaque-dropped producers an unbuilt consumer will actually read.

    A vertex whose live output was dropped to None (Tool/model client) must re-run on resume so a
    consumer that re-runs gets a valid input. But re-running one whose consumers are all still built
    is wasted work — and for a producer with side effects (an Agent re-bills its LLM and re-emits its
    message), that surfaces as duplicate outputs on every later resume. So drop only those reachable
    by an unbuilt successor, iterating to a fixpoint so a dropped producer behind another dropped one
    (e.g. a tool feeding an agent) is freed once the agent itself is freed.
    """
    dropped = [
        vertex for vertex in graph.vertices if vertex.id in graph.checkpoint_opaque_dropped_ids and not vertex.is_input
    ]
    changed = True
    while changed:
        changed = False
        built_ids = {vertex.id for vertex in graph.vertices if vertex.built}
        for vertex in dropped:
            if vertex.built and any(s not in built_ids for s in graph.successor_map.get(vertex.id, [])):
                vertex.built = False
                changed = True


def resume_graph_with_decision(
    checkpoint: GraphCheckpoint, store: CheckpointStore, request_id: str | None, decision: dict
) -> Graph:
    """Restore a paused graph and inject a HITL decision for ``request_id``.

    The shared "restore + inject + un-build" seam for HITL resume: rebuild the graph from the
    checkpoint, re-attach the store, record the decision (merged with any checkpoint-restored ones),
    and un-build the paused vertex so it re-runs and reads the decision. Used by the lfx CLI resume
    loop (``lfx.run.hitl``) and the A2A resume path. ``build.py``'s background resume keeps its own
    variant (it adds tracing + predecessor re-run on top).
    """
    from lfx.graph.graph.base import Graph

    if not request_id:
        # No request_id means the decision can't be routed to a paused vertex: it would silently
        # vanish (no vertex matches) or crash on the startswith below. Fail loud instead.
        msg = "Cannot resume: pause request is missing request_id"
        raise RuntimeError(msg)

    graph = Graph.resume_from_checkpoint(checkpoint, checkpoint_store=store)
    graph.checkpointing_enabled = True
    graph.checkpoint_store = store
    graph.human_input_decisions = {
        **(getattr(graph, "human_input_decisions", {}) or {}),
        request_id: decision,
    }
    for vertex in graph.vertices:
        vertex_request_id = f"{vertex.id}:{graph.run_id}"
        if request_id == vertex_request_id or request_id.startswith(vertex_request_id + ":"):
            vertex.built = False
    # Re-run the fixpoint after un-building the paused vertex so any opaque-dropped
    # producer it consumes is rebuilt instead of restoring a None value.
    _unbuild_needed_dropped_producers(graph)
    return graph


def restore_graph_from_checkpoint(checkpoint: GraphCheckpoint, *, store: CheckpointStore | None = None) -> Graph:
    from lfx.graph.graph.base import Graph

    graph = Graph.from_payload(
        checkpoint.flow_payload,
        flow_id=checkpoint.flow_id,
        user_id=checkpoint.user_id,
    )
    graph.source_flow_id = checkpoint.source_flow_id
    if not graph._prepared:  # noqa: SLF001
        graph.prepare()
    graph.set_run_id(checkpoint.run_id)
    graph.reviewed_tool_packs = dict(checkpoint.reviewed_tool_packs)
    if checkpoint.session_id:
        graph.session_id = checkpoint.session_id
    # Continue under the starting identity; else self.user_id (via graph.user_id) is None
    # and str(None) fails UUID parsing for A2A/flow tools ("badly formed hexadecimal UUID string").
    if checkpoint.user_id:
        graph.user_id = checkpoint.user_id
    graph.job_id = checkpoint.job_id
    graph.checkpointing_enabled = True
    graph.checkpoint_store = store
    graph.resumed_from_checkpoint = True
    graph.vertices_layers = [list(layer) for layer in checkpoint.vertices_layers]
    graph._first_layer = list(checkpoint.first_layer)  # noqa: SLF001
    graph._call_order = list(checkpoint.call_order)  # noqa: SLF001
    # Without these, every vertex resumes ACTIVE and compute_resume_layer revives a ConditionalRouter-stopped branch.
    graph.inactivated_vertices = {str(v) for v in checkpoint.inactivated_vertices}
    graph.branch_inactivation_sources = {
        str(source): {str(vertex) for vertex in vertices}
        for source, vertices in checkpoint.branch_inactivation_sources.items()
    }
    graph.conditionally_excluded_vertices = {str(v) for v in checkpoint.conditionally_excluded_vertices}
    graph.human_input_decisions = dict(checkpoint.human_input_decisions)
    graph.activated_vertices = list(checkpoint.activated_vertices)
    # Built-at-checkpoint vertices must not have their async generators re-consumed; the output loop skips this set.
    graph.checkpoint_restored_built_ids = {vid for vid, vd in checkpoint.vertex_results.items() if vd.built}
    # Opaque output (Tool/client) dropped to None re-runs anywhere; the restored None would crash a consumer.
    graph.checkpoint_opaque_dropped_ids = {
        vid for vid, vd in checkpoint.vertex_results.items() if vd.built and vd.built_object is None
    }
    _restore_run_manager(graph, checkpoint)
    # Any field that fails to restore (built_object, built_result, a result or an artifact) is
    # indistinguishable, downstream, from one dropped at write time, so it joins the same set
    # before the fixpoint decides what to re-run.
    graph.checkpoint_opaque_dropped_ids |= {
        vid for vid in _restore_vertices(graph, checkpoint) if checkpoint.vertex_results[vid].built
    }
    _unbuild_needed_dropped_producers(graph)
    graph._run_queue.clear()  # noqa: SLF001
    graph._run_queue.extend(compute_resume_layer(graph))  # noqa: SLF001
    return graph
