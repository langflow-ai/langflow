"""Memory Base ingestion cannot claim public execution history through a legacy Flow."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from langflow.api.utils.flow_utils import compute_virtual_flow_id
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.memory_base.model import MemoryBase, MemoryBaseCreate
from langflow.services.database.models.message.crud import get_message_for_user
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.user.model import User
from langflow.services.memory_base.provider_scope import (
    MemoryBaseFlowNotFoundError,
    resolve_memory_provider_scope,
)
from langflow.services.memory_base.service import MemoryBaseService
from langflow.services.memory_base.task import IngestionRequest, _fetch_pending_messages, ingest_memory_task


@pytest.fixture
async def memory_history(async_session, monkeypatch, request):
    owner = User(username="memory-owner", password=uuid4().hex, is_active=True)
    victim = User(username="history-owner", password=uuid4().hex, is_active=True)
    async_session.add_all([owner, victim])
    await async_session.flush()
    flow_id = compute_virtual_flow_id(uuid4(), victim.id, principal_type="user") if request.param else uuid4()
    flow = Flow(id=flow_id, user_id=owner.id, name="Legacy imported flow", data={})
    memory_base = MemoryBase(name="Legacy memory", flow_id=flow_id, user_id=owner.id, kb_name="legacy_memory")
    message = MessageTable(
        flow_id=flow_id,
        user_id=victim.id if request.param else owner.id,
        session_id="known-session",
        sender="AI",
        sender_name="AI",
        text="private history",
        properties={},
        category="message",
        error=False,
    )
    async_session.add_all([flow, memory_base, message])
    await async_session.commit()

    @asynccontextmanager
    async def scope():
        yield async_session

    monkeypatch.setattr("langflow.services.memory_base.service.session_scope", scope)
    monkeypatch.setattr("langflow.services.memory_base.task.session_scope", scope)
    return owner, memory_base, message


@pytest.mark.parametrize("memory_history", [True], indirect=True)
async def test_memory_base_creation_rejects_reserved_flow_before_provider_access(memory_history, monkeypatch):
    owner, memory_base, _ = memory_history
    provider_access = AsyncMock(side_effect=AssertionError("Reserved flow reached provider configuration"))
    monkeypatch.setattr(
        "langflow.services.memory_base.service._preflight_memory_provider_configuration", provider_access
    )
    payload = MemoryBaseCreate(
        name="New memory",
        flow_id=memory_base.flow_id,
        embedding_model="text-embedding-3-small",
        backend_type="opensearch",
    )

    with pytest.raises(MemoryBaseFlowNotFoundError, match="not found"):
        await MemoryBaseService().create(payload, user_id=owner.id)

    provider_access.assert_not_awaited()


@pytest.mark.parametrize("memory_history", [True], indirect=True)
async def test_existing_memory_base_ingestion_rejects_reserved_history(memory_history, async_session, monkeypatch):
    owner, memory_base, message = memory_history
    assert await get_message_for_user(async_session, user_id=owner.id, message_id=message.id) is None
    provider_access = AsyncMock(side_effect=AssertionError("Reserved flow reached ingestion provider policy"))
    fetch_messages = AsyncMock(wraps=_fetch_pending_messages)
    monkeypatch.setattr("langflow.services.memory_base.task.preflight_memory_provider_use", provider_access)
    monkeypatch.setattr("langflow.services.memory_base.task._fetch_pending_messages", fetch_messages)
    request = IngestionRequest(
        memory_base_id=memory_base.id,
        session_id=message.session_id,
        flow_id=memory_base.flow_id,
        kb_name=memory_base.kb_name,
        kb_username=owner.username,
        owner_user_id=owner.id,
        actor_user_id=owner.id,
        embedding_provider="OpenAI",
        embedding_model="text-embedding-3-small",
        cursor_id=None,
        task_job_id=uuid4(),
        job_service=MagicMock(),
    )

    with pytest.raises(MemoryBaseFlowNotFoundError, match="not found"):
        await ingest_memory_task(request=request)

    provider_access.assert_not_awaited()
    fetch_messages.assert_not_awaited()
    assert (await async_session.get(MessageTable, message.id)).text == "private history"


@pytest.mark.parametrize("memory_history", [False], indirect=True)
async def test_memory_base_can_still_resolve_and_fetch_owned_uuid4_history(memory_history, async_session):
    owner, memory_base, message = memory_history

    scope = await resolve_memory_provider_scope(
        async_session,
        memory_base_id=memory_base.id,
        owner_user_id=owner.id,
        actor_user_id=owner.id,
    )
    messages = await _fetch_pending_messages(
        async_session, flow_id=scope.flow.id, session_id=message.session_id, cursor_id=None
    )

    assert [item.id for item in messages] == [message.id]
