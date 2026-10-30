"""Python objects as arguments and results: what the fixtures, which are JSON text, cannot show.

A Python value is read with the limits of the JSON parser, and refused with the
same engine error as text that does not parse. Results are Python values, with
numbers as ``json.loads`` reads their text.
"""

from __future__ import annotations

import json
import math

import pytest
from lfx_native import ops


def nested(depth: int, leaf: object, *, as_dict: bool = False) -> object:
    for _ in range(depth):
        leaf = {"x": leaf} if as_dict else [leaf]
    return leaf


def refused_as_text(value: object) -> bool:
    try:
        ops.canonical_json(json.dumps(value).encode())
    except ops.EngineError:
        return True
    return False


@pytest.mark.parametrize("as_dict", [False, True], ids=["lists", "dicts"])
def test_nesting_has_the_parser_limit(as_dict):
    deepest = nested(127, 1, as_dict=as_dict)
    too_deep = nested(128, 1, as_dict=as_dict)
    ops.canonical_json(deepest)
    with pytest.raises(ops.EngineError) as refused:
        ops.canonical_json(too_deep)
    assert (refused.value.kind, refused.value.code) == ("FlowDataValidationError", "FLOW_GRAPH_INVALID")
    # The same limit as the text of the same values.
    assert not refused_as_text(deepest)
    assert refused_as_text(too_deep)


def test_a_flow_nested_too_deep_is_refused():
    flow = {"nodes": [{"id": "a", "data": {"node": {"template": {"t": {"value": nested(122, 1)}}}}}], "edges": []}
    with pytest.raises(ops.EngineError) as refused:
        ops.graph_hash(flow)
    assert refused.value.code == "FLOW_GRAPH_INVALID"
    assert refused_as_text(flow)


@pytest.mark.parametrize(
    "value",
    [{"name": "\ud800"}, ["\udc00"], {"\ud800": 1}],
    ids=["value", "list item", "key"],
)
def test_a_lone_surrogate_is_refused(value):
    with pytest.raises(ops.EngineError) as refused:
        ops.canonical_json(value)
    assert (refused.value.kind, refused.value.code) == ("FlowDataValidationError", "FLOW_GRAPH_INVALID")


@pytest.mark.parametrize("number", [math.nan, math.inf, -math.inf], ids=["nan", "inf", "-inf"])
def test_a_number_that_is_not_finite_is_refused(number):
    with pytest.raises(ops.EngineError) as refused:
        ops.canonical_json({"n": number})
    assert refused.value.code == "FLOW_GRAPH_INVALID"


@pytest.mark.parametrize("value", [{1: "a"}, {"a": {1, 2}}, {"a": object()}], ids=["int key", "set", "object"])
def test_a_value_that_is_not_json_is_a_type_error(value):
    with pytest.raises(TypeError):
        ops.canonical_json(value)


def test_json_values_read_as_json_reads_them():
    assert ops.canonical_json((1, "a", None)) == '[1,"a",null]'
    assert ops.canonical_json([True, False, 1]) == "[true,false,1]"
    # A str is a JSON string, never text to parse.
    assert ops.canonical_json('{"a": 1}') == '"{\\"a\\": 1}"'
    assert [violation["code"] for violation in ops.validate("{}")] == ["FLOW_DATA_NOT_OBJECT"]


FLOW = {
    "nodes": [{"id": "a", "data": {"node": {"template": {"t": {"value": "x", "type": "str"}}}}}],
    "edges": [],
    "viewport": {"x": 0, "y": 0, "zoom": 1},
}


def set_value(value: object) -> list[dict]:
    return [
        {
            "type": "update_nodes",
            "updates": [
                {"id": "a", "op": "set_field", "path": ["data", "node", "template", "t", "value"], "value": value}
            ],
        }
    ]


@pytest.mark.parametrize("value", [1, 1.0, -0.0, 12345678901234567890123, 0.1, "é", None, True], ids=repr)
def test_values_come_back_as_given(value):
    state = ops.GraphState(FLOW)
    state.apply(set_value(value))
    result = state.to_dict()["nodes"][0]["data"]["node"]["template"]["t"]["value"]
    assert type(result) is type(value)
    assert result == value or (isinstance(value, float) and math.isnan(value))
    if isinstance(value, float):
        assert math.copysign(1, result) == math.copysign(1, value)


def test_numbers_come_back_as_json_loads_reads_their_text():
    flow = b'{"nodes": [], "edges": [], "a": 1e2, "b": 1, "c": 1.0, "d": 123456789012345678901234567890}'
    assert ops.GraphState(flow).to_dict() == json.loads(flow)
    assert [type(value) for value in ops.GraphState(flow).to_dict().values()][2:] == [float, int, float, int]


def test_text_and_objects_give_the_same_results():
    text = json.dumps(FLOW).encode()
    assert ops.graph_hash(text) == ops.graph_hash(FLOW)
    assert ops.diff(text, json.dumps(FLOW).encode()) == ops.diff(FLOW, FLOW) == []
    state = ops.GraphState(text)
    assert state.to_dict() == json.loads(state.to_json()) == FLOW


def test_error_details_are_a_dict():
    with pytest.raises(ops.EngineError) as refused:
        ops.GraphState(FLOW).apply([*set_value(1), {"type": "delete_nodes", "ids": "a"}])
    details = refused.value.details
    assert isinstance(details, dict)
    assert details["code"] == refused.value.code


def test_a_result_shares_each_key_as_json_loads_does():
    flow = {
        "nodes": [{"id": node, "data": {"node": {"template": {}}}} for node in ("a", "b")],
        "edges": [],
    }

    def data_key(node: dict) -> str:
        return next(key for key in node if key == "data")

    first, second = ops.GraphState(flow).to_dict()["nodes"]
    assert data_key(first) is data_key(second)
    parsed = json.loads(json.dumps(flow))["nodes"]
    assert data_key(parsed[0]) is data_key(parsed[1])
