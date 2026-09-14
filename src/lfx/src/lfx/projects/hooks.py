"""Resolve and invoke reviewed Hook flows through the existing flow executor."""

import json
from copy import deepcopy

from lfx.base.agents.hooks import HookBinding, HookDecision, HookSourceChangedError
from lfx.projects.bindings import contract_outputs, flow_revision
from lfx.projects.invocation import ReviewedFlowRunner

HOOK_EVENT_CONTEXT = "harness_hook_event"
HOOK_ORIGIN = "_harness_hooks"


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
    """Invoke a Hook contract through the shared reviewed-flow resolver."""

    def __init__(self, component):
        self.component = component
        self.runner = ReviewedFlowRunner(component, validate=validate_hook_binding, label="Hook")

    async def __call__(self, binding: HookBinding, payload: dict) -> HookDecision:
        parent = self.component.graph
        value = await self.runner(
            binding,
            {
                HOOK_EVENT_CONTEXT: {
                    "event": binding.on_event,
                    "payload": payload,
                    "run_id": str(parent.run_id) if parent else None,
                    "session_id": getattr(parent, "session_id", None),
                },
            },
        )
        if not isinstance(value, HookDecision):
            msg = "The Hook flow must return a HookDecision, not a display artifact."
            raise TypeError(msg)
        return value
