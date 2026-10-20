"""The JSON limits: no lone surrogates, and no nesting deeper than 127 levels."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from lfx.services.flow_operations import (
    FlowDataValidationError,
    FlowOperationValidationError,
    apply_flow_operations,
    canonical_graph_json,
    derive_flow_operations,
    diff_flow_data,
    find_graph_violations,
    graph_hash,
    parse_flow_operation,
    parse_flow_operations,
    repair_flow_data,
)
from lfx.services.flow_operations.canonical import canonical_json

FIXTURES = Path(__file__).resolve().parents[5] / "lfx-native" / "fixtures"
DOCUMENT = json.loads((FIXTURES / "limit_cases.json").read_text())
CASES = [*DOCUMENT["refused"], *DOCUMENT["accepted"]]


def _nested(levels: int) -> list:
    value: list = []
    for _ in range(levels - 1):
        value = [value]
    return value


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_limit_case(case):
    assert case.get("rule"), "every case names the rule it checks"
    value = json.loads(case["json"])

    if "error" in case:
        with pytest.raises(FlowDataValidationError) as exc_info:
            canonical_json(value)
        assert {"error": type(exc_info.value).__name__, "code": exc_info.value.code} == case["error"]
        return

    assert canonical_json(value) == case["canonical"]


def test_a_lone_surrogate_in_an_object_key_is_refused():
    with pytest.raises(FlowDataValidationError, match="lone surrogate"):
        canonical_json({"\udc00": 1})


def _set(value) -> dict:
    return {"type": "update_nodes", "updates": [{"op": "set_field", "id": "a", "path": ["x"], "value": value}]}


def test_parsed_operations_meet_the_limits():
    # The list is level 1, the operation 2, its updates 3 and the update 4,
    # so the value's arrays are levels 5 to 127.
    deep_value = _nested(123)
    parse_flow_operations([_set(deep_value)])

    with pytest.raises(FlowOperationValidationError, match="deeper than 127 levels") as exc_info:
        parse_flow_operations([_set([deep_value])])
    assert exc_info.value.code == "FLOW_OPERATION_INVALID"

    with pytest.raises(FlowOperationValidationError, match="lone surrogate"):
        parse_flow_operations([_set("\ud800")])
    with pytest.raises(FlowOperationValidationError, match="lone surrogate"):
        parse_flow_operation(_set("\ud800"))


def _graph_with_edge_handle(source_handle: str) -> tuple[dict, dict]:
    def node(node_id: str) -> dict:
        template = {"text": {"type": "str", "value": ""}}
        return {"id": node_id, "data": {"node": {"template": template, "outputs": [{"name": "out"}]}}}

    edge = {
        "id": "e",
        "source": "a",
        "target": "b",
        "sourceHandle": source_handle,
        "targetHandle": "{œfieldNameœ:œtextœ,œidœ:œbœ}",
        "data": {"sourceHandle": {"id": "a", "name": "out"}, "targetHandle": {"fieldName": "text", "id": "b"}},
    }
    return {"nodes": [node("a"), node("b")], "edges": []}, edge


@pytest.mark.parametrize(
    "source_handle",
    [
        "{œidœ:œaœ,œnameœ:œout\\ud800œ}",
        "{œidœ:œaœ,œnameœ:œoutœ,œxœ:" + "[" * 127 + "]" * 127 + "}",
    ],
    ids=["an escaped lone surrogate", "nesting 128 levels deep"],
)
def test_a_handle_string_that_breaks_a_limit_encodes_no_handle(source_handle):
    flow_data, edge = _graph_with_edge_handle("{œidœ:œaœ,œnameœ:œoutœ}")
    apply_flow_operations(copy.deepcopy(flow_data), parse_flow_operations([{"type": "add_edges", "edges": [edge]}]))

    edge["sourceHandle"] = source_handle
    with pytest.raises(FlowOperationValidationError, match="must be an escaped JSON object") as exc_info:
        apply_flow_operations(flow_data, parse_flow_operations([{"type": "add_edges", "edges": [edge]}]))
    assert exc_info.value.code == "EDGE_HANDLE_INVALID"


def _flow(value, **view_state) -> dict:
    node = {"id": "a", "data": {"node": {"template": {"x": {"value": value}}}}}
    return {"nodes": [node], "edges": [], **view_state}


# The flow is level 1, its nodes 2, the node 3, data 4, data.node 5, the
# template 6 and the field 7, so a value's arrays start at level 8.
DEEPEST = _flow(_nested(120))
BROKEN_GRAPHS = {
    "a lone surrogate": _flow("\udfff"),
    "a lone surrogate in a key": _flow({"\ud800": 1}),
    "nesting 128 levels deep": _flow(_nested(121)),
    "a lone surrogate in view state": _flow("ok", viewport={"label": "\ud800"}),
}
GRAPH_READERS = {
    "validation": find_graph_violations,
    "validation against a base": lambda graph: find_graph_violations(graph, base=DEEPEST),
    "repair": repair_flow_data,
    "the diff target": lambda graph: diff_flow_data(DEEPEST, graph),
    "derive": lambda graph: derive_flow_operations(DEEPEST, graph),
    "the canonical graph": canonical_graph_json,
    "the graph hash": graph_hash,
}


def test_a_graph_nested_127_levels_deep_is_read():
    assert find_graph_violations(DEEPEST) == []
    assert repair_flow_data(DEEPEST).fixes == []
    assert derive_flow_operations(DEEPEST, DEEPEST).operations == []
    graph_hash(DEEPEST)


@pytest.mark.parametrize("read", GRAPH_READERS.values(), ids=GRAPH_READERS.keys())
@pytest.mark.parametrize("graph", BROKEN_GRAPHS.values(), ids=BROKEN_GRAPHS.keys())
def test_a_graph_that_breaks_a_limit_is_refused_with_no_violations(read, graph):
    with pytest.raises(FlowDataValidationError, match="flow data is not valid JSON") as exc_info:
        read(copy.deepcopy(graph))
    assert exc_info.value.code == "FLOW_GRAPH_INVALID"
    assert exc_info.value.violations == []


def test_a_value_that_breaks_a_limit_is_refused_before_it_is_read_as_a_graph():
    for read in (find_graph_violations, repair_flow_data):
        with pytest.raises(FlowDataValidationError, match="lone surrogate"):
            read(["\ud800"])
