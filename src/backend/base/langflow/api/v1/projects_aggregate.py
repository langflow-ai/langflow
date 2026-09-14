"""Project operations that carry a project's whole contents in one request.

Separate from ``projects.py`` because these answer a different question. The
routes there change one project; these two make a project's contents match what
the caller sent, which is the contract the Control Plane consumes — one act, one
audit row, and nothing left behind when it fails.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from lfx.log.logger import logger
from pydantic import BaseModel, Field
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.flows import cascade_delete_flow
from langflow.api.v1.flows_helpers import _new_flow
from langflow.api.v1.projects import _new_project
from langflow.services.audit.events import PROJECT_CREATE, PROJECT_REPLACE, RESOURCE_FLOW
from langflow.services.audit.recorder import absorbed_into_aggregate
from langflow.services.audit.scope import audited_action
from langflow.services.authorization import ProjectAction, ensure_project_permission
from langflow.services.authorization.fetch import authorized_or_owner_scoped
from langflow.services.database.models.flow.model import Flow, FlowCreate
from langflow.services.database.models.folder.model import Folder, FolderCreate, FolderRead
from langflow.services.deps import get_storage_service

# Imported at runtime, not under TYPE_CHECKING: FastAPI resolves the annotation
# to build the dependency, and one it cannot resolve becomes a query parameter.
from langflow.services.storage.service import StorageService

router = APIRouter(prefix="/projects", tags=["Projects"])


class ProjectWithFlowsCreate(BaseModel):
    """A project and everything inside it, as one request."""

    name: str
    description: str | None = None
    flows: list[FlowCreate] = Field(default_factory=list)


class ProjectFlowsReplace(BaseModel):
    """The complete contents a project should end up with."""

    flows: list[FlowCreate] = Field(default_factory=list)


async def _create_flows_in(
    *,
    session: DbSession,
    project_id: UUID,
    flows: list[FlowCreate],
    current_user: CurrentActiveUser,
    storage_service: StorageService,
) -> int:
    """Create every flow inside one project, as part of a larger act."""
    with absorbed_into_aggregate(RESOURCE_FLOW):
        for flow in flows:
            flow.folder_id = project_id
            await _new_flow(
                session=session,
                flow=flow,
                user_id=current_user.id,
                storage_service=storage_service,
                # The caller sent the contents it wants, so a colliding endpoint
                # fails loud. Renaming it silently would return 201 for contents
                # that differ from the ones asked for, with no way to notice.
                fail_on_endpoint_conflict=True,
                propagate_unhandled_errors=True,
            )
    return len(flows)


async def _discard_project(session: DbSession, project_id: UUID) -> None:
    """Remove a project that should never have outlived its failed creation.

    On the caller's own session, and only after rolling it back: a second
    connection cannot write while the first still holds the transaction, and on
    SQLite that is not contention but a hard "database is locked".

    Committed here rather than left to the caller, whose transaction is about to
    be rolled back by the exception on its way out — which would take the
    cleanup with it and leave exactly the half-made project this prevents.

    Best effort: a cleanup that fails must not replace the error the caller
    needs to see.
    """
    from langflow.services.memory_base.flow_cleanup import (
        FlowMemoryBaseCleanup,
        finalize_flow_memory_base_cleanup,
    )

    cleanups: list[FlowMemoryBaseCleanup] = []
    try:
        await session.rollback()
        for flow in (await session.exec(select(Flow).where(Flow.folder_id == project_id))).all():
            cleanups.extend(await cascade_delete_flow(session, flow.id))
        orphan = (await session.exec(select(Folder).where(Folder.id == project_id))).first()
        if orphan is not None:
            await session.delete(orphan)
        await session.commit()
        # After the commit, never before: a remote collection is dropped only
        # for flows that are actually gone.
        await finalize_flow_memory_base_cleanup(cleanups)
    except Exception as exc:  # noqa: BLE001
        await logger.awarning(
            "op=discard_project project_id=%s outcome=left_behind error=%s", project_id, type(exc).__name__
        )


@router.post("/with-flows", response_model=FolderRead, status_code=201)
async def create_project_with_flows(
    *,
    session: DbSession,
    project: ProjectWithFlowsCreate,
    current_user: CurrentActiveUser,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    """Create a project and its complete contents, or create nothing at all.

    Atomic because half a project is worse than none: a caller that has to
    create the project and then fill it cannot undo the first step when the
    second fails, and is left owning something it never asked for.

    One row describes the whole operation. The flows created underneath are
    absorbed into it — the caller performed one act and the trail says so.
    """
    async with audited_action(session, event=PROJECT_CREATE, user_id=current_user.id) as audit:
        await ensure_project_permission(current_user, ProjectAction.CREATE)
        created = await _new_project(
            session=session,
            project=FolderCreate(name=project.name, description=project.description),
            current_user=current_user,
            fail_on_name_conflict=True,
        )
        # Named before the contents are attempted, so a failure is recorded
        # against the project it was about rather than against nothing.
        audit.describe(resource_id=created.id)
        try:
            total = await _create_flows_in(
                session=session,
                project_id=created.id,
                flows=project.flows,
                current_user=current_user,
                storage_service=storage_service,
            )
        except Exception:
            # Creating a project registers an MCP server, and that registration
            # commits — so by the time the contents fail the project is already
            # durable and no rollback can reach it. Undoing it explicitly is the
            # only way to keep the promise this endpoint makes.
            await _discard_project(session, created.id)
            raise
        audit.describe(flows_total=total)
        return created


@router.put("/{project_id}/flows", response_model=FolderRead, status_code=200)
async def replace_project_flows(
    *,
    session: DbSession,
    project_id: UUID,
    body: ProjectFlowsReplace,
    current_user: CurrentActiveUser,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    """Replace everything inside a project, or change nothing at all.

    The contents a caller sends are the contents it should end up with, so what
    is missing from the request is deleted. Atomic for the same reason as
    creation: a project caught between its old and new contents is a state
    nobody asked for and no caller can repair.
    """
    from langflow.services.memory_base.flow_cleanup import (
        FlowMemoryBaseCleanup,
        finalize_flow_memory_base_cleanup,
    )

    async with audited_action(session, event=PROJECT_REPLACE, user_id=current_user.id, resource_id=project_id) as audit:
        project = await authorized_or_owner_scoped(
            session,
            Folder,
            id_column=Folder.id,
            resource_id=project_id,
            owner_column=Folder.user_id,
            owner_id=current_user.id,
        )
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        await ensure_project_permission(
            current_user,
            ProjectAction.WRITE,
            project_id=project_id,
            project_user_id=project.user_id,
            workspace_id=project.workspace_id,
        )

        existing = (await session.exec(select(Flow).where(Flow.folder_id == project_id))).all()
        cleanups: list[FlowMemoryBaseCleanup] = []
        with absorbed_into_aggregate(RESOURCE_FLOW):
            for flow in existing:
                cleanups.extend(await cascade_delete_flow(session, flow.id))
        await session.flush()

        total = await _create_flows_in(
            session=session,
            project_id=project_id,
            flows=body.flows,
            current_user=current_user,
            storage_service=storage_service,
        )
        audit.describe(flows_removed=len(existing), flows_total=total)
        # Committed here rather than at teardown so the remote collections are
        # dropped only once the deletions that justify it are durable.
        await session.commit()
        await finalize_flow_memory_base_cleanup(cleanups)
        return FolderRead.model_validate(project, from_attributes=True)
