from collections import deque

import pytest

from langflow import components
from langflow.code_gen.component import generate_instantiation_string, generate_script
from langflow.code_gen.generic import generate_import_statement
from langflow.components.inputs.ChatInput import ChatInput
from langflow.components.outputs.ChatOutput import ChatOutput
from langflow.components.outputs.TextOutput import TextOutputComponent
from langflow.graph.graph.base import Graph
from langflow.graph.graph.constants import Finish


@pytest.fixture
def client():
    pass


@pytest.mark.asyncio
async def test_graph_not_prepared():
    chat_input = ChatInput()
    chat_output = ChatOutput()
    graph = Graph()
    graph.add_component("chat_input", chat_input)
    graph.add_component("chat_output", chat_output)
    with pytest.raises(ValueError):
        await graph.astep()


@pytest.mark.asyncio
async def test_graph():
    chat_input = ChatInput()
    chat_output = ChatOutput()
    graph = Graph()
    graph.add_component("chat_input", chat_input)
    graph.add_component("chat_output", chat_output)
    with pytest.raises(ValueError, match="Graph has vertices but no edges"):
        graph.prepare()


@pytest.mark.asyncio
async def test_graph_with_edge():
    chat_input = ChatInput()
    chat_output = ChatOutput()
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
    chat_input = ChatInput(_id="chat_input")
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
    results = []
    async for result in graph.async_start():
        results.append(result)

    assert len(results) == 3
    assert all(result.vertex.id in ids for result in results if hasattr(result, "vertex"))
    assert results[-1] == Finish()


def test_graph_functional_start():
    chat_input = ChatInput(_id="chat_input")
    chat_output = ChatOutput(input_value="test", _id="chat_output")
    chat_output.set(sender_name=chat_input.message_response)
    graph = Graph(chat_input, chat_output)
    graph.prepare()
    # Now iterate through the graph
    # and check that the graph is running
    # correctly
    ids = ["chat_input", "chat_output"]
    results = []
    for result in graph.start():
        results.append(result)

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
    results = []
    for result in graph.start():
        results.append(result)

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


def test_generate_import_statement_and_instantiation_string():
    chat_input_instance = components.inputs.ChatInput(_id="chatInput-1230")
    import_statement = generate_import_statement(chat_input_instance)
    instantiation_string = generate_instantiation_string(chat_input_instance)
    assert import_statement == "from langflow.components.inputs import ChatInput"
    assert instantiation_string == "chatinput_1230 = ChatInput(_id='chatInput-1230')"


def test_generate_script():
    chat_input = components.inputs.ChatInput(_id="chatInput-1230")
    text_output = components.outputs.TextOutput.TextOutputComponent(_id="textoutput-1231")(
        input_value=chat_input.message_response
    )
    script = generate_script(chat_input, text_output)
    assert (
        script
        == """from langflow.components.inputs.ChatInput import ChatInput
from langflow.components.outputs.TextOutput import TextOutputComponent

chatinput_1230 = ChatInput(_id='chatInput-1230')
textoutput_1231 = TextOutputComponent(_id='textoutput-1231')

textoutput_1231(input_value=chatinput_1230.message_response)"""
    )


def test_gerenate_script_from_graph():
    chat_input = components.inputs.ChatInput(_id="chatInput-1230")
    text_output = components.outputs.TextOutput.TextOutputComponent(_id="textoutput-1231")(
        input_value=chat_input.message_response
    )
    chat_output = components.outputs.ChatOutput(input_value="test", _id="chatOutput-1232")(
        input_value=text_output.text_response
    )
    graph = Graph(chat_input, chat_output)
    script = generate_script(*graph.sort_components())
    assert (
        script
        == """from langflow.components.inputs.ChatInput import ChatInput
from langflow.components.outputs.ChatOutput import ChatOutput
from langflow.components.outputs.TextOutput import TextOutputComponent

chatinput_1230 = ChatInput(_id='chatInput-1230')
textoutput_1231 = TextOutputComponent(_id='textoutput-1231')
chatoutput_1232 = ChatOutput(_id='chatOutput-1232')

textoutput_1231(input_value=chatinput_1230.message_response)
chatoutput_1232(input_value=textoutput_1231.text_response)"""
    )
