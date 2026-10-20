"""The request state machine: requested -> approved -> erasing -> done, or refused / withdrawn."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import update
from sqlmodel import col, select

from langflow.services.data_subjects import audit_events
from langflow.services.data_subjects.context import EraseContext
from langflow.services.data_subjects.dry_run import builder_dry_run, end_user_dry_run
from langflow.services.data_subjects.errors import (
    DataSubjectError,
    InvalidTransitionError,
    SelfApprovalError,
    SubjectNotFoundError,
)
from langflow.services.data_subjects.identity import end_user_keys, ensure_not_an_account
from langflow.services.data_subjects.lifecycle import (
    account_deletion_mutation,
    ensure_plugin_allows_deletion,
    lock_account,
)
from langflow.services.data_subjects.stop import ensure_builder_erasable, stop_builder, stop_end_user
from langflow.services.data_subjects.storage_steps import builder_storage_plan, end_user_storage_plan
from langflow.services.database.models.data_subject_request import (
    OPEN_STATUSES,
    DataSubjectRequest,
    DataSubjectRequestSource,
    DataSubjectRequestStatus,
    DataSubjectType,
)
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from sqlmodel.ext.asyncio.session import AsyncSession


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _due_at() -> datetime:
    return _now() + timedelta(days=get_settings_service().settings.data_subject_response_days)


async def _open_request_for(session: AsyncSession, subject_user_id: UUID) -> DataSubjectRequest | None:
    return (
        await session.exec(
            select(DataSubjectRequest).where(
                DataSubjectRequest.subject_user_id == subject_user_id,
                col(DataSubjectRequest.status).in_([status.value for status in OPEN_STATUSES]),
            )
        )
    ).first()


async def _create(session: AsyncSession, request: DataSubjectRequest, actor_id: UUID | None) -> DataSubjectRequest:
    session.add(request)
    await session.flush()
    await audit_events.record_dsar_event(
        session,
        actor_id=actor_id,
        action=audit_events.ACTION_REQUEST,
        request_id=request.id,
        details={"request_id": str(request.id), "subject_type": request.subject_type, "source": request.source},
    )
    return request


async def create_builder_request(
    session: AsyncSession, *, subject: User, requested_by: UUID | None, source: DataSubjectRequestSource
) -> tuple[DataSubjectRequest, bool]:
    """Return the open request for this builder, or a new one. The flag is True when it was created."""
    existing = await _open_request_for(session, subject.id)
    if existing is not None:
        return existing, False
    request = DataSubjectRequest(
        subject_type=DataSubjectType.BUILDER.value,
        subject_user_id=subject.id,
        subject_label=subject.username,
        source=source.value,
        requested_by=requested_by,
        due_at=_due_at(),
    )
    return await _create(session, request, requested_by), True


async def create_end_user_request(
    session: AsyncSession,
    *,
    end_user_id: str,
    scope_flow_ids: list[UUID] | None,
    requested_by: UUID | None,
    source: DataSubjectRequestSource,
) -> tuple[DataSubjectRequest, bool]:
    keys = end_user_keys(end_user_id)
    await ensure_not_an_account(session, keys)
    existing = await _open_request_for(session, keys.message_owner_id)
    if existing is not None:
        return existing, False
    request = DataSubjectRequest(
        subject_type=DataSubjectType.END_USER.value,
        subject_user_id=keys.message_owner_id,
        subject_end_user_id=keys.raw_id,
        subject_label=keys.raw_id,
        scope_flow_ids=[str(flow_id) for flow_id in scope_flow_ids] if scope_flow_ids else None,
        source=source.value,
        requested_by=requested_by,
        due_at=_due_at(),
    )
    return await _create(session, request, requested_by), True


def _require_status(request: DataSubjectRequest, *allowed: DataSubjectRequestStatus) -> None:
    if request.status not in {status.value for status in allowed}:
        msg = f"A request in status '{request.status}' cannot do this"
        raise InvalidTransitionError(msg, details={"status": request.status})


async def _claim(session: AsyncSession, request: DataSubjectRequest, new_status: DataSubjectRequestStatus) -> None:
    """Move a ``requested`` row to ``new_status`` only if the database still says ``requested``.

    The loaded instance may be stale: another session can have decided the request since. The
    conditional update is the decision; it also holds the row until commit on PostgreSQL.
    """
    _require_status(request, DataSubjectRequestStatus.REQUESTED)
    result = await session.exec(
        update(DataSubjectRequest)
        .where(
            col(DataSubjectRequest.id) == request.id,
            col(DataSubjectRequest.status) == DataSubjectRequestStatus.REQUESTED.value,
        )
        .values(status=new_status.value)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        await session.refresh(request)
        _require_status(request, DataSubjectRequestStatus.REQUESTED)
        msg = "The request was decided by someone else"
        raise InvalidTransitionError(msg, details={"status": request.status})
    request.status = new_status.value


def close_request(request: DataSubjectRequest, status: DataSubjectRequestStatus) -> None:
    """Closed requests keep the label, ids, counts and times as the accountability record (Art. 5(2)).

    The raw end-user id is dropped; the label is the only identity a closed request keeps.
    """
    request.status = status.value
    request.finished_at = _now()
    request.subject_end_user_id = None
    request.scope_flow_ids = None
    request.pending_paths = None
    request.cursor = None


async def withdraw(session: AsyncSession, request: DataSubjectRequest, actor_id: UUID) -> DataSubjectRequest:
    _require_status(request, DataSubjectRequestStatus.REQUESTED)
    if request.subject_user_id != actor_id:
        msg = "Only the person who asked can withdraw a request"
        raise InvalidTransitionError(msg)
    await _claim(session, request, DataSubjectRequestStatus.WITHDRAWN)
    close_request(request, DataSubjectRequestStatus.WITHDRAWN)
    session.add(request)
    await audit_events.record_dsar_event(
        session,
        actor_id=actor_id,
        action=audit_events.ACTION_WITHDRAW,
        request_id=request.id,
        details={"request_id": str(request.id)},
    )
    return request


async def refuse(
    session: AsyncSession, request: DataSubjectRequest, actor_id: UUID, note: str | None
) -> DataSubjectRequest:
    await _claim(session, request, DataSubjectRequestStatus.REFUSED)
    request.decided_by = actor_id
    request.decided_at = _now()
    request.refusal_note = note
    close_request(request, DataSubjectRequestStatus.REFUSED)
    session.add(request)
    await audit_events.record_dsar_event(
        session,
        actor_id=actor_id,
        action=audit_events.ACTION_REFUSE,
        request_id=request.id,
        details={"request_id": str(request.id)},
    )
    return request


def erase_context(request: DataSubjectRequest, username: str | None = None) -> EraseContext:
    scope = tuple(UUID(value) for value in request.scope_flow_ids or [])
    keys = end_user_keys(request.subject_end_user_id) if request.subject_end_user_id else None
    return EraseContext(
        request_id=request.id,
        subject_user_id=request.subject_user_id,
        username=username or request.subject_label,
        end_user=keys,
        scope_flow_ids=scope,
        cursor=dict(request.cursor or {}),
    )


async def _approve_builder(
    session: AsyncSession, request: DataSubjectRequest, actor_id: UUID | None
) -> tuple[dict[str, int], dict[str, int]]:
    await lock_account(session, request.subject_user_id)
    user = await session.get(User, request.subject_user_id)
    if user is None:
        msg = "The account no longer exists"
        raise SubjectNotFoundError(msg)
    await ensure_builder_erasable(session, user)
    await ensure_plugin_allows_deletion(session, account_deletion_mutation(user, actor_id))
    ctx = erase_context(request, username=user.username)
    request.pending_paths = await builder_storage_plan(session, ctx)
    request.subject_label = user.username
    approved = (await builder_dry_run(session, user)).counts
    return await stop_builder(session, user), approved


async def _approve_end_user(
    session: AsyncSession, request: DataSubjectRequest
) -> tuple[dict[str, int], dict[str, int]]:
    ctx = erase_context(request)
    if ctx.end_user is None:
        msg = "The end-user id of this request is no longer available"
        raise SubjectNotFoundError(msg)
    request.pending_paths = end_user_storage_plan(ctx)
    approved = (await end_user_dry_run(session, ctx.end_user, ctx.scope_flow_ids)).counts
    return await stop_end_user(session, ctx.end_user, ctx.scope_flow_ids), approved


async def approve(
    session: AsyncSession, request: DataSubjectRequest, actor_id: UUID | None, *, automatic: bool = False
) -> DataSubjectRequest:
    """Run phase 1 and hand the request to the worker. Guard refusals are audited and re-raised.

    ``automatic`` marks an approval made by the expiry sweep: there is no approving administrator.
    """
    _require_status(request, DataSubjectRequestStatus.REQUESTED)
    if request.subject_user_id is not None and request.subject_user_id == actor_id:
        msg = "Another administrator must approve the deletion of your own account"
        raise SelfApprovalError(msg)
    # Claimed before any side effect, so a concurrent withdraw or refuse cannot land after the account stops.
    await _claim(session, request, DataSubjectRequestStatus.APPROVED)
    try:
        if request.subject_type == DataSubjectType.BUILDER.value:
            stopped, approved = await _approve_builder(session, request, actor_id)
        else:
            stopped, approved = await _approve_end_user(session, request)
    except DataSubjectError as exc:
        request.status = DataSubjectRequestStatus.REQUESTED.value
        session.add(request)
        await audit_events.record_dsar_event(
            session,
            actor_id=actor_id,
            action=audit_events.ACTION_APPROVE,
            request_id=request.id,
            result="deny",
            details={"request_id": str(request.id), "blocked_by": exc.code, "automatic": automatic},
        )
        raise
    request.status = DataSubjectRequestStatus.APPROVED.value
    request.decided_by = actor_id
    request.decided_at = _now()
    # What the administrator approved, in dry-run units; the engine adds its own per-step counters beside it.
    request.counts = {"stopped": stopped, "approved": approved}
    request.error = None
    session.add(request)
    await audit_events.record_dsar_event(
        session,
        actor_id=actor_id,
        action=audit_events.ACTION_APPROVE,
        request_id=request.id,
        details={"request_id": str(request.id), "subject_type": request.subject_type, "automatic": automatic},
    )
    return request


async def create_and_approve(
    session: AsyncSession,
    create: Awaitable[tuple[DataSubjectRequest, bool]],
    actor_id: UUID | None,
) -> DataSubjectRequest:
    """Open (or reuse) a request and approve it at once, for an administrator who erases directly.

    When a guard refuses, a request this call created is rolled back with its events: nobody asked for
    it, and keeping it would let the expiry sweep approve it later. A request that was already open
    keeps the refusal on record.
    """
    created = False
    try:
        request, created = await create
        if request.status == DataSubjectRequestStatus.REQUESTED.value:
            await approve(session, request, actor_id)
    except DataSubjectError:
        if created:
            await session.rollback()
        else:
            await session.commit()
        raise
    return request


async def retry(session: AsyncSession, request: DataSubjectRequest) -> DataSubjectRequest:
    _require_status(request, DataSubjectRequestStatus.APPROVED, DataSubjectRequestStatus.ERASING)
    request.error = None
    session.add(request)
    return request
