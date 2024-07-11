import asyncio
import json
from fastapi import APIRouter, Query, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from http import HTTPStatus
from langflow.utils.logger import log_buffer

log_router = APIRouter(tags=["Log"])


async def event_generator(request: Request):
    # latest_timestamp = time.time()
    global log_buffer

    last_line = log_buffer.get_last_n(1)
    latest_timestamp, _ = last_line.popitem()
    while True:
        if await request.is_disconnected():
            break

        new_logs = log_buffer.get_after_timestamp(timestamp=latest_timestamp, lines=100)
        if new_logs:
            temp_ts = 0.0
            for ts, msg in new_logs.items():
                if ts > latest_timestamp:
                    yield f"{json.dumps({ts:msg})}\n"
                temp_ts = ts
            # for the next query iteration
            latest_timestamp = temp_ts
        else:
            yield ": keepalive\n\n"

        await asyncio.sleep(1)


@log_router.get("/logs-stream")
async def stream_logs(
    request: Request,
):
    """
    HTTP/2 Server-Sent-Event (SSE) endpoint for streaming logs
    it establishes a long-lived connection to the server and receives log messages in real-time
    the client should use the head "Accept: text/event-stream"
    """
    global log_buffer
    if log_buffer.enabled() is False:
        raise HTTPException(
            status_code=HTTPStatus.NOT_IMPLEMENTED,
            detail="Log retrieval is disabled",
        )

    return StreamingResponse(event_generator(request), media_type="text/event-stream")


@log_router.get("/logs")
async def logs(
    lines_before: int = Query(1, ge=1, description="The number of logs before the timestamp or the last log"),
    lines_after: int = Query(0, ge=1, description="The number of logs after the timestamp"),
    timestamp: float = Query(0, description="The timestamp to start streaming logs from"),
):
    global log_buffer
    if log_buffer.enabled() is False:
        raise HTTPException(
            status_code=HTTPStatus.NOT_IMPLEMENTED,
            detail="Log retrieval is disabled",
        )

    logs = dict()
    if lines_after > 0 and timestamp == 0:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Timestamp is required when requesting logs after the timestamp",
        )

    if lines_after > 0 and timestamp > 0:
        logs = log_buffer.get_after_timestamp(timestamp=timestamp, lines=lines_after)
        return JSONResponse(content=logs)

    if timestamp == 0:
        if lines_before > 0:
            logs = log_buffer.get_last_n(lines_before)
    else:
        if lines_before > 0:
            logs = log_buffer.get_before_timestamp(timestamp=timestamp, lines=lines_before)

    return JSONResponse(content=logs)
