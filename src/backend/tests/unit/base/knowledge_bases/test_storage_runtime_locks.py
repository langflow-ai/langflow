"""Cross-task iterator finalization and nested remote-store lock regression tests."""

from __future__ import annotations

import asyncio
import os
from contextlib import AsyncExitStack, asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from anyio import fail_after
from filelock import FileLock
from langflow.services.knowledge_base_storage import runtime

pytestmark = pytest.mark.no_blockbuster


@pytest.fixture
def local_root(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "storage_root", lambda: tmp_path)
    return tmp_path


@pytest.mark.usefixtures("local_root")
async def test_cross_task_close_releases_lock_without_stale_reentrancy():
    kb_id = uuid4()

    async def values():
        async with runtime.exclusive_lock(kb_id):
            yield "held"

    iterator = values()
    assert await anext(iterator) == "held"
    await asyncio.create_task(iterator.aclose())
    assert runtime._owner(kb_id) not in runtime._held_locks

    acquired = asyncio.Event()
    release = asyncio.Event()

    async def contender():
        async with runtime.exclusive_lock(kb_id):
            acquired.set()
            await release.wait()

    task = asyncio.create_task(contender())
    await asyncio.wait_for(acquired.wait(), 1)
    # The original task must acquire the lock again, not reuse an abandoned
    # context entry while the contender owns it.
    try:
        with fail_after(0.1):
            async with runtime.exclusive_lock(kb_id):
                pytest.fail("Original owner bypassed the contender's lock")
    except TimeoutError:
        pass
    finally:
        release.set()
    await task


async def test_cross_task_outer_close_preserves_active_nested_scope(local_root):
    kb_id = uuid4()

    async def values():
        async with runtime.exclusive_lock(kb_id):
            yield "held"

    iterator = values()
    await anext(iterator)
    async with runtime.exclusive_lock(kb_id):
        await asyncio.create_task(iterator.aclose())
        lease = runtime._held_locks[runtime._owner(kb_id)]
        assert lease.active
        assert lease.users == 1
        lock = FileLock(local_root / ".locks" / f"{kb_id}.lock", thread_local=False)
        with pytest.raises(TimeoutError):
            lock.acquire(timeout=0)
    assert runtime._owner(kb_id) not in runtime._held_locks
    with FileLock(local_root / ".locks" / f"{kb_id}.lock", timeout=0):
        pass


class FakeAdvisoryEngine:
    """Enforce connection capacity and transaction-scoped advisory ownership."""

    def __init__(self):
        self.capacity = asyncio.Semaphore(4)
        self.active = 0
        self.maximum_active = 0
        self.transactions = 0
        self.locks = {}

    @asynccontextmanager
    async def begin(self):
        async with self.capacity:
            transaction = object()
            self.active += 1
            self.transactions += 1
            self.maximum_active = max(self.maximum_active, self.active)

            async def execute(_query, parameters):
                key = parameters["key"]
                acquired = key not in self.locks or self.locks[key] is transaction
                if acquired:
                    self.locks[key] = transaction
                return SimpleNamespace(scalar_one=lambda: acquired)

            try:
                yield SimpleNamespace(execute=execute)
            finally:
                self.locks = {key: owner for key, owner in self.locks.items() if owner is not transaction}
                self.active -= 1


@pytest.fixture
async def remote_engine(monkeypatch):
    engine = FakeAdvisoryEngine()
    url = "postgresql+psycopg://test/coordination"
    service = SimpleNamespace(database_url=url)
    monkeypatch.setattr(runtime, "get_db_service", lambda: service)
    key = (os.getpid(), url, asyncio.get_running_loop())
    monkeypatch.setitem(runtime._coordination_engines, key, engine)
    return engine


async def test_more_than_four_nested_remote_kbs_share_one_transaction(remote_engine):
    ids = sorted((uuid4() for _ in range(9)), key=str)
    with fail_after(1):
        async with AsyncExitStack() as stack:
            for kb_id in ids:
                await stack.enter_async_context(runtime._remote_lock(kb_id))
            assert len(remote_engine.locks) == len(ids)
            assert remote_engine.active == remote_engine.maximum_active == remote_engine.transactions == 1
    assert not remote_engine.locks
    assert remote_engine.active == 0


async def test_child_task_cannot_reuse_parents_remote_transaction(remote_engine):
    first, second = sorted((uuid4(), uuid4()), key=str)
    acquired = asyncio.Event()
    release = asyncio.Event()

    async def child():
        async with runtime._remote_lock(first):
            acquired.set()
            await release.wait()

    async with runtime._remote_lock(first), runtime._remote_lock(second):
        task = asyncio.create_task(child())
        await asyncio.sleep(0.1)
        assert not acquired.is_set()
        assert remote_engine.maximum_active == 2
    await asyncio.wait_for(acquired.wait(), 1)
    release.set()
    await task
    assert not remote_engine.locks


