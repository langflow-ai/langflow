import asyncio
import base64
import json
import os
import queue
import threading
import traceback
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import numpy as np
import requests
import sqlalchemy
import webrtcvad
import websockets
from cryptography.fernet import InvalidToken
from elevenlabs import ElevenLabs
from fastapi import APIRouter, BackgroundTasks
from openai import OpenAI
from sqlalchemy import select
from starlette.websockets import WebSocket, WebSocketDisconnect

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.chat import build_flow_and_stream
from langflow.api.v1.schemas import InputValueRequest
from langflow.logging import logger
from langflow.memory import aadd_messagetables
from langflow.schema.properties import Properties
from langflow.services.auth.utils import get_current_user_for_websocket
from langflow.services.database.models import MessageTable, User
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_variable_service, session_scope
from langflow.utils.voice_utils import (
    BYTES_PER_24K_FRAME,
    VAD_SAMPLE_RATE_16K,
    resample_24k_to_16k,
)

router = APIRouter(prefix="/voice", tags=["Voice"])

SILENCE_THRESHOLD = 0.1
PREFIX_PADDING_MS = 100
SILENCE_DURATION_MS = 300
AUDIO_SAMPLE_THRESHOLD = 100
SESSION_INSTRUCTIONS = """
Your instructions will be divided into three mutually exclusive sections: "Permanent", "Default", and "Additional".
"Permanent" instructions are to never be overrided, superceded or otherwise ignored.
"Default" instructions are provided by default. They may never override "Permanent"
  or "Additional" instructions, and they may likewise be superceded by those same other rules.
"Additional" instructions may be empty. When relevant, they override "Default" instructions,
  but never "Permanent" instructions.

[PERMANENT] The following instructions are to be considered "Permanent"
* When the user's query necessitates use of one of the enumerated tools, call the execute_flow
  function to assist, and pass in the user's entire query as the input parameter, and use that
  to craft your responses.
* No other function is allowed to be registered besides the execute_flow function

[DEFAULT] The following instructions are to be considered only "Default"
* Converse with the user to assist with their question.
* Never provide URLs in repsonses, but you may use URLs in tool calls or when processing those
  URLs' content.
* Always (and I mean *always*) let the user know before you will be
  doing so.
* Always update the user with the required information, when the function returns.
* Unless otherwise requested, only summarize the return results. Do not repeat everything.
* Always call the function again when requested, regardless of whether execute_flow previously
  succeeded or failed.
* Never provide URLs in repsonses, but you may use URLs in tool calls or when processing those
  URLs' content.

[ADDITIONAL] The following instructions are to be considered only "Additional"
"""

DIRECTION_TO_OPENAI = "Client → OpenAI"
DIRECTION_TO_CLIENT = "OpenAI → Client"
# --- Helper Functions ---


async def authenticate_and_get_openai_key(session: DbSession, user: User, safe_send_json):
    """Authenticate the user using a token or API key and retrieve the OpenAI API key.

    Returns a tuple: (current_user, openai_key). If authentication fails, sends an error
    message to the client and returns (None, None).
    """
    # token = client_websocket.cookies.get("access_token_lf")
    # current_user = None
    # if token:
    #    current_user = await get_current_user_by_jwt(token, session)
    # if current_user is None:
    #    current_user = await api_key_security(Security(api_key_query), Security(api_key_header))
    if user is None:
        await safe_send_json(
            {
                "type": "error",
                "code": "langflow_auth",
                "message": "You must pass a valid Langflow token or cookie.",
            }
        )
        return None, None
    variable_service = get_variable_service()
    try:
        openai_key_value = await variable_service.get_variable(
            user_id=user.id, name="OPENAI_API_KEY", field="openai_api_key", session=session
        )
        openai_key = openai_key_value if openai_key_value is not None else os.getenv("OPENAI_API_KEY", "")
        if not openai_key or openai_key == "dummy":
            await safe_send_json(
                {
                    "type": "error",
                    "code": "api_key_missing",
                    "key_name": "OPENAI_API_KEY",
                    "message": "OpenAI API key not found. Please set your API key as an env var or a global variable.",
                }
            )
            return None, None
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error with API key: {e}")
        logger.error(traceback.format_exc())
        return None, None
    return user, openai_key


# --- Synchronous Text Chunker ---
def sync_text_chunker(sync_queue_obj: queue.Queue, timeout: float = 0.3):
    """Synchronous generator that reads text pieces from a sync queue and yields complete chunks."""
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


