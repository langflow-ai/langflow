import time
from typing import Callable

import socketio  # type: ignore
from sqlmodel import select

from langflow.api.utils import format_elapsed_time
from langflow.api.v1.schemas import ResultDataResponse, VertexBuildResponse
from langflow.graph.graph.base import Graph
from langflow.graph.utils import log_vertex_build
from langflow.graph.vertex.base import Vertex
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_session


def set_socketio_server(socketio_server):
    from langflow.services.deps import get_socket_service

    socket_service = get_socket_service()
    socket_service.init(socketio_server)


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
            if isinstance(vertex, Vertex) or not vertex._built:
                await vertex.build(user_id=None, session_id=sid)
            params = vertex._built_object_repr()
            valid = True
            result_dict = vertex.get_built_result()
            # We need to set the artifacts to pass information
            # to the frontend
            vertex.set_artifacts()
            artifacts = vertex.artifacts
            timedelta = time.perf_counter() - start_time
            duration = format_elapsed_time(timedelta)
            result_dict = ResultDataResponse(
                results=result_dict,
                artifacts=artifacts,
                duration=duration,
                timedelta=timedelta,
            )
        except Exception as exc:
            params = str(exc)
            valid = False
            result_dict = ResultDataResponse(results={})
            artifacts = {}
        set_cache(flow_id, graph)
        log_vertex_build(
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
