"""Restores a Graph from a GraphCheckpoint and recomputes the resume layer (LE-1440)."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from lfx.graph.checkpoint.schema import deserialize_value
from lfx.graph.graph.runnable_vertices_manager import RunnableVerticesManager

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
    inactivated = graph.inactivated_vertices
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


def _restore_vertices(graph: Graph, checkpoint: GraphCheckpoint) -> None:
    from lfx.graph.vertex.base import VertexStates

    for vertex_id, vertex_data in checkpoint.vertex_results.items():
        try:
            vertex = graph.get_vertex(vertex_id)
        except ValueError:
            continue
        vertex.built = vertex_data.built
        # Restore ACTIVE/INACTIVE so a branch a ConditionalRouter stopped stays stopped on resume.
        if vertex_data.state in VertexStates.__members__:
            vertex.state = VertexStates[vertex_data.state]
        vertex.results = {k: deserialize_value(v) for k, v in vertex_data.results.items()}
        vertex.artifacts = {k: deserialize_value(v) for k, v in vertex_data.artifacts.items()}
        if vertex_data.built_object is not None:
            vertex.built_object = deserialize_value(vertex_data.built_object)
        if vertex_data.built_result is not None:
            vertex.built_result = deserialize_value(vertex_data.built_result)


def restore_graph_from_checkpoint(checkpoint: GraphCheckpoint, *, store: CheckpointStore | None = None) -> Graph:
    from lfx.graph.graph.base import Graph

    graph = Graph.from_payload(checkpoint.flow_payload, flow_id=checkpoint.flow_id)
    if not graph._prepared:  # noqa: SLF001
        graph.prepare()
    graph.set_run_id(checkpoint.run_id)
    if checkpoint.session_id:
        graph.session_id = checkpoint.session_id
    graph.job_id = checkpoint.job_id
    graph.checkpointing_enabled = True
    graph.checkpoint_store = store
    graph.resumed_from_checkpoint = True
    graph.vertices_layers = [list(layer) for layer in checkpoint.vertices_layers]
    graph._first_layer = list(checkpoint.first_layer)  # noqa: SLF001
    graph._call_order = list(checkpoint.call_order)  # noqa: SLF001
    # Without these, every vertex resumes ACTIVE and compute_resume_layer revives a ConditionalRouter-stopped branch.
    graph.inactivated_vertices = {str(v) for v in checkpoint.inactivated_vertices}
    graph.activated_vertices = list(checkpoint.activated_vertices)
    # Built-at-checkpoint vertices must not have their async generators re-consumed; the output loop skips this set.
    graph.checkpoint_restored_built_ids = {vid for vid, vd in checkpoint.vertex_results.items() if vd.built}
    # Opaque output (Tool/client) dropped to None re-runs anywhere; the restored None would crash a consumer.
    graph.checkpoint_opaque_dropped_ids = {
        vid for vid, vd in checkpoint.vertex_results.items() if vd.built and vd.built_object is None
    }
    _restore_run_manager(graph, checkpoint)
    _restore_vertices(graph, checkpoint)
    for vertex in graph.vertices:
        if vertex.id in graph.checkpoint_opaque_dropped_ids and not vertex.is_input:
            vertex.built = False
    graph._run_queue.clear()  # noqa: SLF001
    graph._run_queue.extend(compute_resume_layer(graph))  # noqa: SLF001
    return graph
