import json
from fastapi import (
    APIRouter,
    HTTPException,
    WebSocket,
    WebSocketException,
    status,
)
from fastapi.responses import StreamingResponse
from langflow.api.v1.schemas import BuiltResponse, InitResponse

from langflow.chat.manager import ChatManager
from langflow.graph.graph.base import Graph
from langflow.utils.logger import logger
from cachetools import LRUCache

router = APIRouter(tags=["Chat"])
chat_manager = ChatManager()
flow_data_store: LRUCache = LRUCache(maxsize=10)


@router.websocket("/chat/{client_id}")
async def chat(client_id: str, websocket: WebSocket):
    """Websocket endpoint for chat."""
    try:
        if client_id in chat_manager.in_memory_cache:
            await chat_manager.handle_websocket(client_id, websocket)
        else:
            message = "Please, build the flow before sending messages"
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=message)
    except WebSocketException as exc:
        logger.error(exc)
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason=str(exc))


@router.post("/build/init", response_model=InitResponse, status_code=201)
async def init_build(graph_data: dict):
    """Initialize the build by storing graph data and returning a unique session ID."""

    try:
        flow_id = graph_data.get("id")
        if flow_id is None:
            raise ValueError("No ID provided")
        flow_data_store[flow_id] = graph_data

        return InitResponse(flowId=flow_id)
    except Exception as exc:
        logger.error(exc)
        return HTTPException(status_code=500, detail=str(exc))


@router.get("/build/{flow_id}/status", response_model=BuiltResponse)
async def build_status(flow_id: str):
    """Check the flow_id is in the flow_data_store."""
    try:
        built = flow_id in flow_data_store and not isinstance(
            flow_data_store[flow_id], dict
        )

        return BuiltResponse(
            built=built,
        )

    except Exception as exc:
        logger.error(exc)
        return HTTPException(status_code=500, detail=str(exc))


@router.get("/build/stream/{flow_id}", response_class=StreamingResponse)
async def stream_build(flow_id: str):
    """Stream the build process based on stored flow data."""

    async def event_stream(flow_id):
        final_response = json.dumps({"end_of_stream": True})
        try:
            if flow_id not in flow_data_store:
                error_message = "Invalid session ID"
                yield f"data: {json.dumps({'error': error_message})}\n\n"
                return

            graph_data = flow_data_store[flow_id].get("data")

            if not graph_data:
                error_message = "No data provided"
                yield f"data: {json.dumps({'error': error_message})}\n\n"
                return

            logger.debug("Building langchain object")
            graph = Graph.from_payload(graph_data)
            for node in graph.generator_build():
                try:
                    node.build()
                    params = node._built_object_repr()
                    valid = True
                    logger.debug(
                        f"Building node {params[:50]}{'...' if len(params) > 50 else ''}"
                    )
                except Exception as exc:
                    params = str(exc)
                    valid = False

                response = json.dumps(
                    {
                        "valid": valid,
                        "params": params,
                        "id": node.id,
                    }
                )
                yield f"data: {response}\n\n"

            chat_manager.set_cache(flow_id, graph.build())
        except Exception as exc:
            logger.error("Error while building the flow: %s", exc)
            yield f"error: {json.dumps({'error': str(exc)})}\n\n"
        finally:
            yield f"data: {final_response}\n\n"

    try:
        return StreamingResponse(event_stream(flow_id), media_type="text/event-stream")
    except Exception as exc:
        logger.error(exc)
        raise HTTPException(status_code=500, detail=str(exc))
