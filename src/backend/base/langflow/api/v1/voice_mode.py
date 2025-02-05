import asyncio
import base64
import json
import os
import traceback
from uuid import UUID, uuid4

import webrtcvad
import websockets
from cryptography.fernet import InvalidToken
from fastapi import APIRouter, BackgroundTasks
from loguru import logger
from sqlalchemy import select
from starlette.websockets import WebSocket, WebSocketDisconnect

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.chat import build_flow
from langflow.api.v1.schemas import InputValueRequest
from langflow.services.auth.utils import get_current_user_by_jwt
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_variable_service, session_scope
from langflow.utils.voice_utils import resample_24k_to_16k, BYTES_PER_24K_FRAME, VAD_SAMPLE_RATE_16K

router = APIRouter(prefix="/voice", tags=["Voice"])

SILENCE_THRESHOLD = 0.5
PREFIX_PADDING_MS = 300
SILENCE_DURATION_MS = 500
SESSION_INSTRUCTIONS = (
    "Converse with the user to assist with their question. "
    "When appropriate, call the execute_flow function to assist with the user's question "
    "as the input parameter and use that to craft your responses. "
    "Always tell the user before you call a function to assist with their question. "
    "And let them know what it does."
)

async def get_flow_desc_from_db(flow_id: str) -> Flow:
    """Get flow from database."""
    async with session_scope() as session:
        stmt = select(Flow).where(Flow.id == UUID(flow_id))
        result = await session.exec(stmt)
        flow = result.scalar_one_or_none()
        if not flow:
            error_message = f"Flow with id {flow_id} not found"
            raise ValueError(error_message)
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
    """Execute the flow, gather the streaming response,
    and send the result back to OpenAI as a function_call_output.
    """
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

        # Collect results from the stream
        result = ""
        events = []
        async for line in response.body_iterator:
            if not line:
                continue
            event_data = json.loads(line)
            events.append(event_data)

            # Forward build progress to client (optional)
            await websocket.send_json({"type": "flow.build.progress", "data": event_data})

            # Accumulate text from "end_vertex" events
            if event_data.get("event") == "end_vertex":
                text_part = (
                    event_data.get("data", {})
                    .get("build_data", "")
                    .get("data", {})
                    .get("results", {})
                    .get("message", {})
                    .get("text", "")
                )
                result += text_part

        # Send function result to OpenAI
        function_output = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": function_call.get("call_id"),
                "output": str(result),
            },
        }
        await openai_ws.send(json.dumps(function_output))
        await openai_ws.send(json.dumps({"type": "response.create"}))

    except Exception as e:  # noqa: BLE001
        logger.error(f"Error executing flow: {e!s}")
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
    """Main WebSocket endpoint.
    - Connects to OpenAI Realtime.
    - Uses local WebRTC VAD for barge‑in detection.
    """
    current_user = await get_current_user_by_jwt(websocket.cookies.get("access_token_lf"), session)
    await websocket.accept()

    # Check for OpenAI API key.
    variable_service = get_variable_service()
    try:
        openai_key = await variable_service.get_variable(
            user_id=current_user.id, name="OPENAI_API_KEY", field="voice_mode", session=session
        )
    except (InvalidToken, ValueError):
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            await websocket.send_json(
                {
                    "type": "error",
                    "code": "api_key_missing",
                    "message": "OpenAI API key not found. Please set your API key in the variables section.",
                }
            )
            await websocket.close()
            return
    except Exception as e:
        logger.error("exception")
        print(e)
        trace = traceback.format_exc()
        print(trace)

    # Build flow tool schema.
    try:
        flow_description = await get_flow_desc_from_db(flow_id)
        flow_tool = {
            "name": "execute_flow",
            "type": "function",
            "description": flow_description or "Execute the flow with the given input",
            "parameters": {
                "type": "object",
                "properties": {"input": {"type": "string", "description": "The input to send to the flow"}},
                "required": ["input"],
            },
        }
    except Exception as e:  # noqa: BLE001
        await websocket.send_json({"error": f"Failed to load flow: {e!s}"})
        logger.error(e)
        return

    # Connect to OpenAI Realtime.
    url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
    headers = {
        "Authorization": f"Bearer {openai_key}",
        "OpenAI-Beta": "realtime=v1",
    }

    async with websockets.connect(url, extra_headers=headers) as openai_ws:
        # Send session update.
        session_update = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": SESSION_INSTRUCTIONS,
                "voice": "echo",
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

        # Create local state for VAD processing.
        vad_queue = asyncio.Queue()
        vad_audio_buffer = bytearray()
        bot_speaking_flag = [False]  # using a one-element list for mutable flag

        # Set up WebRTC VAD instance.
        vad = webrtcvad.Vad(mode=3)

        async def write_debug_audio(raw_chunk_24k: bytes) -> None:
            """
            Offload debug file I/O to a background thread so that it doesn't block the event loop.
            """
            await asyncio.to_thread(lambda: open("debug_incoming_24k.raw", "ab").write(raw_chunk_24k))

        async def process_vad_audio() -> None:
            """
            Continuously process audio chunks from the vad_queue.
            Accumulate audio into vad_audio_buffer, extract 20ms frames,
            and run VAD on each frame. If speech is detected while the bot is speaking,
            send a cancellation message to OpenAI.
            """
            nonlocal vad_audio_buffer
            while True:
                # Wait for the next raw audio chunk from the queue.
                chunk = await vad_queue.get()
                vad_audio_buffer.extend(chunk)

                # Process complete 20ms frames.
                while len(vad_audio_buffer) >= BYTES_PER_24K_FRAME:
                    frame_24k = vad_audio_buffer[:BYTES_PER_24K_FRAME]
                    del vad_audio_buffer[:BYTES_PER_24K_FRAME]

                    try:
                        frame_16k = resample_24k_to_16k(frame_24k)
                    except ValueError as e:
                        logger.error(f"[ERROR] Invalid frame during VAD resampling: {e}")
                        continue

                    try:
                        is_speech = vad.is_speech(frame_16k, VAD_SAMPLE_RATE_16K)
                    except Exception as e:
                        logger.error(f"[ERROR] VAD processing failed: {e}")
                        continue

                    if is_speech and bot_speaking_flag[0]:
                        logger.info("Barge-in detected!")
                        await openai_ws.send(json.dumps({"type": "response.cancel"}))
                        bot_speaking_flag[0] = False
                        # Optionally, clear the accumulated audio if desired.
                        vad_audio_buffer = bytearray()
                        break

        async def forward_to_openai() -> None:
            """
            Forwards messages from the client to OpenAI.
            For audio messages, immediately forwards the raw audio
            and enqueues the raw chunk for background VAD processing.
            """
            try:
                while True:
                    message_text = await websocket.receive_text()
                    msg = json.loads(message_text)

                    if msg.get("type") == "input_audio_buffer.append":
                        base64_data = msg.get("audio", "")
                        if not base64_data:
                            continue

                        # Decode the incoming base64 audio chunk (24kHz PCM16).
                        raw_chunk_24k = base64.b64decode(base64_data)

                        # Immediately forward the original audio message to OpenAI.
                        await openai_ws.send(
                            json.dumps({"type": "input_audio_buffer.append", "audio": base64_data})
                        )

                        # Offload the debug file write (if desired) without blocking.
                        #asyncio.create_task(write_debug_audio(raw_chunk_24k))

                        # Enqueue the raw audio chunk for background VAD processing.
                        await vad_queue.put(raw_chunk_24k)
                    else:
                        # For all non-audio messages, forward them directly.
                        await openai_ws.send(message_text)
            except (WebSocketDisconnect, websockets.ConnectionClosedOK, websockets.ConnectionClosedError):
                pass

        async def forward_to_client() -> None:
            """
            Forwards messages from OpenAI to the client.
            Also updates bot_speaking_flag based on the events received.
            """
            nonlocal bot_speaking_flag
            function_call = None
            function_call_args = ""
            try:
                while True:
                    data = await openai_ws.recv()
                    event = json.loads(data)
                    event_type = event.get("type")

                    if event_type == "response.output_item.added":
                        logger.debug("Bot speaking = True")
                        bot_speaking_flag[0] = True
                        item = event.get("item", {})
                        if item.get("type") == "function_call":
                            function_call = item
                            function_call_args = ""
                    elif event_type == "response.output.complete":
                        logger.debug("Bot speaking = False")
                        bot_speaking_flag[0] = False
                    elif event_type == "response.function_call_arguments.delta":
                        function_call_args += event.get("delta", "")
                    elif event_type == "response.function_call_arguments.done":
                        if function_call:
                            asyncio.create_task(
                                handle_function_call(
                                    websocket,
                                    openai_ws,
                                    function_call,
                                    function_call_args,
                                    flow_id,
                                    background_tasks,
                                    current_user,
                                    session,
                                )
                            )
                            function_call = None
                            function_call_args = ""
                    # Forward all events to the client.
                    await websocket.send_text(data)
            except (WebSocketDisconnect, websockets.ConnectionClosedOK, websockets.ConnectionClosedError):
                pass

        # Start the background VAD processing task.
        asyncio.create_task(process_vad_audio())

        # Run both the client → OpenAI and OpenAI → client tasks concurrently.
        await asyncio.gather(
            forward_to_openai(),
            forward_to_client(),
        )
