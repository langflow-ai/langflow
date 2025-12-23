import json
from uuid import uuid4

import pytest
from langflow.api.v1.flow_assistant import (
    AssistantMessage,
    _build_openai_messages,
    _ensure_tool_call_ids,
    _filter_complete_tool_calls,
)
from pydantic import ValidationError


def test_ensure_tool_call_ids_fills_missing_ids():
    tool_calls = [
        {"type": "function", "function": {"name": "t1", "arguments": "{}"}},
        {"id": "", "type": "function", "function": {"name": "t2", "arguments": "{}"}},
    ]

    _ensure_tool_call_ids(tool_calls)

    assert tool_calls[0]["id"]
    assert tool_calls[1]["id"]
    assert tool_calls[0]["id"] != tool_calls[1]["id"]


def test_ensure_tool_call_ids_does_not_override_existing_ids():
    tool_calls = [{"id": "call_123", "type": "function", "function": {"name": "t", "arguments": "{}"}}]

    _ensure_tool_call_ids(tool_calls)

    assert tool_calls[0]["id"] == "call_123"


def test_filter_complete_tool_calls_requires_function_name():
    tool_calls = [
        {"id": "call_ok", "type": "function", "function": {"name": "lf_workflow_get", "arguments": "{}"}},
        {"id": "call_empty_name", "type": "function", "function": {"name": "", "arguments": "{}"}},
        {"id": "call_no_function", "type": "function"},
    ]

    filtered = _filter_complete_tool_calls(tool_calls)

    assert filtered == [
        {"id": "call_ok", "type": "function", "function": {"name": "lf_workflow_get", "arguments": "{}"}}
    ]


def test_build_openai_messages_preserves_tool_calls_and_tool_call_id():
    flow_id = uuid4()
    history = [
        AssistantMessage(
            role="assistant",
            content=None,
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "t1", "arguments": {"x": 1}},
                }
            ],
        ),
        AssistantMessage(role="tool", content="ok", tool_call_id="call_1"),
    ]

    messages = _build_openai_messages(flow_id=flow_id, message="hello", history=history)

    assert messages[1]["role"] == "assistant"
    assert messages[1]["tool_calls"][0]["id"] == "call_1"
    assert messages[1]["tool_calls"][0]["function"]["name"] == "t1"
    assert json.loads(messages[1]["tool_calls"][0]["function"]["arguments"]) == {"x": 1}
    assert messages[2] == {"role": "tool", "content": "ok", "tool_call_id": "call_1"}


def test_assistant_message_requires_tool_call_id_for_tool_role():
    with pytest.raises(ValidationError):
        AssistantMessage(role="tool", content="ok")


def test_assistant_message_requires_ids_for_tool_calls_in_history():
    with pytest.raises(ValidationError):
        AssistantMessage(
            role="assistant",
            content="",
            tool_calls=[{"type": "function", "function": {"name": "t1", "arguments": "{}"}}],
        )
