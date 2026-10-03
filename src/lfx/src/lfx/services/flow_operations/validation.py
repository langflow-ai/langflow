"""The rules every stored flow graph follows.

These rules are the flow's write contract. The engine checks them on the graph
it starts from, the diff checks them on the graph a save asks for, and
``repair_flow_data`` knows a fix for every one of them. Each rule has a stable
code so a refused write can name what is wrong and where.

Table rows follow extra rules, checked only against the stored graph a write
replaces (``base``): every table value the write adds or changes must have
rows with a unique ``_id`` and a ``_pos``, sorted by ``(_pos, _id)``. A table
the write leaves unchanged is accepted as stored, so legacy tables without
row ids stay valid until someone edits them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any

from lfx.services.flow_operations.canonical import values_equal
from lfx.services.flow_operations.exceptions import FlowDataValidationError
from lfx.services.flow_operations.schema import load_node_schema

GraphPath = tuple[str | int, ...]

# Every node carries these as objects for its whole lifetime; operations patch
# inside them instead of replacing them.
NODE_OBJECT_PATHS: tuple[GraphPath, ...] = (
    ("data",),
    ("data", "node"),
    ("data", "node", "template"),
)


class GraphViolationCode(str, Enum):
    FLOW_DATA_NOT_OBJECT = "FLOW_DATA_NOT_OBJECT"
    COLLECTION_NOT_LIST = "COLLECTION_NOT_LIST"
    NODE_NOT_OBJECT = "NODE_NOT_OBJECT"
    EDGE_NOT_OBJECT = "EDGE_NOT_OBJECT"
    NODE_ID_MISSING = "NODE_ID_MISSING"
    NODE_ID_DUPLICATE = "NODE_ID_DUPLICATE"
    EDGE_ID_MISSING = "EDGE_ID_MISSING"
    EDGE_ID_DUPLICATE = "EDGE_ID_DUPLICATE"
    EDGE_ENDPOINT_INVALID = "EDGE_ENDPOINT_INVALID"
    NODE_DATA_NOT_OBJECT = "NODE_DATA_NOT_OBJECT"
    NON_FINITE_NUMBER = "NON_FINITE_NUMBER"
    TABLE_ROW_NOT_OBJECT = "TABLE_ROW_NOT_OBJECT"
    TABLE_ROW_ID_MISSING = "TABLE_ROW_ID_MISSING"
    TABLE_ROW_ID_DUPLICATE = "TABLE_ROW_ID_DUPLICATE"
    TABLE_ROW_POS_INVALID = "TABLE_ROW_POS_INVALID"
    TABLE_ROWS_UNSORTED = "TABLE_ROWS_UNSORTED"


@dataclass(frozen=True)
class GraphViolation:
    """One broken rule, where it was found, and a message without graph values."""

    code: GraphViolationCode
    path: GraphPath
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code.value, "path": list(self.path), "message": self.message}


def find_graph_violations(
    flow_data: Any,
    *,
    check_values: bool = True,
    base: Any = None,
) -> list[GraphViolation]:
    """Return every rule ``flow_data`` breaks, in document order.

    ``check_values`` also walks every value for NaN and Infinity. The engine
    skips it when replaying stored operations, whose values were checked when
    they were written, so replay stays proportional to the number of nodes and
    edges rather than to the size of the flow.

    ``base`` is the stored graph a write replaces. When it is given, every
    table value ``flow_data`` adds or changes relative to it is checked too;
    pass an empty graph for a flow that has no stored graph yet.
    """
    if not isinstance(flow_data, dict):
        return [GraphViolation(GraphViolationCode.FLOW_DATA_NOT_OBJECT, (), "flow data must be an object")]

    violations: list[GraphViolation] = []
    nodes = flow_data.get("nodes")
    edges = flow_data.get("edges")
    for key, collection in (("nodes", nodes), ("edges", edges)):
        if not isinstance(collection, list):
            violations.append(
                GraphViolation(GraphViolationCode.COLLECTION_NOT_LIST, (key,), f"flow data {key} must be a list")
            )

    node_ids: set[str] = set()
    if isinstance(nodes, list):
        for index, node in enumerate(nodes):
            violations.extend(_node_violations(node, ("nodes", index), node_ids))

    if isinstance(edges, list):
        edge_ids: set[str] = set()
        for index, edge in enumerate(edges):
            violations.extend(_edge_violations(edge, ("edges", index), edge_ids, node_ids))

    if base is not None and isinstance(nodes, list):
        violations.extend(find_table_violations(base, flow_data))
    if check_values:
        violations.extend(_non_finite_violations(flow_data))
    return violations


def validate_flow_data(
    flow_data: Any,
    *,
    check_values: bool = True,
    context: str = "flow.data",
    base: Any = None,
) -> None:
    """Raise ``FlowDataValidationError`` listing every violation, if there are any."""
    violations = find_graph_violations(flow_data, check_values=check_values, base=base)
    if violations:
        first = violations[0]
        location = ".".join(str(part) for part in first.path) or "<root>"
        more = f" (and {len(violations) - 1} more)" if len(violations) > 1 else ""
        msg = f"{context}: {first.message} at {location}{more}"
        raise FlowDataValidationError(msg, violations=violations)


def _node_violations(node: Any, path: GraphPath, node_ids: set[str]) -> list[GraphViolation]:
    if not isinstance(node, dict):
        return [GraphViolation(GraphViolationCode.NODE_NOT_OBJECT, path, "node must be an object")]

    violations: list[GraphViolation] = []
    node_id = node.get("id")
    if not isinstance(node_id, str) or not node_id:
        violations.append(
            GraphViolation(GraphViolationCode.NODE_ID_MISSING, (*path, "id"), "node must have a non-empty string id")
        )
    elif node_id in node_ids:
        violations.append(GraphViolation(GraphViolationCode.NODE_ID_DUPLICATE, (*path, "id"), "duplicate node id"))
    else:
        node_ids.add(node_id)

    value: Any = node
    for object_path in NODE_OBJECT_PATHS:
        value = value.get(object_path[-1]) if isinstance(value, dict) else None
        if not isinstance(value, dict):
            label = ".".join(str(part) for part in object_path)
            violations.append(
                GraphViolation(
                    GraphViolationCode.NODE_DATA_NOT_OBJECT, (*path, *object_path), f"{label} must be an object"
                )
            )
            break
    return violations


def _edge_violations(edge: Any, path: GraphPath, edge_ids: set[str], node_ids: set[str]) -> list[GraphViolation]:
    if not isinstance(edge, dict):
        return [GraphViolation(GraphViolationCode.EDGE_NOT_OBJECT, path, "edge must be an object")]

    violations: list[GraphViolation] = []
    edge_id = edge.get("id")
    if not isinstance(edge_id, str) or not edge_id:
        violations.append(
            GraphViolation(GraphViolationCode.EDGE_ID_MISSING, (*path, "id"), "edge must have a non-empty string id")
        )
    elif edge_id in edge_ids:
        violations.append(GraphViolation(GraphViolationCode.EDGE_ID_DUPLICATE, (*path, "id"), "duplicate edge id"))
    else:
        edge_ids.add(edge_id)

    for endpoint in ("source", "target"):
        node_id = edge.get(endpoint)
        if not isinstance(node_id, str) or not node_id:
            message = f"edge must have a non-empty string {endpoint}"
        elif node_id not in node_ids:
            message = f"edge {endpoint} node does not exist"
        else:
            continue
        violations.append(GraphViolation(GraphViolationCode.EDGE_ENDPOINT_INVALID, (*path, endpoint), message))
    return violations


def _non_finite_violations(flow_data: dict[str, Any]) -> list[GraphViolation]:
    violations: list[GraphViolation] = []
    stack: list[tuple[Any, GraphPath]] = [(flow_data, ())]
    while stack:
        value, path = stack.pop()
        if isinstance(value, float) and not math.isfinite(value):
            violations.append(
                GraphViolation(GraphViolationCode.NON_FINITE_NUMBER, path, "NaN and Infinity are not valid JSON")
            )
        elif isinstance(value, dict):
            stack.extend((item, (*path, key)) for key, item in reversed(value.items()))
        elif isinstance(value, list):
            stack.extend((item, (*path, index)) for index, item in reversed(list(enumerate(value))))
    return violations


# --- Table rows ------------------------------------------------------------------------


@dataclass(frozen=True)
class ChangedTable:
    """A table value a write adds or changes, and where it is."""

    path: GraphPath
    rows: list[Any]


def changed_tables(base: Any, target: dict[str, Any]) -> list[ChangedTable]:
    """Return the table values ``target`` adds or changes relative to ``base``, in document order."""
    schema = load_node_schema()
    base_templates: dict[str, dict[str, Any]] = {}
    for node in _list(base, "nodes"):
        template = _template(node)
        if template is not None and isinstance(node.get("id"), str):
            base_templates.setdefault(node["id"], template)

    tables: list[ChangedTable] = []
    for index, node in enumerate(_list(target, "nodes")):
        template = _template(node)
        if template is None:
            continue
        stored = base_templates.get(node.get("id")) or {}
        for field_name, field in template.items():
            value_path = ("data", "node", "template", field_name, "value")
            if schema.keyed_list_at(node, value_path) is None or not isinstance(field.get("value"), list):
                continue
            stored_field = stored.get(field_name)
            if isinstance(stored_field, dict) and "value" in stored_field:
                try:
                    if values_equal(stored_field["value"], field["value"]):
                        continue
                except FlowDataValidationError:
                    pass
            tables.append(ChangedTable(path=("nodes", index, *value_path), rows=field["value"]))
    return tables


def find_table_violations(base: Any, target: Any) -> list[GraphViolation]:
    """Return the row rules broken by table values ``target`` adds or changes relative to ``base``."""
    violations: list[GraphViolation] = []
    for table in changed_tables(base, target):
        violations.extend(table_row_violations(table.rows, table.path))
    return violations


def table_row_violations(rows: list[Any], path: GraphPath) -> list[GraphViolation]:
    """Return the row rules one table value breaks."""
    table = load_node_schema().table
    id_key, position_key = table.key[0], table.position
    violations: list[GraphViolation] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            violations.append(
                GraphViolation(GraphViolationCode.TABLE_ROW_NOT_OBJECT, (*path, index), "table row must be an object")
            )
            continue
        row_id = row.get(id_key)
        if not isinstance(row_id, str) or not row_id:
            violations.append(
                GraphViolation(
                    GraphViolationCode.TABLE_ROW_ID_MISSING,
                    (*path, index, id_key),
                    f"table row must have a non-empty string {id_key}",
                )
            )
        elif row_id in seen_ids:
            violations.append(
                GraphViolation(GraphViolationCode.TABLE_ROW_ID_DUPLICATE, (*path, index, id_key), "duplicate row id")
            )
        else:
            seen_ids.add(row_id)
        position = row.get(position_key)
        if not isinstance(position, str) or not position:
            violations.append(
                GraphViolation(
                    GraphViolationCode.TABLE_ROW_POS_INVALID,
                    (*path, index, position_key),
                    f"table row must have a non-empty string {position_key}",
                )
            )
    if not violations and not is_sorted_table(rows):
        violations.append(
            GraphViolation(
                GraphViolationCode.TABLE_ROWS_UNSORTED,
                path,
                f"table rows must be sorted by {position_key}, then {id_key}",
            )
        )
    return violations


def is_sorted_table(rows: list[Any]) -> bool:
    """Return whether rows are in ``(_pos, _id)`` order."""
    ordered = list(rows)
    load_node_schema().table.sort(ordered)
    return all(left is right for left, right in zip(ordered, rows, strict=True))


def _list(graph: Any, key: str) -> list[Any]:
    value = graph.get(key) if isinstance(graph, dict) else None
    return value if isinstance(value, list) else []


def _template(node: Any) -> dict[str, Any] | None:
    value: Any = node
    for key in ("data", "node", "template"):
        value = value.get(key) if isinstance(value, dict) else None
    if not isinstance(value, dict):
        return None
    return {name: field for name, field in value.items() if isinstance(field, dict)}
