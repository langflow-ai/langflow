from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from http import HTTPStatus
from langflow.utils.logger import log_buffer

log_router = APIRouter(tags=["Log"])


@log_router.get("/logs")
async def logs(
    start_lines: int = Query(0, ge=1, description="The number of logs from the start"),
    end_lines: int = Query(100, ge=1, description="The number of logs from the end"),
    session_id: str = Query(None, description="The session UUID to retrieve logs from for pagination"),
    page: int = Query(1, ge=1, description="The page number to retrieve logs from for pagination"),
    # TODO: add time based query
):
    global log_buffer
    if log_buffer.enabled() is False:
        raise HTTPException(
            status_code=HTTPStatus.NOT_IMPLEMENTED,
            detail="Log retrieval is disabled",
        )

    if page > 1 and session_id is None:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Session UUID is required for pagination",
        )

    if page == 1 and session_id is None:
        session_id = log_buffer.create_session()

    if session_id:
        result = log_buffer.get_page(session_id, page)
        if "error" in result:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=result["error"],
            )
        return JSONResponse(content=result)

    buffer_size = log_buffer.max_size()
    if start_lines > 0:
        index = min(start_lines, buffer_size)
        return JSONResponse(
            content={
                "logs": log_buffer.readlines()[:index],
                "page": 1,
                "total_pages": 1,
            }
        )
    else:
        index = min(end_lines, buffer_size)
        return JSONResponse(
            content={
                "logs": log_buffer.readlines()[-index:],
                "page": 1,
                "total_pages": 1,
            }
        )
