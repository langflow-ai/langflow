from collections.abc import Callable

from langflow.components.inputs.ChatInput import ChatInput


def test_component_to_toolkit():
    chat_input = ChatInput()
    tools = chat_input.to_toolkit()
    assert len(tools) == 1
    tool = tools[0]

    assert tool.name == "ChatInput-message_response"
    terms = [
        "message_response",
        "files",
        "input_value",
        "sender",
        "sender_name",
        "session_id",
        "should_store_message",
    ]
    assert all(term in tool.description for term in terms)

    assert isinstance(tool.func, Callable)
    assert tool.args_schema is not None


def test_component_to_tool_has_no_component_as_tool():
    chat_input = ChatInput()
    tools = chat_input.to_toolkit()
    assert len(tools) == 1
