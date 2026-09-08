"""Describing a graph change in terms a person recognises.

The server's copy of the comparison the conflict dialog shows. It lives here
rather than being read back from the client because an audit record cannot be
sourced from the party it describes: a client is free to send any summary it
likes, and the row would still be signed with the caller's name.

Kept deliberately in step with ``src/frontend/src/utils/flow-diff.ts`` — the two
describe the same change to the same person, and disagreeing is worse than
either wording alone.
"""

from __future__ import annotations

import json
from typing import Any

INLINE_VALUE_LIMIT = 60

# Stands in for an absent value, so a record never reads "updated from  to x".
EMPTY_VALUE = "—"

_SECRET_FIELD_TYPES = frozenset({"SecretStr"})


def _nodes_by_id(graph: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    nodes = (graph or {}).get("nodes") or []
    return {node["id"]: node for node in nodes if isinstance(node, dict) and node.get("id")}


def _edges_by_id(graph: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    edges = (graph or {}).get("edges") or []
    return {edge["id"]: edge for edge in edges if isinstance(edge, dict) and edge.get("id")}


def _inner(node: dict[str, Any] | None) -> dict[str, Any]:
    return ((node or {}).get("data") or {}).get("node") or {}


def component_name(node: dict[str, Any] | None) -> str:
    inner = _inner(node)
    return inner.get("display_name") or inner.get("name") or (node or {}).get("id") or "Component"


def _template(node: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """The node's fields, without the metadata that sits beside them.

    A real template carries entries that are not fields at all — ``_type`` is a
    bare string — so anything that is not a field-shaped mapping is dropped here
    rather than being compared as though it had a value.
    """
    template = _inner(node).get("template")
    if not isinstance(template, dict):
        return {}
    # Underscore-prefixed keys are node-template metadata (`_type`,
    # `_frontend_node_flow_id`, ...), not component fields, and the rest of the
    # product filters them out of every render path.
    return {
        name: entry
        for name, entry in template.items()
        if isinstance(entry, dict) and not name.startswith("_")
    }


def _is_secret(entry: dict[str, Any] | None) -> bool:
    if not isinstance(entry, dict):
        return False
    return entry.get("password") is True or entry.get("type") in _SECRET_FIELD_TYPES


def _sort_deep(value: Any) -> Any:
    if isinstance(value, list):
        return [_sort_deep(item) for item in value]
    if isinstance(value, dict):
        return {key: _sort_deep(value[key]) for key in sorted(value)}
    return value


def _named_list(value: Any) -> str | None:
    """A list of named things reads as its names, not as the objects carrying them."""
    if not isinstance(value, list):
        return None
    if not value:
        return "[]"
    names = [item.get("name") if isinstance(item, dict) and "name" in item else None for item in value]
    return ", ".join(str(name) for name in names) if all(name is not None for name in names) else None


def render_value(value: Any) -> str:
    """Stable text for comparison and for display. Key order is not a change."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool | int | float):
        return str(value)
    named = _named_list(value)
    if named is not None:
        return named
    try:
        return json.dumps(_sort_deep(value), ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return str(value)


def _fits_inline(before: str, after: str) -> bool:
    return (
        len(before) <= INLINE_VALUE_LIMIT
        and len(after) <= INLINE_VALUE_LIMIT
        and "\n" not in before
        and "\n" not in after
    )


def _moved(base: dict[str, Any], next_node: dict[str, Any]) -> bool:
    base_pos = base.get("position") or {}
    next_pos = next_node.get("position") or {}
    return round(base_pos.get("x", 0)) != round(next_pos.get("x", 0)) or round(base_pos.get("y", 0)) != round(
        next_pos.get("y", 0)
    )


def _field_changes(base: dict[str, Any], next_node: dict[str, Any]) -> list[dict[str, Any]]:
    base_template = _template(base)
    next_template = _template(next_node)
    changes: list[dict[str, Any]] = []

    for name in sorted(set(base_template) | set(next_template)):
        base_entry = base_template.get(name)
        next_entry = next_template.get(name)
        before = render_value((base_entry or {}).get("value"))
        after = render_value((next_entry or {}).get("value"))
        if before == after:
            continue

        secret = _is_secret(next_entry) or _is_secret(base_entry)
        entry = next_entry or base_entry or {}
        change: dict[str, Any] = {
            "kind": "field",
            "field": name,
            "label": entry.get("display_name") or name,
        }
        # A secret is recorded as touched and never as a value: this row outlives
        # the edit, and a value written here is a value on disk from now on.
        if secret:
            change["secret"] = True
        elif _fits_inline(before, after):
            change["before"] = before or EMPTY_VALUE
            change["after"] = after or EMPTY_VALUE
        else:
            change["truncated"] = True
            change["before"] = before[:INLINE_VALUE_LIMIT]
            change["after"] = after[:INLINE_VALUE_LIMIT]
        changes.append(change)

    return changes


def diff_graphs(base: dict[str, Any] | None, next_graph: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Component-level changes that turn *base* into *next_graph*.

    One group per component, because that is the unit a reader recognises and the
    unit the conflict dialog offers.
    """
    base_nodes = _nodes_by_id(base)
    next_nodes = _nodes_by_id(next_graph)
    groups: list[dict[str, Any]] = []

    for node_id, node in next_nodes.items():
        if node_id not in base_nodes:
            groups.append(
                {
                    "target": f"node:{node_id}",
                    "label": component_name(node),
                    "badge": "added",
                    "changes": [{"kind": "node_added"}],
                }
            )

    for node_id, node in base_nodes.items():
        if node_id not in next_nodes:
            groups.append(
                {
                    "target": f"node:{node_id}",
                    "label": component_name(node),
                    "badge": "removed",
                    "changes": [{"kind": "node_removed"}],
                }
            )

    for node_id, node in next_nodes.items():
        previous = base_nodes.get(node_id)
        if previous is None:
            continue
        changes: list[dict[str, Any]] = []
        if _moved(previous, node):
            changes.append({"kind": "moved"})
        changes.extend(_field_changes(previous, node))
        if changes:
            groups.append(
                {
                    "target": f"node:{node_id}",
                    "label": component_name(node),
                    "badge": "modified",
                    "changes": changes,
                }
            )

    base_edges = _edges_by_id(base)
    next_edges = _edges_by_id(next_graph)
    all_nodes = {**base_nodes, **next_nodes}

    for edge_id, edge in next_edges.items():
        if edge_id in base_edges:
            continue
        groups.append(_edge_group(edge_id, edge, all_nodes, "added"))

    for edge_id, edge in base_edges.items():
        if edge_id in next_edges:
            continue
        groups.append(_edge_group(edge_id, edge, all_nodes, "removed"))

    return groups


def _edge_group(
    edge_id: str,
    edge: dict[str, Any],
    nodes: dict[str, dict[str, Any]],
    badge: str,
) -> dict[str, Any]:
    source = component_name(nodes.get(edge.get("source", "")))
    target = component_name(nodes.get(edge.get("target", "")))
    return {
        "target": f"edge:{edge_id}",
        "label": f"{source} → {target}",
        "badge": badge,
        "changes": [{"kind": f"edge_{badge}", "source": source, "target": target}],
    }


def field_value_in(graph: dict[str, Any] | None, node_id: str, field: str) -> str | None:
    """The rendered value a field holds in *graph*, or None when it is not there."""
    node = _nodes_by_id(graph).get(node_id)
    if node is None:
        return None
    entry = _template(node).get(field)
    if entry is None:
        return None
    return render_value(entry.get("value"))
