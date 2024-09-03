import os

import pytest

from langflow.base.tools.component_tool import ComponentToolkit
from langflow.components.agents.ToolCallingAgent import ToolCallingAgentComponent
from langflow.components.inputs.ChatInput import ChatInput
from langflow.components.models.OpenAIModel import OpenAIModelComponent
from langflow.components.outputs import ChatOutput
from langflow.graph.graph.base import Graph
from langflow.schema.message import Message
from langflow.services.settings.feature_flags import FEATURE_FLAGS


@pytest.fixture
def client():
    pass


def test_component_tool():
    chat_input = ChatInput()
    component_toolkit = ComponentToolkit(component=chat_input)
    component_tool = component_toolkit.get_tools()[0]
    assert component_tool.name == "ChatInput.message_response"
    assert (
        component_tool.description
        == "message_response(files: file, input_value: Message, sender: str, sender_name: Message, session_id: Message, should_store_message: bool) - Get chat inputs from the Playground."
    )
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


@pytest.mark.api_key_required
def test_component_tool_with_api_key(client):
    FEATURE_FLAGS.add_toolkit_output = True
    chat_output = ChatOutput()
    openai_llm = OpenAIModelComponent()
    openai_llm.set(api_key=os.environ["OPENAI_API_KEY"])
    tool_calling_agent = ToolCallingAgentComponent()
    tool_calling_agent.set(
        llm=openai_llm.build_model, tools=[chat_output.to_toolkit], input_value="Which tools are available?"
    )

    g = Graph(start=tool_calling_agent, end=tool_calling_agent)
    assert g is not None
    results = list(g.start())
    assert len(results) == 4
    assert "message_response" in tool_calling_agent.outputs[1].value.get_text()