async def test_remote_generator_cross_task_close_releases_transaction(remote_engine):
    kb_id = uuid4()

    async def values():
        async with runtime._remote_lock(kb_id):
            yield "held"

    iterator = values()
    await anext(iterator)
    await asyncio.create_task(iterator.aclose())
    assert not remote_engine.locks
    assert remote_engine.active == 0
    assert runtime._owner(kb_id) not in runtime._held_locks
    async with runtime._remote_lock(kb_id):
        assert remote_engine.active == 1


@pytest.mark.usefixtures("local_root")
async def test_guarded_iterator_closes_underlying_iterator_before_unlock(monkeypatch):
    kb_id = uuid4()
    closed = []

    @asynccontextmanager
    async def operation(_record, *, shared=False):
        assert shared is True
        async with runtime.exclusive_lock(kb_id):
            yield

    monkeypatch.setattr(runtime, "operation", operation)

    class Backend:
        async def iter_documents(self):
            try:
                yield ["first"]
                yield ["second"]
            finally:
                closed.append(any(key[-1] == kb_id and lease.active for key, lease in runtime._held_locks.items()))

    backend = runtime._GuardedMethods(Backend(), object())
    iterator = backend.iter_documents()
    assert await anext(iterator) == ["first"]
    await asyncio.create_task(iterator.aclose())
    assert closed == [True]
    assert runtime._owner(kb_id) not in runtime._held_locks


async def test_cancelled_nested_remote_acquisition_releases_its_parent_transaction(remote_engine):
    first, second = sorted((uuid4(), uuid4()), key=str)
    started = asyncio.Event()

    async def blocked():
        async with runtime._remote_lock(first):
            started.set()
            async with runtime._remote_lock(second):
                pytest.fail("Nested lock unexpectedly acquired")

    async with runtime._remote_lock(second):
        task = asyncio.create_task(blocked())
        await asyncio.wait_for(started.wait(), 1)
        await asyncio.sleep(0.1)
        assert remote_engine.active == 2
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert remote_engine.active == 1
        assert len(remote_engine.locks) == 1
    assert not remote_engine.locks
    assert remote_engine.active == 0


@pytest.mark.skipif(os.name != "posix", reason="Shared file locks require POSIX flock")
@pytest.mark.usefixtures("local_root")
async def test_shared_readers_overlap_and_exclude_writer(monkeypatch):
    """Concurrent readers must overlap, while a writer times out without entering."""
    kb_id = uuid4()
    entered = asyncio.Event()
    finish = asyncio.Event()
    monkeypatch.setattr(runtime, "LOCK_TIMEOUT_SECONDS", 0.1)

    async def reader():
        async with runtime.shared_lock(kb_id):
            entered.set()
            await finish.wait()

    async with runtime.shared_lock(kb_id):
        task = asyncio.create_task(reader())
        try:
            await asyncio.wait_for(entered.wait(), 1)
            with pytest.raises(runtime.StorageUnavailableError, match="upgrade"):
                async with runtime.exclusive_lock(kb_id):
                    pytest.fail("A read lease was upgraded")

            async def writer():
                async with runtime.exclusive_lock(kb_id):
                    pytest.fail("Writer entered during active reads")

            with pytest.raises(runtime.StorageUnavailableError, match="busy"):
                await asyncio.create_task(writer())
        finally:
            finish.set()
            await task
    async with runtime.exclusive_lock(kb_id):
        pass


async def test_remote_lock_contention_has_bounded_wait(remote_engine, monkeypatch):
    """A remote contender releases its pool connection when the deadline expires."""
    monkeypatch.setattr(runtime, "LOCK_TIMEOUT_SECONDS", 0.05)
    kb_id = uuid4()

    async def contender():
        async with runtime._remote_lock(kb_id):
            pytest.fail("Contender bypassed the writer")

    async with runtime._remote_lock(kb_id):
        with pytest.raises(runtime.StorageUnavailableError, match="busy"):
            await asyncio.create_task(contender())
        assert remote_engine.active == 1
    assert remote_engine.active == 0


async def test_content_id_lookup_takes_a_shared_lease(monkeypatch):
    # Ingestion looks up stored hashes before embedding; that read must not
    # block other readers of the same knowledge base.
    leases = []

    @asynccontextmanager
    async def operation(_record, *, shared=False):
        leases.append(shared)
        yield

    monkeypatch.setattr(runtime, "operation", operation)

    class Backend:
        async def existing_content_ids(self, content_ids):
            return {"stored"} & set(content_ids)

    backend = runtime._GuardedMethods(Backend(), object())
    assert await backend.existing_content_ids({"stored", "new"}) == {"stored"}
    assert leases == [True]
