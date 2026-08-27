"""Regression tests for Anthropic thinking-block compatibility in LFX."""

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from lfx.base.models.anthropic_chat_model import (
    ChatAnthropicThinkingCompat,
    _ensure_thinking_field,
    _install_thinking_compat,
)
from lfx.base.models.unified_models.class_registry import get_model_class
from lfx.base.models.unified_models.instantiation import get_llm


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


def test_payload_thinking_blocks_always_carry_thinking_field():
    model = ChatAnthropicThinkingCompat(
        model="claude-sonnet-5",
        api_key="test-key",  # pragma: allowlist secret
        max_tokens=1024,
    )

    blocks = _thinking_blocks(model._get_request_payload(_malformed_history()))

    assert blocks
    assert all(block.get("thinking") == "" for block in blocks)


def test_payload_preserves_existing_thinking_text():
    model = ChatAnthropicThinkingCompat(
        model="claude-sonnet-5",
        api_key="test-key",  # pragma: allowlist secret
        max_tokens=1024,
    )
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


def test_agent_registry_resolves_compat_class():
    assert get_model_class("ChatAnthropic") is ChatAnthropicThinkingCompat


def test_unified_language_model_builds_anthropic_compat_class():
    model = get_llm(
        [
            {
                "name": "claude-sonnet-5",
                "provider": "Anthropic",
                "metadata": {
                    "model_class": "ChatAnthropic",
                    "model_name_param": "model",
                    "api_key_param": "api_key",  # pragma: allowlist secret
                },
            }
        ],
        user_id=None,
        api_key="test-key",  # pragma: allowlist secret
    )

    assert type(model) is ChatAnthropicThinkingCompat


def test_compat_reuses_parent_pydantic_model_and_defaults():
    assert ChatAnthropicThinkingCompat is ChatAnthropic
    required_fields = {name for name, field in ChatAnthropicThinkingCompat.model_fields.items() if field.is_required()}
    assert required_fields == {"model"}
    assert ChatAnthropicThinkingCompat.model_fields["temperature"].default is None


def test_compat_install_is_idempotent():
    request_hook = getattr(ChatAnthropic, "_get_request_payload")  # noqa: B009
    assert _install_thinking_compat() is ChatAnthropic
    assert getattr(ChatAnthropic, "_get_request_payload") is request_hook  # noqa: B009


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
