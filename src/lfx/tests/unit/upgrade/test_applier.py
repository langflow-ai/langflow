"""Unit tests for the upgrade applier."""

import copy

import pytest
from lfx.upgrade.applier import apply_safe_upgrades
from lfx.upgrade.checker import check_flow_compatibility

REGISTRY_CODE = "class MyComp:\n    pass  # v2"
NODE_CODE = "class MyComp:\n    pass  # v1"


def _registry(code=REGISTRY_CODE, template_extra=None):
    template = {"code": {"value": code}}
    if template_extra:
        template.update(template_extra)
    return {
        "Cat": {
            "MyComp": {
                "template": template,
                "outputs": [{"name": "o", "display_name": "O", "types": ["M"], "method": "m", "allows_loop": False}],
                "metadata": {},
            }
        }
    }


def _node(code=NODE_CODE, type_="MyComp", template_extra=None):
    template = {"code": {"value": code}}
    if template_extra:
        template.update(template_extra)
    return {
        "id": "n1",
        "data": {
            "id": "n1",
            "type": type_,
            "node": {
                "display_name": "My Component",
                "edited": False,
                "template": template,
                "outputs": [{"name": "o", "display_name": "O", "types": ["M"], "method": "m", "allows_loop": False}],
            },
        },
    }


def _flow(*nodes):
    return {"nodes": list(nodes), "edges": []}


def test_apply_updates_safe_node_code():
    flow = _flow(_node(code=NODE_CODE))
    registry = _registry(code=REGISTRY_CODE)
    report = check_flow_compatibility(flow, registry)
    assert report.nodes[0].status == "outdated_safe"

    updated = apply_safe_upgrades(flow, registry, report)
    code = updated["nodes"][0]["data"]["node"]["template"]["code"]["value"]
    assert code == REGISTRY_CODE


def test_apply_does_not_mutate_original():
    flow = _flow(_node(code=NODE_CODE))
    original_code = flow["nodes"][0]["data"]["node"]["template"]["code"]["value"]
    registry = _registry(code=REGISTRY_CODE)
    report = check_flow_compatibility(flow, registry)

    apply_safe_upgrades(flow, registry, report)
    assert flow["nodes"][0]["data"]["node"]["template"]["code"]["value"] == original_code


def test_apply_skips_breaking_nodes():
    new_outputs = [{"name": "renamed_out", "display_name": "O", "types": ["M"], "method": "m", "allows_loop": False}]
    flow = _flow(_node(code=NODE_CODE))
    registry = {
        "Cat": {
            "MyComp": {
                "template": {"code": {"value": REGISTRY_CODE}},
                "outputs": new_outputs,
                "metadata": {},
            }
        }
    }
    report = check_flow_compatibility(flow, registry)
    assert report.nodes[0].status == "outdated_breaking"

    updated = apply_safe_upgrades(flow, registry, report)
    code = updated["nodes"][0]["data"]["node"]["template"]["code"]["value"]
    assert code == NODE_CODE


def test_apply_skips_blocked_nodes():
    flow = _flow(_node(type_="Ghost"))
    registry = {}
    report = check_flow_compatibility(flow, registry)
    assert report.nodes[0].status == "blocked"

    updated = apply_safe_upgrades(flow, registry, report)
    assert updated["nodes"][0]["data"]["node"]["template"]["code"]["value"] == NODE_CODE


def test_apply_skips_ok_nodes():
    flow = _flow(_node(code=REGISTRY_CODE))
    registry = _registry(code=REGISTRY_CODE)
    report = check_flow_compatibility(flow, registry)
    assert report.nodes[0].status == "ok"

    updated = apply_safe_upgrades(flow, registry, report)
    assert updated["nodes"][0]["data"]["node"]["template"]["code"]["value"] == REGISTRY_CODE


def test_apply_returns_count_of_updated_nodes():
    node_a = _node(code=NODE_CODE)
    node_b = copy.deepcopy(node_a)
    node_b["id"] = "n2"
    node_b["data"]["id"] = "n2"
    node_b["data"]["type"] = "Ghost"
    flow = _flow(node_a, node_b)
    registry = _registry(code=REGISTRY_CODE)
    report = check_flow_compatibility(flow, registry)

    _, count = apply_safe_upgrades(flow, registry, report, return_count=True)
    assert count == 1


