"""Run copies are deep-copied once, and nothing they change reaches the template or another run."""

import copy

import pytest
from lfx.graph import Graph
from lfx.graph.graph import base as graph_base


def _node(node_id: str, *, headers: dict | None = None) -> dict:
    template = {
        "_type": "Generic",
        "stream": {"name": "stream", "type": "bool", "value": True, "list": False, "show": True, "advanced": False},
        "headers": {
            "name": "headers",
            "type": "dict",
            "value": headers or {"a": "1"},
            "list": False,
            "show": True,
            "advanced": False,
        },
    }
    return {
        "id": node_id,
        "type": "genericNode",
        "data": {
            "id": node_id,
            "type": "Generic",
            "node": {"template": template, "base_classes": [], "display_name": node_id, "outputs": []},
        },
    }


def _flat_flow() -> dict:
    return {"nodes": [_node("first"), _node("second")], "edges": []}


def _grouped_flow() -> dict:
    group = {
        "id": "group-1",
        "type": "genericNode",
        "data": {
            "id": "group-1",
            "type": "Group",
            "node": {
                "template": {
                    "headers": {
                        "name": "headers",
                        "type": "dict",
                        "value": {"proxied": "yes"},
                        "show": True,
                        "proxy": {"field": "headers", "id": "child-1"},
                    }
                },
                "flow": {"data": {"nodes": [_node("child-1")], "edges": []}},
            },
        },
    }
    return {"nodes": [group], "edges": []}


def _template(flow: dict) -> Graph:
    template = Graph(flow_id="flow-id", instantiate_components=False)
    template.add_nodes_and_edges(flow["nodes"], flow["edges"])
    return template


def _mutable_ids(graph: Graph) -> set[int]:
    """Ids of every dict and list a run can reach through the graph's flow data and vertices."""
    ids: set[int] = set()
    stack: list = [graph.raw_graph_data, graph._graph_data]
    stack += [vertex.full_data for vertex in graph.vertices]
    stack += [vertex.params for vertex in graph.vertices]
    while stack:
        obj = stack.pop()
        if isinstance(obj, dict | list) and id(obj) not in ids:
            ids.add(id(obj))
            stack.extend(obj.values() if isinstance(obj, dict) else obj)
    return ids


@pytest.fixture(autouse=True)
def _no_component_construction(monkeypatch):
    monkeypatch.setattr(Graph, "_instantiate_components_in_vertices", lambda _graph: None)


@pytest.fixture
def process_flow_calls(monkeypatch):
    calls: list[int] = []
    original = graph_base.process_flow

    def counting_process_flow(flow):
        calls.append(len(flow["nodes"]))
        return original(flow)

    monkeypatch.setattr(graph_base, "process_flow", counting_process_flow)
    return calls


def test_flat_run_copy_builds_vertices_from_its_own_copy(process_flow_calls):
    template = _template(_flat_flow())
    process_flow_calls.clear()

    run = template.copy_for_run(user_id="caller")

    assert process_flow_calls == []
    for node in run.raw_graph_data["nodes"]:
        assert run.get_vertex(node["id"]).full_data["data"] is node["data"]
    # Later structural additions go to the graph's own lists, not to its raw flow data.
    assert run._vertices is not run.raw_graph_data["nodes"]
    assert run._edges is not run.raw_graph_data["edges"]


def test_run_copies_share_no_mutable_data_with_the_template_or_each_other():
    template = _template(_flat_flow())

    first = template.copy_for_run(user_id="caller-1")
    second = template.copy_for_run(user_id="caller-2")

    template_ids, first_ids, second_ids = _mutable_ids(template), _mutable_ids(first), _mutable_ids(second)
    assert not template_ids & first_ids
    assert not template_ids & second_ids
    assert not first_ids & second_ids


def test_in_place_edits_in_a_run_copy_stay_in_that_run():
    template = _template(_flat_flow())
    pristine = copy.deepcopy(template.raw_graph_data)

    first = template.copy_for_run(user_id="caller-1")
    # A component that edits its dict input in place, and a stream-mode override of a field.
    first.get_vertex("first").params["headers"]["added"] = "by run 1"
    first.get_vertex("second").data["node"]["template"]["stream"]["value"] = False
    second = template.copy_for_run(user_id="caller-2")

    assert template.raw_graph_data == pristine
    assert template.get_vertex("first").params["headers"] == {"a": "1"}
    assert second.raw_graph_data == pristine
    assert second.get_vertex("first").params["headers"] == {"a": "1"}
    assert second.get_vertex("second").data["node"]["template"]["stream"]["value"] is True
    # The single copy belongs to the run, so its own flow data shows the run's edits.
    assert first.raw_graph_data["nodes"][0]["data"]["node"]["template"]["headers"]["value"] == {
        "a": "1",
        "added": "by run 1",
    }


def test_grouped_run_copy_keeps_its_raw_flow_data_in_frontend_shape(process_flow_calls):
    """Expanding groups edits the copy it works on, so grouped flows keep the second copy."""
    template = _template(_grouped_flow())
    pristine = copy.deepcopy(template.raw_graph_data)
    process_flow_calls.clear()

    run = template.copy_for_run(user_id="caller")

    assert process_flow_calls == [1]
    assert run.raw_graph_data == pristine
    child = run.raw_graph_data["nodes"][0]["data"]["node"]["flow"]["data"]["nodes"][0]
    assert "parent_node_id" not in child["data"]["node"]
    assert child["data"]["node"]["template"]["headers"]["value"] == {"a": "1"}
    assert run.get_vertex("child-1").params["headers"] == {"proxied": "yes"}
    assert run.get_vertex("child-1").full_data["data"] is not child["data"]

    # A copy of the run copy expands the same groups again.
    again = run.copy_for_run(user_id="caller")
    assert again.raw_graph_data == pristine
    assert again.get_vertex("child-1").params["headers"] == {"proxied": "yes"}


def test_building_from_caller_data_never_aliases_it(process_flow_calls):
    """``from_payload`` and other callers keep their nodes; only run copies skip the second copy."""
    flow = _flat_flow()
    pristine = copy.deepcopy(flow)

    graph = _template(flow)
    graph.get_vertex("first").params["headers"]["added"] = "by the graph"
    graph.get_vertex("first").data["node"]["template"]["stream"]["value"] = False

    assert flow == pristine
    assert graph.get_vertex("first").full_data["data"] is not flow["nodes"][0]["data"]
    assert process_flow_calls == [2]


def test_deepcopy_of_a_graph_keeps_its_raw_flow_data_separate(process_flow_calls):
    """``copy.deepcopy`` copies can be checkpointed from raw_graph_data, so it must not show run edits."""
    template = _template(_flat_flow())
    pristine = copy.deepcopy(template.raw_graph_data)
    process_flow_calls.clear()

    copied = copy.deepcopy(template)
    copied.get_vertex("first").params["headers"]["added"] = "by the copy"

    assert copied.raw_graph_data == pristine
    assert process_flow_calls == [2]
