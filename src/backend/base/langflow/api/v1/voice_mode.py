import asyncio
import base64
import json
import os

# For sync queue and thread
import queue
import threading
import traceback
import uuid
from datetime import datetime
from uuid import UUID, uuid4

import numpy as np
import webrtcvad
import websockets
from cryptography.fernet import InvalidToken
from elevenlabs.client import ElevenLabs
from fastapi import APIRouter, BackgroundTasks, Security
from sqlalchemy import select
from starlette.websockets import WebSocket, WebSocketDisconnect

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.chat import build_flow_and_stream
from langflow.api.v1.schemas import InputValueRequest
from langflow.logging import logger
from langflow.memory import aadd_messagetables
from langflow.schema.properties import Properties
from langflow.services.auth.utils import api_key_header, api_key_query, api_key_security, get_current_user_by_jwt
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import get_variable_service, session_scope
from langflow.utils.voice_utils import (
    BYTES_PER_24K_FRAME,
    VAD_SAMPLE_RATE_16K,
    resample_24k_to_16k,
)

router = APIRouter(prefix="/voice", tags=["Voice"])

SILENCE_THRESHOLD = 0.1
PREFIX_PADDING_MS = 100
SILENCE_DURATION_MS = 100
SESSION_INSTRUCTIONS = (
    "Converse with the user to assist with their question. "
    "When appropriate, call the execute_flow function to assist with the user's question "
    "as the input parameter and use that to craft your responses. "
    "*Always* let the user know before you call a function that you will be doing so. "
    "Once the function responds make sure to update the user with the required information."
    "If the execute_flow function failed to get a response for a certain query, but the user asks again, run it again"
    "When encountering URLs, use them in tools, access, and process their content as needed, but do not read the URLs themselves aloud."
)

use_elevenlabs = False
elevenlabs_voice = "JBFqnCBsd6RMkjVDRZzb"
elevenlabs_model = "eleven_multilingual_v2"
elevenlabs_client = None
elevenlabs_key = None

barge_in_enabled = False


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


def pcm16_to_float_array(pcm_data):
    values = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32)
    normalized = values / 32768.0  # Normalize to -1.0 to 1.0
    return normalized


async def text_chunker_with_timeout(chunks, timeout=0.3):
    """Async generator that takes an async iterable (of text pieces),
    accumulates them and yields chunks without breaking sentences.
    If no new text is received within 'timeout' seconds and there is
    buffered text, it flushes that text.
    """
    splitters = (".", ",", "?", "!", ";", ":", "—", "-", "(", ")", "[", "]", "}", " ")
    buffer = ""
    ait = chunks.__aiter__()
    while True:
        try:
            text = await asyncio.wait_for(ait.__anext__(), timeout=timeout)
        except asyncio.TimeoutError:
            if buffer:
                yield buffer + " "
                buffer = ""
            continue
        except StopAsyncIteration:
            break
        if text is None:
            if buffer:
                yield buffer + " "
            break
        if buffer and buffer[-1] in splitters:
            yield buffer + " "
            buffer = text
        elif text and text[0] in splitters:
            yield buffer + text[0] + " "
            buffer = text[1:]
        else:
            buffer += text
    if buffer:
        yield buffer + " "


async def queue_generator(queue: asyncio.Queue):
    """Async generator that yields items from a queue."""
    while True:
        item = await queue.get()
        if item is None:
            break
        yield item


async def handle_function_call(
    websocket: WebSocket,
    openai_ws: websockets.WebSocketClientProtocol,
    function_call: dict,
    function_call_args: str,
    flow_id: str,
    background_tasks: BackgroundTasks,
    current_user: CurrentActiveUser,
    session: DbSession,
    conversation_id: str,
):
    try:
        args = json.loads(function_call_args) if function_call_args else {}
        input_request = InputValueRequest(
            input_value=args.get("input"), components=[], type="chat", session=conversation_id
        )
        response = await build_flow_and_stream(
            flow_id=UUID(flow_id),
            inputs=input_request,
            background_tasks=background_tasks,
            current_user=current_user,
        )

        result = ""
        async for line in response.body_iterator:
            if not line:
                continue
            event_data = json.loads(line)
            await websocket.send_json({"type": "flow.build.progress", "data": event_data})
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
    except Exception as e:
        trace = traceback.format_exc()
        logger.error(f"Error executing flow: {e!s}\ntrace: {trace}")
        function_output = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": function_call.get("call_id"),
                "output": f"Error executing flow: {e!s}",
            },
        }
        await openai_ws.send(json.dumps(function_output))


