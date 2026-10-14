"""Self-service routes: a builder asks for their account to be deleted, withdraws, or exports their data.

Nothing here deletes anything; an administrator approves every request.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlmodel import col, select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.utils.migration_pause import changes_the_instance
from langflow.api.v1.data_subjects_common import require_data_subject_feature, to_http_error, zip_response
from langflow.services.auth.context import AUTH_METHOD_API_KEY, AUTH_METHOD_AUTO_LOGIN, get_current_auth_context
from langflow.services.data_subjects import audit_events
from langflow.services.data_subjects import requests as request_service
from langflow.services.data_subjects.errors import DataSubjectError
from langflow.services.data_subjects.export import export_builder
from langflow.services.data_subjects.schemas import OwnDeletionRequestStatus
from langflow.services.data_subjects.stop import ensure_not_last_administrator
from langflow.services.database.models.data_subject_request import (
    OPEN_STATUSES,
    DataSubjectRequest,
    DataSubjectRequestSource,
    DataSubjectType,
)
from langflow.services.rate_limit.service import check_rate_limit, get_user_limiter_key

router = APIRouter(
    prefix="/users/me",
    tags=["Data Subjects"],
    dependencies=[Depends(require_data_subject_feature)],
)
REQUESTS_PER_HOUR = 10
EXPORTS_PER_HOUR = 5


def _require_interactive_login(current_user: CurrentActiveUser) -> None:  # noqa: ARG001 - resolves auth first
    """Only a signed-in person may ask; an API key or AUTO_LOGIN session is not that person."""
    context = get_current_auth_context()
    if context is None or context.method in {AUTH_METHOD_API_KEY, AUTH_METHOD_AUTO_LOGIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sign in interactively to manage your own data",
            headers={"X-Langflow-Error-Code": "interactive_login_required"},
        )


InteractiveLogin = Annotated[None, Depends(_require_interactive_login)]


async def _latest_own_request(session, user_id) -> DataSubjectRequest | None:
    return (
        await session.exec(
            select(DataSubjectRequest)
            .where(
                DataSubjectRequest.subject_user_id == user_id,
                DataSubjectRequest.subject_type == DataSubjectType.BUILDER.value,
            )
            .order_by(col(DataSubjectRequest.requested_at).desc())
            .limit(1)
        )
    ).first()


def _own_status(request: DataSubjectRequest) -> OwnDeletionRequestStatus:
    return OwnDeletionRequestStatus(
        id=request.id, status=request.status, requested_at=request.requested_at, decided_at=request.decided_at
    )


@router.get("/deletion-request", response_model=OwnDeletionRequestStatus)
async def get_own_deletion_request(current_user: CurrentActiveUser, session: DbSession) -> OwnDeletionRequestStatus:
    request = await _latest_own_request(session, current_user.id)
    if request is None:
        raise HTTPException(status_code=404, detail="No deletion request")
    return _own_status(request)


@router.post("/deletion-request", response_model=OwnDeletionRequestStatus)
async def request_own_deletion(
    http_request: Request,
    current_user: CurrentActiveUser,
    session: DbSession,
    response: Response,
    _: InteractiveLogin,
) -> OwnDeletionRequestStatus:
    check_rate_limit(
        http_request,
        scope="dsr-self-request",
        limit_per_hour=REQUESTS_PER_HOUR,
        key=get_user_limiter_key(current_user.id),
    )
    try:
        await ensure_not_last_administrator(session, current_user)
    except DataSubjectError as exc:
        raise to_http_error(exc) from exc
    request, created = await request_service.create_builder_request(
        session, subject=current_user, requested_by=current_user.id, source=DataSubjectRequestSource.SELF
    )
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return _own_status(request)


@router.delete("/deletion-request", response_model=OwnDeletionRequestStatus)
async def withdraw_own_deletion(
    current_user: CurrentActiveUser, session: DbSession, _: InteractiveLogin
) -> OwnDeletionRequestStatus:
    request = await _latest_own_request(session, current_user.id)
    if request is None or request.status not in {s.value for s in OPEN_STATUSES}:
        raise HTTPException(status_code=404, detail="No pending deletion request")
    try:
        await request_service.withdraw(session, request, current_user.id)
    except DataSubjectError as exc:
        raise to_http_error(exc) from exc
    return _own_status(request)


# The export answers a GET and adds a row to the audit log, so a paused instance refuses it.
@router.get("/data-export", dependencies=[Depends(changes_the_instance)])
async def export_own_data(
    http_request: Request, current_user: CurrentActiveUser, session: DbSession, _: InteractiveLogin
):
    check_rate_limit(
        http_request,
        scope="dsr-self-export",
        limit_per_hour=EXPORTS_PER_HOUR,
        key=get_user_limiter_key(current_user.id),
    )
    archive = await export_builder(session, current_user, current_user.id)
    await audit_events.record_dsar_event(
        session,
        actor_id=current_user.id,
        action=audit_events.ACTION_EXPORT,
        request_id=None,
        details={"subject_type": DataSubjectType.BUILDER.value, "source": DataSubjectRequestSource.SELF.value},
    )
    await session.commit()
    return zip_response(archive, "my-langflow-data.zip")
