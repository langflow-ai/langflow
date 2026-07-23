"""Ensure model-generated tool calls have IDs before LangGraph routes them."""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from uuid import uuid4

from langchain.agents.middleware import AgentMiddleware, ExtendedModelResponse, ModelResponse
from langchain_core.messages import AIMessage

from lfx.log.logger import logger


class ToolCallIDMiddleware(AgentMiddleware):
    """Fill missing tool-call IDs on completed model responses."""

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

    logger.warning(
        "[ToolCallIDMiddleware] Unrecognized response shape %s — tool-call ID normalization bypassed",
        type(response).__name__,
    )
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


def _valid_id(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _normalize_message(message: AIMessage) -> AIMessage | None:
    tool_calls = message.tool_calls or []
    if not tool_calls:
        return None

    content = message.content
    tool_blocks: list[tuple[int, dict[str, Any]]] = []
    if isinstance(content, list):
        tool_blocks = [
            (index, block)
            for index, block in enumerate(content)
            if isinstance(block, dict) and block.get("type") == "tool_use"
        ]

    normalized_calls = list(tool_calls)
    content_is_list = isinstance(content, list)
    normalized_content = list(content) if content_is_list else []
    changed = False

    for index, tool_call in enumerate(tool_calls):
        content_block = tool_blocks[index][1] if index < len(tool_blocks) else None
        call_id = _valid_id(tool_call.get("id"))
        content_id = _valid_id(content_block.get("id")) if content_block is not None else None
        resolved_id = call_id or content_id or f"call_{uuid4().hex}"

        if call_id is None:
            normalized_calls[index] = {**tool_call, "id": resolved_id}
            changed = True

        if content_block is not None and content_id is None:
            content_index = tool_blocks[index][0]
            normalized_content[content_index] = {**content_block, "id": resolved_id}
            changed = True

    if not changed:
        return None
    updates: dict[str, Any] = {"tool_calls": normalized_calls}
    if content_is_list:
        updates["content"] = normalized_content
    return message.model_copy(update=updates)
