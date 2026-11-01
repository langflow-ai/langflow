"""Replaying stored operations on a flow.

Replay carries out stored operations as they are written, in the order they
are written: the forward operations of the operation log, and backward
operations to show an earlier revision. It runs no rule, because the
operations already passed the rules when they were applied. A rule that was
added later must not stop history from replaying.

So replay checks no edge rule, no list position, and no other item of a list
it writes into. It deletes no edge as a cascade delete either: stored
operations list every edge they delete. It fails only when an operation
cannot be carried out:

- ``add_nodes`` or ``add_edges`` adds an id that the flow already has;
- ``add_edges`` names a source or target node that does not exist;
- ``update_nodes`` or ``delete_nodes`` names a node that does not exist;
- an update's path does not exist up to its last segment;
- a list item key segment matches no item before the last segment, or
  matches two items.

Apply makes each of these checks too, with the same code. So the forward
operations of apply always replay, and give the flow that apply gave. Replay
shares with apply the steps that carry out an operation (``apply.py``).

This is the Rust engine's ``lfx::ops::replay``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.services.flow_operations.apply import (
    AddedEdges,
    FieldBackward,
    Report,
    add_nodes,
    invalid,
    remove_edges,
    remove_nodes,
    require_new_edge,
    require_node,
    require_path,
    run_batch,
    walk,
    write_update,
)
from lfx.services.flow_operations.parse import ADD_EDGES, ADD_NODES, DELETE_NODES, UPDATE_NODES, FieldUpdate, Operation

if TYPE_CHECKING:
    from lfx.services.flow_operations.state import GraphState


def replay_batch(state: GraphState, operations: list[Operation], *, backward: bool = False) -> dict[str, Any]:
    """Replay parsed stored operations in order, with no rule, into a new layer, which the caller commits."""
    state.discard()
    report = Report(forward=False, backward=backward)
    run_batch(state, operations, report, _replay_operation)
    return report.result()


def _replay_operation(state: GraphState, operation: Operation, report: Report) -> None:
    kind, payload = operation
    if kind == UPDATE_NODES:
        _replay_update_nodes(state, payload, report)
    elif kind == ADD_NODES:
        add_nodes(state, payload, report)
    elif kind == DELETE_NODES:
        _replay_delete_nodes(state, payload, report)
    elif kind == ADD_EDGES:
        _replay_add_edges(state, payload, report)
    else:
        remove_edges(state, payload, report)


def _replay_update_nodes(state: GraphState, updates: list[FieldUpdate], report: Report) -> None:
    backward = FieldBackward() if report.keep_backward else None
    for place, update in enumerate(updates):
        require_node(state, update.id)
        walked = walk(state, update, place)
        require_path(update, walked, place)
        if backward is not None:
            backward.add(update, walked)
        write_update(state, update, walked)
    if backward is not None:
        backward.record(report)


def _replay_delete_nodes(state: GraphState, ids: list[str], report: Report) -> None:
    """Delete nodes, each of which must exist. Their edges stay: the stored operations delete them."""
    unique = list(dict.fromkeys(ids))
    for node_id in unique:
        if not state.has_node(node_id):
            msg = f"delete_nodes: node does not exist: {node_id!r}"
            raise invalid(msg)
    remove_nodes(state, unique, report)


def _replay_add_edges(state: GraphState, edges: list[dict[str, Any]], report: Report) -> None:
    added = AddedEdges(report)
    for edge in edges:
        require_new_edge(state, edge)
        added.insert(state, edge)
    added.record()
