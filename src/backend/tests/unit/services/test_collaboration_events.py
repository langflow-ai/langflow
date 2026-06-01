"""Tests for the collaboration event backplane and SQLite presence store."""

from __future__ import annotations

import time
from uuid import UUID, uuid4

import pytest
from langflow.services.collaboration_events import (
    CollaborationPollCursor,
    CollaborationPresenceChange,
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
def svc(tmp_path):
    return SQLiteCollaborationEventService(cache_dir=tmp_path / "cache")


def test_factory_returns_sqlite_implementation():
    from lfx.services.settings.factory import SettingsServiceFactory

    settings_service = SettingsServiceFactory().create()
    service = CollaborationEventServiceFactory().create(settings_service)
    assert isinstance(service, SQLiteCollaborationEventService)


def test_publish_and_poll_by_flow_id(svc: SQLiteCollaborationEventService, flow_id: UUID):
    svc.publish(flow_id, "operation.accepted", {"revision": 1, "forward_ops": []})
    svc.publish(flow_id, "presence.joined", {"worker_id": "w1", "user": {"user_id": str(uuid4()), "username": "a"}})

    events, cursor = svc.poll(flow_id)
    assert len(events) == 2
    assert events[0].type == "operation.accepted"
    assert events[0].payload["revision"] == 1
    assert events[1].type == "presence.joined"
    assert cursor.event_id == events[1].id
    assert cursor.created_at == events[1].created_at


def test_flow_isolation(svc: SQLiteCollaborationEventService, flow_id: UUID, other_flow_id: UUID):
    svc.publish(flow_id, "operation.accepted", {"revision": 1})
    svc.publish(other_flow_id, "operation.accepted", {"revision": 2})

    events_a, _ = svc.poll(flow_id)
    events_b, _ = svc.poll(other_flow_id)

    assert len(events_a) == 1
    assert events_a[0].payload["revision"] == 1
    assert len(events_b) == 1
    assert events_b[0].payload["revision"] == 2


def test_poll_cursor_skips_seen_events(svc: SQLiteCollaborationEventService, flow_id: UUID):
    first = svc.publish(flow_id, "operation.accepted", {"revision": 1})
    svc.publish(flow_id, "operation.accepted", {"revision": 2})

    events, cursor = svc.poll(
        flow_id,
        cursor=CollaborationPollCursor(created_at=first.created_at, event_id=first.id),
    )
    assert len(events) == 1
    assert events[0].payload["revision"] == 2
    assert cursor.event_id == events[0].id


def test_poll_at_cursor_returns_empty(svc: SQLiteCollaborationEventService, flow_id: UUID):
    event = svc.publish(flow_id, "operation.accepted", {"revision": 1})

    events, cursor = svc.poll(
        flow_id,
        cursor=CollaborationPollCursor(created_at=event.created_at, event_id=event.id),
    )
    assert events == []
    assert cursor == CollaborationPollCursor(created_at=event.created_at, event_id=event.id)


def test_ttl_expiry(svc: SQLiteCollaborationEventService, flow_id: UUID):
    svc.TTL_SECONDS = 0.1
    svc.publish(flow_id, "operation.accepted", {"revision": 1})

    time.sleep(0.15)

    events, _ = svc.poll(flow_id)
    assert events == []


def test_cleanup_removes_expired(svc: SQLiteCollaborationEventService, flow_id: UUID):
    svc.TTL_SECONDS = 0.1
    svc.publish(flow_id, "operation.accepted", {"revision": 1})

    time.sleep(0.15)
    svc.cleanup()

    events, _ = svc.poll(flow_id)
    assert events == []


def test_per_flow_cap_eviction(svc: SQLiteCollaborationEventService, flow_id: UUID):
    svc.MAX_EVENTS_PER_FLOW = 3

    for revision in range(5):
        svc.publish(flow_id, "operation.accepted", {"revision": revision})

    events, _ = svc.poll(flow_id)
    assert len(events) == 3
    assert [event.payload["revision"] for event in events] == [2, 3, 4]


def test_cross_worker_visibility(tmp_path, flow_id: UUID):
    """Two service instances sharing a cache_dir see each other's events."""
    shared = tmp_path / "shared"

    worker_a = SQLiteCollaborationEventService(cache_dir=shared)
    worker_b = SQLiteCollaborationEventService(cache_dir=shared)

    worker_a.publish(flow_id, "operation.accepted", {"revision": 1})

    events, _ = worker_b.poll(flow_id)
    assert len(events) == 1
    assert events[0].payload["revision"] == 1

    worker_b.publish(flow_id, "selection.updated", {"worker_id": "w2", "user_id": str(uuid4()), "selected": None})

    events, _ = worker_a.poll(flow_id)
    assert len(events) == 2


def test_cross_worker_flow_isolation(tmp_path, flow_id: UUID, other_flow_id: UUID):
    shared = tmp_path / "shared"

    worker_a = SQLiteCollaborationEventService(cache_dir=shared)
    worker_b = SQLiteCollaborationEventService(cache_dir=shared)

    worker_a.publish(flow_id, "operation.accepted", {"revision": 1})
    worker_b.publish(other_flow_id, "operation.accepted", {"revision": 2})

    events_a, _ = worker_b.poll(flow_id)
    events_b, _ = worker_a.poll(other_flow_id)

    assert len(events_a) == 1
    assert events_a[0].payload["revision"] == 1
    assert len(events_b) == 1
    assert events_b[0].payload["revision"] == 2


def test_publish_requires_event_type(svc: SQLiteCollaborationEventService, flow_id: UUID):
    with pytest.raises(ValueError, match="event_type"):
        svc.publish(flow_id, "", {})


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


def test_add_update_remove_and_list_presence(svc: SQLiteCollaborationEventService, flow_id: UUID):
    user_id = uuid4()
    conn_a = "conn-a"
    conn_b = "conn-b"

    joined = svc.add_connection(
        flow_id=flow_id,
        user_id=user_id,
        connection_id=conn_a,
        username="alice",
        profile_image=None,
    )
    assert joined is not None
    assert joined.joined is not None
    assert joined.joined.username == "alice"

    snapshot = svc.list_users(flow_id)
    assert len(snapshot.users) == 1

    second = svc.add_connection(
        flow_id=flow_id,
        user_id=user_id,
        connection_id=conn_b,
        username="alice",
        profile_image=None,
    )
    assert second is None
    assert len(svc.list_users(flow_id).users) == 1

    change = svc.update_connection(
        flow_id=flow_id,
        connection_id=conn_a,
        selected=CollaborationSelectionTarget(kind="node", id="node-1"),
    )
    assert change is not None
    assert change.selection_updated is not None
    assert change.selection_updated.selected == CollaborationSelectionTarget(kind="node", id="node-1")

    snapshot = svc.list_users(flow_id)
    assert snapshot.users[0].selected == CollaborationSelectionTarget(kind="node", id="node-1")

    left = svc.remove_connection(flow_id=flow_id, connection_id=conn_a)
    assert left is not None
    assert left.left_user_id is None
    assert left.selection_updated == CollaborationUserSelection(user_id=user_id, selected=None)
    assert len(svc.list_users(flow_id).users) == 1

    final = svc.remove_connection(flow_id=flow_id, connection_id=conn_b)
    assert final is not None
    assert final.left_user_id == user_id
    assert final.selection_updated is None
    assert svc.list_users(flow_id).users == []


def test_presence_ttl_cleanup(svc: SQLiteCollaborationEventService, flow_id: UUID):
    svc.PRESENCE_TTL_SECONDS = 0.1
    user_id = uuid4()
    svc.add_connection(
        flow_id=flow_id,
        user_id=user_id,
        connection_id="conn-1",
        username="alice",
        profile_image=None,
    )
    assert len(svc.list_users(flow_id).users) == 1

    time.sleep(0.15)
    svc.cleanup()

    assert svc.list_users(flow_id).users == []


def test_effective_selection_uses_latest_connection(svc: SQLiteCollaborationEventService, flow_id: UUID):
    user_id = uuid4()
    svc.add_connection(
        flow_id=flow_id,
        user_id=user_id,
        connection_id="conn-a",
        username="alice",
        profile_image=None,
    )
    svc.add_connection(
        flow_id=flow_id,
        user_id=user_id,
        connection_id="conn-b",
        username="alice",
        profile_image=None,
    )
    svc.update_connection(
        flow_id=flow_id,
        connection_id="conn-a",
        selected=CollaborationSelectionTarget(kind="node", id="old"),
    )
    time.sleep(0.01)
    svc.update_connection(
        flow_id=flow_id,
        connection_id="conn-b",
        selected=CollaborationSelectionTarget(kind="edge", id="new"),
    )

    snapshot = svc.list_users(flow_id)
    assert snapshot.users[0].selected == CollaborationSelectionTarget(kind="edge", id="new")


def test_cross_worker_presence_visibility(tmp_path, flow_id: UUID):
    shared = tmp_path / "shared"
    user_id = uuid4()

    worker_a = SQLiteCollaborationEventService(cache_dir=shared)
    worker_b = SQLiteCollaborationEventService(cache_dir=shared)

    worker_a.add_connection(
        flow_id=flow_id,
        user_id=user_id,
        connection_id="remote-conn",
        username="bob",
        profile_image=None,
    )

    snapshot = worker_b.list_users(flow_id)
    assert len(snapshot.users) == 1
    assert snapshot.users[0].username == "bob"
