"""Storage behavior behind the Agent's rolling chat-summary: CAS saves, scoped reads, cursor ranges, cleanup."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from langflow.api.utils.flow_utils import cascade_delete_flow, compute_virtual_flow_id
from langflow.api.v1.monitor import _delete_session_summaries
from langflow.memory import (
    adelete_messages,
    aget_messages,
    aget_messages_between,
    aget_session_memory_state,
    asave_session_memory_state,
    aupdate_messages,
    delete_message,
    rename_session_memory,
    reset_folded_memory_for_update,
)
from langflow.schema.message import Message
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.session_memory.model import SessionMemoryStateTable
from langflow.services.deps import session_scope
from lfx.memory.flow_context import reset_evals_memory_isolated, set_evals_memory_isolated
from lfx.memory.session_state import summary_snapshot
from sqlalchemy import update
from sqlmodel import col, select

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
    category: str = "message",
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
                category="error" if error else category,
                files=[],
                content_blocks=[],
            )
        )
    return msg_id


def _scope(flow_id: UUID, user_id: UUID, session_id: str = "s1", context_id: str | None = None) -> dict:
    return {"flow_id": flow_id, "user_id": user_id, "session_id": session_id, "context_id": context_id}


async def _save(
    scope: dict, cursor: UUID, expected_version: int, *, summary: str = "sum", delta: int = 2, batch: tuple = ()
):
    """Save state folding ``batch`` (default: just the cursor message) as the messages are stored now."""
    async with session_scope() as session:
        rows = await session.exec(select(MessageTable).where(col(MessageTable.id).in_([cursor, *batch])))
        batch_snapshot = {row.id: summary_snapshot(row) for row in rows.all()}
    state = await aget_session_memory_state(**scope)
    return await asave_session_memory_state(
        **scope,
        summary=summary,
        cursor_message_id=cursor,
        folded_delta=delta,
        summary_model="m",
        expected_version=expected_version,
        batch_snapshot=batch_snapshot,
        expected_state_id=getattr(state, "id", None),
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
        **scope, after_message_id=ids[0], after_timestamp=T0, before_message_id=last, limit=10
    )
    assert [m.text for m in between] == [str(ids[1]), str(ids[2])]

    middle_only = await aget_messages_between(
        **scope, after_message_id=ids[0], after_timestamp=T0, before_message_id=ids[2], limit=10
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


async def test_should_not_read_fold_or_write_state_while_evals_memory_is_isolated(client):  # noqa: ARG001
    flow_id, user_id = uuid4(), uuid4()
    scope = _scope(flow_id, user_id)
    first = await _add_message(flow_id, user_id, "s1", ts=T0)
    second = await _add_message(flow_id, user_id, "s1", ts=T0 + timedelta(seconds=1))
    assert await _save(scope, first, 0) is not None

    token = set_evals_memory_isolated(True)
    try:
        assert await aget_session_memory_state(**scope) is None
        assert await _save(scope, second, 1) is None
        assert (
            await aget_messages_between(
                **scope, after_message_id=None, after_timestamp=None, before_message_id=second, limit=10
            )
            == []
        )
    finally:
        reset_evals_memory_isolated(token)

    assert (await aget_session_memory_state(**scope)).version == 1


async def test_should_validate_the_message_executor_before_saving_state(client):  # noqa: ARG001
    flow_id, user_id = uuid4(), uuid4()
    cursor = await _add_message(flow_id, user_id, "s1", ts=T0)
    validator = AsyncMock(side_effect=PermissionError)
    with patch("langflow.memory._validate_message_executor", new=validator), pytest.raises(PermissionError):
        await _save(_scope(flow_id, user_id), cursor, 0)
    validator.assert_awaited_once()
    assert (await aget_session_memory_state(**_scope(flow_id, user_id))).version == 0


async def _three_messages_with_state(flow_id: UUID, user_id: UUID, session_id: str = "s1") -> list[UUID]:
    """Three messages; the state has folded the first two."""
    ids = [
        await _add_message(flow_id, user_id, session_id, ts=T0 + timedelta(seconds=i), text=f"m{i}") for i in range(3)
    ]
    assert await _save(_scope(flow_id, user_id, session_id), ids[1], 0) is not None
    return ids


async def _has_state(flow_id: UUID, user_id: UUID, session_id: str = "s1") -> bool:
    return (await aget_session_memory_state(**_scope(flow_id, user_id, session_id))).version > 0


async def test_should_reset_state_only_when_a_folded_message_is_edited(client):  # noqa: ARG001
    flow_id, user_id = uuid4(), uuid4()
    ids = await _three_messages_with_state(flow_id, user_id)

    # Same text, or a message after the cursor: the fold stays valid.
    await aupdate_messages(Message(id=ids[0], text="m0"))
    await aupdate_messages(Message(id=ids[2], text="edited"))
    assert await _has_state(flow_id, user_id)

    await aupdate_messages(Message(id=ids[1], text="edited"))
    assert not await _has_state(flow_id, user_id)


async def test_should_reset_state_when_folded_messages_are_deleted(client):  # noqa: ARG001
    flow_id, user_id = uuid4(), uuid4()
    ids = await _three_messages_with_state(flow_id, user_id)

    await delete_message(ids[2])
    assert await _has_state(flow_id, user_id)

    await delete_message(ids[0])
    assert not await _has_state(flow_id, user_id)

    other_user = uuid4()
    await _three_messages_with_state(flow_id, other_user)
    await adelete_messages("s1", flow_id=flow_id, user_id=user_id)
    assert await _has_state(flow_id, other_user)
    await adelete_messages("s1", flow_id=flow_id, user_id=other_user)
    assert not await _has_state(flow_id, other_user)


async def test_should_reset_state_when_endpoints_edit_or_delete_folded_messages(client, logged_in_headers, active_user):
    async with session_scope() as session:
        flow = Flow(name=f"summary-{uuid4().hex[:8]}", user_id=active_user.id, data={"nodes": [], "edges": []})
        session.add(flow)
        await session.flush()
        flow_id = flow.id
    ids = await _three_messages_with_state(flow_id, active_user.id)

    response = await client.put(f"api/v1/monitor/messages/{ids[2]}", json={"text": "edited"}, headers=logged_in_headers)
    assert response.status_code == 200
    assert await _has_state(flow_id, active_user.id)

    response = await client.put(f"api/v1/monitor/messages/{ids[0]}", json={"text": "edited"}, headers=logged_in_headers)
    assert response.status_code == 200
    assert not await _has_state(flow_id, active_user.id)

    assert await _save(_scope(flow_id, active_user.id), ids[1], 0) is not None
    response = await client.request("DELETE", "api/v1/monitor/messages", json=[str(ids[1])], headers=logged_in_headers)
    assert response.status_code == 204
    assert not await _has_state(flow_id, active_user.id)


async def test_should_move_state_with_a_session_rename(client, logged_in_headers, flow_with_state):
    flow_id, states = flow_with_state
    user_id = states["keep"]["user_id"]

    response = await client.patch(
        "api/v1/monitor/messages/session/keep", params={"new_session_id": "renamed"}, headers=logged_in_headers
    )

    assert response.status_code == 200
    assert await _state_session_ids(flow_id) == {"renamed", "drop"}
    assert (await aget_session_memory_state(**_scope(flow_id, user_id, "renamed"))).version == 1


async def test_should_drop_state_when_a_rename_merges_into_an_existing_session(
    client, logged_in_headers, flow_with_state
):
    flow_id, _ = flow_with_state

    response = await client.patch(
        "api/v1/monitor/messages/session/keep", params={"new_session_id": "drop"}, headers=logged_in_headers
    )

    assert response.status_code == 200
    assert await _state_session_ids(flow_id) == set()


async def test_should_move_state_with_a_shared_session_rename(client, logged_in_headers, active_user):
    source_flow_id = uuid4()
    virtual_flow_id = compute_virtual_flow_id(active_user.id, source_flow_id, principal_type="user")
    cursor = await _add_message(virtual_flow_id, active_user.id, "old", ts=T0)
    assert await _save(_scope(virtual_flow_id, active_user.id, "old"), cursor, 0) is not None

    response = await client.patch(
        f"api/v1/monitor/messages/shared/session/old?new_session_id=new&source_flow_id={source_flow_id}",
        headers=logged_in_headers,
    )

    assert response.status_code == 200
    assert await _state_session_ids(virtual_flow_id) == {"new"}


async def test_should_include_null_category_and_skip_error_messages_between(client):  # noqa: ARG001
    flow_id, user_id = uuid4(), uuid4()
    plain = await _add_message(flow_id, user_id, "s1", ts=T0, text="null")
    async with session_scope() as session:  # the column is nullable; the model refuses None on insert
        await session.exec(update(MessageTable).where(MessageTable.id == plain).values(category=None))
    await _add_message(flow_id, user_id, "s1", ts=T0 + timedelta(seconds=1), category="message", text="msg")
    await _add_message(flow_id, user_id, "s1", ts=T0 + timedelta(seconds=2), category="error", text="err")
    await _add_message(flow_id, user_id, "s1", ts=T0 + timedelta(seconds=3), error=True, text="flagged")
    boundary = await _add_message(flow_id, user_id, "s1", ts=T0 + timedelta(seconds=4))

    between = await aget_messages_between(
        **_scope(flow_id, user_id), after_message_id=None, after_timestamp=None, before_message_id=boundary, limit=10
    )

    assert [m.text for m in between] == ["null", "msg"]
    assert between[0].id == plain


@pytest.mark.parametrize("change", ["delete", "edit", "none"])
async def test_should_save_nothing_when_a_batch_message_changes_during_the_summary_call(client, change):  # noqa: ARG001
    from lfx.base.memory.session_compressor import fold_batch

    flow_id, user_id = uuid4(), uuid4()
    scope = _scope(flow_id, user_id)
    ids = [await _add_message(flow_id, user_id, "s1", ts=T0 + timedelta(seconds=i), text=f"m{i}") for i in range(4)]
    batch = await aget_messages_between(
        **scope, after_message_id=None, after_timestamp=None, before_message_id=ids[3], limit=10
    )

    async def summarize_while_message_changes(_previous, _messages):
        if change == "delete":
            await delete_message(ids[1])
        elif change == "edit":
            await aupdate_messages(Message(id=ids[1], text="edited"))
        return "SUMMARY"

    await fold_batch(
        scope=scope,
        state=await aget_session_memory_state(**scope),
        batch=batch,
        summarize=summarize_while_message_changes,
        summary_model=None,
    )

    # "none" is the control: the same fold does save when nothing changed.
    assert await _has_state(flow_id, user_id) == (change == "none")


async def test_should_reset_both_scopes_when_an_endpoint_moves_a_folded_message(client, logged_in_headers, active_user):
    async with session_scope() as session:
        flow = Flow(name=f"summary-{uuid4().hex[:8]}", user_id=active_user.id, data={"nodes": [], "edges": []})
        session.add(flow)
        await session.flush()
        flow_id = flow.id
    old_ids = await _three_messages_with_state(flow_id, active_user.id, "old")
    await _three_messages_with_state(flow_id, active_user.id, "new")

    response = await client.put(
        f"api/v1/monitor/messages/{old_ids[0]}", json={"session_id": "new"}, headers=logged_in_headers
    )

    assert response.status_code == 200
    assert not await _has_state(flow_id, active_user.id, "old")
    assert not await _has_state(flow_id, active_user.id, "new")


async def test_should_keep_state_when_an_update_changes_nothing_the_fold_reads(client, logged_in_headers, active_user):
    async with session_scope() as session:
        flow = Flow(name=f"summary-{uuid4().hex[:8]}", user_id=active_user.id, data={"nodes": [], "edges": []})
        session.add(flow)
        await session.flush()
        flow_id = flow.id
    ids = await _three_messages_with_state(flow_id, active_user.id)

    response = await client.put(
        f"api/v1/monitor/messages/{ids[0]}", json={"sender_name": "Someone"}, headers=logged_in_headers
    )

    assert response.status_code == 200
    assert await _has_state(flow_id, active_user.id)


async def _snapshot_of(*message_ids: UUID) -> dict:
    async with session_scope() as session:
        rows = await session.exec(select(MessageTable).where(col(MessageTable.id).in_(message_ids)))
        return {row.id: summary_snapshot(row) for row in rows.all()}


async def _save_snapshot(scope: dict, cursor: UUID, snapshot: dict, *, version: int = 0, state_id: UUID | None = None):
    return await asave_session_memory_state(
        **scope,
        summary="sum",
        cursor_message_id=cursor,
        folded_delta=len(snapshot),
        summary_model="m",
        expected_version=version,
        batch_snapshot=snapshot,
        expected_state_id=state_id,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [("sender", "Machine"), ("context_id", "other"), ("error", True), ("category", "error"), ("text", "edited")],
)
async def test_should_refuse_a_save_when_any_summary_field_of_the_batch_changed(client, field, value):  # noqa: ARG001
    flow_id, user_id = uuid4(), uuid4()
    ids = [await _add_message(flow_id, user_id, "s1", ts=T0 + timedelta(seconds=i)) for i in range(2)]
    snapshot = await _snapshot_of(*ids)
    async with session_scope() as session:
        await session.exec(update(MessageTable).where(MessageTable.id == ids[0]).values(**{field: value}))

    assert await _save_snapshot(_scope(flow_id, user_id), ids[1], snapshot) is None
    assert not await _has_state(flow_id, user_id)


async def test_should_roll_back_a_save_when_a_message_is_deleted_after_the_first_check(client):  # noqa: ARG001
    """SQLite ignores FOR UPDATE: a delete can commit between the first check and the write."""
    import langflow.memory as memory_module

    flow_id, user_id = uuid4(), uuid4()
    ids = [await _add_message(flow_id, user_id, "s1", ts=T0 + timedelta(seconds=i)) for i in range(2)]
    snapshot = await _snapshot_of(*ids)
    real_check = memory_module._batch_timestamps
    calls = []

    async def check_then_delete(*args, **kwargs):
        result = await real_check(*args, **kwargs)
        calls.append(kwargs["lock"])
        if len(calls) == 1:
            await delete_message(ids[0])  # commits in its own session, after the first check passed
        return result

    with patch.object(memory_module, "_batch_timestamps", new=check_then_delete):
        saved = await _save_snapshot(_scope(flow_id, user_id), ids[1], snapshot)

    assert calls == [True, False]
    assert saved is None
    assert not await _has_state(flow_id, user_id)


async def test_should_reject_a_stale_save_after_the_state_row_was_reset_and_re_created(client):  # noqa: ARG001
    flow_id, user_id = uuid4(), uuid4()
    scope = _scope(flow_id, user_id)
    ids = [await _add_message(flow_id, user_id, "s1", ts=T0 + timedelta(seconds=i), text=f"m{i}") for i in range(6)]
    assert await _save(scope, ids[1], 0) is not None
    stale_state = await aget_session_memory_state(**scope)
    assert stale_state.version == 1
    snapshot = await _snapshot_of(ids[2], ids[3])

    await aupdate_messages(Message(id=ids[0], text="edited"))  # reset: the row is deleted
    assert not await _has_state(flow_id, user_id)
    assert await _save(scope, ids[1], 0, summary="fresh") is not None  # re-created at version 1, new id
    fresh = await aget_session_memory_state(**scope)
    assert (fresh.version, fresh.id != stale_state.id) == (1, True)

    stale = await _save_snapshot(scope, ids[3], snapshot, version=1, state_id=stale_state.id)

    assert stale is None
    assert (await aget_session_memory_state(**scope)).summary == "fresh"


async def test_should_reset_a_folded_text_edit_with_three_indexed_statements(client):  # noqa: ARG001
    """A streamed text update costs two key reads and one DELETE, none of them a table scan."""
    from langflow.memory import reset_folded_memory_for_update
    from sqlalchemy import event

    flow_id, user_id = uuid4(), uuid4()
    ids = await _three_messages_with_state(flow_id, user_id)
    captured = []
    async with session_scope() as session:
        engine = session.bind.sync_engine
        message = await session.get(MessageTable, ids[0])

        def capture(_conn, _cursor, statement, parameters, _context, _executemany):
            captured.append((statement, parameters))

        event.listen(engine, "before_cursor_execute", capture)
        try:
            async with reset_folded_memory_for_update(session, message, {"text": "edited"}):
                message.text = "edited"
        finally:
            event.remove(engine, "before_cursor_execute", capture)
        extra = [(sql, params) for sql, params in captured if not sql.startswith("UPDATE message")]
        assert [sql.split()[0] for sql, _ in extra] == ["SELECT", "SELECT", "DELETE"], extra
        if engine.dialect.name == "sqlite":
            for sql, params in extra:
                plan = await session.run_sync(
                    lambda sync_session, sql=sql, params=params: list(
                        sync_session.connection().exec_driver_sql(f"EXPLAIN QUERY PLAN {sql}", params)
                    )
                )
                details = " | ".join(row[3] for row in plan)
                assert details.startswith("SEARCH"), details
                assert "SCAN" not in details, details
    assert not await _has_state(flow_id, user_id)


async def test_should_reset_the_new_session_when_an_edit_races_a_rename(client):  # noqa: ARG001
    flow_id, user_id = uuid4(), uuid4()
    ids = await _three_messages_with_state(flow_id, user_id, "A")
    async with session_scope() as edit_session:
        message = await edit_session.get(MessageTable, ids[0])  # the edit request loads the row in session A
        async with session_scope() as rename_session:  # a rename commits: messages and summary move to B
            rows = (await rename_session.exec(select(MessageTable).where(MessageTable.session_id == "A"))).all()
            async with rename_session_memory(rename_session, rows, "B"):
                for row in rows:
                    row.session_id = "B"
                rename_session.add_all(rows)
        assert await _has_state(flow_id, user_id, "B")
        updates = {"text": "edited"}
        async with reset_folded_memory_for_update(edit_session, message, updates):
            message.sqlmodel_update(updates)
            edit_session.add(message)

    assert not await _has_state(flow_id, user_id, "B")
    assert not await _has_state(flow_id, user_id, "A")


async def test_should_not_delete_state_of_a_virtual_flow_owned_by_a_legacy_row(client, active_user):  # noqa: ARG001
    victim = uuid4()
    virtual_flow_id = compute_virtual_flow_id(victim, uuid4(), principal_type="user")
    async with session_scope() as session:
        # A legacy flow row in the virtual id range, owned by someone else.
        session.add(Flow(id=virtual_flow_id, name=f"legacy-{virtual_flow_id}", user_id=active_user.id, data={}))
        session.add(SessionMemoryStateTable(flow_id=virtual_flow_id, user_id=victim, session_id="s", summary="v"))
    async with session_scope() as session:
        await _delete_session_summaries(session, active_user.id, ["s"])

    assert await _state_session_ids(virtual_flow_id) == {"s"}