# --- Synchronous text chunker using a standard queue ---
def sync_text_chunker(sync_queue_obj: queue.Queue, timeout: float = 0.3):
    """Synchronous generator that reads text pieces from a sync queue,
    accumulates them and yields complete chunks.
    """
    splitters = (".", ",", "?", "!", ";", ":", "—", "-", "(", ")", "[", "]", "}", " ")
    buffer = ""
    while True:
        try:
            text = sync_queue_obj.get(timeout=timeout)
        except queue.Empty:
            if buffer:
                yield buffer + " "
                buffer = ""
            continue
        if text is None:
            if buffer:
                yield buffer + " "
            break
        if buffer and buffer[-1] in splitters:
            yield buffer + " "
            buffer = text
        elif text and text[0] in splitters:
            yield buffer + text[0] + " "
            buffer = text[1:]
        else:
            buffer += text
    if buffer:
        yield buffer + " "


@router.websocket("/ws/flow_as_tool/{flow_id}")
async def flow_as_tool_websocket_no_session(
        client_websocket: WebSocket,
        flow_id: str,
        background_tasks: BackgroundTasks,
        session: DbSession,
):
    session_id = str(uuid4())
    await flow_as_tool_websocket(
        client_websocket=client_websocket,
        flow_id=flow_id,
        background_tasks=background_tasks,
        session=session,
        session_id=session_id
    )

