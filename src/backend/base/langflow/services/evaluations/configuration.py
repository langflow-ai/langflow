"""Review scorer dependencies and store server-owned FlowVersion references."""

from fastapi import HTTPException
from lfx.projects.bindings import flow_revision
from lfx.projects.dependencies import binding_dependencies, validate_binding_dependencies
from lfx.projects.evaluations import EvalSuiteConfig, scorer_outputs, validate_scorer

from langflow.services.authorization import FlowAction
from langflow.services.database.models.folder.flow_bindings import (
    _authorize,
    flow_definitions,
    resolve_binding_flows,
    resolve_binding_snapshot,
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
        for choice in scorer_outputs(flow.data or {})
    ]


async def save_eval_config(session, user, config, previous):
    from langflow.services.database.models.folder.config_writer import _binding_version

    try:
        suite = EvalSuiteConfig.model_validate(config)
        binding = suite.scorer
        if binding is not None:
            if previous and previous.get("scorer") == binding.model_dump(mode="json") and binding.version_id:
                await resolve_binding_snapshot(session, user, binding, "scorer", require_current=False)
            else:
                root = await _authorize(session, user, binding.flow_id, FlowAction.EXECUTE)
                validate_scorer(root.data or {}, binding)
                sources = await resolve_binding_flows(session, user, root, action=FlowAction.EXECUTE)
                validate_binding_dependencies(binding, flow_definitions(sources.values()))
                # Never accept caller-supplied version IDs as proof of review.
                for item in [binding, *binding.dependencies]:
                    item.version_id = await _binding_version(session, sources[item.flow_id], "scorer")
        return suite.model_dump(mode="json")
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
