"""Concurrency regressions for the process-local warm graph registry."""

from __future__ import annotations

import asyncio
import contextlib
import threading
from types import SimpleNamespace
from uuid import UUID

import orjson
import pytest
from langflow.services.database.models.flow.model import FlowRead
from langflow.services.warm_registry import reconcile as reconcile_mod
from langflow.services.warm_registry.service import WarmGraphRegistry, WarmRegistryCapacityError


class _FakeGraph:
    """Small graph sentinel that records which payload produced it."""

    def __init__(self, marker: str) -> None:
        self.marker = marker


def _flow_snapshot(
    flow_id: UUID,
    owner_id: UUID,
    endpoint_name: str,
    marker: str,
    *,
    name: str = "Flow",
) -> FlowRead:
    return FlowRead(
        id=flow_id,
        name=name,
        data={"nodes": [], "edges": [], "marker": marker},
        user_id=owner_id,
        folder_id=None,
        endpoint_name=endpoint_name,
    )


async def test_concurrent_same_version_adds_build_once(monkeypatch):
    """Concurrent cache misses for one flow/version share a single build."""
    loop = asyncio.get_running_loop()
    build_started = asyncio.Event()
    release_build = threading.Event()
    build_calls: list[str] = []

    def _blocking_build(flow_id: str, name: str | None, data: dict) -> _FakeGraph:  # noqa: ARG001
        build_calls.append(data["marker"])
        loop.call_soon_threadsafe(build_started.set)
        if not release_build.wait(timeout=5):
            msg = "timed out waiting to release registry build"
            raise TimeoutError(msg)
        return _FakeGraph(data["marker"])

    monkeypatch.setattr(WarmGraphRegistry, "_build", staticmethod(_blocking_build))
    registry = WarmGraphRegistry()

    first = asyncio.create_task(registry.add("flow-1", "Flow", {"marker": "same"}, "v1"))
    await asyncio.wait_for(build_started.wait(), timeout=1)
    second = asyncio.create_task(registry.add("flow-1", "Flow", {"marker": "same"}, "v1"))
    await asyncio.sleep(0)

    release_build.set()
    await asyncio.gather(first, second)

    assert build_calls == ["same"]
    assert registry.get("flow-1")[1] == "v1"


async def test_queued_newer_version_replaces_older_build(monkeypatch):
    """A newer version queued behind an older build is the final resident entry."""
    loop = asyncio.get_running_loop()
    old_build_started = asyncio.Event()
    release_old_build = threading.Event()
    build_calls: list[str] = []

    def _blocking_old_build(flow_id: str, name: str | None, data: dict) -> _FakeGraph:  # noqa: ARG001
        marker = data["marker"]
        build_calls.append(marker)
        if marker == "old":
            loop.call_soon_threadsafe(old_build_started.set)
            if not release_old_build.wait(timeout=5):
                msg = "timed out waiting to release old registry build"
                raise TimeoutError(msg)
        return _FakeGraph(marker)

    monkeypatch.setattr(WarmGraphRegistry, "_build", staticmethod(_blocking_old_build))
    registry = WarmGraphRegistry()

    older = asyncio.create_task(registry.add("flow-1", "Flow", {"marker": "old"}, "v1"))
    await asyncio.wait_for(old_build_started.wait(), timeout=1)
    newer = asyncio.create_task(registry.add("flow-1", "Flow", {"marker": "new"}, "v2"))
    await asyncio.sleep(0)

    release_old_build.set()
    await asyncio.gather(older, newer)

    graph, version = registry.get("flow-1")
    assert (graph.marker, version) == ("new", "v2")
    assert build_calls == ["old", "new"]


