import pytest

from langflow.components.helpers.Memory import MemoryComponent
from langflow.components.inputs.ChatInput import ChatInput
from langflow.components.models.OpenAIModel import OpenAIModelComponent
from langflow.components.outputs.ChatOutput import ChatOutput
from langflow.components.prompts.Prompt import PromptComponent
from langflow.graph import Graph
from langflow.graph.graph.constants import Finish
from langflow.graph.graph.state_model import create_state_model_from_graph


@pytest.fixture
def client():
    pass


def test_graph_state_model():
    session_id = "test_session_id"
    template = """{context}

User: {user_message}
AI: """
    memory_component = MemoryComponent(_id="chat_memory")
    memory_component.set(session_id=session_id)
    chat_input = ChatInput(_id="chat_input")
    prompt_component = PromptComponent(_id="prompt")
    prompt_component.set(
        template=template, user_message=chat_input.message_response, context=memory_component.retrieve_messages_as_text
    )
    openai_component = OpenAIModelComponent(_id="openai")
    openai_component.set(
        input_value=prompt_component.build_prompt, max_tokens=100, temperature=0.1, api_key="test_api_key"
    )
    openai_component.get_output("text_output").value = "Mock response"

    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=openai_component.text_response)

    graph = Graph(chat_input, chat_output)

    GraphStateModel = create_state_model_from_graph(graph)
    assert GraphStateModel.__name__ == "GraphStateModel"
    assert list(GraphStateModel.model_computed_fields.keys()) == [
        "chat_input",
        "chat_output",
        "openai",
        "prompt",
        "chat_memory",
    ]


def test_graph_functional_start_graph_state_update():
    chat_input = ChatInput(_id="chat_input")
    chat_input.set(input_value="Test Sender Name")
    chat_output = ChatOutput(input_value="test", _id="chat_output")
    chat_output.set(sender_name=chat_input.message_response)

    graph = Graph(chat_input, chat_output)
    graph.prepare()
    # Now iterate through the graph
    # and check that the graph is running
    # correctly
    GraphStateModel = create_state_model_from_graph(graph)
    graph_state_model = GraphStateModel()
    ids = ["chat_input", "chat_output"]
    results = []
    for result in graph.start():
        results.append(result)

    assert len(results) == 3
    assert all(result.vertex.id in ids for result in results if hasattr(result, "vertex"))
    assert results[-1] == Finish()

    assert graph_state_model.__class__.__name__ == "GraphStateModel"
    assert graph_state_model.chat_input.message.get_text() == "Test Sender Name"
    assert graph_state_model.chat_output.message.get_text() == "test"
