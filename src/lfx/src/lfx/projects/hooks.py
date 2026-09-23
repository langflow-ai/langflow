"""Resolve and invoke reviewed Hook flows through the existing flow executor."""

import json
from contextvars import ContextVar
from copy import deepcopy

from pydantic import TypeAdapter

from lfx.base.agents.hooks import HookBinding, HookDecision, HookSourceChangedError
from lfx.projects.bindings import contract_outputs, flow_revision

HOOK_EVENT_CONTEXT = "harness_hook_event"
HOOK_ORIGIN = "_harness_hooks"
_ACTIVE_HOOKS: ContextVar[tuple[str, ...]] = ContextVar("active_harness_hooks", default=())


def compose_hooks(data: dict, *, project_id: str, agent_id: str, bindings: list[HookBinding]) -> dict:
    """Write reviewed hooks to the Agent, refusing to overwrite independent canvas edits."""
    updated = deepcopy(data)
    node = next(node for node in updated["nodes"] if node["id"] == agent_id)
    node_data = node["data"]
    origin = node_data.get(HOOK_ORIGIN)
    owned = isinstance(origin, dict) and origin.get("project_id") == project_id
    if not bindings and not owned:
        return data
    entry = node_data["node"]["template"].get("hook_bindings")
    if not isinstance(entry, dict):
        msg = "Update the Agent component on its canvas before configuring hooks."
        raise TypeError(msg)
    current = json.loads(entry.get("value") or "[]")
    baseline = origin.get("bindings", []) if owned else []
    connected = any(
        edge.get("target") == agent_id
        and edge.get("data", {}).get("targetHandle", {}).get("fieldName") == "hook_bindings"
        for edge in data.get("edges", [])
    )
    if current != baseline or connected or (origin and not owned):
        msg = "Hooks have independent canvas edits. Restore the saved hook configuration before changing its binding."
        raise ValueError(msg)
    values = [binding.model_dump() for binding in bindings]
    entry["value"] = json.dumps(values)
    entry["override_skip"] = True
    if bindings:
        node_data[HOOK_ORIGIN] = {"project_id": project_id, "bindings": values}
    else:
        node_data.pop(HOOK_ORIGIN, None)
    return updated


def flow_hook_bindings(data: dict) -> list[HookBinding]:
    """Read runtime bindings without importing any saved Agent code."""
    return [
        binding
        for node in data.get("nodes", [])
        if node.get("data", {}).get("type") == "Agent"
        for binding in TypeAdapter(list[HookBinding]).validate_json(
            node["data"]["node"]["template"].get("hook_bindings", {}).get("value") or "[]"
        )
    ]


def remap_flow_hooks(flows: dict[str, dict], id_map: dict[str, str], project_id: str) -> None:
    """Remap imported runtime references after ordinary Run Flow links, children first.

    Callers validate reviewed definitions before mutating any imported flow. This updates
    references in every Agent, including nested ones, without copying old version IDs.
    """
    visited = set()

    def visit(flow_id, active):
        if flow_id in active:
            msg = "The imported Hook flows contain a recursive reference."
            raise ValueError(msg)
        if flow_id in visited:
            return
        data = flows[flow_id]

        def remap(binding):
            target = binding.flow_id
            if target not in id_map:
                msg = "An imported Hook binding must reference a flow in the archive."
                raise ValueError(msg)
            visit(target, active | {flow_id})
            return binding.model_copy(
                update={"flow_id": id_map[target], "revision": flow_revision(flows[target]), "version_id": None}
            ).model_dump()

        for node in data.get("nodes", []):
            node_data = node.get("data", {})
            if node_data.get("type") != "Agent":
                continue
            entry = node_data["node"]["template"].get("hook_bindings")
            if entry:
                bindings = TypeAdapter(list[HookBinding]).validate_json(entry.get("value") or "[]")
                if bindings:
                    entry["value"] = json.dumps([remap(binding) for binding in bindings])
            origin = node_data.get(HOOK_ORIGIN)
            if isinstance(origin, dict):
                origin["project_id"] = project_id
                origin["bindings"] = [
                    remap(binding) for binding in TypeAdapter(list[HookBinding]).validate_python(origin["bindings"])
                ]
        visited.add(flow_id)

    for flow_id in flows:
        visit(flow_id, set())


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
