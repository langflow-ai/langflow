"""Restore omitted thinking fields dropped from streamed Anthropic responses.

Recent Claude models can return thinking blocks with an empty ``thinking`` field
and a signature when thinking display is ``omitted``. During streaming,
``langchain-anthropic`` can aggregate that response into a signature-only block.
Replaying it in the next tool iteration fails because the Messages API still
requires ``thinking``.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from langchain.agents.middleware import AgentMiddleware, ExtendedModelResponse, ModelResponse
from langchain_core.messages import AIMessage


class AnthropicThinkingMiddleware(AgentMiddleware):
    """Restore ``thinking: ""`` on signature-only Anthropic thinking blocks."""

    def wrap_model_call(self, request: Any, handler: Any) -> Any:
        return _normalize_response(handler(request))

    async def awrap_model_call(self, request: Any, handler: Any) -> Any:
        return _normalize_response(await handler(request))


def _normalize_response(response: Any) -> Any:
    if isinstance(response, ExtendedModelResponse):
        normalized = _normalize_response(response.model_response)
        if normalized is response.model_response:
            return response
        return replace(response, model_response=normalized)

    if isinstance(response, ModelResponse):
        normalized = _normalize_messages(response.result)
        if normalized is response.result:
            return response
        return replace(response, result=normalized)

    if isinstance(response, AIMessage):
        normalized = _normalize_message(response)
        return normalized if normalized is not None else response

    return response


def _normalize_messages(messages: list[Any]) -> list[Any]:
    normalized_messages: list[Any] = []
    changed = False
    for message in messages:
        if isinstance(message, AIMessage):
            normalized = _normalize_message(message)
            if normalized is not None:
                normalized_messages.append(normalized)
                changed = True
                continue
        normalized_messages.append(message)
    return normalized_messages if changed else messages


def _normalize_message(message: AIMessage) -> AIMessage | None:
    if not isinstance(message.content, list):
        return None

    normalized_content: list[Any] = []
    changed = False
    for block in message.content:
        if isinstance(block, dict) and block.get("type") == "thinking" and "thinking" not in block:
            normalized_content.append({**block, "thinking": ""})
            changed = True
        else:
            normalized_content.append(block)

    if not changed:
        return None
    return message.model_copy(update={"content": normalized_content})