def test_apply_merges_new_registry_fields_with_defaults():
    """Fields the saved flow predates are introduced exactly as the registry declares them.

    Counterpart to test_outdated_safe_when_registry_added_optional_field in test_checker.py:
    the checker calls the node safe because the applier fills the field, so the applier
    must actually fill it — otherwise the re-stamped code runs without a field it expects.
    """
    new_field = {"value": False, "required": False, "type": "bool"}
    flow = _flow(_node(code=NODE_CODE))
    registry = _registry(code=REGISTRY_CODE, template_extra={"new_flag": new_field})
    report = check_flow_compatibility(flow, registry)
    assert report.nodes[0].status == "outdated_safe"

    updated = apply_safe_upgrades(flow, registry, report)
    template = updated["nodes"][0]["data"]["node"]["template"]
    assert template["code"]["value"] == REGISTRY_CODE
    assert template["new_flag"] == new_field

    # The merged field must be a copy: editing the upgraded flow later must not reach
    # back into the shared registry lookup.
    template["new_flag"]["value"] = True
    assert registry["Cat"]["MyComp"]["template"]["new_flag"]["value"] is False


def test_apply_replaces_an_empty_retyped_field_with_the_registry_declaration():
    """An empty, unconnected field whose type changed is safe; the applier takes the new declaration."""
    registry_field = {"value": {}, "type": "dict"}
    flow = _flow(_node(code=NODE_CODE, template_extra={"opt": {"value": "", "type": "str"}}))
    registry = _registry(code=REGISTRY_CODE, template_extra={"opt": registry_field})
    report = check_flow_compatibility(flow, registry)
    assert report.nodes[0].status == "outdated_safe"

    updated = apply_safe_upgrades(flow, registry, report)
    template = updated["nodes"][0]["data"]["node"]["template"]
    assert template["opt"] == registry_field
    assert template["opt"] is not registry["Cat"]["MyComp"]["template"]["opt"]

    recheck = check_flow_compatibility(updated, registry)
    assert recheck.nodes[0].status == "ok"


def test_retyped_field_holding_a_value_is_breaking_and_left_alone():
    """The update would drop the saved value, so the node is breaking and the applier skips it."""
    flow = _flow(_node(code=NODE_CODE, template_extra={"opt": {"value": "user set", "type": "str"}}))
    registry = _registry(code=REGISTRY_CODE, template_extra={"opt": {"value": {}, "type": "dict"}})
    report = check_flow_compatibility(flow, registry)
    assert report.nodes[0].status == "outdated_breaking"

    updated = apply_safe_upgrades(flow, registry, report)
    assert updated["nodes"][0]["data"]["node"]["template"]["opt"] == {"value": "user set", "type": "str"}


def test_apply_writes_the_registry_outputs_keeping_hidden_options_and_picked_type():
    """An added output is safe, so it must reach the node; the saved hidden flag, options and picked type stay.

    ``options`` holds the filter set in the output inspection view, which the runtime applies to the result.
    """
    flow = _flow(_node(code=NODE_CODE))
    saved_output = flow["nodes"][0]["data"]["node"]["outputs"][0]
    saved_output.update(display_name="Old", hidden=True, selected="M", options={"filter": "results.0"})
    registry = _registry(code=REGISTRY_CODE)
    registry_outputs = [
        {"name": "o", "display_name": "O", "types": ["D", "M"], "selected": "D", "method": "m", "allows_loop": False},
        {"name": "o2", "display_name": "O2", "types": ["D"], "selected": "D", "method": "m2", "allows_loop": False},
    ]
    registry["Cat"]["MyComp"]["outputs"] = registry_outputs
    report = check_flow_compatibility(flow, registry)
    assert report.nodes[0].status == "outdated_safe"

    updated = apply_safe_upgrades(flow, registry, report)

    assert updated["nodes"][0]["data"]["node"]["outputs"] == [
        {**registry_outputs[0], "hidden": True, "selected": "M", "options": {"filter": "results.0"}},
        registry_outputs[1],
    ]
    assert registry_outputs[0]["selected"] == "D"


def test_apply_keeps_a_picked_type_the_output_now_names_differently():
    """A saved ``Data`` pick on an output that now names the type ``JSON`` stays picked, as ``JSON``.

    Taking the registry's pick instead would switch the output to ``M``, and the editor drops an edge whose
    source handle reads ``Data`` from it.
    """
    flow = _flow(_node(code=NODE_CODE))
    saved_output = flow["nodes"][0]["data"]["node"]["outputs"][0]
    saved_output.update(types=["Data", "M"], selected="Data")
    registry = _registry(code=REGISTRY_CODE)
    registry_output = {
        "name": "o",
        "display_name": "O",
        "types": ["JSON", "M"],
        "selected": "M",
        "method": "m",
        "allows_loop": False,
    }
    registry["Cat"]["MyComp"]["outputs"] = [registry_output]
    report = check_flow_compatibility(flow, registry)
    assert report.nodes[0].status == "outdated_safe"

    updated = apply_safe_upgrades(flow, registry, report)

    assert updated["nodes"][0]["data"]["node"]["outputs"] == [{**registry_output, "selected": "JSON"}]


