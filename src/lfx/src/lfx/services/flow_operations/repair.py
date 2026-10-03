"""Bringing a graph that breaks the engine's rules back within them.

Flows stored before the engine enforced its rules, imported flows, and flows
edited directly in the database can break them, and such a flow cannot take
any edit until it is repaired. ``repair_flow_data`` fixes every violation
``find_graph_violations`` reports and lists what it changed.

Repair is never implicit: callers invoke it only when a request asks for it,
and they keep the original first, so even a fix that discards a value (an edge
to a node that does not exist) loses nothing permanently. Replay and ordinary
saves never repair.

Given the stored graph a write replaces (``base``), repair also fixes the rows
of every table the write adds or changes: it assigns missing row ids and
positions (evenly spaced keys that keep the rows in their current order),
regenerates duplicate ids, and sorts the rows.
"""

from __future__ import annotations

import copy
import hashlib
import itertools
import math
from dataclasses import dataclass
from typing import Any

from lfx.services.flow_operations.canonical import canonical_json
from lfx.services.flow_operations.fractional_index import generate_n_keys_between, is_order_key
from lfx.services.flow_operations.schema import load_node_schema
from lfx.services.flow_operations.validation import (
    NODE_OBJECT_PATHS,
    GraphPath,
    GraphViolationCode,
    changed_tables,
    is_sorted_table,
    validate_flow_data,
)

# The fix applied for every rule. A rule without an entry here would leave a
# flow that can neither be saved nor repaired, so tests require one per code.
REPAIRS: dict[GraphViolationCode, str] = {
    GraphViolationCode.FLOW_DATA_NOT_OBJECT: "replaced with an empty flow",
    GraphViolationCode.COLLECTION_NOT_LIST: "replaced with an empty list",
    GraphViolationCode.NODE_NOT_OBJECT: "dropped the entry",
    GraphViolationCode.EDGE_NOT_OBJECT: "dropped the entry",
    GraphViolationCode.NODE_ID_MISSING: "assigned a generated id",
    GraphViolationCode.NODE_ID_DUPLICATE: "assigned a generated id; the first node keeps the id and its edges",
    GraphViolationCode.EDGE_ID_MISSING: "assigned a generated id",
    GraphViolationCode.EDGE_ID_DUPLICATE: "assigned a generated id",
    GraphViolationCode.EDGE_ENDPOINT_INVALID: "dropped the edge",
    GraphViolationCode.NODE_DATA_NOT_OBJECT: "replaced with an empty object",
    GraphViolationCode.NON_FINITE_NUMBER: "replaced with null",
    GraphViolationCode.TABLE_ROW_NOT_OBJECT: "dropped the row",
    GraphViolationCode.TABLE_ROW_ID_MISSING: "assigned a generated row id",
    GraphViolationCode.TABLE_ROW_ID_DUPLICATE: "assigned a generated row id; the first row keeps the id",
    GraphViolationCode.TABLE_ROW_POS_INVALID: "assigned a position that keeps the row where it is",
    GraphViolationCode.TABLE_ROWS_UNSORTED: "sorted the rows by position",
}

_GENERATED_ID_LENGTH = 5
_ID_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


@dataclass(frozen=True)
class GraphFix:
    """One change repair made, at the path the violation was found."""

    code: GraphViolationCode
    path: GraphPath
    action: str

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code.value, "path": list(self.path), "action": self.action}


@dataclass(frozen=True)
class RepairResult:
    flow_data: dict[str, Any]
    fixes: list[GraphFix]


def repair_flow_data(flow_data: Any, *, base: Any = None) -> RepairResult:
    """Return a copy of ``flow_data`` that follows every rule, and the fixes applied.

    Generated IDs are derived from the entry's content and position, so
    repairing the same graph twice gives the same result. With ``base``, the
    table rows the write adds or changes are repaired too.
    """
    fixes: list[GraphFix] = []

    def fix(code: GraphViolationCode, path: GraphPath) -> None:
        fixes.append(GraphFix(code, path, REPAIRS[code]))

    if not isinstance(flow_data, dict):
        fix(GraphViolationCode.FLOW_DATA_NOT_OBJECT, ())
        repaired: dict[str, Any] = {"nodes": [], "edges": []}
        return RepairResult(repaired, fixes)

    repaired = copy.deepcopy(flow_data)
    _replace_non_finite(repaired, (), fix)
    for key in ("nodes", "edges"):
        if not isinstance(repaired.get(key), list):
            fix(GraphViolationCode.COLLECTION_NOT_LIST, (key,))
            repaired[key] = []

    repaired["nodes"] = _repair_nodes(repaired["nodes"], fix)
    node_ids = {node["id"] for node in repaired["nodes"]}
    repaired["edges"] = _repair_edges(repaired["edges"], node_ids, fix)
    if base is not None:
        for table in changed_tables(base, repaired):
            _repair_table(table.rows, table.path, fix)

    # Repair must never return a graph the strict path would refuse.
    validate_flow_data(repaired, context="repaired flow.data", base=base)
    return RepairResult(repaired, fixes)


