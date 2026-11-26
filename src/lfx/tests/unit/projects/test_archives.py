"""Relocation follows graph dependencies and changes only declared reference fields."""

# ruff: noqa: F811 -- Imported pytest fixture is injected by name.

from copy import deepcopy
from uuid import uuid4

import pytest
from lfx.components.flow_controls.run_flow import RunFlowComponent
from lfx.projects.archives import ArchivedProject, CompositionGraph, ProjectComposition
from lfx.projects.bindings import flow_revision
from lfx.projects.tool_packs import tool_pack_manifest

from .test_tool_packs import tool  # noqa: F401


def run_flow_node(flow):
    node = RunFlowComponent().to_frontend_node()
    node["id"] = "RunFlow-child"
    node["data"]["id"] = node["id"]
    template = node["data"]["node"]["template"]
    template["flow_id_selected"]["value"] = flow["id"]
    template["flow_name_selected"]["value"] = flow["name"]
    return node


def relocate(composition):
    graph = CompositionGraph(composition)
    return graph.relocate(
        project_ids={key: str(uuid4()) for key in graph.projects},
        flow_ids={key: str(uuid4()) for key in graph.flows},
        version_ids={key: str(uuid4()) for key in graph.flows},
        flow_names={key: f"{flow['name']} copy" for key, flow in graph.flows.items()},
    )


def composition_for(tool, extra_flows=None):
    project = ArchivedProject(
        id=uuid4(),
        name="Research tools",
        project_type="tool-pack",
        project_config={"tools": [tool["id"]]},
        flows=[tool, *(extra_flows or [])],
    )
    return ProjectComposition(root_project_id=project.id, projects=[project])


def test_nested_run_flow_links_and_export_revisions_follow_imported_children(tool):
    child = {**deepcopy(tool), "id": str(uuid4()), "name": "Nested lookup"}
    tool["data"]["nodes"].append(run_flow_node(child))
    composition = composition_for(tool, [child])
    original = composition.model_dump()
    CompositionGraph(composition).validate()
    imported = relocate(composition)
    CompositionGraph(imported).validate()
    project = imported.projects[0]
    parent, nested = project.flows
    selected = parent["data"]["nodes"][-1]["data"]["node"]["template"]
    assert selected["flow_id_selected"]["value"] == nested["id"] != child["id"]
    assert selected["flow_name_selected"]["value"] == nested["name"]
    assert selected["flow_name_selected"]["selected_metadata"]["id"] == nested["id"]
    assert project.project_config["tools"] == [parent["id"]]
    manifest = tool_pack_manifest(
        project_id=project.id,
        name=project.name,
        config=project.project_config,
        flows=project.flows,
    )
    assert manifest.tools[0].revision == flow_revision(parent["data"])
    assert composition.model_dump() == original


@pytest.mark.parametrize("by_name", [False, True])
def test_missing_nested_dependencies_never_resolve_outside_archive(tool, by_name):
    child = {**deepcopy(tool), "id": str(uuid4()), "name": "Not included"}
    node = run_flow_node(child)
    if by_name:
        node["data"]["node"]["template"]["flow_id_selected"]["value"] = ""
    tool["data"]["nodes"].append(node)
    with pytest.raises(ValueError, match="missing"):
        CompositionGraph(composition_for(tool)).validate()


def test_recursive_run_flow_cannot_be_relocated(tool):
    tool["data"]["nodes"].append(run_flow_node(tool))
    composition = composition_for(tool)
    with pytest.raises(ValueError, match="recursive"):
        relocate(composition)


def test_named_dependency_is_relocated_when_unique(tool):
    child = {**deepcopy(tool), "id": str(uuid4()), "name": "Named lookup"}
    node = run_flow_node(child)
    node["data"]["node"]["template"]["flow_id_selected"]["value"] = ""
    tool["data"]["nodes"].append(node)
    composition = composition_for(tool, [child])
    CompositionGraph(composition).validate()
    imported = relocate(composition)
    parent, nested = imported.projects[0].flows
    assert parent["data"]["nodes"][-1]["data"]["node"]["template"]["flow_id_selected"]["value"] == nested["id"]
