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
    parse_flow_operation,
    parse_flow_operations,
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
