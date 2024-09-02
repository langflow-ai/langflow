from collections.abc import Callable

import pytest

from langflow.base.tools.component_tool import ComponentToolkit
from langflow.components.inputs.ChatInput import ChatInput


@pytest.fixture
def client():
    pass


def test_component_to_tool():
    chat_input = ChatInput()
    toolkit = chat_input.to_toolkit()
    assert isinstance(toolkit, ComponentToolkit)
    assert toolkit.component == chat_input

    tools = toolkit.get_tools()
    assert len(tools) == 1
    tool = tools[0]

    assert tool.name == "ChatInput.message_response"
    assert (
        tool.description
        == "message_response(files: file, input_value: Message, sender: str, sender_name: Message, session_id: Message, should_store_message: bool) - Get chat inputs from the Playground."
    )
    assert isinstance(tool.func, Callable)
    assert tool.args_schema is not None
