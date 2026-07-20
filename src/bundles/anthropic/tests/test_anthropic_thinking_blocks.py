"""Regression tests for Anthropic thinking-block compatibility in the bundle."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from lfx_anthropic.anthropic_chat_model import ChatAnthropicThinkingCompat, _ensure_thinking_field
from lfx_anthropic.components.anthropic.anthropic import AnthropicModelComponent


def _malformed_history() -> list:
    """Return a tool-use history whose thinking block is missing `thinking`."""
    ai_message = AIMessage(
        content=[
            {"type": "thinking", "signature": "sig==", "index": 0},
            {
                "type": "tool_use",
                "id": "toolu_01",
                "name": "echo",
                "input": {"text": "hello"},
                "index": 1,
            },
        ],
        tool_calls=[{"name": "echo", "args": {"text": "hello"}, "id": "toolu_01", "type": "tool_call"}],
    )
    return [
        HumanMessage(content="Use the 'echo' tool to echo: hello"),
        ai_message,
        ToolMessage(content="hello", tool_call_id="toolu_01"),
    ]


def _thinking_blocks(payload: dict) -> list[dict]:
    blocks = []
    for message in payload.get("messages", []):
        content = message.get("content")
        if isinstance(content, list):
            blocks.extend(block for block in content if isinstance(block, dict) and block.get("type") == "thinking")
    return blocks


def _build_model() -> ChatAnthropicThinkingCompat:
    component = AnthropicModelComponent(
        model_name="claude-sonnet-5",
        api_key="test-key",  # pragma: allowlist secret
        max_tokens=1024,
        temperature=0.1,
        base_url="https://api.anthropic.com",
        stream=False,
    )
    return component.build_model()


def test_component_builds_bundle_local_compat_class():
    model = _build_model()

    assert type(model) is ChatAnthropicThinkingCompat
    blocks = _thinking_blocks(model._get_request_payload(_malformed_history()))
    assert blocks
    assert all(block.get("thinking") == "" for block in blocks)


def test_payload_preserves_existing_thinking_text():
    model = _build_model()
    history = _malformed_history()
    history[1].content[0] = {
        "type": "thinking",
        "thinking": "let me reason",
        "signature": "sig==",
        "index": 0,
    }

    blocks = _thinking_blocks(model._get_request_payload(history))

    assert blocks
    assert blocks[0]["thinking"] == "let me reason"


def test_compat_class_rebuilds_deferred_parent_annotations():
    assert ChatAnthropicThinkingCompat.model_rebuild(force=True) is True
    assert ChatAnthropicThinkingCompat.__pydantic_complete__


def test_ensure_thinking_field_handles_missing_and_none():
    payload = {
        "messages": [
            {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "signature": "a=="},
                    {"type": "thinking", "thinking": None, "signature": "b=="},
                    {"type": "thinking", "thinking": "kept", "signature": "c=="},
                    {"type": "text", "text": "hi"},
                ],
            },
            {"role": "user", "content": "plain string content"},
        ]
    }

    _ensure_thinking_field(payload)

    blocks = payload["messages"][0]["content"]
    assert blocks[0]["thinking"] == ""
    assert blocks[1]["thinking"] == ""
    assert blocks[2]["thinking"] == "kept"
    assert payload["messages"][1]["content"] == "plain string content"
