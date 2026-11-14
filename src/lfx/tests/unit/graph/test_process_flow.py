"""Group expansion preserves the payload while copying each flow only once."""

import copy

import pytest
from lfx.graph.graph import utils


def _node(node_id):
    return {
        "id": node_id,
        "data": {
            "id": node_id,
            "type": "Example",
            "node": {
                "template": {
                    "input_value": {"value": node_id, "show": True, "advanced": False, "name": "Input"},
                },
                "outputs": [{"name": "output", "types": ["Message"]}],
            },
        },
    }


def _group(group_id, nodes, edges=()):
    node = _node(group_id)
    node["data"]["node"]["flow"] = {"data": {"nodes": nodes, "edges": list(edges)}}
    node["data"]["node"]["template"] = {}
    node["data"]["node"]["outputs"] = []
    return node


def _edge(source, target, *, proxy=None):
    target_handle = {"id": target, "fieldName": "input_value", "type": "str", "inputTypes": ["Message"]}
    if proxy is not None:
        target_handle["proxy"] = {"id": proxy, "field": "input_value"}
    return {
        "id": f"{source}-{target}",
        "source": source,
        "target": target,
        "data": {
            "sourceHandle": {"id": source, "name": "output", "dataType": "Example", "output_types": ["Message"]},
            "targetHandle": target_handle,
        },
    }


def _expanded(node, parent):
    node["parent_node_id"] = parent
    node["data"]["node"]["frozen"] = False
    return node


@pytest.mark.parametrize("depth", [0, 1, 3, 6])
def test_nested_groups_copy_flow_once(monkeypatch, depth):
    flow = {"nodes": [_node("leaf")], "edges": []}
    for level in range(depth):
        flow = {"nodes": [_group(f"group-{level}", flow["nodes"])], "edges": []}
    original = copy.deepcopy(flow)
    deepcopy = copy.deepcopy
    flow_copies = []

    def count_flow_copies(value, *args, **kwargs):
        if isinstance(value, dict) and "nodes" in value and "edges" in value:
            flow_copies.append(value)
        return deepcopy(value, *args, **kwargs)

    monkeypatch.setattr(utils.copy, "deepcopy", count_flow_copies)
    result = utils.process_flow(flow)

    expected = _node("leaf") if depth == 0 else _expanded(_node("leaf"), "group-0")
    assert result == {"nodes": [expected], "edges": []}
    assert flow == original
    assert len(flow_copies) == 1


def test_nested_sibling_groups_and_boundary_edges():
    a, b, c = (_node(name) for name in ("a", "b", "c"))
    inner = _group("inner", [a, b], [_edge("a", "b")])
    inner["data"]["node"]["outputs"] = [{"name": "output", "proxy": {"id": "b", "name": "output"}}]
    outer = _group("outer", [inner], [])
    sibling = _group("sibling", [c])
    sibling["data"]["node"]["template"] = {
        "input_value": {"proxy": {"id": "c", "field": "input_value"}, "value": "override"},
    }
    outer["data"]["node"]["outputs"] = [{"name": "output", "proxy": {"id": "inner", "name": "output"}}]
    flow = {
        "nodes": [outer, sibling, _node("end")],
        "edges": [_edge("outer", "sibling", proxy="c"), _edge("sibling", "end")],
        "viewport": {"x": 12, "y": 34, "zoom": 0.5},
    }
    original = copy.deepcopy(flow)

    result = utils.process_flow(flow)

    expected_c = _expanded(_node("c"), "sibling")
    expected_c["data"]["node"]["template"]["input_value"] = {
        "proxy": {"id": "c", "field": "input_value"},
        "value": "override",
        "show": True,
        "advanced": False,
        "display_name": "Input",
    }
    first_edge = _edge("c", "end")
    first_edge["id"] = "sibling-end"
    second_edge = _edge("b", "c")
    second_edge["id"] = "outer-sibling"
    assert result == {
        "nodes": [_node("end"), expected_c, _expanded(_node("a"), "inner"), _expanded(_node("b"), "inner")],
        "edges": [first_edge, _edge("a", "b"), second_edge],
        "viewport": flow["viewport"],
    }
    assert flow == original
    result["nodes"][1]["data"]["node"]["template"]["input_value"]["value"] = "changed"
    assert flow == original


def test_empty_groups():
    flow = {"nodes": [_group("empty", []), _node("leaf"), _group("nested", [_group("also-empty", [])])], "edges": []}
    original = copy.deepcopy(flow)
    assert utils.process_flow(flow) == {"nodes": [_node("leaf")], "edges": []}
    assert flow == original


@pytest.mark.parametrize("malformed", ["missing-node", "missing-field", "missing-type"])
def test_malformed_group_references(malformed):
    group = _group("group", [_node("leaf")])
    edge = _edge("group", "end")
    error, match = ValueError, "missing node missing"
    if malformed == "missing-node":
        group["data"]["node"]["outputs"] = [{"name": "output", "proxy": {"id": "missing", "name": "output"}}]
    elif malformed == "missing-field":
        group["data"]["node"]["template"] = {"input_value": {"proxy": {"id": "leaf", "field": "missing"}}}
        error, match = KeyError, "missing"
    else:
        edge = _edge("start", "group", proxy="leaf")
        del edge["data"]["targetHandle"]["type"]
        error, match = KeyError, "'type' key must be present"
    flow = {"nodes": [group, _node("end")], "edges": [edge]}
    original = copy.deepcopy(flow)
    with pytest.raises(error, match=match):
        utils.process_flow(flow)
    assert flow == original
