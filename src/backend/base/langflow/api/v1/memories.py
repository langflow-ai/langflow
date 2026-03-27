"""REST API for Memory Base management.

Endpoints:
    POST   /memories                    – Create
    GET    /memories                    – List (current user, paginated)
    GET    /memories/{id}               – Get one
    GET    /memories/{id}/sessions      – List sessions (tracked + untracked from MessageTable)
    PATCH  /memories/{id}               – Update (name / threshold / auto_capture / preprocessing)
    DELETE /memories/{id}               – Delete (cancels active tasks + removes KB from disk)
    POST   /memories/{id}/flush        – Manual flush / trigger ingestion
    POST   /memories/{id}/regenerate    – Regenerate from mismatch

Edge cases enforced:
    409 Conflict  – name already in use for this user (on create).
    409 Conflict  – active ingestion task already running for same (mb, session).
    404 Not Found – memory base does not belong to the current user.
    422 Unprocessable – preprocessing=true but preproc_model missing.
"""

from __future__ import annotations

import uuid
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlmodel import apaginate
from pydantic import BaseModel

from langflow.api.utils import CurrentActiveUser
from langflow.services.database.models.memory_base.model import (
    MemoryBaseCreate,
    MemoryBaseRead,
    MemoryBaseSessionRead,
    MemoryBaseUpdate,
)
from langflow.services.deps import session_scope
from langflow.services.memory_base.service import MemoryBaseService

router = APIRouter(tags=["Memories"], prefix="/memories", include_in_schema=False)

# Module-level singleton – lightweight; no DB state stored on instance
_service = MemoryBaseService()


# ------------------------------------------------------------------ #
#  Request / Response schemas                                           #
# ------------------------------------------------------------------ #


class FlushRequest(BaseModel):
    session_id: str


class MismatchResponse(BaseModel):
    mismatch_detected: bool


class RegenerateResponse(BaseModel):
    job_ids: list[str]


# ------------------------------------------------------------------ #
#  CRUD                                                                #
# ------------------------------------------------------------------ #


