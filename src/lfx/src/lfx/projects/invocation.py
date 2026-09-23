"""Run reviewed flow outputs with isolated invocation context and shared identity checks."""

from contextvars import ContextVar
from copy import deepcopy

_ACTIVE_FLOWS: ContextVar[tuple[str, ...]] = ContextVar("active_harness_flows", default=())
_MAX_DEPENDENCY_FLOWS = 500


async def reviewed_flow_source(component, binding, *, field_name, validate):
    """Resolve a reviewed definition once, retaining its identity across restored runs."""
    from lfx.components.flow_controls.run_flow import RunFlowComponent
    from lfx.helpers import get_harness_flow
    from lfx.projects.dependencies import flow_references, validate_binding_dependencies
    from lfx.utils.langflow_utils import has_langflow_memory

    parent = component.graph
    frozen = getattr(parent, "frozen_tool_flows", None)
    directory = (parent.context or {}).get("project_dir") if parent else None
    if frozen is not None or not binding.version_id or directory or not has_langflow_memory():
        resolver = RunFlowComponent(_user_id=component.user_id)
        resolver._vertex = component._vertex  # noqa: SLF001
        source = await resolver.get_flow(flow_id_selected=binding.flow_id)
        candidate = getattr(parent, "runtime_candidate", None)
        executable_binding = candidate.execution_binding(binding) if candidate else binding
        validate(source.data if field_name == "tools" else source.data.get("data", {}), executable_binding)
        if frozen is None:
            definitions = {
                binding.flow_id: {
                    **deepcopy(source.data),
                    "id": binding.flow_id,
                    "name": source.data.get("name", binding.flow_id),
                }
            }
            pending = [binding.flow_id]
            while pending:
                for reference in flow_references(definitions[pending.pop()]["data"]):
                    if reference.flow_id in definitions:
                        continue
                    nested = await resolver.get_flow(
                        flow_id_selected=reference.flow_id, flow_name_selected=reference.name
                    )
                    identity = reference.flow_id or nested.data.get("id")
                    if not identity or not nested.data.get("data"):
                        msg = "A reviewed flow dependency is unavailable."
                        raise ValueError(msg)
                    if identity not in definitions:
                        definitions[identity] = {**deepcopy(nested.data), "id": identity}
                        pending.append(identity)
                    if len(definitions) > _MAX_DEPENDENCY_FLOWS:
                        msg = "A harness customization cannot depend on more than 500 flows."
                        raise ValueError(msg)
            validate_binding_dependencies(binding, list(definitions.values()))
            frozen = definitions
        return {**deepcopy(source.data), "dependencies": frozen}
    key = f"{field_name}:{binding.flow_id}:{getattr(binding, 'node_id', '')}:{getattr(binding, 'output_name', '')}"
    recorded = getattr(parent, "reviewed_harness_flows", {})
    value = binding.model_dump(mode="json")
    source = await get_harness_flow(
        user_id=component.user_id, binding=binding, field_name=field_name, require_current=recorded.get(key) != value
    )
    validate(source.data if field_name == "tools" else source.data["data"], binding)
    if parent is not None:
        parent.reviewed_harness_flows[key] = value
    return deepcopy(source.data)


class ReviewedFlowRunner:
    """Cache reviewed definitions for one compiled Agent; build a fresh graph per invocation."""

    def __init__(self, component, *, validate, label: str):
        self.component = component
        self.validate = validate
        self.label = label
        self.definitions = {}

    async def __call__(self, binding, context: dict):
        active = _ACTIVE_FLOWS.get()
        if binding.flow_id in active:
            msg = "A harness flow cannot recursively invoke itself."
            raise ValueError(msg)
        token = _ACTIVE_FLOWS.set((*active, binding.flow_id))
        try:
            return await self._invoke(binding, context)
        finally:
            _ACTIVE_FLOWS.reset(token)

    async def _invoke(self, binding, context):
        from lfx.base.tools.run_flow import _model_provider_policy
        from lfx.graph.graph.base import Graph
        from lfx.helpers.flow import run_flow

        key = binding.model_dump_json()
        if key not in self.definitions:
            field_name = {
                "Hook": "hooks",
                "context": "context_strategy",
                "compaction": "compaction",
                "permission": "tool_policy",
            }[self.label]
            self.definitions[key] = await reviewed_flow_source(
                self.component, binding, field_name=field_name, validate=self.validate
            )
        source = self.definitions[key]
        data = source["data"]
        parent = self.component.graph
        candidate = getattr(parent, "runtime_candidate", None)
        self.validate(data, candidate.execution_binding(binding) if candidate else binding)
        context = {
            **deepcopy(context),
            "project_dir": (parent.context or {}).get("project_dir") if parent else None,
        }
        async with _model_provider_policy(
            user_id=self.component.user_id, flow_id=binding.flow_id, flow_name=None, runtime_candidate=candidate
        ):
            graph = Graph.from_payload(
                deepcopy(data), flow_id=binding.flow_id, user_id=self.component.user_id, context=context
            )
            graph.frozen_tool_flows = source.get("dependencies")
            if candidate:
                candidate.inherit(parent, graph)
            await run_flow(
                graph=graph,
                inputs={},
                user_id=self.component.user_id,
                output_type="any",
                session_id=getattr(parent, "session_id", None),
            )
        vertex = graph.get_vertex(binding.node_id)
        if not vertex.built or vertex.custom_component is None:
            msg = f"The {self.label} flow did not produce its selected output."
            raise ValueError(msg)
        return vertex.custom_component.get_output(binding.output_name).value