async def test_late_older_version_cannot_overwrite_newer_build(monkeypatch):
    """An older request queued while a newer build runs is discarded on recheck."""
    loop = asyncio.get_running_loop()
    new_build_started = asyncio.Event()
    release_new_build = threading.Event()
    build_calls: list[str] = []

    def _blocking_new_build(flow_id: str, name: str | None, data: dict) -> _FakeGraph:  # noqa: ARG001
        marker = data["marker"]
        build_calls.append(marker)
        if marker == "new":
            loop.call_soon_threadsafe(new_build_started.set)
            if not release_new_build.wait(timeout=5):
                msg = "timed out waiting to release new registry build"
                raise TimeoutError(msg)
        return _FakeGraph(marker)

    monkeypatch.setattr(WarmGraphRegistry, "_build", staticmethod(_blocking_new_build))
    registry = WarmGraphRegistry()

    newer = asyncio.create_task(registry.add("flow-1", "Flow", {"marker": "new"}, "v2"))
    await asyncio.wait_for(new_build_started.wait(), timeout=1)
    older = asyncio.create_task(registry.add("flow-1", "Flow", {"marker": "old"}, "v1"))
    await asyncio.sleep(0)

    release_new_build.set()
    await asyncio.gather(newer, older)

    graph, version = registry.get("flow-1")
    assert (graph.marker, version) == ("new", "v2")
    assert build_calls == ["new"]


async def test_failed_newer_build_evicts_and_tombstones_stale_entry(monkeypatch):
    """A failed changed-data build cannot leave or later resurrect the old graph."""
    build_calls: list[str] = []

    def _build(flow_id: str, name: str | None, data: dict) -> _FakeGraph:  # noqa: ARG001
        marker = data["marker"]
        build_calls.append(marker)
        if data.get("fail"):
            msg = "invalid changed flow"
            raise ValueError(msg)
        return _FakeGraph(marker)

    monkeypatch.setattr(WarmGraphRegistry, "_build", staticmethod(_build))
    registry = WarmGraphRegistry()
    await registry.add("flow-1", "Flow", {"marker": "old"}, "v1")

    with pytest.raises(ValueError, match="invalid changed flow"):
        await registry.add("flow-1", "Flow", {"marker": "broken", "fail": True}, "v2")

    assert registry.get("flow-1") is None

    # A delayed observation of v1 must not resurrect the known-stale template.
    await registry.add("flow-1", "Flow", {"marker": "old-again"}, "v1")
    assert registry.get("flow-1") is None
    assert build_calls == ["old", "broken"]

    # The failed revision backs off until the database advances its version.
    await registry.add("flow-1", "Flow", {"marker": "repaired"}, "v3")
    graph, version = registry.get("flow-1")
    assert (graph.marker, version) == ("repaired", "v3")


async def test_failed_same_version_metadata_revision_blocks_older_snapshot(monkeypatch):
    """A failed metadata revision tombstones delayed snapshots with the same timestamp."""
    build_calls: list[str] = []

    def _build(flow_id: str, name: str | None, data: dict) -> _FakeGraph:  # noqa: ARG001
        marker = data["marker"]
        build_calls.append(marker)
        if marker == "broken":
            msg = "invalid renamed flow"
            raise ValueError(msg)
        return _FakeGraph(marker)

    monkeypatch.setattr(WarmGraphRegistry, "_build", staticmethod(_build))
    registry = WarmGraphRegistry()
    flow_id = UUID("00000000-0000-0000-0000-000000000021")
    owner_id = UUID("00000000-0000-0000-0000-000000000022")
    old = _flow_snapshot(flow_id, owner_id, "old-endpoint", "old")
    broken = _flow_snapshot(flow_id, owner_id, "new-endpoint", "broken", name="Renamed")

    await registry.add(str(flow_id), old.name, old.data, "v1", flow=old)
    old_revision = registry.revision_of(str(flow_id))
    assert old_revision is not None
    assert await registry.evict_if_revision(str(flow_id), old_revision) is True
    with pytest.raises(ValueError, match="invalid renamed flow"):
        await registry.add(str(flow_id), broken.name, broken.data, "v1", flow=broken)

    assert registry.get(str(flow_id)) is None
    await registry.add(str(flow_id), old.name, old.data, "v1", flow=old)
    assert registry.get(str(flow_id)) is None
    assert registry.get_flow_by_endpoint(owner_id, "old-endpoint") is None
    assert build_calls == ["old", "broken"]

    repaired = _flow_snapshot(flow_id, owner_id, "new-endpoint", "repaired", name="Renamed")
    await registry.add(str(flow_id), repaired.name, repaired.data, "v2", flow=repaired)
    assert registry.get_flow_by_endpoint(owner_id, "new-endpoint") is not None