def common_response_create(session_id, original: dict | None = None) -> dict:
    msg = {}
    if original is not None:
        msg = original
    msg["type"] = "response.create"
    voice_config = get_voice_config(session_id)
    if voice_config.use_elevenlabs:
        response = msg.setdefault("response", {})
        response["modalities"] = ["text"]
    return msg


class VoiceConfig:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.use_elevenlabs = False
        self.elevenlabs_voice = "JBFqnCBsd6RMkjVDRZzb"
        self.elevenlabs_model = "eleven_multilingual_v2"
        self.elevenlabs_client = None
        self.elevenlabs_key = None
        self.barge_in_enabled = False
        self.progress_enabled = True

        self.default_openai_realtime_session = {
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
            "tools": [],
            "tool_choice": "auto",
        }
        self.openai_realtime_session: dict[str, Any] = {}

    def get_session_dict(self):
        return dict(self.default_openai_realtime_session)


class ElevenLabsClientManager:
    _instance = None
    _api_key = None

    @classmethod
    async def get_client(cls, user_id=None, session=None):
        """Get or create an ElevenLabs client with the API key."""
        if cls._instance is None:
            if cls._api_key is None and user_id and session:
                variable_service = get_variable_service()
                try:
                    cls._api_key = await variable_service.get_variable(
                        user_id=user_id,
                        name="ELEVENLABS_API_KEY",
                        field="elevenlabs_api_key",
                        session=session,
                    )
                except (InvalidToken, ValueError) as e:
                    logger.error(f"Error with ElevenLabs API key: {e}")
                    cls._api_key = os.getenv("ELEVENLABS_API_KEY", "")
                    if not cls._api_key:
                        logger.error("ElevenLabs API key not found")
                        return None
                except (KeyError, AttributeError, sqlalchemy.exc.SQLAlchemyError) as e:
                    logger.error(f"Exception getting ElevenLabs API key: {e}")
                    return None

            if cls._api_key:
                cls._instance = ElevenLabs(api_key=cls._api_key)

        return cls._instance


def get_voice_config(session_id: str) -> VoiceConfig:
    if session_id is None:
        msg = "session_id cannot be None"
        raise ValueError(msg)
    if session_id not in voice_config_cache:
        voice_config_cache[session_id] = VoiceConfig(session_id)
    return voice_config_cache[session_id]


class TTSConfig:
    def __init__(self, session_id: str, openai_key: str):
        self.session_id = session_id
        self.use_elevenlabs = False
        self.elevenlabs_voice = "JBFqnCBsd6RMkjVDRZzb"
        self.elevenlabs_model = "eleven_multilingual_v2"
        self.elevenlabs_client = None
        self.default_tts_session = {
            "type": "transcription_session.update",
            "session": {
                "input_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "gpt-4o-transcribe",
                    "language": "en",
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": SILENCE_THRESHOLD,
                    "prefix_padding_ms": PREFIX_PADDING_MS,
                    "silence_duration_ms": SILENCE_DURATION_MS,
                },
                "input_audio_noise_reduction": {"type": "near_field"},
                "include": [],
            },
        }
        self.tts_session: dict[str, Any] = {}
        self.oai_client = OpenAI(api_key=openai_key)
        self.openai_voice = "echo"

    def get_session_dict(self):
        return dict(self.default_tts_session)

    def get_openai_client(self):
        return self.oai_client

    def get_openai_voice(self):
        return self.openai_voice


def get_tts_config(session_id: str, openai_key: str) -> TTSConfig:
    if session_id is None:
        msg = "session_id cannot be None"
        raise ValueError(msg)
    if session_id not in tts_config_cache:
        tts_config_cache[session_id] = TTSConfig(session_id, openai_key)
    return tts_config_cache[session_id]


async def add_message_to_db(message, session, flow_id, session_id, sender, sender_name):
    """Enforce alternating sequence by checking the last sender.

    If two consecutive messages come from the same party (e.g. AI/AI), wait briefly.
    """
    queue_key = f"{flow_id}:{session_id}"

    # If the incoming sender is the same as the last recorded sender,
    # wait for a change (with a timeout as a fallback).
    if last_sender_by_session[queue_key] == sender:
        await wait_for_sender_change(queue_key, sender, timeout=5)
    last_sender_by_session[queue_key] = sender

    # Now proceed to create the message
    message_obj = MessageTable(
        text=message,
        sender=sender,
        sender_name=sender_name,
        session_id=session_id,
        files=[],
        flow_id=uuid.UUID(flow_id) if isinstance(flow_id, str) else flow_id,
        properties=Properties().model_dump(),
        content_blocks=[],
        category="message",
    )

    await message_queues[queue_key].put(message_obj)
    # Update last sender for this session

    if queue_key not in message_tasks or message_tasks[queue_key].done():
        message_tasks[queue_key] = asyncio.create_task(process_message_queue(queue_key, session))


