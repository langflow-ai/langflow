import time

from langflow.services.flow_events.service import FlowEventsService


def test_append_and_get_events(tmp_path):
    svc = FlowEventsService(cache_dir=tmp_path / "cache")
    svc.append("flow-1", "component_added", "Added OpenAI")
    svc.append("flow-1", "connection_added", "Connected to Chat Output")

    events, settled = svc.get_since("flow-1", 0.0)
    assert len(events) == 2
    assert events[0].type == "component_added"
    assert events[1].type == "connection_added"
    assert not settled


def test_get_since_filters_by_timestamp(tmp_path):
    svc = FlowEventsService(cache_dir=tmp_path / "cache")
    e1 = svc.append("flow-1", "component_added", "First")
    svc.append("flow-1", "component_added", "Second")

    events, _ = svc.get_since("flow-1", e1.timestamp)
    assert len(events) == 1
    assert events[0].summary == "Second"


def test_settled_on_flow_settled_event(tmp_path):
    svc = FlowEventsService(cache_dir=tmp_path / "cache")
    svc.append("flow-1", "component_added", "Added something")
    svc.append("flow-1", "flow_settled", "Done")

    events, settled = svc.get_since("flow-1", 0.0)
    assert settled is True
    assert any(e.type == "flow_settled" for e in events)


def test_settled_on_timeout(tmp_path):
    svc = FlowEventsService(cache_dir=tmp_path / "cache")
    svc.SETTLE_TIMEOUT = 0.1
    svc.append("flow-1", "component_added", "Added something")

    time.sleep(0.15)

    _, settled = svc.get_since("flow-1", 0.0)
    assert settled is True


def test_empty_flow_returns_settled(tmp_path):
    svc = FlowEventsService(cache_dir=tmp_path / "cache")
    events, settled = svc.get_since("nonexistent", 0.0)
    assert events == []
    assert settled is True


def test_ttl_cleanup(tmp_path):
    svc = FlowEventsService(cache_dir=tmp_path / "cache")
    svc.TTL_SECONDS = 0.1
    svc.append("flow-1", "component_added", "Old event")

    time.sleep(0.15)

    # Force re-append to reset TTL for the key, then read
    # Actually just read -- the key should have expired via diskcache expire
    events, _ = svc.get_since("flow-1", 0.0)
    assert len(events) == 0


def test_cursor_ahead_of_all_events_not_settled(tmp_path):
    svc = FlowEventsService(cache_dir=tmp_path / "cache")
    e = svc.append("flow-1", "component_added", "Added something")

    events, settled = svc.get_since("flow-1", e.timestamp + 1.0)
    assert events == []
    assert settled is False  # last event is recent, not past SETTLE_TIMEOUT


def test_cursor_ahead_of_all_events_settled_after_timeout(tmp_path):
    svc = FlowEventsService(cache_dir=tmp_path / "cache")
    svc.SETTLE_TIMEOUT = 0.1
    svc.append("flow-1", "component_added", "Added something")

    time.sleep(0.15)

    events, settled = svc.get_since("flow-1", time.time())
    assert events == []
    assert settled is True  # last event is past SETTLE_TIMEOUT


def test_flow_settled_before_cursor_does_not_settle(tmp_path):
    svc = FlowEventsService(cache_dir=tmp_path / "cache")
    settled_event = svc.append("flow-1", "flow_settled", "Done")
    svc.append("flow-1", "component_added", "Added after settle")

    events, settled = svc.get_since("flow-1", settled_event.timestamp)
    assert len(events) == 1
    assert events[0].type == "component_added"
    assert settled is False  # flow_settled is before cursor, should not trigger


def test_different_flows_isolated(tmp_path):
    svc = FlowEventsService(cache_dir=tmp_path / "cache")
    svc.append("flow-1", "component_added", "Flow 1")
    svc.append("flow-2", "connection_added", "Flow 2")

    events_1, _ = svc.get_since("flow-1", 0.0)
    events_2, _ = svc.get_since("flow-2", 0.0)

    assert len(events_1) == 1
    assert events_1[0].summary == "Flow 1"
    assert len(events_2) == 1
    assert events_2[0].summary == "Flow 2"


def test_max_events_per_flow_cap(tmp_path):
    svc = FlowEventsService(cache_dir=tmp_path / "cache")
    svc.MAX_EVENTS_PER_FLOW = 5

    for i in range(10):
        svc.append("flow-1", "component_added", f"Event {i}")

    events, _ = svc.get_since("flow-1", 0.0)
    assert len(events) == 5
    # Should keep the most recent 5
    assert events[0].summary == "Event 5"
    assert events[-1].summary == "Event 9"


def test_cross_worker_visibility(tmp_path):
    """Two separate service instances sharing the same cache dir can see each other's events.

    This simulates two uvicorn/gunicorn workers writing and reading from the same disk cache.
    """
    shared_dir = tmp_path / "shared_cache"

    worker_a = FlowEventsService(cache_dir=shared_dir)
    worker_b = FlowEventsService(cache_dir=shared_dir)

    # Worker A appends an event
    worker_a.append("flow-1", "component_added", "Added by worker A")

    # Worker B should see it
    events, settled = worker_b.get_since("flow-1", 0.0)
    assert len(events) == 1
    assert events[0].summary == "Added by worker A"
    assert not settled

    # Worker B appends another event
    worker_b.append("flow-1", "connection_added", "Connected by worker B")

    # Worker A should see both
    events, _ = worker_a.get_since("flow-1", 0.0)
    assert len(events) == 2
    assert events[0].summary == "Added by worker A"
    assert events[1].summary == "Connected by worker B"


def test_cross_worker_settle(tmp_path):
    """Worker A emits events, worker B emits flow_settled, worker A sees settled=True."""
    shared_dir = tmp_path / "shared_cache"

    worker_a = FlowEventsService(cache_dir=shared_dir)
    worker_b = FlowEventsService(cache_dir=shared_dir)

    worker_a.append("flow-1", "component_added", "Work in progress")
    worker_b.append("flow-1", "flow_settled", "Done")

    events, settled = worker_a.get_since("flow-1", 0.0)
    assert settled is True
    assert len(events) == 2


def test_cross_worker_flow_isolation(tmp_path):
    """Events from different flows don't leak across workers."""
    shared_dir = tmp_path / "shared_cache"

    worker_a = FlowEventsService(cache_dir=shared_dir)
    worker_b = FlowEventsService(cache_dir=shared_dir)

    worker_a.append("flow-1", "component_added", "Flow 1 event")
    worker_b.append("flow-2", "component_added", "Flow 2 event")

    events_1, _ = worker_b.get_since("flow-1", 0.0)
    events_2, _ = worker_a.get_since("flow-2", 0.0)

    assert len(events_1) == 1
    assert events_1[0].summary == "Flow 1 event"
    assert len(events_2) == 1
    assert events_2[0].summary == "Flow 2 event"


def test_cross_worker_ttl_expiry(tmp_path):
    """Expired events are invisible to all workers."""
    shared_dir = tmp_path / "shared_cache"

    worker_a = FlowEventsService(cache_dir=shared_dir)
    worker_a.TTL_SECONDS = 0.1
    worker_a.append("flow-1", "component_added", "Short-lived event")

    time.sleep(0.15)

    worker_b = FlowEventsService(cache_dir=shared_dir)
    events, _ = worker_b.get_since("flow-1", 0.0)
    assert len(events) == 0
