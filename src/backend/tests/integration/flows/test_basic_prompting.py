import pytest
from langflow.components.inputs import ChatInput
from langflow.components.outputs import ChatOutput
from langflow.components.prompts import PromptComponent
from langflow.graph import Graph
from langflow.schema.message import Message
from tests.integration.utils import run_flow


@pytest.mark.asyncio
async def test_simple_no_llm():
    graph = Graph()
    input = graph.add_component(ChatInput())
    output = graph.add_component(ChatOutput())
    component = PromptComponent(template="This is the message: {var1}", var1="")
    prompt = graph.add_component(component)
    graph.add_component_edge(input, ("message", "var1"), prompt)
    graph.add_component_edge(prompt, ("prompt", "input_value"), output)
    outputs = await run_flow(graph, run_input="hello!")
    assert isinstance(outputs["message"], Message)
    assert outputs["message"].text == "This is the message: hello!"
