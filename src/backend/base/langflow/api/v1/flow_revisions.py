"""The history of a flow's graph: its timeline, any recorded revision, and restoring one.

Access follows the parent flow: whoever can read the flow can read its whole
history, whoever authored it; restoring needs write access. Nothing is filtered
by the requesting user.

Revisions are the history's own order and stay internal to clients: the
timeline pages by them and preview and restore address them, but the interface
shows people times and authors.
"""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import col, select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.utils.flow_history import history_http_error
from langflow.api.v1.authz_route_dependencies import AuthorizedReadFlow, AuthorizedWriteFlow
from langflow.api.v1.flows import _validate_catalog_policy_for_write
from langflow.api.v1.flows_helpers import _export_variable_names, _patch_flow
from langflow.services.database.models.flow.guards import lock_flow_for_read, lock_flow_for_update
from langflow.services.database.models.flow.model import FlowUpdate, FlowWriteRead
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_catalog_policy_service, get_storage_service
from langflow.services.flow_history.envelope import RESTORE_CAUSE
from langflow.services.flow_history.errors import FlowHistoryError
from langflow.services.flow_history.replay import reconstruct_graph
from langflow.services.flow_history.secrets import strip_graph_secrets
from langflow.services.flow_history.timeline import TimelineEntry, read_timeline
from langflow.services.storage.service import StorageService

router = APIRouter(prefix="/flows/{flow_id}/revisions", tags=["Flow History"])

MAX_PAGE_SIZE = 200


class RevisionActor(BaseModel):
    id: UUID
    username: str | None = Field(None, description="None when the user has since been deleted")


class RevisionOperation(BaseModel):
    revision: int
    actor: RevisionActor
    request_id: UUID
    cause: str | None = Field(None, description="What made the write that recorded it, when the writer said so")
    operation: dict = Field(description="The operation as recorded, with literal secret values removed")


class RevisionVersion(BaseModel):
    id: UUID
    version_number: int
    version_tag: str
    description: str | None
    created_at: datetime
    operation_revision: int
    saved_by: RevisionActor | None


class RevisionEntry(BaseModel):
    id: UUID
    start_revision: int
    end_revision: int = Field(description="The revision this entry can be previewed at or restored to")
    created_at: datetime | None
    actors: list[RevisionActor]
    request_ids: list[UUID]
    versions: list[RevisionVersion] = Field(description="Saved versions whose graph is one of this entry's revisions")
    operations: list[RevisionOperation] | None = Field(None, description="Present with include=operations")


class RevisionPage(BaseModel):
    flow_id: UUID
    latest_revision: int
    current_revision: int
    earliest_revision: int | None = Field(None, description="The first revision still retained; None before history")
    entries: list[RevisionEntry]
    next_before: int | None = Field(None, description="Pass as `before` to read the next, older page")


class RevisionGraph(BaseModel):
    flow_id: UUID
    revision: int
    latest_revision: int
    data: dict = Field(description="The flow's graph at the revision, with literal secret values removed")


class RevisionRestore(BaseModel):
    request_id: UUID | None = Field(None, description="Identifies this restore across retries")
    repair_revision_mismatch: bool = False


