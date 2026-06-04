"""Tests for the collaboration event backplane and SQLite presence store."""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from langflow.services.collaboration_events import (
    CollaborationPollCursor,
    CollaborationPresenceChange,
    CollaborationPresenceChangeEnvelope,
    CollaborationPresenceConnectionUser,
    CollaborationSelectionTarget,
    CollaborationUserSelection,
    SQLiteCollaborationEventService,
)
from langflow.services.collaboration_events.factory import CollaborationEventServiceFactory


@pytest.fixture
def flow_id() -> UUID:
    return uuid4()


@pytest.fixture
def other_flow_id() -> UUID:
    return uuid4()


@pytest.fixture
async def svc(tmp_path):
    service = SQLiteCollaborationEventService(cache_dir=tmp_path / "cache")
    yield service
    await service.teardown()


def test_factory_returns_sqlite_implementation():
    from lfx.services.settings.factory import SettingsServiceFactory

    settings_service = SettingsServiceFactory().create()
    service = CollaborationEventServiceFactory().create(settings_service)
    assert isinstance(service, SQLiteCollaborationEventService)


async def test_publish_and_poll_by_flow_id(svc: SQLiteCollaborationEventService, flow_id: UUID):
    await svc.publish(flow_id, "operation.accepted", {"revision": 1, "forward_ops": []})
    await svc.publish(
        flow_id,
        "presence.joined",
        {"worker_id": "w1", "user": {"user_id": str(uuid4()), "username": "a"}},
    )

    events, cursor = await svc.poll(flow_id)
    assert len(events) == 2
    assert events[0].type == "operation.accepted"
    assert events[0].payload["revision"] == 1
    assert events[1].type == "presence.joined"
    assert cursor.event_id == events[1].id
    assert cursor.created_at == events[1].created_at


async def test_flow_isolation(svc: SQLiteCollaborationEventService, flow_id: UUID, other_flow_id: UUID):
    await svc.publish(flow_id, "operation.accepted", {"revision": 1})
    await svc.publish(other_flow_id, "operation.accepted", {"revision": 2})

    events_a, _ = await svc.poll(flow_id)
    events_b, _ = await svc.poll(other_flow_id)

    assert len(events_a) == 1
    assert events_a[0].payload["revision"] == 1
    assert len(events_b) == 1
    assert events_b[0].payload["revision"] == 2


async def test_poll_cursor_skips_seen_events(svc: SQLiteCollaborationEventService, flow_id: UUID):
    first = await svc.publish(flow_id, "operation.accepted", {"revision": 1})
    await svc.publish(flow_id, "operation.accepted", {"revision": 2})

    events, cursor = await svc.poll(
        flow_id,
        cursor=CollaborationPollCursor(created_at=first.created_at, event_id=first.id),
    )
    assert len(events) == 1
    assert events[0].payload["revision"] == 2
    assert cursor.event_id == events[0].id


async def test_poll_at_cursor_returns_empty(svc: SQLiteCollaborationEventService, flow_id: UUID):
    event = await svc.publish(flow_id, "operation.accepted", {"revision": 1})

    events, cursor = await svc.poll(
        flow_id,
        cursor=CollaborationPollCursor(created_at=event.created_at, event_id=event.id),
    )
    assert events == []
    assert cursor == CollaborationPollCursor(created_at=event.created_at, event_id=event.id)


async def test_ttl_expiry(svc: SQLiteCollaborationEventService, flow_id: UUID):
    svc.TTL_SECONDS = 0.1
    await svc.publish(flow_id, "operation.accepted", {"revision": 1})

    await asyncio.sleep(0.15)

    events, _ = await svc.poll(flow_id)
    assert events == []


async def test_cleanup_removes_expired(svc: SQLiteCollaborationEventService, flow_id: UUID):
    svc.TTL_SECONDS = 0.1
    await svc.publish(flow_id, "operation.accepted", {"revision": 1})

    await asyncio.sleep(0.15)
    await svc.cleanup()

    events, _ = await svc.poll(flow_id)
    assert events == []


async def test_per_flow_cap_eviction(svc: SQLiteCollaborationEventService, flow_id: UUID):
    svc.MAX_EVENTS_PER_FLOW = 3

    for revision in range(5):
        await svc.publish(flow_id, "operation.accepted", {"revision": revision})

    events, _ = await svc.poll(flow_id)
    assert len(events) == 3
    assert [event.payload["revision"] for event in events] == [2, 3, 4]


