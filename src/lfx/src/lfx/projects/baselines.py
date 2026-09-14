"""Executable starting points for supported, reusable slot contracts."""

from __future__ import annotations

from lfx.projects.builtin_slots import SYSTEM_PROMPT_BUILDER


def instructions_baseline(initial_value: str | None = None) -> dict:
    """Build a runnable Instructions flow without loading any saved component code."""
    from lfx.base.agents.default_system_prompt import DEFAULT_SYSTEM_PROMPT_TEMPLATE
    from lfx.components.models_and_agents.system_prompt_builder import SystemPromptBuilderComponent
    from lfx.graph.flow_builder import add_component, empty_flow

    component = SystemPromptBuilderComponent()
    component.set(
        input_value=initial_value if initial_value and initial_value.strip() else DEFAULT_SYSTEM_PROMPT_TEMPLATE
    )
    flow = empty_flow("Instructions", "Build the instructions the agent receives before each run.")
    add_component(flow, component.name, {component.name: component.to_frontend_node()["data"]["node"]})
    flow["data"]["nodes"][0]["position"] = {"x": 300, "y": 150}
    flow["data"]["harness_contract"] = {
        "slot": SYSTEM_PROMPT_BUILDER.name,
        "field_name": "system_prompt",
    }
    return flow


def build_slot_baseline(reference: str, initial_value: str | None = None) -> dict:
    """Resolve only shipped, executable baselines. References never import arbitrary code."""
    if reference == "builtin:instructions":
        return instructions_baseline(initial_value)
    if reference == "builtin:hook":
        return hook_baseline()
    msg = "This contract does not yet provide a working baseline."
    raise ValueError(msg)


def hook_baseline() -> dict:
    from lfx.components.models_and_agents.hook import HookComponent
    from lfx.components.models_and_agents.hook_event import HookEventComponent
    from lfx.graph.flow_builder import add_component, add_connection, empty_flow

    flow = empty_flow("Hook", "Observe an invocation, then return a decision to the agent harness.")
    event, hook = HookEventComponent(), HookComponent()
    for component in (event, hook):
        add_component(flow, component.name, {component.name: component.to_frontend_node()["data"]["node"]})
    source, target = flow["data"]["nodes"]
    source["position"], target["position"] = {"x": 150, "y": 150}, {"x": 600, "y": 150}
    add_connection(flow, source["id"], "event", target["id"], "event")
    flow["data"]["harness_contract"] = {"slot": "Hook", "field_name": "hooks"}
    return flow
