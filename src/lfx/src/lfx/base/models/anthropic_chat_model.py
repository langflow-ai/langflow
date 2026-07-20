"""ChatAnthropic subclass that keeps thinking blocks round-trippable.

langchain-anthropic (<= 1.4.8) drops the empty `thinking` text while merging
streamed chunks when the model omits thinking display (the default on
claude-sonnet-5 and newer), so assistant turns that carried a thinking block
are serialized back to the API without the required field and the follow-up
request fails with HTTP 400 `thinking.thinking: Field required`, aborting the
Agent turn with an empty final message.
"""

from collections.abc import Mapping
from typing import Any

from langchain_anthropic import ChatAnthropic
from pydantic import SecretStr


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


# Pydantic resolves inherited forward annotations in the subclass module. Make
# ChatAnthropic's annotation types available before the first construction.
_MODEL_REBUILD_TYPES_NAMESPACE = {"Mapping": Mapping, "SecretStr": SecretStr}
ChatAnthropicThinkingCompat.model_rebuild(_types_namespace=_MODEL_REBUILD_TYPES_NAMESPACE)
