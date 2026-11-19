"""Repair plans must preserve difficult saved graphs before any database write."""

import copy

import pytest
from langflow.services.flow_repair.models import RepairApplyRequest, RepairPreviewRequest
from langflow.services.flow_repair.planning import data_digest, plan_flow_repair
from lfx.graph.graph.utils import process_flow
from lfx.upgrade.applier import apply_safe_upgrades
from lfx.upgrade.checker import check_flow_compatibility, iter_flow_nodes
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


def grouped_graph(depth, *, child_matches_group=False, **source):
    child = node()
    child["data"]["node"]["template"]["text"].update(
        name="text", display_name="Text", advanced=False, value="stale child value", load_from_db=False
    )
    if child_matches_group:
        child["data"]["node"]["template"]["text"].update(value="actual exposed selection", **source)
    field_name = "text"
    for level in range(depth):
        exposed = copy.deepcopy(child["data"]["node"]["template"][field_name])
        exposed.update(
            value="actual exposed selection" if level == depth - 1 else "stale nested selection",
            proxy={"id": child["id"], "field": field_name},
            **source,
        )
        group_id, field_name = f"group-{level}", f"exposed_{level}"
        child = {
            "id": group_id,
            "data": {
                "id": group_id,
                "type": "Group",
                "node": {"template": {field_name: exposed}, "flow": {"data": graph(child)}},
            },
        }
    return graph(child)


@pytest.mark.parametrize("depth", [1, 2])
@pytest.mark.parametrize(
    "source",
    [{"load_from_db": False}, {"load_from_db": True}, {"file_path": ["owner/saved.txt"]}],
    ids=["literal", "global-reference", "uploaded-file"],
)
def test_grouped_repair_preserves_the_effective_value_and_source_mode(depth, source):
    saved = grouped_graph(depth, child_matches_group=depth > 1, **source)
    before = copy.deepcopy(saved)
    leaf, _, _ = list(iter_flow_nodes(saved["nodes"], saved["edges"]))[-1]
    effective = leaf["data"]["node"]["template"]["text"]
    runtime = process_flow(copy.deepcopy(saved))["nodes"][0]["data"]["node"]["template"]["text"]
    assert {key: runtime.get(key) for key in ("value", "load_from_db", "file_path")} == {
        key: effective.get(key) for key in ("value", "load_from_db", "file_path")
    }

    plan = plan_flow_repair(saved, registry())

    assert plan.updated_nodes == 1
    assert plan.reason_codes == []
    updated = process_flow(copy.deepcopy(plan.data))["nodes"][0]["data"]["node"]["template"]["text"]
    assert updated["value"] == effective["value"] == "actual exposed selection"
    for key in ("load_from_db", "file_path"):
        assert updated.get(key) == effective.get(key)
    assert saved == before


@pytest.mark.parametrize(
    ("key", "stale_value"),
    [("value", "stale child value"), ("load_from_db", False), ("file_path", ["owner/previous.txt"])],
)
def test_nested_repair_refuses_changes_to_consumed_runtime_inputs(key, stale_value):
    saved = grouped_graph(2, child_matches_group=True, load_from_db=True, file_path=["owner/saved.txt"])
    inner = saved["nodes"][0]["data"]["node"]["flow"]["data"]["nodes"][0]
    child = inner["data"]["node"]["flow"]["data"]["nodes"][0]
    child["data"]["node"]["template"]["text"][key] = stale_value
    before = copy.deepcopy(saved)
    target = registry()
    candidate, count = apply_safe_upgrades(saved, target, check_flow_compatibility(saved, target), return_count=True)
    assert count == 1
    # The current runtime replaces an inner proxy when flattening this nested
    # group, so the consumed child state differs from the exposed selection.
    old_runtime = process_flow(copy.deepcopy(saved))["nodes"][0]["data"]["node"]["template"]["text"]
    new_runtime = process_flow(copy.deepcopy(candidate))["nodes"][0]["data"]["node"]["template"]["text"]
    assert old_runtime[key] != new_runtime[key]

    plan = plan_flow_repair(saved, target)

    assert plan.data is None
    assert plan.reason_codes == ["preservation_failed"]
    assert saved == before


