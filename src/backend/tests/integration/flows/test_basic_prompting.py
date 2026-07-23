from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models_and_agents import PromptComponent
from lfx.graph import Graph
from lfx.schema.message import Message

from tests.integration.utils import pyleak_marker, run_flow


# Disable event-loop-block detection: the MCP StreamableHTTP session manager
# started by the FastAPI lifespan (via the autouse `_start_app(client)` fixture)
# initiates an anyio `try_connect` that can exceed pyleak's 0.2s blocking
# threshold under load, producing flaky EventLoopBlockError. Same rationale as
# tests/integration/components/inputs/test_chat_input.py.
@pyleak_marker(blocking=False)
async def test_simple_no_llm():
    graph = Graph()
    flow_input = graph.add_component(ChatInput())
    flow_output = graph.add_component(ChatOutput())
    component = PromptComponent(template="This is the message: {var1}", var1="")
    prompt = graph.add_component(component)
    graph.add_component_edge(flow_input, ("message", "var1"), prompt)
    graph.add_component_edge(prompt, ("prompt", "input_value"), flow_output)
    outputs = await run_flow(graph, run_input="hello!")
    assert isinstance(outputs["message"], Message)
    assert outputs["message"].text == "This is the message: hello!"
