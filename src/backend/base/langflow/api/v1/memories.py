"""REST API for Memory Base management.

Endpoints:
    POST   /memories                    - Create
    GET    /memories                    - List (current user, paginated)
    GET    /memories/{id}               - Get one
    GET    /memories/{id}/sessions      - List sessions (tracked + untracked from MessageTable)
    GET    /memories/{id}/messages      - List ingested messages (optionally filtered by ?session_id=)
    PATCH  /memories/{id}               - Update (name / threshold / auto_capture)
    DELETE /memories/{id}               - Delete (cancels active tasks + removes KB from disk)
    POST   /memories/{id}/flush        - Manual flush / trigger ingestion
    POST   /memories/{id}/regenerate    - Regenerate from mismatch

Edge cases enforced:
    409 Conflict  - name already in use for this user (on create).
    409 Conflict  - active ingestion task already running for same (mb, session).
    404 Not Found - memory base does not belong to the current user.
    422 Unprocessable - preprocessing=true but preproc_model missing.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlmodel import apaginate
from pydantic import BaseModel
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser
from langflow.services.database.models.memory_base.model import (
    MemoryBase,
    MemoryBaseCreate,
    MemoryBaseRead,
    MemoryBaseSessionRead,
    MemoryBaseUpdate,
)
from langflow.services.deps import get_memory_base_service, session_scope
from langflow.services.jobs import DuplicateJobError
from langflow.services.memory_base.service import PreprocessingValidationError

router = APIRouter(tags=["Memories"], prefix="/memories", include_in_schema=False)


# ------------------------------------------------------------------ #
#  Request / Response schemas                                           #
# ------------------------------------------------------------------ #


class MessageReadResponse(BaseModel):
    """Slim message projection for Memory Base session message listings.

    Only messages that have been ingested into the requested Memory Base are returned.
    ``job_id`` and ``ingested_at`` are sourced from MessageIngestionRecord.
    """

    model_config = {"from_attributes": True}

    id: uuid.UUID
    timestamp: datetime | None = None
    sender: str
    sender_name: str
    session_id: str
    text: str
    content_blocks: list[dict[str, Any]] = []
    job_id: uuid.UUID | None = None
    ingested_at: datetime | None = None


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
    payload: Annotated[MemoryBaseCreate, Body(embed=False)],
) -> MemoryBaseRead:
    """Create a new Memory Base.

    - kb_name is auto-generated as `{sanitized_name}_{8hex}`.
    - KB directory and embedding_metadata.json are created on disk immediately.
    - Returns 409 if a Memory Base with the same name already exists for this user.
    - Returns 422 if preprocessing=true but preproc_model is missing.
    """
    try:
        mb = await get_memory_base_service().create(payload, user_id=current_user.id)
    except PermissionError as exc:
        # Flow not found or belongs to another user — return 404 to avoid info-leak
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PreprocessingValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MemoryBaseRead.model_validate(mb)


@router.get("", status_code=HTTPStatus.OK)
@router.get("/", status_code=HTTPStatus.OK)
async def list_memory_bases(
    current_user: CurrentActiveUser,
    params: Annotated[Params, Depends()],
    flow_id: uuid.UUID | None = None,
) -> Page[MemoryBaseRead]:
    """List all Memory Bases owned by the current user (paginated) for a flow_id.

    Query params (from fastapi-pagination):
        page  - 1-based page number (default 1)
        size  - page size (default 50)
    """
    async with session_scope() as db:
        stmt = get_memory_base_service().list_for_user_stmt(user_id=current_user.id, flow_id=flow_id)
        return await apaginate(
            db, stmt, params=params, transformer=lambda items: [MemoryBaseRead.model_validate(m) for m in items]
        )


@router.get("/{memory_base_id}", status_code=HTTPStatus.OK)
async def get_memory_base(
    memory_base_id: uuid.UUID,
    current_user: CurrentActiveUser,
) -> MemoryBaseRead:
    """Get details for a specific Memory Base."""
    mb = await get_memory_base_service().get(memory_base_id, user_id=current_user.id)
    if mb is None:
        raise HTTPException(status_code=404, detail="Memory base not found")
    return MemoryBaseRead.model_validate(mb)


@router.get("/{memory_base_id}/sessions", status_code=HTTPStatus.OK)
async def list_sessions(
    memory_base_id: uuid.UUID,
    current_user: CurrentActiveUser,
    params: Annotated[Params, Depends()],
) -> Page[MemoryBaseSessionRead]:
    """List persisted sessions for this Memory Base (paginated).

    Only sessions that have been synced at least once (i.e. have a
    MemoryBaseSession row) are returned.  Results are ordered by
    last_sync_at descending.

    Each item includes ``pending_count``: the number of completed flow runs
    remaining before the next auto-capture ingestion is triggered.
    """
    from langflow.services.memory_base.ingestion import count_pending_messages

    async with session_scope() as db:
        try:
            mb = await get_memory_base_service().get_memory_base_or_404(db, memory_base_id, current_user.id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        stmt = get_memory_base_service().sessions_stmt(memory_base_id, current_user.id)
        raw_page = await apaginate(db, stmt, params=params)

        items: list[MemoryBaseSessionRead] = []
        for s in raw_page.items:
            pending_count = await count_pending_messages(db, mb, s)
            read = MemoryBaseSessionRead.model_validate(s)
            read.pending_count = pending_count
            items.append(read)

    return raw_page.model_copy(update={"items": items})


@router.get("/{memory_base_id}/messages", status_code=HTTPStatus.OK)
async def list_memory_base_messages(
    memory_base_id: uuid.UUID,
    current_user: CurrentActiveUser,
    params: Annotated[Params, Depends()],
    session_id: str | None = None,
) -> Page[MessageReadResponse]:
    """List messages ingested into this Memory Base (paginated).

    Only messages that have been successfully ingested into the requested Memory Base
    are returned, ordered by timestamp descending. When ``session_id`` is provided,
    results are filtered to that session; otherwise all ingested messages across
    sessions are returned. Each item includes ``job_id`` and ``ingested_at`` from
    the MessageIngestionRecord.

    Returns 404 if the Memory Base does not belong to the current user.
    """
    service = get_memory_base_service()
    async with session_scope() as db:
        mb_stmt = select(MemoryBase).where(MemoryBase.id == memory_base_id).where(MemoryBase.user_id == current_user.id)
        result = await db.exec(mb_stmt)
        mb = result.first()
        if mb is None:
            raise HTTPException(status_code=404, detail="Memory base not found")

        if mb.preprocessing:
            # Preprocessing MBs: the KB holds LLM-distilled output, so the
            # surface for "what's in the KB" is MemoryBasePreprocessingOutput,
            # not MessageTable.  Project the row into the same response shape
            # so the API contract is identical from the frontend's perspective.
            stmt = service.session_preprocessed_outputs_stmt(memory_base_id, session_id)
            return await apaginate(
                db,
                stmt,
                params=params,
                transformer=lambda rows: [
                    MessageReadResponse(
                        id=row.id,
                        timestamp=row.created_at,
                        sender="Machine",
                        sender_name="Preprocessor",
                        session_id=row.session_id,
                        text=row.output_text or "",
                        content_blocks=[],
                        job_id=row.job_id,
                        ingested_at=row.created_at,
                    )
                    for row in rows
                ],
            )

        stmt = service.session_raw_messages_stmt(memory_base_id, session_id)
        return await apaginate(
            db,
            stmt,
            params=params,
            transformer=lambda rows: [
                MessageReadResponse(
                    id=msg.id,
                    timestamp=msg.timestamp,
                    sender=msg.sender,
                    sender_name=msg.sender_name,
                    session_id=msg.session_id,
                    text=msg.text,
                    content_blocks=msg.content_blocks or [],
                    job_id=mir.job_id,
                    ingested_at=mir.ingested_at,
                )
                for msg, mir in rows
            ],
        )


@router.patch("/{memory_base_id}", status_code=HTTPStatus.OK)
async def update_memory_base(
    memory_base_id: uuid.UUID,
    current_user: CurrentActiveUser,
    patch: Annotated[MemoryBaseUpdate, Body(embed=False)],
) -> MemoryBaseRead:
    """Update mutable parameters (name, threshold, auto_capture).

    Threshold changes only take effect at the next auto-capture trigger.
    Any already-running ingestion task continues with its original arguments.
    Preprocessing fields (preprocessing, preproc_model, preproc_instructions, preproc_kill_phrase)
    are immutable after creation and cannot be patched.
    """
    try:
        mb = await get_memory_base_service().update(memory_base_id, user_id=current_user.id, patch=patch)
    except PreprocessingValidationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
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
    deleted = await get_memory_base_service().delete(memory_base_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory base not found")


# ------------------------------------------------------------------ #
#  Ingestion trigger                                                   #
# ------------------------------------------------------------------ #


@router.post("/{memory_base_id}/flush", status_code=HTTPStatus.ACCEPTED)
async def flush_memory_base(
    memory_base_id: uuid.UUID,
    current_user: CurrentActiveUser,
    body: Annotated[FlushRequest, Body(embed=False)],
) -> dict:
    """Manually trigger an ingestion / sync job regardless of the threshold.

    Returns 409 Conflict if an ingestion task is already in progress for the
    given (memory_base_id, session_id) pair to prevent concurrent indexing.
    """
    try:
        job_id = await get_memory_base_service().trigger_ingestion(
            memory_base_id=memory_base_id,
            user_id=current_user.id,
            session_id=body.session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DuplicateJobError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
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
        detected = await get_memory_base_service().check_mismatch(memory_base_id, user_id=current_user.id)
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
        job_ids = await get_memory_base_service().regenerate(memory_base_id, user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RegenerateResponse(job_ids=job_ids)
