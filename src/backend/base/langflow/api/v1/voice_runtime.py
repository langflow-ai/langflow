"""Thin Pipecat voice runtime endpoints (Phase 7).

Loads a voice graph JSON, injects per-session context (live WebSocket, session
IDs, etc.) via ``aload_flow_from_json(session_context=...)``, drives the graph
to build every vertex (so transports / services / pipelines instantiate their
underlying Pipecat objects), locates the terminal ``PipecatPipelineTask``
output, and feeds it to ``PipelineRunner``.

All service / transport instantiation lives in components — this module is the
runner shell. ~50 lines of real logic per endpoint.

NOT to be confused with ``voice_mode.py`` (OpenAI Realtime + ElevenLabs legacy
path mounted at ``/api/v1/voice``). This runtime is mounted at
``/api/v1/voice-runtime`` to keep them side-by-side without conflict.
"""

from __future__ import annotations

import contextlib
import json
import os
import traceback
from pathlib import Path
from typing import Any

from fastapi import APIRouter, WebSocketDisconnect
from lfx.load.load import aload_flow_from_json
from lfx.log.logger import logger
from starlette.websockets import WebSocket

router = APIRouter(prefix="/voice-runtime", tags=["Voice Runtime"], include_in_schema=False)


# --------------------------------------------------------------------------- #
# Agent JSON resolution                                                       #
# --------------------------------------------------------------------------- #

_AGENT_DIR_ENV = "LANGFLOW_VOICE_AGENTS_DIR"
_AGENT_DIR_DEFAULT = Path.cwd() / "agents"


def _voice_agents_dir() -> Path:
    return Path(os.environ.get(_AGENT_DIR_ENV) or _AGENT_DIR_DEFAULT)


def resolve_voice_flow_path(agent_id: str) -> Path:
    """Resolve an agent ID to an on-disk JSON file path.

    Supported forms:
      - absolute path -> used as-is
      - relative path -> resolved against the voice-agents dir
      - bare ID       -> joined with .json under the voice-agents dir
    """
    if not agent_id:
        msg = "Empty agent_id."
        raise ValueError(msg)
    candidate = Path(agent_id)
    if candidate.is_absolute():
        return candidate
    base = _voice_agents_dir()
    direct = base / candidate
    if direct.exists():
        return direct
    with_json = base / f"{agent_id}.json"
    if with_json.exists():
        return with_json
    msg = (
        f"Voice agent '{agent_id}' not found. Looked at:\n"
        f"  {direct}\n  {with_json}\n"
        f"(Set {_AGENT_DIR_ENV} to override the search directory.)"
    )
    raise FileNotFoundError(msg)


# --------------------------------------------------------------------------- #
# Graph -> PipelineTask                                                       #
# --------------------------------------------------------------------------- #


async def _build_pipeline_task(graph: Any) -> Any:
    """Drive the graph to completion and return the resolved PipelineTask value.

    Iterates ``graph.async_start()`` which performs a topological walk, building
    each vertex's component and resolving its output methods. Then looks up the
    unique vertex whose declared output type is ``PipecatPipelineTask`` and
    returns the live value sitting on that vertex's output.
    """
    from lfx.graph.graph.constants import Finish  # local import to avoid early load

    # Consume the build generator; we only care that every vertex finishes.
    async for result in graph.async_start():
        if isinstance(result, Finish):
            break

    vertex, output_name = graph.terminal_output_of_type("PipecatPipelineTask")
    outputs_map = vertex.custom_component.get_outputs_map()
    output = outputs_map.get(output_name)
    if output is None or output.value is None or output.value == "__UNDEFINED__":
        msg = (
            f"Terminal vertex '{vertex.id}' has no resolved value on output '{output_name}'. "
            "Did the graph finish building cleanly?"
        )
        raise RuntimeError(msg)
    return output.value


# --------------------------------------------------------------------------- #
# Endpoints                                                                   #
# --------------------------------------------------------------------------- #


