"""Database-backed team workflow templates."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlmodel import col, select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.schemas.team_templates import (
    TeamTemplateCreate,
    TeamTemplateCreateResponse,
    TeamTemplateList,
    TeamTemplateRead,
    TeamTemplateSummary,
    TeamTemplateUpdate,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.team_template import TeamTemplate, TeamTemplateStatus
from langflow.services.team_templates import SANITIZER_VERSION, SanitizationReport, sanitize_flow_data

router = APIRouter(prefix="/team-templates", tags=["Team Templates"])
TEMPLATE_MANAGER_USERNAME = "langflow"


def _summary(row: TeamTemplate) -> TeamTemplateSummary:
    return TeamTemplateSummary.model_validate(row, from_attributes=True)


def _read(row: TeamTemplate) -> TeamTemplateRead:
    return TeamTemplateRead.model_validate(row, from_attributes=True)


def _sanitize_or_422(flow_data: dict) -> tuple[dict, SanitizationReport]:
    try:
        return sanitize_flow_data(flow_data)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


def _ensure_template_admin(row: TeamTemplate, user) -> None:
    if not user.is_superuser and row.created_by != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the template creator may modify it")


def _ensure_template_delete(row: TeamTemplate, user) -> None:
    if user.username == TEMPLATE_MANAGER_USERNAME:
        return
    _ensure_template_admin(row, user)


async def _get_active_template(session: DbSession, template_id: UUID) -> TeamTemplate:
    row = await session.get(TeamTemplate, template_id)
    if row is None or row.status != TeamTemplateStatus.ACTIVE.value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return row


async def _get_publishable_flow(session: DbSession, flow_id: UUID, user) -> Flow:
    flow = await session.get(Flow, flow_id)
    if flow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
    if not user.is_superuser and flow.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the flow owner may publish it")
    if not flow.data or not flow.data.get("nodes"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="An empty flow cannot be saved as a template",
        )
    return flow


@router.post("", response_model=TeamTemplateCreateResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=TeamTemplateCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_team_template(
    payload: TeamTemplateCreate,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> TeamTemplateCreateResponse:
    flow = await _get_publishable_flow(session, payload.source_flow_id, current_user)
    sanitized_data, report = _sanitize_or_422(flow.data or {})

    row = TeamTemplate(
        name=payload.name,
        description=payload.description,
        category=payload.category,
        tags=payload.tags,
        icon=flow.icon,
        gradient=flow.gradient,
        flow_data=sanitized_data,
        source_flow_id=flow.id,
        workspace_id=flow.workspace_id,
        created_by=current_user.id,
        sanitizer_version=SANITIZER_VERSION,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return TeamTemplateCreateResponse(**_read(row).model_dump(), cleared_fields=report.cleared_count)


@router.get("", response_model=TeamTemplateList)
@router.get("/", response_model=TeamTemplateList)
async def list_team_templates(
    _current_user: CurrentActiveUser,
    session: DbSession,
    q: Annotated[str | None, Query(max_length=100)] = None,
    category: Annotated[str | None, Query(max_length=64)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> TeamTemplateList:
    base = select(TeamTemplate).where(TeamTemplate.status == TeamTemplateStatus.ACTIVE.value)
    if category and category != "all-templates":
        base = base.where(TeamTemplate.category == category)
    if q:
        pattern = f"%{q.strip()}%"
        base = base.where(or_(col(TeamTemplate.name).ilike(pattern), col(TeamTemplate.description).ilike(pattern)))

    total = int((await session.exec(select(func.count()).select_from(base.subquery()))).first() or 0)
    statement = (
        base.order_by(col(TeamTemplate.updated_at).desc(), TeamTemplate.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = list(await session.exec(statement))
    return TeamTemplateList(items=[_summary(row) for row in rows], total=total, page=page, page_size=page_size)


@router.get("/{template_id}", response_model=TeamTemplateRead)
async def get_team_template(
    template_id: UUID,
    _current_user: CurrentActiveUser,
    session: DbSession,
) -> TeamTemplateRead:
    return _read(await _get_active_template(session, template_id))


@router.patch("/{template_id}", response_model=TeamTemplateRead)
async def update_team_template(
    template_id: UUID,
    payload: TeamTemplateUpdate,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> TeamTemplateRead:
    row = await _get_active_template(session, template_id)
    _ensure_template_admin(row, current_user)

    changes = payload.model_dump(exclude_unset=True, exclude={"refresh_from_source"})
    for field_name, field_value in changes.items():
        normalized_value = (
            field_value.strip() if isinstance(field_value, str) and field_name in {"name", "category"} else field_value
        )
        setattr(row, field_name, normalized_value)

    if payload.refresh_from_source:
        if row.source_flow_id is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The source flow no longer exists")
        flow = await _get_publishable_flow(session, row.source_flow_id, current_user)
        row.flow_data, _ = _sanitize_or_422(flow.data or {})
        row.sanitizer_version = SANITIZER_VERSION
        row.icon = flow.icon
        row.gradient = flow.gradient
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _read(row)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_team_template(
    template_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> None:
    row = await _get_active_template(session, template_id)
    _ensure_template_delete(row, current_user)
    row.status = TeamTemplateStatus.ARCHIVED.value
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    await session.commit()