async def test_registry_bounds_entry_count_and_payload_bytes(monkeypatch):
    """Oversized/new excess flows stay cold without displacing a valid entry."""
    monkeypatch.setattr(
        WarmGraphRegistry,
        "_build",
        staticmethod(lambda flow_id, name, data: _FakeGraph(data["marker"])),  # noqa: ARG005
    )
    registry = WarmGraphRegistry(max_entries=1, max_flow_bytes=40, max_total_bytes=40)
    await registry.add("flow-1", "Flow", {"marker": "one"}, "v1")

    with pytest.raises(WarmRegistryCapacityError, match="entry count"):
        await registry.add("flow-2", "Flow", {"marker": "two"}, "v1")

    assert registry.get("flow-1") is not None
    assert registry.get("flow-2") is None

    await registry.evict("flow-1")
    # The rejected revision is backed off even if capacity later opens; a new
    # database revision gets a fresh cache-admission attempt.
    await registry.add("flow-2", "Flow", {"marker": "two"}, "v1")
    assert registry.get("flow-2") is None
    await registry.add("flow-2", "Flow", {"marker": "two"}, "v2")
    assert registry.get("flow-2") is not None


async def test_oversized_changed_revision_evicts_and_backs_off(monkeypatch):
    """A too-large changed flow cannot serve stale data or retry every interval."""
    build_calls: list[str] = []
    prepare_calls = 0

    def _build(flow_id: str, name: str | None, data: dict) -> _FakeGraph:  # noqa: ARG001
        build_calls.append(data["marker"])
        return _FakeGraph(data["marker"])

    monkeypatch.setattr(WarmGraphRegistry, "_build", staticmethod(_build))
    original_prepare = WarmGraphRegistry._prepare_snapshot.__func__

    def _prepare(cls, *args):
        nonlocal prepare_calls
        prepare_calls += 1
        return original_prepare(cls, *args)

    monkeypatch.setattr(WarmGraphRegistry, "_prepare_snapshot", classmethod(_prepare))
    registry = WarmGraphRegistry(max_flow_bytes=40)
    await registry.add("flow-1", "Flow", {"marker": "old"}, "v1")
    oversized = {"marker": "x" * 100}

    with pytest.raises(WarmRegistryCapacityError, match="entry"):
        await registry.add("flow-1", "Flow", oversized, "v2")

    assert registry.get("flow-1") is None
    await registry.add("flow-1", "Flow", oversized, "v2")
    assert build_calls == ["old"]
    assert prepare_calls == 2  # resident v1 + first v2; repeated tombstone is cheap


async def test_retained_snapshot_is_minimal_and_all_retained_metadata_is_measured(monkeypatch):
    """Unneeded metadata is dropped; retained metadata participates in byte limits."""
    monkeypatch.setattr(
        WarmGraphRegistry,
        "_build",
        staticmethod(lambda flow_id, name, data: _FakeGraph(data["marker"])),  # noqa: ARG005
    )
    flow_id = UUID("00000000-0000-0000-0000-000000000041")
    owner_id = UUID("00000000-0000-0000-0000-000000000042")
    source = _flow_snapshot(flow_id, owner_id, "endpoint", "small")
    source.description = "x" * 1_000_000
    source.action_description = "y" * 1_000_000

    registry = WarmGraphRegistry(max_flow_bytes=2_000, max_total_bytes=2_000)
    await registry.add(str(flow_id), source.name, source.data, "v1", flow=source)

    retained = registry.get_flow(str(flow_id))
    assert retained is not None
    assert retained.description is None
    assert retained.action_description is None
    assert registry._flow_payload_bytes[str(flow_id)] < 2_000

    large_name = _flow_snapshot(UUID(int=43), owner_id, "large-name", "small", name="n" * 5_000)
    with pytest.raises(WarmRegistryCapacityError, match="entry"):
        await registry.add(str(large_name.id), large_name.name, large_name.data, "v1", flow=large_name)


