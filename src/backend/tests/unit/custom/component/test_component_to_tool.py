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


def test_component_add_tool_output():
    chat_input = ChatInput()
    assert len(chat_input.outputs) == 1
    chat_input._append_tool_output()
    assert len(chat_input.outputs) == 2
    assert chat_input.outputs[-1].name == "component_as_tool"
    assert chat_input.outputs[-1].display_name == "Tool"
    assert chat_input.outputs[-1].method == "to_tool"