async def test_cross_worker_visibility(tmp_path, flow_id: UUID):
    """Two service instances sharing a cache_dir see each other's events."""
    shared = tmp_path / "shared"

    worker_a = SQLiteCollaborationEventService(cache_dir=shared)
    worker_b = SQLiteCollaborationEventService(cache_dir=shared)

    try:
        await worker_a.publish(flow_id, "operation.accepted", {"revision": 1})

        events, _ = await worker_b.poll(flow_id)
        assert len(events) == 1
        assert events[0].payload["revision"] == 1

        await worker_b.publish(
            flow_id, "selection.updated", {"worker_id": "w2", "user_id": str(uuid4()), "selected": None}
        )

        events, _ = await worker_a.poll(flow_id)
        assert len(events) == 2
    finally:
        await worker_a.teardown()
        await worker_b.teardown()


async def test_cross_worker_flow_isolation(tmp_path, flow_id: UUID, other_flow_id: UUID):
    shared = tmp_path / "shared"

    worker_a = SQLiteCollaborationEventService(cache_dir=shared)
    worker_b = SQLiteCollaborationEventService(cache_dir=shared)

    try:
        await worker_a.publish(flow_id, "operation.accepted", {"revision": 1})
        await worker_b.publish(other_flow_id, "operation.accepted", {"revision": 2})

        events_a, _ = await worker_b.poll(flow_id)
        events_b, _ = await worker_a.poll(other_flow_id)

        assert len(events_a) == 1
        assert events_a[0].payload["revision"] == 1
        assert len(events_b) == 1
        assert events_b[0].payload["revision"] == 2
    finally:
        await worker_a.teardown()
        await worker_b.teardown()


async def test_publish_requires_event_type(svc: SQLiteCollaborationEventService, flow_id: UUID):
    with pytest.raises(ValueError, match="event_type"):
        await svc.publish(flow_id, "", {})


def test_presence_change_fields_are_mutually_exclusive():
    user_id = uuid4()
    joined = CollaborationPresenceConnectionUser(user_id=user_id, username="alice")
    selection = CollaborationUserSelection(user_id=user_id, selected=None)

    CollaborationPresenceChange(joined=joined)
    CollaborationPresenceChange(left_user_id=user_id)
    CollaborationPresenceChange(selection_updated=selection)

    with pytest.raises(ValueError, match="exactly one"):
        CollaborationPresenceChange()

    with pytest.raises(ValueError, match="exactly one"):
        CollaborationPresenceChange(left_user_id=user_id, selection_updated=selection)


async def test_list_users_requires_flow_ids(svc: SQLiteCollaborationEventService):
    with pytest.raises(ValueError, match="flow_ids"):
        await svc.list_users([])


async def test_add_update_remove_and_list_presence(svc: SQLiteCollaborationEventService, flow_id: UUID):
    user_id = uuid4()
    conn_a = uuid4()
    conn_b = uuid4()

    joined = await svc.add_connection(
        flow_id=flow_id,
        user_id=user_id,
        connection_id=conn_a,
        username="alice",
        profile_image=None,
    )
    assert joined is not None
    assert joined.joined is not None
    assert joined.joined.username == "alice"

    snapshot = (await svc.list_users([flow_id]))[flow_id]
    assert len(snapshot.users) == 1

    second = await svc.add_connection(
        flow_id=flow_id,
        user_id=user_id,
        connection_id=conn_b,
        username="alice",
        profile_image=None,
    )
    assert second is None
    assert len((await svc.list_users([flow_id]))[flow_id].users) == 1

    change = await svc.update_connection(
        connection_id=conn_a,
        selected=CollaborationSelectionTarget(kind="node", id="node-1"),
    )
    assert change is not None
    assert change.selection_updated is not None
    assert change.selection_updated.selected == CollaborationSelectionTarget(kind="node", id="node-1")

    snapshot = (await svc.list_users([flow_id]))[flow_id]
    assert snapshot.users[0].selected == CollaborationSelectionTarget(kind="node", id="node-1")

    left = await svc.remove_connection(connection_id=conn_a)
    assert left is not None
    assert left.left_user_id is None
    assert left.selection_updated == CollaborationUserSelection(user_id=user_id, selected=None)
    assert len((await svc.list_users([flow_id]))[flow_id].users) == 1

    final = await svc.remove_connection(connection_id=conn_b)
    assert final is not None
    assert final.left_user_id == user_id
    assert final.selection_updated is None
    assert (await svc.list_users([flow_id]))[flow_id].users == []


