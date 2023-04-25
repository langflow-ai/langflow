from typing import Any
from langchain.callbacks.base import AsyncCallbackHandler

from langflow.api.schemas import ChatResponse


# https://github.com/hwchase17/chat-langchain/blob/master/callback.py
class StreamingLLMCallbackHandler(AsyncCallbackHandler):
    """Callback handler for streaming LLM responses."""

    def __init__(self, websocket):
        self.websocket = websocket

    async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        resp = ChatResponse(message=token, type="stream", intermediate_steps="")
        await self.websocket.send_json(resp.dict())
