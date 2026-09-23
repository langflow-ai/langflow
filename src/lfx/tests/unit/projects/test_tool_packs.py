from copy import deepcopy
from uuid import uuid4

import pytest
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph.flow_builder import add_component, add_connection, empty_flow
from lfx.projects import get_project_type, get_slot
from lfx.projects.tool_packs import ToolPackReference, exported_flow_ids, tool_pack_manifest, tool_pack_references


@pytest.mark.parametrize(
    "value",
    [
        None,
        {},
        ["id"],
        [{"project_id": str(uuid4())}],
        [{"project_id": str(uuid4()), "expected_type": "agent-harness", "revision": "a" * 64}],
    ],
)
def test_invalid_consumer_references_are_rejected(value):
    with pytest.raises((TypeError, ValueError)):
        tool_pack_references(value)


def test_duplicate_consumer_references_are_rejected():
    reference = ToolPackReference(project_id=uuid4(), revision="a" * 64).model_dump(mode="json")
    with pytest.raises(ValueError, match="only once"):
        tool_pack_references([reference, reference])


@pytest.fixture
def tool():
    registry = {}
    for component in (ChatInput, ChatOutput):
        frontend = component().to_frontend_node()
        node = frontend.get("data", frontend)["node"]
        node["field_order"] = [item.name for item in component.inputs]
        registry[component.name] = node
    flow = empty_flow("source lookup")
    source = add_component(flow, "ChatInput", registry, component_id="ChatInput-query")
    target = add_component(flow, "ChatOutput", registry, component_id="ChatOutput-result")
    add_connection(flow, source["id"], "message", target["id"], "input_value")
    return {"id": str(uuid4()), "name": "Source lookup", "description": "Find source text", "data": flow["data"]}


@pytest.fixture
def pack(tool):
    return {"project_id": uuid4(), "name": "Research tools", "config": {"tools": [tool["id"]]}, "flows": [tool]}


def test_pack_and_harness_share_the_registered_tool_contract():
    pack = get_project_type("tool-pack")
    assert pack.field_names() == ("tools",)
    assert pack.fields[0].slot_definition is get_slot("Tool")
    harness = next(field for field in get_project_type("agent-harness").fields if field.name == "tools")
    assert pack.fields[0].slot_definition is harness.slot_definition
    assert pack.fields[0].writes_to is None


def test_manifest_lists_only_selected_exports_and_no_source_code(pack, tool):
    other = {**deepcopy(tool), "id": str(uuid4())}
    pack["flows"].append(other)
    pack["config"]["tools"].append(tool["id"])
    manifest = tool_pack_manifest(**pack)
    assert [str(export.flow_id) for export in manifest.tools] == [tool["id"]]
    assert manifest.reference.expected_type == "tool-pack"
    assert len(manifest.reference.revision) == 64
    assert "template" not in manifest.model_dump_json()
    assert "class ChatInput" not in manifest.model_dump_json()
    assert exported_flow_ids(None) == ()
    assert not tool_pack_manifest(**{**pack, "config": None}).tools


@pytest.mark.parametrize("change", ["membership", "order", "tool_name", "description", "code", "input"])
def test_revision_changes_with_the_effective_export_contract(pack, tool, change):
    other = {**deepcopy(tool), "id": str(uuid4()), "name": "Second source"}
    pack["flows"].append(other)
    pack["config"]["tools"].append(other["id"])
    before = tool_pack_manifest(**pack).reference.revision
    if change == "membership":
        pack["config"]["tools"].pop()
    elif change == "order":
        pack["config"]["tools"].reverse()
    elif change in {"tool_name", "description"}:
        tool["name" if change == "tool_name" else "description"] = "Changed"
    else:
        template = tool["data"]["nodes"][0]["data"]["node"]["template"]
        template["code" if change == "code" else "input_value"]["value"] += " changed"
    assert tool_pack_manifest(**pack).reference.revision != before


def test_revision_ignores_layout_labels_unexported_flows_and_mcp(pack, tool):
    before = tool_pack_manifest(**pack).reference.revision
    tool["data"]["nodes"][0]["position"] = {"x": 100, "y": 200}
    tool["data"]["nodes"][0]["selected"] = True
    tool["mcp_enabled"] = True
    pack["name"] = "Renamed pack"
    pack["config"]["mcp_enabled"] = False
    pack["flows"].append({**deepcopy(tool), "id": str(uuid4()), "data": {}})
    assert tool_pack_manifest(**pack).reference.revision == before


@pytest.mark.parametrize("value", [None, {}, "flow", [True], [123], ["not-a-uuid"]])
def test_rejects_invalid_export_selections(value):
    with pytest.raises(ValueError, match=r"Exported tools|UUID"):
        exported_flow_ids({"tools": value})


@pytest.mark.parametrize("change", ["missing", "component", "not_callable"])
def test_rejects_exports_that_cannot_supply_the_tool_contract(pack, tool, change):
    if change == "missing":
        pack["flows"] = []
    elif change == "component":
        tool["is_component"] = True
    else:
        tool["data"] = {"nodes": [], "edges": []}
    with pytest.raises(ValueError, match=r"exported tool|exposed input"):
        tool_pack_manifest(**pack)


def test_export_validation_never_executes_saved_code(pack, tool):
    for node in tool["data"]["nodes"]:
        node["data"]["node"]["template"]["code"]["value"] = 'raise AssertionError("must not execute")'
    assert len(tool_pack_manifest(**pack).tools) == 1


@pytest.mark.parametrize("change", [{"expected_type": "agent-harness"}, {"revision": "latest"}, {"unknown": True}])
def test_reference_requires_an_explicit_type_and_content_revision(pack, change):
    reference = tool_pack_manifest(**pack).reference.model_dump()
    with pytest.raises(ValueError, match=r"expected_type|revision|unknown"):
        ToolPackReference.model_validate({**reference, **change})