async def test_remove_connections_batches_presence_changes(svc: SQLiteCollaborationEventService, flow_id: UUID):
    user_id = uuid4()
    other_user_id = uuid4()
    conn_a = uuid4()
    conn_b = uuid4()
    conn_c = uuid4()
    await svc.add_connection(
        flow_id=flow_id,
        user_id=user_id,
        connection_id=conn_a,
        username="alice",
        profile_image=None,
    )
    await svc.add_connection(
        flow_id=flow_id,
        user_id=user_id,
        connection_id=conn_b,
        username="alice",
        profile_image=None,
    )
    await svc.add_connection(
        flow_id=flow_id,
        user_id=other_user_id,
        connection_id=conn_c,
        username="bob",
        profile_image=None,
    )

    changes = await svc.remove_connections([conn_a, conn_c])

    assert changes == [
        CollaborationPresenceChangeEnvelope(
            flow_id=flow_id,
            change=CollaborationPresenceChange(left_user_id=other_user_id),
        )
    ]
    assert [user.user_id for user in (await svc.list_users([flow_id]))[flow_id].users] == [user_id]

    final_changes = await svc.remove_connections([conn_b])
    assert final_changes == [
        CollaborationPresenceChangeEnvelope(
            flow_id=flow_id,
            change=CollaborationPresenceChange(left_user_id=user_id),
        )
    ]
    assert (await svc.list_users([flow_id]))[flow_id].users == []


async def test_remove_connections_batches_effective_user_reads(svc: SQLiteCollaborationEventService, flow_id: UUID):
    user_ids = [uuid4() for _ in range(5)]
    connection_ids = []
    for index, user_id in enumerate(user_ids):
        connection_id = uuid4()
        connection_ids.append(connection_id)
        await svc.add_connection(
            flow_id=flow_id,
            user_id=user_id,
            connection_id=connection_id,
            username=f"user-{index}",
            profile_image=None,
        )

    conn = await svc._ensure_conn()
    traced_statements: list[str] = []
    await conn.set_trace_callback(lambda statement: traced_statements.append(statement.strip()))
    try:
        changes = await svc.remove_connections(connection_ids)
    finally:
        await conn.set_trace_callback(None)

    connection_reads = [
        statement
        for statement in traced_statements
        if statement.startswith("WITH") and "FROM connections AS c" in statement
    ]
    assert len(connection_reads) == 3
    assert {presence_change.flow_id for presence_change in changes} == {flow_id}
    assert {presence_change.change.left_user_id for presence_change in changes} == set(user_ids)


async def test_presence_ttl_cleanup(svc: SQLiteCollaborationEventService, flow_id: UUID):
    svc.PRESENCE_TTL_SECONDS = 0.1
    user_id = uuid4()
    conn_id = uuid4()
    await svc.add_connection(
        flow_id=flow_id,
        user_id=user_id,
        connection_id=conn_id,
        username="alice",
        profile_image=None,
    )
    assert len((await svc.list_users([flow_id]))[flow_id].users) == 1

    await asyncio.sleep(0.15)
    await svc.cleanup()

    assert (await svc.list_users([flow_id]))[flow_id].users == []


async def test_list_users_removes_expired_connections(svc: SQLiteCollaborationEventService, flow_id: UUID):
    svc.PRESENCE_TTL_SECONDS = 0.1
    user_id = uuid4()
    conn_id = uuid4()
    await svc.add_connection(
        flow_id=flow_id,
        user_id=user_id,
        connection_id=conn_id,
        username="alice",
        profile_image=None,
    )

    await asyncio.sleep(0.15)

    snapshots = await svc.list_users([flow_id])
    assert snapshots[flow_id].users == []
    assert (await svc.list_users([flow_id]))[flow_id].users == []


async def test_poll_does_not_consume_expired_presence_before_list_users(
    svc: SQLiteCollaborationEventService,
    flow_id: UUID,
):
    svc.PRESENCE_TTL_SECONDS = 0.1
    user_id = uuid4()
    conn_id = uuid4()
    await svc.add_connection(
        flow_id=flow_id,
        user_id=user_id,
        connection_id=conn_id,
        username="alice",
        profile_image=None,
    )

    await asyncio.sleep(0.15)
    await svc.publish(flow_id, "operation.accepted", {"revision": 1})
    await svc.poll(flow_id)

    snapshots = await svc.list_users([flow_id])
    assert snapshots[flow_id].users == []


