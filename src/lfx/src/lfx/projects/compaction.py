"""Reviewed implementations of the threshold-triggered Compactor contract."""

from langchain_core.runnables import RunnableLambda
from pydantic import Field

from lfx.base.agents.compaction import COMPACTION_MODEL, CompactionResult
from lfx.base.agents.context_messages import messages_to_table
from lfx.projects.bindings import FlowBinding, contract_outputs, flow_revision
from lfx.projects.invocation import ReviewedFlowRunner

COMPACTION_INPUT = "harness_compaction_input"


class CompactionBinding(FlowBinding):
    trigger_tokens: int = Field(default=8000, ge=1, le=10000000)
    timeout_seconds: float = Field(default=60, gt=0, le=300)


class CompactionFlowError(ValueError):
    """Compaction failed before any conversation state was replaced."""


class CompactionSourceChangedError(CompactionFlowError):
    """The source definition requires explicit review."""


def compaction_outputs(data: dict) -> list[dict]:
    sources = [node for node in data.get("nodes", []) if node.get("data", {}).get("type") == "CompactionInput"]
    if len(sources) != 1:
        msg = "A compaction flow needs one Compaction Input connected to a CompactionResult output."
        raise ValueError(msg)
    reachable = {sources[0]["id"]}
    for _ in data.get("nodes", []):
        reachable.update(edge["target"] for edge in data.get("edges", []) if edge.get("source") in reachable)
    return [choice for choice in contract_outputs(data, {"CompactionResult"}) if choice["node_id"] in reachable]


def validate_compaction_binding(data: dict, binding: FlowBinding) -> None:
    if not any(
        output["node_id"] == binding.node_id and output["output_name"] == binding.output_name
        for output in compaction_outputs(data)
    ):
        msg = "Connect Compaction Input to the selected CompactionResult output before running."
        raise ValueError(msg)
    if flow_revision(data) != binding.revision:
        msg = "The compaction flow changed. Review it and update its binding before running."
        raise CompactionSourceChangedError(msg)


def parse_compaction_binding(value: str) -> CompactionBinding | None:
    return CompactionBinding.model_validate_json(value) if value.strip() not in {"", "null", "{}"} else None


class CompactionFlowRunner:
    def __init__(self, component, binding: CompactionBinding, model):
        self.binding = binding
        self.model = model
        self.runner = ReviewedFlowRunner(component, validate=validate_compaction_binding, label="compaction")

    async def __call__(self, messages, *, estimated_tokens):
        async def invoke(rows):
            token = COMPACTION_MODEL.set(self.model)
            try:
                result = await self.runner(
                    self.binding,
                    {
                        COMPACTION_INPUT: {
                            "messages": rows,
                            "trigger_reason": "proactive",
                            "estimated_tokens": estimated_tokens,
                            "trigger_tokens": self.binding.trigger_tokens,
                        }
                    },
                )
                if not isinstance(result, CompactionResult):
                    msg = "A compaction flow must return CompactionResult, not a display artifact."
                    raise TypeError(msg)
                return result
            finally:
                COMPACTION_MODEL.reset(token)

        return await RunnableLambda(invoke, name="harness_compaction_flow").ainvoke(
            messages_to_table(messages).to_dict(orient="records"), config={"tags": ["harness:compaction"]}
        )
