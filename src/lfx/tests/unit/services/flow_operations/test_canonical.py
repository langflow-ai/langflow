"""Canonical form: RFC 8785 serialization, value equality and graph equality."""

from __future__ import annotations

import itertools
import math

import pytest
from lfx.services.flow_operations import (
    FlowDataValidationError,
    canonical_graph_json,
    canonical_json,
    graph_hash,
    graphs_equal,
    json_type,
    parse_handle,
    values_equal,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "0"),
        (-0.0, "0"),
        (1.0, "1"),
        (-1.5, "-1.5"),
        (0.1, "0.1"),
        (123.456, "123.456"),
        (1e20, "100000000000000000000"),
        (1e21, "1e+21"),
        (1.5e21, "1.5e+21"),
        (0.000001, "0.000001"),
        (1e-7, "1e-7"),
        (1.25e-7, "1.25e-7"),
        (5e-324, "5e-324"),
        (1.7976931348623157e308, "1.7976931348623157e+308"),
        (333333333.3333333, "333333333.3333333"),
        (2**53, "9007199254740992"),
        # Beyond 2**53 an integer is printed as the double JavaScript rounds it to.
        (2**53 + 1, "9007199254740992"),
    ],
)
def test_numbers_print_as_javascript_does(value, expected):
    assert canonical_json(value) == expected


def test_object_keys_sort_by_utf16_code_units():
    # The RFC 8785 sorting example: code-point order would put the emoji last.
    value = {"\u20ac": 1, "\r": 2, "\ufb33": 3, "1": 4, "\U0001f600": 5, "\u0080": 6, "\u00f6": 7}

    assert canonical_json(value) == '{"\\r":2,"1":4,"\u0080":6,"\u00f6":7,"\u20ac":1,"\U0001f600":5,"\ufb33":3}'


def test_strings_escape_only_what_json_requires():
    assert canonical_json('a"b\\c\n\u0001é/') == '"a\\"b\\\\c\\n\\u0001é/"'


def test_literals_and_containers():
    assert canonical_json({"b": [True, False, None], "a": {}}) == '{"a":{},"b":[true,false,null]}'


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_non_finite_numbers_are_rejected(value):
    with pytest.raises(FlowDataValidationError):
        canonical_json({"x": value})


def test_non_json_values_are_rejected():
    with pytest.raises(FlowDataValidationError):
        canonical_json({"x": object()})
    with pytest.raises(FlowDataValidationError):
        canonical_json({1: "x"})


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({}, "object"),
        ([], "array"),
        ("", "string"),
        (1, "number"),
        (1.5, "number"),
        (True, "boolean"),
        (None, "null"),
    ],
)
def test_json_type(value, expected):
    assert json_type(value) == expected


def _graph(**overrides):
    graph = {
        "nodes": [
            {"id": "b", "position": {"x": 1.0, "y": 0}, "data": {"node": {"template": {}}}},
            {"id": "a", "position": {"x": 0, "y": 0}, "data": {"node": {"template": {}}}},
        ],
        "edges": [{"id": "e", "source": "a", "target": "b"}],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }
    graph.update(overrides)
    return graph


def test_node_and_edge_order_is_not_state():
    reordered = _graph()
    reordered["nodes"].reverse()

    assert graphs_equal(_graph(), reordered)
    assert graph_hash(_graph()) == graph_hash(reordered)


def test_view_state_is_not_state():
    viewed = _graph(viewport={"x": 50, "y": 50, "zoom": 2})
    viewed["nodes"][0].update(selected=True, dragging=False, resizing=False, measured={"width": 10, "height": 5})
    viewed["edges"][0].update(selected=True, animated=True, className="running")

    assert graphs_equal(_graph(), viewed)
    assert graph_hash(_graph()) == graph_hash(viewed)


def test_integer_and_float_forms_of_a_number_are_equal():
    as_int = _graph()
    as_int["nodes"][0]["position"]["x"] = 1

    assert graphs_equal(_graph(), as_int)


def test_boolean_and_number_are_different():
    as_bool = _graph()
    as_bool["nodes"][0]["position"]["x"] = True

    assert not graphs_equal(_graph(), as_bool)
    assert graph_hash(_graph()) != graph_hash(as_bool)