async def test_list_users_batches_flow_snapshots(
    svc: SQLiteCollaborationEventService,
    flow_id: UUID,
    other_flow_id: UUID,
):
    svc.PRESENCE_TTL_SECONDS = 0.1
    expired_user_id = uuid4()
    active_user_id = uuid4()
    expired_conn_id = uuid4()
    active_conn_id = uuid4()
    await svc.add_connection(
        flow_id=flow_id,
        user_id=expired_user_id,
        connection_id=expired_conn_id,
        username="expired",
        profile_image=None,
    )
    svc.PRESENCE_TTL_SECONDS = 30.0
    await svc.add_connection(
        flow_id=other_flow_id,
        user_id=active_user_id,
        connection_id=active_conn_id,
        username="active",
        profile_image=None,
    )

    await asyncio.sleep(0.15)

    snapshots = await svc.list_users([flow_id, other_flow_id])
    assert snapshots[flow_id].users == []
    assert len(snapshots[other_flow_id].users) == 1
    assert snapshots[other_flow_id].users[0].user_id == active_user_id


async def test_effective_selection_uses_latest_connection(svc: SQLiteCollaborationEventService, flow_id: UUID):
    user_id = uuid4()
    conn_a = uuid4()
    conn_b = uuid4()
    await svc.add_connection(
        flow_id=flow_id,
        user_id=user_id,
        connection_id=conn_a,
        username="alice",
        profile_image=None,
    )
    await svc.add_connection(
        flow_id=flow_id,
        user_id=user_id,
        connection_id=conn_b,
        username="alice",
        profile_image=None,
    )
    await svc.update_connection(
        connection_id=conn_a,
        selected=CollaborationSelectionTarget(kind="node", id="old"),
    )
    await asyncio.sleep(0.01)
    await svc.update_connection(
        connection_id=conn_b,
        selected=CollaborationSelectionTarget(kind="edge", id="new"),
    )

    snapshot = (await svc.list_users([flow_id]))[flow_id]
    assert snapshot.users[0].selected == CollaborationSelectionTarget(kind="edge", id="new")


async def test_initial_connection_counts_as_currently_unselected(svc: SQLiteCollaborationEventService, flow_id: UUID):
    user_id = uuid4()
    conn_a = uuid4()
    conn_b = uuid4()
    await svc.add_connection(
        flow_id=flow_id,
        user_id=user_id,
        connection_id=conn_a,
        username="alice",
        profile_image=None,
    )
    await svc.update_connection(
        connection_id=conn_a,
        selected=CollaborationSelectionTarget(kind="node", id="old"),
    )
    await asyncio.sleep(0.01)
    await svc.add_connection(
        flow_id=flow_id,
        user_id=user_id,
        connection_id=conn_b,
        username="alice",
        profile_image=None,
    )

    snapshot = (await svc.list_users([flow_id]))[flow_id]
    assert snapshot.users[0].selected is None


async def test_new_distinct_user_snapshot_preserves_existing_user_selection(
    svc: SQLiteCollaborationEventService,
    flow_id: UUID,
):
    selected_user_id = uuid4()
    joining_user_id = uuid4()
    selected_conn_id = uuid4()
    joining_conn_id = uuid4()

    await svc.add_connection(
        flow_id=flow_id,
        user_id=selected_user_id,
        connection_id=selected_conn_id,
        username="selected-user",
        profile_image=None,
    )
    await svc.update_connection(
        connection_id=selected_conn_id,
        selected=CollaborationSelectionTarget(kind="node", id="node-1"),
    )

    await svc.add_connection(
        flow_id=flow_id,
        user_id=joining_user_id,
        connection_id=joining_conn_id,
        username="joining-user",
        profile_image=None,
    )

    snapshot = (await svc.list_users([flow_id]))[flow_id]
    users_by_id = {user.user_id: user for user in snapshot.users}

    assert users_by_id[selected_user_id].selected == CollaborationSelectionTarget(kind="node", id="node-1")
    assert users_by_id[joining_user_id].selected is None


async def test_cross_worker_presence_visibility(tmp_path, flow_id: UUID):
    shared = tmp_path / "shared"
    user_id = uuid4()
    conn_id = uuid4()

    worker_a = SQLiteCollaborationEventService(cache_dir=shared)
    worker_b = SQLiteCollaborationEventService(cache_dir=shared)

    try:
        await worker_a.add_connection(
            flow_id=flow_id,
            user_id=user_id,
            connection_id=conn_id,
            username="bob",
            profile_image=None,
        )

        snapshot = (await worker_b.list_users([flow_id]))[flow_id]
        assert len(snapshot.users) == 1
        assert snapshot.users[0].username == "bob"
    finally:
        await worker_a.teardown()
        await worker_b.teardown()
