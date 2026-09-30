import multiprocessing
import time

from lfx.services.extension_events.service import ExtensionEventsService


def _worker_emit(cache_dir, event_type, payload):
    """Top-level helper for multiprocessing tests; must be picklable."""
    svc = ExtensionEventsService(cache_dir=cache_dir)
    svc.emit(event_type, payload)


# ---------------------------------------------------------------------------
# Basic emit / since
# ---------------------------------------------------------------------------


def test_emit_and_since(tmp_path):
    svc = ExtensionEventsService(cache_dir=tmp_path / "cache")
    svc.emit("bundle_reloaded", {"bundle": "my-ext", "reload_id": "r1"})
    svc.emit("bundle_reload_failed", {"bundle": "my-ext", "reload_id": "r2"})

    events, settled = svc.since(0.0)
    assert len(events) == 2
    assert events[0].type == "bundle_reloaded"
    assert events[1].type == "bundle_reload_failed"
    assert events[0].payload["bundle"] == "my-ext"
    assert not settled


def test_since_filters_by_timestamp(tmp_path):
    svc = ExtensionEventsService(cache_dir=tmp_path / "cache")
    e1 = svc.emit("bundle_reloaded", {"bundle": "a"})
    svc.emit("flow_migrated", {"flow_id": "f1"})

    events, _ = svc.since(e1.timestamp)
    assert len(events) == 1
    assert events[0].type == "flow_migrated"


def test_cursor_at_or_before_event_excluded(tmp_path):
    svc = ExtensionEventsService(cache_dir=tmp_path / "cache")
    e1 = svc.emit("bundle_reloaded", {"bundle": "a"})

    events, _ = svc.since(e1.timestamp)
    assert events == []


def test_empty_keyspace_returns_settled(tmp_path):
    svc = ExtensionEventsService(cache_dir=tmp_path / "cache")
    events, settled = svc.since(0.0)
    assert events == []
    assert settled is True


# ---------------------------------------------------------------------------
# Settled logic
# ---------------------------------------------------------------------------


def test_settled_on_timeout(tmp_path):
    svc = ExtensionEventsService(cache_dir=tmp_path / "cache")
    svc.SETTLE_TIMEOUT = 0.1
    svc.emit("bundle_reloaded", {"bundle": "a"})

    time.sleep(0.15)

    _, settled = svc.since(0.0)
    assert settled is True


def test_not_settled_with_recent_event(tmp_path):
    svc = ExtensionEventsService(cache_dir=tmp_path / "cache")
    svc.emit("bundle_reloaded", {"bundle": "a"})

    _, settled = svc.since(0.0)
    assert settled is False


# ---------------------------------------------------------------------------
# TTL expiry
# ---------------------------------------------------------------------------


def test_ttl_expiry(tmp_path):
    svc = ExtensionEventsService(cache_dir=tmp_path / "cache")
    svc.TTL_SECONDS = 0.1
    svc.emit("bundle_reloaded", {"bundle": "a"})

    time.sleep(0.15)

    events, _ = svc.since(0.0)
    assert len(events) == 0


def test_cleanup_removes_expired(tmp_path):
    svc = ExtensionEventsService(cache_dir=tmp_path / "cache")
    svc.TTL_SECONDS = 0.1
    svc.emit("bundle_reloaded", {"bundle": "a"})

    time.sleep(0.15)
    svc.cleanup()

    events, _ = svc.since(0.0)
    assert len(events) == 0


# ---------------------------------------------------------------------------
# Global cap eviction
# ---------------------------------------------------------------------------


def test_global_cap_eviction(tmp_path):
    svc = ExtensionEventsService(cache_dir=tmp_path / "cache")
    svc.MAX_EVENTS = 5

    for i in range(10):
        svc.emit("bundle_reloaded", {"bundle": f"b{i}"})

    events, _ = svc.since(0.0)
    assert len(events) == 5
    # Should keep the 5 most recent
    assert events[0].payload["bundle"] == "b5"
    assert events[-1].payload["bundle"] == "b9"


