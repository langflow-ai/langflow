"""Deriving operations from whole-flow saves."""

from __future__ import annotations

import copy
import math

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from lfx.services.flow_operations import (
    AddEdgesOp,
    AddNodesOp,
    DeleteEdgesOp,
    DeleteNodesOp,
    FlowDataValidationError,
    KeySelector,
    UpdateEdgesOp,
    UpdateMetadataOp,
    UpdateNodesOp,
    apply_flow_operations,
    derive_flow_operations,
    diff_flow_data,
    graphs_equal,
)


def _node(node_id: str, **template) -> dict:
    return {
        "id": node_id,
        "type": "genericNode",
        "position": {"x": 0, "y": 0},
        "data": {"id": node_id, "type": "Prompt", "node": {"display_name": node_id, "template": template}},
    }


def _edge(edge_id: str, source: str, target: str) -> dict:
    return {"id": edge_id, "source": source, "target": target, "sourceHandle": "s", "targetHandle": "t"}


def _graph() -> dict:
    return {
        "nodes": [
            _node("a", text={"name": "text", "type": "str", "value": "hi"}),
            _node("b", api_key={"name": "api_key", "type": "str", "password": True, "value": "sk"}),
        ],
        "edges": [_edge("e-ab", "a", "b")],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
        "description": "demo",
    }


def _template(graph: dict, node_id: str) -> dict:
    node = next(node for node in graph["nodes"] if node["id"] == node_id)
    return node["data"]["node"]["template"]


def _replays(base: dict, target: dict) -> list:
    """Diff, then apply the operations one at a time, as history replay does."""
    operations = diff_flow_data(base, target)
    graph = base
    for operation in operations:
        graph = apply_flow_operations(graph, [operation]).flow_data
    assert graphs_equal(graph, target)
    return operations


def test_identical_graphs_produce_no_operations():
    assert diff_flow_data(_graph(), _graph()) == []


def test_reordering_nodes_and_edges_produces_no_operations():
    target = _graph()
    target["nodes"].reverse()

    assert diff_flow_data(_graph(), target) == []


def test_view_state_changes_produce_no_operations():
    target = _graph()
    target["viewport"] = {"x": 10, "y": 10, "zoom": 3}
    target["nodes"][0].update(selected=True, dragging=True, measured={"width": 1, "height": 1})
    target["edges"][0].update(selected=True, animated=True, className="running")

    assert diff_flow_data(_graph(), target) == []


def test_integer_and_float_forms_of_a_number_produce_no_operations():
    base = _graph()
    base["nodes"][0]["position"]["x"] = 0.0

    assert diff_flow_data(base, _graph()) == []


def test_a_field_edit_is_one_set_field():
    target = _graph()
    _template(target, "a")["text"]["value"] = "hello"

    operations = _replays(_graph(), target)

    assert operations == [
        UpdateNodesOp(
            type="update_nodes",
            updates=[
                {
                    "id": "a",
                    "op": "set_field",
                    "path": ["data", "node", "template", "text", "value"],
                    "value": "hello",
                    "template_field": {"name": "text", "type": "str"},
                }
            ],
        )
    ]


def test_a_type_change_declares_the_replaced_type():
    target = _graph()
    _template(target, "a")["text"]["value"] = 1

    (operation,) = _replays(_graph(), target)

    assert operation.updates[0].from_type == "string"


def test_a_boolean_replacing_a_number_is_a_type_change():
    base = _graph()
    _template(base, "a")["text"]["value"] = 1
    target = copy.deepcopy(base)
    _template(target, "a")["text"]["value"] = True

    (operation,) = _replays(base, target)

    assert operation.updates[0].from_type == "number"


def test_template_field_metadata_is_recorded_only_inside_a_field():
    target = _graph()
    _template(target, "b")["api_key"]["value"] = "sk-new"
    _template(target, "a")["new_field"] = {"name": "new_field", "type": "str", "value": "x"}
    target["nodes"][0]["position"] = {"x": 5, "y": 0}

    (operation,) = _replays(_graph(), target)
    by_path = {tuple(update.path): update for update in operation.updates}

    assert by_path[("data", "node", "template", "api_key", "value")].template_field == {
        "name": "api_key",
        "type": "str",
        "password": True,
    }
    assert by_path[("data", "node", "template", "new_field")].template_field is None
    assert by_path[("position",)].template_field is None


