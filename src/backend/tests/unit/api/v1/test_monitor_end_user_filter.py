"""Serving-plane: GET /monitor/messages can pull one end user's messages by the indexed owner.

Messages are stamped with the end user's derived owner id (P2 write); the new ``end_user_id`` filter
resolves the raw id through the SAME derivation (D6) so the predicate matches. The filter is optional
and off by default, so existing callers are unchanged (BC). The flow-ownership gate is preserved.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from langflow.schema.message import Message
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.message.model import MessageTable
from lfx.memory.flow_context import derive_message_owner_uuid
from lfx.services.deps import session_scope


@pytest.fixture
async def flow_with_end_user_messages(active_user):
    """A flow owned by active_user with one message per end user (owner = derived uuid)."""
    async with session_scope() as session:
        flow = Flow(name=f"eu-flow-{uuid4().hex[:8]}", user_id=active_user.id, data={"nodes": [], "edges": []})
        session.add(flow)
        await session.flush()
        for owner_raw, text in (("alice", "from alice"), ("bob", "from bob")):
            mt = MessageTable.from_message(
                Message(text=text, sender="User", sender_name="User", session_id=f"{owner_raw}::s1"),
                user_id=derive_message_owner_uuid(owner_raw),
            )
            mt.flow_id = flow.id
            session.add(mt)
        await session.flush()
    return flow


async def test_end_user_filter_returns_only_that_end_user(
    client: AsyncClient,
    logged_in_headers,
    flow_with_end_user_messages,  # noqa: ARG001
):
    resp = await client.get("api/v1/monitor/messages?end_user_id=alice", headers=logged_in_headers)
    assert resp.status_code == 200, resp.text
    texts = [m["text"] for m in resp.json()]
    assert texts == ["from alice"]


async def test_other_end_user_isolated(client: AsyncClient, logged_in_headers, flow_with_end_user_messages):  # noqa: ARG001
    resp = await client.get("api/v1/monitor/messages?end_user_id=bob", headers=logged_in_headers)
    assert resp.status_code == 200, resp.text
    assert [m["text"] for m in resp.json()] == ["from bob"]


async def test_no_filter_returns_all_bc(client: AsyncClient, logged_in_headers, flow_with_end_user_messages):  # noqa: ARG001
    # Omitting the param is byte-for-byte the prior behavior: both end users' messages come back.
    resp = await client.get("api/v1/monitor/messages", headers=logged_in_headers)
    assert resp.status_code == 200, resp.text
    texts = {m["text"] for m in resp.json()}
    assert {"from alice", "from bob"} <= texts
