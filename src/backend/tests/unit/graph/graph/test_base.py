from langflow import components
from langflow.graph.graph.base import Graph


def test_graph():
    chat_input = components.inputs.ChatInput()
    chat_output = components.outputs.ChatOutput()
    graph = Graph()
    graph.add_component("chat_input", chat_input)
    graph.add_component("chat_output", chat_output)
    graph.add_component_edge("chat_input", (chat_input.outputs[0].name, chat_input.inputs[0].name), "chat_output")
    assert graph.vertices[0].id == "chat_input"
    assert graph.vertices[1].id == "chat_output"
    assert graph.edges[0].source_id == "chat_input"
    assert graph.edges[0].target_id == "chat_output"