async def test_inflight_reservation_prevents_excess_distinct_flow_builds(monkeypatch):
    """Concurrent misses cannot parse more new entries than the cache can retain."""
    loop = asyncio.get_running_loop()
    first_started = asyncio.Event()
    release_first = threading.Event()
    build_calls: list[str] = []

    def _build(flow_id: str, name: str | None, data: dict) -> _FakeGraph:  # noqa: ARG001
        build_calls.append(data["marker"])
        if data["marker"] == "first":
            loop.call_soon_threadsafe(first_started.set)
            if not release_first.wait(timeout=5):
                raise TimeoutError
        return _FakeGraph(data["marker"])

    monkeypatch.setattr(WarmGraphRegistry, "_build", staticmethod(_build))
    registry = WarmGraphRegistry(max_entries=1)
    first = asyncio.create_task(registry.add("flow-1", "Flow", {"marker": "first"}, "v1"))
    await asyncio.wait_for(first_started.wait(), timeout=1)
    second = asyncio.create_task(registry.add("flow-2", "Flow", {"marker": "second"}, "v1"))

    release_first.set()
    await first
    with pytest.raises(WarmRegistryCapacityError, match="entry count"):
        await second

    assert build_calls == ["first"]
    assert registry.rejects_version("flow-2", "v1") is True


async def test_transient_reservation_rejection_retries_after_competing_build_fails(monkeypatch):
    """A failed competitor cannot leave an otherwise-fitting flow tombstoned."""
    loop = asyncio.get_running_loop()
    first_started = asyncio.Event()
    release_first = threading.Event()

    def _build(flow_id: str, name: str | None, data: dict) -> _FakeGraph:  # noqa: ARG001
        if data["marker"] == "first":
            loop.call_soon_threadsafe(first_started.set)
            if not release_first.wait(timeout=5):
                raise TimeoutError
            message = "first failed"
            raise ValueError(message)
        return _FakeGraph(data["marker"])

    monkeypatch.setattr(WarmGraphRegistry, "_build", staticmethod(_build))
    first_data = {"marker": "first"}
    second_data = {"marker": "second"}
    registry = WarmGraphRegistry(max_entries=2, max_total_bytes=len(orjson.dumps(second_data)))
    first = asyncio.create_task(registry.add("flow-1", "Flow", first_data, "v1"))
    await asyncio.wait_for(first_started.wait(), timeout=1)

    with pytest.raises(WarmRegistryCapacityError) as exc_info:
        await registry.add("flow-2", "Flow", second_data, "v1")
    assert exc_info.value.transient is True
    assert registry.rejects_version("flow-2", "v1") is False

    release_first.set()
    with pytest.raises(ValueError, match="first failed"):
        await first
    await registry.add("flow-2", "Flow", second_data, "v1")

    assert registry.get("flow-2")[0].marker == "second"


async def test_resident_rebuild_reservation_does_not_block_valid_new_entry(monkeypatch):
    """A resident replacement is charged as a delta, not a second entry."""
    loop = asyncio.get_running_loop()
    rebuild_started = asyncio.Event()
    release_rebuild = threading.Event()

    def _build(flow_id: str, name: str | None, data: dict) -> _FakeGraph:  # noqa: ARG001
        if data["marker"] == "replacement":
            loop.call_soon_threadsafe(rebuild_started.set)
            if not release_rebuild.wait(timeout=5):
                raise TimeoutError
        return _FakeGraph(data["marker"])

    monkeypatch.setattr(WarmGraphRegistry, "_build", staticmethod(_build))
    registry = WarmGraphRegistry(max_entries=2, max_total_bytes=1_000)
    await registry.add("flow-a", "Flow A", {"marker": "old"}, "v1")
    replacement_data = {"marker": "replacement"}
    new_data = {"marker": "new"}
    registry._max_total_bytes = len(orjson.dumps(replacement_data)) + len(orjson.dumps(new_data))

    rebuild = asyncio.create_task(registry.add("flow-a", "Flow A", replacement_data, "v2"))
    await asyncio.wait_for(rebuild_started.wait(), timeout=1)
    await registry.add("flow-b", "Flow B", new_data, "v1")

    release_rebuild.set()
    await rebuild

    assert registry.get("flow-a")[0].marker == "replacement"
    assert registry.get("flow-b")[0].marker == "new"