def test_apply_drops_a_picked_type_the_output_no_longer_offers():
    """A saved pick the output no longer offers under any name takes the registry's pick."""
    flow = _flow(_node(code=NODE_CODE))
    saved_output = flow["nodes"][0]["data"]["node"]["outputs"][0]
    saved_output.update(types=["M"], selected="Gone")
    registry = _registry(code=REGISTRY_CODE)
    registry_output = {
        "name": "o",
        "display_name": "O",
        "types": ["JSON", "M"],
        "selected": "M",
        "method": "m",
        "allows_loop": False,
    }
    registry["Cat"]["MyComp"]["outputs"] = [registry_output]
    report = check_flow_compatibility(flow, registry)
    assert report.nodes[0].status == "outdated_safe"

    updated = apply_safe_upgrades(flow, registry, report)

    assert updated["nodes"][0]["data"]["node"]["outputs"] == [registry_output]


def _apply_to_saved_output(saved_output_fields: dict, registry_types: list[str]) -> dict:
    """Apply a safe update to a node whose output ``o`` is saved with these fields; return the written output."""
    flow = _flow(_node(code=NODE_CODE))
    saved_output = flow["nodes"][0]["data"]["node"]["outputs"][0]
    saved_output.update(saved_output_fields)
    registry = _registry(code=REGISTRY_CODE)
    registry["Cat"]["MyComp"]["outputs"] = [
        {
            "name": "o",
            "display_name": "O",
            "types": registry_types,
            "selected": "M",
            "method": "m",
            "allows_loop": False,
        },
    ]
    report = check_flow_compatibility(flow, registry)
    assert report.nodes[0].status == "outdated_safe"
    return apply_safe_upgrades(flow, registry, report)["nodes"][0]["data"]["node"]["outputs"][0]


def test_apply_keeps_an_exact_pick_over_its_other_name():
    """When the output offers both ``Data`` and ``JSON``, a saved ``Data`` pick stays ``Data``."""
    output = _apply_to_saved_output({"types": ["Data", "M"], "selected": "Data"}, ["JSON", "Data", "M"])

    assert output["selected"] == "Data"


@pytest.mark.parametrize(
    "saved_selected",
    [{}, {"selected": None}, {"selected": ["Data"]}, {"selected": {"Data": 1}}],
    ids=["missing", "none", "list", "dict"],
)
def test_apply_counts_the_only_type_of_an_output_saved_without_a_pick_as_its_pick(saved_selected):
    """A single-type output saved with no picked type keeps that type when the output gains types.

    Taking the registry's pick would switch the output to ``M``, and the editor drops an edge whose source
    handle reads ``Data`` from it.
    """
    output = _apply_to_saved_output({"types": ["Data"], **saved_selected}, ["JSON", "M"])

    assert output["selected"] == "JSON"


@pytest.mark.parametrize("saved_selected", [["Data"], {"Data": 1}], ids=["list", "dict"])
def test_apply_takes_the_registry_pick_when_the_saved_pick_is_not_a_string(saved_selected):
    output = _apply_to_saved_output({"types": ["Data", "M"], "selected": saved_selected}, ["JSON", "M"])

    assert output["selected"] == "M"


def test_apply_takes_the_registry_pick_when_the_saved_types_are_not_a_list():
    output = _apply_to_saved_output({"types": {"Data": 1}}, ["JSON", "M"])

    assert output["selected"] == "M"


def test_apply_keeps_the_toolset_output_of_a_tool_mode_node():
    """A node in tool mode has only the toolset output, which the registry's outputs would replace."""
    toolset = [{"name": "component_as_tool", "display_name": "Toolset", "types": ["Tool"], "method": "to_toolkit"}]
    node = _node(code=NODE_CODE, template_extra={"q": {"tool_mode": True}})
    node["data"]["node"]["outputs"] = toolset
    registry = _registry(code=REGISTRY_CODE, template_extra={"q": {"tool_mode": True}})
    report = check_flow_compatibility(_flow(node), registry)
    assert report.nodes[0].status == "outdated_safe"

    updated = apply_safe_upgrades(_flow(node), registry, report)

    assert updated["nodes"][0]["data"]["node"]["outputs"] == toolset


