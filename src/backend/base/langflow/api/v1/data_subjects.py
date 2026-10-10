"""Admin API for GDPR data subject requests: queue, find, export, approve, refuse, erase."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlmodel import col, select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.utils.migration_pause import changes_the_instance
from langflow.api.v1.data_subjects_common import (
    request_read,
    require_data_subject_feature,
    to_http_error,
    zip_response,
)
from langflow.services.auth.context import AUTH_METHOD_API_KEY, get_current_auth_context
from langflow.services.authorization.admin import administration_denied, is_administrator
from langflow.services.data_subjects import audit_events
from langflow.services.data_subjects import requests as request_service
from langflow.services.data_subjects.dry_run import builder_dry_run, end_user_dry_run
from langflow.services.data_subjects.end_user_search import search_end_users
from langflow.services.data_subjects.errors import (
    DataSubjectError,
    InvalidTransitionError,
    RequestNotFoundError,
    SubjectNotFoundError,
)
from langflow.services.data_subjects.export import export_builder, export_end_user
from langflow.services.data_subjects.identity import end_user_keys, ensure_not_an_account
from langflow.services.data_subjects.schemas import (
    DataSubjectRef,
    DataSubjectRequestPage,
    DataSubjectRequestRead,
    DryRunSummary,
    EndUserMatch,
    RefuseRequest,
)
from langflow.services.data_subjects.worker import data_subject_erase_worker
from langflow.services.database.models.data_subject_request import (
    OPEN_STATUSES,
    DataSubjectRequest,
    DataSubjectRequestSource,
    DataSubjectRequestStatus,
    DataSubjectType,
)
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_authorization_service

router = APIRouter(
    prefix="/data-subjects",
    tags=["Data Subjects"],
    dependencies=[Depends(require_data_subject_feature)],
)
MAX_PAGE_SIZE = 200
MAX_END_USER_MATCHES = 50


async def _require_admin(user: User) -> None:
    if not await is_administrator(user, resource="user", authorization_service=get_authorization_service()):
        raise administration_denied(None, resource="user")


async def _load_request(session, request_id: UUID) -> DataSubjectRequest:
    request = await session.get(DataSubjectRequest, request_id)
    if request is None:
        raise to_http_error(RequestNotFoundError("Data subject request not found"))
    return request


async def _load_builder(session, user_id: UUID, actor: User) -> User:
    subject = await session.get(User, user_id)
    if subject is None:
        raise to_http_error(SubjectNotFoundError("User not found"))
    if subject.is_superuser and not actor.is_superuser:
        raise HTTPException(status_code=403, detail="Only a superuser may erase a platform superuser")
    return subject


async def _builder_id(session, ref: DataSubjectRef) -> UUID:
    """Resolve a builder named by id or by username; an email address is the username under SSO.

    Usernames are unique ignoring case (``ix_user_username_lower``), so a case-insensitive match is exact.
    """
    if ref.user_id is not None:
        return ref.user_id
    name = (ref.username or "").strip().lower()
    user_id = (await session.exec(select(User.id).where(func.lower(User.username) == name))).first()
    if user_id is None:
        raise to_http_error(SubjectNotFoundError("User not found"))
    return user_id


def _caller_source() -> DataSubjectRequestSource:
    """A request made with an API key came from an integration; anything else was an admin at the console."""
    context = get_current_auth_context()
    if context is not None and context.method == AUTH_METHOD_API_KEY:
        return DataSubjectRequestSource.API
    return DataSubjectRequestSource.ADMIN


async def _create(session, ref: DataSubjectRef, actor: User, source: DataSubjectRequestSource):
    if ref.subject_type == DataSubjectType.BUILDER:
        subject = await _load_builder(session, await _builder_id(session, ref), actor)
        return await request_service.create_builder_request(
            session, subject=subject, requested_by=actor.id, source=source
        )
    return await request_service.create_end_user_request(
        session, end_user_id=ref.end_user_id, scope_flow_ids=ref.flow_ids, requested_by=actor.id, source=source
    )


@router.post("/requests", response_model=DataSubjectRequestRead)
async def create_request(
    ref: DataSubjectRef, current_user: CurrentActiveUser, session: DbSession, response: Response
) -> DataSubjectRequestRead:
    """Record a request for an admin to review. Returns the open request when one already exists."""
    await _require_admin(current_user)
    try:
        request, created = await _create(session, ref, current_user, _caller_source())
    except DataSubjectError as exc:
        raise to_http_error(exc) from exc
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return request_read(request)


@router.get("/requests", response_model=DataSubjectRequestPage)
async def list_requests(
    *,
    current_user: CurrentActiveUser,
    session: DbSession,
    status_filter: Annotated[list[DataSubjectRequestStatus] | None, Query(alias="status")] = None,
    subject_type: DataSubjectType | None = None,
    open_only: bool = False,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
) -> DataSubjectRequestPage:
    await _require_admin(current_user)
    stmt = select(DataSubjectRequest)
    if status_filter:
        stmt = stmt.where(col(DataSubjectRequest.status).in_([s.value for s in status_filter]))
    if open_only:
        stmt = stmt.where(col(DataSubjectRequest.status).in_([s.value for s in OPEN_STATUSES]))
    if subject_type is not None:
        stmt = stmt.where(DataSubjectRequest.subject_type == subject_type.value)
    total = (await session.exec(select(func.count()).select_from(stmt.subquery()))).one()
    rows = (
        await session.exec(
            stmt.order_by(col(DataSubjectRequest.requested_at).desc(), col(DataSubjectRequest.id))
            .offset(skip)
            .limit(limit)
        )
    ).all()
    return DataSubjectRequestPage(total_count=total, requests=[request_read(row) for row in rows])


@router.get("/requests/{request_id}", response_model=DataSubjectRequestRead)
async def get_request(request_id: UUID, current_user: CurrentActiveUser, session: DbSession):
    await _require_admin(current_user)
    return request_read(await _load_request(session, request_id))


async def _dry_run(session, request: DataSubjectRequest) -> DryRunSummary:
    if request.subject_type == DataSubjectType.BUILDER.value:
        subject = await session.get(User, request.subject_user_id)
        if subject is None:
            raise to_http_error(SubjectNotFoundError("The account no longer exists"))
        return await builder_dry_run(session, subject)
    if not request.subject_end_user_id:
        raise to_http_error(InvalidTransitionError("This request is closed"))
    scope = tuple(UUID(v) for v in request.scope_flow_ids or [])
    return await end_user_dry_run(session, end_user_keys(request.subject_end_user_id), scope)


@router.get("/requests/{request_id}/dry-run", response_model=DryRunSummary)
async def dry_run_request(request_id: UUID, current_user: CurrentActiveUser, session: DbSession) -> DryRunSummary:
    """What approving would erase, and whether a guard blocks it."""
    await _require_admin(current_user)
    return await _dry_run(session, await _load_request(session, request_id))


@router.post("/requests/{request_id}/approve", response_model=DataSubjectRequestRead, status_code=202)
async def approve_request(request_id: UUID, current_user: CurrentActiveUser, session: DbSession):
    """Stop all access now and erase in the background."""
    await _require_admin(current_user)
    request = await _load_request(session, request_id)
    if request.subject_type == DataSubjectType.BUILDER.value:
        await _load_builder(session, request.subject_user_id, current_user)
    try:
        await request_service.approve(session, request, current_user.id)
    except DataSubjectError as exc:
        await session.commit()
        raise to_http_error(exc) from exc
    await session.commit()
    data_subject_erase_worker.notify()
    return request_read(request)


@router.post("/requests/{request_id}/refuse", response_model=DataSubjectRequestRead)
async def refuse_request(
    request_id: UUID, body: RefuseRequest, current_user: CurrentActiveUser, session: DbSession
) -> DataSubjectRequestRead:
    """Decline a request (legal hold or another Art. 17(3) exception). The note stays internal."""
    await _require_admin(current_user)
    request = await _load_request(session, request_id)
    try:
        await request_service.refuse(session, request, current_user.id, body.note)
    except DataSubjectError as exc:
        raise to_http_error(exc) from exc
    return request_read(request)


@router.post("/requests/{request_id}/retry", response_model=DataSubjectRequestRead, status_code=202)
async def retry_request(request_id: UUID, current_user: CurrentActiveUser, session: DbSession):
    await _require_admin(current_user)
    request = await _load_request(session, request_id)
    try:
        await request_service.retry(session, request)
    except DataSubjectError as exc:
        raise to_http_error(exc) from exc
    await session.commit()
    data_subject_erase_worker.notify()
    return request_read(request)


# An export and a search answer a GET and add a row to the audit log, so a paused instance refuses them.
@router.get("/requests/{request_id}/export", dependencies=[Depends(changes_the_instance)])
async def export_request(request_id: UUID, current_user: CurrentActiveUser, session: DbSession):
    """Download what Langflow holds about the subject, while the request is still open."""
    await _require_admin(current_user)
    request = await _load_request(session, request_id)
    if request.status not in {s.value for s in OPEN_STATUSES} or request.status == DataSubjectRequestStatus.ERASING:
        raise to_http_error(InvalidTransitionError("Export is available until the erase starts"))
    if request.subject_type == DataSubjectType.BUILDER.value:
        subject = await _load_builder(session, request.subject_user_id, current_user)
        archive = await export_builder(session, subject, current_user.id)
    else:
        scope = tuple(UUID(v) for v in request.scope_flow_ids or [])
        archive = await export_end_user(session, end_user_keys(request.subject_end_user_id), scope, current_user.id)
    await audit_events.record_dsar_event(
        session,
        actor_id=current_user.id,
        action=audit_events.ACTION_EXPORT,
        request_id=request.id,
        details={"request_id": str(request.id), "subject_type": request.subject_type},
    )
    await session.commit()
    return zip_response(archive, f"data-subject-{request.id}.zip")


@router.get("/end-users", response_model=list[EndUserMatch], dependencies=[Depends(changes_the_instance)])
async def find_end_users(
    current_user: CurrentActiveUser,
    session: DbSession,
    search: Annotated[str, Query(min_length=2, max_length=255)],
    limit: Annotated[int, Query(ge=1, le=MAX_END_USER_MATCHES)] = 20,
) -> list[EndUserMatch]:
    """End-user ids that contain ``search``, so an admin can pick the exact id the app sent."""
    await _require_admin(current_user)
    matches = await search_end_users(session, search, limit)
    await audit_events.record_dsar_event(
        session,
        actor_id=current_user.id,
        action=audit_events.ACTION_FIND,
        request_id=None,
        details={"subject_type": DataSubjectType.END_USER.value},
    )
    return matches


@router.post("/find", response_model=DryRunSummary)
async def find_subject(ref: DataSubjectRef, current_user: CurrentActiveUser, session: DbSession) -> DryRunSummary:
    """Count what Langflow holds about a subject, without creating a request."""
    await _require_admin(current_user)
    try:
        if ref.subject_type == DataSubjectType.BUILDER:
            builder = await _load_builder(session, await _builder_id(session, ref), current_user)
            summary = await builder_dry_run(session, builder)
        else:
            keys = end_user_keys(ref.end_user_id)
            await ensure_not_an_account(session, keys)
            summary = await end_user_dry_run(session, keys, tuple(ref.flow_ids or ()))
    except DataSubjectError as exc:
        raise to_http_error(exc) from exc
    await audit_events.record_dsar_event(
        session,
        actor_id=current_user.id,
        action=audit_events.ACTION_FIND,
        request_id=None,
        details={"subject_type": ref.subject_type.value},
    )
    return summary


@router.post("/erase", response_model=DataSubjectRequestRead, status_code=202)
async def erase_subject(ref: DataSubjectRef, current_user: CurrentActiveUser, session: DbSession):
    """Create and approve in one call, for a customer app that decides on its own."""
    await _require_admin(current_user)
    try:
        request = await request_service.create_and_approve(
            session, _create(session, ref, current_user, _caller_source()), current_user.id
        )
    except DataSubjectError as exc:
        raise to_http_error(exc) from exc
    await session.commit()
    data_subject_erase_worker.notify()
    return request_read(request)
