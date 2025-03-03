import asyncio
import base64
import json
import os
import traceback
from datetime import datetime
from uuid import UUID, uuid4

import webrtcvad
import websockets
from cryptography.fernet import InvalidToken
from fastapi import APIRouter, BackgroundTasks
from sqlalchemy import select
from starlette.websockets import WebSocket, WebSocketDisconnect

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.chat import build_flow
from langflow.api.v1.schemas import InputValueRequest
from langflow.logging import logger
from langflow.services.auth.utils import get_current_user_by_jwt
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_variable_service, session_scope
from langflow.utils.voice_utils import (
    BYTES_PER_24K_FRAME,
    VAD_SAMPLE_RATE_16K,
    resample_24k_to_16k,
    write_audio_to_file,
)

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
    client_websocket: WebSocket,
    flow_id: str,
    background_tasks: BackgroundTasks,
    session: DbSession,
):
    """Main WebSocket endpoint.
    - Connects to OpenAI Realtime.
    - Uses local WebRTC VAD for barge‑in detection.
    """
    current_user = await get_current_user_by_jwt(client_websocket.cookies.get("access_token_lf"), session)
    await client_websocket.accept()

    # Check for OpenAI API key.
    variable_service = get_variable_service()
    try:
        openai_key = await variable_service.get_variable(
            user_id=current_user.id, name="OPENAI_API_KEY", field="voice_mode", session=session
        )
    except (InvalidToken, ValueError):
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key or openai_key == "dummy":
            await client_websocket.send_json(
                {
                    "type": "error",
                    "code": "api_key_missing",
                    "message": "OpenAI API key not found. Please set your API key in the variables section.",
                }
            )
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
        await client_websocket.send_json({"error": f"Failed to load flow: {e!s}"})
        logger.error(e)
        return

    # Connect to OpenAI Realtime.
    url = "wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview"
    # url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview"
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
                "input_audio_transcription": {"model": "whisper-1"},
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

        async def process_vad_audio() -> None:
            """Continuously process audio chunks from the vad_queue.
            Runs VAD detection in parallel with audio streaming.
            If speech is detected while the bot is speaking, sends a cancellation message.
            """
            nonlocal vad_audio_buffer
            last_speech_time = datetime.now()
            last_queue_check = datetime.now()

            while True:
                base64_data = await vad_queue.get()
                raw_chunk_24k = base64.b64decode(base64_data)

                # Process audio for VAD
                vad_audio_buffer.extend(raw_chunk_24k)
                has_speech = False

                while len(vad_audio_buffer) >= BYTES_PER_24K_FRAME:
                    frame_24k = vad_audio_buffer[:BYTES_PER_24K_FRAME]
                    del vad_audio_buffer[:BYTES_PER_24K_FRAME]

                    try:
                        frame_16k = resample_24k_to_16k(frame_24k)
                        is_speech = vad.is_speech(frame_16k, VAD_SAMPLE_RATE_16K)

                        if is_speech:
                            has_speech = True
                            logger.trace("!", end="")
                            if bot_speaking_flag[0]:
                                print("\nBarge-in detected!", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                await openai_ws.send(json.dumps({"type": "response.cancel"}))
                                print("bot speaking false")
                                bot_speaking_flag[0] = False

                    except Exception as e:
                        logger.error(f"[ERROR] VAD processing failed: {e}")
                        continue

                if has_speech:
                    last_speech_time = datetime.now()
                    logger.trace(".", end="")
                else:
                    time_since_speech = (datetime.now() - last_speech_time).total_seconds()
                    if time_since_speech >= 1.0:
                        logger.trace("_", end="")

        # Shared state for event tracking
        shared_state = {"last_event_type": None, "event_count": 0}

        def log_event(event_type: str, direction: str) -> None:
            """Helper to log events consistently"""
            if event_type != shared_state["last_event_type"]:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n  {timestamp} --  {direction} {event_type} ", end="", flush=True)
                shared_state["last_event_type"] = event_type
                shared_state["event_count"] = 0

            shared_state["event_count"] += 1
            # if shared_state["event_count"] % 10 == 0:
            #    print(f"[{shared_state['event_count']}]", end="", flush=True)
            # else:
            #    print(".", end="", flush=True)

        async def forward_to_openai() -> None:
            """Forwards messages from the client to OpenAI."""
            try:
                while True:
                    message_text = await client_websocket.receive_text()
                    msg = json.loads(message_text)
                    event_type = msg.get("type")
                    log_event(event_type, "↑")

                    if msg.get("type") == "input_audio_buffer.append":
                        logger.trace(f"buffer_id {msg.get('buffer_id', '')}")
                        base64_data = msg.get("audio", "")
                        if not base64_data:
                            continue

                        # Optional: Write audio to file for debugging
                        asyncio.create_task(write_audio_to_file(base64_data))

                        # Send audio directly to OpenAI while also queueing for VAD
                        await openai_ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": base64_data}))
                        await vad_queue.put(base64_data)
                    else:
                        await openai_ws.send(message_text)
            except (WebSocketDisconnect, websockets.ConnectionClosedOK, websockets.ConnectionClosedError):
                pass

        async def forward_to_client() -> None:
            """Forwards messages from OpenAI to the client."""
            nonlocal bot_speaking_flag
            function_call = None
            function_call_args = ""
            try:
                while True:
                    data = await openai_ws.recv()
                    await client_websocket.send_text(data)
                    event = json.loads(data)
                    event_type = event.get("type")

                    # Debug print the full event for session events
                    if event_type in ["session.created", "session.updated"]:
                        print(f"\nDEBUG - Full event: {event}")

                    log_event(event_type, "↓")

                    if "transcript" in event:
                        if event_type == "response.audio_transcript.done":
                            print(f"\n      bot transcript: {event.get('transcript')}")
                        else:
                            print(f"\n      user transcript: {event.get('transcript')}")
                    if event_type == "response.output_item.added":
                        print("Bot speaking = True")
                        bot_speaking_flag[0] = True
                        item = event.get("item", {})
                        if item.get("type") == "function_call":
                            function_call = item
                            function_call_args = ""
                    elif event_type == "response.output_item.done":
                        print("Bot speaking = False")
                        bot_speaking_flag[0] = False
                    elif event_type == "response.function_call_arguments.delta":
                        function_call_args += event.get("delta", "")
                    elif event_type == "response.function_call_arguments.done":
                        if function_call:
                            asyncio.create_task(
                                handle_function_call(
                                    client_websocket,
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
                    elif event_type == "response.audio.delta":
                        audio_delta = event.get("delta", "")
                        if audio_delta:
                            asyncio.create_task(write_audio_to_file(audio_delta))
            except (WebSocketDisconnect, websockets.ConnectionClosedOK, websockets.ConnectionClosedError) as e:
                print(f"Websocket exception: {e}")

        # Start the background VAD processing task.
        asyncio.create_task(process_vad_audio())

        # Run both the client → OpenAI and OpenAI → client tasks concurrently.
        await asyncio.gather(
            forward_to_openai(),
            forward_to_client(),
        )
