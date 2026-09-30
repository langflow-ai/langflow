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


# --- BUG-02: the hand-built HITL card must be stamped so its owner's per-user pull returns it ----


def _enable_serving(monkeypatch) -> None:
    from lfx.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "serving_end_user_header", "X-End-User-Id")
    monkeypatch.setattr(settings, "serving_trust_proxy_headers", True)


@pytest.fixture
async def hitl_card_flow(active_user):
    async with session_scope() as session:
        flow = Flow(name=f"hitl-flow-{uuid4().hex[:8]}", user_id=active_user.id, data={"nodes": [], "edges": []})
        session.add(flow)
        await session.flush()
        return flow.id


async def test_hitl_card_is_visible_to_its_end_user(
    client: AsyncClient, logged_in_headers, hitl_card_flow, monkeypatch
):
    # The card is built by hand and bypasses Component._store_message; without the owner stamp it
    # persists user_id=NULL and this pull (exact owner match) returns 0. With the fix it returns it.
    from langflow.api.v2.hitl import persist_human_input_card

    _enable_serving(monkeypatch)
    await persist_human_input_card(
        {"request_id": "r1", "prompt": "approve?", "allowed_decisions": []},
        flow_id=hitl_card_flow,
        session_id="alice::card1",
        job_id=None,
    )
    resp = await client.get(
        f"api/v1/monitor/messages?flow_id={hitl_card_flow}&end_user_id=alice", headers=logged_in_headers
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 1  # the card is retrievable under alice (was 0 before the fix)


async def test_hitl_card_feature_off_stays_unstamped(hitl_card_flow, monkeypatch):
    # Feature off: no end user to attribute, so the card owner stays NULL exactly as before (BC).
    from langflow.api.v2.hitl import persist_human_input_card
    from langflow.services.deps import get_settings_service
    from sqlmodel import select

    monkeypatch.setattr(get_settings_service().settings, "serving_end_user_header", None)
    await persist_human_input_card(
        {"request_id": "r1", "prompt": "approve?"}, flow_id=hitl_card_flow, session_id="s1", job_id=None
    )
    async with session_scope() as session:
        rows = (await session.exec(select(MessageTable).where(MessageTable.flow_id == hitl_card_flow))).all()
    assert len(rows) == 1
    assert rows[0].user_id is None
