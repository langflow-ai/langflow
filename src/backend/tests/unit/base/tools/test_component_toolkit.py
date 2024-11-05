import os

import pytest
from langflow.base.tools.component_tool import ComponentToolkit
from langflow.components.agents import ToolCallingAgentComponent
from langflow.components.inputs import ChatInput
from langflow.components.models import OpenAIModelComponent
from langflow.components.outputs import ChatOutput
from langflow.graph import Graph
from langflow.schema.message import Message
from langflow.services.settings.feature_flags import FEATURE_FLAGS


@pytest.fixture
def _add_toolkit_output():
    FEATURE_FLAGS.add_toolkit_output = True
    yield
    FEATURE_FLAGS.add_toolkit_output = False


def test_component_tool():
    chat_input = ChatInput()
    component_toolkit = ComponentToolkit(component=chat_input)
    component_tool = component_toolkit.get_tools()[0]
    assert component_tool.name == "ChatInput-message_response"
    terms = [
        "message_response",
        "files",
        "input_value",
        "sender",
        "sender_name",
        "session_id",
        "should_store_message",
    ]
    assert all(term in component_tool.description for term in terms)
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
        "background_color": {
            "default": "",
            "description": "The background color of the icon.",
            "title": "Background Color",
            "type": "string",
        },
        "chat_icon": {
            "default": "",
            "description": "The icon of the message.",
            "title": "Chat Icon",
            "type": "string",
        },
        "text_color": {
            "default": "",
            "description": "The text color of the name",
            "title": "Text Color",
            "type": "string",
        },
    }
    assert component_toolkit.component == chat_input

    result = component_tool.invoke(input={"input_value": "test"})
    assert isinstance(result, Message)
    assert result.get_text() == "test"


@pytest.mark.api_key_required
@pytest.mark.usefixtures("_add_toolkit_output")
def test_component_tool_with_api_key():
    chat_output = ChatOutput()
    openai_llm = OpenAIModelComponent()
    openai_llm.set(api_key=os.environ["OPENAI_API_KEY"])
    tool_calling_agent = ToolCallingAgentComponent()
    tool_calling_agent.set(
        llm=openai_llm.build_model, tools=[chat_output], input_value="Which tools are available? Please tell its name."
    )

    g = Graph(start=tool_calling_agent, end=tool_calling_agent)
    assert g is not None
    results = list(g.start())
    assert len(results) == 4
    assert "message_response" in tool_calling_agent._outputs_map["response"].value.get_text()
