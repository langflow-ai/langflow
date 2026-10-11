"""The rules an edge follows when a write adds it or changes its handles.

An edge connects one output of its source node to one input of its target
node, and its handles name them: ``sourceHandle.name`` is an output of the
source, and ``targetHandle.fieldName`` is a template field of the target. A
loop feedback edge instead names an output of its target, with
``targetHandle.name``, and that output must declare ``allows_loop``.

Every edge carries each handle twice: as an object under ``data``, and as an
escaped JSON string (``œ`` stands for ``"``). Both forms must be present and
agree. Nothing is exempt: group nodes are checked like any node, and an edge
may not touch a note, which has no handles.

The rules apply only to the edges a write adds or rewires. A stored edge that
breaks them stays until something touches it; but an edge whose handles a
rule must read, to see whether a field is taken or which edges a removed
output carries, is read strictly too.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from lfx.services.flow_operations.canonical import values_equal
from lfx.services.flow_operations.exceptions import FlowDataValidationError, FlowOperationValidationError
from lfx.services.flow_operations.schema import load_node_schema

if TYPE_CHECKING:
    from lfx.services.flow_operations.keyed_lists import ListIndex
    from lfx.services.flow_operations.state import GraphState

HANDLE_KEYS = ("sourceHandle", "targetHandle")
HANDLE_QUOTE = "œ"
NOTE_NODE_TYPE = "noteNode"
OUTPUTS_PATH = ("data", "node", "outputs")


class EdgeRuleCode(str, Enum):
    # A handle has one of its two forms, and the other is valid.
    HANDLE_FORM_MISSING = "EDGE_HANDLE_FORM_MISSING"
    # A handle is missing, is not an object, does not parse, or its forms disagree.
    HANDLE_INVALID = "EDGE_HANDLE_INVALID"
    # A handle names an output or field its node does not have.
    HANDLE_NOT_FOUND = "EDGE_HANDLE_NOT_FOUND"
    # A field that takes one connection, or a loop output, already has one.
    TARGET_OCCUPIED = "EDGE_TARGET_OCCUPIED"
    # An edge has a note at one end.
    TOUCHES_NOTE = "EDGE_TOUCHES_NOTE"


# The input an edge connects at its target: ("field", template key) or ("output", loop output name).
Input = tuple[str, str]


@dataclass(frozen=True)
class Handles:
    """The output an edge leaves from and the input it enters."""

    output: str
    input: Input


@dataclass
class Connections:
    """A node's edges, by the input they enter and the output they leave from."""

    inputs: defaultdict[Input, set[str]] = field(default_factory=lambda: defaultdict(set))
    outputs: defaultdict[str, set[str]] = field(default_factory=lambda: defaultdict(set))


def read_handles(edge: dict[str, Any]) -> Handles:
    """Read an edge's handles strictly: both forms present, the string parsing to the object."""
    source = _handle(edge, "sourceHandle")
    target = _handle(edge, "targetHandle")
    output = source.get("name")
    if not isinstance(output, str) or not output:
        raise _error(edge, EdgeRuleCode.HANDLE_INVALID, "sourceHandle must name an output")
    field_name = target.get("fieldName")
    loop_output = target.get("name")
    if (field_name is None) == (loop_output is None):
        raise _error(edge, EdgeRuleCode.HANDLE_INVALID, "targetHandle must name exactly one of a field or an output")
    name = field_name if field_name is not None else loop_output
    if not isinstance(name, str) or not name:
        raise _error(edge, EdgeRuleCode.HANDLE_INVALID, "targetHandle must name its field or output as a string")
    return Handles(output=output, input=("field", name) if field_name is not None else ("output", name))


