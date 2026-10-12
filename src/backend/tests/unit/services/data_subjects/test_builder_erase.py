from uuid import uuid4

import pytest
from langflow.services.data_subjects.engine import run_request
from langflow.services.data_subjects.errors import InvalidTransitionError, LastAdministratorError
from langflow.services.data_subjects.requests import approve, create_builder_request, refuse, withdraw
from langflow.services.database.models.a2a.model import A2ATask
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.auth.authz import AuthzAccessException, AuthzAuditLog, AuthzShare
from langflow.services.database.models.data_subject_request import (
    DataSubjectRequest,
    DataSubjectRequestSource,
    DataSubjectRequestStatus,
)
from langflow.services.database.models.file.model import File
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.jobs.model import Job, JobEvent
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.traces.model import SpanTable, TraceTable
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.user.model import User
from langflow.services.database.models.variable.model import Variable
from langflow.services.database.models.vertex_builds.model import VertexBuildTable
from langflow.services.deps import session_scope
from sqlalchemy import func
from sqlmodel import col, select

from tests.unit.services.data_subjects._seed import create_user, seed_builder


async def _count(session, model, *where) -> int:
    return (await session.exec(select(func.count()).select_from(model).where(*where))).one()


async def _request_and_approve(subject_id, admin_id):
    async with session_scope() as session:
        user = await session.get(User, subject_id)
        request, created = await create_builder_request(
            session, subject=user, requested_by=admin_id, source=DataSubjectRequestSource.ADMIN
        )
        assert created
        await approve(session, request, admin_id)
        return request.id


@pytest.mark.usefixtures("client")
async def test_should_leave_no_rows_or_files_when_builder_erase_completes():
    seeded = await seed_builder()
    admin_id = await create_user("dsr-admin", superuser=True)

    request_id = await _request_and_approve(seeded.user_id, admin_id)
    status = await run_request(request_id)

    assert status == DataSubjectRequestStatus.DONE.value
    uid, flow_id = seeded.user_id, seeded.flow_id
    async with session_scope() as session:
        assert await session.get(User, uid) is None
        leftovers = {
            "flows": await _count(session, Flow, Flow.user_id == uid),
            "folders": await _count(session, Folder, Folder.user_id == uid),
            "messages_in_flow": await _count(session, MessageTable, MessageTable.flow_id == flow_id),
            "messages_by_user": await _count(session, MessageTable, MessageTable.user_id == uid),
            "transactions": await _count(session, TransactionTable, TransactionTable.flow_id == flow_id),
            "vertex_builds": await _count(session, VertexBuildTable, VertexBuildTable.flow_id == flow_id),
            "traces": await _count(session, TraceTable, TraceTable.flow_id == flow_id),
            "spans": await _count(session, SpanTable),
            "jobs": await _count(session, Job, Job.flow_id == flow_id),
            "job_events": await _count(session, JobEvent),
            "a2a": await _count(session, A2ATask, col(A2ATask.owner).startswith(f"{flow_id}:")),
            "variables": await _count(session, Variable, Variable.user_id == uid),
            "api_keys": await _count(session, ApiKey, ApiKey.user_id == uid),
            "files": await _count(session, File, File.user_id == uid),
            "shares": await _count(
                session, AuthzShare, (AuthzShare.target_id == uid) | (AuthzShare.resource_id == flow_id)
            ),
        }
        assert leftovers == dict.fromkeys(leftovers, 0)
        assert await _count(session, Flow, Flow.id == seeded.colleague_flow_id) == 1
        assert await _count(session, MessageTable, MessageTable.user_id == seeded.colleague_id) == 1
    assert not seeded.file_path.exists()


@pytest.mark.usefixtures("client")
async def test_should_delete_access_exceptions_naming_the_builder_and_keep_ones_they_created():
    seeded = await seed_builder()
    admin_id = await create_user("dsr-admin", superuser=True)
    async with session_scope() as session:
        naming_builder = AuthzAccessException(
            user_id=seeded.user_id,
            resource_type="flow",
            resource_id=seeded.colleague_flow_id,
            created_by=seeded.colleague_id,
        )
        created_by_builder = AuthzAccessException(
            user_id=seeded.colleague_id,
            resource_type="flow",
            resource_id=seeded.colleague_flow_id,
            created_by=seeded.user_id,
        )
        session.add_all([naming_builder, created_by_builder])
        await session.commit()
        naming_id, created_id = naming_builder.id, created_by_builder.id

    status = await run_request(await _request_and_approve(seeded.user_id, admin_id))

    assert status == DataSubjectRequestStatus.DONE.value
    async with session_scope() as session:
        assert await session.get(AuthzAccessException, naming_id) is None
        kept = await session.get(AuthzAccessException, created_id)
        assert kept is not None
        assert kept.user_id == seeded.colleague_id
        assert kept.created_by is None
        assert await _count(session, AuthzAccessException, AuthzAccessException.user_id == seeded.user_id) == 0