# ---------------------------------------------------------------------------
# Invalid event type
# ---------------------------------------------------------------------------


def test_invalid_event_type_raises(tmp_path):
    svc = ExtensionEventsService(cache_dir=tmp_path / "cache")
    import pytest

    with pytest.raises(ValueError, match="Invalid event type"):
        svc.emit("not_a_real_event", {})


# ---------------------------------------------------------------------------
# Keyspace isolation
# ---------------------------------------------------------------------------


def test_keyspace_isolation(tmp_path):
    svc = ExtensionEventsService(cache_dir=tmp_path / "cache")
    svc.emit("bundle_reloaded", {"bundle": "a"}, keyspace="global")
    svc.emit("flow_migrated", {"flow_id": "f1"}, keyspace="session:abc")

    global_events, _ = svc.since(0.0, keyspace="global")
    session_events, _ = svc.since(0.0, keyspace="session:abc")

    assert len(global_events) == 1
    assert global_events[0].type == "bundle_reloaded"

    assert len(session_events) == 1
    assert session_events[0].type == "flow_migrated"


# ---------------------------------------------------------------------------
# Cross-worker visibility (same process, two service instances)
# ---------------------------------------------------------------------------


def test_cross_worker_visibility(tmp_path):
    """Two service instances sharing a cache_dir see each other's events."""
    shared = tmp_path / "shared"

    worker_a = ExtensionEventsService(cache_dir=shared)
    worker_b = ExtensionEventsService(cache_dir=shared)

    worker_a.emit("bundle_reloaded", {"bundle": "a", "reload_id": "r1"})

    events, _ = worker_b.since(0.0)
    assert len(events) == 1
    assert events[0].payload["bundle"] == "a"

    worker_b.emit("bundle_reload_failed", {"bundle": "b", "reload_id": "r2"})

    events, _ = worker_a.since(0.0)
    assert len(events) == 2


def test_cross_worker_keyspace_isolation(tmp_path):
    shared = tmp_path / "shared"

    worker_a = ExtensionEventsService(cache_dir=shared)
    worker_b = ExtensionEventsService(cache_dir=shared)

    worker_a.emit("bundle_reloaded", {"bundle": "a"}, keyspace="global")
    worker_b.emit("flow_migrated", {"flow_id": "f1"}, keyspace="session:xyz")

    global_events, _ = worker_b.since(0.0, keyspace="global")
    session_events, _ = worker_a.since(0.0, keyspace="session:xyz")

    assert len(global_events) == 1
    assert len(session_events) == 1


def test_cross_worker_ttl_expiry(tmp_path):
    """Expired events are invisible to all workers."""
    shared = tmp_path / "shared"

    worker_a = ExtensionEventsService(cache_dir=shared)
    worker_a.TTL_SECONDS = 0.1
    worker_a.emit("bundle_reloaded", {"bundle": "a"})

    time.sleep(0.15)

    worker_b = ExtensionEventsService(cache_dir=shared)
    events, _ = worker_b.since(0.0)
    assert len(events) == 0


# ---------------------------------------------------------------------------
# Multi-process visibility
# ---------------------------------------------------------------------------


def test_multi_process_visibility(tmp_path):
    """A separate OS process can write events that this process reads."""
    shared = tmp_path / "shared"

    ctx = multiprocessing.get_context("spawn")
    proc = ctx.Process(
        target=_worker_emit,
        args=(str(shared), "bundle_reloaded", {"bundle": "from-child", "reload_id": "mp-1"}),
    )
    proc.start()
    proc.join(timeout=10)
    assert proc.exitcode == 0, "Child process failed to emit event"

    reader = ExtensionEventsService(cache_dir=shared)
    events, _ = reader.since(0.0)
    assert len(events) == 1
    assert events[0].payload["bundle"] == "from-child"
