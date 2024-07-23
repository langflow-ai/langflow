from collections import deque

import pytest

from langflow import components
from langflow.graph.graph.base import Graph


@pytest.fixture
def client():
    pass


@pytest.mark.asyncio
async def test_graph_not_prepared():
    chat_input = components.inputs.ChatInput()
    chat_output = components.outputs.ChatOutput()
    graph = Graph()
    graph.add_component("chat_input", chat_input)
    graph.add_component("chat_output", chat_output)
    graph.add_component_edge("chat_input", (chat_input.outputs[0].name, chat_input.inputs[0].name), "chat_output")
    with pytest.raises(ValueError):
        await graph.astep()


@pytest.mark.asyncio
async def test_graph():
    chat_input = components.inputs.ChatInput()
    chat_output = components.outputs.ChatOutput()
    graph = Graph()
    graph.add_component("chat_input", chat_input)
    graph.add_component("chat_output", chat_output)
    graph.add_component_edge("chat_input", (chat_input.outputs[0].name, chat_input.inputs[0].name), "chat_output")
    graph.prepare()
    assert graph._run_queue == deque(["chat_input"])
    await graph.astep()
    assert graph._run_queue == deque(["chat_output"])

    assert graph.vertices[0].id == "chat_input"
    assert graph.vertices[1].id == "chat_output"
    assert graph.edges[0].source_id == "chat_input"
    assert graph.edges[0].target_id == "chat_output"


@pytest.mark.asyncio
async def test_graph_functional():
    chat_input = components.inputs.ChatInput(_id="chat_input")
    chat_output = components.outputs.ChatOutput(message="test", _id="chat_output")(
        sender_name=chat_input.message_response
    )
    graph = Graph(chat_input, chat_output)
    assert graph._run_queue == deque([])
    graph.prepare()
    assert graph._run_queue == deque(["chat_input"])
    await graph.astep()
    assert graph._run_queue == deque(["chat_output"])

    assert graph.vertices[0].id == "chat_input"
    assert graph.vertices[1].id == "chat_output"
    assert graph.edges[0].source_id == "chat_input"
    assert graph.edges[0].target_id == "chat_output"