async def wait_for_sender_change(queue_key, current_sender, timeout=5):
    """Wait until the last sender for this session is not the same as current_sender.

    or until the timeout expires.
    """
    waited = 0
    interval = 0.05
    while last_sender_by_session[queue_key] == current_sender and waited < timeout:
        await asyncio.sleep(interval)
        waited += interval


async def process_message_queue(queue_key, session):
    """Process messages from the queue one by one."""
    try:
        while True:
            message = await message_queues[queue_key].get()

            try:
                await aadd_messagetables([message], session)
                logger.debug(f"Added message to DB: {message.text[:30]}...")
            except ValueError as e:
                logger.error(f"Error saving message to database (ValueError): {e}")
                logger.error(traceback.format_exc())
            except sqlalchemy.exc.SQLAlchemyError as e:
                logger.error(f"Error saving message to database (SQLAlchemyError): {e}")
                logger.error(traceback.format_exc())
            except (KeyError, AttributeError, TypeError) as e:
                # More specific exceptions instead of blind Exception
                logger.error(f"Error saving message to database: {e}")
                logger.error(traceback.format_exc())
            finally:
                message_queues[queue_key].task_done()

            if message_queues[queue_key].empty():
                break
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Message queue processor for {queue_key} was cancelled: {e}")
        logger.error(traceback.format_exc())


async def handle_function_call(
    function_call: dict,
    function_call_args: str,
    flow_id: str,
    background_tasks: BackgroundTasks,
    current_user: CurrentActiveUser,
    conversation_id: str,
    session_id: str,
    voice_config: VoiceConfig,
    client_safe_send_json,
    openai_send,
):
    """Handle function calls from the OpenAI API."""
    try:
        # trigger response that tool was called
        if voice_config.progress_enabled:
            openai_send(
                {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "system",
                        "content": [
                            {
                                "type": "input_text",
                                "text": "Tell the user you are now looking into or solving "
                                "a request that will be explained later. Do not repeat "
                                "the prompt exactly, summarize what's being requested."
                                "Keep it very short."
                                f"\n\nThe request: {function_call_args}",
                            }
                        ],
                    },
                }
            )
            openai_send(common_response_create(session_id))
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
            client_safe_send_json({"type": "flow.build.progress", "data": event_data})
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
        openai_send(function_output)
        openai_send(common_response_create(session_id))
    except json.JSONDecodeError as e:
        trace = traceback.format_exc()
        logger.error(f"JSON decode error: {e!s}\ntrace: {trace}")
        function_output = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": function_call.get("call_id"),
                "output": f"Error parsing arguments: {e!s}",
            },
        }
        openai_send(function_output)
    except ValueError as e:
        trace = traceback.format_exc()
        logger.error(f"Value error: {e!s}\ntrace: {trace}")
        function_output = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": function_call.get("call_id"),
                "output": f"Error with input values: {e!s}",
            },
        }
        openai_send(function_output)
    except (ConnectionError, websockets.exceptions.WebSocketException) as e:
        trace = traceback.format_exc()
        logger.error(f"Connection error: {e!s}\ntrace: {trace}")
        function_output = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": function_call.get("call_id"),
                "output": f"Connection error: {e!s}",
            },
        }
        openai_send(function_output)
    except (KeyError, AttributeError, TypeError) as e:
        logger.error(f"Error executing flow: {e}")
        logger.error(traceback.format_exc())
        function_output = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": function_call.get("call_id"),
                "output": f"Error executing flow: {e}",
            },
        }
        openai_send(function_output)


voice_config_cache: dict[str, VoiceConfig] = {}
tts_config_cache: dict[str, TTSConfig] = {}


# --- Global Queues and Message Processing ---

message_queues: dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
message_tasks: dict[str, asyncio.Task] = {}
last_sender_by_session: defaultdict[str, str | None] = defaultdict(lambda: None)


async def get_flow_desc_from_db(flow_id: str) -> Flow:
    async with session_scope() as session:
        stmt = select(Flow).where(Flow.id == UUID(flow_id))
        result = await session.exec(stmt)
        flow = result.scalar_one_or_none()
        if not flow:
            msg = f"Flow with id {flow_id} not found"
            raise ValueError(msg)
        return flow.description


async def get_or_create_elevenlabs_client(user_id=None, session=None):
    """Get or create an ElevenLabs client with the API key."""
    return await ElevenLabsClientManager.get_client(user_id, session)


def pcm16_to_float_array(pcm_data):
    values = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32)
    return values / 32768.0


