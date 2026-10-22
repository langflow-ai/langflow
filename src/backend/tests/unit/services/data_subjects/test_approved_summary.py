"""An erased request reports what the administrator approved, in the units of the dry-run they saw."""

from uuid import uuid4

import pytest
from langflow.services.data_subjects.engine import run_request
from langflow.services.data_subjects.requests import approve, create_builder_request, create_end_user_request
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.data_subject_request import DataSubjectRequest, DataSubjectRequestSource
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope

from tests.unit.services.data_subjects._seed import create_user, end_user_message


async def _counts(request_id) -> dict:
    async with session_scope() as session:
        return (await session.get(DataSubjectRequest, request_id)).counts


@pytest.mark.usefixtures("client")
async def test_should_keep_the_builders_approved_dry_run_after_the_erase():
    admin = await create_user(f"dsr-admin-{uuid4().hex[:8]}", superuser=True)
    builder = await create_user(f"builder-{uuid4().hex[:8]}")
    async with session_scope() as session:
        folder = Folder(name="project", user_id=builder)
        session.add(folder)
        await session.flush()
        session.add_all(
            [
                Flow(name="one", user_id=builder, folder_id=folder.id),
                Flow(name="two", user_id=builder, folder_id=folder.id),
                ApiKey(name="key", api_key=f"sk-{uuid4().hex}", user_id=builder),
            ]
        )

    async with session_scope() as session:
        subject = await session.get(User, builder)
        request, _ = await create_builder_request(
            session, subject=subject, requested_by=admin, source=DataSubjectRequestSource.ADMIN
        )
        await approve(session, request, admin)
        request_id = request.id
    assert await run_request(request_id) == "done"

    approved = (await _counts(request_id))["approved"]
    assert approved["flows"] == 2
    assert approved["projects"] == 1
    assert approved["api_keys"] == 1


@pytest.mark.usefixtures("client")
async def test_should_keep_the_end_users_approved_dry_run_after_the_erase():
    admin = await create_user(f"dsr-admin-{uuid4().hex[:8]}", superuser=True)
    owner = await create_user(f"owner-{uuid4().hex[:8]}")
    async with session_scope() as session:
        flow = Flow(name="assistant", user_id=owner)
        session.add(flow)
        await session.flush()
        session.add_all([end_user_message(flow.id, "carol", "hi"), end_user_message(flow.id, "carol", "again")])

    async with session_scope() as session:
        request, _ = await create_end_user_request(
            session, end_user_id="carol", scope_flow_ids=None, requested_by=admin, source=DataSubjectRequestSource.API
        )
        await approve(session, request, admin)
        request_id = request.id
    assert await run_request(request_id) == "done"

    assert (await _counts(request_id))["approved"] == {
        "messages": 2,
        "traces": 0,
        "transactions": 0,
        "runs": 0,
        "flows": 1,
    }
