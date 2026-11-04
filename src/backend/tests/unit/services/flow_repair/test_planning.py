"""Repair plans must preserve difficult saved graphs before any database write."""

import copy

import pytest
from langflow.services.flow_repair.models import RepairApplyRequest, RepairPreviewRequest
from langflow.services.flow_repair.planning import data_digest, plan_flow_repair
from pydantic import ValidationError


def registry():
    return {
        "helpers": {
            "Example": {
                "display_name": "Example",
                "template": {
                    "_type": "Component",
                    "code": {"type": "code", "value": "target source"},
                    "text": {"type": "str", "value": "default", "input_types": ["Message"], "show": True},
                    "added": {"type": "str", "value": "added default", "required": False},
                },
                "outputs": [{"name": "out", "types": ["Message"], "selected": "Message"}],
            }
        }
    }


def node(node_id="Example-1", *, edited=False):
    info = copy.deepcopy(registry()["helpers"]["Example"])
    info["template"].pop("added")
    info["template"]["code"]["value"] = "saved source"
    info["template"]["text"].update(value="owner-secret-reference", load_from_db=True, show=False)
    info["edited"] = edited
    return {"id": node_id, "data": {"id": node_id, "type": "Example", "node": info}, "position": {"x": 0, "y": 0}}


def graph(*nodes):
    return {"nodes": list(nodes) or [node()], "edges": []}


def test_safe_plan_preserves_values_and_uses_only_target_source():
    saved = graph()
    before = copy.deepcopy(saved)

    plan = plan_flow_repair(saved, registry())

    assert plan.updated_nodes == 1
    assert plan.reason_codes == []
    template = plan.data["nodes"][0]["data"]["node"]["template"]
    assert template["code"]["value"] == "target source"
    assert template["text"]["value"] == "owner-secret-reference"
    assert template["text"]["load_from_db"] is True
    assert template["added"]["value"] == "added default"
    assert saved == before


def test_edited_node_is_untouched_while_other_nodes_upgrade():
    edited = node("Example-edited", edited=True)
    saved = graph(edited, node("Example-safe"))

    plan = plan_flow_repair(saved, registry())

    assert plan.updated_nodes == 1
    assert plan.data["nodes"][0] == edited
    assert plan.data["nodes"][1]["data"]["node"]["template"]["code"]["value"] == "target source"


def test_hidden_field_edge_and_removed_field_keep_whole_flow_unchanged():
    saved = graph(node("Example-1"), node("Example-2"))
    saved["nodes"][1]["data"]["node"]["template"]["old_hidden"] = {
        "type": "str",
        "value": "",
        "show": False,
        "input_types": ["Message"],
    }
    saved["edges"] = [
        {"source": "Example-1", "target": "Example-2", "data": {"targetHandle": {"fieldName": "old_hidden"}}}
    ]
    before = copy.deepcopy(saved)

    plan = plan_flow_repair(saved, registry())

    assert plan.data is None
    assert plan.updated_nodes == 0
    assert "outdated_breaking" in plan.reason_codes
    assert saved == before


def test_nested_group_preserves_internal_edges_and_values():
    first, second = node("Example-inner-1"), node("Example-inner-2")
    inner = graph(first, second)
    inner["edges"] = [{"source": first["id"], "target": second["id"], "data": {"targetHandle": {"fieldName": "text"}}}]
    group = {"id": "group", "data": {"node": {"flow": {"data": inner}}}}
    saved = graph(group)

    plan = plan_flow_repair(saved, registry())

    assert plan.updated_nodes == 2
    assert plan.data["nodes"][0]["data"]["node"]["flow"]["data"]["edges"] == inner["edges"]


@pytest.mark.parametrize("corruption", ["duplicate", "nested_duplicate", "null_node", "missing_edges"])
def test_malformed_or_ambiguous_nodes_are_not_repaired(corruption):
    saved = graph()
    if corruption == "duplicate":
        saved["nodes"].append(copy.deepcopy(saved["nodes"][0]))
    elif corruption == "nested_duplicate":
        saved["nodes"].append({"id": "group", "data": {"node": {"flow": {"data": graph()}}}})
    elif corruption == "null_node":
        saved["nodes"][0]["data"]["node"] = None
    else:
        saved.pop("edges")
    before = copy.deepcopy(saved)

    plan = plan_flow_repair(saved, registry())

    assert plan.data is None
    assert saved == before


def test_an_applier_that_loses_a_saved_value_is_refused(monkeypatch):
    from langflow.services.flow_repair import planning

    saved = graph()
    lossy = copy.deepcopy(saved)
    lossy["nodes"][0]["data"]["node"]["template"]["text"]["value"] = "default"
    monkeypatch.setattr(planning, "apply_safe_upgrades", lambda *_args, **_kwargs: (lossy, 1))

    plan = plan_flow_repair(saved, registry())

    assert plan.data is None
    assert plan.reason_codes == ["preservation_failed"]


def test_request_never_accepts_replacement_code_and_requires_explicit_nullable_token():
    from uuid import uuid4

    selection = {"flow_id": str(uuid4()), "data_sha256": data_digest(graph())}
    with pytest.raises(ValidationError):
        RepairApplyRequest.model_validate({"flows": [selection], "target_sha256": data_digest(registry())})
    selection["version_token"] = None
    with pytest.raises(ValidationError):
        RepairApplyRequest.model_validate(
            {"flows": [selection], "target_sha256": data_digest(registry()), "code": "request source"}
        )
    with pytest.raises(ValidationError):
        RepairPreviewRequest.model_validate({"flow_ids": [selection["flow_id"], selection["flow_id"]]})


@pytest.mark.parametrize("lost", ["selected", "hidden", "options"])
def test_an_applier_that_loses_saved_output_state_is_refused(monkeypatch, lost):
    from langflow.services.flow_repair import planning

    saved = graph()
    output = saved["nodes"][0]["data"]["node"]["outputs"][0]
    output.update(hidden=True, options={"group": "saved"})
    lossy = copy.deepcopy(saved)
    lossy["nodes"][0]["data"]["node"]["outputs"][0].pop(lost)
    monkeypatch.setattr(planning, "apply_safe_upgrades", lambda *_args, **_kwargs: (lossy, 1))

    plan = plan_flow_repair(saved, registry())

    assert plan.data is None
    assert plan.reason_codes == ["preservation_failed"]