async def test_cancellation_while_waiting_to_publish_releases_reservation(monkeypatch):
    """A cancelled request cannot permanently consume reserved entries/bytes."""
    loop = asyncio.get_running_loop()
    build_started = asyncio.Event()
    build_finished = asyncio.Event()
    release_build = threading.Event()

    def _build(flow_id: str, name: str | None, data: dict) -> _FakeGraph:  # noqa: ARG001
        loop.call_soon_threadsafe(build_started.set)
        if not release_build.wait(timeout=5):
            raise TimeoutError
        loop.call_soon_threadsafe(build_finished.set)
        return _FakeGraph(data["marker"])

    monkeypatch.setattr(WarmGraphRegistry, "_build", staticmethod(_build))
    registry = WarmGraphRegistry(max_entries=1)
    task = asyncio.create_task(registry.add("flow-1", "Flow", {"marker": "one"}, "v1"))
    await asyncio.wait_for(build_started.wait(), timeout=1)

    await registry._lock.acquire()
    try:
        release_build.set()
        await asyncio.wait_for(build_finished.wait(), timeout=1)
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        assert registry._build_reservations
    finally:
        registry._lock.release()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert registry._build_reservations == {}
    assert registry._reserved_payload_bytes == 0


async def test_repeated_cancellation_keeps_build_bounds_until_thread_finishes(monkeypatch):
    """Repeated cancellation cannot abandon native work outside cache bounds."""
    loop = asyncio.get_running_loop()
    build_started = asyncio.Event()
    release_build = threading.Event()

    def _build(flow_id: str, name: str | None, data: dict) -> _FakeGraph:  # noqa: ARG001
        loop.call_soon_threadsafe(build_started.set)
        if not release_build.wait(timeout=5):
            raise TimeoutError
        return _FakeGraph(data["marker"])

    monkeypatch.setattr(WarmGraphRegistry, "_build", staticmethod(_build))
    registry = WarmGraphRegistry(max_entries=1)
    task = asyncio.create_task(registry.add("flow-1", "Flow", {"marker": "one"}, "v1"))
    await asyncio.wait_for(build_started.wait(), timeout=1)

    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.sleep(0)

    assert not task.done()
    assert registry._build_semaphore._value == 0
    assert registry._build_reservations

    release_build.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert registry._build_semaphore._value == 1
    assert registry._build_reservations == {}
    assert registry._reserved_payload_bytes == 0


async def test_cancelled_request_stays_cancelled_when_drained_build_fails(monkeypatch):
    """A late worker exception cannot replace an already-requested cancellation."""
    loop = asyncio.get_running_loop()
    build_started = asyncio.Event()
    release_build = threading.Event()

    def _build(flow_id: str, name: str | None, data: dict) -> _FakeGraph:  # noqa: ARG001
        loop.call_soon_threadsafe(build_started.set)
        if not release_build.wait(timeout=5):
            raise TimeoutError
        message = "late build failure"
        raise ValueError(message)

    monkeypatch.setattr(WarmGraphRegistry, "_build", staticmethod(_build))
    registry = WarmGraphRegistry(max_entries=1)
    task = asyncio.create_task(registry.add("flow-1", "Flow", {"marker": "one"}, "v1"))
    await asyncio.wait_for(build_started.wait(), timeout=1)

    task.cancel()
    await asyncio.sleep(0)
    release_build.set()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert registry._build_semaphore._value == 1
    assert registry._build_reservations == {}


async def test_failed_revision_bookkeeping_is_bounded(monkeypatch):
    """Distinct invalid lazy-warm attempts cannot grow side maps without bound."""

    def _reject(flow_id: str, name: str | None, data: dict) -> _FakeGraph:  # noqa: ARG001
        message = "invalid graph"
        raise ValueError(message)

    monkeypatch.setattr(WarmGraphRegistry, "_build", staticmethod(_reject))
    registry = WarmGraphRegistry(max_entries=2)

    for index in range(10):
        with pytest.raises(ValueError, match="invalid graph"):
            await registry.add(f"flow-{index}", "Flow", {"marker": str(index)}, "v1")

    assert len(registry._failed_revisions) <= 4


