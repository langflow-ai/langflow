"""Tests for extract_final_text — pulls the final assistant text from a LangGraph state.

Slice S4 of langchain_classic.AgentExecutor → langchain.agents.create_agent migration.
The new `on_chain_end` event emits `data.output = {"messages": [HumanMessage, ..., AIMessage]}`
instead of the legacy `AgentFinish`.
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from lfx.base.agents.graph_event_extractor import extract_final_text


def test_should_extract_final_text_from_messages_state_when_chain_ends() -> None:
    state = {
        "messages": [
            HumanMessage(content="hi"),
            AIMessage(content="final answer"),
        ]
    }

    assert extract_final_text(state) == "final answer"


def test_should_extract_text_from_ai_message_with_list_content() -> None:
    state = {
        "messages": [
            AIMessage(content=[{"type": "text", "text": "hello world"}]),
        ]
    }

    assert extract_final_text(state) == "hello world"


def test_should_concatenate_multiple_text_parts_in_list_content() -> None:
    state = {
        "messages": [
            AIMessage(content=[{"type": "text", "text": "part 1 "}, {"type": "text", "text": "part 2"}]),
        ]
    }

    assert extract_final_text(state) == "part 1 part 2"


def test_should_skip_tool_use_parts_when_extracting_text() -> None:
    state = {
        "messages": [
            AIMessage(
                content=[
                    {"type": "text", "text": "let me compute"},
                    {"type": "tool_use", "id": "abc", "name": "calc", "input": {}},
                ]
            ),
        ]
    }

    assert extract_final_text(state) == "let me compute"


def test_should_return_empty_string_when_state_has_no_messages() -> None:
    assert extract_final_text({"messages": []}) == ""


def test_should_return_empty_string_when_state_is_missing_messages_key() -> None:
    assert extract_final_text({}) == ""


def test_should_return_empty_string_when_state_is_none() -> None:
    assert extract_final_text(None) == ""


def test_should_return_last_ai_message_text_when_multiple_ai_messages_present() -> None:
    """Final text = last AI message — earlier turns are intermediate reasoning."""
    state = {
        "messages": [
            HumanMessage(content="q1"),
            AIMessage(content="thinking..."),
            ToolMessage(content="tool result", tool_call_id="t1"),
            AIMessage(content="final"),
        ]
    }

    assert extract_final_text(state) == "final"


def test_should_skip_non_ai_trailing_messages_when_finding_last_ai_text() -> None:
    """If the trailing messages are not AI (e.g. tool messages), walk back to the last AI."""
    state = {
        "messages": [
            HumanMessage(content="q"),
            AIMessage(content="answer"),
            ToolMessage(content="meta", tool_call_id="t1"),
        ]
    }

    assert extract_final_text(state) == "answer"


def test_should_return_empty_string_when_only_human_or_system_messages() -> None:
    state = {
        "messages": [
            SystemMessage(content="sys"),
            HumanMessage(content="user q"),
        ]
    }

    assert extract_final_text(state) == ""


def test_should_handle_state_as_typed_object_with_messages_attr() -> None:
    """Some intermediate states are dataclass-like with a .messages attr instead of dict-key."""

    class FakeState:
        def __init__(self, messages: list) -> None:
            self.messages = messages

    state = FakeState(messages=[HumanMessage(content="hi"), AIMessage(content="bye")])

    assert extract_final_text(state) == "bye"
