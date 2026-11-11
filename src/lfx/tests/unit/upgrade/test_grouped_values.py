"""Grouped upgrades use the exposed values the runtime passes to child components."""

from copy import deepcopy

import pytest
from lfx.custom import Component
from lfx.custom.utils import build_custom_component_template
from lfx.graph.graph.utils import process_flow
from lfx.upgrade.applier import apply_safe_upgrades
from lfx.upgrade.checker import check_flow_compatibility, iter_flow_nodes

CODE = """from lfx.custom import Component
from lfx.io import StrInput, Output
class SavedValueComponent(Component):
    display_name = "Saved Value"
    inputs = [StrInput(name="value", value="")]
    outputs = [Output(name="result", method="result")]
    def result(self) -> str:
        return str(self.value)
"""


def _grouped_flow(depth, *, child_value="", group_value="saved value", **source):
    saved, _ = build_custom_component_template(Component(_code=CODE))
    saved["template"]["value"]["value"] = child_value
    child = {"id": "leaf", "data": {"id": "leaf", "type": "SavedValueComponent", "node": saved}}
    field_name = "value"
    for level in range(depth):
        exposed = deepcopy(child["data"]["node"]["template"][field_name])
        exposed.update(
            value=group_value if level == depth - 1 else "stale nested group value",
            proxy={"id": child["id"], "field": field_name},
            **source,
        )
        group_id = f"group-{level}"
        field_name = f"exposed_{level}"
        child = {
            "id": group_id,
            "data": {
                "id": group_id,
                "type": "Group",
                "node": {
                    "template": {field_name: exposed},
                    "flow": {"data": {"nodes": [child], "edges": []}},
                },
            },
        }
    return {"nodes": [child], "edges": []}


def _registry(*, retyped=True):
    code = CODE.replace("StrInput", "IntInput").replace('value=""', "value=0") if retyped else CODE + "\n# updated"
    current, _ = build_custom_component_template(Component(_code=code))
    return {"Test": {"SavedValueComponent": current}}


@pytest.mark.parametrize("depth", [1, 2])
def test_checker_rejects_retyping_a_nonempty_group_value(depth):
    flow = _grouped_flow(depth)
    original = deepcopy(flow)

    report = check_flow_compatibility(flow, _registry())

    assert [(node.node_id, node.status) for node in report.nodes] == [("leaf", "outdated_breaking")]
    assert flow == original


@pytest.mark.parametrize("depth", [1, 2])
def test_safe_upgrade_leaves_a_breaking_group_value_unchanged(depth):
    flow = _grouped_flow(depth)
    registry = _registry()
    report = check_flow_compatibility(flow, registry)

    updated, count = apply_safe_upgrades(flow, registry, report, return_count=True)

    assert count == 0
    assert updated == flow


@pytest.mark.parametrize("depth", [1, 2])
def test_safe_retyping_updates_the_group_proxy_contract(depth):
    flow = _grouped_flow(depth, child_value="stale child value", group_value="")
    registry = _registry()
    report = check_flow_compatibility(flow, registry)
    assert report.nodes[0].status == "outdated_safe"

    updated, count = apply_safe_upgrades(flow, registry, report, return_count=True)

    assert count == 1
    effective = process_flow(updated)["nodes"][0]["data"]["node"]
    assert effective["template"]["value"]["type"] == "int"
    assert effective["template"]["value"]["value"] == 0
    _, instance = build_custom_component_template(Component(_code=effective["template"]["code"]["value"]))
    instance.set_attributes({"value": effective["template"]["value"]["value"]})
    assert instance.result() == "0"


@pytest.mark.parametrize("depth", [1, 2])
@pytest.mark.parametrize(
    "source",
    [{"load_from_db": True}, {"load_from_db": False, "file_path": ["owner/saved.txt"]}],
)
def test_group_values_and_source_modes_reach_the_leaf_without_mutating_the_flow(depth, source):
    flow = _grouped_flow(depth, group_value="SAVED_REFERENCE", **source)
    original = deepcopy(flow)

    leaf, _, path = list(iter_flow_nodes(flow["nodes"], flow["edges"]))[-1]

    assert len(path) == depth
    field = leaf["data"]["node"]["template"]["value"]
    assert field["value"] == "SAVED_REFERENCE"
    assert {name: field[name] for name in source} == source
    assert flow == original


@pytest.mark.parametrize("depth", [1, 2])
@pytest.mark.parametrize("source", [{"load_from_db": True}, {"load_from_db": False, "file_path": ["owner/saved.txt"]}])
def test_safe_update_keeps_group_values_and_source_modes(depth, source):
    flow = _grouped_flow(depth, group_value="SAVED_REFERENCE", **source)
    original = deepcopy(flow)
    registry = _registry(retyped=False)

    updated, count = apply_safe_upgrades(flow, registry, check_flow_compatibility(flow, registry), return_count=True)

    assert count == 1
    effective = process_flow(updated)["nodes"][0]["data"]["node"]["template"]["value"]
    assert effective["value"] == "SAVED_REFERENCE"
    assert {name: effective[name] for name in source} == source
    assert flow == original