def test_a_removed_definition_key_rewrites_the_definition_unit():
    target = _graph()
    del _template(target, "a")["text"]["type"]

    (operation,) = _replays(_graph(), target)

    assert [(update.op, update.path) for update in operation.updates] == [
        ("set_field", ("data", "node", "template", "text", "name")),
        ("delete_field", ("data", "node", "template", "text", "type")),
    ]


def test_arrays_outside_keyed_lists_are_replaced_whole():
    base = _graph()
    base["nodes"][0]["data"]["node"]["base_classes"] = ["Message", "Data"]
    target = copy.deepcopy(base)
    target["nodes"][0]["data"]["node"]["base_classes"][1] = "Text"

    (operation,) = _replays(base, target)

    assert [tuple(update.path) for update in operation.updates] == [("data", "node", "base_classes")]


def test_outputs_are_written_per_item():
    base = _graph()
    base["nodes"][0]["data"]["node"]["outputs"] = [{"name": "a"}, {"name": "b"}]
    target = copy.deepcopy(base)
    target["nodes"][0]["data"]["node"]["outputs"][1] = {"name": "c"}

    (operation,) = _replays(base, target)

    assert [(update.op, update.path) for update in operation.updates] == [
        ("set_field", ("data", "node", "outputs", KeySelector(key="c"))),
        ("delete_field", ("data", "node", "outputs", KeySelector(key="b"))),
    ]


def test_a_changed_edge_between_the_same_nodes_is_updated_in_place():
    target = _graph()
    target["edges"][0]["targetHandle"] = "other"

    operations = _replays(_graph(), target)

    assert operations == [
        UpdateEdgesOp(
            type="update_edges",
            updates=[{"id": "e-ab", "op": "set_field", "path": ["targetHandle"], "value": "other"}],
        )
    ]


def test_an_edge_reconnected_to_another_node_is_deleted_and_added():
    target = _graph()
    target["nodes"].append(_node("c"))
    target["edges"][0]["target"] = "c"

    operations = _replays(_graph(), target)

    assert operations[0] == DeleteEdgesOp(type="delete_edges", ids=["e-ab"])
    assert operations[-1] == AddEdgesOp(type="add_edges", edges=[target["edges"][0]])


def test_deleting_a_node_deletes_its_edges_explicitly_first():
    target = _graph()
    target["nodes"] = [node for node in target["nodes"] if node["id"] != "b"]
    target["edges"] = []

    operations = _replays(_graph(), target)

    assert operations == [
        DeleteEdgesOp(type="delete_edges", ids=["e-ab"]),
        DeleteNodesOp(type="delete_nodes", ids=["b"]),
    ]


def test_operation_types_come_in_a_fixed_order_and_list_items_by_id():
    target = _graph()
    target["nodes"] = [node for node in target["nodes"] if node["id"] != "b"]
    target["nodes"] += [_node("d"), _node("c")]
    target["edges"] = [_edge("e-dc", "d", "c"), _edge("e-ac", "a", "c")]
    target["nodes"][0]["position"] = {"x": 1, "y": 1}
    target["description"] = "changed"
    selected = copy.deepcopy(target)
    selected["nodes"][1]["selected"] = True

    operations = _replays(_graph(), selected)

    assert [operation.type for operation in operations] == [
        "delete_edges",
        "delete_nodes",
        "add_nodes",
        "update_nodes",
        "add_edges",
        "update_metadata",
    ]
    add_nodes = operations[2]
    assert isinstance(add_nodes, AddNodesOp)
    assert [node["id"] for node in add_nodes.nodes] == ["c", "d"]
    # Added nodes carry no view state.
    assert all("selected" not in node for node in add_nodes.nodes)
    assert [edge["id"] for edge in operations[4].edges] == ["e-ac", "e-dc"]


