"""Naming what an edit touched, without ever recording what it became.

Names only. A value written here would be a value on disk for as long as the
row lives, and the one field most worth auditing is the one most worth never
storing.
"""

from __future__ import annotations

import json
from typing import Any

CHANGES_LIMIT = 50


def _nodes_by_id(graph: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    nodes = (graph or {}).get("nodes") or []
    return {node["id"]: node for node in nodes if isinstance(node, dict) and node.get("id")}


def _edge_ids(graph: dict[str, Any] | None) -> set[str]:
    edges = (graph or {}).get("edges") or []
    return {edge["id"] for edge in edges if isinstance(edge, dict) and edge.get("id")}


def _inner(node: dict[str, Any]) -> dict[str, Any]:
    return (node.get("data") or {}).get("node") or {}


def component_name(node: dict[str, Any]) -> str:
    inner = _inner(node)
    return inner.get("display_name") or inner.get("name") or node.get("id") or "Component"


def _template(node: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """A node's fields, without the metadata that sits beside them.

    A real template carries entries that are not fields — ``_type`` is a bare
    string — so anything that is not a field-shaped mapping is dropped rather
    than compared as though it had a value.
    """
    template = _inner(node).get("template")
    if not isinstance(template, dict):
        return {}
    return {name: entry for name, entry in template.items() if isinstance(entry, dict) and not name.startswith("_")}


def _stable(value: Any) -> str:
    """Text used only to decide whether a value changed; never recorded."""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


def _changed_fields(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    base, next_ = _template(before), _template(after)
    return [
        name
        for name in sorted(set(base) | set(next_))
        if _stable((base.get(name) or {}).get("value")) != _stable((next_.get(name) or {}).get("value"))
    ]


def summarize_flow_changes(before: dict[str, Any] | None, after: dict[str, Any] | None) -> tuple[list[str], int]:
    """Names of what changed between two graphs, and how many there were.

    Returns at most ``CHANGES_LIMIT`` names; the second element is the true
    total, so a mass edit is reported honestly without an unbounded row.
    """
    base_nodes, next_nodes = _nodes_by_id(before), _nodes_by_id(after)
    names: list[str] = []

    names.extend(f"+{component_name(node)}" for node_id, node in next_nodes.items() if node_id not in base_nodes)
    names.extend(f"-{component_name(node)}" for node_id, node in base_nodes.items() if node_id not in next_nodes)

    for node_id, node in next_nodes.items():
        previous = base_nodes.get(node_id)
        if previous is None:
            continue
        label = component_name(node)
        names.extend(f"{label}.{field}" for field in _changed_fields(previous, node))

    base_edges, next_edges = _edge_ids(before), _edge_ids(after)
    added, removed = len(next_edges - base_edges), len(base_edges - next_edges)
    if added:
        names.append(f"+{added} connection{'s' if added > 1 else ''}")
    if removed:
        names.append(f"-{removed} connection{'s' if removed > 1 else ''}")

    return names[:CHANGES_LIMIT], len(names)
