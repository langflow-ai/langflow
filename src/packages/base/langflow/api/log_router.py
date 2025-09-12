import asyncio
import json
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from lfx.log.logger import log_buffer

log_router = APIRouter(tags=["Log"])


NUMBER_OF_NOT_SENT_BEFORE_KEEPALIVE = 5


async def event_generator(request: Request):
    global log_buffer  # noqa: PLW0602
    last_read_item = None
    current_not_sent = 0
    while not await request.is_disconnected():
        to_write: list[Any] = []
        with log_buffer.get_write_lock():
            if last_read_item is None:
                last_read_item = log_buffer.buffer[len(log_buffer.buffer) - 1]
            else:
                found_last = False
                for item in log_buffer.buffer:
                    if found_last:
                        to_write.append(item)
                        last_read_item = item
                        continue
                    if item is last_read_item:
                        found_last = True
                        continue

                # in case the last item is nomore in the buffer
                if not found_last:
                    for item in log_buffer.buffer:
                        to_write.append(item)
                        last_read_item = item
        if to_write:
            for ts, msg in to_write:
                yield f"{json.dumps({ts: msg})}\n\n"
        else:
            current_not_sent += 1
            if current_not_sent == NUMBER_OF_NOT_SENT_BEFORE_KEEPALIVE:
                current_not_sent = 0
                yield "keepalive\n\n"

        await asyncio.sleep(1)


@log_router.get("/logs-stream")
async def stream_logs(
    request: Request,
):
    """HTTP/2 Server-Sent-Event (SSE) endpoint for streaming logs.

    It establishes a long-lived connection to the server and receives log messages in real-time.
    The client should use the header "Accept: text/event-stream".
    """
    global log_buffer  # noqa: PLW0602
    if log_buffer.enabled() is False:
        raise HTTPException(
            status_code=HTTPStatus.NOT_IMPLEMENTED,
            detail="Log retrieval is disabled",
        )

    return StreamingResponse(event_generator(request), media_type="text/event-stream")


@log_router.get("/logs")
async def logs(
    lines_before: Annotated[int, Query(description="The number of logs before the timestamp or the last log")] = 0,
    lines_after: Annotated[int, Query(description="The number of logs after the timestamp")] = 0,
    timestamp: Annotated[int, Query(description="The timestamp to start getting logs from")] = 0,
):
    global log_buffer  # noqa: PLW0602
    if log_buffer.enabled() is False:
        raise HTTPException(
            status_code=HTTPStatus.NOT_IMPLEMENTED,
            detail="Log retrieval is disabled",
        )
    if lines_after > 0 and lines_before > 0:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Cannot request logs before and after the timestamp",
        )
    if timestamp <= 0:
        if lines_after > 0:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Timestamp is required when requesting logs after the timestamp",
            )
        content = log_buffer.get_last_n(10) if lines_before <= 0 else log_buffer.get_last_n(lines_before)
    elif lines_before > 0:
        content = log_buffer.get_before_timestamp(timestamp=timestamp, lines=lines_before)
    elif lines_after > 0:
        content = log_buffer.get_after_timestamp(timestamp=timestamp, lines=lines_after)
    else:
        content = log_buffer.get_before_timestamp(timestamp=timestamp, lines=10)
    return JSONResponse(content=content)