def test_metadata_changes_exclude_viewport_and_graph_collections():
    target = _graph()
    target["description"] = "changed"
    target["notes"] = {"k": "v"}
    target["viewport"] = {"x": 1, "y": 1, "zoom": 1}
    base = _graph()
    base["legacy"] = True

    operations = _replays(base, target)

    assert operations == [
        UpdateMetadataOp(
            type="update_metadata",
            fields={"description": "changed", "notes": {"k": "v"}},
            delete_keys=["legacy"],
        )
    ]


@pytest.mark.parametrize(
    "break_target",
    [
        lambda graph: graph["nodes"].append(copy.deepcopy(graph["nodes"][0])),
        lambda graph: graph["edges"].append({"id": "e-x", "source": "a"}),
        lambda graph: graph["edges"].append({"source": "a", "target": "b"}),
        lambda graph: graph["nodes"][0]["data"].pop("node"),
        lambda graph: graph["nodes"][0]["data"]["node"].update(template=[]),
        lambda graph: graph["nodes"][0]["position"].update(x=math.nan),
    ],
    ids=["duplicate node", "edge without target", "edge without id", "no data.node", "template list", "nan"],
)
def test_a_target_that_breaks_the_rules_fails_validation_not_replay(break_target):
    target = _graph()
    break_target(target)

    with pytest.raises(FlowDataValidationError):
        derive_flow_operations(_graph(), target)


def test_derive_returns_the_replayed_graph():
    target = _graph()
    _template(target, "a")["text"]["value"] = "hello"

    derived = derive_flow_operations(_graph(), target)

    assert graphs_equal(derived.flow_data, target)
    assert len(derived.operations) == 1


def test_diff_does_not_mutate_its_inputs():
    base, target = _graph(), _graph()
    target["nodes"].append(_node("c"))
    target["nodes"][0]["position"]["x"] = 9
    base_copy, target_copy = copy.deepcopy(base), copy.deepcopy(target)

    derive_flow_operations(base, target)

    assert base == base_copy
    assert target == target_copy


# --- Property: apply(base, diff(base, target)) == target for any valid pair ---

_KEYS = st.sampled_from(["a", "b", "c", "value", "type"])
_LEAVES = (
    st.none()
    | st.booleans()
    | st.integers(min_value=-(2**40), max_value=2**40)
    | st.floats(allow_nan=False, allow_infinity=False, width=64)
    | st.text(max_size=4)
)
_JSON = st.recursive(
    _LEAVES,
    lambda children: st.lists(children, max_size=3) | st.dictionaries(_KEYS, children, max_size=3),
    max_leaves=8,
)


@st.composite
def _graphs(draw):
    node_ids = draw(st.lists(st.sampled_from(["n1", "n2", "n3", "n4", "n5"]), unique=True, max_size=5))
    nodes = []
    for node_id in node_ids:
        node = {
            "id": node_id,
            "position": {"x": draw(_LEAVES), "y": 0},
            "data": {
                "type": draw(st.sampled_from(["Prompt", "ChatInput"])),
                "node": {
                    "template": draw(st.dictionaries(_KEYS, st.dictionaries(_KEYS, _JSON, max_size=3), max_size=3)),
                    "extra": draw(_JSON),
                },
            },
        }
        if draw(st.booleans()):
            node["selected"] = draw(st.booleans())
        nodes.append(node)

    edge_ids = draw(st.lists(st.sampled_from(["e1", "e2", "e3", "e4"]), unique=True, max_size=4)) if node_ids else []
    edges = [
        {
            "id": edge_id,
            "source": draw(st.sampled_from(node_ids)),
            "target": draw(st.sampled_from(node_ids)),
            "data": draw(_JSON),
        }
        for edge_id in edge_ids
    ]
    graph = {"nodes": draw(st.permutations(nodes)), "edges": edges}
    graph.update(draw(st.dictionaries(st.sampled_from(["description", "notes", "viewport"]), _JSON, max_size=2)))
    return graph


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(base=_graphs(), target=_graphs())
def test_any_valid_transition_replays_exactly(base, target):
    base_copy = copy.deepcopy(base)

    _replays(base, target)
    derived = derive_flow_operations(base, target)

    assert graphs_equal(derived.flow_data, target)
    assert base == base_copy
    # A second diff from the result finds nothing left to change.
    assert diff_flow_data(derived.flow_data, target) == []