def test_size_is_view_state_but_position_is_state():
    resized = _graph()
    resized["nodes"][0].update(width=300, height=120)
    moved = _graph()
    moved["nodes"][0]["position"] = {"x": 5, "y": 0}

    assert graphs_equal(_graph(), resized)
    assert not graphs_equal(_graph(), moved)


def test_canonical_graph_orders_nodes_by_id():
    assert canonical_graph_json(_graph()).index('"id":"a"') < canonical_graph_json(_graph()).index('"id":"b"')


SAMPLES = [
    None,
    True,
    False,
    0,
    0.0,
    -0.0,
    1,
    1.0,
    1.5,
    2**53,
    2**53 + 1,
    float(2**53),
    1e21,
    "",
    "a",
    "1",
    [],
    [1],
    [1.0],
    [1, 2],
    [2, 1],
    {},
    {"a": 1},
    {"a": 1.0},
    {"b": 1},
    {"a": 1, "b": [True, None]},
    {"b": [True, None], "a": 1},
    {"a": {"b": {"c": 0}}},
    {"a": {"b": {"c": -0.0}}},
    {"a": {"b": {"c": 1}}},
]


@pytest.mark.parametrize(("left", "right"), list(itertools.product(SAMPLES, repeat=2)))
def test_equality_matches_the_canonical_form(left, right):
    assert values_equal(left, right) == (canonical_json(left) == canonical_json(right))


def test_numbers_compare_as_the_doubles_javascript_holds():
    assert values_equal(1, 1.0)
    assert values_equal(0, -0.0)
    assert values_equal(2**53 + 1, 2**53)
    assert not values_equal(left=True, right=1)


@pytest.mark.parametrize(
    ("left", "right"),
    [(float("nan"), 1.0), (1.0, float("inf")), ([1, float("-inf")], [1, 2])],
)
def test_non_finite_numbers_are_not_json(left, right):
    with pytest.raises(FlowDataValidationError, match="not valid JSON numbers"):
        values_equal(left, right)


def test_object_keys_must_be_strings():
    with pytest.raises(FlowDataValidationError, match="is not a string"):
        values_equal({1: "a"}, {"1": "a"})


def _table_graph(rows: list[dict]) -> dict:
    template = {"rows": {"type": "table", "value": rows}}
    return {"nodes": [{"id": "t", "data": {"node": {"template": template}}}], "edges": []}


def test_table_row_order_is_not_state():
    rows = [{"_id": "a", "_pos": 1, "v": "x"}, {"_id": "b", "_pos": 2, "v": "y"}]
    reordered = _table_graph(list(reversed(rows)))

    assert graphs_equal(_table_graph(rows), reordered)
    assert graph_hash(_table_graph(rows)) == graph_hash(reordered)


def test_a_legacy_table_without_row_ids_keeps_its_order():
    rows = [{"v": "x"}, {"v": "y"}]

    assert not graphs_equal(_table_graph(rows), _table_graph(list(reversed(rows))))


def test_handles_compare_by_the_object_they_encode():
    edge = {"id": "e", "source": "a", "target": "b", "sourceHandle": "{œnameœ:œoutœ,œidœ:œaœ}"}
    respelled = {**edge, "sourceHandle": "{œidœ: œaœ, œnameœ: œoutœ}"}
    graph = _graph(edges=[edge])
    other = _graph(edges=[respelled])

    assert graphs_equal(graph, other)
    assert graph_hash(graph) == graph_hash(other)


# The editor's canonical tests read the same strings: JSON.parse refuses these tokens.
@pytest.mark.parametrize(
    "handle", ["{œnameœ:œoutœ,œxœ:NaN}", "{œnameœ:œoutœ,œxœ:Infinity}", "{œnameœ:œoutœ,œxœ:-Infinity}"]
)
def test_a_handle_string_with_a_non_finite_token_does_not_parse(handle):
    assert parse_handle(handle) is None


@pytest.mark.parametrize(
    "change",
    [
        lambda graph: graph["nodes"][0]["position"].update(x=5),
        lambda graph: graph["edges"][0].update(target="a"),
        lambda graph: graph.update(description="changed"),
        lambda graph: graph["nodes"].pop(),
    ],
)
def test_equality_agrees_with_the_hash(change):
    changed = _graph()
    change(changed)

    assert graphs_equal(_graph(), changed) is (graph_hash(_graph()) == graph_hash(changed))
