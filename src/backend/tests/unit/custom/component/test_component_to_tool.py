import pytest

from langflow.components.inputs.ChatInput import ChatInput


@pytest.fixture
def client():
    pass


def test_component_to_tool():
    chat_input = ChatInput()
    tool = chat_input.to_tool()
    assert tool.name == "ChatInput"
    assert tool.description == "Get chat inputs from the Playground."
    assert tool.component._id == chat_input._id
