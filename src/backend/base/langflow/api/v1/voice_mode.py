import asyncio
import json
import os
from uuid import UUID, uuid4

import websockets
from fastapi import APIRouter, BackgroundTasks
from loguru import logger
from sqlalchemy import select
from starlette.websockets import WebSocket, WebSocketDisconnect

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.chat import build_flow
from langflow.api.v1.schemas import InputValueRequest
from langflow.services.auth.utils import get_current_user_by_jwt
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import async_session_scope

router = APIRouter(prefix="/voice", tags=["Voice"])

SILENCE_THRESHOLD = 0.5
PREFIX_PADDING_MS = 300
SILENCE_DURATION_MS = 500
SESSION_INSTRUCTIONS = "Always call the execute_flow function with the user's question as the input parameter and use that to craft your responses."


async def get_flow_desc_from_db(flow_id: str) -> Flow:
    """Get flow from database."""
    async with async_session_scope() as session:
        stmt = select(Flow).where(Flow.id == UUID(flow_id))
        result = await session.exec(stmt)
        flow = result.scalar_one_or_none()
        if not flow:
            raise ValueError(f"Flow {flow_id} not found")
        return flow.description


async def handle_function_call(
    websocket: WebSocket,
    openai_ws: websockets.WebSocketClientProtocol,
    function_call: dict,
    function_call_args: str,
    flow_id: str,
    background_tasks: BackgroundTasks,
    current_user: CurrentActiveUser,
    session: DbSession,
):
    try:
        conversation_id = str(uuid4())
        args = json.loads(function_call_args) if function_call_args else {}

        input_request = InputValueRequest(
            input_value=args.get("input"), components=[], type="chat", session=conversation_id
        )

        # Get streaming response from build_flow
        response = await build_flow(
            flow_id=UUID(flow_id),
            inputs=input_request,
            background_tasks=background_tasks,
            current_user=current_user,
            session=session,
        )

        # Collect all results from the stream
        result = ""
        events = []  # for debug
        async for line in response.body_iterator:
            if not line:
                continue
            event_data = json.loads(line)
            events.append(event_data)  # for debug

            # Forward build progress to client
            await websocket.send_json({"type": "flow.build.progress", "data": event_data})

            # Potentially also collect intermediate results like content_blocks
            if event_data.get("event") == "end_vertex":
                result = result + event_data.get("data", {}).get("build_data", "").get("data", {}).get(
                    "results", {}
                ).get("message", {}).get("text", "")

        # Send function result back to OpenAI with correct format
        function_output = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": function_call.get("call_id"),
                "output": str(result),  # Ensure result is a string
            },
        }
        await openai_ws.send(json.dumps(function_output))
        await openai_ws.send(json.dumps({"type": "response.create"}))

    except Exception as e:
        logger.error(f"Error executing flow: {e!s}")
        # Send error back to OpenAI with correct format
        function_output = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": function_call.get("call_id"),
                "output": f"Error executing flow: {e!s}",
            },
        }
        await openai_ws.send(json.dumps(function_output))


@router.websocket("/ws/{flow_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    flow_id: str,
    background_tasks: BackgroundTasks,
    session: DbSession,
):
    # Generate a unique session ID for this conversation
    conversation_id = str(uuid4())  # renamed to avoid confusion with session param
    current_user = await get_current_user_by_jwt(websocket.cookies.get("access_token_lf"), session)
    await websocket.accept()

    # Get flow and build tool schema
    try:
        flow_description = await get_flow_desc_from_db(flow_id)
        flow_tool = {
            # "type": "function",
            # "function":{
            "name": "execute_flow",
            "type": "function",
            "description": flow_description or "Execute the flow with the given input",
            "parameters": {
                "type": "object",
                "properties": {"input": {"type": "string", "description": "The input to send to the flow"}},
                "required": ["input"],
            },
        }
        # }
    except Exception as e:
        await websocket.send_json({"error": f"Failed to load flow: {e!s}"})
        logger.error(e)
        return

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        await websocket.send_json({"error": "API key not set"})
        return

    url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "OpenAI-Beta": "realtime=v1",
    }

    async with websockets.connect(url, extra_headers=headers) as openai_ws:
        # Initialize the session with flow tool
        session_update = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": SESSION_INSTRUCTIONS,
                "voice": "alloy",
                "temperature": 0.8,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": SILENCE_THRESHOLD,
                    "prefix_padding_ms": PREFIX_PADDING_MS,
                    "silence_duration_ms": SILENCE_DURATION_MS,
                },
                "tools": [flow_tool],
                "tool_choice": "auto",
            },
        }
        await openai_ws.send(json.dumps(session_update))

        async def forward_to_client():
            function_call = None
            function_call_args = ""

            try:
                while True:
                    data = await openai_ws.recv()
                    event = json.loads(data)
                    event_type = event.get("type")

                    if event_type == "response.output_item.added":
                        item = event.get("item", {})
                        if item.get("type") == "function_call":
                            function_call = item
                            function_call_args = ""
                    elif event_type == "response.function_call_arguments.delta":
                        function_call_args += event.get("delta", "")
                    elif event_type == "response.function_call_arguments.done":
                        if function_call:
                            await handle_function_call(
                                websocket,
                                openai_ws,
                                function_call,
                                function_call_args,
                                flow_id,
                                background_tasks,
                                current_user,
                                session,
                            )
                            function_call = None
                            function_call_args = ""
                            continue

                    # Forward OpenAI messages to client
                    await websocket.send_text(data)
            except WebSocketDisconnect:
                pass

        async def forward_to_openai():
            try:
                while True:
                    data = await websocket.receive_text()
                    await openai_ws.send(data)
            except WebSocketDisconnect:
                pass

        await asyncio.gather(forward_to_openai(), forward_to_client())
