"""RED: GET /api/v1/memories/{id}/messages 500s on legacy NULL message text.

The monitor history endpoints coerce legacy NULL ``text`` to ``""``
(#15076, ``_message_history_response``), and the preprocessing branch of this
same endpoint already does ``row.output_text or ""`` — but the raw-messages
branch passes ``msg.text`` straight into ``MessageReadResponse.text: str``,
so a single legacy NULL-text row fails response validation and the whole
listing returns 500.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.memory_base.model import MemoryBase, MessageIngestionRecord
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import session_scope


def _make_mb(**kwargs) -> MemoryBase:
    return MemoryBase(
        id=kwargs["id"],
        name="mb-null-text",
        flow_id=kwargs["flow_id"],
        user_id=kwargs["user_id"],
        threshold=10,
        kb_name=f"kb-{uuid4().hex[:8]}",
        auto_capture=True,
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_mb_messages_returns_empty_text_for_legacy_null(client: AsyncClient, active_user, logged_in_headers):
    mb_id = uuid4()
    session_id = f"sess-null-{uuid4().hex[:8]}"
    async with session_scope() as session:
        flow = Flow(
            name=f"mb-null-text-flow-{uuid4().hex[:8]}",
            user_id=active_user.id,
            data={"nodes": [], "edges": []},
        )
        session.add(flow)
        await session.flush()
        flow_id = flow.id
        session.add(_make_mb(id=mb_id, flow_id=flow_id, user_id=active_user.id))
        good_id, empty_id, null_id = uuid4(), uuid4(), uuid4()
        for mid, txt in ((good_id, "hello"), (empty_id, ""), (null_id, "placeholder")):
            session.add(
                MessageTable(
                    id=mid,
                    sender="AI",
                    sender_name="Bot",
                    session_id=session_id,
                    text=txt,
                    flow_id=flow_id,
                )
            )
            session.add(
                MessageIngestionRecord(
                    message_id=mid,
                    memory_base_id=mb_id,
                    session_id=session_id,
                    ingested_at=datetime.now(timezone.utc),
                )
            )
        await session.flush()
        # Simulate a legacy row written before text was validated: NULL in
        # storage, bypassing ORM-level validation the way an old writer did.
        from sqlalchemy import text as sa_text

        await session.execute(sa_text("UPDATE message SET text = NULL WHERE id = :id"), {"id": null_id.hex})
        stored = (
            await session.execute(sa_text("SELECT text FROM message WHERE id = :id"), {"id": null_id.hex})
        ).first()
        assert stored is not None
        assert stored[0] is None, "legacy NULL row was not simulated"

    response = await client.get(f"api/v1/memories/{mb_id}/messages", headers=logged_in_headers)

    assert response.status_code == 200
    items = {item["id"]: item["text"] for item in response.json()["items"]}
    assert set(items) == {str(good_id), str(empty_id), str(null_id)}
    assert items[str(null_id)] == ""
