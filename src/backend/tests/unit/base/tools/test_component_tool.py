import copy

import pytest

from langflow.base.tools.component_tool import ComponentTool
from langflow.components.agents.ToolCallingAgent import \
    ToolCallingAgentComponent
from langflow.components.inputs.ChatInput import ChatInput
from langflow.components.outputs.ChatOutput import ChatOutput
from langflow.graph.graph.base import Graph
from langflow.services.deps import get_tracing_service


@pytest.fixture
def client():
    pass


def test_copy_component_tool():
    chat_input = ChatInput()
    chat_output = ChatOutput()
    chat_output.set(input_value=chat_input.message_response)
    graph = Graph(start=chat_input, end=chat_output)
    assert chat_input.graph == graph
    component_tool = ComponentTool(component=chat_input)
    component_tool_copy = copy.copy(component_tool)
    assert component_tool_copy.name == "ChatInput"
    assert component_tool_copy.description == chat_input.description
    component_tool_deepcopy = copy.deepcopy(component_tool)
    assert component_tool_deepcopy.name == "ChatInput"
    assert component_tool_deepcopy.description == chat_input.description


def test_component_tool_tracing_service_interaction():
    tracing_service = get_tracing_service()
    chat_output = ChatOutput(_add_tool_output=True, _tracing_service=tracing_service)

    tool_calling_agent = ToolCallingAgentComponent(_tracing_service=tracing_service)
    tool_calling_agent.set(tools=[chat_output.to_tool], input_value="Hello, World!")

    graph = Graph(start=chat_output, end=tool_calling_agent)
    assert chat_output.graph == graph
    assert tool_calling_agent.graph == graph
    results = list(graph.start())
    assert len(results) > 1


def test_component_tool():
    chat_input = ChatInput()
    component_tool = ComponentTool(component=chat_input)
    assert component_tool.name == "ChatInput"
    assert component_tool.description == chat_input.description
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
    assert component_tool.component == chat_input

    result = component_tool.invoke(input=dict(input_value="test"))
    assert isinstance(result, dict)
    assert hasattr(result["message"], "get_text")
    assert result["message"].get_text() == "test"
