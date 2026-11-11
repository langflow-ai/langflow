"""Chat Output preserves messages and edges when upgrading historical MessageInput templates."""

import copy
import json
from importlib.resources import files
from pathlib import Path

import pytest
from lfx.custom import Component
from lfx.custom.utils import build_custom_component_template
from lfx.template.field_migrations import can_migrate_chat_output_input
from lfx.upgrade.applier import apply_safe_upgrades
from lfx.upgrade.checker import build_registry_lookup, check_flow_compatibility

from .test_component_compat import SOURCE_RELEASES, _require_tags, _show

YOUTUBE_FLOW = "src/bundles/lfx-bundles/src/lfx_bundles/youtube/starter_projects/Youtube Analysis.json"
MIGRATION_CASES = json.loads(
    (Path(__file__).parents[2] / "data" / "component_compat" / "chat_output_migration_cases.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("case", MIGRATION_CASES["cases"], ids=[case["name"] for case in MIGRATION_CASES["cases"]])
def test_shared_chat_output_migration_contract(case):
    values = MIGRATION_CASES["defaults"] | case
    assert (
        can_migrate_chat_output_input(
            values["component_class_name"], values["field_name"], values["current_field"], values["saved_field"]
        )
        is values["expected"]
    )


def _registry():
    index = json.loads(files("lfx").joinpath("_assets/component_index.json").read_text())
    return build_registry_lookup(dict(index["entries"]))


def _saved_chat_output(tag):
    _require_tags()
    flow = json.loads(_show(tag, YOUTUBE_FLOW))["data"]
    node = next(node for node in flow["nodes"] if node["data"]["type"] == "ChatOutput")
    return flow, node


@pytest.mark.parametrize("tag", SOURCE_RELEASES)
@pytest.mark.parametrize("saved_type", ["str", "other"])
@pytest.mark.parametrize("has_metadata", [True, False])
def test_safe_upgrade_preserves_chat_output_string_and_connections(tag, saved_type, has_metadata):
    flow, node = _saved_chat_output(tag)
    if not has_metadata:
        node["data"]["node"].pop("metadata", None)
    field = node["data"]["node"]["template"]["input_value"]
    field.update(
        type=saved_type,
        _input_type="MessageInput" if saved_type == "str" else "HandleInput",
        value="Keep this message",
        load_from_db=False,
    )
    if saved_type == "other":
        for edge in flow["edges"]:
            if edge["target"] == node["id"]:
                old_handle = edge["targetHandle"]
                handle = json.loads(old_handle.replace("œ", '"'))
                handle["type"] = "other"
                edge["targetHandle"] = json.dumps(handle).replace('"', "œ")
                edge["id"] = edge["id"].replace(old_handle, edge["targetHandle"])
                edge["data"]["targetHandle"]["type"] = "other"
    registry = _registry()
    original = copy.deepcopy(flow)

    report = check_flow_compatibility(flow, {}, registry=registry)
    status = next(status for status in report.nodes if status.node_id == node["id"])
    assert status.status == "outdated_safe"
    updated = apply_safe_upgrades(flow, {}, report, registry=registry)
    updated_node = next(n for n in updated["nodes"] if n["id"] == node["id"])
    updated_field = updated_node["data"]["node"]["template"]["input_value"]

    if saved_type == "str":
        assert updated_node["data"]["node"]["metadata"]["component_class_name"] == "ChatOutput"
    assert updated_field["type"] == "other"
    assert updated_field["value"] == "Keep this message"
    assert updated_field["load_from_db"] is False
    assert updated["edges"] == original["edges"]
    assert flow == original


@pytest.mark.asyncio
@pytest.mark.parametrize("saved_type", ["str", "other"])
async def test_editor_update_preserves_chat_output_string_and_runtime_output(saved_type):
    _, node = _saved_chat_output("v1.12.6")
    saved = node["data"]["node"]
    saved["template"]["input_value"].update(
        type=saved_type,
        _input_type="MessageInput" if saved_type == "str" else "HandleInput",
        value="Keep this message",
        load_from_db=False,
    )
    code = _registry()["ChatOutput"]["template"]["code"]["value"]
    rebuilt, component = build_custom_component_template(Component(_code=code), class_name="ChatOutput")

    updated = await component.update_frontend_node(rebuilt, saved)

    assert updated["template"]["input_value"]["type"] == "other"
    assert updated["template"]["input_value"]["value"] == "Keep this message"
    assert updated["template"]["input_value"]["load_from_db"] is False
    component.set(input_value=updated["template"]["input_value"]["value"], should_store_message=False)
    message = await component.message_response()
    assert message.text == "Keep this message"
