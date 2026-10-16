"""Storage behavior behind the Agent's rolling chat-summary: CAS saves, scoped reads, cursor ranges, cleanup."""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from langflow.api.utils.flow_utils import cascade_delete_flow, compute_virtual_flow_id
from langflow.memory import (
    adelete_session_memory_states,
    aget_messages,
    aget_messages_between,
    aget_session_memory_state,
    asave_session_memory_state,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.session_memory.model import SessionMemoryStateTable
from langflow.services.deps import session_scope
from sqlmodel import select

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


async def _add_message(
    flow_id: UUID,
    user_id: UUID,
    session_id: str,
    *,
    ts: datetime,
    msg_id: UUID | None = None,
    text: str = "hi",
    error: bool = False,
    context_id: str | None = None,
) -> UUID:
    msg_id = msg_id or uuid4()
    async with session_scope() as session:
        session.add(
            MessageTable(
                id=msg_id,
                flow_id=flow_id,
                user_id=user_id,
                session_id=session_id,
                context_id=context_id,
                timestamp=ts,
                sender="User",
                sender_name="User",
                text=text,
                error=error,
                category="error" if error else "message",
                files=[],
                content_blocks=[],
            )
        )
    return msg_id


def _scope(flow_id: UUID, user_id: UUID, session_id: str = "s1", context_id: str | None = None) -> dict:
    return {"flow_id": flow_id, "user_id": user_id, "session_id": session_id, "context_id": context_id}


async def _save(scope: dict, cursor: UUID, expected_version: int, *, summary: str = "sum", delta: int = 2):
    return await asave_session_memory_state(
        **scope,
        summary=summary,
        cursor_message_id=cursor,
        folded_delta=delta,
        summary_model="m",
        expected_version=expected_version,
    )


async def test_should_insert_then_compare_and_swap(client):  # noqa: ARG001
    flow_id, user_id = uuid4(), uuid4()
    scope = _scope(flow_id, user_id)
    first = await _add_message(flow_id, user_id, "s1", ts=T0)
    second = await _add_message(flow_id, user_id, "s1", ts=T0 + timedelta(seconds=1))

    assert (await aget_session_memory_state(**scope)).version == 0

    saved = await _save(scope, first, 0)
    assert saved is not None
    assert (saved.version, saved.folded_count, saved.cursor_message_id) == (1, 2, first)
    assert saved.cursor_timestamp is not None

    updated = await _save(scope, second, 1, summary="newer", delta=3)
    assert updated is not None
    assert (updated.version, updated.folded_count, updated.summary) == (2, 5, "newer")
    assert await aget_session_memory_state(**scope) == updated

    # A writer holding the old version, and a second first-insert, both lose.
    assert await _save(scope, second, 1) is None
    assert await _save(scope, second, 0) is None
    assert (await aget_session_memory_state(**scope)).version == 2


async def test_should_return_none_when_cursor_message_is_missing(client):  # noqa: ARG001
    scope = _scope(uuid4(), uuid4())
    assert await _save(scope, uuid4(), 0) is None
    assert (await aget_session_memory_state(**scope)).version == 0


async def test_should_isolate_state_by_user_flow_and_context(client):  # noqa: ARG001
    flow_id, user_id = uuid4(), uuid4()
    scope = _scope(flow_id, user_id, context_id="ctx")
    cursor = await _add_message(flow_id, user_id, "s1", ts=T0, context_id="ctx")
    assert await _save(scope, cursor, 0, summary="mine") is not None

    for other in (
        {**scope, "user_id": uuid4()},
        {**scope, "flow_id": uuid4()},
        {**scope, "context_id": "other"},
        {**scope, "context_id": None},
    ):
        assert (await aget_session_memory_state(**other)).version == 0

    # Another user or flow cannot write against this cursor message either.
    assert await _save({**scope, "user_id": uuid4()}, cursor, 0) is None
    assert await _save({**scope, "flow_id": uuid4()}, cursor, 0) is None

    assert (await aget_session_memory_state(**scope)).summary == "mine"


async def test_should_order_between_by_timestamp_then_id_with_exclusive_bounds(client):  # noqa: ARG001
    flow_id, user_id = uuid4(), uuid4()
    ids = sorted(uuid4() for _ in range(4))
    # Same timestamp for the first three: only the id breaks the tie.
    for msg_id in ids[:3]:
        await _add_message(flow_id, user_id, "s1", ts=T0, msg_id=msg_id, text=str(msg_id))
    last = await _add_message(flow_id, user_id, "s1", ts=T0 + timedelta(seconds=1), msg_id=ids[3])
    await _add_message(flow_id, user_id, "s1", ts=T0 + timedelta(milliseconds=500), error=True, text="boom")
    await _add_message(flow_id, user_id, "other-session", ts=T0 + timedelta(milliseconds=100))
    scope = _scope(flow_id, user_id)

    between = await aget_messages_between(
        **scope, after_message_id=ids[0], after_timestamp=None, before_message_id=last, limit=10
    )
    assert [m.text for m in between] == [str(ids[1]), str(ids[2])]

    middle_only = await aget_messages_between(
        **scope, after_message_id=ids[0], after_timestamp=None, before_message_id=ids[2], limit=10
    )
    assert [m.text for m in middle_only] == [str(ids[1])]

    open_below = await aget_messages_between(
        **scope, after_message_id=None, after_timestamp=None, before_message_id=ids[1], limit=10
    )
    assert [m.text for m in open_below] == [str(ids[0])]

    limited = await aget_messages_between(
        **scope, after_message_id=None, after_timestamp=None, before_message_id=last, limit=2
    )
    assert [m.text for m in limited] == [str(ids[0]), str(ids[1])]

    assert (
        await aget_messages_between(
            **scope, after_message_id=None, after_timestamp=None, before_message_id=uuid4(), limit=10
        )
        == []
    )
    assert (
        await aget_messages_between(
            **{**scope, "user_id": uuid4()},
            after_message_id=None,
            after_timestamp=None,
            before_message_id=last,
            limit=10,
        )
        == []
    )


async def test_should_fall_back_to_read_back_cursor_timestamp_when_cursor_message_was_deleted(client):  # noqa: ARG001
    flow_id, user_id = uuid4(), uuid4()
    scope = _scope(flow_id, user_id)
    old = await _add_message(flow_id, user_id, "s1", ts=T0, text="old")
    kept = await _add_message(flow_id, user_id, "s1", ts=T0 + timedelta(seconds=1), text="kept")
    boundary = await _add_message(flow_id, user_id, "s1", ts=T0 + timedelta(seconds=2))
    assert await _save(scope, old, 0) is not None
    # SQLite hands datetimes back naive unless the column type is timezone-aware.
    state = await aget_session_memory_state(**scope)
    assert state.cursor_timestamp is not None
    async with session_scope() as session:
        await session.delete(await session.get(MessageTable, old))

    result = await aget_messages_between(
        **scope,
        after_message_id=state.cursor_message_id,
        after_timestamp=state.cursor_timestamp,
        before_message_id=boundary,
        limit=10,
    )
    assert [m.text for m in result] == ["kept"]
    assert kept


async def test_should_include_tied_rows_with_greater_id_when_cursor_message_was_deleted(client):  # noqa: ARG001
    flow_id, user_id = uuid4(), uuid4()
    ids = sorted(uuid4() for _ in range(3))
    for msg_id in ids:
        await _add_message(flow_id, user_id, "s1", ts=T0, msg_id=msg_id, text=str(msg_id))
    boundary = await _add_message(flow_id, user_id, "s1", ts=T0 + timedelta(seconds=1))
    async with session_scope() as session:
        await session.delete(await session.get(MessageTable, ids[0]))

    result = await aget_messages_between(
        **_scope(flow_id, user_id),
        after_message_id=ids[0],
        after_timestamp=T0,
        before_message_id=boundary,
        limit=10,
    )
    assert [m.text for m in result] == [str(ids[1]), str(ids[2])]


async def test_should_split_window_and_older_range_without_overlap_when_timestamps_tie(client):  # noqa: ARG001
    flow_id, user_id = uuid4(), uuid4()
    ids = sorted(uuid4() for _ in range(5))
    for msg_id in ids:
        await _add_message(flow_id, user_id, "s1", ts=T0, msg_id=msg_id, text=str(msg_id))

    newest_first = await aget_messages(flow_id=flow_id, user_id=user_id, session_id="s1", order="DESC")
    assert [m.text for m in newest_first] == [str(i) for i in reversed(ids)]

    window = list(reversed(await aget_messages(flow_id=flow_id, user_id=user_id, session_id="s1", limit=2)))
    older = await aget_messages_between(
        **_scope(flow_id, user_id),
        after_message_id=None,
        after_timestamp=None,
        before_message_id=window[0].id,
        limit=10,
    )
    assert [m.text for m in older + window] == [str(i) for i in ids]


@pytest.fixture
async def flow_with_state(active_user):
    async with session_scope() as session:
        flow = Flow(name=f"summary-{uuid4().hex[:8]}", user_id=active_user.id, data={"nodes": [], "edges": []})
        session.add(flow)
        await session.flush()
        flow_id = flow.id
    states = {}
    for session_id in ("keep", "drop"):
        cursor = await _add_message(flow_id, active_user.id, session_id, ts=T0)
        scope = _scope(flow_id, active_user.id, session_id)
        assert await _save(scope, cursor, 0) is not None
        states[session_id] = scope
    return flow_id, states


async def _state_session_ids(flow_id: UUID) -> set[str]:
    async with session_scope() as session:
        rows = await session.exec(
            select(SessionMemoryStateTable.session_id).where(SessionMemoryStateTable.flow_id == flow_id)
        )
        return set(rows.all())


async def test_should_delete_state_with_session_endpoints(client, logged_in_headers, flow_with_state):
    flow_id, _ = flow_with_state

    response = await client.delete("api/v1/monitor/messages/session/drop", headers=logged_in_headers)
    assert response.status_code == 204
    assert await _state_session_ids(flow_id) == {"keep"}

    response = await client.request(
        "DELETE", "api/v1/monitor/messages/sessions", json=["keep"], headers=logged_in_headers
    )
    assert response.status_code == 200
    assert await _state_session_ids(flow_id) == set()


async def test_should_not_delete_other_users_state_via_session_endpoint(client, logged_in_headers):
    foreign_flow, foreign_user = uuid4(), uuid4()
    cursor = await _add_message(foreign_flow, foreign_user, "drop", ts=T0)
    assert await _save(_scope(foreign_flow, foreign_user, "drop"), cursor, 0) is not None

    await client.delete("api/v1/monitor/messages/session/drop", headers=logged_in_headers)

    assert await _state_session_ids(foreign_flow) == {"drop"}


async def test_should_delete_state_with_flow(flow_with_state):
    flow_id, _ = flow_with_state
    async with session_scope() as session:
        assert await cascade_delete_flow(session, flow_id)
    assert await _state_session_ids(flow_id) == set()


async def test_adelete_session_memory_states_handles_empty_and_filters(flow_with_state):
    flow_id, _ = flow_with_state
    assert await adelete_session_memory_states(flow_ids=[]) == 0
    assert await adelete_session_memory_states(flow_ids=[flow_id], session_ids=["drop"]) == 1
    assert await _state_session_ids(flow_id) == {"keep"}
    assert await adelete_session_memory_states(flow_ids=[flow_id]) == 1


async def test_should_delete_state_with_shared_session_endpoint(client, logged_in_headers, active_user):
    source_flow_id = uuid4()
    virtual_flow_id = compute_virtual_flow_id(active_user.id, source_flow_id, principal_type="user")
    for session_id in ("keep", "drop"):
        cursor = await _add_message(virtual_flow_id, active_user.id, session_id, ts=T0)
        assert await _save(_scope(virtual_flow_id, active_user.id, session_id), cursor, 0) is not None

    response = await client.delete(
        f"api/v1/monitor/messages/shared/session/drop?source_flow_id={source_flow_id}", headers=logged_in_headers
    )

    assert response.status_code == 204
    assert await _state_session_ids(virtual_flow_id) == {"keep"}
