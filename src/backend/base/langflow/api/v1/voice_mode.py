import asyncio
import os
import json

from fastapi import APIRouter
import websockets
from starlette.websockets import WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/voice", tags=["Voice"])

SILENCE_THRESHOLD = 0.5
PREFIX_PADDING_MS = 300
SILENCE_DURATION_MS = 400
SESSION_INSTRUCTIONS = "You are Flow, a concise and efficient **voice assistant** for Langflow, rapid responses.\n2. Immediately utilize available functions when appropriate, except for destructive actions.\n3. Immediately relay subordinate agent responses. Sometimes it may make sense to wait for the subordinate agent to respond before continuing.\n4. If you find yourself providing a long response, STOP and ask if the user still wants you to continue."


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        await websocket.send_text(json.dumps({"error": "API key not set"}))
        return

    url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "OpenAI-Beta": "realtime=v1",
    }

    async with websockets.connect(url, extra_headers=headers) as openai_ws:
        # Initialize the session
        session_update = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": SESSION_INSTRUCTIONS,
                "voice": "shimmer",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": SILENCE_THRESHOLD,
                    "prefix_padding_ms": PREFIX_PADDING_MS,
                    "silence_duration_ms": SILENCE_DURATION_MS,
                },
            },
        }
        await openai_ws.send(json.dumps(session_update))

        # Set up bidirectional communication
        async def forward_to_openai():
            try:
                while True:
                    data = await websocket.receive_text()
                    await openai_ws.send(data)
            except WebSocketDisconnect:
                pass

        async def forward_to_client():
            try:
                while True:
                    data = await openai_ws.recv()
                    await websocket.send_text(data)
            except WebSocketDisconnect:
                pass

        await asyncio.gather(forward_to_openai(), forward_to_client())
