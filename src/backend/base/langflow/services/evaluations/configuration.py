"""Review scorer dependencies and store server-owned FlowVersion references."""

from lfx.projects.bindings import flow_revision
from lfx.projects.builtin_slots import SCORER
from lfx.projects.dependencies import binding_dependencies

from langflow.services.database.models.folder.flow_bindings import (
    flow_definitions,
    resolve_binding_flows,
)


async def scorer_choices(session, user, flow):
    sources = await resolve_binding_flows(session, user, flow)
    dependencies = binding_dependencies(str(flow.id), flow_definitions(sources.values()))
    return [
        {
            **choice,
            "flow_id": str(flow.id),
            "flow_name": flow.name,
            "revision": flow_revision(flow.data),
            "dependencies": [item.model_dump(mode="json") for item in dependencies],
        }
        for choice in SCORER.binding_outputs(flow.data or {})
    ]
