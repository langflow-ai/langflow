"""Authorized storage adapter for one project preparation attempt. Never commits."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from lfx.projects.bindings import flow_revision
from lfx.projects.lifecycle import (
    FlowSelector,
    FlowView,
    ProjectConfigError,
    ProjectResourceUnavailableError,
    ProjectSaveConflictError,
    ProjectView,
    SourceSnapshot,
    SourceVersionReference,
)
from sqlmodel import col, select, update

from langflow.services.authorization import FlowAction, ProjectAction, ensure_flow_permission, ensure_project_permission
from langflow.services.authorization.fetch import authorized_or_owner_scoped
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.crud import create_flow_version_entry
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.folder.model import Folder

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.user.model import User


MAX_CONTEXT_RESOURCES = 500


def project_error_http(exc: ProjectConfigError) -> HTTPException:
    code = (
        404
        if isinstance(exc, ProjectResourceUnavailableError)
        else 409
        if isinstance(exc, ProjectSaveConflictError)
        else 422
    )
    return HTTPException(code, str(exc))


def public_config(config: dict | None) -> dict | None:
    if config is None:
        return None
    return deepcopy({key: value for key, value in config.items() if key != "_applied"})


def _flow_state(row: Flow) -> dict:
    return deepcopy(
        {
            name: getattr(row, name)
            for name in (
                "data",
                "name",
                "description",
                "folder_id",
                "user_id",
                "workspace_id",
                "is_component",
                "flow_type",
                "locked",
            )
        }
    )


def _project_state(row: Folder) -> dict:
    return deepcopy(
        {name: getattr(row, name) for name in ("name", "project_type", "project_config", "user_id", "workspace_id")}
    )


class LangflowProjectSaveContext:
    """Private row state backs detached views, including when plugin code mutates a copy."""

    def __init__(self, session: AsyncSession, user: User):
        self._session = session
        self._user = user
        self._flows: dict[UUID, tuple[Flow, dict, FlowView]] = {}
        self._projects: dict[UUID, tuple[Folder, dict]] = {}
        self._tokens: dict[str, UUID] = {}
        self._execute: set[UUID] = set()
        self._snapshots: dict[UUID, SourceSnapshot] = {}
        self._writable = False

    async def start_save(self, project: Folder) -> ProjectView:
        # Acquire a write transaction even for an otherwise unchanged config.
        # FOR UPDATE alone is ignored by SQLite; this also serializes its writers.
        await self._session.exec(update(Folder).where(Folder.id == project.id).values(id=Folder.id))
        self._writable = True
        self._projects[project.id] = (project, _project_state(project))
        return ProjectView(project.id, project.name, project.project_type, public_config(project.project_config))

    async def read_project(self, project_id: UUID, *, expected_type: str) -> ProjectView:
        if project_id in self._projects:
            row, state = self._projects[project_id]
        else:
            row = await authorized_or_owner_scoped(
                self._session,
                Folder,
                id_column=Folder.id,
                resource_id=project_id,
                owner_column=Folder.user_id,
                owner_id=self._user.id,
            )
            if row is None:
                msg = "Referenced project not found"
                raise ProjectResourceUnavailableError(msg)
            state = _project_state(row)
        try:
            await ensure_project_permission(
                self._user,
                ProjectAction.READ,
                project_id=row.id,
                project_user_id=row.user_id,
                workspace_id=row.workspace_id,
            )
        except HTTPException as exc:
            if exc.status_code != status.HTTP_403_FORBIDDEN:
                raise
            msg = "Referenced project not found"
            raise ProjectResourceUnavailableError(msg) from exc
        if state["project_type"] != expected_type:
            msg = f"Choose a project of type {expected_type}."
            raise ProjectConfigError(msg)
        if len(self._projects) >= MAX_CONTEXT_RESOURCES and project_id not in self._projects:
            msg = "A project configuration cannot reference more than 500 projects."
            raise ProjectConfigError(msg)
        self._projects[project_id] = (row, state)
        return ProjectView(project_id, state["name"], state["project_type"], public_config(state["project_config"]))

    async def _authorize_flow(self, row: Flow, action: FlowAction) -> None:
        try:
            await ensure_flow_permission(
                self._user,
                action,
                flow_id=row.id,
                flow_user_id=row.user_id,
                folder_id=row.folder_id,
                workspace_id=row.workspace_id,
            )
        except HTTPException as exc:
            if exc.status_code != status.HTTP_403_FORBIDDEN:
                raise
            msg = "Project flow dependency not found"
            raise ProjectResourceUnavailableError(msg) from exc

    async def read_flow(self, selector: FlowSelector, *, access: Literal["read", "execute"]) -> FlowView:
        if access not in {"read", "execute"}:
            msg = "Choose read or execute access."
            raise ProjectConfigError(msg)
        flow_id = selector.id
        if flow_id is None:
            matches = list(
                (
                    await self._session.exec(
                        select(Flow.id).where(Flow.user_id == self._user.id, Flow.name == selector.name).limit(2)
                    )
                ).all()
            )
            if len(matches) != 1:
                msg = "A named flow dependency is missing or ambiguous."
                raise ProjectConfigError(msg)
            flow_id = matches[0]
        if flow_id in self._flows:
            row, _, view = self._flows[flow_id]
        else:
            row = await authorized_or_owner_scoped(
                self._session,
                Flow,
                id_column=Flow.id,
                resource_id=flow_id,
                owner_column=Flow.user_id,
                owner_id=self._user.id,
            )
            if row is None:
                msg = "Project flow dependency not found"
                raise ProjectResourceUnavailableError(msg)
            await self._authorize_flow(row, FlowAction.READ)
            if len(self._flows) >= MAX_CONTEXT_RESOURCES:
                msg = "A project configuration cannot depend on more than 500 flows."
                raise ProjectConfigError(msg)
            state = _flow_state(row)
            view = FlowView(
                row.id,
                row.folder_id,
                row.name,
                row.description or "",
                deepcopy(row.data or {}),
                row.is_component,
                row.flow_type,
                bool(row.locked),
                flow_revision(row.data or {}),
                uuid4().hex,
            )
            self._flows[flow_id] = (row, state, view)
            self._tokens[view.token] = flow_id
        if access == "execute":
            await self._authorize_flow(row, FlowAction.EXECUTE)
            self._execute.add(flow_id)
        return deepcopy(view)

    async def verify_unchanged(self) -> None:
        """Refresh under row locks; include layout and metadata, not only executable hashes."""
        for project_id in sorted(self._projects, key=str):
            row, state = self._projects[project_id]
            await self._session.refresh(row, with_for_update=True)
            if _project_state(row) != state:
                msg = "A referenced project changed during save. Reload and try again."
                raise ProjectSaveConflictError(msg)
        for flow_id in sorted(self._flows, key=str):
            row, state, _ = self._flows[flow_id]
            await self._session.refresh(row, with_for_update=True)
            if _flow_state(row) != state:
                msg = "A source or target flow changed during save. Reload and try again."
                raise ProjectSaveConflictError(msg)

    async def pin_sources(self, tokens: tuple[str, ...], *, label: str) -> tuple[SourceSnapshot, ...]:
        if not self._writable:
            msg = "Source snapshots require a project save transaction."
            raise ProjectConfigError(msg)
        ids = []
        for token in tokens:
            flow_id = self._tokens.get(token)
            if flow_id is None or flow_id not in self._execute:
                msg = "Read each source with execute access before pinning it."
                raise ProjectConfigError(msg)
            ids.append(flow_id)
        await self.verify_unchanged()
        for flow_id in dict.fromkeys(ids):
            if flow_id in self._snapshots:
                continue
            row, _, view = self._flows[flow_id]
            if row.user_id is None:
                msg = "The source has no owner and cannot be snapshotted."
                raise ProjectConfigError(msg)
            version = (
                await self._session.exec(
                    select(FlowVersion)
                    .where(FlowVersion.flow_id == flow_id, FlowVersion.user_id == row.user_id)
                    .order_by(col(FlowVersion.version_number).desc())
                    .limit(1)
                )
            ).first()
            if version is None or version.data != view.data:
                version = await create_flow_version_entry(
                    self._session,
                    flow_id,
                    row.user_id,
                    data=deepcopy(view.data),
                    description=f"Project {label} binding"[:500],
                )
            self._snapshots[flow_id] = SourceSnapshot(
                SourceVersionReference(flow_id, version.id, view.revision), deepcopy(view.data)
            )
        return tuple(deepcopy(self._snapshots[flow_id]) for flow_id in ids)

    async def read_saved_source(self, reference: SourceVersionReference) -> SourceSnapshot:
        await self.read_flow(FlowSelector(id=reference.flow_id), access="execute")
        row, _, _ = self._flows[reference.flow_id]
        version = await self._session.get(FlowVersion, reference.version_id)
        if (
            version is None
            or version.flow_id != row.id
            or version.user_id != row.user_id
            or flow_revision(version.data or {}) != reference.revision
        ):
            msg = "A required source snapshot is unavailable. Review and save the binding."
            raise ProjectConfigError(msg)
        return SourceSnapshot(reference, deepcopy(version.data or {}))

    async def writable_target(self, flow_id: UUID, project: Folder) -> Flow:
        if flow_id not in self._flows:
            msg = "Choose a target flow from this project."
            raise ProjectConfigError(msg)
        row, _, _ = self._flows[flow_id]
        if row.folder_id != project.id or row.user_id != project.user_id:
            msg = "Choose a target flow from this project."
            raise ProjectConfigError(msg)
        await self._authorize_flow(row, FlowAction.WRITE)
        return row
