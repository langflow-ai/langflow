from typing import Any

import socketio
from loguru import logger

from langflow.services.base import Service
from langflow.services.cache.base import AsyncBaseCacheService, CacheService
from langflow.services.deps import get_chat_service
from langflow.services.socket.utils import build_vertex, get_vertices


class SocketIOService(Service):
    name = "socket_service"

    def __init__(self, cache_service: CacheService | AsyncBaseCacheService):
        self.cache_service = cache_service

    def init(self, sio: socketio.AsyncServer) -> None:
        # Registering event handlers
        self.sio = sio
        if self.sio:
            self.sio.event(self.connect)
            self.sio.event(self.disconnect)
            self.sio.on("message")(self.message)
            self.sio.on("get_vertices")(self.on_get_vertices)
            self.sio.on("build_vertex")(self.on_build_vertex)
        self.sessions = {}  # type: dict[str, dict]

    async def emit_error(self, sid, error) -> None:
        await self.sio.emit("error", to=sid, data=error)

    async def connect(self, sid, environ) -> None:
        logger.info(f"Socket connected: {sid}")
        self.sessions[sid] = environ

    async def disconnect(self, sid) -> None:
        logger.info(f"Socket disconnected: {sid}")
        self.sessions.pop(sid, None)

    async def message(self, sid, data=None) -> None:
        # Logic for handling messages
        await self.emit_message(to=sid, data=data or {"foo": "bar", "baz": [1, 2, 3]})

    async def emit_message(self, to, data) -> None:
        # Abstracting sio.emit
        await self.sio.emit("message", to=to, data=data)

    async def emit_token(self, to, data) -> None:
        await self.sio.emit("token", to=to, data=data)

    async def on_get_vertices(self, sid, flow_id) -> None:
        await get_vertices(self.sio, sid, flow_id, get_chat_service())

    async def on_build_vertex(self, sid, flow_id, vertex_id) -> None:
        await build_vertex(
            sio=self.sio,
            sid=sid,
            flow_id=flow_id,
            vertex_id=vertex_id,
            get_cache=self.get_cache,
            set_cache=self.set_cache,
        )

    async def get_cache(self, sid: str) -> Any:
        """Get the cache for a client."""
        value = self.cache_service.get(sid)
        if isinstance(self.cache_service, AsyncBaseCacheService):
            return await value
        return value

    async def set_cache(self, sid: str, build_result: Any) -> bool:
        """Set the cache for a client."""
        # client_id is the flow id but that already exists in the cache
        # so we need to change it to something else

        result_dict = {
            "result": build_result,
            "type": type(build_result),
        }
        result = self.cache_service.upsert(sid, result_dict)
        if isinstance(self.cache_service, AsyncBaseCacheService):
            await result
            return await self.cache_service.contains(sid)
        return sid in self.cache_service
