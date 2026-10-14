"""API coverage for memory bases containing legacy messages with NULL text."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from langflow.api.utils.flow_utils import compute_virtual_flow_id
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.memory_base.model import MemoryBase, MessageIngestionRecord
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import session_scope
from sqlalchemy import update
from sqlmodel import select


@pytest.mark.asyncio
@pytest.mark.parametrize("filter_session", [False, True])
async def test_memory_base_messages_accept_legacy_null_text(
    client: AsyncClient, active_user, logged_in_headers, *, filter_session: bool
):
    """List ingested NULL text without losing message metadata or session filtering."""
    memory_base_id = uuid4()
    session_id = f"legacy-{uuid4().hex}"
    other_session_id = f"other-{uuid4().hex}"
    null_id, empty_id, normal_id, pending_id = (uuid4() for _ in range(4))
    ingested_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    async with session_scope() as session:
        flow = Flow(name="Legacy message flow", user_id=active_user.id, data={"nodes": [], "edges": []})
        session.add(flow)
        await session.flush()
        session.add(
            MemoryBase(
                id=memory_base_id,
                name="Legacy message memory",
                flow_id=flow.id,
                user_id=active_user.id,
                kb_name=f"legacy-{uuid4().hex}",
            )
        )
        await session.flush()
        for message_id, message_text, message_session_id in (
            (null_id, "placeholder", session_id),
            (empty_id, "", session_id),
            (normal_id, "hello", other_session_id),
            (pending_id, "not ingested", session_id),
        ):
            session.add(
                MessageTable(
                    id=message_id,
                    sender="AI",
                    sender_name="Bot",
                    session_id=message_session_id,
                    text=message_text,
                    flow_id=flow.id,
                    user_id=active_user.id,
                )
            )
        await session.flush()
        for message_id, message_session_id in (
            (null_id, session_id),
            (empty_id, session_id),
            (normal_id, other_session_id),
        ):
            session.add(
                MessageIngestionRecord(
                    message_id=message_id,
                    memory_base_id=memory_base_id,
                    session_id=message_session_id,
                    ingested_at=ingested_at,
                )
            )
        # Old writers could store NULL even though today's message schema expects
        # a string. Update storage directly to reproduce that persisted state.
        await session.execute(update(MessageTable).where(MessageTable.id == null_id).values(text=None))
        assert (await session.exec(select(MessageTable.text).where(MessageTable.id == null_id))).one() is None

    response = await client.get(
        f"api/v1/memories/{memory_base_id}/messages",
        headers=logged_in_headers,
        params={"session_id": session_id} if filter_session else {},
    )

    assert response.status_code == 200
    page = response.json()
    items = {item["id"]: item for item in page["items"]}
    expected_ids = {str(null_id), str(empty_id)}
    if not filter_session:
        expected_ids.add(str(normal_id))
        assert items[str(normal_id)]["text"] == "hello"
    assert set(items) == expected_ids
    assert page["total"] == len(expected_ids)
    assert items[str(null_id)]["text"] == ""
    assert items[str(empty_id)]["text"] == ""
    for item in items.values():
        assert item["sender"] == "AI"
        assert item["sender_name"] == "Bot"
        assert item["content_blocks"] == []
        assert item["job_id"] is None
        assert datetime.fromisoformat(item["ingested_at"]).replace(tzinfo=timezone.utc) == ingested_at
    assert items[str(null_id)]["session_id"] == session_id


@pytest.mark.asyncio
@pytest.mark.parametrize("shared", [False, True])
@pytest.mark.parametrize("persisted_text", [None, "", "hello"])
async def test_message_properties_update_preserves_legacy_text(
    client: AsyncClient, active_user, logged_in_headers, persisted_text: str | None, *, shared: bool
):
    """Normalize update responses without rewriting stored NULL, empty, or normal text."""
    message_id = uuid4()
    session_id = f"legacy-update-{uuid4().hex}"
    async with session_scope() as session:
        flow = Flow(name="Legacy update flow", user_id=active_user.id, data={"nodes": [], "edges": []})
        session.add(flow)
        await session.flush()
        source_flow_id = flow.id
        message_flow_id = (
            compute_virtual_flow_id(active_user.id, source_flow_id, principal_type="user") if shared else source_flow_id
        )
        session.add(
            MessageTable(
                id=message_id,
                sender="AI",
                sender_name="Bot",
                session_id=session_id,
                text="placeholder" if persisted_text is None else persisted_text,
                category="message",
                flow_id=message_flow_id,
                user_id=active_user.id,
                session_metadata={"source": "legacy"},
            )
        )
        await session.flush()
        if persisted_text is None:
            await session.execute(update(MessageTable).where(MessageTable.id == message_id).values(text=None))

    route = "messages/shared" if shared else "messages"
    response = await client.put(
        f"api/v1/monitor/{route}/{message_id}",
        headers=logged_in_headers,
        params={"source_flow_id": str(source_flow_id)} if shared else {},
        json={"properties": {"build_duration": 1500, "usage": {"total_tokens": 42}}},
    )

    assert response.status_code == 200, response.text
    message = response.json()
    assert message["id"] == str(message_id)
    assert message["text"] == (persisted_text or "")
    assert message["properties"]["build_duration"] == 1500
    assert message["properties"]["usage"]["total_tokens"] == 42
    assert message["flow_id"] == str(message_flow_id)
    assert message["session_id"] == session_id
    assert message["sender"] == "AI"
    assert message["sender_name"] == "Bot"
    assert message["session_metadata"] == {"source": "legacy"}
    assert message["edit"] is False

    async with session_scope() as session:
        stored_message = await session.get(MessageTable, message_id)
        assert stored_message is not None
        assert stored_message.text == persisted_text
        assert stored_message.properties["build_duration"] == 1500
        assert stored_message.properties["usage"]["total_tokens"] == 42
