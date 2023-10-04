import asyncio
from uuid import UUID

from langchain.callbacks.base import AsyncCallbackHandler, BaseCallbackHandler

from langflow.api.v1.schemas import ChatResponse, PromptResponse


from typing import Any, Dict, List, Optional
from langflow.services.getters import get_chat_service


from langflow.utils.util import remove_ansi_escape_codes
from langchain.schema import AgentAction, AgentFinish
from loguru import logger


# https://github.com/hwchase17/chat-langchain/blob/master/callback.py
class AsyncStreamingLLMCallbackHandler(AsyncCallbackHandler):
    """Callback handler for streaming LLM responses."""

    def __init__(self, client_id: str):
        self.chat_service = get_chat_service()
        self.client_id = client_id
        self.websocket = self.chat_service.active_connections[self.client_id]

    async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        resp = ChatResponse(message=token, type="stream", intermediate_steps="")
        await self.websocket.send_json(resp.dict())

    async def on_tool_start(
        self, serialized: Dict[str, Any], input_str: str, **kwargs: Any
    ) -> Any:
        """Run when tool starts running."""
        resp = ChatResponse(
            message="",
            type="stream",
            intermediate_steps=f"Tool input: {input_str}",
        )
        await self.websocket.send_json(resp.dict())

    async def on_tool_end(self, output: str, **kwargs: Any) -> Any:
        """Run when tool ends running."""
        observation_prefix = kwargs.get("observation_prefix", "Tool output: ")
        split_output = output.split()
        first_word = split_output[0]
        rest_of_output = split_output[1:]
        # Create a formatted message.
        intermediate_steps = f"{observation_prefix}{first_word}"

        # Create a ChatResponse instance.
        resp = ChatResponse(
            message="",
            type="stream",
            intermediate_steps=intermediate_steps,
        )
        rest_of_resps = [
            ChatResponse(
                message="",
                type="stream",
                intermediate_steps=f"{word}",
            )
            for word in rest_of_output
        ]
        resps = [resp] + rest_of_resps
        # Try to send the response, handle potential errors.

        try:
            # This is to emulate the stream of tokens
            for resp in resps:
                await self.websocket.send_json(resp.dict())
        except Exception as exc:
            logger.error(f"Error sending response: {exc}")

    async def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Run when tool errors."""

    async def on_text(self, text: str, **kwargs: Any) -> Any:
        """Run on arbitrary text."""
        # This runs when first sending the prompt
        # to the LLM, adding it will send the final prompt
        # to the frontend
        if "Prompt after formatting" in text:
            text = text.replace("Prompt after formatting:\n", "")
            text = remove_ansi_escape_codes(text)
            resp = PromptResponse(
                prompt=text,
            )
            await self.websocket.send_json(resp.dict())
            self.chat_service.chat_history.add_message(self.client_id, resp)

    async def on_agent_action(self, action: AgentAction, **kwargs: Any):
        log = f"Thought: {action.log}"
        # if there are line breaks, split them and send them
        # as separate messages
        if "\n" in log:
            logs = log.split("\n")
            for log in logs:
                resp = ChatResponse(message="", type="stream", intermediate_steps=log)
                await self.websocket.send_json(resp.dict())
        else:
            resp = ChatResponse(message="", type="stream", intermediate_steps=log)
            await self.websocket.send_json(resp.dict())

    async def on_agent_finish(self, finish: AgentFinish, **kwargs: Any) -> Any:
        """Run on agent end."""
        resp = ChatResponse(
            message="",
            type="stream",
            intermediate_steps=finish.log,
        )
        await self.websocket.send_json(resp.dict())


class StreamingLLMCallbackHandler(BaseCallbackHandler):
    """Callback handler for streaming LLM responses."""

    def __init__(self, client_id: str):
        self.chat_service = get_chat_service()
        self.client_id = client_id
        self.websocket = self.chat_service.active_connections[self.client_id]

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        resp = ChatResponse(message=token, type="stream", intermediate_steps="")

        loop = asyncio.get_event_loop()
        coroutine = self.websocket.send_json(resp.dict())
        asyncio.run_coroutine_threadsafe(coroutine, loop)
