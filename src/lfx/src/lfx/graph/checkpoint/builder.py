"""Builds a GraphCheckpoint from a live Graph instance (LE-1440)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.graph.checkpoint.schema import (
    GraphCheckpoint,
    VertexCheckpointData,
    serialize_value,
    wire_has_opaque_drop,
)
from lfx.graph.utils import UnbuiltObject, UnbuiltResult

if TYPE_CHECKING:
    from lfx.graph.graph.base import Graph
    from lfx.graph.vertex.base import Vertex

_EMPTY_GRAPH_DATA = {"nodes": [], "edges": []}


def _vertex_data(vertex: Vertex) -> VertexCheckpointData:
    built_object_wire: dict[str, Any] | None = None
    raw = vertex.built_object
    if vertex.built and raw is not None and not isinstance(raw, (UnbuiltObject, UnbuiltResult)):
        candidate = serialize_value(raw)
        # Why: an opaque member of a dict built_object degrades to a bare None inside the envelope;
        # store the whole built_object as None (downstream re-derives it) instead of corrupting it to
        # {'x': None} or hard-raising (which would bypass the pause path and finalize the run FAILED).
        built_object_wire = None if wire_has_opaque_drop(candidate) else candidate
    built_result_wire = None
    if vertex.built and vertex.built_result is not None and not isinstance(vertex.built_result, UnbuiltResult):
        built_result_wire = serialize_value(vertex.built_result)
    return VertexCheckpointData(
        vertex_id=vertex.id,
        built=vertex.built,
        state=getattr(vertex.state, "name", "ACTIVE"),
        results={k: serialize_value(v) for k, v in vertex.results.items()},
        artifacts={k: serialize_value(v) for k, v in vertex.artifacts.items()},
        built_object=built_object_wire,
        built_result=built_result_wire,
    )


def build_checkpoint(graph: Graph) -> GraphCheckpoint:
    run_state = graph.run_manager.to_dict()
    flow_payload: dict[str, Any] = dict(graph.raw_graph_data)
    if flow_payload == _EMPTY_GRAPH_DATA:
        flow_payload = {"nodes": list(graph._vertices), "edges": list(graph._edges)}  # noqa: SLF001
    return GraphCheckpoint(
        run_id=str(graph.run_id),
        flow_id=str(graph.flow_id) if graph.flow_id else None,
        session_id=graph.session_id or None,
        user_id=str(graph.user_id) if graph.user_id else None,
        job_id=graph.job_id,
        flow_payload=flow_payload,
        run_map={k: list(v) for k, v in run_state["run_map"].items()},
        run_predecessors={k: list(v) for k, v in run_state["run_predecessors"].items()},
        vertices_to_run=set(run_state["vertices_to_run"]),
        vertices_being_run=set(run_state["vertices_being_run"]),
        ran_at_least_once=set(run_state["ran_at_least_once"]),
        run_queue=list(graph._run_queue),  # noqa: SLF001
        call_order=list(graph._call_order),  # noqa: SLF001
        vertices_layers=[list(layer) for layer in graph.vertices_layers],
        first_layer=list(graph._first_layer),  # noqa: SLF001
        inactivated_vertices={str(v) for v in graph.inactivated_vertices},
        conditionally_excluded_vertices={str(v) for v in graph.conditionally_excluded_vertices},
        activated_vertices=list(graph.activated_vertices),
        vertex_results={vertex.id: _vertex_data(vertex) for vertex in graph.vertices},
        pause_context=graph.pause_info,
        human_input_decisions=dict(getattr(graph, "human_input_decisions", {}) or {}),
    )
