"""Two sessions deciding the same request: the first decision wins and the second changes nothing."""

import pytest
from langflow.services.data_subjects.errors import InvalidTransitionError
from langflow.services.data_subjects.requests import approve, create_builder_request, refuse, withdraw
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.data_subject_request import (
    DataSubjectRequest,
    DataSubjectRequestSource,
    DataSubjectRequestStatus,
)
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from sqlalchemy import func
from sqlmodel import select

from tests.unit.services.data_subjects._seed import create_user


async def _pending_request(username: str):
    subject = await create_user(username)
    admin = await create_user(f"{username}-admin", superuser=True)
    async with session_scope() as session:
        session.add(ApiKey(name="key", api_key=f"sk-{username}", user_id=subject))
        user = await session.get(User, subject)
        request, _ = await create_builder_request(
            session, subject=user, requested_by=subject, source=DataSubjectRequestSource.SELF
        )
        return request.id, subject, admin


async def _approve_in_own_session(request_id, admin) -> None:
    async with session_scope() as session:
        await approve(session, await session.get(DataSubjectRequest, request_id), admin)


async def _status(request_id) -> str:
    async with session_scope() as session:
        return (await session.get(DataSubjectRequest, request_id)).status


@pytest.mark.usefixtures("client")
async def test_should_refuse_a_stale_withdraw_after_another_session_approved():
    request_id, subject, admin = await _pending_request("race-withdraw")

    async with session_scope() as stale_session:
        stale = await stale_session.get(DataSubjectRequest, request_id)
        await _approve_in_own_session(request_id, admin)
        with pytest.raises(InvalidTransitionError):
            await withdraw(stale_session, stale, subject)

    assert await _status(request_id) == DataSubjectRequestStatus.APPROVED.value


@pytest.mark.usefixtures("client")
async def test_should_refuse_a_stale_refusal_after_another_session_approved():
    request_id, _, admin = await _pending_request("race-refuse")

    async with session_scope() as stale_session:
        stale = await stale_session.get(DataSubjectRequest, request_id)
        await _approve_in_own_session(request_id, admin)
        with pytest.raises(InvalidTransitionError):
            await refuse(stale_session, stale, admin, "legal hold")

    assert await _status(request_id) == DataSubjectRequestStatus.APPROVED.value


@pytest.mark.usefixtures("client")
async def test_should_not_stop_the_account_when_approval_loses_to_a_withdraw():
    request_id, subject, admin = await _pending_request("race-approve")

    async with session_scope() as stale_session:
        stale = await stale_session.get(DataSubjectRequest, request_id)
        async with session_scope() as session:
            await withdraw(session, await session.get(DataSubjectRequest, request_id), subject)
        with pytest.raises(InvalidTransitionError):
            await approve(stale_session, stale, admin)

    assert await _status(request_id) == DataSubjectRequestStatus.WITHDRAWN.value
    async with session_scope() as session:
        assert (await session.get(User, subject)).is_active
        keys = (await session.exec(select(func.count()).select_from(ApiKey).where(ApiKey.user_id == subject))).one()
        assert keys == 1
