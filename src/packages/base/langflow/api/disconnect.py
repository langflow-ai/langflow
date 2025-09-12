import asyncio
import typing

from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from starlette.responses import ContentStream
from starlette.types import Receive


class DisconnectHandlerStreamingResponse(StreamingResponse):
    def __init__(
        self,
        content: ContentStream,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
        media_type: str | None = None,
        background: BackgroundTask | None = None,
        on_disconnect: typing.Callable | None = None,
    ):
        super().__init__(content, status_code, headers, media_type, background)
        self.on_disconnect = on_disconnect

    async def listen_for_disconnect(self, receive: Receive) -> None:
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                if self.on_disconnect:
                    coro = self.on_disconnect()
                    if asyncio.iscoroutine(coro):
                        await coro
                break
