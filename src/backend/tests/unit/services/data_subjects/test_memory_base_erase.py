"""A Memory Base's remote collection must be gone before a builder erase can finish."""

from datetime import datetime, timedelta, timezone

import pytest
from langflow.services.data_subjects.engine import run_request
from langflow.services.data_subjects.requests import approve, create_builder_request
from langflow.services.database.models.data_subject_request import (
    DataSubjectRequest,
    DataSubjectRequestSource,
    DataSubjectRequestStatus,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
from langflow.services.database.models.memory_base.model import MemoryBase
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from sqlalchemy import func
from sqlmodel import select

from tests.unit.services.data_subjects._seed import create_user

REMOTE_CONFIG = {"url": "https://vectors.example.com", "index": "mb-remote"}


class _RemoteStore:
    """Stands in for a remote vector store; only an outage cannot be reproduced against a real one."""

    def __init__(self) -> None:
        self.reachable = False
        self.deleted: list[tuple[str, dict]] = []

    def build(self, *, backend_type, kb_name, backend_config, **_kwargs):  # noqa: ARG002
        store = self

        class _Backend:
            async def ensure_ready(self) -> None:
                if not store.reachable:
                    msg = "connection refused"
                    raise ConnectionError(msg)

            async def delete_collection(self) -> None:
                store.deleted.append((kb_name, backend_config))

            async def teardown(self) -> None:
                return None

        return _Backend()


async def _seed_builder_with_remote_memory_base(username: str):
    uid = await create_user(username)
    admin = await create_user(f"{username}-admin", superuser=True)
    async with session_scope() as session:
        flow = Flow(name="support", user_id=uid)
        session.add(flow)
        await session.flush()
        session.add_all(
            [
                MemoryBase(name="memory", kb_name="mb_remote", flow_id=flow.id, user_id=uid),
                KnowledgeBaseRecord(
                    name="mb_remote", user_id=uid, backend_type="opensearch", backend_config=REMOTE_CONFIG
                ),
            ]
        )
        user = await session.get(User, uid)
        request, _ = await create_builder_request(
            session, subject=user, requested_by=admin, source=DataSubjectRequestSource.ADMIN
        )
        await approve(session, request, admin)
        return request.id, uid


async def _make_retry_due(request_id) -> None:
    async with session_scope() as session:
        request = await session.get(DataSubjectRequest, request_id)
        past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        request.error = {**(request.error or {}), "retry_at": past}
        session.add(request)


@pytest.mark.usefixtures("client")
async def test_should_keep_the_request_open_until_the_remote_collection_is_deleted(monkeypatch):
    store = _RemoteStore()
    monkeypatch.setattr("langflow.services.knowledge_base_storage.runtime.create_backend", store.build)
    request_id, uid = await _seed_builder_with_remote_memory_base("mb-outage")

    first = await run_request(request_id)

    assert first == DataSubjectRequestStatus.ERASING.value
    async with session_scope() as session:
        request = await session.get(DataSubjectRequest, request_id)
        assert request.error is not None
        pending = [item for item in request.pending_paths if item["kind"] == "memory_base"]
        assert pending == [
            {
                "kind": "memory_base",
                "value": "mb_remote",
                "user_id": str(uid),
                "kb_username": "mb-outage",
                "backend_type": "opensearch",
                "backend_config": REMOTE_CONFIG,
            }
        ]
        assert (await session.exec(select(func.count()).select_from(MemoryBase))).one() == 0

    store.reachable = True
    await _make_retry_due(request_id)
    second = await run_request(request_id)

    assert second == DataSubjectRequestStatus.DONE.value
    assert store.deleted == [("mb_remote", REMOTE_CONFIG)]
    async with session_scope() as session:
        assert await session.get(User, uid) is None