def _repair_nodes(nodes: list[Any], fix) -> list[dict[str, Any]]:
    kept: list[tuple[int, dict[str, Any]]] = []
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            fix(GraphViolationCode.NODE_NOT_OBJECT, ("nodes", index))
            continue
        _repair_node_objects(node, ("nodes", index), fix)
        kept.append((index, node))

    used_ids = {node["id"] for _, node in kept if _is_id(node.get("id"))}
    seen_ids: set[str] = set()
    for index, node in kept:
        node_id = node.get("id")
        if _is_id(node_id) and node_id not in seen_ids:
            seen_ids.add(node_id)
            continue
        code = GraphViolationCode.NODE_ID_DUPLICATE if _is_id(node_id) else GraphViolationCode.NODE_ID_MISSING
        fix(code, ("nodes", index, "id"))
        new_id = _generate_node_id(node, index, used_ids)
        used_ids.add(new_id)
        seen_ids.add(new_id)
        node["id"] = new_id
        # The editor keeps a node's own id in data.id; follow a rename there.
        if node["data"].get("id") in (node_id, None):
            node["data"]["id"] = new_id
    return [node for _, node in kept]


def _repair_node_objects(node: dict[str, Any], path: GraphPath, fix) -> None:
    parent: dict[str, Any] = node
    for object_path in NODE_OBJECT_PATHS:
        key = object_path[-1]
        if not isinstance(parent.get(key), dict):
            fix(GraphViolationCode.NODE_DATA_NOT_OBJECT, (*path, *object_path))
            parent[key] = {}
        parent = parent[key]


def _repair_edges(edges: list[Any], node_ids: set[str], fix) -> list[dict[str, Any]]:
    kept: list[tuple[int, dict[str, Any]]] = []
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            fix(GraphViolationCode.EDGE_NOT_OBJECT, ("edges", index))
            continue
        # The editor drops these on every load (cleanEdges); nothing can draw them.
        invalid = [
            endpoint
            for endpoint in ("source", "target")
            if not isinstance(edge.get(endpoint), str) or edge[endpoint] not in node_ids
        ]
        if invalid:
            fix(GraphViolationCode.EDGE_ENDPOINT_INVALID, ("edges", index, invalid[0]))
            continue
        kept.append((index, edge))

    used_ids = {edge["id"] for _, edge in kept if _is_id(edge.get("id"))}
    seen_ids: set[str] = set()
    for index, edge in kept:
        edge_id = edge.get("id")
        if _is_id(edge_id) and edge_id not in seen_ids:
            seen_ids.add(edge_id)
            continue
        code = GraphViolationCode.EDGE_ID_DUPLICATE if _is_id(edge_id) else GraphViolationCode.EDGE_ID_MISSING
        fix(code, ("edges", index, "id"))
        new_id = _generate_edge_id(edge, used_ids)
        used_ids.add(new_id)
        seen_ids.add(new_id)
        edge["id"] = new_id
    return [edge for _, edge in kept]


