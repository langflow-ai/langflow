from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.callbacks.base import AsyncCallbackHandler
from loguru import logger
from typing_extensions import override

from langflow.api.v1.schemas import ChatResponse, PromptResponse
from langflow.services.deps import get_chat_service, get_socket_service
from langflow.utils.util import remove_ansi_escape_codes

if TYPE_CHECKING:
    from langflow.services.socket.service import SocketIOService


# https://github.com/hwchase17/chat-langchain/blob/master/callback.py
class AsyncStreamingLLMCallbackHandleSIO(AsyncCallbackHandler):
    """Callback handler for streaming LLM responses."""

    @property
    def ignore_chain(self) -> bool:
        """Whether to ignore chain callbacks."""
        return False

    def __init__(self, session_id: str):
        self.chat_service = get_chat_service()
        self.client_id = session_id
        self.socketio_service: SocketIOService = get_socket_service()
        self.sid = session_id
        # self.socketio_service = self.chat_service.active_connections[self.client_id]

    @override
    async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:  # type: ignore[misc]
        resp = ChatResponse(message=token, type="stream", intermediate_steps="")
        await self.socketio_service.emit_token(to=self.sid, data=resp.model_dump())

    @override
    async def on_tool_start(self, serialized: dict[str, Any], input_str: str, **kwargs: Any) -> Any:  # type: ignore[misc]
        """Run when tool starts running."""
        resp = ChatResponse(
            message="",
            type="stream",
            intermediate_steps=f"Tool input: {input_str}",
        )
        await self.socketio_service.emit_token(to=self.sid, data=resp.model_dump())

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
        resps = [resp, *rest_of_resps]
        # Try to send the response, handle potential errors.

        try:
            # This is to emulate the stream of tokens
            for resp in resps:
                await self.socketio_service.emit_token(to=self.sid, data=resp.model_dump())
        except Exception:  # noqa: BLE001
            logger.exception("Error sending response")

    async def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Run when tool errors."""

    @override
    async def on_text(  # type: ignore[misc]
        self, text: str, **kwargs: Any
    ) -> Any:
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
            await self.socketio_service.emit_message(to=self.sid, data=resp.model_dump())

    @override
    async def on_agent_action(  # type: ignore[misc]
        self, action: AgentAction, **kwargs: Any
    ) -> None:
        log = f"Thought: {action.log}"
        # if there are line breaks, split them and send them
        # as separate messages
        if "\n" in log:
            logs = log.split("\n")
            for log in logs:
                resp = ChatResponse(message="", type="stream", intermediate_steps=log)
                await self.socketio_service.emit_token(to=self.sid, data=resp.model_dump())
        else:
            resp = ChatResponse(message="", type="stream", intermediate_steps=log)
            await self.socketio_service.emit_token(to=self.sid, data=resp.model_dump())

    @override
    async def on_agent_finish(  # type: ignore[misc]
        self, finish: AgentFinish, **kwargs: Any
    ) -> Any:
        """Run on agent end."""
        resp = ChatResponse(
            message="",
            type="stream",
            intermediate_steps=finish.log,
        )
        await self.socketio_service.emit_token(to=self.sid, data=resp.model_dump())
