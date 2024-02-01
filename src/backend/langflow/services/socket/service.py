import time
from typing import TYPE_CHECKING, Any, Callable

import socketio
from langflow.api.utils import format_elapsed_time
from langflow.api.v1.schemas import ResultDict, VertexBuildResponse
from langflow.graph.graph.base import Graph
from langflow.graph.vertex.base import StatelessVertex
from langflow.services.base import Service
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_chat_service, get_session
from langflow.services.monitor.utils import log_vertex_build
from loguru import logger
from sqlmodel import select

if TYPE_CHECKING:
    from langflow.services.cache.service import BaseCacheService


class SocketIOService(Service):
    name = "socket_io_service"

    def __init__(self, cache_service: "BaseCacheService"):
        self.cache_service = cache_service

    def init(self, sio: socketio.AsyncServer):
        # Registering event handlers
        self.sio = sio
        self.sio.event(self.connect)
        self.sio.event(self.disconnect)
        self.sio.on("message")(self.message)
        self.sio.on("get_vertices")(self.on_get_vertices)
        self.sio.on("build_vertex")(self.on_build_vertex)
        self.sessions = {}

    async def emit_error(self, sid, error):
        await self.sio.emit("error", to=sid, data=error)

    async def connect(self, sid, environ):
        logger.info(f"Socket connected: {sid}")
        self.sessions[sid] = environ

    async def disconnect(self, sid):
        logger.info(f"Socket disconnected: {sid}")
        self.sessions.pop(sid, None)

    async def message(self, sid, data=None):
        # Logic for handling messages
        await self.emit_message(to=sid, data=data or {"foo": "bar", "baz": [1, 2, 3]})

    async def emit_message(self, to, data):
        # Abstracting sio.emit
        await self.sio.emit("message", to=to, data=data)

    async def emit_token(self, to, data):
        await self.sio.emit("token", to=to, data=data)

    async def on_get_vertices(self, sid, flow_id):
        await get_vertices(self.sio, sid, flow_id, get_chat_service())

    async def on_build_vertex(self, sid, flow_id, vertex_id, tweaks, inputs):
        await build_vertex(
            sio=self.sio,
            sid=sid,
            flow_id=flow_id,
            vertex_id=vertex_id,
            tweaks=tweaks,
            inputs=inputs,
            get_cache=self.get_cache,
            set_cache=self.set_cache,
        )

    def get_cache(self, sid: str) -> Any:
        """
        Get the cache for a client.
        """
        return self.cache_service.get(sid)

    def set_cache(self, sid: str, build_result: Any) -> bool:
        """
        Set the cache for a client.
        """
        # client_id is the flow id but that already exists in the cache
        # so we need to change it to something else

        result_dict = {
            "result": build_result,
            "type": type(build_result),
        }
        self.cache_service.upsert(sid, result_dict)
        return sid in self.cache_service


async def build_vertex(
    sio: socketio.AsyncServer,
    sid: str,
    flow_id: str,
    vertex_id: str,
    get_cache: Callable,
    set_cache: Callable,
    tweaks=None,
    inputs=None,
):
    try:
        cache = get_cache(flow_id)
        graph = cache.get("result")

        if not isinstance(graph, Graph):
            await sio.emit("error", data="Invalid graph", to=sid)
            return

        vertex = graph.get_vertex(vertex_id)
        if not vertex:
            await sio.emit("error", data="Invalid vertex", to=sid)
            return
        start_time = time.perf_counter()
        try:
            if isinstance(vertex, StatelessVertex) or not vertex._built:
                await vertex.build(user_id=None)
            params = vertex._built_object_repr()
            valid = True
            result_dict = vertex.get_built_result()
            # We need to set the artifacts to pass information
            # to the frontend
            vertex.set_artifacts()
            artifacts = vertex.artifacts
            timedelta = time.perf_counter() - start_time
            duration = format_elapsed_time(timedelta)
            result_dict = ResultDict(results=result_dict, artifacts=artifacts, duration=duration, timedelta=timedelta)
        except Exception as exc:
            params = str(exc)
            valid = False
            result_dict = ResultDict(results={})
            artifacts = {}
        set_cache(flow_id, graph)
        await log_vertex_build(
            flow_id=flow_id,
            vertex_id=vertex_id,
            valid=valid,
            params=params,
            data=result_dict,
            artifacts=artifacts,
        )

        # Emit the vertex build response
        response = VertexBuildResponse(valid=valid, params=params, id=vertex.id, data=result_dict)
        await sio.emit("vertex_build", data=response.model_dump(), to=sid)

    except Exception as exc:
        await sio.emit("error", data=str(exc), to=sid)


async def get_vertices(sio, sid, flow_id, chat_service):
    try:
        session = get_session()
        flow: Flow = session.exec(select(Flow).where(Flow.id == flow_id)).first()
        if not flow or not flow.data:
            await sio.emit("error", data="Invalid flow ID", to=sid)
            return

        graph = Graph.from_payload(flow.data)
        chat_service.set_cache(flow_id, graph)
        vertices = graph.layered_topological_sort()

        # Emit the vertices to the client
        await sio.emit("vertices_order", data=vertices, to=sid)

    except Exception as exc:
        await sio.emit("error", data=str(exc), to=sid)
