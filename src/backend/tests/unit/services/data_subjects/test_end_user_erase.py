from datetime import datetime, timezone
from uuid import uuid4

import pytest
from langflow.services.data_subjects.dry_run import end_user_dry_run
from langflow.services.data_subjects.engine import run_request
from langflow.services.data_subjects.errors import InvalidEndUserIdError
from langflow.services.data_subjects.identity import end_user_keys
from langflow.services.data_subjects.requests import approve, create_end_user_request
from langflow.services.database.models.data_subject_request import (
    DataSubjectRequest,
    DataSubjectRequestSource,
    DataSubjectRequestStatus,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import Job, JobStatus
from langflow.services.database.models.memory_base.model import MemoryBase, MemoryBaseSession
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.traces.model import SpanStatus, TraceTable
from langflow.services.database.models.vertex_builds.model import VertexBuildTable
from langflow.services.deps import session_scope
from lfx.memory.flow_context import derive_message_owner_uuid
from lfx.services.authorization.base import PUBLIC_ANONYMOUS_ACTOR_ID
from sqlalchemy import func
from sqlmodel import col, select

from tests.unit.services.data_subjects._seed import create_user, end_user_message


def _now():
    return datetime.now(timezone.utc)


async def _seed_end_users() -> tuple:
    owner = await create_user("serving-owner")
    async with session_scope() as session:
        flow = Flow(name="assistant", user_id=owner)
        other_flow = Flow(name="other-assistant", user_id=owner)
        session.add_all([flow, other_flow])
        await session.flush()
        memory = MemoryBase(name="memory", flow_id=flow.id, user_id=owner, created_at=_now())
        session.add(memory)
        await session.flush()
        rows = []
        for end_user in ("alice", "bob"):
            job = Job(
                job_id=uuid4(),
                flow_id=flow.id,
                status=JobStatus.COMPLETED,
                created_timestamp=_now(),
                user_id=owner,
                job_metadata={"end_user_id": end_user},
            )
            rows += [
                end_user_message(flow.id, end_user, f"{end_user}@example.com"),
                TraceTable(name="run", status=SpanStatus.OK, flow_id=flow.id, session_id=f"{end_user}::s1"),
                job,
                VertexBuildTable(id="v", valid=True, flow_id=flow.id, job_id=job.job_id, data={"t": end_user}),
                MemoryBaseSession(session_id=f"{end_user}::s1", memory_base_id=memory.id),
            ]
        rows.append(end_user_message(other_flow.id, "alice", "alice in another flow"))
        session.add_all(rows)
        return owner, flow.id, other_flow.id


async def _messages_of(session, end_user: str, flow_id=None) -> int:
    where = [MessageTable.user_id == derive_message_owner_uuid(end_user)]
    if flow_id is not None:
        where.append(MessageTable.flow_id == flow_id)
    return (await session.exec(select(func.count()).select_from(MessageTable).where(*where))).one()


async def _erase(end_user: str, admin_id, flow_ids=None):
    async with session_scope() as session:
        request, _ = await create_end_user_request(
            session,
            end_user_id=end_user,
            scope_flow_ids=flow_ids,
            requested_by=admin_id,
            source=DataSubjectRequestSource.API,
        )
        await approve(session, request, admin_id)
        request_id = request.id
    return request_id, await run_request(request_id)


@pytest.mark.usefixtures("client")
async def test_should_erase_only_that_end_user_when_others_share_the_flow():
    admin = await create_user("dsr-eu-admin", superuser=True)
    _, flow_id, other_flow_id = await _seed_end_users()

    request_id, status = await _erase("alice", admin)

    assert status == DataSubjectRequestStatus.DONE.value
    async with session_scope() as session:
        assert await _messages_of(session, "alice") == 0
        assert await _messages_of(session, "bob") == 1
        traces = (await session.exec(select(TraceTable.session_id).where(TraceTable.flow_id == flow_id))).all()
        assert traces == ["bob::s1"]
        jobs = (await session.exec(select(Job.job_metadata).where(Job.flow_id == flow_id))).all()
        assert [meta["end_user_id"] for meta in jobs] == ["bob"]
        builds = (await session.exec(select(VertexBuildTable.data).where(VertexBuildTable.flow_id == flow_id))).all()
        assert [data["t"] for data in builds] == ["bob"]
        memory_sessions = (await session.exec(select(MemoryBaseSession.session_id))).all()
        assert memory_sessions == ["bob::s1"]
        assert await session.get(Flow, flow_id) is not None
        assert await session.get(Flow, other_flow_id) is not None
        request = await session.get(DataSubjectRequest, request_id)
        assert request.subject_end_user_id is None
        assert request.subject_label == "alice"


@pytest.mark.usefixtures("client")
async def test_should_leave_other_flows_alone_when_scope_is_given():
    admin = await create_user("dsr-eu-admin-2", superuser=True)
    _, flow_id, other_flow_id = await _seed_end_users()

    _, status = await _erase("alice", admin, flow_ids=[flow_id])

    assert status == DataSubjectRequestStatus.DONE.value
    async with session_scope() as session:
        assert await _messages_of(session, "alice", flow_id) == 0
        assert await _messages_of(session, "alice", other_flow_id) == 1


@pytest.mark.usefixtures("client")
async def test_should_count_what_would_be_erased_without_changing_anything():
    await _seed_end_users()

    async with session_scope() as session:
        summary = await end_user_dry_run(session, end_user_keys("alice"), ())
        messages_after = await _messages_of(session, "alice")

    assert summary.counts == {"messages": 2, "traces": 1, "transactions": 0, "runs": 1, "flows": 2}
    assert messages_after == 2


@pytest.mark.parametrize(
    "end_user_id",
    ["a::b", "", "   ", "anon", "x" * 256],
)
@pytest.mark.usefixtures("client")
async def test_should_refuse_ambiguous_end_user_ids(end_user_id):
    async with session_scope() as session:
        with pytest.raises(InvalidEndUserIdError):
            await create_end_user_request(
                session,
                end_user_id=end_user_id,
                scope_flow_ids=None,
                requested_by=None,
                source=DataSubjectRequestSource.API,
            )


@pytest.mark.usefixtures("client")
async def test_should_refuse_an_end_user_id_that_is_an_account_id():
    account = await create_user("collides")

    async with session_scope() as session:
        with pytest.raises(InvalidEndUserIdError, match="existing account"):
            await create_end_user_request(
                session,
                end_user_id=str(account),
                scope_flow_ids=None,
                requested_by=None,
                source=DataSubjectRequestSource.API,
            )
        with pytest.raises(InvalidEndUserIdError, match="public principal"):
            await create_end_user_request(
                session,
                end_user_id=str(PUBLIC_ANONYMOUS_ACTOR_ID),
                scope_flow_ids=None,
                requested_by=None,
                source=DataSubjectRequestSource.API,
            )
        assert (await session.exec(select(func.count()).select_from(DataSubjectRequest))).one() == 0


@pytest.mark.usefixtures("client")
async def test_should_not_match_other_users_when_the_id_contains_like_wildcards():
    admin = await create_user("dsr-eu-admin-3", superuser=True)
    owner = await create_user("wildcard-owner")
    async with session_scope() as session:
        flow = Flow(name="wild", user_id=owner)
        session.add(flow)
        await session.flush()
        session.add_all(
            [
                end_user_message(flow.id, "a_c", "underscore user"),
                end_user_message(flow.id, "abc", "should survive"),
                end_user_message(flow.id, "a%", "percent user"),
                end_user_message(flow.id, "a%z", "should survive too"),
            ]
        )

    await _erase("a_c", admin)
    await _erase("a%", admin)

    async with session_scope() as session:
        texts = sorted((await session.exec(select(MessageTable.text).where(col(MessageTable.text).is_not(None)))).all())
        assert "should survive" in texts
        assert "should survive too" in texts
        assert "underscore user" not in texts
        assert "percent user" not in texts