@router.get("", response_model=RevisionPage)
async def list_revisions(
    *,
    session: DbSession,
    flow_id: UUID,  # noqa: ARG001 -- resolved by the flow dependency
    flow: AuthorizedReadFlow,
    before: Annotated[int | None, Query(ge=1, description="Exclusive revision cursor from next_before")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    include: Annotated[
        str | None, Query(description="Comma-separated extras; 'operations' adds each entry's operations")
    ] = None,
) -> RevisionPage:
    """List the flow's history, newest first, one entry per recorded batch of operations."""
    extras = {part.strip() for part in (include or "").split(",") if part.strip()}
    unknown = extras - {"operations"}
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown include value(s): {', '.join(sorted(unknown))}")

    await lock_flow_for_read(session, flow)
    try:
        page = await read_timeline(
            session,
            flow,
            before=before,
            limit=limit,
            include_operations="operations" in extras,
            known_variable_names=await _export_variable_names(session, flow.user_id),
        )
    except FlowHistoryError as exc:
        raise history_http_error(exc) from exc

    usernames = await _usernames(session, page.entries)
    return RevisionPage(
        flow_id=flow.id,
        latest_revision=flow.latest_revision,
        current_revision=flow.current_revision,
        earliest_revision=page.earliest_revision,
        entries=[_entry(entry, usernames) for entry in page.entries],
        next_before=page.next_before,
    )


@router.get("/{revision}", response_model=RevisionGraph)
async def read_revision(
    *,
    session: DbSession,
    flow_id: UUID,  # noqa: ARG001 -- resolved by the flow dependency
    flow: AuthorizedReadFlow,
    revision: int,
) -> RevisionGraph:
    """Return the flow's graph as it was at ``revision``."""
    await lock_flow_for_read(session, flow)
    try:
        graph = await reconstruct_graph(
            session, flow.id, revision, latest_revision=flow.latest_revision, verify_anchor=True
        )
    except FlowHistoryError as exc:
        raise history_http_error(exc) from exc
    known_variable_names = await _export_variable_names(session, flow.user_id)
    return RevisionGraph(
        flow_id=flow.id,
        revision=revision,
        latest_revision=flow.latest_revision,
        data=strip_graph_secrets(graph, known_variable_names),
    )


@router.post("/{revision}/restore", response_model=FlowWriteRead)
async def restore_revision(
    *,
    session: DbSession,
    flow_id: UUID,  # noqa: ARG001 -- resolved by the flow dependency
    flow: AuthorizedWriteFlow,
    revision: int,
    current_user: CurrentActiveUser,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
    body: RevisionRestore | None = None,
) -> FlowWriteRead:
    """Make the graph at ``revision`` the flow's current graph, recorded as new revisions.

    The graph is replayed here rather than sent by the client: what a client
    can read has its secrets removed, and saving that back would blank them.
    Restoring the recorded graph restores its secrets too.
    """
    options = body or RevisionRestore()
    await lock_flow_for_update(session, flow)
    try:
        graph = copy.deepcopy(
            await reconstruct_graph(
                session, flow.id, revision, latest_revision=flow.latest_revision, verify_anchor=True
            )
        )
    except FlowHistoryError as exc:
        raise history_http_error(exc) from exc
    _validate_catalog_policy_for_write(graph, snapshot=get_catalog_policy_service().snapshot)
    return await _patch_flow(
        session=session,
        db_flow=flow,
        flow=FlowUpdate(
            data=graph,
            request_id=options.request_id,
            repair_revision_mismatch=options.repair_revision_mismatch,
            cause=RESTORE_CAUSE,
        ),
        user_id=current_user.id,
        storage_service=storage_service,
    )


async def _usernames(session: DbSession, entries: list[TimelineEntry]) -> dict[UUID, str]:
    user_ids = {actor for entry in entries for actor in entry.actor_user_ids}
    if entries and entries[0].operations is not None:
        user_ids |= {operation.actor_user_id for entry in entries for operation in entry.operations or []}
    user_ids |= {
        version.saved_by_user_id for entry in entries for version in entry.versions if version.saved_by_user_id
    }
    if not user_ids:
        return {}
    rows = (await session.exec(select(User.id, User.username).where(col(User.id).in_(user_ids)))).all()
    return dict(rows)


def _actor(user_id: UUID, usernames: dict[UUID, str]) -> RevisionActor:
    return RevisionActor(id=user_id, username=usernames.get(user_id))


def _version(version: FlowVersion, usernames: dict[UUID, str]) -> RevisionVersion:
    return RevisionVersion(
        id=version.id,
        version_number=version.version_number,
        version_tag=f"v{version.version_number}",
        description=version.description,
        created_at=version.created_at,
        operation_revision=version.operation_revision,
        saved_by=_actor(version.saved_by_user_id, usernames) if version.saved_by_user_id else None,
    )


def _entry(entry: TimelineEntry, usernames: dict[UUID, str]) -> RevisionEntry:
    return RevisionEntry(
        id=entry.id,
        start_revision=entry.start_revision,
        end_revision=entry.end_revision,
        created_at=entry.created_at,
        actors=[_actor(user_id, usernames) for user_id in entry.actor_user_ids],
        request_ids=entry.request_ids,
        versions=[_version(version, usernames) for version in entry.versions],
        operations=None
        if entry.operations is None
        else [
            RevisionOperation(
                revision=operation.revision,
                actor=_actor(operation.actor_user_id, usernames),
                request_id=operation.request_id,
                cause=operation.cause,
                operation=operation.operation,
            )
            for operation in entry.operations
        ],
    )
