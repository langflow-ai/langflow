"""The rules every stored flow graph follows.

These rules are the flow's write contract. The engine checks them on the graph
it starts from, the diff checks them on the graph a save asks for, and
``repair_flow_data`` knows a fix for every one of them. Each rule has a stable
code so a refused write can name what is wrong and where.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any

from lfx.services.flow_operations.exceptions import FlowDataValidationError

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


@dataclass(frozen=True)
class GraphViolation:
    """One broken rule, where it was found, and a message without graph values."""

    code: GraphViolationCode
    path: GraphPath
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code.value, "path": list(self.path), "message": self.message}


def find_graph_violations(flow_data: Any, *, check_values: bool = True) -> list[GraphViolation]:
    """Return every rule ``flow_data`` breaks, in document order.

    ``check_values`` also walks every value for NaN and Infinity. The engine
    skips it when replaying stored operations, whose values were checked when
    they were written, so replay stays proportional to the number of nodes and
    edges rather than to the size of the flow.
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

    if check_values:
        violations.extend(_non_finite_violations(flow_data))
    return violations


def validate_flow_data(flow_data: Any, *, check_values: bool = True, context: str = "flow.data") -> None:
    """Raise ``FlowDataValidationError`` listing every violation, if there are any."""
    violations = find_graph_violations(flow_data, check_values=check_values)
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
