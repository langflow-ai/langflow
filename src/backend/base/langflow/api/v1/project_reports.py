"""Project report discovery and full evidence reads through existing flow storage."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from lfx.projects.artifact_store import (
    MAX_REPORT_PAGE_SIZE,
    InvalidReportCursorError,
    ReportPage,
    list_reports,
    read_report,
)
from lfx.projects.artifacts import SourcedReport
from lfx.services.storage.service import StorageService
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession, build_content_disposition
from langflow.services.authorization import (
    FlowAction,
    ProjectAction,
    ensure_flow_permission,
    ensure_project_permission,
    filter_visible_resources,
)
from langflow.services.authorization.fetch import authorized_or_owner_scoped, deny_to_404
from langflow.services.authorization.utils import _resolve_authz_domain
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import get_authorization_service, get_storage_service

router = APIRouter(prefix="/projects/{project_id}/reports", tags=["Projects"])
Storage = Annotated[StorageService, Depends(get_storage_service)]


async def report_project(project_id: UUID, session: DbSession, current_user: CurrentActiveUser) -> Folder:
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
    try:
        await ensure_project_permission(
            current_user,
            ProjectAction.READ,
            project_id=project.id,
            project_user_id=project.user_id,
            workspace_id=project.workspace_id,
        )
    except HTTPException as exc:
        raise deny_to_404(exc, "Project not found") from exc
    return project


ReportProject = Annotated[Folder, Depends(report_project)]


async def report_flow(
    flow_id: UUID, project: ReportProject, session: DbSession, current_user: CurrentActiveUser
) -> Flow:
    flow = await authorized_or_owner_scoped(
        session,
        Flow,
        id_column=Flow.id,
        resource_id=flow_id,
        owner_column=Flow.user_id,
        owner_id=current_user.id,
    )
    if flow is None or flow.folder_id != project.id:
        raise HTTPException(status_code=404, detail="Report not found")
    try:
        await ensure_flow_permission(
            current_user,
            FlowAction.READ,
            flow_id=flow.id,
            flow_user_id=flow.user_id,
            folder_id=flow.folder_id,
            workspace_id=project.workspace_id,
        )
    except HTTPException as exc:
        raise deny_to_404(exc, "Report not found") from exc
    return flow


ReportFlow = Annotated[Flow, Depends(report_flow)]


@router.get("", response_model=ReportPage)
async def project_reports(
    project: ReportProject,
    session: DbSession,
    current_user: CurrentActiveUser,
    storage: Storage,
    limit: Annotated[int, Query(ge=1, le=MAX_REPORT_PAGE_SIZE)] = 20,
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
):
    stmt = select(Flow).where(Flow.folder_id == project.id, Flow.is_component == False)  # noqa: E712
    authz = get_authorization_service()
    if not (await authz.supports_cross_user_fetch() and await authz.is_enabled()):
        stmt = stmt.where(Flow.user_id == current_user.id)
    flows = await filter_visible_resources(
        current_user,
        resource_type="flow",
        candidates=list((await session.exec(stmt)).all()),
        domain_extractor=lambda flow: _resolve_authz_domain(project.workspace_id, flow.folder_id),
        owner_extractor=lambda flow: flow.user_id,
        act=FlowAction.READ,
    )
    try:
        return await list_reports(storage, [flow.id for flow in flows], limit=limit, cursor=cursor)
    except InvalidReportCursorError as exc:
        raise HTTPException(status_code=422, detail="Invalid report cursor.") from exc


async def stored_report(report_id: UUID, flow: ReportFlow, storage: Storage) -> SourcedReport:
    try:
        return await read_report(storage, flow.id, report_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=409, detail="The saved report is invalid. Its evidence could not be verified."
        ) from exc


@router.get("/{flow_id}/{report_id}", response_model=SourcedReport)  # noqa: FAST003 - path fields are dependencies
async def project_report(report: Annotated[SourcedReport, Depends(stored_report)]):
    return report


@router.get("/{flow_id}/{report_id}/download/{format}")  # noqa: FAST003 - path fields are dependencies
async def download_project_report(
    report: Annotated[SourcedReport, Depends(stored_report)],
    format: Literal["markdown", "json"],  # noqa: A002
):
    # Both downloads derive from the validated canonical record, so the report
    # remains usable if a separate Markdown copy was removed from file storage.
    markdown = format == "markdown"
    name = f"report-{report.id}.{'md' if markdown else 'json'}"
    return Response(
        content=report.render_markdown() if markdown else report.model_dump_json(indent=2),
        media_type="text/markdown" if markdown else "application/json",
        headers={"Content-Disposition": build_content_disposition(name)},
    )
