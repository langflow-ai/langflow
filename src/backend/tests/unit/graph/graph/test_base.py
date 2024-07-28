import re
from collections import deque

import pytest

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


def generate_import_statement(instance):
    class_name = instance.__class__.__name__
    module_path = instance.__class__.__module__
    parts = module_path.split(".")

    # Construct the correct import statement
    if len(parts) > 2:
        module_path = ".".join(parts)
        return f"from {module_path} import {class_name}"
    else:
        return f"from {module_path} import {class_name}"


def get_variable_name(instance):
    return re.sub(r"[^0-9a-zA-Z_]", "_", instance._id.lower())


def generate_instantiation_string(instance):
    class_name = instance.__class__.__name__
    instance_id = instance._id
    variable_name = get_variable_name(instance)
    return f"{variable_name} = {class_name}(_id='{instance_id}')"


def generate_call_string(instance):
    variable_name = get_variable_name(instance)
    if hasattr(instance, "_call_inputs"):
        args = ", ".join(
            f"{key}={get_variable_name(value.__self__)}.{value.__name__}" if callable(value) else f"{key}={repr(value)}"
            for key, value in instance._call_inputs.items()
        )
        if args:
            return f"{variable_name}({args})"


def generate_script(*instances):
    import_statements = set()
    instantiation_strings = []
    call_strings = []

    for instance in instances:
        import_statements.add(generate_import_statement(instance))
        instantiation_strings.append(generate_instantiation_string(instance))
        call_string = generate_call_string(instance)

        if call_string:
            call_strings.append(call_string)

    import_code = "\n".join(sorted(import_statements))
    instantiation_code = "\n".join(instantiation_strings)
    call_code = "\n".join(call_strings)

    return f"{import_code}\n\n{instantiation_code}\n\n{call_code}"


def test_generate_code():
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
