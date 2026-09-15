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


def build_slot_baseline(
    reference: str, initial_value: str | None = None, *, initial_config: dict | None = None
) -> dict:
    """Resolve only shipped, executable baselines. References never import arbitrary code."""
    if reference == "builtin:instructions":
        return instructions_baseline(initial_value)
    if reference == "builtin:hook":
        return hook_baseline()
    if reference == "builtin:context":
        return context_baseline(initial_config)
    if reference == "builtin:compaction":
        return compaction_baseline(initial_config)
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


def compaction_baseline(initial_config: dict | None = None) -> dict:
    from lfx.base.agents.harness import HarnessRuntimeConfig
    from lfx.components.models_and_agents.compaction_input import CompactionInputComponent
    from lfx.components.models_and_agents.compactor import CompactorComponent
    from lfx.graph.flow_builder import add_component, add_connection, empty_flow

    policy = HarnessRuntimeConfig.model_validate(initial_config or {})
    flow = empty_flow(
        "Compaction", "Summarize older conversation messages while preserving recent messages and sources."
    )
    compactor = CompactorComponent()
    compactor.set(keep_messages=policy.compaction_keep_messages)
    for component in (CompactionInputComponent(), compactor):
        add_component(flow, component.name, {component.name: component.to_frontend_node()["data"]["node"]})
    source, target = flow["data"]["nodes"]
    source["position"], target["position"] = {"x": 150, "y": 150}, {"x": 650, "y": 150}
    add_connection(flow, source["id"], "messages", target["id"], "messages")
    add_connection(flow, source["id"], "model", target["id"], "model")
    flow["data"]["harness_contract"] = {"slot": "Compactor", "field_name": "compaction"}
    return flow


def context_baseline(initial_config: dict | None = None) -> dict:
    from lfx.base.agents.harness import HarnessRuntimeConfig
    from lfx.components.models_and_agents.agent_context import AgentContextComponent
    from lfx.components.models_and_agents.context_manager import ContextManagerComponent
    from lfx.graph.flow_builder import add_component, add_connection, empty_flow

    flow = empty_flow("Context", "Prepare the messages the agent receives before each model call.")
    policy = HarnessRuntimeConfig.model_validate(initial_config or {})
    context = ContextManagerComponent()
    context.set(strategy=policy.context_strategy, turns=policy.context_turns)
    for component in (AgentContextComponent(), context):
        add_component(flow, component.name, {component.name: component.to_frontend_node()["data"]["node"]})
    source, target = flow["data"]["nodes"]
    source["position"], target["position"] = {"x": 150, "y": 150}, {"x": 600, "y": 150}
    add_connection(flow, source["id"], "messages", target["id"], "messages")
    flow["data"]["harness_contract"] = {"slot": "ContextManager", "field_name": "context_strategy"}
    return flow
