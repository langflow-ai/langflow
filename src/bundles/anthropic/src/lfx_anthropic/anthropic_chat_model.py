"""Bundle-local ChatAnthropic compatibility wrapper.

Keep this implementation inside ``lfx-anthropic`` so the standalone bundle
continues to work with every LFX version admitted by its minor-line dependency
floor. The LFX unified-model registry carries an equivalent wrapper for Agent
model construction.
"""

from typing import Any

from langchain_anthropic import ChatAnthropic


def _ensure_thinking_field(payload: dict) -> None:
    """Backfill `thinking` on thinking blocks serialized without it."""
    for message in payload.get("messages", []):
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "thinking" and block.get("thinking") is None:
                block["thinking"] = ""


def _install_thinking_compat() -> type[ChatAnthropic]:
    """Patch ChatAnthropic's request hook once without rebuilding its Pydantic model."""
    original_get_request_payload = getattr(ChatAnthropic, "_get_request_payload")  # noqa: B009
    if getattr(original_get_request_payload, "__lfx_thinking_compat__", False):
        return ChatAnthropic

    def get_request_payload_with_thinking_compat(self: ChatAnthropic, *args: Any, **kwargs: Any) -> dict:
        payload = original_get_request_payload(self, *args, **kwargs)
        _ensure_thinking_field(payload)
        return payload

    setattr(get_request_payload_with_thinking_compat, "__lfx_thinking_compat__", True)  # noqa: B010
    setattr(ChatAnthropic, "_get_request_payload", get_request_payload_with_thinking_compat)  # noqa: B010
    return ChatAnthropic


# Do not subclass ChatAnthropic here. Pydantic 2.14 can leave its inherited
# fields deferred during server startup; rebuilding a subclass then resolves
# those fields without their defaults. Patch the request hook once and keep the
# already-supported ChatAnthropic model and validator intact.
ChatAnthropicThinkingCompat = _install_thinking_compat()
