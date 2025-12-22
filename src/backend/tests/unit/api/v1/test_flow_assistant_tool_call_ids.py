from langflow.api.v1.flow_assistant import _ensure_tool_call_ids, _filter_complete_tool_calls


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
