"""The reviewed AgenticLoop flow: a While Loop whose Last Message is the Agent's answer, run as the Agent's loop."""

from langchain_core.runnables import RunnableLambda

from lfx.base.agents.context_messages import messages_to_table
from lfx.base.agents.loop_rows import HARNESS_LOOP_KEY, row_to_message
from lfx.base.agents.loop_runtime import HarnessLoopRuntime
from lfx.projects.bindings import FlowBinding, check_required_inputs, flow_revision
from lfx.projects.context import AGENT_CONTEXT
from lfx.projects.invocation import ReviewedFlowRunner

LOOP_OUTPUT = "last_message"


def parse_loop_binding(value: str) -> FlowBinding | None:
    return FlowBinding.model_validate_json(value) if value.strip() not in {"", "null", "{}"} else None


def loop_outputs(data: dict) -> list[dict]:
    """The Last Message outputs of While Loops that feed a node. An output nothing reads is never built."""
    check_required_inputs(data)
    fed = {
        (edge.get("source"), edge.get("data", {}).get("sourceHandle", {}).get("name")) for edge in data.get("edges", [])
    }
    return [
        {
            "node_id": node["id"],
            "output_name": LOOP_OUTPUT,
            "display_name": f"{node['data'].get('node', {}).get('display_name', node['id'])} · Last Message",
        }
        for node in data.get("nodes", [])
        if node.get("data", {}).get("type") == "WhileLoopComponent" and (node["id"], LOOP_OUTPUT) in fed
    ]


def validate_loop_binding(data: dict, binding: FlowBinding) -> None:
    if not any(
        output["node_id"] == binding.node_id and output["output_name"] == binding.output_name
        for output in loop_outputs(data)
    ):
        msg = "Connect a While Loop's Last Message output to a Chat Output and bind it before running."
        raise ValueError(msg)
    if flow_revision(data) != binding.revision:
        msg = "The loop flow changed. Review it and update its binding before running."
        raise ValueError(msg)


def loop_flow_runnable(
    component, binding: FlowBinding, *, llm, tools: list, system_prompt: str, middleware: list
) -> RunnableLambda:
    """The Agent's loop as a runnable for `run_agent` to stream: the reviewed loop flow, run quiet.

    The flow gets the turn `run_agent` built (`state["messages"]`) through Agent Context. Its blocks make their calls
    through a HarnessLoopRuntime built here from the Agent's middleware. It is built inside the streamed run and makes
    its calls in that context, so every harness control applies, the tools run under the Agent's scopes, and the chat
    shows one Agent message. The flow's Last Message is the answer, and `finish()` then runs the after-agent hooks.
    """
    runner = ReviewedFlowRunner(component, validate=validate_loop_binding, label="loop", field_name="agentic_loop")

    async def run(state: dict) -> dict:
        runtime = HarnessLoopRuntime(model=llm, tools=tools, system_prompt=system_prompt, middleware=middleware)
        turn = {"messages": messages_to_table(state["messages"]).to_dict(orient="records")}
        answer = await runner(binding, {AGENT_CONTEXT: turn}, live={HARNESS_LOOP_KEY: runtime}, quiet=True)
        await runtime.finish()
        # The runtime state carries source evidence and run configurations, as a create_agent result does.
        return {"messages": [row_to_message(answer.data)], **runtime.state}

    return RunnableLambda(run, name="harness_loop_flow")
