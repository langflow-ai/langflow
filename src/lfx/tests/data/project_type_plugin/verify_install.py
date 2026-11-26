"""Run after installing this fixture wheel in standalone LFX."""

# ruff: noqa: INP001 -- Standalone distribution verification script, not a package module.

import asyncio
import sys
from copy import deepcopy
from uuid import uuid4

from lfx.projects import get_project_type
from lfx.projects.archives import ArchivedProject, CompositionGraph, ProjectComposition
from lfx.projects.bindings import flow_revision
from lfx.projects.lifecycle import (
    CompositionContext,
    FlowView,
    ProjectView,
    SaveRequest,
    SourceSnapshot,
    SourceVersionReference,
)
from lfx.projects.starters import build_project_starter, get_project_starter

assert "langflow" not in sys.modules
definition = get_project_type("support-desk")
assert definition.__class__.__module__ == "sample_project_types"
assert definition.to_template()["instructions"]["display_name"] == "Instructions"
project_id, target_id, source_id, version_id = (uuid4() for _ in range(4))
target_token, source_token = str(uuid4()), str(uuid4())
data = {
    "nodes": [
        {"id": "Agent-1", "data": {"type": "Agent", "node": {"template": {"system_prompt": {"value": "Original"}}}}}
    ],
    "edges": [],
}
source_data = {"nodes": [], "edges": []}
flow = FlowView(
    id=target_id,
    project_id=project_id,
    name="Agent",
    description="",
    data=data,
    is_component=False,
    flow_type="flow",
    locked=False,
    revision=flow_revision(data),
    token=target_token,
)
source = FlowView(
    id=source_id,
    project_id=project_id,
    name="Source",
    description="",
    data=source_data,
    is_component=False,
    flow_type="flow",
    locked=False,
    revision=flow_revision(source_data),
    token=source_token,
)
project = ProjectView(project_id, "Support", definition.name, None)


class Context:
    async def read_flow(self, selector, *, access):
        assert selector.id == source_id
        assert access == "execute"
        return deepcopy(source)

    async def pin_sources(self, tokens, *, label):
        assert tokens == (source_token,)
        assert label == "support reference"
        return (SourceSnapshot(SourceVersionReference(source_id, version_id, source.revision), deepcopy(source_data)),)


async def main():
    request = SaveRequest(
        project, "replace", {"instructions": "  Be clear  ", "source_id": str(source_id)}, None, (flow, source)
    )
    prepared = await definition.save_config(request, Context())
    assert prepared.config["instructions"] == "Be clear"
    changes = definition.compose(prepared, CompositionContext(project, (flow, source), {}))
    assert changes[0].data["nodes"][0]["data"]["node"]["template"]["system_prompt"]["value"] == "Be clear"
    assert data["nodes"][0]["data"]["node"]["template"]["system_prompt"]["value"] == "Original"
    composition = ProjectComposition(
        root_project_id=project_id,
        projects=[
            ArchivedProject(
                id=project_id,
                name="Support",
                project_type=definition.name,
                project_config=prepared.config,
                flows=[
                    {**item.definition(), "data": change.data}
                    for item, change in zip((flow, source), changes, strict=True)
                ],
            )
        ],
    )
    graph = CompositionGraph(composition)
    graph.validate()
    exported = graph.relocate(
        project_ids={str(project_id): str(project_id)},
        flow_ids={key: key for key in graph.flows},
        version_ids={key: str(uuid4()) for key in graph.flows},
        operation="export",
    )
    graph = CompositionGraph(exported)
    ids = {key: str(uuid4()) for key in graph.flows}
    imported = graph.relocate(
        project_ids={str(project_id): str(uuid4())},
        flow_ids=ids,
        version_ids={key: str(uuid4()) for key in graph.flows},
    )
    assert imported.projects[0].project_config["source_id"] == ids[str(source_id)]
    owner, starter = get_project_starter("support-inbox")
    assert build_project_starter(owner, starter).projects[0].project_type == definition.name
    assert not any(name == "langflow" or name.startswith("langflow.") for name in sys.modules)
    print("PASS: wheel discovery, form, save, composition, archives, starter; no Langflow imported.")  # noqa: T201


if __name__ == "__main__":
    asyncio.run(main())
