"""Transaction rows hold a run's inputs and outputs, so an erase must reach the subject's own runs."""

import io
import json
import zipfile
from uuid import uuid4

import pytest
from langflow.services.data_subjects.dry_run import end_user_dry_run
from langflow.services.data_subjects.engine import run_request
from langflow.services.data_subjects.export import export_end_user
from langflow.services.data_subjects.identity import end_user_keys
from langflow.services.data_subjects.requests import approve, create_builder_request, create_end_user_request
from langflow.services.database.models.data_subject_request import DataSubjectRequest, DataSubjectRequestSource
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from lfx.memory.flow_context import derive_message_owner_uuid
from sqlmodel import select

from tests.unit.services.data_subjects._seed import create_user


def _run_row(flow_id, vertex_id: str, text: str, *, user_id=None, session_id=None, input_session=None):
    inputs = {"input_value": text}
    if input_session is not None:
        inputs["session_id"] = input_session
    return TransactionTable(
        vertex_id=vertex_id,
        status="success",
        flow_id=flow_id,
        inputs=inputs,
        outputs={"message": text},
        user_id=user_id,
        session_id=session_id,
    )


async def _remaining_texts(flow_id) -> list[str]:
    async with session_scope() as session:
        rows = (await session.exec(select(TransactionTable).where(TransactionTable.flow_id == flow_id))).all()
        return sorted(row.inputs["input_value"] for row in rows)


async def _seed_serving_flow() -> tuple:
    owner = await create_user(f"serving-{uuid4().hex[:8]}")
    async with session_scope() as session:
        flow = Flow(name="assistant", user_id=owner)
        session.add(flow)
        await session.flush()
        alice, bob = derive_message_owner_uuid("alice"), derive_message_owner_uuid("bob")
        session.add_all(
            [
                _run_row(flow.id, "ChatInput", "alice chat", user_id=alice, session_id="alice::s1"),
                _run_row(flow.id, "OpenAIModel", "alice llm", user_id=alice, session_id="alice::s1"),
                _run_row(flow.id, "ChatInput", "alice legacy", input_session="alice::s0"),
                _run_row(flow.id, "ChatInput", "bob chat", user_id=bob, session_id="bob::s1"),
                _run_row(flow.id, "ChatInput", "bob legacy", input_session="bob::s0"),
                _run_row(flow.id, "Prompt", "playground", user_id=owner, session_id=str(flow.id)),
            ]
        )
        return owner, flow.id


@pytest.mark.usefixtures("client")
async def test_should_erase_the_end_users_transactions_and_keep_everyone_elses():
    admin = await create_user(f"dsr-admin-{uuid4().hex[:8]}", superuser=True)
    _, flow_id = await _seed_serving_flow()

    async with session_scope() as session:
        request, _ = await create_end_user_request(
            session, end_user_id="alice", scope_flow_ids=None, requested_by=admin, source=DataSubjectRequestSource.API
        )
        await approve(session, request, admin)
        request_id = request.id
    status = await run_request(request_id)

    assert status == "done"
    async with session_scope() as session:
        assert (await session.get(DataSubjectRequest, request_id)).counts["transactions"] == 3
    assert await _remaining_texts(flow_id) == ["bob chat", "bob legacy", "playground"]


@pytest.mark.usefixtures("client")
async def test_should_count_and_export_the_end_users_transactions():
    _, flow_id = await _seed_serving_flow()
    keys = end_user_keys("alice")

    async with session_scope() as session:
        summary = await end_user_dry_run(session, keys, ())
        exported = await export_end_user(session, keys, (), None)

    assert summary.counts["transactions"] == 3
    exported.seek(0)
    rows = json.loads(zipfile.ZipFile(io.BytesIO(exported.read())).read("transactions.json"))
    assert sorted(row["inputs"]["input_value"] for row in rows) == ["alice chat", "alice legacy", "alice llm"]
    assert await _remaining_texts(flow_id) != []


@pytest.mark.usefixtures("client")
async def test_should_erase_a_builders_runs_in_a_colleagues_flow():
    admin = await create_user(f"dsr-admin-{uuid4().hex[:8]}", superuser=True)
    builder = await create_user(f"builder-{uuid4().hex[:8]}")
    colleague, flow_id = await _seed_serving_flow()
    async with session_scope() as session:
        session.add(_run_row(flow_id, "ChatInput", "builder in shared flow", user_id=builder, session_id=str(flow_id)))

    async with session_scope() as session:
        subject = await session.get(User, builder)
        request, _ = await create_builder_request(
            session, subject=subject, requested_by=admin, source=DataSubjectRequestSource.ADMIN
        )
        await approve(session, request, admin)
        request_id = request.id
    status = await run_request(request_id)

    assert status == "done"
    remaining = await _remaining_texts(flow_id)
    assert "builder in shared flow" not in remaining
    assert "playground" in remaining
    assert colleague != builder