@router.post("", status_code=HTTPStatus.CREATED)
@router.post("/", status_code=HTTPStatus.CREATED)
async def create_memory_base(
    current_user: CurrentActiveUser,
    payload: MemoryBaseCreate = Body(..., embed=False),
) -> MemoryBaseRead:
    """Create a new Memory Base.

    - kb_name is auto-generated as `{sanitized_name}_{8hex}`.
    - KB directory and embedding_metadata.json are created on disk immediately.
    - Returns 409 if a Memory Base with the same name already exists for this user.
    - Returns 422 if preprocessing=true but preproc_model is missing.
    """
    try:
        mb = await _service.create(payload, user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MemoryBaseRead.model_validate(mb)


@router.get("", status_code=HTTPStatus.OK)
@router.get("/", status_code=HTTPStatus.OK)
async def list_memory_bases(
    current_user: CurrentActiveUser,
    params: Annotated[Params, Depends()],
) -> Page[MemoryBaseRead]:
    """List all Memory Bases owned by the current user (paginated).

    Query params (from fastapi-pagination):
        page  – 1-based page number (default 1)
        size  – page size (default 50)
    """
    async with session_scope() as db:
        stmt = _service.list_for_user_stmt(user_id=current_user.id)
        return await apaginate(
            db, stmt, params=params, transformer=lambda items: [MemoryBaseRead.model_validate(m) for m in items]
        )


@router.get("/{memory_base_id}", status_code=HTTPStatus.OK)
async def get_memory_base(
    memory_base_id: uuid.UUID,
    current_user: CurrentActiveUser,
) -> MemoryBaseRead:
    """Get details for a specific Memory Base."""
    mb = await _service.get(memory_base_id, user_id=current_user.id)
    if mb is None:
        raise HTTPException(status_code=404, detail="Memory base not found")
    return MemoryBaseRead.model_validate(mb)


@router.get("/{memory_base_id}/sessions", status_code=HTTPStatus.OK)
async def list_sessions(
    memory_base_id: uuid.UUID,
    current_user: CurrentActiveUser,
) -> list[MemoryBaseSessionRead]:
    """List all sessions tracked by this Memory Base.

    Auth: ownership is verified via current_user.id — only sessions belonging
    to this user's Memory Base are returned.

    Includes both:
    - Sessions already tracked in MemoryBaseSession (synced/triggered).
    - Sessions that have flow output messages but have never been synced yet
      (pending_count > 0, total_processed == 0, cursor_id == None).
    """
    try:
        return await _service.get_sessions(memory_base_id, user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{memory_base_id}", status_code=HTTPStatus.OK)
async def update_memory_base(
    memory_base_id: uuid.UUID,
    current_user: CurrentActiveUser,
    patch: MemoryBaseUpdate = Body(..., embed=False),
) -> MemoryBaseRead:
    """Update mutable parameters (threshold, auto_capture, preprocessing, etc.).

    Threshold changes only take effect at the next auto-capture trigger.
    Any already-running ingestion task continues with its original arguments.
    """
    mb = await _service.update(memory_base_id, user_id=current_user.id, patch=patch)
    if mb is None:
        raise HTTPException(status_code=404, detail="Memory base not found")
    return MemoryBaseRead.model_validate(mb)


@router.delete("/{memory_base_id}", status_code=HTTPStatus.NO_CONTENT)
async def delete_memory_base(
    memory_base_id: uuid.UUID,
    current_user: CurrentActiveUser,
) -> None:
    """Delete a Memory Base.

    Active ingestion tasks are forcefully cancelled before the DB record is
    removed. The associated KB directory is deleted from disk afterwards
    (best-effort — a disk failure will not affect the 204 response).
    """
    deleted = await _service.delete(memory_base_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory base not found")


# ------------------------------------------------------------------ #
#  Ingestion trigger                                                   #
# ------------------------------------------------------------------ #


@router.post("/{memory_base_id}/flush", status_code=HTTPStatus.ACCEPTED)
async def flush_memory_base(
    memory_base_id: uuid.UUID,
    current_user: CurrentActiveUser,
    body: FlushRequest = Body(..., embed=False),
) -> dict:
    """Manually trigger an ingestion / sync job regardless of the threshold.

    Returns 409 Conflict if an ingestion task is already in progress for the
    given (memory_base_id, session_id) pair to prevent concurrent indexing.
    """
    try:
        job_id = await _service.trigger_ingestion(
            memory_base_id=memory_base_id,
            user_id=current_user.id,
            session_id=body.session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {"job_id": job_id}


# ------------------------------------------------------------------ #
#  Mismatch detection & regeneration                                   #
# ------------------------------------------------------------------ #


@router.get("/{memory_base_id}/mismatch", status_code=HTTPStatus.OK)
async def check_mismatch(
    memory_base_id: uuid.UUID,
    current_user: CurrentActiveUser,
) -> MismatchResponse:
    """Detect if the vector store is empty while metadata records processed messages.

    The UI should surface a "Mismatch Detected" warning and offer a Regenerate button.
    """
    try:
        detected = await _service.check_mismatch(memory_base_id, user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MismatchResponse(mismatch_detected=detected)


@router.post("/{memory_base_id}/regenerate", status_code=HTTPStatus.ACCEPTED)
async def regenerate_memory_base(
    memory_base_id: uuid.UUID,
    current_user: CurrentActiveUser,
) -> RegenerateResponse:
    """Regenerate the Knowledge Base by resetting all session cursors and re-ingesting.

    Use this to recover from external Chroma directory deletions or vector DB corruption.
    All MemoryBaseSession.cursor_id values are set to None before re-running ingestion.
    """
    try:
        job_ids = await _service.regenerate(memory_base_id, user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RegenerateResponse(job_ids=job_ids)
