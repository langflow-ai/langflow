import pytest

from langflow.base.tools.component_tool import ComponentToolkit
from langflow.components.inputs.ChatInput import ChatInput
from langflow.schema.message import Message


@pytest.fixture
def client():
    pass


def test_component_tool():
    chat_input = ChatInput()
    component_toolkit = ComponentToolkit(component=chat_input)
    component_tool = component_toolkit.get_tools()[0]
    assert component_tool.name == "ChatInput.message_response"
    assert component_tool.description == "Description: Get chat inputs from the Playground.\nOutput Types: ['Message']"
    assert component_tool.args == {
        "input_value": {
            "default": "",
            "description": "Message to be passed as input.",
            "title": "Input Value",
            "type": "string",
        },
        "should_store_message": {
            "default": True,
            "description": "Store the message in the history.",
            "title": "Should Store Message",
            "type": "boolean",
        },
        "sender": {
            "default": "User",
            "description": "Type of sender.",
            "enum": ["Machine", "User"],
            "title": "Sender",
            "type": "string",
        },
        "sender_name": {
            "default": "User",
            "description": "Name of the sender.",
            "title": "Sender Name",
            "type": "string",
        },
        "session_id": {
            "default": "",
            "description": "The session ID of the chat. If empty, the current session ID parameter will be used.",
            "title": "Session Id",
            "type": "string",
        },
        "files": {
            "default": "",
            "description": "Files to be sent with the message.",
            "items": {"type": "string"},
            "title": "Files",
            "type": "array",
        },
    }
    assert component_toolkit.component == chat_input

    result = component_tool.invoke(input=dict(input_value="test"))
    assert isinstance(result, Message)
    assert result.get_text() == "test"