async def text_chunker_with_timeout(chunks, timeout=0.3):
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
    while True:
        item = await queue.get()
        if item is None:
            break
        yield item


def create_event_logger(session_id: str):
    state = {"last_event_type": None, "event_count": 0}

    def log_event(event: dict, direction: str) -> None:
        event_type = event.get("type", "None")
        event_id = event.get("event_id", "None")
        if event_type != state["last_event_type"]:
            logger.debug(f"Event (id - {event_id}) (session - {session_id}): {direction} {event_type}")
            state["last_event_type"] = event_type
            state["event_count"] = 0
            if event_type == "response.created":
                response_id = event.get("response").get("id")
                logger.debug(f"response_id: {response_id}")
            if "error" in event_type:
                logger.debug(f"Error {event}")
        current_count = 0 if state["event_count"] is None else state["event_count"]
        state["event_count"] = current_count + 1

    return log_event


# --- WebSocket Endpoints for Flow-as-Tool ---
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
        session_id=session_id,
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

        openai_send_q: asyncio.Queue[str] = asyncio.Queue()
        client_send_q: asyncio.Queue[str] = asyncio.Queue()

        async def openai_writer():
            while True:
                msg = await openai_send_q.get()
                if msg is None:
                    break
                await openai_ws.send(msg)

        async def client_writer():
            while True:
                msg = await client_send_q.get()
                if msg is None:
                    break
                await client_websocket.send_text(msg)

        log_event = create_event_logger(session_id)

        def openai_send(payload):
            log_event(payload, DIRECTION_TO_OPENAI)
            logger.trace(f"Sending text {DIRECTION_TO_OPENAI}: {payload['type']}")
            openai_send_q.put_nowait(json.dumps(payload))
            logger.trace("JSON sent.")

        def client_send(payload):
            log_event(payload, DIRECTION_TO_CLIENT)
            logger.trace(f"Sending JSON {DIRECTION_TO_CLIENT}: {payload.get('type', 'None')}")
            client_send_q.put_nowait(json.dumps(payload))
            logger.trace("JSON sent.")

        async def close():
            openai_send_q.put_nowait(None)
            client_send_q.put_nowait(None)
            await openai_writer_task
            await client_writer_task
            await client_websocket.close()
            await openai_ws.close()

        vad_task = None
        voice_config = get_voice_config(session_id)
        current_user: User = await get_current_user_for_websocket(client_websocket, session)
        current_user, openai_key = await authenticate_and_get_openai_key(session, current_user, client_send)
        if current_user is None or openai_key is None:
            return
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
            client_send({"error": f"Failed to load flow: {e!s}"})
            logger.error(f"Failed to load flow: {e}")
            return

        url = "wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview"
        headers = {
            "Authorization": f"Bearer {openai_key}",
            "OpenAI-Beta": "realtime=v1",
        }

        def init_session_dict():
            session_dict = voice_config.get_session_dict()
            session_dict["tools"] = [flow_tool]
            return session_dict

        async with websockets.connect(url, extra_headers=headers) as openai_ws:
            openai_realtime_session = init_session_dict()

            openai_writer_task = asyncio.create_task(openai_writer())
            client_writer_task = asyncio.create_task(client_writer())

            session_update = {"type": "session.update", "session": openai_realtime_session}
            openai_send(session_update)

            # Setup for VAD processing.
            vad_queue: asyncio.Queue = asyncio.Queue()
            vad_audio_buffer = bytearray()
            bot_speaking_flag = [False]
            vad = webrtcvad.Vad(mode=3)

            async def process_vad_audio() -> None:
                nonlocal vad_audio_buffer
                last_speech_time = datetime.now(tz=timezone.utc)
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
                                    openai_send({"type": "response.cancel"})
                                    bot_speaking_flag[0] = False
                        except Exception as e:  # noqa: BLE001
                            logger.error(f"[ERROR] VAD processing failed (ValueError): {e}")
                            continue
                    if has_speech:
                        last_speech_time = datetime.now(tz=timezone.utc)
                        logger.trace(".", end="")
                    else:
                        time_since_speech = (datetime.now(tz=timezone.utc) - last_speech_time).total_seconds()
                        if time_since_speech >= 1.0:
                            logger.trace("_", end="")

            def client_send_event_from_thread(event, loop) -> None:
                return loop.call_soon_threadsafe(client_send, event)

            def pass_through(from_dict, to_dict, keys):
                for key in keys:
                    if key in from_dict:
                        to_dict[key] = from_dict[key]

            def merge(from_dict, to_dict, keys):
                for key in keys:
                    if key in from_dict:
                        if not isinstance(from_dict[key], str):
                            msg = f"Only string values are supported for merge. Issue with key: {key}"
                            raise ValueError(msg)
                        new_value = from_dict[key]

                        if key not in to_dict:
                            to_dict[key] = new_value
                        else:
                            if not isinstance(to_dict[key], str):
                                msg = f"Only string values are supported for merge. Issue with key: {key}"
                                raise ValueError(msg)
                            old_value = to_dict[key]

                            to_dict[key] = f"{old_value}\n{new_value}"

            def warn_if_present(config_dict, keys):
                for key in keys:
                    if key in config_dict:
                        logger.warning(f"Removing key {key} from session.update.")

            def update_global_session(from_session):
                # Create a new session dict instead of modifying global
                new_session = init_session_dict()
                pass_through(
                    from_session,
                    new_session,
                    ["voice", "temperature", "turn_detection", "input_audio_transcription"],
                )
                merge(from_session, new_session, ["instructions"])
                warn_if_present(
                    from_session, ["modalities", "tools", "tool_choice", "input_audio_format", "output_audio_format"]
                )
                return new_session


            class Response:
                def __init__(self, response_id : str, use_elevenlabs : bool = False):
                    self.response_id = response_id
                    if use_elevenlabs:
                        self.text_delta_queue = asyncio.Queue()
                        self.text_delta_task = asyncio.create_task(process_text_deltas(self))
            responses = {}

            async def process_text_deltas(rsp : Response):
                """Transfer text deltas from the async queue to a synchronous queue.

                then run the ElevenLabs TTS call (which expects a sync generator) in a separate thread.
                """
                sync_q: queue.Queue = queue.Queue()

                async def transfer_text_deltas():
                    while True:
                        item = await rsp.text_delta_queue.get()
                        sync_q.put(item)
                        if item is None:
                            break

                # Schedule the transfer task in the main event loop.
                transfer_task = asyncio.create_task(transfer_text_deltas())

                # Create the synchronous generator from the sync queue.
                sync_gen = sync_text_chunker(sync_q, timeout=0.3)
                elevenlabs_client = await get_or_create_elevenlabs_client(current_user.id, session)
                if elevenlabs_client is None:
                    transfer_task.cancel()
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
                                voice=voice_config.elevenlabs_voice,
                                output_format="pcm_24000",
                                text=sync_gen,  # synchronous generator expected by ElevenLabs
                                model=voice_config.elevenlabs_model,
                                voice_settings=None,
                                stream=True,
                            )
                            for chunk in audio_stream:
                                base64_audio = base64.b64encode(chunk).decode("utf-8")
                                # Schedule sending the audio chunk in the main event loop.
                                event = {"type": "response.audio.delta",
                                         "delta": base64_audio,
                                         "response_id" : rsp.responseId}
                                client_send_event_from_thread(event, main_loop)

                            event = {"type": "response.done",
                                     "response": { "id": rsp.responseId } }
                            client_send_event_from_thread(event, main_loop)
                        except Exception as e:  # noqa: BLE001
                            logger.error(f"Error in TTS processing (ValueError): {e}")

                    new_loop.run_until_complete(run_tts())
                    new_loop.close()

                threading.Thread(target=tts_thread, daemon=True).start()

            async def forward_to_openai() -> None:
                nonlocal openai_realtime_session
                try:
                    num_audio_samples = 0  # Initialize as an integer instead of None
                    while True:
                        message_text = await client_websocket.receive_text()
                        msg = json.loads(message_text)
                        if msg.get("type") == "input_audio_buffer.append":
                            logger.trace(f"buffer_id {msg.get('buffer_id', '')}")
                            base64_data = msg.get("audio", "")
                            if not base64_data:
                                continue
                            # Ensure we're adding to an integer
                            num_audio_samples += len(base64_data)
                            event = {"type": "input_audio_buffer.append", "audio": base64_data}
                            openai_send(event)
                            if voice_config.barge_in_enabled:
                                await vad_queue.put(base64_data)
                        elif msg.get("type") == "response.create":
                            openai_send(common_response_create(session_id, msg))
                        elif msg.get("type") == "input_audio_buffer.commit":
                            if num_audio_samples > AUDIO_SAMPLE_THRESHOLD:
                                openai_send(msg)
                                num_audio_samples = 0
                        elif msg.get("type") == "langflow.voice_mode.config":
                            logger.info(f"langflow.voice_mode.config {msg}")
                            voice_config.progress_enabled = msg.get("progress_enabled", True)
                        elif msg.get("type") == "langflow.elevenlabs.config":
                            logger.info(f"langflow.elevenlabs.config {msg}")
                            voice_config.use_elevenlabs = msg["enabled"]
                            voice_config.elevenlabs_voice = msg.get("voice_id", voice_config.elevenlabs_voice)

                            # Update modalities based on TTS choice
                            modalities = ["text"] if voice_config.use_elevenlabs else ["audio", "text"]
                            openai_realtime_session["modalities"] = modalities
                            session_update = {"type": "session.update", "session": openai_realtime_session}
                            openai_send(session_update)
                        elif msg.get("type") == "session.update":
                            openai_realtime_session = update_global_session(msg["session"])
                            session_update = {"type": "session.update", "session": openai_realtime_session}
                            openai_send(session_update)
                        else:
                            openai_send(msg)
                except (WebSocketDisconnect, websockets.ConnectionClosedOK, websockets.ConnectionClosedError):
                    pass

            async def forward_to_client() -> None:
                nonlocal bot_speaking_flag, responses
                function_call = None
                function_call_args = ""
                conversation_id = str(uuid4())
                # Store function call tasks to prevent garbage collection
                function_call_tasks = []
                

                try:
                    while True:
                        data = await openai_ws.recv()
                        event = json.loads(data)
                        event_type = event.get("type")

                        do_forward = True
                        do_forward = do_forward and not (event_type == "response.done" and voice_config.use_elevenlabs)
                        do_forward = do_forward and event_type.find("flow.") != 0
                        
                        if do_forward:
                            client_send(event)
                        if event_type == "response.created":
                            response_id = event["response"]["id"]
                            responses[response_id] = Response(response_id, voice_config.use_elevenlabs)
                        elif event_type == "response.text.delta":
                            if voice_config.use_elevenlabs:
                                response_id = event["response_id"]
                                delta = event.get("delta", "")
                                rsp : Response = responses[response_id]
                                await rsp.text_delta_queue.put(delta)
                        elif event_type == "response.text.done":
                            if voice_config.use_elevenlabs:
                                response_id = event["response_id"]
                                rsp : Response = responses[response_id]
                                await rsp.text_delta_queue.put(None)
                                if rsp.text_delta_task and not rsp.text_delta_task.done():
                                    await rsp.text_delta_task
                                responses.pop(response_id)

                                try:
                                    message_text = event.get("text", "")
                                    await add_message_to_db(message_text, session, flow_id, session_id, "Machine", "AI")
                                except ValueError as e:
                                    logger.error(f"Error saving message to database (ValueError): {e}")
                                    logger.error(traceback.format_exc())
                                except (KeyError, AttributeError, TypeError) as e:
                                    # Replace blind Exception with specific exceptions
                                    logger.error(f"Error saving message to database: {e}")
                                    logger.error(traceback.format_exc())

                        elif event_type == "response.output_item.added":
                            bot_speaking_flag[0] = True
                            item = event.get("item", {})
                            if item.get("type") == "function_call":
                                function_call = item
                                function_call_args = ""
                        elif event_type == "response.output_item.done":
                            try:
                                transcript = extract_transcript(event)
                                if transcript and transcript.strip():
                                    await add_message_to_db(transcript, session, flow_id, session_id, "Machine", "AI")
                            except ValueError as e:
                                logger.error(f"Error saving message to database (ValueError): {e}")
                                logger.error(traceback.format_exc())
                            except (KeyError, AttributeError, TypeError) as e:
                                # Replace blind Exception with specific exceptions
                                logger.error(f"Error saving message to database: {e}")
                                logger.error(traceback.format_exc())
                            bot_speaking_flag[0] = False
                        elif event_type == "response.function_call_arguments.delta":
                            function_call_args += event.get("delta", "")
                        elif event_type == "response.function_call_arguments.done":
                            if function_call:
                                # Create and store reference to the task
                                function_call_task = asyncio.create_task(
                                    handle_function_call(
                                        function_call,
                                        function_call_args,
                                        flow_id,
                                        background_tasks,
                                        current_user,
                                        conversation_id,
                                        session_id,
                                        voice_config,
                                        client_send,
                                        openai_send,
                                    )
                                )
                                # Store the task reference to prevent garbage collection
                                function_call_tasks.append(function_call_task)
                                # Clean up completed tasks periodically
                                function_call_tasks = [t for t in function_call_tasks if not t.done()]
                                function_call = None
                                function_call_args = ""
                        elif event_type == "response.audio.delta":
                            # there are no audio deltas from OpenAI if ElevenLabs is used (because modality = ["text"]).
                            event.get("delta", "")
                        elif event_type == "conversation.item.input_audio_transcription.completed":
                            try:
                                message_text = event.get("transcript", "")
                                if message_text and message_text.strip():
                                    await add_message_to_db(message_text, session, flow_id, session_id, "User", "User")
                            except ValueError as e:
                                logger.error(f"Error saving message to database (ValueError): {e}")
                                logger.error(traceback.format_exc())
                            except (KeyError, AttributeError, TypeError) as e:
                                # Replace blind Exception with specific exceptions
                                logger.error(f"Error saving message to database: {e}")
                                logger.error(traceback.format_exc())
                        elif event_type == "error":
                            pass

                except (WebSocketDisconnect, websockets.ConnectionClosedOK, websockets.ConnectionClosedError):
                    pass

            if voice_config.barge_in_enabled:
                # Store the task reference to prevent it from being garbage collected
                vad_task = asyncio.create_task(process_vad_audio())

            try:
                # TaskGroup handles cancellation & error propagation for you
                async with asyncio.TaskGroup() as tg:
                    tg.create_task(forward_to_openai())
                    tg.create_task(forward_to_client())
                # if both finish normally, TaskGroup exits cleanly here
            except* Exception as excs:  # noqa: BLE001
                # handle any exceptions from any task
                for exc in excs.exceptions:
                    logger.error("WS loop failed:", exc_info=exc)
                logger.error(traceback.format_exc())
            finally:
                # shared cleanup for writers & sockets
                await close()
    except Exception as e:  # noqa: BLE001
        logger.error(f"Unexpected error: {e}")
        logger.error(traceback.format_exc())
    finally:
        # Make sure to clean up the task
        if vad_task and not vad_task.done():
            vad_task.cancel()