async def _run_session(websocket: WebSocket, agent_id: str, extra_session: dict[str, Any]) -> None:
    """Common runner used by every endpoint variant."""
    from pipecat.pipeline.runner import PipelineRunner

    try:
        flow_path = resolve_voice_flow_path(agent_id)
    except FileNotFoundError as exc:
        await websocket.close(code=4404, reason=str(exc))
        return

    session_context: dict[str, Any] = {"websocket": websocket, **extra_session}
    logger.info(f"[voice] starting agent='{agent_id}' flow='{flow_path}'")

    try:
        graph = await aload_flow_from_json(
            flow=flow_path,
            session_context=session_context,
            disable_logs=False,
        )
        task = await _build_pipeline_task(graph)
    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"[voice] graph load/build failed: {exc}")
        traceback.print_exc()
        with contextlib.suppress(Exception):
            await websocket.close(code=4500, reason=f"flow load failed: {exc}")
        return

    try:
        await PipelineRunner(handle_sigint=False).run(task)
    except WebSocketDisconnect:
        logger.info(f"[voice] websocket disconnected for agent='{agent_id}'")
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"[voice] pipeline run failed: {exc}")
        traceback.print_exc()
        with contextlib.suppress(Exception):
            await websocket.close(code=4500, reason=f"pipeline error: {exc}")


@router.websocket("/ws/browser/{agent_id}")
async def browser_websocket(websocket: WebSocket, agent_id: str) -> None:
    """Browser raw-PCM voice session. Use with FastAPIWebsocketTransportComponent."""
    await websocket.accept()
    extra = {
        "session_id": websocket.query_params.get("session_id", ""),
        "user_id":    websocket.query_params.get("user_id", ""),
        "token":      websocket.query_params.get("token", ""),
        "transport":  "browser",
    }
    await _run_session(websocket, agent_id, extra)


@router.websocket("/ws/exotel/{agent_id}")
async def exotel_websocket(websocket: WebSocket, agent_id: str) -> None:
    """Exotel telephony voice session. Use with ExotelTransportComponent.

    Exotel sends a 'connected' frame followed by a 'start' frame containing
    ``stream_sid``/``call_sid`` before media frames begin. We read those here
    so transport components can use them.
    """
    await websocket.accept()
    stream_sid, call_sid = await _read_telephony_handshake(websocket, vendor="exotel")
    if stream_sid is None:
        await websocket.close(code=4400, reason="missing stream_sid in handshake")
        return
    extra = {
        "stream_sid": stream_sid,
        "call_sid":   call_sid or "",
        "user_id":    websocket.query_params.get("user_id", ""),
        "transport":  "exotel",
    }
    await _run_session(websocket, agent_id, extra)


@router.websocket("/ws/twilio/{agent_id}")
async def twilio_websocket(websocket: WebSocket, agent_id: str) -> None:
    """Twilio Media Streams voice session. Use with TwilioTransportComponent."""
    await websocket.accept()
    stream_sid, call_sid = await _read_telephony_handshake(websocket, vendor="twilio")
    if stream_sid is None:
        await websocket.close(code=4400, reason="missing stream_sid in handshake")
        return
    extra = {
        "stream_sid": stream_sid,
        "call_sid":   call_sid or "",
        "user_id":    websocket.query_params.get("user_id", ""),
        "transport":  "twilio",
    }
    await _run_session(websocket, agent_id, extra)


async def _read_telephony_handshake(websocket: WebSocket, *, vendor: str) -> tuple[str | None, str | None]:
    """Drain Exotel/Twilio control frames until the 'start' frame, return SIDs.

    Both vendors send JSON-text frames with an 'event' key. The 'start' frame
    carries ``start.streamSid`` (Twilio) / ``start.stream_sid`` (Exotel).
    """
    for _ in range(5):  # very short handshake; bail out if it stalls
        try:
            raw = await websocket.receive_text()
        except WebSocketDisconnect:
            return None, None
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        event = msg.get("event")
        if event == "connected":
            continue
        if event == "start":
            start = msg.get("start", {}) or {}
            stream_sid = start.get("streamSid") or start.get("stream_sid")
            call_sid = start.get("callSid") or start.get("call_sid")
            logger.info(f"[voice/{vendor}] start frame: stream_sid={stream_sid} call_sid={call_sid}")
            return stream_sid, call_sid
        logger.debug(f"[voice/{vendor}] unexpected handshake event: {event}")
    return None, None
