"""Resolve the per-model-call ContextManager contract and invoke its reviewed implementation."""

import json
from copy import deepcopy

from langchain_core.runnables import RunnableLambda
from pydantic import Field

from lfx.base.agents.context_messages import messages_from_table, messages_to_table
from lfx.projects.bindings import FlowBinding, contract_outputs, flow_revision
from lfx.projects.invocation import ReviewedFlowRunner

AGENT_CONTEXT = "harness_agent_context"
CONTEXT_ORIGIN = "_harness_context"


class ContextBinding(FlowBinding):
    timeout_seconds: float = Field(default=30, gt=0, le=300)


class ContextFlowError(ValueError):
    """Context preparation stopped before calling the model."""


class ContextSourceChangedError(ContextFlowError):
    """A new source revision requires explicit review."""


def context_outputs(data: dict) -> list[dict]:
    sources = [node for node in data.get("nodes", []) if node.get("data", {}).get("type") == "AgentContext"]
    if len(sources) != 1:
        msg = "A context flow needs one Agent Context connected to a message Table output."
        raise ValueError(msg)
    reachable = {sources[0]["id"]}
    for _ in data.get("nodes", []):
        reachable.update(edge["target"] for edge in data.get("edges", []) if edge.get("source") in reachable)
    return [choice for choice in contract_outputs(data, {"DataFrame", "Table"}) if choice["node_id"] in reachable]


def validate_context_binding(data: dict, binding: FlowBinding) -> None:
    if not any(
        output["node_id"] == binding.node_id and output["output_name"] == binding.output_name
        for output in context_outputs(data)
    ):
        msg = "The selected context output is missing or incompatible. Connect Agent Context to a message Table output."
        raise ValueError(msg)
    if flow_revision(data) != binding.revision:
        msg = "The context flow changed. Review it and update its binding before running."
        raise ContextSourceChangedError(msg)


def parse_context_binding(value: str) -> ContextBinding | None:
    return ContextBinding.model_validate_json(value) if value.strip() not in {"", "null", "{}"} else None


def compose_context(data: dict, *, project_id: str, agent_id: str, binding: ContextBinding | None) -> dict:
    """Reconcile the runtime value only when it still matches the project's last write."""
    updated = deepcopy(data)
    node_data = next(node for node in updated["nodes"] if node["id"] == agent_id)["data"]
    origin = node_data.get(CONTEXT_ORIGIN)
    owned = isinstance(origin, dict) and origin.get("project_id") == project_id
    if binding is None and not owned:
        return data
    entry = node_data["node"]["template"].get("context_binding")
    if not isinstance(entry, dict):
        msg = "Update the Agent component on its canvas before configuring a context flow."
        raise TypeError(msg)
    value = entry.get("value") or "null"
    if not isinstance(value, str):
        msg = "The canvas context binding must contain JSON text."
        raise TypeError(msg)
    current = json.loads(value) if value.strip() not in {"", "null", "{}"} else None
    baseline = origin.get("binding") if owned else None
    connected = any(
        edge.get("target") == agent_id
        and edge.get("data", {}).get("targetHandle", {}).get("fieldName") == "context_binding"
        for edge in data.get("edges", [])
    )
    if current != baseline or connected or (origin and not owned):
        msg = (
            "Context has independent canvas edits. Restore the saved context configuration before changing its binding."
        )
        raise ValueError(msg)
    value = binding.model_dump() if binding else None
    entry["value"] = json.dumps(value) if binding else ""
    entry["override_skip"] = True
    if binding:
        node_data[CONTEXT_ORIGIN] = {"project_id": project_id, "binding": value}
    else:
        node_data.pop(CONTEXT_ORIGIN, None)
    return updated


class ContextFlowRunner:
    def __init__(self, component, binding: ContextBinding):
        self.binding = binding
        self.runner = ReviewedFlowRunner(component, validate=validate_context_binding, label="context")

    async def __call__(self, messages):
        async def invoke(rows):
            value = await self.runner(self.binding, {AGENT_CONTEXT: {"messages": rows}})
            return messages_from_table(value)

        return await RunnableLambda(invoke, name="harness_context_flow").ainvoke(
            messages_to_table(messages).to_dict(orient="records"), config={"tags": ["harness:context"]}
        )