def _handle(edge: dict[str, Any], key: str) -> dict[str, Any]:
    data = edge.get("data")
    if data is not None and not isinstance(data, dict):
        raise _error(edge, EdgeRuleCode.HANDLE_INVALID, "data must be an object")
    has_object = data is not None and key in data
    has_string = key in edge
    if has_object and not isinstance(data[key], dict):
        raise _error(edge, EdgeRuleCode.HANDLE_INVALID, f"data.{key} must be an object")
    if has_string:
        parsed = _parse_handle(edge[key])
        if parsed is None:
            raise _error(edge, EdgeRuleCode.HANDLE_INVALID, f"{key} must be an escaped JSON object")
        if has_object and not values_equal(parsed, data[key]):
            raise _error(edge, EdgeRuleCode.HANDLE_INVALID, f"{key} and data.{key} name different handles")
    if has_object and has_string:
        return data[key]
    if has_object or has_string:
        missing = key if has_object else f"data.{key}"
        raise _error(edge, EdgeRuleCode.HANDLE_FORM_MISSING, f"{missing} is missing")
    raise _error(edge, EdgeRuleCode.HANDLE_INVALID, f"edge has no {key}")


def _parse_handle(handle: Any) -> dict[str, Any] | None:
    if not isinstance(handle, str):
        return None
    try:
        parsed = json.loads(handle.replace(HANDLE_QUOTE, '"'))
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def check_edge(state: GraphState, edge: dict[str, Any]) -> Handles:
    """Check an edge a write adds or rewires, and return its handles.

    The edge must not touch a note, its handles must be valid and name an
    output of its source and an input of its target, and a single input must
    not be taken by another edge.
    """
    for end in ("source", "target"):
        if state.nodes_by_id[edge[end]].get("type") == NOTE_NODE_TYPE:
            raise _error(edge, EdgeRuleCode.TOUCHES_NOTE, f"its {end} {edge[end]!r} is a note, which has no handles")
    handles = state.handles(edge)

    source_outputs = node_outputs(state, edge["source"])
    if source_outputs is None or handles.output not in source_outputs.by_key:
        raise _error(
            edge, EdgeRuleCode.HANDLE_NOT_FOUND, f"source node {edge['source']!r} has no output {handles.output!r}"
        )

    kind, name = handles.input
    target_id = edge["target"]
    if kind == "field":
        template = node_body(state, target_id).get("template")
        if not isinstance(template, dict):
            msg = f"node {target_id!r}: data.node.template must be an object"
            raise FlowDataValidationError(msg)
        target_field = template.get(name)
        if not isinstance(target_field, dict):
            raise _error(edge, EdgeRuleCode.HANDLE_NOT_FOUND, f"target node {target_id!r} has no field {name!r}")
        single = target_field.get("list") is not True
    else:
        target_outputs = node_outputs(state, target_id)
        loop_output = target_outputs.by_key.get(name) if target_outputs is not None else None
        if loop_output is None or loop_output.get("allows_loop") is not True:
            raise _error(edge, EdgeRuleCode.HANDLE_NOT_FOUND, f"target node {target_id!r} has no loop output {name!r}")
        single = True

    if single:
        others = state.connections(target_id).inputs.get(handles.input, set()) - {edge["id"]}
        if others:
            raise _error(
                edge,
                EdgeRuleCode.TARGET_OCCUPIED,
                f"{kind} {name!r} of node {target_id!r} takes one connection and already has {min(others)!r}",
            )
    return handles


def node_body(state: GraphState, node_id: str) -> dict[str, Any]:
    """Return a node's ``data.node``, which every node carries as an object."""
    data = state.nodes_by_id[node_id].get("data")
    body = data.get("node") if isinstance(data, dict) else None
    if not isinstance(body, dict):
        msg = f"node {node_id!r}: data.node must be an object"
        raise FlowDataValidationError(msg)
    return body


def node_outputs(state: GraphState, node_id: str) -> ListIndex | None:
    """Return the index of a node's outputs, or None for a node without an ``outputs`` key."""
    body = node_body(state, node_id)
    if "outputs" not in body:
        return None
    outputs = body["outputs"]
    if not isinstance(outputs, list):
        msg = f"node {node_id!r}: data.node.outputs must be a list"
        raise FlowDataValidationError(msg)
    keyed = load_node_schema().keyed_list_at(state.nodes_by_id[node_id], OUTPUTS_PATH)
    return state.list_index(keyed, outputs, context=f"node {node_id!r}: data.node.outputs")


def _error(edge: dict[str, Any], code: EdgeRuleCode, reason: str) -> FlowOperationValidationError:
    return FlowOperationValidationError(f"edge {edge.get('id')!r}: {reason}", code=code.value)
