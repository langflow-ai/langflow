"""Remote destructive calls must finish before their UUID fence is released."""

import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langflow.services.knowledge_base_storage import runtime
from lfx.base.knowledge_bases.backends.opensearch import OpenSearchBackend

from . import test_storage_upgrade as storage_tests

database = storage_tests.database
make_kb = storage_tests.make_kb
read_kb = storage_tests.read_kb

pytestmark = pytest.mark.no_blockbuster


async def test_remote_initialization_failure_retains_deletion_identity(database, monkeypatch):
    row = await make_kb(database, backend="opensearch")
    backend = SimpleNamespace(
        ensure_ready=AsyncMock(side_effect=OSError("credential resolution failed")),
        delete_collection=AsyncMock(),
        teardown=AsyncMock(),
    )
    monkeypatch.setattr(runtime, "_raw_backend", lambda _row: backend)
    with pytest.raises(OSError, match="credential resolution failed"):
        await runtime.delete_storage_for_record(row)
    assert (await read_kb(database, row.id)).storage_state == "ready"
    backend.delete_collection.assert_not_awaited()
    backend.teardown.assert_awaited_once()
    backend.ensure_ready.side_effect = None
    await runtime.delete_storage_for_record(await read_kb(database, row.id))
    assert (await read_kb(database, row.id)).storage_state == "deleted"
    backend.delete_collection.assert_awaited_once()


async def test_cancelled_remote_purge_keeps_concurrent_writer_out_until_native_completion(database):
    row = await make_kb(database, backend="opensearch")
    started = threading.Event()
    release = threading.Event()
    native_done = threading.Event()
    writer_entered = asyncio.Event()

    def native_delete(**_kwargs):
        started.set()
        assert release.wait(5)
        native_done.set()
        return {"deleted": 1, "failures": [], "timed_out": False}

    backend = OpenSearchBackend(kb_name=row.name, backend_config={}, user_id=row.user_id)
    backend.ensure_ready = AsyncMock()
    backend._os_client = SimpleNamespace(delete_by_query=native_delete)
    backend._os_index = "test-index"
    guarded = runtime._GuardedMethods(backend, row)
    purge = asyncio.create_task(guarded.delete_by({"session_id": "session"}))

    async def next_writer():
        async with runtime.operation(row):
            assert native_done.is_set()
            writer_entered.set()

    writer = None
    try:
        assert await asyncio.to_thread(started.wait, 2)
        purge.cancel()
        writer = asyncio.create_task(next_writer())
        await asyncio.sleep(0.1)
        assert not purge.done()
        assert not writer_entered.is_set()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await purge
    await asyncio.wait_for(writer, 2)
    assert writer_entered.is_set()