@pytest.mark.parametrize("depth", [1, 2])
@pytest.mark.parametrize(
    ("key", "replacement"),
    [("value", "lost selection"), ("load_from_db", False), ("file_path", ["owner/changed.txt"])],
)
def test_grouped_repair_refuses_changed_effective_saved_state(monkeypatch, depth, key, replacement):
    from langflow.services.flow_repair import planning

    saved = grouped_graph(depth, load_from_db=True, file_path=["owner/saved.txt"])
    target = registry()
    lossy, count = apply_safe_upgrades(saved, target, check_flow_compatibility(saved, target), return_count=True)
    assert count == 1
    lossy["nodes"][0]["data"]["node"]["template"][f"exposed_{depth - 1}"][key] = replacement
    monkeypatch.setattr(planning, "apply_safe_upgrades", lambda *_args, **_kwargs: (lossy, count))

    plan = plan_flow_repair(saved, target)

    assert plan.data is None
    assert plan.reason_codes == ["preservation_failed"]


def test_group_projection_does_not_hide_changes_to_an_edited_child(monkeypatch):
    from langflow.services.flow_repair import planning

    saved = grouped_graph(1)
    child = saved["nodes"][0]["data"]["node"]["flow"]["data"]["nodes"][0]
    child["data"]["node"]["edited"] = True
    lossy = copy.deepcopy(saved)
    changed = lossy["nodes"][0]["data"]["node"]["flow"]["data"]["nodes"][0]
    changed["data"]["node"]["template"]["text"]["value"] = "changed stored selection"
    assert process_flow(copy.deepcopy(saved)) == process_flow(copy.deepcopy(lossy))
    monkeypatch.setattr(planning, "apply_safe_upgrades", lambda *_args, **_kwargs: (lossy, 1))

    plan = plan_flow_repair(saved, registry())

    assert plan.data is None
    assert plan.reason_codes == ["preservation_failed"]


@pytest.mark.parametrize("outer_source", ["outer custom code", "target source", "old custom code"])
def test_nested_repair_preserves_skipped_custom_runtime_code(outer_source):
    custom = {
        "id": "Custom-1",
        "data": {
            "id": "Custom-1",
            "type": "CustomComponent",
            "node": {
                "template": {
                    "code": {
                        "name": "code",
                        "type": "code",
                        "value": "old custom code",
                        "show": True,
                        "advanced": False,
                    }
                },
                "outputs": [],
            },
        },
    }
    inner_field = {
        **copy.deepcopy(custom["data"]["node"]["template"]["code"]),
        "proxy": {"id": custom["id"], "field": "code"},
    }
    inner = {
        "id": "inner",
        "data": {
            "id": "inner",
            "type": "Group",
            "node": {"template": {"custom_source": inner_field}, "flow": {"data": graph(custom, node())}},
        },
    }
    outer_field = {
        **copy.deepcopy(inner_field),
        "value": outer_source,
        "proxy": {"id": "inner", "field": "custom_source"},
    }
    outer = {
        "id": "outer",
        "data": {
            "id": "outer",
            "type": "Group",
            "node": {"template": {"custom_source": outer_field}, "flow": {"data": graph(inner)}},
        },
    }
    saved = graph(outer)
    before = copy.deepcopy(saved)
    target = registry()
    report = check_flow_compatibility(saved, target)
    assert {(item.node_id, item.status) for item in report.nodes} == {
        ("Custom-1", "ok"),
        ("Example-1", "outdated_safe"),
    }
    candidate, count = apply_safe_upgrades(saved, target, report, return_count=True)
    assert count == 1
    old_runtime = {item["id"]: item for item in process_flow(copy.deepcopy(saved))["nodes"]}
    new_runtime = {item["id"]: item for item in process_flow(copy.deepcopy(candidate))["nodes"]}
    assert old_runtime["Custom-1"]["data"]["node"]["template"]["code"]["value"] == "old custom code"
    assert new_runtime["Custom-1"]["data"]["node"]["template"]["code"]["value"] == outer_source

    plan = plan_flow_repair(saved, target)

    if outer_source == "old custom code":
        assert plan.updated_nodes == 1
        assert plan.reason_codes == []
    else:
        assert plan.data is None
        assert plan.reason_codes == ["preservation_failed"]
    assert saved == before


def test_an_eligible_update_cannot_replace_source_with_nonregistry_code(monkeypatch):
    from langflow.services.flow_repair import planning

    saved, target = graph(), registry()
    candidate, count = apply_safe_upgrades(saved, target, check_flow_compatibility(saved, target), return_count=True)
    assert count == 1
    candidate["nodes"][0]["data"]["node"]["template"]["code"]["value"] = "unexpected source"
    monkeypatch.setattr(planning, "apply_safe_upgrades", lambda *_args, **_kwargs: (candidate, count))

    plan = plan_flow_repair(saved, target)

    assert plan.data is None
    assert plan.reason_codes == ["preservation_failed"]


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
    group = {"id": "group", "data": {"id": "group", "node": {"template": {}, "flow": {"data": inner}}}}
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
