"""Resolve the per-model-call ContextManager contract and invoke its reviewed implementation."""

from langchain_core.runnables import RunnableLambda
from pydantic import Field

from lfx.base.agents.context_messages import messages_from_table, messages_to_table
from lfx.projects.bindings import FlowBinding, compose_single_binding, contract_outputs, flow_revision
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
    return compose_single_binding(
        data,
        project_id=project_id,
        agent_id=agent_id,
        binding=binding,
        input_name="context_binding",
        origin_name=CONTEXT_ORIGIN,
        label="Context",
    )


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
