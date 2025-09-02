from collections import deque

import pytest

from lfx.components.input_output import ChatInput, ChatOutput, TextOutputComponent
from lfx.graph import Graph
from lfx.graph.graph.constants import Finish


@pytest.mark.asyncio
async def test_graph_not_prepared():
    chat_input = ChatInput()
    chat_output = ChatOutput()
    graph = Graph()
    graph.add_component(chat_input)
    graph.add_component(chat_output)
    with pytest.raises(ValueError, match="Graph not prepared"):
        await graph.astep()


@pytest.mark.asyncio
async def test_graph_with_edge():
    chat_input = ChatInput()
    chat_output = ChatOutput()
    graph = Graph()
    input_id = graph.add_component(chat_input)
    output_id = graph.add_component(chat_output)
    graph.add_component_edge(input_id, (chat_input.outputs[0].name, chat_input.inputs[0].name), output_id)
    graph.prepare()
    # ensure prepare is idempotent
    graph.prepare()
    assert graph._run_queue == deque([input_id])
    await graph.astep()
    assert graph._run_queue == deque([output_id])

    assert graph.vertices[0].id == input_id
    assert graph.vertices[1].id == output_id
    assert graph.edges[0].source_id == input_id
    assert graph.edges[0].target_id == output_id


@pytest.mark.asyncio
async def test_graph_functional():
    chat_input = ChatInput(_id="chat_input")
    chat_input.set(should_store_message=False)
    chat_output = ChatOutput(input_value="test", _id="chat_output")
    chat_output.set(sender_name=chat_input.message_response)
    graph = Graph(chat_input, chat_output)
    assert graph._run_queue == deque(["chat_input"])
    await graph.astep()
    assert graph._run_queue == deque(["chat_output"])

    assert graph.vertices[0].id == "chat_input"
    assert graph.vertices[1].id == "chat_output"
    assert graph.edges[0].source_id == "chat_input"
    assert graph.edges[0].target_id == "chat_output"


@pytest.mark.asyncio
async def test_graph_functional_async_start():
    chat_input = ChatInput(_id="chat_input")
    chat_output = ChatOutput(input_value="test", _id="chat_output")
    chat_output.set(sender_name=chat_input.message_response)
    graph = Graph(chat_input, chat_output)
    # Now iterate through the graph
    # and check that the graph is running
    # correctly
    ids = ["chat_input", "chat_output"]
    results = [result async for result in graph.async_start()]

    assert len(results) == 3
    assert all(result.vertex.id in ids for result in results if hasattr(result, "vertex"))
    assert results[-1] == Finish()


def test_graph_functional_start_end():
    chat_input = ChatInput(_id="chat_input")
    text_output = TextOutputComponent(_id="text_output")
    text_output.set(input_value=chat_input.message_response)
    chat_output = ChatOutput(input_value="test", _id="chat_output")
    chat_output.set(input_value=text_output.text_response)
    graph = Graph(chat_input, text_output)
    graph.prepare()
    # Now iterate through the graph
    # and check that the graph is running
    # correctly
    ids = ["chat_input", "text_output"]
    results = list(graph.start())

    assert len(results) == len(ids) + 1
    assert all(result.vertex.id in ids for result in results if hasattr(result, "vertex"))
    assert results[-1] == Finish()
    # Now, using the same components but different start and end components
    graph = Graph(chat_input, chat_output)
    graph.prepare()
    ids = ["chat_input", "chat_output", "text_output"]
    results = []
    for result in graph.start():
        results.append(result)

    assert len(results) == len(ids) + 1
    assert all(result.vertex.id in ids for result in results if hasattr(result, "vertex"))
    assert results[-1] == Finish()


# TODO: Move to Langflow tests
@pytest.mark.skip(reason="Temporarily disabled")
def test_graph_set_with_valid_component():
    from lfx.components.langchain_utilities.tool_calling import ToolCallingAgentComponent
    from lfx.components.tools.yahoo_finance import YfinanceToolComponent

    tool = YfinanceToolComponent()
    tool_calling_agent = ToolCallingAgentComponent()
    tool_calling_agent.set(tools=[tool])