def _repair_table(rows: list[Any], path: GraphPath, fix) -> None:
    """Fix one table value in place: rows are objects with unique ids and positions, in order."""
    table = load_node_schema().table
    id_key, position_key = table.key[0], table.position

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            fix(GraphViolationCode.TABLE_ROW_NOT_OBJECT, (*path, index))
    rows[:] = [row for row in rows if isinstance(row, dict)]

    used_ids = {row[id_key] for row in rows if _is_id(row.get(id_key))}
    seen_ids: set[str] = set()
    for index, row in enumerate(rows):
        row_id = row.get(id_key)
        if _is_id(row_id) and row_id not in seen_ids:
            seen_ids.add(row_id)
            continue
        code = GraphViolationCode.TABLE_ROW_ID_DUPLICATE if _is_id(row_id) else GraphViolationCode.TABLE_ROW_ID_MISSING
        fix(code, (*path, index, id_key))
        new_id = _generate_row_id(path, index, row, used_ids)
        used_ids.add(new_id)
        seen_ids.add(new_id)
        row[id_key] = new_id

    missing = [index for index, row in enumerate(rows) if not _is_id(row.get(position_key))]
    if missing:
        for index in missing:
            fix(GraphViolationCode.TABLE_ROW_POS_INVALID, (*path, index, position_key))
        positions = _positions_keeping_order([row.get(position_key) for row in rows])
        if positions is None:
            positions = generate_n_keys_between(None, None, len(rows))
        for row, position in zip(rows, positions, strict=True):
            row[position_key] = position

    if not is_sorted_table(rows):
        fix(GraphViolationCode.TABLE_ROWS_UNSORTED, path)
        table.sort(rows)


def _positions_keeping_order(positions: list[Any]) -> list[str] | None:
    """Fill missing positions between their neighbours, or return None when the others are out of order."""
    present = [position for position in positions if _is_id(position)]
    if not all(is_order_key(position) for position in present):
        return None
    if any(left >= right for left, right in itertools.pairwise(present)):
        return None
    filled = list(positions)
    index = 0
    while index < len(filled):
        if _is_id(filled[index]):
            index += 1
            continue
        end = index
        while end < len(filled) and not _is_id(filled[end]):
            end += 1
        before = filled[index - 1] if index > 0 else None
        after = filled[end] if end < len(filled) else None
        filled[index:end] = generate_n_keys_between(before, after, end - index)
        index = end
    return filled


def _generate_row_id(path: GraphPath, index: int, row: dict[str, Any], used_ids: set[str]) -> str:
    seed = f"{list(path)}:{index}:{canonical_json(_json_safe(row))}"
    attempt = 0
    while True:
        candidate = _short_digest(f"{seed}:{attempt}")
        if candidate not in used_ids:
            return candidate
        attempt += 1


def _replace_non_finite(value: Any, path: GraphPath, fix) -> Any:
    stack: list[tuple[Any, GraphPath]] = [(value, path)]
    while stack:
        container, container_path = stack.pop()
        items = container.items() if isinstance(container, dict) else enumerate(container)
        for key, item in list(items):
            if isinstance(item, float) and not math.isfinite(item):
                fix(GraphViolationCode.NON_FINITE_NUMBER, (*container_path, key))
                container[key] = None
            elif isinstance(item, (dict, list)):
                stack.append((item, (*container_path, key)))
    return value


def _is_id(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _generate_node_id(node: dict[str, Any], index: int, used_ids: set[str]) -> str:
    # Same shape as the editor's getNodeId: "<component type>-<5 characters>".
    node_type = node["data"].get("type")
    prefix = node_type if _is_id(node_type) else "node"
    seed = f"{index}:{canonical_json(_json_safe(node))}"
    attempt = 0
    while True:
        candidate = f"{prefix}-{_short_digest(f'{seed}:{attempt}')}"
        if candidate not in used_ids:
            return candidate
        attempt += 1


def _generate_edge_id(edge: dict[str, Any], used_ids: set[str]) -> str:
    # Same shape as the editor's updateIds/getHandleId.
    source_handle = edge.get("sourceHandle") if isinstance(edge.get("sourceHandle"), str) else ""
    target_handle = edge.get("targetHandle") if isinstance(edge.get("targetHandle"), str) else ""
    base = f"reactflow__edge-{edge['source']}{source_handle}-{edge['target']}{target_handle}"
    candidate = base
    suffix = 1
    while candidate in used_ids:
        suffix += 1
        candidate = f"{base}-{suffix}"
    return candidate


def _short_digest(seed: str) -> str:
    number = int.from_bytes(hashlib.sha256(seed.encode("utf-8", "surrogatepass")).digest()[:8], "big")
    characters = []
    for _ in range(_GENERATED_ID_LENGTH):
        number, remainder = divmod(number, len(_ID_ALPHABET))
        characters.append(_ID_ALPHABET[remainder])
    return "".join(characters)


def _json_safe(value: Any) -> Any:
    """Make a value serializable for seeding an id, whatever odd types it holds."""
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return repr(value)