@router.websocket("/ws/flow_as_tool/{flow_id}/{session_id}")
async def flow_as_tool_websocket(
    client_websocket: WebSocket,
    flow_id: str,
    background_tasks: BackgroundTasks,
    session: DbSession,
    session_id: str,
):
    """WebSocket endpoint registering the flow as a tool for real-time interaction."""
    try:
        await client_websocket.accept()
        token = client_websocket.cookies.get("access_token_lf")
        if token:
            current_user = await get_current_user_by_jwt(token, session)
        else:
            current_user = await api_key_security(Security(api_key_query), Security(api_key_header))
            if current_user is None:
                await client_websocket.send_json(
                    {"type": "error", "code": "langflow_auth", "message": "You must pass a valid Langflow token or cookie."}
                )

        variable_service = get_variable_service()
        try:
            openai_key = await variable_service.get_variable(
                user_id=current_user.id, name="OPENAI_API_KEY", field="openai_api_key", session=session
            )
        except (InvalidToken, ValueError):
            openai_key = os.getenv("OPENAI_API_KEY")
            if not openai_key or openai_key == "dummy":
                await client_websocket.send_json(
                    {
                        "type": "error",
                        "code": "api_key_missing",
                        "key_name": "OPENAI_API_KEY",
                        "message": "OpenAI API key not found. Please set your API key as an env var or a global variable.",
                    }
                )
                return
        except Exception as e:
            logger.error("exception")
            print(e)
            print(traceback.format_exc())

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
        except Exception as e:
            await client_websocket.send_json({"error": f"Failed to load flow: {e!s}"})
            logger.error(e)
            return

        url = "wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview"
        headers = {
            "Authorization": f"Bearer {openai_key}",
            "OpenAI-Beta": "realtime=v1",
        }

        async with websockets.connect(url, extra_headers=headers) as openai_ws:
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

            # Setup for VAD processing.
            vad_queue = asyncio.Queue()
            vad_audio_buffer = bytearray()
            bot_speaking_flag = [False]
            vad = webrtcvad.Vad(mode=3)

            async def process_vad_audio() -> None:
                nonlocal vad_audio_buffer
                last_speech_time = datetime.now()
                while True:
                    base64_data = await vad_queue.get()
                    raw_chunk_24k = base64.b64decode(base64_data)
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

            shared_state = {"last_event_type": None, "event_count": 0}

            def log_event(event_type: str, direction: str) -> None:
                if event_type != shared_state["last_event_type"]:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"\n  {timestamp} --  {direction} {event_type} ", end="", flush=True)
                    shared_state["last_event_type"] = event_type
                    shared_state["event_count"] = 0
                shared_state["event_count"] += 1

            def send_event(websocket, event, loop, direction) -> None:
                asyncio.run_coroutine_threadsafe(
                    websocket.send_json(event),
                    loop,
                ).result()
                log_event(event["type"], direction)

            # --- Spawn a text delta queue and task for TTS ---
            text_delta_queue = asyncio.Queue()
            text_delta_task = None  # Will hold our background task.

            async def process_text_deltas(async_q: asyncio.Queue):
                """Transfer text deltas from the async queue to a synchronous queue,
                then run the ElevenLabs TTS call (which expects a sync generator) in a separate thread.
                """
                sync_q = queue.Queue()

                async def transfer_text_deltas():
                    while True:
                        item = await async_q.get()
                        sync_q.put(item)
                        if item is None:
                            break

                # Schedule the transfer task in the main event loop.
                asyncio.create_task(transfer_text_deltas())

                # Create the synchronous generator from the sync queue.
                sync_gen = sync_text_chunker(sync_q, timeout=0.3)
                elevenlabs_client = await get_or_create_elevenlabs_client(current_user.id, session)
                if elevenlabs_client is None:
                    return
                # Capture the current event loop to schedule send operations.
                main_loop = asyncio.get_running_loop()

                def tts_thread():
                    # Create a new event loop for this thread.
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)

                    async def run_tts():
                        try:
                            audio_stream = elevenlabs_client.generate(
                                voice=elevenlabs_voice,
                                output_format="pcm_24000",
                                text=sync_gen,  # synchronous generator expected by ElevenLabs
                                model=elevenlabs_model,
                                voice_settings=None,
                                stream=True,
                            )
                            for chunk in audio_stream:
                                base64_audio = base64.b64encode(chunk).decode("utf-8")
                                # Schedule sending the audio chunk in the main event loop.
                                event = {"type": "response.audio.delta", "delta": base64_audio}
                                send_event(client_websocket, event, main_loop, "↓")

                            event = {"type": "response.done"}
                            send_event(client_websocket, event, main_loop, "↓")
                        except Exception as e:
                            print(e)
                            print(traceback.format_exc())

                    new_loop.run_until_complete(run_tts())
                    new_loop.close()

                threading.Thread(target=tts_thread, daemon=True).start()

            async def forward_to_openai() -> None:
                global use_elevenlabs, elevenlabs_voice
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
                            await openai_ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": base64_data}))
                            if barge_in_enabled:
                                await vad_queue.put(base64_data)
                        elif msg.get("type") == "elevenlabs.config":
                            logger.info(f"elevenlabs.config {msg}")
                            use_elevenlabs = msg["enabled"]
                            elevenlabs_voice = msg["voice_id"]
                            modalities = ["audio", "text"]
                            if use_elevenlabs:
                                modalities = ["text"]
                            session_update = {
                                "type": "session.update",
                                "session": {
                                    "modalities": modalities,
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
                            # response = {
                            #    "type": "session.update",
                            #    "session":
                            # }
                            # await openai_ws.send(json.dumps(response))
                        else:
                            await openai_ws.send(message_text)
                except (WebSocketDisconnect, websockets.ConnectionClosedOK, websockets.ConnectionClosedError):
                    pass

            async def forward_to_client() -> None:
                global elevenlabs_client, elevenlabs_key
                nonlocal bot_speaking_flag, text_delta_queue, text_delta_task
                function_call = None
                function_call_args = ""
                conversation_id = str(uuid4())
                try:
                    while True:
                        data = await openai_ws.recv()
                        event = json.loads(data)
                        event_type = event.get("type")

                        # forward all openai events except response.done if using elevenlabs to the client
                        if not (event_type == "response.done" and use_elevenlabs):
                            await client_websocket.send_text(data)

                        if event_type == "response.text.delta":
                            if use_elevenlabs:
                                delta = event.get("delta", "")
                                await text_delta_queue.put(delta)
                                if text_delta_task is None:
                                    text_delta_task = asyncio.create_task(process_text_deltas(text_delta_queue))
                        elif event_type == "response.text.done":
                            if use_elevenlabs:
                                await text_delta_queue.put(None)
                                text_delta_task = None
                                print(f"\n      bot response: {event.get('text')}")

                                try:
                                    message_text = event.get("text", "")
                                    await add_message_to_db(message_text, session, flow_id, session_id, "Machine", "AI")
                                except Exception as e:
                                    logger.error(f"Error saving message to database: {e}")
                                    logger.error(traceback.format_exc())

                        elif event_type == "response.output_item.added":
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
                                        conversation_id,
                                    )
                                )
                                function_call = None
                                function_call_args = ""
                        elif event_type == "response.audio.delta":
                            # Audio deltas from OpenAI are not forwarded if ElevenLabs is used.
                            audio_delta = event.get("delta", "")
                        elif event_type == "conversation.item.input_audio_transcription.completed":
                            try:
                                message_text = event.get("transcript", "")
                                if message_text and message_text.strip():
                                    await add_message_to_db(message_text, session, flow_id, session_id, "User", "User")
                            except Exception as e:
                                logger.error(f"Error saving message to database: {e}")
                                logger.error(traceback.format_exc())
                        elif event_type == "error":
                            print(event)
                        else:
                            await client_websocket.send_text(data)
                        log_event(event_type, "↓")

                except (WebSocketDisconnect, websockets.ConnectionClosedOK, websockets.ConnectionClosedError) as e:
                    print(f"Websocket exception: {e}")

            def _blocking_tts(elevenlabs_client, text, client_websocket, loop):
                try:
                    audio_stream = elevenlabs_client.generate(
                        voice=elevenlabs_voice,
                        output_format="pcm_24000",
                        text=text,
                        model=elevenlabs_model,
                        voice_settings=None,
                        stream=True,
                    )
                    for chunk in audio_stream:
                        base64_audio = base64.b64encode(chunk).decode("utf-8")
                        # Use asyncio.run_coroutine_threadsafe to send the audio chunk back to the client.
                        future = asyncio.run_coroutine_threadsafe(
                            client_websocket.send_json({"type": "response.audio.delta", "delta": base64_audio}), loop
                        )
                        # Optionally, wait for the send to complete.
                        future.result()
                except Exception as e:
                    print(e)
                    print(traceback.format_exc())

            if barge_in_enabled:
                asyncio.create_task(process_vad_audio())

            await asyncio.gather(
                forward_to_openai(),
                forward_to_client(),
            )
    except (WebSocketDisconnect, websockets.ConnectionClosedOK, websockets.ConnectionClosedError) as e:
        # Catch disconnect exceptions from the client websocket.
        logger.info("Client websocket disconnected. Closing connections.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.error(traceback.format_exc())
    finally:
        # Ensure that the client websocket is closed.
        try:
            await client_websocket.close()
        except Exception as e:
            logger.error(f"Error closing client websocket: {e}")
        logger.info("Client websocket cleanup complete.")

@router.get("/elevenlabs/voice_ids")
async def get_elevenlabs_voice_ids(
    current_user: CurrentActiveUser,
    session: DbSession,
):
    """Get available voice IDs from ElevenLabs API."""
    try:
        # Get or create the ElevenLabs client
        elevenlabs_client = await get_or_create_elevenlabs_client(current_user.id, session)
        if elevenlabs_client is None:
            return {"error": "ElevenLabs API key not found or invalid"}

        voices_response = elevenlabs_client.voices.get_all()
        voices = voices_response.voices

        voice_list = []
        for voice in voices:
            voice_list.append(
                {
                    "voice_id": voice.voice_id,
                    "name": voice.name,
                }
            )

        return voice_list
    except Exception as e:
        logger.error(f"Error fetching ElevenLabs voices: {e}")
        return {"error": str(e)}


async def get_or_create_elevenlabs_client(user_id=None, session=None):
    """Get or create an ElevenLabs client with the API key."""
    global elevenlabs_key, elevenlabs_client

    if elevenlabs_client is None:
        if elevenlabs_key is None and user_id and session:
            variable_service = get_variable_service()
            try:
                elevenlabs_key = await variable_service.get_variable(
                    user_id=user_id,
                    name="ELEVENLABS_API_KEY",
                    field="elevenlabs_api_key",
                    session=session,
                )
            except (InvalidToken, ValueError):
                elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
                if not elevenlabs_key:
                    logger.error("ElevenLabs API key not found")
                    return None
            except Exception as e:
                logger.error(f"Exception getting ElevenLabs API key: {e}")
                print(traceback.format_exc())
                return None

        if elevenlabs_key:
            elevenlabs_client = ElevenLabs(api_key=elevenlabs_key)

    return elevenlabs_client


async def add_message_to_db(message, session, flow_id, session_id, sender, sender_name):
    message = MessageTable(
        text=message,
        sender=sender,
        sender_name=sender_name,
        session_id=session_id,
        files=[],
        flow_id=uuid.UUID(flow_id) if isinstance(flow_id, str) else flow_id,
        properties=Properties().model_dump(),
        content_blocks=[],
    )
    await aadd_messagetables([message], session)
