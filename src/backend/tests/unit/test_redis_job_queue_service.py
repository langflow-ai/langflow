"""Unit tests for RedisJobQueueService and RedisQueueWrapper.

Uses fakeredis so no real Redis instance is required.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from typing import Any

import fakeredis.aioredis as fakeredis_aio
import pytest
from langflow.services.job_queue.service import (
    _STREAM_SENTINEL_DATA,
    RedisJobQueueService,
    RedisQueueWrapper,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_service(ttl: int = 60) -> tuple[RedisJobQueueService, fakeredis_aio.FakeRedis]:
    """Return a started RedisJobQueueService backed by a FakeRedis client."""
    fake_client = fakeredis_aio.FakeRedis()
    service = RedisJobQueueService(ttl=ttl)
    # Inject the fake client directly so no real Redis connection is attempted.
    service._client = fake_client
    service._closed = False
    service._cleanup_task = asyncio.create_task(service._periodic_cleanup())
    service.ready = True
    return service, fake_client


async def _stop_service(service: RedisJobQueueService) -> None:
    service._closed = True
    if service._cleanup_task:
        service._cleanup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await service._cleanup_task
    for bridge in list(service._bridge_tasks.values()):
        if not bridge.done():
            bridge.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await bridge
    service._bridge_tasks.clear()
    for wrapper in list(service._consumer_wrappers.values()):
        await wrapper.cancel()
    service._consumer_wrappers.clear()
    if service._client:
        await service._client.aclose()
        service._client = None


class _BlockingXaddClient:
    """Redis client wrapper that blocks inside xadd until the caller cancels it."""

    def __init__(self, client: fakeredis_aio.FakeRedis) -> None:
        self._client = client
        self.xadd_started = asyncio.Event()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    async def xadd(self, *_args: Any, **_kwargs: Any) -> None:
        self.xadd_started.set()
        await asyncio.Event().wait()


# ---------------------------------------------------------------------------
# RedisQueueWrapper tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redis_queue_wrapper_reads_events():
    """RedisQueueWrapper delivers events published to the Redis Stream."""
    fake_client = fakeredis_aio.FakeRedis()
    job_id = str(uuid.uuid4())
    stream_key = f"langflow:queue:{job_id}"

    wrapper = RedisQueueWrapper(job_id, fake_client, ttl=60)

    # Publish two events followed by the sentinel.
    await fake_client.xadd(stream_key, {"event_id": "e1", "data": b"hello", "ts": "1.0"})
    await fake_client.xadd(stream_key, {"event_id": "e2", "data": b"world", "ts": "2.0"})
    await fake_client.xadd(
        stream_key,
        {"event_id": "__sentinel__", "data": _STREAM_SENTINEL_DATA, "ts": "3.0"},
    )

    event1 = await asyncio.wait_for(wrapper.get(), timeout=5)
    event2 = await asyncio.wait_for(wrapper.get(), timeout=5)
    sentinel = await asyncio.wait_for(wrapper.get(), timeout=5)

    assert event1 == ("e1", b"hello", 1.0)
    assert event2 == ("e2", b"world", 2.0)
    assert sentinel == (None, None, 3.0)

    await wrapper.cancel()
    await fake_client.aclose()


@pytest.mark.asyncio
async def test_redis_queue_wrapper_self_terminates_on_key_deletion():
    """RedisQueueWrapper sends the end-of-stream sentinel when the key is deleted."""
    fake_client = fakeredis_aio.FakeRedis()
    job_id = str(uuid.uuid4())
    stream_key = f"langflow:queue:{job_id}"

    wrapper = RedisQueueWrapper(job_id, fake_client, ttl=60)

    # Publish one event then delete the key (simulates cleanup_job on another worker).
    await fake_client.xadd(stream_key, {"event_id": "e1", "data": b"data", "ts": "1.0"})
    event1 = await asyncio.wait_for(wrapper.get(), timeout=5)
    assert event1[1] == b"data"

    await fake_client.delete(stream_key)

    # The wrapper's fill task should detect the missing key and put the sentinel.
    sentinel = await asyncio.wait_for(wrapper.get(), timeout=5)
    assert sentinel[0] is None
    assert sentinel[1] is None

    await wrapper.cancel()
    await fake_client.aclose()


@pytest.mark.asyncio
async def test_redis_queue_wrapper_empty_reflects_buffer():
    """empty() reports the state of the local buffer, not Redis directly."""
    fake_client = fakeredis_aio.FakeRedis()
    job_id = str(uuid.uuid4())
    stream_key = f"langflow:queue:{job_id}"

    wrapper = RedisQueueWrapper(job_id, fake_client, ttl=60)
    assert wrapper.empty()

    await fake_client.xadd(stream_key, {"event_id": "e1", "data": b"x", "ts": "1.0"})
    await fake_client.xadd(
        stream_key,
        {"event_id": "__sentinel__", "data": _STREAM_SENTINEL_DATA, "ts": "2.0"},
    )

    # Allow the fill task to process the events.
    await asyncio.sleep(0.1)
    assert not wrapper.empty()

    await wrapper.cancel()
    await fake_client.aclose()


@pytest.mark.asyncio
async def test_redis_queue_wrapper_put_nowait_is_noop():
    """put_nowait on the consumer-side wrapper is a no-op (does not raise)."""
    fake_client = fakeredis_aio.FakeRedis()
    job_id = str(uuid.uuid4())
    wrapper = RedisQueueWrapper(job_id, fake_client, ttl=60)

    wrapper.put_nowait(("e1", b"data", 1.0))
    assert wrapper.empty()

    await wrapper.cancel()
    await fake_client.aclose()


# ---------------------------------------------------------------------------
# RedisJobQueueService tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redis_service_create_and_publish():
    """Events written via EventManager appear in the Redis Stream."""
    service, fake_client = await _make_service()
    try:
        job_id = str(uuid.uuid4())
        _queue, event_manager = service.create_queue(job_id)

        async def _build():
            event_manager.on_token(data={"chunk": "hi"})
            await event_manager.queue.put((None, None, time.time()))

        service.start_job(job_id, _build())
        await asyncio.sleep(0.2)

        stream_key = f"langflow:queue:{job_id}"
        messages = await fake_client.xrange(stream_key)
        assert len(messages) >= 2  # at least one event + sentinel
    finally:
        await _stop_service(service)


@pytest.mark.asyncio
async def test_redis_service_cross_worker_get_queue_data():
    """get_queue_data returns a RedisQueueWrapper for jobs not on this worker."""
    service, fake_client = await _make_service()
    try:
        job_id = str(uuid.uuid4())
        stream_key = f"langflow:queue:{job_id}"

        # Simulate another worker having published events to this stream.
        await fake_client.xadd(stream_key, {"event_id": "e1", "data": b"bytes", "ts": "1.0"})
        await fake_client.xadd(
            stream_key,
            {"event_id": "__sentinel__", "data": _STREAM_SENTINEL_DATA, "ts": "2.0"},
        )

        queue, _event_manager, task, _ = service.get_queue_data(job_id)

        assert isinstance(queue, RedisQueueWrapper)
        assert task is None

        event = await asyncio.wait_for(queue.get(), timeout=5)
        assert event[1] == b"bytes"
        sentinel = await asyncio.wait_for(queue.get(), timeout=5)
        assert sentinel[0] is None

        await queue.cancel()
    finally:
        await _stop_service(service)


@pytest.mark.asyncio
async def test_redis_service_local_job_returns_redis_wrapper():
    """get_queue_data returns a RedisQueueWrapper even for same-worker jobs.

    The bridge coroutine is the sole reader of the local asyncio.Queue; giving the
    HTTP consumer a RedisQueueWrapper prevents the race condition where both would
    compete to drain the same queue and events would be lost.
    """
    service, _ = await _make_service()
    try:
        job_id = str(uuid.uuid4())
        service.create_queue(job_id)

        async def _noop():
            await asyncio.sleep(0)

        service.start_job(job_id, _noop())

        queue, _, task, _ = service.get_queue_data(job_id)
        # Consumer always gets a RedisQueueWrapper, never the raw asyncio.Queue
        assert isinstance(queue, RedisQueueWrapper)
        # Task reference is still available from the local registry
        assert task is not None
    finally:
        await _stop_service(service)


@pytest.mark.asyncio
async def test_redis_service_reuses_consumer_wrapper_for_sequential_polls():
    """Repeated get_queue_data calls for a job continue from the last Redis Stream ID."""
    service, fake_client = await _make_service()
    try:
        job_id = str(uuid.uuid4())
        stream_key = f"langflow:queue:{job_id}"

        await fake_client.xadd(stream_key, {"event_id": "e1", "data": b"first", "ts": "1.0"})
        await fake_client.xadd(stream_key, {"event_id": "e2", "data": b"second", "ts": "2.0"})

        first_queue, _, _, _ = service.get_queue_data(job_id)
        first_event = await asyncio.wait_for(first_queue.get(), timeout=5)

        second_queue, _, _, _ = service.get_queue_data(job_id)
        second_event = await asyncio.wait_for(second_queue.get(), timeout=5)

        assert second_queue is first_queue
        assert first_event == ("e1", b"first", 1.0)
        assert second_event == ("e2", b"second", 2.0)
    finally:
        await _stop_service(service)


@pytest.mark.asyncio
async def test_redis_service_cleanup_cancels_cached_consumer_wrapper():
    """cleanup_job cancels the cached Redis consumer fill task for the job."""
    service, _ = await _make_service()
    try:
        job_id = str(uuid.uuid4())
        queue, _, _, _ = service.get_queue_data(job_id)

        assert isinstance(queue, RedisQueueWrapper)
        assert job_id in service._consumer_wrappers

        await service.cleanup_job(job_id)

        assert job_id not in service._consumer_wrappers
        assert queue._fill_task.done()
    finally:
        await _stop_service(service)


@pytest.mark.asyncio
async def test_redis_service_raises_when_closed():
    """get_queue_data raises RuntimeError when the service is closed."""
    service, _ = await _make_service()
    service._closed = True

    with pytest.raises(RuntimeError, match="closed"):
        service.get_queue_data("some-job-id")

    await _stop_service(service)


@pytest.mark.asyncio
async def test_redis_service_cleanup_deletes_redis_keys():
    """cleanup_job removes the Redis Stream and owner keys."""
    service, fake_client = await _make_service()
    try:
        job_id = str(uuid.uuid4())
        service.create_queue(job_id)

        async def _noop():
            await asyncio.sleep(0)

        service.start_job(job_id, _noop())
        await asyncio.sleep(0.05)

        stream_key = f"langflow:queue:{job_id}"
        owner_key = f"langflow:owner:{job_id}"

        # Manually create the keys to verify deletion.
        await fake_client.xadd(stream_key, {"event_id": "e1", "data": b"x", "ts": "1.0"})
        await fake_client.set(owner_key, "some-user")

        await service.cleanup_job(job_id)

        assert not await fake_client.exists(stream_key)
        assert not await fake_client.exists(owner_key)
    finally:
        await _stop_service(service)


@pytest.mark.asyncio
async def test_redis_service_cleanup_deletes_redis_keys_when_cancelled():
    """cleanup_job removes Redis keys even when local task cancellation is re-raised."""
    service, fake_client = await _make_service()
    try:
        job_id = str(uuid.uuid4())
        service.create_queue(job_id)

        async def _long_running():
            await asyncio.Event().wait()

        service.start_job(job_id, _long_running())
        await asyncio.sleep(0.05)

        stream_key = f"langflow:queue:{job_id}"
        owner_key = f"langflow:owner:{job_id}"

        await fake_client.xadd(stream_key, {"event_id": "e1", "data": b"x", "ts": "1.0"})
        await fake_client.set(owner_key, "some-user")

        with pytest.raises(asyncio.CancelledError):
            await service.cleanup_job(job_id)

        assert not await fake_client.exists(stream_key)
        assert not await fake_client.exists(owner_key)
    finally:
        await _stop_service(service)


@pytest.mark.asyncio
async def test_redis_service_owner_stored_in_redis():
    """register_job_owner writes to Redis; get_job_owner reads it cross-worker."""
    service, fake_client = await _make_service()
    try:
        job_id = str(uuid.uuid4())
        user_id = uuid.uuid4()

        await service.register_job_owner(job_id, user_id)

        # Verify Redis key was written.
        raw = await fake_client.get(f"langflow:owner:{job_id}")
        assert raw is not None
        assert str(user_id) == raw.decode()

        # Simulate cross-worker lookup: clear in-memory dict.
        service._job_owners.clear()
        retrieved = await service.get_job_owner(job_id)
        assert retrieved == user_id
    finally:
        await _stop_service(service)


@pytest.mark.asyncio
async def test_redis_service_owner_cleaned_up_after_cleanup_job():
    """cleanup_job removes the _job_owners entry and the Redis owner key."""
    service, fake_client = await _make_service()
    try:
        job_id = str(uuid.uuid4())
        user_id = uuid.uuid4()

        service.create_queue(job_id)

        async def _noop():
            await asyncio.sleep(0)

        service.start_job(job_id, _noop())
        await asyncio.sleep(0.05)
        await service.register_job_owner(job_id, user_id)

        assert await service.get_job_owner(job_id) == user_id

        await service.cleanup_job(job_id)

        assert await service.get_job_owner(job_id) is None
        assert not await fake_client.exists(f"langflow:owner:{job_id}")
    finally:
        await _stop_service(service)


@pytest.mark.asyncio
async def test_redis_service_get_job_owner_returns_none_for_unknown_job():
    """get_job_owner returns None for a job_id that was never registered."""
    service, _ = await _make_service()
    try:
        result = await service.get_job_owner("nonexistent-job-id")
        assert result is None
    finally:
        await _stop_service(service)


@pytest.mark.asyncio
async def test_redis_service_bridge_publishes_sentinel_on_end():
    """The bridge task publishes the end-of-stream sentinel when the build ends."""
    service, fake_client = await _make_service()
    try:
        job_id = str(uuid.uuid4())
        _queue, event_manager = service.create_queue(job_id)

        async def _build():
            await event_manager.queue.put((None, None, time.time()))

        service.start_job(job_id, _build())

        # Wait long enough for the bridge to publish.
        await asyncio.sleep(0.2)

        stream_key = f"langflow:queue:{job_id}"
        messages = await fake_client.xrange(stream_key)
        assert messages, "Expected at least one message in the stream"
        last_fields = messages[-1][1]
        assert last_fields.get(b"data") == _STREAM_SENTINEL_DATA
    finally:
        await _stop_service(service)


@pytest.mark.asyncio
async def test_redis_service_bridge_requeues_sentinel_when_cancelled_during_xadd():
    """A cancelled bridge restores an unpublished sentinel instead of dropping it."""
    service, fake_client = await _make_service()
    blocking_client = _BlockingXaddClient(fake_client)
    service._client = blocking_client
    try:
        job_id = str(uuid.uuid4())
        local_queue, _event_manager = service.create_queue(job_id)
        sentinel = (None, None, time.time())

        await local_queue.put(sentinel)
        await asyncio.wait_for(blocking_client.xadd_started.wait(), timeout=1)

        bridge = service._bridge_tasks[job_id]
        bridge.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await bridge

        assert local_queue.get_nowait() == sentinel
    finally:
        await _stop_service(service)
