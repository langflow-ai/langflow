"""Run reviewed flow outputs with isolated invocation context and shared identity checks."""

from contextvars import ContextVar
from copy import deepcopy

_ACTIVE_FLOWS: ContextVar[tuple[str, ...]] = ContextVar("active_harness_flows", default=())


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
        from lfx.base.tools.run_flow import _model_provider_policy, get_user_is_superuser
        from lfx.components.flow_controls.run_flow import RunFlowComponent
        from lfx.graph.graph.base import Graph
        from lfx.helpers.flow import run_flow
        from lfx.utils.flow_validation import custom_component_admin_only_enabled, prepare_flow_build_for_user

        key = (binding.flow_id, binding.revision)
        if key not in self.definitions:
            resolver = RunFlowComponent(_user_id=self.component.user_id)
            resolver._vertex = self.component._vertex  # noqa: SLF001
            source = await resolver.get_flow(flow_id_selected=binding.flow_id)
            data = source.data.get("data", {})
            self.validate(data, binding)
            self.definitions[key] = deepcopy(data)
        data = self.definitions[key]
        self.validate(data, binding)
        parent = self.component.graph
        context = {
            **deepcopy(context),
            "project_dir": (parent.context or {}).get("project_dir") if parent else None,
        }
        async with _model_provider_policy(user_id=self.component.user_id, flow_id=binding.flow_id, flow_name=None):
            # A reviewed definition is still caller-authored. Recheck policy on
            # every invocation, including definitions cached earlier in this run.
            is_superuser = False
            if custom_component_admin_only_enabled() is not False:
                is_superuser = await get_user_is_superuser(self.component.user_id)
            prepared = await prepare_flow_build_for_user(deepcopy(data), is_superuser=is_superuser)
            graph = Graph.from_payload(
                prepared if prepared is not None else deepcopy(data),
                flow_id=binding.flow_id,
                user_id=self.component.user_id,
                context=context,
            )
            graph.frozen_tool_flows = getattr(parent, "frozen_tool_flows", None)
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
