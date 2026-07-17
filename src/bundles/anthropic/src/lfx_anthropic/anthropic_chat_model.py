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


class ChatAnthropicThinkingCompat(ChatAnthropic):
    """ChatAnthropic that normalizes thinking blocks in outgoing payloads."""

    def _get_request_payload(self, *args: Any, **kwargs: Any) -> dict:
        payload = super()._get_request_payload(*args, **kwargs)
        _ensure_thinking_field(payload)
        return payload
