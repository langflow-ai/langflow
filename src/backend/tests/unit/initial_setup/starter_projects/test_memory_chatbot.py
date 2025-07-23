import operator
from collections import deque
from typing import TYPE_CHECKING

import pytest

from langflow.code_gen.graph import generate_script_from_graph
from langflow.components.helpers.Memory import MemoryComponent
from langflow.components.inputs.ChatInput import ChatInput
from langflow.components.models.OpenAIModel import OpenAIModelComponent
from langflow.components.outputs.ChatOutput import ChatOutput
from langflow.components.prompts.Prompt import PromptComponent
from langflow.graph import Graph
from langflow.components.helpers.memory import MemoryComponent
from langflow.components.input_output import ChatInput, ChatOutput
from langflow.components.openai.openai_chat_model import OpenAIModelComponent
from langflow.components.processing import PromptComponent
from langflow.components.processing.converter import TypeConverterComponent
from langflow.graph.graph.base import Graph
from langflow.graph.graph.constants import Finish

if TYPE_CHECKING:
    from langflow.graph.graph.schema import GraphDump


@pytest.fixture
def memory_chatbot_graph():
    session_id = "test_session_id"
    template = """{context}

User: {user_message}
AI: """
    memory_component = MemoryComponent(_id="chat_memory")
    memory_component.set(session_id=session_id)
    chat_input = ChatInput(_id="chat_input")
    type_converter = TypeConverterComponent(_id="type_converter")
    type_converter.set(input_data=memory_component.retrieve_messages_dataframe)
    prompt_component = PromptComponent(_id="prompt")
    prompt_component.set(
        template=template,
        user_message=chat_input.message_response,
        context=type_converter.convert_to_message,
    )
    openai_component = OpenAIModelComponent(_id="openai")
    openai_component.set(
        input_value=prompt_component.build_prompt, max_tokens=100, temperature=0.1, api_key="test_api_key"
    )
    openai_component.set_on_output(name="text_output", value="Mock response", cache=True)

    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=openai_component.text_response)

    graph = Graph(chat_input, chat_output)
    assert graph.in_degree_map == {
        "chat_output": 1,
        "type_converter": 1,
        "prompt": 2,
        "openai": 1,
        "chat_input": 0,
        "chat_memory": 0,
    }
    return graph


@pytest.mark.usefixtures("client")
def test_memory_chatbot(memory_chatbot_graph):
    # Now we run step by step
    expected_order = deque(["chat_input", "chat_memory", "type_converter", "prompt", "openai", "chat_output"])
    assert memory_chatbot_graph.in_degree_map == {
        "chat_output": 1,
        "type_converter": 1,
        "prompt": 2,
        "openai": 1,
        "chat_input": 0,
        "chat_memory": 0,
    }
    assert memory_chatbot_graph.vertices_layers == [["type_converter"], ["prompt"], ["openai"], ["chat_output"]]
    assert memory_chatbot_graph.first_layer == ["chat_input", "chat_memory"]

    for step in expected_order:
        result = memory_chatbot_graph.step()
        if isinstance(result, Finish):
            break

        assert step == result.vertex.id, (memory_chatbot_graph.in_degree_map, memory_chatbot_graph.vertices_layers)


def test_memory_chatbot_dump_structure(memory_chatbot_graph: Graph):
    # Now we run step by step
    graph_dict = memory_chatbot_graph.dump(
        name="Memory Chatbot", description="A memory chatbot", endpoint_name="membot"
    )
    assert isinstance(graph_dict, dict)
    # Test structure
    assert "data" in graph_dict
    assert "is_component" in graph_dict

    data_dict = graph_dict["data"]
    assert "nodes" in data_dict
    assert "edges" in data_dict
    assert "description" in graph_dict
    assert "endpoint_name" in graph_dict

    # Test data
    nodes = data_dict["nodes"]
    edges = data_dict["edges"]
    description = graph_dict["description"]
    endpoint_name = graph_dict["endpoint_name"]

    assert len(nodes) == 6
    assert len(edges) == 5
    assert description is not None
    assert endpoint_name is not None


def test_memory_chatbot_dump_components_and_edges(memory_chatbot_graph: Graph):
    # Check all components and edges were dumped correctly
    graph_dict: GraphDump = memory_chatbot_graph.dump(
        name="Memory Chatbot", description="A memory chatbot", endpoint_name="membot"
    )

    data_dict = graph_dict["data"]
    nodes = data_dict["nodes"]
    edges = data_dict["edges"]

    # sort the nodes by id
    nodes = sorted(nodes, key=operator.itemgetter("id"))

    # Check each node
    assert nodes[0]["data"]["type"] == "ChatInput"
    assert nodes[0]["id"] == "chat_input"

    assert nodes[1]["data"]["type"] == "Memory"
    assert nodes[1]["id"] == "chat_memory"

    assert nodes[2]["data"]["type"] == "ChatOutput"
    assert nodes[2]["id"] == "chat_output"

    assert nodes[3]["data"]["type"] == "OpenAIModel"
    assert nodes[3]["id"] == "openai"

    assert nodes[4]["data"]["type"] == "Prompt Template"
    assert nodes[4]["id"] == "prompt"

    # Check edges
    expected_edges = [
        ("chat_input", "prompt"),
        ("chat_memory", "type_converter"),
        ("type_converter", "prompt"),
        ("prompt", "openai"),
        ("openai", "chat_output"),
    ]

    assert len(edges) == len(expected_edges)

    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        assert (source, target) in expected_edges, edge


def test_memory_chatbot_generate_script(memory_chatbot_graph: Graph):
    script = generate_script_from_graph(memory_chatbot_graph)
    expected_script = """from langflow.components.inputs.ChatInput import ChatInput
from langflow.components.outputs.ChatOutput import ChatOutput
from langflow.components.helpers.Memory import MemoryComponent
from langflow.components.prompts.Prompt import PromptComponent
from langflow.components.models.OpenAIModel import OpenAIModelComponent

chat_input = ChatInput(_id='chat_input')
chat_memory = MemoryComponent(_id='chat_memory')
prompt = PromptComponent(_id='prompt')
openai = OpenAIModelComponent(_id='openai')
chat_output = ChatOutput(_id='chat_output')

# Setting up the components
chat_memory.set(session_id='test_session_id')
prompt.set(template='{context}\\n\\nUser: {user_message}\\nAI: ', user_message=chat_input.message_response, context=chat_memory.retrieve_messages_as_text)
openai.set(input_value=prompt.build_prompt, max_tokens=100, temperature=0.1, api_key='test_api_key')
chat_output.set(input_value=openai.text_response)

# Building the graph
graph = Graph(entry=chat_input, exit=chat_output)
"""
    assert script == expected_script