@pytest.mark.usefixtures("client")
async def test_should_redact_audit_rows_and_record_dsar_events_when_builder_is_erased():
    seeded = await seed_builder("joana")
    admin_id = await create_user("dsr-admin-2", superuser=True)

    request_id = await _request_and_approve(seeded.user_id, admin_id)
    await run_request(request_id)

    async with session_scope() as session:
        rows = (await session.exec(select(AuthzAuditLog).where(AuthzAuditLog.actor_id == seeded.user_id))).all()
        assert rows
        for row in rows:
            assert row.user_id is None
            assert "username" not in (row.details or {})
            assert "client_ip" not in (row.details or {})
        actions = set(
            (await session.exec(select(AuthzAuditLog.action).where(AuthzAuditLog.resource_id == request_id))).all()
        )
        assert {"dsar:request", "dsar:approve", "dsar:erase"} <= actions
        request = await session.get(DataSubjectRequest, request_id)
        assert request.subject_label is not None
        assert request.pending_paths is None
        assert request.counts["flows"] >= 1


@pytest.mark.usefixtures("client")
async def test_should_resume_and_finish_when_a_step_fails_once(monkeypatch):
    seeded = await seed_builder("pedro-b")
    admin_id = await create_user("dsr-admin-3", superuser=True)
    request_id = await _request_and_approve(seeded.user_id, admin_id)
    from langflow.services.data_subjects import engine

    calls = {"n": 0}
    original = engine.run_storage_item

    async def _flaky(item):
        calls["n"] += 1
        if calls["n"] == 1:
            msg = "storage briefly unavailable"
            raise OSError(msg)
        await original(item)

    monkeypatch.setattr(engine, "run_storage_item", _flaky)

    first = await run_request(request_id)
    async with session_scope() as session:
        request = await session.get(DataSubjectRequest, request_id)
        assert first == DataSubjectRequestStatus.ERASING.value
        assert request.error["code"] == "OSError"
        assert "storage briefly" not in str(request.error)
        request.error = {**request.error, "retry_at": None}
        session.add(request)

    second = await run_request(request_id)

    assert second == DataSubjectRequestStatus.DONE.value
    async with session_scope() as session:
        assert await session.get(User, seeded.user_id) is None


@pytest.mark.usefixtures("client")
async def test_should_refuse_to_erase_the_last_active_superuser():
    async with session_scope() as session:
        for user in (await session.exec(select(User).where(col(User.is_superuser).is_(True)))).all():
            user.is_active = False
            session.add(user)
    lone_admin = await create_user("lone-admin", superuser=True)

    async with session_scope() as session:
        user = await session.get(User, lone_admin)
        request, _ = await create_builder_request(
            session, subject=user, requested_by=lone_admin, source=DataSubjectRequestSource.SELF
        )
        with pytest.raises(LastAdministratorError):
            await approve(session, request, uuid4())


@pytest.mark.usefixtures("client")
async def test_should_reuse_the_open_request_when_the_same_builder_asks_twice():
    uid = await create_user("twice")
    async with session_scope() as session:
        user = await session.get(User, uid)
        first, created_first = await create_builder_request(
            session, subject=user, requested_by=uid, source=DataSubjectRequestSource.SELF
        )
        second, created_second = await create_builder_request(
            session, subject=user, requested_by=uid, source=DataSubjectRequestSource.SELF
        )

    assert (created_first, created_second) == (True, False)
    assert first.id == second.id


@pytest.mark.usefixtures("client")
async def test_should_only_let_the_requester_withdraw_a_pending_request():
    uid = await create_user("withdrawer")
    other = await create_user("someone-else")
    async with session_scope() as session:
        user = await session.get(User, uid)
        request, _ = await create_builder_request(
            session, subject=user, requested_by=uid, source=DataSubjectRequestSource.SELF
        )
        with pytest.raises(InvalidTransitionError):
            await withdraw(session, request, other)
        await withdraw(session, request, uid)

        assert request.status == DataSubjectRequestStatus.WITHDRAWN.value
        assert request.subject_label is not None
        with pytest.raises(InvalidTransitionError):
            await refuse(session, request, other, "too late")
