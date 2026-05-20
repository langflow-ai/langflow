"""CRUD endpoints for the native triggers feature.

The route handlers are intentionally thin. Validation (cron + timezone)
is delegated to ``langflow.services.triggers.scheduler``; the
scheduling of the first ``trigger_job`` row is delegated to the same
module so the worker and the API stay in agreement about when a
trigger fires.

Ownership rule: a trigger is visible/editable only to its owning user.
Cross-user access returns 404 (not 403), mirroring the convention
used by the flow endpoints.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.database.models.triggers import (
    Trigger,
    TriggerCreate,
    TriggerJob,
    TriggerJobRead,
    TriggerRead,
    TriggerUpdate,
)
from langflow.services.triggers.scheduler import (
    InvalidTriggerConfigError,
    next_fire_time_utc,
    validate_trigger_config,
)

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


router = APIRouter(prefix="/triggers", tags=["Triggers"])


# --------------------------------------------------------------------------- #
#  Helpers                                                                     #
# --------------------------------------------------------------------------- #


async def _get_owned_trigger(session: AsyncSession, trigger_id: UUID, user_id: UUID) -> Trigger:
    statement = select(Trigger).where(Trigger.id == trigger_id, Trigger.user_id == user_id)
    result = await session.exec(statement)
    trigger = result.first()
    if trigger is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trigger not found")
    return trigger


async def _assert_flow_owned(session: AsyncSession, flow_id: UUID, user_id: UUID) -> None:
    statement = select(Flow.id).where(Flow.id == flow_id, Flow.user_id == user_id)
    result = await session.exec(statement)
    if result.first() is None:
        # Cross-user access returns 404, same as the flow read endpoints.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")


def _validate_config_or_400(*, cron_expression: str, timezone_name: str) -> None:
    try:
        validate_trigger_config(cron_expression=cron_expression, timezone_name=timezone_name)
    except InvalidTriggerConfigError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


# --------------------------------------------------------------------------- #
#  CRUD                                                                        #
# --------------------------------------------------------------------------- #


@router.post("", response_model=TriggerRead, status_code=status.HTTP_201_CREATED)
async def create_trigger(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    body: TriggerCreate,
) -> Trigger:
    """Create a trigger and enqueue its first ``trigger_job``."""
    _validate_config_or_400(cron_expression=body.cron_expression, timezone_name=body.timezone)
    if not 1 <= body.max_attempts <= 10:  # noqa: PLR2004
        raise HTTPException(status_code=400, detail="max_attempts must be in [1, 10]")

    await _assert_flow_owned(session, body.flow_id, current_user.id)

    now = datetime.now(timezone.utc)
    trigger = Trigger(
        id=uuid4(),
        flow_id=body.flow_id,
        user_id=current_user.id,
        name=body.name,
        trigger_type=body.trigger_type,
        cron_expression=body.cron_expression,
        timezone=body.timezone,
        payload=body.payload,
        max_attempts=body.max_attempts,
        is_active=body.is_active,
        created_at=now,
        updated_at=now,
    )
    session.add(trigger)

    if trigger.is_active:
        first_fire = next_fire_time_utc(
            cron_expression=body.cron_expression,
            timezone_name=body.timezone,
            after=now,
        )
        session.add(
            TriggerJob(
                id=uuid4(),
                trigger_id=trigger.id,
                status=JobStatus.QUEUED,
                scheduled_at=first_fire,
                attempt=1,
                max_attempts=body.max_attempts,
                created_at=now,
            ),
        )

    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Trigger with name {body.name!r} already exists",
        ) from exc

    return trigger


@router.get("", response_model=list[TriggerRead])
async def list_triggers(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    flow_id: UUID | None = None,
) -> list[Trigger]:
    statement = select(Trigger).where(Trigger.user_id == current_user.id)
    if flow_id is not None:
        statement = statement.where(Trigger.flow_id == flow_id)
    statement = statement.order_by(col(Trigger.created_at).desc())
    result = await session.exec(statement)
    return list(result.all())


@router.get("/{trigger_id}", response_model=TriggerRead)
async def get_trigger(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    trigger_id: UUID,
) -> Trigger:
    return await _get_owned_trigger(session, trigger_id, current_user.id)


@router.patch("/{trigger_id}", response_model=TriggerRead)
async def update_trigger(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    trigger_id: UUID,
    body: TriggerUpdate,
) -> Trigger:
    trigger = await _get_owned_trigger(session, trigger_id, current_user.id)

    new_cron = body.cron_expression if body.cron_expression is not None else trigger.cron_expression
    new_tz = body.timezone if body.timezone is not None else trigger.timezone
    if body.cron_expression is not None or body.timezone is not None:
        _validate_config_or_400(cron_expression=new_cron or "", timezone_name=new_tz)

    if body.max_attempts is not None and not 1 <= body.max_attempts <= 10:  # noqa: PLR2004
        raise HTTPException(status_code=400, detail="max_attempts must be in [1, 10]")

    if body.name is not None:
        trigger.name = body.name
    if body.cron_expression is not None:
        trigger.cron_expression = body.cron_expression
    if body.timezone is not None:
        trigger.timezone = body.timezone
    if body.payload is not None:
        trigger.payload = body.payload
    if body.max_attempts is not None:
        trigger.max_attempts = body.max_attempts
    if body.is_active is not None:
        trigger.is_active = body.is_active

    trigger.updated_at = datetime.now(timezone.utc)
    session.add(trigger)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Trigger with name {trigger.name!r} already exists",
        ) from exc
    return trigger


@router.delete("/{trigger_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trigger(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    trigger_id: UUID,
) -> None:
    trigger = await _get_owned_trigger(session, trigger_id, current_user.id)
    # ON DELETE CASCADE on trigger_job.trigger_id removes the queued
    # rows. Any in-flight worker iteration finishes against the
    # already-loaded Flow object; its terminal write becomes a no-op.
    await session.delete(trigger)
    await session.flush()


@router.get("/{trigger_id}/jobs", response_model=list[TriggerJobRead])
async def list_trigger_jobs(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    trigger_id: UUID,
    status_filter: JobStatus | None = None,
    limit: int = 50,
) -> list[TriggerJob]:
    # Authorise by re-using the ownership check.
    await _get_owned_trigger(session, trigger_id, current_user.id)

    statement = select(TriggerJob).where(TriggerJob.trigger_id == trigger_id)
    if status_filter is not None:
        statement = statement.where(TriggerJob.status == status_filter)
    statement = statement.order_by(col(TriggerJob.scheduled_at).desc()).limit(limit)
    result = await session.exec(statement)
    return list(result.all())