@router.websocket("/ws/flow_tts/{flow_id}")
async def flow_tts_websocket_no_session(
    client_websocket: WebSocket,
    flow_id: str,
    background_tasks: BackgroundTasks,
    session: DbSession,
):
    session_id = str(uuid4())
    await flow_tts_websocket(
        client_websocket=client_websocket,
        flow_id=flow_id,
        background_tasks=background_tasks,
        session=session,
        session_id=session_id,
    )


@router.websocket("/ws/flow_tts/{flow_id}/{session_id}")
async def flow_tts_websocket(
    client_websocket: WebSocket,
    flow_id: str,
    background_tasks: BackgroundTasks,
    session: DbSession,
    session_id: str,
):
    """WebSocket endpoint for direct flow text-to-speech interaction."""
    try:
        await client_websocket.accept()

        openai_send_q: asyncio.Queue[str] = asyncio.Queue()
        client_send_q: asyncio.Queue[str] = asyncio.Queue()

        async def openai_writer():
            while True:
                msg = await openai_send_q.get()
                if msg is None:
                    break
                await openai_ws.send(msg)

        async def client_writer():
            while True:
                msg = await client_send_q.get()
                if msg is None:
                    break
                await client_websocket.send_text(msg)

        log_event = create_event_logger(session_id)

        def openai_send(payload):
            log_event(payload, DIRECTION_TO_OPENAI)
            logger.trace(f"Sending text {DIRECTION_TO_OPENAI}: {payload['type']}")
            openai_send_q.put_nowait(json.dumps(payload))
            logger.trace("JSON sent.")

        def client_send(payload):
            log_event(payload, DIRECTION_TO_CLIENT)
            logger.trace(f"Sending JSON {DIRECTION_TO_CLIENT}: {payload['type']}")
            client_send_q.put_nowait(json.dumps(payload))
            logger.trace("JSON sent.")

        async def close():
            openai_send_q.put_nowait(None)
            client_send_q.put_nowait(None)
            await openai_writer_task
            await client_writer_task
            await client_websocket.close()
            await openai_ws.close()

        log_event = create_event_logger(session_id)
        current_user: User = await get_current_user_for_websocket(client_websocket, session)
        current_user, openai_key = await authenticate_and_get_openai_key(session, current_user, client_send)
        url = "wss://api.openai.com/v1/realtime?intent=transcription"
        headers = {
            "Authorization": f"Bearer {openai_key}",
            "OpenAI-Beta": "realtime=v1",
        }

        tts_config = get_tts_config(session_id, openai_key)
        async with websockets.connect(url, extra_headers=headers) as openai_ws:
            openai_writer_task = asyncio.create_task(openai_writer())
            client_writer_task = asyncio.create_task(client_writer())

            tts_realtime_session = tts_config.get_session_dict()

            openai_send(tts_realtime_session)

            async def forward_to_openai() -> None:
                try:
                    while True:
                        message_text = await client_websocket.receive_text()
                        event = json.loads(message_text)
                        if event.get("type") == "input_audio_buffer.append":
                            base64_data = event.get("audio", "")
                            if not base64_data:
                                continue
                            out_event = {"type": "input_audio_buffer.append", "audio": base64_data}
                            openai_send(out_event)
                        elif event.get("type") == "input_audio_buffer.commit":
                            openai_send(event)
                        elif event.get("type") == "langflow.elevenlabs.config":
                            logger.info(f"langflow.elevenlabs.config {event}")
                            tts_config.use_elevenlabs = event["enabled"]
                            tts_config.elevenlabs_voice = event.get("voice_id", tts_config.elevenlabs_voice)
                        elif event.get("type") == "voice.settings":
                            # Store the voice setting
                            if event.get("voice"):
                                tts_config.openai_voice = event.get("voice")
                                logger.info(f"Updated OpenAI voice to: {tts_config.openai_voice}")
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Error in WebSocket communication: {e}")

            async def forward_to_client() -> None:
                try:
                    while True:
                        data = await openai_ws.recv()
                        event = json.loads(data)
                        client_send(event)
                        if event.get("type") == "conversation.item.input_audio_transcription.completed":
                            transcript = event.get("transcript")
                            if transcript is not None and transcript != "":
                                input_request = InputValueRequest(
                                    input_value=transcript, components=[], type="chat", session=session_id
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
                                    client_send({"type": "flow.build.progress", "data": event_data})
                                    if event_data.get("event") == "end_vertex":
                                        text = (
                                            event_data.get("data", {})
                                            .get("build_data", "")
                                            .get("data", {})
                                            .get("results", {})
                                            .get("message", {})
                                            .get("text", "")
                                        )
                                        if text:
                                            result = text
                                if result != "":
                                    if tts_config.use_elevenlabs:
                                        elevenlabs_client = await get_or_create_elevenlabs_client(
                                            current_user.id, session
                                        )
                                        if elevenlabs_client is None:
                                            return
                                        audio_stream = elevenlabs_client.generate(
                                            voice=tts_config.elevenlabs_voice,
                                            output_format="pcm_24000",
                                            text=result,
                                            model=tts_config.elevenlabs_model,
                                            voice_settings=None,
                                            stream=True,
                                        )
                                        for chunk in audio_stream:
                                            base64_audio = base64.b64encode(chunk).decode("utf-8")
                                            audio_event = {"type": "response.audio.delta", "delta": base64_audio}
                                            client_send(audio_event)
                                    else:
                                        oai_client = tts_config.get_openai_client()
                                        voice = tts_config.get_openai_voice()
                                        response = oai_client.audio.speech.create(
                                            model="gpt-4o-mini-tts",
                                            voice=voice,
                                            input=result,  # Use result instead of undefined input variable
                                            instructions="be cheerful",
                                            response_format="pcm",
                                        )

                                        base64_audio = base64.b64encode(response.content).decode("utf-8")
                                        audio_event = {"type": "response.audio.delta", "delta": base64_audio}
                                        client_send(audio_event)
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Error in WebSocket communication: {e}")

            try:
                # TaskGroup handles cancellation & error propagation for you
                async with asyncio.TaskGroup() as tg:
                    tg.create_task(forward_to_openai())
                    tg.create_task(forward_to_client())
                # if both finish normally, TaskGroup exits cleanly here
            except* Exception as excs:  # noqa: BLE001
                # handle any exceptions from any task
                for exc in excs.exceptions:
                    logger.error("WS loop failed:", exc_info=exc)
            finally:
                # shared cleanup for writers & sockets
                await close()
    except Exception as e:  # noqa: BLE001
        logger.error(f"Unexpected error: {e}")
        logger.error(traceback.format_exc())


def extract_transcript(json_data):
    try:
        content_list = json_data.get("item", {}).get("content", [])
        for content_item in content_list:
            if content_item.get("type") == "audio":
                return content_item.get("transcript", "")
    except (KeyError, TypeError, AttributeError) as e:
        logger.debug(f"Error extracting transcript: {e}")
        return ""
    else:
        return ""


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

        # Fix for PERF401: Use list comprehension
        return [
            {
                "voice_id": voice.voice_id,
                "name": voice.name,
            }
            for voice in voices
        ]
    except ValueError as e:
        logger.error(f"Error fetching ElevenLabs voices (ValueError): {e}")
        return {"error": str(e)}
    except requests.RequestException as e:
        logger.error(f"Error fetching ElevenLabs voices (RequestException): {e}")
        return {"error": str(e)}
    except (KeyError, AttributeError, TypeError) as e:
        # More specific exceptions instead of blind Exception
        logger.error(f"Error fetching ElevenLabs voices: {e}")
        logger.error(traceback.format_exc())
        return {"error": str(e)}
