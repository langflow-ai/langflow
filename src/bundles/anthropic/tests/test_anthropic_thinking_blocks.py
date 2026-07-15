"""Regression tests for Anthropic 400 `thinking.thinking: Field required`.

On thinking-capable models (e.g. claude-sonnet-5) the API streams thinking
blocks with an empty `thinking` text by default (`display: omitted`).
langchain-anthropic (<= 1.4.8) drops the empty field while merging stream
chunks, so the assistant turn that carried thinking + tool_use is serialized
back to the API without the required `thinking` key and the follow-up request
fails with HTTP 400, leaving the Agent with an empty final message.
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

pytest.importorskip("langchain_anthropic")

from lfx.base.models.anthropic_chat_model import ChatAnthropicThinkingCompat, _ensure_thinking_field
from lfx_anthropic.components.anthropic.anthropic import AnthropicModelComponent


def _malformed_history() -> list:
    """Conversation whose assistant turn has a thinking block missing `thinking`.

    This is exactly what langchain-anthropic produces when merging a streamed
    thinking block that only received `signature_delta` events.
    """
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


def _build_model():
    component = AnthropicModelComponent(
        model_name="claude-sonnet-5",
        api_key="sk-ant-test",
        max_tokens=1024,
        temperature=0.1,
        base_url="https://api.anthropic.com",
        stream=False,
    )
    return component.build_model()


def test_payload_thinking_blocks_always_carry_thinking_field():
    model = _build_model()
    payload = model._get_request_payload(_malformed_history())

    blocks = _thinking_blocks(payload)
    assert blocks, "expected the assistant thinking block to be serialized"
    for block in blocks:
        assert "thinking" in block, f"thinking block missing `thinking` field: {block}"
        assert block["thinking"] is not None


def test_payload_preserves_existing_thinking_text():
    model = _build_model()
    history = _malformed_history()
    history[1].content[0] = {
        "type": "thinking",
        "thinking": "let me reason",
        "signature": "sig==",
        "index": 0,
    }
    payload = model._get_request_payload(history)

    blocks = _thinking_blocks(payload)
    assert blocks
    assert blocks[0]["thinking"] == "let me reason"


def test_agent_registry_resolves_compat_class():
    """The Agent builds its LLM via the unified-models registry, not the component."""
    from lfx.base.models.unified_models.class_registry import get_model_class

    assert get_model_class("ChatAnthropic") is ChatAnthropicThinkingCompat


def test_registry_class_payload_backfills_thinking():
    model = ChatAnthropicThinkingCompat(model="claude-sonnet-5", api_key="sk-ant-test", max_tokens=1024)
    payload = model._get_request_payload(_malformed_history())

    blocks = _thinking_blocks(payload)
    assert blocks
    assert all("thinking" in block for block in blocks)


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
