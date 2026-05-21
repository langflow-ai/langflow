"""Strip CronTrigger nodes out of ``flow.data``.

Used by the bulk and single-trigger DELETE endpoints. The function is
pure on the input dict — it returns a new ``flow.data`` plus the list
of removed component ids. The route handler writes the new data back
to the flow row and then calls the standard lifecycle hook, which
takes care of cancelling the now-orphaned queued ``trigger_job`` rows.

Keeping the mutation pure (no DB access) makes the deletion logic
trivially unit-testable and keeps the API handlers free of dict
gymnastics.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from langflow.services.triggers.discovery import CRON_TRIGGER_TYPE


def remove_cron_trigger_node(
    flow_data: dict[str, Any] | None,
    component_id: str,
) -> tuple[dict[str, Any], bool]:
    """Return ``(new_flow_data, was_removed)`` after dropping a single node.

    Also prunes any edge whose source or target was the removed node,
    so saving the result through the standard flow update path leaves
    a valid graph for downstream consumers. The caller decides what
    to do with ``was_removed`` (typically: 404 when False).
    """
    if not flow_data:
        return flow_data or {"nodes": [], "edges": []}, False

    new_data = deepcopy(flow_data)
    nodes = new_data.get("nodes")
    if not isinstance(nodes, list):
        return new_data, False

    survivors = [n for n in nodes if not _matches(n, component_id)]
    was_removed = len(survivors) != len(nodes)
    new_data["nodes"] = survivors

    if was_removed:
        new_data["edges"] = _prune_edges(new_data.get("edges"), {component_id})

    return new_data, was_removed


def remove_all_cron_trigger_nodes(
    flow_data: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    """Strip every CronTrigger node from ``flow_data`` in one pass.

    Returns ``(new_flow_data, removed_component_ids)``. ``removed_*``
    is the list of node ids that disappeared, in the order they
    appeared in the original graph — useful for bulk-delete responses
    that want to surface what was actually removed.
    """
    if not flow_data:
        return flow_data or {"nodes": [], "edges": []}, []

    new_data = deepcopy(flow_data)
    nodes = new_data.get("nodes")
    if not isinstance(nodes, list):
        return new_data, []

    removed_ids: list[str] = []
    survivors: list[dict[str, Any]] = []
    for node in nodes:
        if _is_cron_trigger_node(node):
            node_id = node.get("id") if isinstance(node, dict) else None
            if isinstance(node_id, str):
                removed_ids.append(node_id)
            continue
        survivors.append(node)

    new_data["nodes"] = survivors
    if removed_ids:
        new_data["edges"] = _prune_edges(new_data.get("edges"), set(removed_ids))
    return new_data, removed_ids


# --------------------------------------------------------------------------- #
#  internal helpers
# --------------------------------------------------------------------------- #


def _matches(node: object, component_id: str) -> bool:
    """Return True when ``node`` is the CronTrigger with the given id."""
    return (
        isinstance(node, dict)
        and node.get("id") == component_id
        and _is_cron_trigger_node(node)
    )


def _is_cron_trigger_node(node: object) -> bool:
    """Same matcher used by ``discovery.find_cron_trigger_nodes``.

    Guarded inline so this module stays import-free from heavy
    discovery state — just the constant.
    """
    if not isinstance(node, dict):
        return False
    data = node.get("data")
    return isinstance(data, dict) and data.get("type") == CRON_TRIGGER_TYPE


def _prune_edges(edges: Any, removed_ids: set[str]) -> list[Any]:
    """Drop any edge that references a removed node id."""
    if not isinstance(edges, list):
        return []
    return [
        edge
        for edge in edges
        if not (
            isinstance(edge, dict)
            and (edge.get("source") in removed_ids or edge.get("target") in removed_ids)
        )
    ]
