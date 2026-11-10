from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.data_subjects.engine import run_request
from langflow.services.data_subjects.expiry import AUTO_APPROVAL_BLOCKED, EXPIRY_BATCH, approve_expired_requests
from langflow.services.data_subjects.requests import create_builder_request
from langflow.services.database.models.auth.authz import AuthzAuditLog
from langflow.services.database.models.data_subject_request import (
    DataSubjectRequest,
    DataSubjectRequestSource,
    DataSubjectRequestStatus,
)
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service, session_scope
from lfx.services.settings.feature_flags import FEATURE_FLAGS
from sqlmodel import col, select

from tests.unit.services.data_subjects._seed import create_user


def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
def feature_on(monkeypatch):
    monkeypatch.setattr(FEATURE_FLAGS, "data_subject_requests", True)


@pytest.fixture
def auto_erase_on(monkeypatch, feature_on):  # noqa: ARG001 - the flag must be on too
    monkeypatch.setattr(get_settings_service().settings, "data_subject_auto_erase_on_expiry", True)


async def _builder_request(username: str, *, overdue_by: timedelta | None = None, superuser: bool = False):
    uid = await create_user(username, superuser=superuser)
    async with session_scope() as session:
        user = await session.get(User, uid)
        request, _ = await create_builder_request(
            session, subject=user, requested_by=uid, source=DataSubjectRequestSource.SELF
        )
        if overdue_by is not None:
            request.due_at = _now() - overdue_by
            session.add(request)
        return request.id, uid


async def _status(request_id) -> str:
    async with session_scope() as session:
        return (await session.get(DataSubjectRequest, request_id)).status


@pytest.mark.usefixtures("client")
async def test_should_set_the_due_date_from_the_response_days_setting(monkeypatch):
    monkeypatch.setattr(get_settings_service().settings, "data_subject_response_days", 10)

    request_id, _ = await _builder_request("ten-days")

    async with session_scope() as session:
        request = await session.get(DataSubjectRequest, request_id)
    due_at = request.due_at if request.due_at.tzinfo else request.due_at.replace(tzinfo=timezone.utc)
    assert timedelta(days=9, hours=23) < due_at - _now() <= timedelta(days=10)


@pytest.mark.usefixtures("client")
def test_should_default_to_thirty_days_without_auto_erase():
    settings = get_settings_service().settings

    assert settings.data_subject_response_days == 30
    assert settings.data_subject_auto_erase_on_expiry is False


@pytest.mark.usefixtures("client", "feature_on")
async def test_should_leave_overdue_requests_alone_when_auto_erase_is_off():
    request_id, _ = await _builder_request("overdue-manual", overdue_by=timedelta(days=1))

    approved = await approve_expired_requests()

    assert approved == 0
    assert await _status(request_id) == DataSubjectRequestStatus.REQUESTED.value


@pytest.mark.usefixtures("client")
async def test_should_leave_overdue_requests_alone_when_the_feature_is_off(monkeypatch):
    monkeypatch.setattr(get_settings_service().settings, "data_subject_auto_erase_on_expiry", True)
    request_id, _ = await _builder_request("overdue-flag-off", overdue_by=timedelta(days=1))

    approved = await approve_expired_requests()

    assert approved == 0
    assert await _status(request_id) == DataSubjectRequestStatus.REQUESTED.value


@pytest.mark.usefixtures("client", "auto_erase_on")
async def test_should_approve_and_erase_overdue_requests_when_auto_erase_is_on():
    overdue_id, overdue_user = await _builder_request("overdue-auto", overdue_by=timedelta(minutes=1))
    pending_id, _ = await _builder_request("not-yet-due")

    approved = await approve_expired_requests()
    status = await run_request(overdue_id)

    assert approved == 1
    assert status == DataSubjectRequestStatus.DONE.value
    assert await _status(pending_id) == DataSubjectRequestStatus.REQUESTED.value
    async with session_scope() as session:
        request = await session.get(DataSubjectRequest, overdue_id)
        assert request.decided_by is None
        assert await session.get(User, overdue_user) is None
        approvals = (
            await session.exec(select(AuthzAuditLog.details).where(col(AuthzAuditLog.action) == "dsar:approve"))
        ).all()
        assert any(d.get("request_id") == str(overdue_id) and d.get("automatic") is True for d in approvals)


@pytest.mark.usefixtures("client", "auto_erase_on")
async def test_should_keep_a_blocked_request_open_and_not_retry_it():
    async with session_scope() as session:
        for user in (await session.exec(select(User).where(col(User.is_superuser).is_(True)))).all():
            user.is_active = False
            session.add(user)
    request_id, _ = await _builder_request("lone-overdue-admin", overdue_by=timedelta(days=1), superuser=True)

    first = await approve_expired_requests()
    second = await approve_expired_requests()

    assert (first, second) == (0, 0)
    async with session_scope() as session:
        request = await session.get(DataSubjectRequest, request_id)
        assert request.status == DataSubjectRequestStatus.REQUESTED.value
        assert request.error["code"] == "last_administrator"


@pytest.mark.usefixtures("client", "auto_erase_on")
async def test_should_approve_an_overdue_request_behind_a_full_batch_of_blocked_requests():
    now = _now()
    async with session_scope() as session:
        session.add_all(
            DataSubjectRequest(
                subject_type="builder",
                subject_user_id=uuid4(),
                source="self",
                due_at=now - timedelta(days=2),
                error={AUTO_APPROVAL_BLOCKED: True, "code": "protected_account"},
            )
            for _ in range(EXPIRY_BATCH)
        )
    request_id, _ = await _builder_request("overdue-after-blocked", overdue_by=timedelta(days=1))

    assert await approve_expired_requests(now) == 1
    assert await _status(request_id) == DataSubjectRequestStatus.APPROVED.value
