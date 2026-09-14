"""Resolve and invoke reviewed Hook flows through the existing flow executor."""

from contextvars import ContextVar
from copy import deepcopy

from lfx.base.agents.hooks import HookBinding, HookDecision, HookSourceChangedError
from lfx.projects.bindings import contract_outputs, flow_revision

HOOK_EVENT_CONTEXT = "harness_hook_event"
_ACTIVE_HOOKS: ContextVar[tuple[str, ...]] = ContextVar("active_harness_hooks", default=())


def hook_outputs(data: dict) -> list[dict]:
    events = [node for node in data.get("nodes", []) if node.get("data", {}).get("type") == "HookEvent"]
    if len(events) != 1:
        msg = "A Hook flow needs one Hook Event connected to a Hook decision output."
        raise ValueError(msg)
    reachable = {events[0]["id"]}
    for _ in data.get("nodes", []):
        reachable.update(edge["target"] for edge in data.get("edges", []) if edge.get("source") in reachable)
    return [choice for choice in contract_outputs(data, {"HookDecision"}) if choice["node_id"] in reachable]


def validate_hook_binding(data: dict, binding: HookBinding) -> None:
    if not any(
        output["node_id"] == binding.node_id and output["output_name"] == binding.output_name
        for output in hook_outputs(data)
    ):
        msg = "The selected Hook output is missing or incompatible. Connect Hook Event to a Hook decision output."
        raise ValueError(msg)
    if flow_revision(data) != binding.revision:
        msg = "The Hook flow changed. Review it and update its binding before running."
        raise HookSourceChangedError(msg)


class HookFlowRunner:
    """Resolve through Run Flow's identity/sibling rules and retain one definition per run.

    Each invocation builds a fresh graph from that definition. Event data lives only in
    graph context. It cannot rewrite component code, credentials, or saved input values.
    """

    def __init__(self, component):
        self.component = component
        self.definitions = {}

    async def __call__(self, binding: HookBinding, payload: dict) -> HookDecision:
        active = _ACTIVE_HOOKS.get()
        if binding.flow_id in active:
            msg = "A Hook flow cannot recursively invoke itself."
            raise ValueError(msg)
        token = _ACTIVE_HOOKS.set((*active, binding.flow_id))
        try:
            return await self._invoke(binding, payload)
        finally:
            _ACTIVE_HOOKS.reset(token)

    async def _invoke(self, binding: HookBinding, payload: dict) -> HookDecision:
        from lfx.base.tools.run_flow import _model_provider_policy
        from lfx.components.flow_controls.run_flow import RunFlowComponent
        from lfx.graph.graph.base import Graph
        from lfx.helpers.flow import run_flow

        key = (binding.flow_id, binding.revision)
        if key not in self.definitions:
            resolver = RunFlowComponent(_user_id=self.component.user_id)
            resolver._vertex = self.component._vertex  # noqa: SLF001
            source = await resolver.get_flow(flow_id_selected=binding.flow_id)
            data = source.data.get("data", {})
            validate_hook_binding(data, binding)
            self.definitions[key] = deepcopy(data)
        data = self.definitions[key]
        validate_hook_binding(data, binding)
        parent = self.component.graph
        context = {
            HOOK_EVENT_CONTEXT: {
                "event": binding.on_event,
                "payload": deepcopy(payload),
                "run_id": str(parent.run_id) if parent else None,
                "session_id": getattr(parent, "session_id", None),
            },
            "project_dir": (parent.context or {}).get("project_dir") if parent else None,
        }
        async with _model_provider_policy(user_id=self.component.user_id, flow_id=binding.flow_id, flow_name=None):
            graph = Graph.from_payload(
                deepcopy(data), flow_id=binding.flow_id, user_id=self.component.user_id, context=context
            )
            await run_flow(
                graph=graph,
                inputs={},
                user_id=self.component.user_id,
                output_type="any",
                session_id=getattr(parent, "session_id", None),
            )
        vertex = graph.get_vertex(binding.node_id)
        if not vertex.built or vertex.custom_component is None:
            msg = "The Hook flow did not produce its selected output."
            raise ValueError(msg)
        value = vertex.custom_component.get_output(binding.output_name).value
        if not isinstance(value, HookDecision):
            msg = "The Hook flow must return a HookDecision, not a display artifact."
            raise TypeError(msg)
        return value