async def test_delayed_same_version_revision_cannot_overwrite_resident_entry(monkeypatch):
    """A successful old snapshot cannot regress aliases at an equal timestamp."""
    build_calls: list[str] = []

    def _build(flow_id: str, name: str | None, data: dict) -> _FakeGraph:  # noqa: ARG001
        build_calls.append(data["marker"])
        return _FakeGraph(data["marker"])

    monkeypatch.setattr(WarmGraphRegistry, "_build", staticmethod(_build))
    registry = WarmGraphRegistry()
    flow_id = UUID("00000000-0000-0000-0000-000000000031")
    owner_id = UUID("00000000-0000-0000-0000-000000000032")
    current = _flow_snapshot(flow_id, owner_id, "new-endpoint", "new", name="Renamed")
    delayed = _flow_snapshot(flow_id, owner_id, "old-endpoint", "old")

    await registry.add(str(flow_id), current.name, current.data, "same-version", flow=current)
    await registry.add(str(flow_id), delayed.name, delayed.data, "same-version", flow=delayed)

    assert registry.get_flow_by_endpoint(owner_id, "new-endpoint") is not None
    assert registry.get_flow_by_endpoint(owner_id, "old-endpoint") is None
    assert build_calls == ["new"]


async def test_flow_metadata_is_isolated_and_endpoint_alias_is_owner_scoped(monkeypatch):
    """Stored/read snapshots cannot mutate and endpoint aliases never cross owners."""
    monkeypatch.setattr(
        WarmGraphRegistry,
        "_build",
        staticmethod(lambda flow_id, name, data: _FakeGraph(data["marker"])),  # noqa: ARG005
    )
    registry = WarmGraphRegistry()
    flow_id = UUID("00000000-0000-0000-0000-000000000001")
    owner_id = UUID("00000000-0000-0000-0000-000000000002")
    other_owner_id = UUID("00000000-0000-0000-0000-000000000003")
    source = _flow_snapshot(flow_id, owner_id, "owned-endpoint", "original")

    await registry.add(str(flow_id), source.name, source.data, "v1", flow=source)
    source.name = "mutated source"
    source.data["marker"] = "mutated source"

    by_id = registry.get_flow(str(flow_id))
    by_endpoint = registry.get_flow_by_endpoint(owner_id, "owned-endpoint")
    assert by_id is not None
    assert by_endpoint is not None
    assert (by_id.name, by_id.data["marker"]) == ("Flow", "original")
    assert by_endpoint.id == flow_id
    assert registry.get_flow_by_endpoint(other_owner_id, "owned-endpoint") is None

    by_id.data["marker"] = "mutated return"
    assert registry.get_flow(str(flow_id)).data["marker"] == "original"


async def test_newer_metadata_replaces_alias_and_evict_removes_it(monkeypatch):
    """Rename/owner changes swap aliases atomically and eviction removes metadata."""
    build_calls: list[str] = []

    def _build(flow_id: str, name: str | None, data: dict) -> _FakeGraph:  # noqa: ARG001
        build_calls.append(data["marker"])
        return _FakeGraph(data["marker"])

    monkeypatch.setattr(WarmGraphRegistry, "_build", staticmethod(_build))
    registry = WarmGraphRegistry()
    flow_id = UUID("00000000-0000-0000-0000-000000000011")
    old_owner = UUID("00000000-0000-0000-0000-000000000012")
    new_owner = UUID("00000000-0000-0000-0000-000000000013")
    old = _flow_snapshot(flow_id, old_owner, "old-endpoint", "old")
    new = _flow_snapshot(flow_id, new_owner, "new-endpoint", "new", name="Renamed")

    await registry.add(str(flow_id), old.name, old.data, "v1", flow=old)
    old_revision = registry.revision_of(str(flow_id))
    assert old_revision is not None
    await registry.add(str(flow_id), new.name, new.data, "v2", flow=new)

    assert registry.get_flow_by_endpoint(old_owner, "old-endpoint") is None
    resolved = registry.get_flow_by_endpoint(new_owner, "new-endpoint")
    assert resolved is not None
    assert (resolved.id, resolved.name) == (flow_id, "Renamed")

    # A delayed old build cannot restore its matching stale snapshot/alias.
    await registry.add(str(flow_id), old.name, old.data, "v1", flow=old)
    assert registry.get_flow_by_endpoint(old_owner, "old-endpoint") is None
    assert registry.get_flow_by_endpoint(new_owner, "new-endpoint") is not None
    assert build_calls == ["old", "new"]

    # A validator that observed v1 cannot evict the concurrently-published v2.
    assert await registry.evict_if_revision(str(flow_id), old_revision) is False
    current_revision = registry.revision_of(str(flow_id))
    assert current_revision is not None
    assert await registry.evict_if_revision(str(flow_id), current_revision) is True
    assert registry.get(str(flow_id)) is None
    assert registry.get_flow(str(flow_id)) is None
    assert registry.get_flow_by_endpoint(new_owner, "new-endpoint") is None


