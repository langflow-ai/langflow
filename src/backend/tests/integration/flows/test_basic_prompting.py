from langflow.schema.message import Message

from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.processing import PromptComponent
from lfx.graph import Graph
from tests.integration.utils import pyleak_marker, run_flow


@pyleak_marker()
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
