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


@pytest.fixture
def archive_type(monkeypatch):
    from lfx.inputs.inputs import StrInput
    from lfx.projects import ProjectTypeDefinition, ProjectTypeField, registry

    class CustomArchiveType(ProjectTypeDefinition):
        name = "archive-test"
        display_name = "Archive test"
        icon = "Box"
        fields = (
            ProjectTypeField(name="libraries", input=StrInput(name="libraries", list=True), references="archive-test"),
        )

        def export_config(self, config, mapping):
            config = super().export_config(config, mapping)
            return {**(config or {}), "direction": "export"}

        def import_config(self, config, mapping):
            config = super().import_config(config, mapping)
            return {**(config or {}), "direction": "import"}

    original = registry.get_project_type
    monkeypatch.setattr(
        "lfx.projects.archives.get_project_type",
        lambda name: CustomArchiveType() if name == CustomArchiveType.name else original(name),
    )
    return CustomArchiveType


def test_custom_archive_hooks_remap_declared_references_without_changing_source(archive_type):
    dependency = ArchivedProject(id=uuid4(), name="Library", project_type=archive_type.name, flows=[])
    root = ArchivedProject(
        id=uuid4(),
        name="Support",
        project_type=archive_type.name,
        flows=[],
        project_config={"libraries": [{"project_id": str(dependency.id), "revision": "a" * 64}]},
    )
    graph = CompositionGraph(ProjectComposition(root_project_id=root.id, projects=[root, dependency]))
    original = graph.composition.model_dump()
    graph.validate()
    mapped_ids = {key: str(uuid4()) for key in graph.projects}
    exported = graph.relocate(project_ids=mapped_ids, flow_ids={}, version_ids={}, operation="export")
    assert exported.projects[0].project_config["direction"] == "export"
    assert exported.projects[0].project_config["libraries"][0]["project_id"] == mapped_ids[str(dependency.id)]
    imported = relocate(exported)
    assert imported.projects[0].project_config["direction"] == "import"
    assert graph.composition.model_dump() == original


def test_declared_archive_references_cannot_escape_closed_graph(archive_type):
    root = ArchivedProject(
        id=uuid4(),
        name="Support",
        project_type=archive_type.name,
        flows=[],
        project_config={"libraries": [{"project_id": str(uuid4()), "revision": "a" * 64}]},
    )
    with pytest.raises(ValueError, match="missing or has the wrong type"):
        CompositionGraph(ProjectComposition(root_project_id=root.id, projects=[root])).validate()


def test_unavailable_project_type_is_not_downgraded():
    root = ArchivedProject(id=uuid4(), name="Unknown", project_type="plugin-no-longer-installed", flows=[])
    with pytest.raises(ValueError, match="not registered"):
        CompositionGraph(ProjectComposition(root_project_id=root.id, projects=[root])).validate()


@pytest.mark.parametrize("result", [[], {"_applied": {}}, {"invalid": float("nan")}])
def test_archive_hook_invalid_results_are_rejected(archive_type, monkeypatch, result):
    monkeypatch.setattr(archive_type, "import_config", lambda *_: result)
    root = ArchivedProject(id=uuid4(), name="Invalid", project_type=archive_type.name, flows=[])
    with pytest.raises(ValueError, match=r"archive hook|Out of range float"):
        relocate(ProjectComposition(root_project_id=root.id, projects=[root]))