async def test_warm_all_serializes_machine_local_startup(monkeypatch, tmp_path):
    """A second local worker cannot enter its DB scan while the first warm holds the lock."""
    first_query_entered = asyncio.Event()
    release_first_query = asyncio.Event()
    query_calls = 0

    class _Result:
        @staticmethod
        def all() -> list:
            return []

    class _Session:
        async def exec(self, statement):  # noqa: ARG002
            nonlocal query_calls
            query_calls += 1
            if query_calls == 1:
                first_query_entered.set()
                await release_first_query.wait()
            return _Result()

    @contextlib.asynccontextmanager
    async def _session_scope():
        yield _Session()

    monkeypatch.setattr(reconcile_mod, "session_scope", _session_scope)
    monkeypatch.setattr(reconcile_mod, "_WARM_ALL_LOCK_PATH", tmp_path / "warm.lock")
    monkeypatch.setattr(
        reconcile_mod,
        "get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(warm_registry_preload_limit=1)),
    )

    first = asyncio.create_task(reconcile_mod.warm_all())
    await asyncio.wait_for(first_query_entered.wait(), timeout=1)
    second = asyncio.create_task(reconcile_mod.warm_all())
    try:
        await asyncio.sleep(0.05)
        assert query_calls == 1
    finally:
        release_first_query.set()
        await asyncio.wait_for(asyncio.gather(first, second), timeout=2)

    assert query_calls == 2


async def test_warm_all_releases_startup_lock_after_query_error(monkeypatch, tmp_path):
    """A failed startup scan cannot strand the machine-local lock."""

    @contextlib.asynccontextmanager
    async def _failing_scope():
        msg = "startup DB unavailable"
        raise RuntimeError(msg)
        yield  # pragma: no cover

    class _Result:
        @staticmethod
        def all() -> list:
            return []

    class _Session:
        async def exec(self, statement):  # noqa: ARG002
            return _Result()

    @contextlib.asynccontextmanager
    async def _working_scope():
        yield _Session()

    monkeypatch.setattr(reconcile_mod, "_WARM_ALL_LOCK_PATH", tmp_path / "warm.lock")
    monkeypatch.setattr(
        reconcile_mod,
        "get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(warm_registry_preload_limit=1)),
    )
    monkeypatch.setattr(reconcile_mod, "session_scope", _failing_scope)
    with pytest.raises(RuntimeError, match="startup DB unavailable"):
        await reconcile_mod.warm_all()

    monkeypatch.setattr(reconcile_mod, "session_scope", _working_scope)
    await asyncio.wait_for(reconcile_mod.warm_all(), timeout=1)


def test_tombstone_budget_covers_preload_window():
    """Un-warmable flows above 2*max_entries must NOT rotate out of the tombstone set.

    Regression for the reconcile churn: when the tombstone budget was sized against
    ``max_entries`` alone, an un-warmable population larger than ``2*max_entries`` evicted
    older tombstones, so those flows dropped out of backoff and were re-selected as "new"
    every pass (full SELECT + deepcopy + serialize, forever). The budget must instead cover
    the preload scan window (``preload_limit``), the population that can be selected.
    """
    # 6 un-warmable flows, max_entries=2 (old budget = 2*2 = 4), preload_limit=50.
    reg = WarmGraphRegistry(max_entries=2, preload_limit=50)
    for i in range(6):
        reg._record_failed_locked(f"flow-{i}", "v1", ("v1",))
    # New budget = max(4, 50) = 50 -> all 6 survive -> reconcile skips them next pass -> converges.
    assert reg.rejection_count() == 6
    for i in range(6):
        assert reg.rejects_version(f"flow-{i}", "v1") is True


def test_tombstone_budget_default_preserves_prior_bound():
    """With preload disabled (preload_limit=0, the default) the budget stays 2*max_entries."""
    reg = WarmGraphRegistry(max_entries=2, preload_limit=0)
    for i in range(10):
        reg._record_failed_locked(f"flow-{i}", "v1", ("v1",))
    # max(2*2, 0) = 4 -> oldest evicted, newest 4 kept (backwards-compatible behavior).
    assert reg.rejection_count() == 4
