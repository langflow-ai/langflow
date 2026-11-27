"""Cap each tool result before it enters the agent run state.

A tool that returns a large log or page can push one run past the model context window. This
middleware cuts the text of each tool result to its head and tail, with a marker in the middle.
The cut happens after the tool has run, so the `on_tool_end` event, the UI and the stored message
keep the full result. Only the model input sees the capped text.
"""

from __future__ import annotations

from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

from lfx.base.memory.context_budget import TOOL_RESULT_CAP_TOKENS, cap_text, estimate_tokens
from lfx.log.logger import logger


class ToolResultCapMiddleware(AgentMiddleware):
    """Cut every tool result to `max_tokens`. Results that are not a ToolMessage pass unchanged."""

    def __init__(self, max_tokens: int = TOOL_RESULT_CAP_TOKENS) -> None:
        super().__init__()
        self.max_tokens = max_tokens

    def wrap_tool_call(self, request: Any, handler: Any) -> Any:
        return self._cap(handler(request))

    async def awrap_tool_call(self, request: Any, handler: Any) -> Any:
        return self._cap(await handler(request))

    def _cap(self, result: Any) -> Any:
        if not isinstance(result, ToolMessage):
            return result  # a Command, for example; it carries its own messages
        content = result.content
        if isinstance(content, str):
            capped: Any = cap_text(content, self.max_tokens)
            changed = capped is not content
        elif isinstance(content, list):
            capped = self._cap_blocks(content)
            changed = capped is not content
        else:
            return result
        if not changed:
            return result
        logger.debug(
            f"tool_result_capped tool={result.name} tokens_before={estimate_tokens(str(content))} "
            f"tokens_after={estimate_tokens(str(capped))}"
        )
        return result.model_copy(update={"content": capped})

    def _cap_blocks(self, blocks: list) -> list:
        """Join the text blocks and cap them as one text. Other blocks, such as images, pass unchanged."""
        texts = [b if isinstance(b, str) else b["text"] for b in blocks if _is_text_block(b)]
        joined = "\n".join(texts)
        capped = cap_text(joined, self.max_tokens)
        if capped is joined:
            return blocks
        others = [b for b in blocks if not _is_text_block(b)]
        return [*others, {"type": "text", "text": capped}]


def _is_text_block(block: Any) -> bool:
    return isinstance(block, str) or (
        isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
    )