def test_apply_tells_apart_nodes_that_share_a_data_id():
    """Edges target ``node.id``. A copy sharing ``data.id`` with a safe node must not be overwritten."""
    original = _node(code=NODE_CODE, template_extra={"num": {"value": "", "type": "str"}})
    copy_ = copy.deepcopy(original)
    copy_["id"] = "n1-copy"
    edge = {"source": "x", "target": "n1-copy", "data": {"targetHandle": {"fieldName": "num", "id": "n1-copy"}}}
    flow = {"nodes": [original, copy_], "edges": [edge]}
    registry = _registry(code=REGISTRY_CODE, template_extra={"num": {"value": 0, "type": "int"}})
    report = check_flow_compatibility(flow, registry)
    assert [(n.node_id, n.status) for n in report.nodes] == [("n1", "outdated_safe"), ("n1-copy", "outdated_breaking")]

    updated = apply_safe_upgrades(flow, registry, report)

    assert updated["nodes"][0]["data"]["node"]["template"]["num"] == {"value": 0, "type": "int"}
    assert updated["nodes"][1]["data"]["node"]["template"]["num"] == {"value": "", "type": "str"}


def test_apply_preserves_fields_registry_dropped():
    """A field only the flow has makes the node breaking, so the applier leaves it as saved."""
    flow = _flow(_node(code=NODE_CODE, template_extra={"legacy": {"value": "keep me"}}))
    registry = _registry(code=REGISTRY_CODE)
    report = check_flow_compatibility(flow, registry)
    assert report.nodes[0].status == "outdated_breaking"

    updated = apply_safe_upgrades(flow, registry, report)
    template = updated["nodes"][0]["data"]["node"]["template"]
    assert template["code"]["value"] == NODE_CODE
    assert template["legacy"] == {"value": "keep me"}


def test_apply_does_not_overwrite_existing_field_values():
    """Only fields the flow lacks are merged; the user's saved values always win."""
    flow = _flow(_node(code=NODE_CODE, template_extra={"opt": {"value": "user-set"}}))
    registry = _registry(code=REGISTRY_CODE, template_extra={"opt": {"value": "default"}})
    report = check_flow_compatibility(flow, registry)
    assert report.nodes[0].status == "outdated_safe"

    updated = apply_safe_upgrades(flow, registry, report)
    assert updated["nodes"][0]["data"]["node"]["template"]["opt"]["value"] == "user-set"


def test_apply_then_recheck_reports_ok_after_field_merge():
    """A safe upgrade over a grown template converges: the re-checked node is ok."""
    flow = _flow(_node(code=NODE_CODE))
    registry = _registry(code=REGISTRY_CODE, template_extra={"new_flag": {"value": False}})
    report = check_flow_compatibility(flow, registry)
    assert report.nodes[0].status == "outdated_safe"

    updated = apply_safe_upgrades(flow, registry, report)
    recheck = check_flow_compatibility(updated, registry)
    assert recheck.nodes[0].status == "ok"


def test_apply_updates_nested_flow_safe_node_code():
    """Safe upgrades inside a grouped component's nested flow must be written, not skipped.

    Counterpart to test_nested_flow_nodes_are_classified in test_checker.py: the checker
    classifies nested nodes, so the applier must also write them, otherwise the report
    advertises a safe upgrade that never actually lands on disk.
    """
    nested = _node(code=NODE_CODE)
    nested["id"] = "nested-1"
    nested["data"]["id"] = "nested-1"
    outer = {
        "id": "group-1",
        "data": {
            "id": "group-1",
            "type": "SomeGrouping",
            "node": {
                "display_name": "Group",
                "template": {},
                "outputs": [],
                "flow": {"data": {"nodes": [nested], "edges": []}},
            },
        },
    }
    flow = _flow(outer)
    registry = _registry(code=REGISTRY_CODE, template_extra={"new_flag": {"value": False}})
    report = check_flow_compatibility(flow, registry)
    assert any(n.node_id == "nested-1" and n.status == "outdated_safe" for n in report.nodes)

    updated, count = apply_safe_upgrades(flow, registry, report, return_count=True)
    assert count == 1
    written = updated["nodes"][0]["data"]["node"]["flow"]["data"]["nodes"][0]
    assert written["data"]["node"]["template"]["code"]["value"] == REGISTRY_CODE
    # New registry fields must be merged on the nested path too, not only at top level.
    assert written["data"]["node"]["template"]["new_flag"] == {"value": False}
