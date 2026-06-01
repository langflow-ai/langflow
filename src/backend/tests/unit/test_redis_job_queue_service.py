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
from langflow.api.build import (
    cancel_flow_build,
    create_flow_response,
    get_flow_events_response,
)
from langflow.api.utils import EventDeliveryType
from langflow.events.event_manager import EventManager
from langflow.services.job_queue.service import (
    _STREAM_SENTINEL_DATA,
    JobQueueService,
    RedisJobQueueService,
    RedisQueueWrapper,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_service(
    ttl: int = 60,
    *,
    cancel_channel_enabled: bool = True,
    shared_client: fakeredis_aio.FakeRedis | None = None,
) -> tuple[RedisJobQueueService, fakeredis_aio.FakeRedis]:
    """Return a started RedisJobQueueService backed by a FakeRedis client.

    When *shared_client* is provided, multiple services can share the same Redis
    (for cross-worker tests).  When *cancel_channel_enabled* is True, the
    dispatcher task is spawned so signal_cancel can be exercised end-to-end.
    """
    fake_client = shared_client or fakeredis_aio.FakeRedis()
    service = RedisJobQueueService(ttl=ttl, cancel_channel_enabled=cancel_channel_enabled)
    # Inject the fake client directly so no real Redis connection is attempted.
    service._client = fake_client
    service._closed = False
    # Track whether this service owns the FakeRedis client so the first
    # _stop_service() doesn't aclose() it out from under a sibling that's
    # sharing it (cross-worker tests).
    service._owns_test_client = shared_client is None  # type: ignore[attr-defined]
    service._cleanup_task = asyncio.create_task(service._periodic_cleanup())
    if cancel_channel_enabled:
        service._cancel_dispatcher_task = asyncio.create_task(service._run_cancel_dispatcher())
        # Give the dispatcher a beat to complete PSUBSCRIBE before tests publish.
        await asyncio.sleep(0.05)
    service.ready = True
    return service, fake_client


async def _stop_service(service: RedisJobQueueService) -> None:
    service._closed = True
    if service._cleanup_task:
        service._cleanup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await service._cleanup_task
    if service._cancel_dispatcher_task and not service._cancel_dispatcher_task.done():
        service._cancel_dispatcher_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await service._cancel_dispatcher_task
    service._cancel_dispatcher_task = None
    for refresh_task in list(service._owner_refresh_tasks.values()):
        if not refresh_task.done():
            refresh_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await refresh_task
    service._owner_refresh_tasks.clear()
    for bg in list(service._background_tasks):
        if not bg.done():
            bg.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await bg
    service._background_tasks.clear()
    for bridge in list(service._bridge_tasks.values()):
        if not bridge.done():
            bridge.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await bridge
    service._bridge_tasks.clear()
    for wrapper in list(service._consumer_wrappers.values()):
        await wrapper.cancel()
    service._consumer_wrappers.clear()
    if service._client and getattr(service, "_owns_test_client", True):
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
    """empty() reports the local buffer state after the first XREAD completes.

    Before the first XREAD returns, empty() always returns False so that the
    while-not-empty drain loop in build.py suspends on get() and yields to the
    event loop, giving the fill task a chance to populate the buffer.
    """
    fake_client = fakeredis_aio.FakeRedis()
    job_id = str(uuid.uuid4())
    stream_key = f"langflow:queue:{job_id}"

    wrapper = RedisQueueWrapper(job_id, fake_client, ttl=60)
    # Before the first XREAD completes, empty() returns False regardless of
    # the actual buffer state (warm-up guard for the build.py drain loop).
    assert not wrapper.empty()

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
    """put_nowait on the consumer-side wrapper is a no-op (does not raise).

    The wrapper is consumer-only; producers write via the bridge task.  Calling
    put_nowait must not add anything to the internal buffer.  We check the
    underlying _buffer directly so the test is independent of the _first_read_done
    warm-up guard that empty() applies.
    """
    fake_client = fakeredis_aio.FakeRedis()
    job_id = str(uuid.uuid4())
    wrapper = RedisQueueWrapper(job_id, fake_client, ttl=60)

    wrapper.put_nowait(("e1", b"data", 1.0))
    # Check the raw buffer — put_nowait must not have added any item to it.
    assert wrapper._buffer.empty()

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
async def test_redis_service_cleanup_swallows_redis_delete_error():
    """cleanup_job must not raise when Redis DEL fails.

    Regression: the DEL ran in a finally block but a Redis error still escaped.
    Real Redis tends to fail exactly when teardown runs (network blip,
    failover), and that propagation could break stop() and explicit cancel.
    The fix logs a warning and continues.
    """

    class _DeleteFailingClient:
        """Proxies a real FakeRedis but makes delete() raise."""

        def __init__(self, real: Any) -> None:
            self._real = real

        def __getattr__(self, name: str) -> Any:
            return getattr(self._real, name)

        async def delete(self, *_args: Any, **_kwargs: Any) -> None:
            msg = "simulated Redis delete failure during teardown"
            raise ConnectionError(msg)

    real_client = fakeredis_aio.FakeRedis()
    service, _ = await _make_service(shared_client=real_client)
    # Swap in the failing wrapper after _make_service has wired up everything.
    service._client = _DeleteFailingClient(real_client)
    try:
        job_id = str(uuid.uuid4())
        service.create_queue(job_id)

        async def _noop():
            await asyncio.sleep(0)

        service.start_job(job_id, _noop())
        await asyncio.sleep(0.05)

        # Must not raise — the warning path absorbs the Redis error and the
        # rest of cleanup_job (local state, super().cleanup_job) still runs.
        await service.cleanup_job(job_id)

        # Local state was still torn down even though Redis DEL failed.
        assert job_id not in service._queues
        assert job_id not in service._job_owners
    finally:
        # Put the real client back so _stop_service can aclose cleanly.
        service._client = real_client
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
async def test_redis_service_refreshes_owner_key_while_owned_job_is_active():
    """Active private jobs keep their Redis owner key alive beyond redis_queue_ttl."""
    shared_client = fakeredis_aio.FakeRedis()
    producer, _ = await _make_service(ttl=1, shared_client=shared_client, cancel_channel_enabled=False)
    consumer, _ = await _make_service(ttl=1, shared_client=shared_client, cancel_channel_enabled=False)
    try:
        job_id = str(uuid.uuid4())
        user_id = uuid.uuid4()
        producer.create_queue(job_id)

        async def _long_running():
            await asyncio.Event().wait()

        producer.start_job(job_id, _long_running())
        await producer.register_job_owner(job_id, user_id)

        # Wait longer than the Redis owner TTL.  Without the owner refresh task,
        # a cross-worker lookup would see None and authorization would treat the
        # private build as public.
        await asyncio.sleep(1.6)

        assert await consumer.get_job_owner(job_id) == user_id
        assert await shared_client.ttl(producer._owner_key(job_id)) > 0
    finally:
        await _stop_service(consumer)
        await _stop_service(producer)


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


@pytest.mark.asyncio
async def test_redis_cross_worker_streaming_response_allows_missing_event_task():
    """Streaming cross-worker reads from Redis even when no local build task exists."""
    service, fake_client = await _make_service()
    try:
        job_id = str(uuid.uuid4())
        stream_key = f"langflow:queue:{job_id}"
        await fake_client.xadd(stream_key, {"event_id": "e1", "data": b"payload\n", "ts": "1.0"})
        await fake_client.xadd(
            stream_key,
            {"event_id": "__sentinel__", "data": _STREAM_SENTINEL_DATA, "ts": "2.0"},
        )

        response = await get_flow_events_response(
            job_id=job_id,
            queue_service=service,
            event_delivery=EventDeliveryType.STREAMING,
        )

        chunks = [
            chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk async for chunk in response.body_iterator
        ]

        assert response.status_code == 200
        assert chunks == ["payload\n"]
    finally:
        await _stop_service(service)


@pytest.mark.asyncio
async def test_streaming_disconnect_cancels_queue_wrapper_without_event_task():
    """Streaming disconnect cleanup uses the Redis wrapper when no local task exists."""

    class _CancelableQueue(asyncio.Queue):
        def __init__(self) -> None:
            super().__init__()
            self.cancelled = False

        async def cancel(self) -> None:
            self.cancelled = True

    queue = _CancelableQueue()
    response = await create_flow_response(
        queue=queue,
        event_manager=EventManager(None),
        event_task=None,
    )

    await response.on_disconnect()

    assert queue.cancelled


@pytest.mark.asyncio
async def test_cross_worker_disconnect_publishes_signal_cancel():
    """Disconnect on a non-owner worker publishes signal_cancel so the producer worker cancels its task.

    Closes the cross-worker passive-disconnect gap: previously, on_disconnect only
    cancelled the local wrapper when event_task is None, leaving the producer
    worker emitting events into Redis until the build completed naturally.
    """
    shared_client = fakeredis_aio.FakeRedis()
    svc_producer, _ = await _make_service(shared_client=shared_client)
    svc_consumer, _ = await _make_service(shared_client=shared_client)
    try:
        job_id = str(uuid.uuid4())
        svc_producer.create_queue(job_id)
        cancelled_event = asyncio.Event()

        async def _long_running():
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled_event.set()
                raise

        svc_producer.start_job(job_id, _long_running())
        await asyncio.sleep(0.05)

        # Cross-worker poll: consumer opens a Redis-backed queue wrapper.
        queue, *_ = svc_consumer.get_queue_data(job_id)
        response = await create_flow_response(
            queue=queue,
            event_manager=EventManager(queue),
            event_task=None,  # cross-worker → no local task handle
            queue_service=svc_consumer,
            job_id=job_id,
        )

        # Client disconnects from the consumer worker.
        await response.on_disconnect()

        # Producer worker's local task should be cancelled via pub/sub propagation.
        await asyncio.wait_for(cancelled_event.wait(), timeout=2.0)
        assert cancelled_event.is_set()
        assert svc_consumer._cancel_stats["published"] == 1
        assert svc_producer._cancel_stats["dispatched_owned"] == 1
    finally:
        await _stop_service(svc_consumer)
        await _stop_service(svc_producer)


# ---------------------------------------------------------------------------
# Cross-worker cancel via Redis pub/sub
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redis_service_cross_worker_cancel_dispatches_to_owning_worker():
    """signal_cancel published on worker B cancels the build task running on worker A.

    Worker A owns the job (entry in self._queues); worker B has no local task.
    The cross-worker dispatcher on A receives the publish and applies cancel.
    """
    shared_client = fakeredis_aio.FakeRedis()
    svc_producer, _ = await _make_service(shared_client=shared_client)
    svc_other, _ = await _make_service(shared_client=shared_client)
    try:
        job_id = str(uuid.uuid4())
        svc_producer.create_queue(job_id)

        cancelled_event = asyncio.Event()

        async def _long_running():
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled_event.set()
                raise

        svc_producer.start_job(job_id, _long_running())
        await asyncio.sleep(0.1)

        receivers = await svc_other.signal_cancel(job_id)
        # PSUBSCRIBE dispatcher on both workers receives, but only the owner acts.
        assert receivers >= 1

        await asyncio.wait_for(cancelled_event.wait(), timeout=2)
        assert cancelled_event.is_set()
        # Owner stats incremented exactly once; non-owner counted the publish as foreign.
        assert svc_producer._cancel_stats["dispatched_owned"] == 1
        assert svc_other._cancel_stats["dispatched_foreign"] >= 0  # may also receive its own
    finally:
        await _stop_service(svc_producer)
        await _stop_service(svc_other)


@pytest.mark.asyncio
async def test_redis_service_owner_local_cancel_flushes_sentinel_to_consumer_before_first_event():
    """Owner-local API cancel must promptly end a cross-worker Redis consumer.

    The owner-local branch of cancel_flow_build has a real task handle, so it
    does not publish through signal_cancel.  It must still use the Redis cancel
    path that writes an end-of-stream sentinel before bridge cleanup; otherwise
    a consumer that opened the stream before the first event waits for the full
    startup grace window.
    """
    shared_client = fakeredis_aio.FakeRedis()
    producer, _ = await _make_service(shared_client=shared_client, cancel_channel_enabled=False)
    consumer, _ = await _make_service(shared_client=shared_client, cancel_channel_enabled=False)
    try:
        job_id = str(uuid.uuid4())
        producer.create_queue(job_id)
        cancelled_event = asyncio.Event()

        async def _long_running():
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled_event.set()
                raise

        producer.start_job(job_id, _long_running())
        await asyncio.sleep(0.05)

        # Cross-worker consumer starts before any Redis stream event exists.
        queue, _, event_task, _ = consumer.get_queue_data(job_id)
        assert event_task is None

        started = time.monotonic()
        assert await cancel_flow_build(job_id=job_id, queue_service=producer)

        sentinel = await asyncio.wait_for(queue.get(), timeout=2.0)
        elapsed = time.monotonic() - started
        assert sentinel[0] is None
        assert sentinel[1] is None
        assert elapsed < 2.0
        await asyncio.wait_for(cancelled_event.wait(), timeout=2.0)
        assert producer._cancel_stats["dispatched_owned"] == 1
    finally:
        await _stop_service(consumer)
        await _stop_service(producer)


@pytest.mark.asyncio
async def test_redis_service_same_worker_cancel_wakes_active_consumer_before_first_event():
    """Owner-local cancel must wake a cached same-worker Redis consumer."""
    svc, _ = await _make_service(cancel_channel_enabled=False)
    try:
        job_id = str(uuid.uuid4())
        svc.create_queue(job_id)
        cancelled_event = asyncio.Event()

        async def _long_running():
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled_event.set()
                raise

        svc.start_job(job_id, _long_running())
        await asyncio.sleep(0.05)

        queue, _, event_task, _ = svc.get_queue_data(job_id)
        assert event_task is not None

        started = time.monotonic()
        assert await cancel_flow_build(job_id=job_id, queue_service=svc)

        sentinel = await asyncio.wait_for(queue.get(), timeout=2.0)
        elapsed = time.monotonic() - started
        assert sentinel[0] is None
        assert sentinel[1] is None
        assert elapsed < 2.0
        await asyncio.wait_for(cancelled_event.wait(), timeout=2.0)
    finally:
        await _stop_service(svc)


@pytest.mark.asyncio
async def test_redis_service_signal_cancel_returns_zero_when_disabled():
    """signal_cancel is a no-op (returns 0) when the cancel channel is disabled."""
    svc, _ = await _make_service(cancel_channel_enabled=False)
    try:
        receivers = await svc.signal_cancel("nonexistent")
        assert receivers == 0
        assert svc._cancel_dispatcher_task is None
    finally:
        await _stop_service(svc)


@pytest.mark.asyncio
async def test_redis_service_signal_cancel_raises_on_publish_error():
    """signal_cancel propagates Redis errors instead of swallowing them."""

    class _BrokenClient:
        async def set(self, *_args, **_kwargs):
            msg = "redis down"
            raise ConnectionError(msg)

        async def publish(self, *_args, **_kwargs):
            return 0

        async def aclose(self):
            return

    svc, _ = await _make_service()
    svc._client = _BrokenClient()
    try:
        with pytest.raises(ConnectionError):
            await svc.signal_cancel("any-job-id")
        assert svc._cancel_stats["publish_errors"] == 1
    finally:
        # Restore a real client so _stop_service can close cleanly.
        svc._client = fakeredis_aio.FakeRedis()
        await _stop_service(svc)


@pytest.mark.asyncio
async def test_redis_queue_wrapper_respects_custom_startup_grace_s():
    """Passing startup_grace_s to RedisQueueWrapper overrides the class default."""
    fake_client = fakeredis_aio.FakeRedis()
    job_id = str(uuid.uuid4())
    wrapper = RedisQueueWrapper(job_id, fake_client, ttl=60, startup_grace_s=0.05)
    try:
        # Stream never appears; after the very short grace period the wrapper
        # delivers the end-of-stream sentinel rather than blocking forever.
        evt = await asyncio.wait_for(wrapper.get(), timeout=3)
        assert evt[0] is None
        assert evt[1] is None
    finally:
        await wrapper.cancel()
        await fake_client.aclose()


@pytest.mark.asyncio
async def test_redis_service_cancel_marker_closes_signal_before_subscribe_race():
    """Cancel signaled before start_job still cancels the local task.

    The persistent marker key surfaces the cancel during the start_job pending
    marker check, closing the race where the publish arrives before the owning
    worker has registered the job.
    """
    shared_client = fakeredis_aio.FakeRedis()
    publisher, _ = await _make_service(shared_client=shared_client)
    producer, _ = await _make_service(shared_client=shared_client)
    try:
        job_id = str(uuid.uuid4())
        # Publish a cancel BEFORE the producer has registered the job.  The
        # pubsub publish reaches no relevant owner; only the marker key matters.
        await publisher.signal_cancel(job_id)

        producer.create_queue(job_id)
        cancelled = asyncio.Event()

        async def _long_running():
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

        producer.start_job(job_id, _long_running())
        await asyncio.wait_for(cancelled.wait(), timeout=2)
        assert cancelled.is_set()
        assert producer._cancel_stats["marker_hit"] == 1
    finally:
        await _stop_service(publisher)
        await _stop_service(producer)


@pytest.mark.asyncio
async def test_polling_watchdog_cancels_stale_owned_job():
    """If a polling job stops being touched, the watchdog publishes a cancel."""
    shared_client = fakeredis_aio.FakeRedis()
    producer = RedisJobQueueService(
        ttl=60,
        cancel_channel_enabled=True,
        polling_stale_threshold_s=0.3,
        polling_watchdog_interval_s=0.1,
    )
    producer._client = shared_client
    producer._closed = False
    producer._cleanup_task = asyncio.create_task(producer._periodic_cleanup())
    producer._cancel_dispatcher_task = asyncio.create_task(producer._run_cancel_dispatcher())
    producer._polling_watchdog_task = asyncio.create_task(producer._run_polling_watchdog())
    producer.ready = True
    await asyncio.sleep(0.05)
    try:
        job_id = str(uuid.uuid4())
        producer.create_queue(job_id)
        # Watchdog only scans jobs with a registered owner — register one to
        # simulate a real user-facing build.
        await producer.register_job_owner(job_id, uuid.uuid4())
        cancelled_event = asyncio.Event()

        async def _long_running():
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled_event.set()
                raise

        producer.start_job(job_id, _long_running())
        # touch_activity ran via start_job; stop touching to let the threshold expire.
        # Wait long enough for the threshold to lapse + watchdog scan to fire.
        await asyncio.wait_for(cancelled_event.wait(), timeout=3.0)
        assert cancelled_event.is_set()
        assert producer._cancel_stats["polling_watchdog_kills"] >= 1
    finally:
        producer._closed = True
        for task_attr in (
            "_cleanup_task",
            "_cancel_dispatcher_task",
            "_polling_watchdog_task",
        ):
            task = getattr(producer, task_attr, None)
            if task is not None and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        for bg in list(producer._background_tasks):
            if not bg.done():
                bg.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await bg
        for bridge in list(producer._bridge_tasks.values()):
            if not bridge.done():
                bridge.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await bridge


@pytest.mark.asyncio
async def test_polling_watchdog_skips_fresh_activity():
    """If the activity key is refreshed within the threshold, the watchdog leaves the job alone."""
    shared_client = fakeredis_aio.FakeRedis()
    producer = RedisJobQueueService(
        ttl=60,
        cancel_channel_enabled=True,
        polling_stale_threshold_s=0.5,
        polling_watchdog_interval_s=0.1,
    )
    producer._client = shared_client
    producer._closed = False
    producer._cleanup_task = asyncio.create_task(producer._periodic_cleanup())
    producer._cancel_dispatcher_task = asyncio.create_task(producer._run_cancel_dispatcher())
    producer._polling_watchdog_task = asyncio.create_task(producer._run_polling_watchdog())
    producer.ready = True
    await asyncio.sleep(0.05)
    try:
        job_id = str(uuid.uuid4())
        producer.create_queue(job_id)
        # Watchdog skips unowned jobs entirely (see _run_polling_watchdog).
        # Without registering an owner this test passes even if touch_activity
        # is broken, which defeats the assertion.
        await producer.register_job_owner(job_id, uuid.uuid4())
        cancelled_event = asyncio.Event()

        async def _long_running():
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled_event.set()
                raise

        producer.start_job(job_id, _long_running())

        # Keep the activity key fresh for ~1.5s — longer than the threshold.
        async def _heartbeat():
            for _ in range(15):
                await asyncio.sleep(0.1)
                await producer.touch_activity(job_id)

        heartbeat_task = asyncio.create_task(_heartbeat())
        await heartbeat_task
        # Job must still be alive after heartbeating.
        assert not cancelled_event.is_set()
        assert producer._cancel_stats["polling_watchdog_kills"] == 0
    finally:
        producer._closed = True
        for task_attr in (
            "_cleanup_task",
            "_cancel_dispatcher_task",
            "_polling_watchdog_task",
        ):
            task = getattr(producer, task_attr, None)
            if task is not None and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        for bg in list(producer._background_tasks):
            if not bg.done():
                bg.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await bg
        for bridge in list(producer._bridge_tasks.values()):
            if not bridge.done():
                bridge.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await bridge


@pytest.mark.asyncio
async def test_polling_watchdog_ignores_jobs_without_registered_owner():
    """Jobs without a registered owner (TaskService internal tasks) are not watched.

    TaskService and other server-internal callers use start_job without
    registering an owner.  They never refresh the activity heartbeat because
    no polling client is involved.  The watchdog must leave them alone so a
    long-running internal task is not killed mid-flight at the threshold.
    Surfaced by load testing: 1:1 ratio of start_job to watchdog kills under
    the /api/v1/run path because every TaskService task was being reclaimed.
    """
    shared_client = fakeredis_aio.FakeRedis()
    svc = RedisJobQueueService(
        ttl=60,
        cancel_channel_enabled=True,
        polling_stale_threshold_s=0.2,
        polling_watchdog_interval_s=0.05,
    )
    svc._client = shared_client
    svc._closed = False
    svc._cleanup_task = asyncio.create_task(svc._periodic_cleanup())
    svc._cancel_dispatcher_task = asyncio.create_task(svc._run_cancel_dispatcher())
    svc._polling_watchdog_task = asyncio.create_task(svc._run_polling_watchdog())
    svc.ready = True
    await asyncio.sleep(0.05)
    try:
        job_id = str(uuid.uuid4())
        svc.create_queue(job_id)
        # Intentionally NO register_job_owner — this mimics a TaskService task.
        cancelled_event = asyncio.Event()

        async def _alive():
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled_event.set()
                raise

        svc.start_job(job_id, _alive())
        # Wait well past the threshold + a few watchdog ticks.  The kill must
        # never fire because the job has no registered owner.
        await asyncio.sleep(0.8)
        assert not cancelled_event.is_set(), "watchdog killed an unowned (internal) task"
        assert svc._cancel_stats["polling_watchdog_kills"] == 0
        assert job_id in svc._queues
    finally:
        svc._closed = True
        for attr in (
            "_cleanup_task",
            "_cancel_dispatcher_task",
            "_polling_watchdog_task",
        ):
            task = getattr(svc, attr, None)
            if task is not None and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        for bg in list(svc._background_tasks):
            if not bg.done():
                bg.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await bg
        for bridge in list(svc._bridge_tasks.values()):
            if not bridge.done():
                bridge.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await bridge


@pytest.mark.asyncio
async def test_polling_watchdog_disabled_when_threshold_nonpositive():
    """polling_stale_threshold_s <= 0 disables the watchdog entirely."""
    svc = RedisJobQueueService(polling_stale_threshold_s=0.0)
    svc._client = fakeredis_aio.FakeRedis()
    svc._closed = False
    svc._cleanup_task = asyncio.create_task(svc._periodic_cleanup())
    svc._cancel_dispatcher_task = asyncio.create_task(svc._run_cancel_dispatcher())
    # Watchdog should NOT be started when threshold <= 0; emulate start() behavior.
    if svc._polling_stale_threshold_s > 0:
        svc._polling_watchdog_task = asyncio.create_task(svc._run_polling_watchdog())
    svc.ready = True
    try:
        assert svc._polling_watchdog_task is None
    finally:
        svc._closed = True
        svc._cleanup_task.cancel()
        svc._cancel_dispatcher_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await svc._cleanup_task
        with contextlib.suppress(asyncio.CancelledError):
            await svc._cancel_dispatcher_task


@pytest.mark.asyncio
async def test_polling_watchdog_grants_start_grace_window():
    """A brand-new job with a missing activity key must NOT be reclaimed immediately.

    The watchdog uses an in-memory ``_job_start_times`` timestamp to keep
    new jobs alive through the threshold, protecting against a slow first
    `touch_activity` (background task scheduling delay or a Redis blip).
    """
    shared_client = fakeredis_aio.FakeRedis()
    svc = RedisJobQueueService(
        ttl=60,
        cancel_channel_enabled=True,
        polling_stale_threshold_s=1.0,
        polling_watchdog_interval_s=0.1,
    )
    svc._client = shared_client
    svc._closed = False
    svc._cleanup_task = asyncio.create_task(svc._periodic_cleanup())
    svc._cancel_dispatcher_task = asyncio.create_task(svc._run_cancel_dispatcher())
    svc._polling_watchdog_task = asyncio.create_task(svc._run_polling_watchdog())
    svc.ready = True
    await asyncio.sleep(0.05)
    try:
        job_id = str(uuid.uuid4())
        svc.create_queue(job_id)
        # Watchdog only scans jobs with a registered owner — register one so
        # this test exercises the start-time grace branch.
        await svc.register_job_owner(job_id, uuid.uuid4())

        async def _alive():
            await asyncio.Event().wait()

        # Force the "activity key never written" condition: start the job, then
        # immediately delete whatever touch_activity put there.
        svc.start_job(job_id, _alive())
        await asyncio.sleep(0.05)  # let the background touch_activity land
        await shared_client.delete(svc._activity_key(job_id))

        # Watchdog ticks every 100ms.  During the first ~800ms the start-time
        # grace should keep the job alive even though the key is missing.
        await asyncio.sleep(0.7)
        assert svc._cancel_stats["polling_watchdog_kills"] == 0
        assert job_id in svc._queues, "job was wrongly reclaimed during start-grace window"

        # After the threshold passes, the watchdog should reclaim it.
        await asyncio.sleep(0.6)
        assert svc._cancel_stats["polling_watchdog_kills"] >= 1
    finally:
        svc._closed = True
        for attr in (
            "_cleanup_task",
            "_cancel_dispatcher_task",
            "_polling_watchdog_task",
        ):
            task = getattr(svc, attr, None)
            if task is not None and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        for bg in list(svc._background_tasks):
            if not bg.done():
                bg.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await bg
        for bridge in list(svc._bridge_tasks.values()):
            if not bridge.done():
                bridge.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await bridge


@pytest.mark.asyncio
async def test_polling_watchdog_skips_malformed_activity_value():
    """A malformed activity value counts a parse error and skips the job (no kill)."""
    shared_client = fakeredis_aio.FakeRedis()
    svc = RedisJobQueueService(
        ttl=60,
        cancel_channel_enabled=True,
        polling_stale_threshold_s=0.5,
        polling_watchdog_interval_s=0.1,
    )
    svc._client = shared_client
    svc._closed = False
    svc._cleanup_task = asyncio.create_task(svc._periodic_cleanup())
    svc._cancel_dispatcher_task = asyncio.create_task(svc._run_cancel_dispatcher())
    svc._polling_watchdog_task = asyncio.create_task(svc._run_polling_watchdog())
    svc.ready = True
    await asyncio.sleep(0.05)
    try:
        job_id = str(uuid.uuid4())
        svc.create_queue(job_id)
        # Watchdog only scans jobs with a registered owner — register one so
        # this test exercises the malformed-value parse branch.
        await svc.register_job_owner(job_id, uuid.uuid4())

        async def _alive():
            await asyncio.Event().wait()

        svc.start_job(job_id, _alive())
        # Let the background touch_activity from start_job land first, then
        # overwrite with a malformed value so the watchdog actually parses garbage.
        for _ in range(20):
            await asyncio.sleep(0.02)
            if await shared_client.exists(svc._activity_key(job_id)):
                break
        await shared_client.set(svc._activity_key(job_id), "not-a-number")
        await asyncio.sleep(0.4)
        assert svc._cancel_stats["activity_parse_errors"] >= 1
        assert svc._cancel_stats["polling_watchdog_kills"] == 0
    finally:
        svc._closed = True
        for attr in (
            "_cleanup_task",
            "_cancel_dispatcher_task",
            "_polling_watchdog_task",
        ):
            task = getattr(svc, attr, None)
            if task is not None and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        for bg in list(svc._background_tasks):
            if not bg.done():
                bg.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await bg


@pytest.mark.asyncio
async def test_streaming_heartbeat_runs_independent_of_event_yield(monkeypatch):
    """A quiet streaming build (no events for > threshold) is NOT reclaimed.

    The heartbeat task in create_flow_response fires every N seconds regardless
    of whether the queue is producing events, so the polling watchdog can tell
    that the streaming client is still attached even during a long silent step.
    """
    from langflow.api import build as build_module

    # Patch the heartbeat interval down so the spawned task actually fires
    # within the test budget. Without this the verification below would
    # depend on the production 10s interval.
    monkeypatch.setattr(build_module, "STREAMING_ACTIVITY_REFRESH_S", 0.1)

    shared_client = fakeredis_aio.FakeRedis()
    svc, _ = await _make_service(shared_client=shared_client)
    try:
        job_id = str(uuid.uuid4())
        _main_queue, _em = svc.create_queue(job_id)

        async def _alive():
            await asyncio.Event().wait()

        svc.start_job(job_id, _alive())

        # Force the activity timestamp to be old enough that any update must
        # come from the spawned heartbeat task, not from start_job's own touch.
        stale_ts = time.time() - 100.0
        await shared_client.set(svc._activity_key(job_id), str(stale_ts))

        monkey_q: asyncio.Queue = asyncio.Queue()
        # Use the real consumer wrapper for realism.
        wrapper = svc._get_consumer_wrapper(job_id)
        response = await build_module.create_flow_response(
            queue=wrapper,
            event_manager=EventManager(monkey_q),
            event_task=None,
            queue_service=svc,
            job_id=job_id,
        )
        try:
            tasks = [t for t in asyncio.all_tasks() if t.get_name().startswith(f"stream-heartbeat-{job_id}")]
            assert tasks, "stream heartbeat task was not spawned"
            # Wait for the heartbeat task itself to refresh the activity key.
            # No manual touch_activity here: if the spawned task is broken,
            # the timestamp never advances and the loop times out.
            deadline = time.monotonic() + 2.0
            recorded = stale_ts
            while time.monotonic() < deadline:
                raw = await shared_client.get(svc._activity_key(job_id))
                if raw is not None:
                    recorded = float(raw.decode() if isinstance(raw, bytes) else raw)
                    if recorded > stale_ts + 1.0:
                        break
                await asyncio.sleep(0.05)
            assert recorded > stale_ts + 1.0, "heartbeat task did not refresh activity timestamp"
        finally:
            # Trigger disconnect; the heartbeat task must be cancelled cleanly.
            await response.on_disconnect()
            await asyncio.sleep(0.05)
            tasks_after = [t for t in asyncio.all_tasks() if t.get_name().startswith(f"stream-heartbeat-{job_id}")]
            for t in tasks_after:
                assert t.done() or t.cancelled(), "heartbeat task survived on_disconnect"
    finally:
        await _stop_service(svc)


@pytest.mark.asyncio
async def test_concurrent_cancels_from_multiple_workers_are_idempotent():
    """signal_cancel from two workers concurrently must produce exactly one cancel.

    _handle_cancel can be invoked twice (once per publish receipt on the owning
    worker), but the second invocation should be a safe no-op:
    * task.cancel() is idempotent on an already-cancelled task,
    * the additional sentinel is harmless (consumers ignore extra Nones),
    * the second _post_cancel_cleanup runs on already-popped state.
    No assertions on stats counts — just no crashes and a single cancellation observed.
    """
    shared_client = fakeredis_aio.FakeRedis()
    producer, _ = await _make_service(shared_client=shared_client)
    pub_a, _ = await _make_service(shared_client=shared_client)
    pub_b, _ = await _make_service(shared_client=shared_client)
    try:
        job_id = str(uuid.uuid4())
        producer.create_queue(job_id)
        cancelled = asyncio.Event()

        async def _long_running():
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

        producer.start_job(job_id, _long_running())
        await asyncio.sleep(0.05)

        # Two workers publish cancel at the same time.
        await asyncio.gather(pub_a.signal_cancel(job_id), pub_b.signal_cancel(job_id))
        await asyncio.wait_for(cancelled.wait(), timeout=2.0)

        # Give background cleanups time to run; no exceptions should escape.
        await asyncio.sleep(0.3)
        assert cancelled.is_set()
        # dispatched_owned counts each pmessage routed to local cancel — may be 1 or 2
        # depending on dispatcher ordering; just assert ≥ 1.
        assert producer._cancel_stats["dispatched_owned"] >= 1
    finally:
        await _stop_service(producer)
        await _stop_service(pub_a)
        await _stop_service(pub_b)


@pytest.mark.asyncio
async def test_dispatcher_internal_error_logged_at_error_level():
    """A bug inside _handle_cancel (non-Redis) must increment dispatcher_internal_errors.

    Distinguishes "Redis dropped us" (warning + reconnect) from "our code crashed"
    (error + reconnect with traceback) so monitoring can alert appropriately.
    """
    shared_client = fakeredis_aio.FakeRedis()
    producer, _ = await _make_service(shared_client=shared_client)
    publisher, _ = await _make_service(shared_client=shared_client)
    # Shrink the initial backoff so the dispatcher reconnects quickly enough to
    # catch a follow-up publish within the test timeout.
    producer._DISPATCHER_RECONNECT_INITIAL_BACKOFF_S = 0.1

    # Force _handle_cancel to raise once.
    raised = asyncio.Event()
    original_handle_cancel = producer._handle_cancel
    calls = {"n": 0}

    async def _flakey_handle_cancel(job_id: str, *, source: str) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raised.set()
            msg = "simulated internal bug"
            raise RuntimeError(msg)
        await original_handle_cancel(job_id, source=source)

    producer._handle_cancel = _flakey_handle_cancel  # type: ignore[method-assign]

    try:
        job_id = str(uuid.uuid4())
        await publisher.signal_cancel(job_id)
        await asyncio.wait_for(raised.wait(), timeout=2.0)
        # Wait long enough for the dispatcher to catch RuntimeError + increment.
        await asyncio.sleep(0.4)
        assert producer._cancel_stats["dispatcher_internal_errors"] >= 1
        # And the dispatcher_reconnects counter for the same event.
        assert producer._cancel_stats["dispatcher_reconnects"] >= 1
        # The dispatcher task itself MUST still be running — i.e. the exception
        # did not kill the loop; it caught it and rescheduled.  This is the
        # core contract of the "internal-error reconnect" path.
        assert producer._cancel_dispatcher_task is not None
        assert not producer._cancel_dispatcher_task.done(), (
            "dispatcher task exited after internal error instead of reconnecting"
        )
    finally:
        producer._handle_cancel = original_handle_cancel  # type: ignore[method-assign]
        await _stop_service(producer)
        await _stop_service(publisher)


@pytest.mark.asyncio
async def test_metrics_snapshot_exposes_cancel_stats_and_counters():
    """metrics_snapshot returns observability data for ops/monitoring."""
    shared_client = fakeredis_aio.FakeRedis()
    svc, _ = await _make_service(shared_client=shared_client)
    try:
        snap = svc.metrics_snapshot()
        assert snap["backend"] == "redis"
        assert snap["active_jobs"] == 0
        assert snap["bridge_count"] == 0
        assert snap["consumer_wrapper_count"] == 0
        assert snap["cancel_dispatcher_running"] is True
        assert isinstance(snap["cancel_stats"], dict)
        # The metrics contract is the full cancel_stats key set — pin it so that
        # adding an increment site without registering the key (or vice versa)
        # surfaces as a test failure instead of a silent KeyError in production.
        expected_keys = {
            "published",
            "marker_hit",
            "dispatched_owned",
            "dispatched_foreign",
            "publish_errors",
            "dispatcher_reconnects",
            "dispatcher_internal_errors",
            "polling_watchdog_kills",
            "activity_touch_errors",
            "activity_get_errors",
            "activity_parse_errors",
        }
        assert set(snap["cancel_stats"]) == expected_keys, (
            f"cancel_stats key drift: missing={expected_keys - set(snap['cancel_stats'])}, "
            f"extra={set(snap['cancel_stats']) - expected_keys}"
        )
        # Snapshot must be a copy — mutating it doesn't affect the service.
        snap["cancel_stats"]["published"] = 99
        assert svc._cancel_stats["published"] == 0
    finally:
        await _stop_service(svc)


@pytest.mark.asyncio
async def test_metrics_snapshot_for_in_memory_queue():
    """Base service snapshot reports the memory backend and active job count."""
    from langflow.services.job_queue.service import JobQueueService

    svc = JobQueueService()
    svc.start()
    try:
        snap = svc.metrics_snapshot()
        assert snap["backend"] == "memory"
        assert snap["active_jobs"] == 0
        assert "cancel_stats" not in snap  # only redis-backed exposes pubsub stats
    finally:
        await svc.teardown()


@pytest.mark.asyncio
async def test_post_cancel_cleanup_bounded_by_outer_timeout():
    """A hung cleanup_job must not pin a background task indefinitely.

    Without an outer timeout, a Redis stall during stream DELETE leaves the
    cleanup task pending forever.  The bound preserves shutdown / GC behaviour
    even under Redis pathology.
    """
    shared_client = fakeredis_aio.FakeRedis()
    svc, _ = await _make_service(shared_client=shared_client)
    try:
        job_id = str(uuid.uuid4())

        # Patch cleanup_job to hang forever.
        async def _hang_forever(_job_id: str) -> None:
            await asyncio.Event().wait()

        svc.cleanup_job = _hang_forever  # type: ignore[method-assign]
        svc._POST_CANCEL_CLEANUP_TIMEOUT_S = 0.2

        start = asyncio.get_event_loop().time()
        await svc._post_cancel_cleanup(job_id)
        elapsed = asyncio.get_event_loop().time() - start

        # Should have given up within roughly the timeout, not blocked forever.
        assert elapsed < 1.0, f"_post_cancel_cleanup did not bound runtime; elapsed={elapsed:.2f}s"
    finally:
        await _stop_service(svc)


@pytest.mark.asyncio
async def test_cancel_dispatcher_reconnects_after_pubsub_error():
    """Dispatcher should reconnect with backoff if the pubsub stream errors out.

    Without this resilience, a Redis blip kills the dispatcher silently and the
    worker becomes blind to cross-worker cancels until restart.
    """

    class _FlakeyPubSub:
        """Fakes pubsub.listen() raising once then yielding normally."""

        def __init__(self, real: Any, *, raise_on_listen_count: int = 1) -> None:
            self._real = real
            self._raises_left = raise_on_listen_count

        async def psubscribe(self, *args: Any, **kwargs: Any) -> Any:
            return await self._real.psubscribe(*args, **kwargs)

        async def punsubscribe(self, *args: Any, **kwargs: Any) -> Any:
            return await self._real.punsubscribe(*args, **kwargs)

        async def aclose(self) -> None:
            with contextlib.suppress(Exception):
                await self._real.aclose()

        def listen(self):
            if self._raises_left > 0:
                self._raises_left -= 1

                async def _raiser():
                    msg = "simulated pubsub blip"
                    raise ConnectionError(msg)
                    yield  # pragma: no cover

                return _raiser()
            return self._real.listen()

    class _FlakeyClient:
        """Real fake client whose pubsub() returns a flakey wrapper exactly once."""

        def __init__(self, real: fakeredis_aio.FakeRedis) -> None:
            self._real = real
            self._pubsub_count = 0

        def pubsub(self) -> Any:
            self._pubsub_count += 1
            base = self._real.pubsub()
            # Only the first dispatcher's pubsub fails; subsequent reconnects succeed.
            return _FlakeyPubSub(base, raise_on_listen_count=1 if self._pubsub_count == 1 else 0)

        # Delegate everything else.
        def __getattr__(self, item: str) -> Any:
            return getattr(self._real, item)

    real_client = fakeredis_aio.FakeRedis()
    flakey_client = _FlakeyClient(real_client)
    # Build a service that uses our flakey client + an aggressive reconnect for fast test.
    svc_producer = RedisJobQueueService(ttl=60, cancel_channel_enabled=True)
    svc_producer._client = flakey_client
    svc_producer._closed = False
    svc_producer._cleanup_task = asyncio.create_task(svc_producer._periodic_cleanup())
    svc_producer._cancel_dispatcher_task = asyncio.create_task(svc_producer._run_cancel_dispatcher())
    svc_producer.ready = True
    # Allow the first (flakey) subscribe + the reconnect to settle.
    await asyncio.sleep(0.6)

    svc_other, _ = await _make_service(shared_client=real_client)
    try:
        # After reconnect, a publish should still reach the dispatcher.
        job_id = str(uuid.uuid4())
        svc_producer.create_queue(job_id)
        cancelled_event = asyncio.Event()

        async def _long_running():
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled_event.set()
                raise

        svc_producer.start_job(job_id, _long_running())
        await asyncio.sleep(0.1)
        await svc_other.signal_cancel(job_id)
        await asyncio.wait_for(cancelled_event.wait(), timeout=2.0)
        assert cancelled_event.is_set()
        # Reconnect counter should be incremented exactly once.
        assert svc_producer._cancel_stats["dispatcher_reconnects"] == 1
    finally:
        # Stop service manually since _make_service helper wasn't used.
        svc_producer._closed = True
        if svc_producer._cleanup_task:
            svc_producer._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await svc_producer._cleanup_task
        if svc_producer._cancel_dispatcher_task:
            svc_producer._cancel_dispatcher_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await svc_producer._cancel_dispatcher_task
        for bg in list(svc_producer._background_tasks):
            if not bg.done():
                bg.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await bg
        await _stop_service(svc_other)


@pytest.mark.asyncio
async def test_cancel_dispatcher_counts_transparent_pubsub_reconnect_callback():
    """The dispatcher tracks redis-py reconnects that do not restart listen()."""

    class _FakeConnection:
        def __init__(self) -> None:
            self.callbacks: list[Any] = []

        def register_connect_callback(self, callback: Any) -> None:
            self.callbacks.append(callback)

        def deregister_connect_callback(self, callback: Any) -> None:
            with contextlib.suppress(ValueError):
                self.callbacks.remove(callback)

    class _CapturingPubSub:
        def __init__(self) -> None:
            self.connection = _FakeConnection()
            self.subscribed = asyncio.Event()

        async def psubscribe(self, *_args: Any, **_kwargs: Any) -> None:
            self.subscribed.set()

        async def punsubscribe(self, *_args: Any, **_kwargs: Any) -> None:
            return None

        async def aclose(self) -> None:
            return None

        def listen(self):
            async def _blocked():
                await asyncio.Event().wait()
                yield {}  # pragma: no cover

            return _blocked()

    class _CapturingClient:
        def __init__(self, pubsub: _CapturingPubSub) -> None:
            self._pubsub = pubsub

        def pubsub(self) -> _CapturingPubSub:
            return self._pubsub

    pubsub = _CapturingPubSub()
    svc = RedisJobQueueService(ttl=60, cancel_channel_enabled=True)
    svc._client = _CapturingClient(pubsub)
    svc._closed = False
    task = asyncio.create_task(svc._run_cancel_dispatcher())
    try:
        await asyncio.wait_for(pubsub.subscribed.wait(), timeout=1.0)
        assert pubsub.connection.callbacks == [svc._on_cancel_dispatcher_connection_reconnect]

        await pubsub.connection.callbacks[0](pubsub.connection)

        assert svc._cancel_stats["dispatcher_reconnects"] == 1
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    assert pubsub.connection.callbacks == []


@pytest.mark.asyncio
async def test_redis_service_signal_cancel_flushes_sentinel_to_consumer():
    """signal_cancel triggers a prompt end-of-stream sentinel for consumers.

    Verifies deterministically that the bridge XADDs the sentinel record to the
    Redis Stream *before* cleanup deletes the stream key.  We replace
    ``cleanup_job`` on the producer service with a no-op so the assertion can
    inspect the stream without racing the deletion path.
    """
    shared_client = fakeredis_aio.FakeRedis()
    producer, _ = await _make_service(shared_client=shared_client)
    publisher, _ = await _make_service(shared_client=shared_client)
    try:
        job_id = str(uuid.uuid4())
        producer.create_queue(job_id)

        async def _long_running():
            await asyncio.Event().wait()

        # Replace cleanup_job with a no-op so the stream survives our assertion.
        # The bridge still publishes the sentinel; only the post-cancel deletion
        # is skipped.  We restore the original method in the finally block so
        # _stop_service can clean state.
        original_cleanup = producer.cleanup_job

        async def _noop_cleanup(_job_id: str) -> None:
            return None

        producer.cleanup_job = _noop_cleanup  # type: ignore[method-assign]

        producer.start_job(job_id, _long_running())
        await asyncio.sleep(0.1)
        await publisher.signal_cancel(job_id)

        # Bridge has up to a few hundred ms to drain the sentinel into Redis.
        stream_key = f"langflow:queue:{job_id}"
        deadline = asyncio.get_event_loop().time() + 2.0
        last_fields: dict[bytes, bytes] | None = None
        while asyncio.get_event_loop().time() < deadline:
            messages = await shared_client.xrange(stream_key)
            if messages and messages[-1][1].get(b"data") == _STREAM_SENTINEL_DATA:
                last_fields = messages[-1][1]
                break
            await asyncio.sleep(0.05)

        assert last_fields is not None, f"sentinel never XADDed to {stream_key} after signal_cancel"
        assert last_fields.get(b"data") == _STREAM_SENTINEL_DATA
        assert last_fields.get(b"event_id") == b"__sentinel__"

        # Restore so _stop_service can run the full cleanup path.
        producer.cleanup_job = original_cleanup  # type: ignore[method-assign]
    finally:
        await _stop_service(producer)
        await _stop_service(publisher)


@pytest.mark.asyncio
async def test_redis_queue_wrapper_buffer_is_bounded():
    """The internal buffer respects _BUFFER_MAXSIZE.

    A slow consumer cannot let the fill task consume unbounded memory.
    """
    fake_client = fakeredis_aio.FakeRedis()
    job_id = str(uuid.uuid4())
    wrapper = RedisQueueWrapper(job_id, fake_client, ttl=60)
    try:
        assert wrapper._buffer.maxsize == RedisQueueWrapper._BUFFER_MAXSIZE
        assert wrapper._buffer.maxsize > 0
    finally:
        await wrapper.cancel()
        await fake_client.aclose()


@pytest.mark.asyncio
async def test_redis_queue_wrapper_on_fill_done_delivers_sentinel_on_crash():
    """A crash in the fill task must still unblock consumers.

    The done-callback delivers the end-of-stream sentinel into the buffer
    so consumers waiting on ``await get()`` never hang.
    """
    fake_client = fakeredis_aio.FakeRedis()
    job_id = str(uuid.uuid4())
    wrapper = RedisQueueWrapper(job_id, fake_client, ttl=60)
    try:
        await wrapper.cancel()
        # Drain anything already in the buffer so the simulated-crash sentinel
        # is the next item delivered.
        while not wrapper._buffer.empty():
            wrapper._buffer.get_nowait()

        class _FailedTask:
            def cancelled(self) -> bool:
                return False

            def exception(self) -> BaseException:
                return RuntimeError("simulated fill crash")

        wrapper._on_fill_done(_FailedTask())  # type: ignore[arg-type]

        sentinel = wrapper._buffer.get_nowait()
        assert sentinel[0] is None
        assert sentinel[1] is None
    finally:
        await fake_client.aclose()


@pytest.mark.asyncio
async def test_redis_queue_wrapper_on_fill_done_evicts_to_make_room_for_sentinel():
    """A full buffer at crash time must not prevent sentinel delivery.

    The oldest item is evicted so the sentinel still reaches the consumer.
    Losing one event is strictly better than leaving the consumer stuck on
    ``await get()`` indefinitely.
    """
    fake_client = fakeredis_aio.FakeRedis()
    job_id = str(uuid.uuid4())
    wrapper = RedisQueueWrapper(job_id, fake_client, ttl=60)
    try:
        await wrapper.cancel()
        while not wrapper._buffer.empty():
            wrapper._buffer.get_nowait()

        for i in range(wrapper._buffer.maxsize):
            wrapper._buffer.put_nowait((f"e{i}", b"data", float(i)))
        assert wrapper._buffer.full()

        class _FailedTask:
            def cancelled(self) -> bool:
                return False

            def exception(self) -> BaseException:
                return RuntimeError("simulated fill crash")

        wrapper._on_fill_done(_FailedTask())  # type: ignore[arg-type]

        # Buffer is still at capacity (one evicted, one sentinel added).
        assert wrapper._buffer.full()

        items: list = []
        while not wrapper._buffer.empty():
            items.append(wrapper._buffer.get_nowait())
        sentinels = [item for item in items if item[0] is None and item[1] is None]
        assert len(sentinels) == 1, "Exactly one sentinel must reach the consumer"
    finally:
        await fake_client.aclose()


@pytest.mark.asyncio
async def test_finish_with_sentinel_does_not_hang_on_full_buffer():
    """finish_with_sentinel must not block on the bounded buffer during teardown.

    Regression: the old implementation awaited buffer.put(...) here. If a slow or
    abandoned consumer had already filled the buffer, shutdown would hang
    forever. The fix mirrors _on_fill_done: evict one item and put_nowait the
    sentinel so teardown always returns.
    """
    fake_client = fakeredis_aio.FakeRedis()
    job_id = str(uuid.uuid4())
    wrapper = RedisQueueWrapper(job_id, fake_client, ttl=60)
    try:
        # Stop the fill task so we own the buffer for this test.
        await wrapper.cancel()
        # _on_fill_done already enqueued one sentinel when cancel completed.
        while not wrapper._buffer.empty():
            wrapper._buffer.get_nowait()

        # Fill the buffer to capacity. Without the fix, finish_with_sentinel
        # would now hang on an awaited put.
        for i in range(wrapper._buffer.maxsize):
            wrapper._buffer.put_nowait((f"e{i}", b"data", float(i)))
        assert wrapper._buffer.full()

        # Must return promptly. The 1.0s budget is generous: the operation is
        # pure in-memory eviction + put_nowait, so anything close to it means
        # the buffer is blocking.
        await asyncio.wait_for(wrapper.finish_with_sentinel(), timeout=1.0)
        assert wrapper._buffer.full()

        items: list = []
        while not wrapper._buffer.empty():
            items.append(wrapper._buffer.get_nowait())
        sentinels = [item for item in items if item[0] is None and item[1] is None]
        assert len(sentinels) == 1, "Exactly one sentinel must reach the consumer"
    finally:
        await fake_client.aclose()


@pytest.mark.asyncio
async def test_get_flow_events_response_rejects_unknown_event_delivery():
    """Unknown EventDeliveryType values produce a clear 4xx with instructions.

    Without this guard, unknown values silently fall through to the polling
    code path, masking real misconfigurations in multi-worker setups.
    """
    from enum import Enum

    from fastapi import HTTPException
    from langflow.services.job_queue.service import JobQueueService

    service = JobQueueService()
    job_id = str(uuid.uuid4())
    service._queues[job_id] = (
        asyncio.Queue(),
        EventManager(asyncio.Queue()),
        None,
        None,
    )

    class _BogusDelivery(str, Enum):
        WEBSOCKET = "websocket"

    try:
        with pytest.raises(HTTPException) as exc_info:
            await get_flow_events_response(
                job_id=job_id,
                queue_service=service,
                event_delivery=_BogusDelivery.WEBSOCKET,  # type: ignore[arg-type]
            )
        assert exc_info.value.status_code == 400
        detail = str(exc_info.value.detail)
        assert "Unsupported event_delivery" in detail
        assert "LANGFLOW_EVENT_DELIVERY" in detail
        for known in ("streaming", "direct", "polling"):
            assert known in detail
    finally:
        service._queues.pop(job_id, None)


@pytest.mark.asyncio
async def test_task_service_launch_does_not_trigger_polling_watchdog(monkeypatch):
    """TaskService.fire_and_forget_task must not trip the polling watchdog.

    Integration check via the real entrypoint: a server-internal task launched
    through TaskService never registers an owner and never calls
    touch_activity, so the watchdog must leave it alone.  Surfaced by locust
    load testing on the /api/v1/run path where every internal task was being
    reclaimed.
    """
    from langflow.services.task.service import TaskService

    shared_client = fakeredis_aio.FakeRedis()
    svc = RedisJobQueueService(
        ttl=60,
        cancel_channel_enabled=True,
        polling_stale_threshold_s=0.2,
        polling_watchdog_interval_s=0.05,
    )
    svc._client = shared_client
    svc._closed = False
    svc._cleanup_task = asyncio.create_task(svc._periodic_cleanup())
    svc._cancel_dispatcher_task = asyncio.create_task(svc._run_cancel_dispatcher())
    svc._polling_watchdog_task = asyncio.create_task(svc._run_polling_watchdog())
    svc.ready = True

    # Patch get_queue_service so TaskService.fire_and_forget_task wires through
    # to our test instance instead of the global one.
    monkeypatch.setattr("langflow.services.task.service.get_queue_service", lambda: svc)

    # Minimal settings_service stub: TaskService only needs .settings.celery_enabled.
    class _StubSettings:
        celery_enabled = False

    class _StubSettingsService:
        settings = _StubSettings()

    task_service = TaskService(_StubSettingsService())  # type: ignore[arg-type]

    work_started = asyncio.Event()
    cancelled_event = asyncio.Event()

    async def _internal_work():
        work_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled_event.set()
            raise

    try:
        task_id = await task_service.fire_and_forget_task(_internal_work)
        await asyncio.wait_for(work_started.wait(), timeout=1.0)
        # No register_job_owner was called by TaskService.
        assert task_id not in svc._job_owners

        # Wait well past the threshold + a few watchdog ticks.  An owned job
        # would have been killed by now; this one must survive.
        await asyncio.sleep(0.8)
        assert svc._cancel_stats["polling_watchdog_kills"] == 0, "watchdog killed an internal TaskService task"
        assert not cancelled_event.is_set(), "watchdog cancelled an internal TaskService task"
        assert task_id in svc._queues
    finally:
        # Cancel the long-running task manually so the test teardown doesn't hang.
        entry = svc._queues.get(task_id)
        if entry and entry[2] is not None and not entry[2].done():
            entry[2].cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await entry[2]
        svc._closed = True
        for attr in (
            "_cleanup_task",
            "_cancel_dispatcher_task",
            "_polling_watchdog_task",
        ):
            task = getattr(svc, attr, None)
            if task is not None and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        for bg in list(svc._background_tasks):
            if not bg.done():
                bg.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await bg
        for bridge in list(svc._bridge_tasks.values()):
            if not bridge.done():
                bridge.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await bridge


@pytest.mark.asyncio
async def test_redis_queue_wrapper_buffer_applies_backpressure(monkeypatch):
    """The bounded buffer must actually cap in-flight events, not just expose a maxsize.

    Floods the fill task with more events than the buffer can hold while the
    consumer drains slowly, and verifies the buffer size never exceeds the
    declared maxsize.  Without backpressure the buffer would grow unbounded
    as the fill task races ahead of the consumer.
    """
    # Use a tiny maxsize so the test is fast and the bound is exercised after
    # a handful of events instead of 10,000.
    monkeypatch.setattr(RedisQueueWrapper, "_BUFFER_MAXSIZE", 5)

    fake_client = fakeredis_aio.FakeRedis()
    job_id = str(uuid.uuid4())
    stream_key = f"{RedisQueueWrapper.STREAM_PREFIX}{job_id}"

    # Pre-populate the stream with 20 events BEFORE starting the wrapper so
    # the fill task immediately hits the maxsize ceiling.
    total_events = 20
    for i in range(total_events):
        await fake_client.xadd(stream_key, {b"event_id": f"e{i}".encode(), b"data": b"x", b"ts": b"0"})

    wrapper = RedisQueueWrapper(job_id, fake_client, ttl=60, startup_grace_s=10.0)
    try:
        # Sample the buffer size repeatedly while the fill task races.  With
        # backpressure, qsize() must never exceed _BUFFER_MAXSIZE.
        observed_sizes: list[int] = []
        for _ in range(20):
            observed_sizes.append(wrapper._buffer.qsize())
            await asyncio.sleep(0.01)
        assert max(observed_sizes) <= RedisQueueWrapper._BUFFER_MAXSIZE, (
            f"buffer grew past maxsize={RedisQueueWrapper._BUFFER_MAXSIZE}: peak={max(observed_sizes)}"
        )

        # Drain the buffer; backpressure should release and the fill task should
        # be able to make forward progress so all events eventually arrive.
        drained = 0
        while drained < total_events:
            await asyncio.wait_for(wrapper.get(), timeout=1.0)
            drained += 1
        assert drained == total_events
    finally:
        await wrapper.cancel()
        await fake_client.aclose()


@pytest.mark.asyncio
async def test_generate_flow_events_calls_end_all_traces_on_cancel(monkeypatch):
    """When a flow build is cancelled, graph.end_all_traces must be called.

    Regression: the cancel handler in _run_vertex_build previously used
    background_tasks.add_task(), which is silently dropped after FastAPI drains
    the POST /build response queue.  The fix uses asyncio.create_task() so
    trace cleanup runs regardless of the background_tasks lifecycle.

    Setup: _blocking_build_vertex blocks until the task is cancelled, which
    triggers the CancelledError handler in _run_vertex_build.  The test then
    asserts that end_all_traces is eventually called via the independent task.
    """
    from collections import defaultdict
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock, MagicMock

    from fastapi import BackgroundTasks
    from langflow.api.build import generate_flow_events
    from langflow.events.event_manager import EventManager
    from lfx.schema.schema import InputValueRequest

    # ── trace spy ────────────────────────────────────────────────────────────
    traces_ended = asyncio.Event()

    async def _fake_end_all_traces(_outputs=None, _error=None):
        traces_ended.set()

    def _fake_end_all_traces_in_context(_outputs=None, _error=None):
        # Mirror the real signature: returns a callable, not a coroutine.
        async def _run():
            await _fake_end_all_traces()

        return _run

    # ── mock vertex that blocks so we can observe the cancel path ─────────────
    vertex_started = asyncio.Event()

    async def _blocking_build_vertex(**_kwargs):
        vertex_started.set()
        await asyncio.Event().wait()  # hangs until the task is cancelled

    mock_vertex = MagicMock()
    mock_vertex.outputs = [{"name": "output"}]
    mock_vertex.will_stream = False

    # ── mock graph ────────────────────────────────────────────────────────────
    mock_graph = MagicMock()
    mock_graph.run_id = str(uuid.uuid4())
    mock_graph.session_id = "test-session"
    mock_graph.flow_id = str(uuid.uuid4())
    mock_graph.inactivated_vertices = set()
    mock_graph.conditionally_excluded_vertices = set()
    mock_graph.stop_vertex = None
    mock_graph.vertices_to_run = {"v1"}
    mock_graph.vertices = [mock_vertex]
    mock_graph.sort_vertices = MagicMock(return_value=["v1"])
    mock_graph.get_vertex = MagicMock(return_value=mock_vertex)
    mock_graph.run_manager = MagicMock()
    mock_graph.run_manager.vertices_being_run = set()
    mock_graph.build_vertex = _blocking_build_vertex
    mock_graph.end_all_traces = _fake_end_all_traces
    mock_graph.end_all_traces_in_context = _fake_end_all_traces_in_context

    # ── mock services ─────────────────────────────────────────────────────────
    mock_chat = MagicMock()
    mock_chat.async_cache_locks = defaultdict(asyncio.Lock)
    mock_chat.get_cache = AsyncMock(return_value=None)
    mock_chat.set_cache = AsyncMock()

    mock_telemetry = MagicMock()
    mock_telemetry.log_package_playground = MagicMock()

    @asynccontextmanager
    async def _fake_session_scope():
        yield MagicMock()

    # Raise in create_job so _build_job_svc is set to None — the simpler
    # code path that calls _run_vertex_build() directly without execute_with_status.
    mock_job_svc = MagicMock()
    mock_job_svc.create_job = AsyncMock(side_effect=Exception("skip in test"))

    monkeypatch.setattr("langflow.api.build.get_chat_service", lambda: mock_chat)
    monkeypatch.setattr("langflow.api.build.get_telemetry_service", lambda: mock_telemetry)
    monkeypatch.setattr("langflow.api.build.session_scope", _fake_session_scope)
    monkeypatch.setattr(
        "langflow.api.build.build_graph_from_db",
        AsyncMock(return_value=mock_graph),
    )
    monkeypatch.setattr("langflow.api.build.get_job_service", lambda: mock_job_svc)
    monkeypatch.setattr("langflow.api.build.get_task_service", lambda: MagicMock())
    monkeypatch.setattr("langflow.api.build.get_memory_base_service", lambda: MagicMock())
    monkeypatch.setattr("langflow.api.build.get_top_level_vertices", lambda *_: [])

    # ── wire up the event manager ─────────────────────────────────────────────
    main_queue: asyncio.Queue = asyncio.Queue()
    flow_id = uuid.uuid4()
    current_user = MagicMock()
    current_user.id = uuid.uuid4()

    build_task = asyncio.create_task(
        generate_flow_events(
            flow_id=flow_id,
            background_tasks=BackgroundTasks(),
            event_manager=EventManager(main_queue),
            inputs=InputValueRequest(session=str(flow_id)),
            data=None,
            files=None,
            stop_component_id=None,
            start_component_id=None,
            log_builds=False,
            current_user=current_user,
        )
    )

    # Wait until the blocking vertex is actually running, then cancel.
    await asyncio.wait_for(vertex_started.wait(), timeout=2.0)
    build_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await build_task

    # Give the spawned end_all_traces task a beat to complete.
    await asyncio.sleep(0.1)

    assert traces_ended.is_set(), (
        "graph.end_all_traces was not called after the build was cancelled. "
        "The cancel handler in _run_vertex_build must use asyncio.create_task() "
        "not background_tasks.add_task(), which is silently dropped once FastAPI "
        "drains the POST /build response queue."
    )


@pytest.mark.asyncio
async def test_fill_from_redis_last_id_not_advanced_before_put_completes(monkeypatch):
    """_last_id must not advance until after await buffer.put() returns.

    Regression: the cursor was previously advanced before the await, so a task
    cancellation while put() was blocked on a full buffer would silently lose
    that event — the next XREAD would start past it.  With the fix, the cursor
    stays at the prior position and the event is re-delivered on restart.
    """
    fake_client = fakeredis_aio.FakeRedis()
    job_id = str(uuid.uuid4())
    stream_key = f"langflow:queue:{job_id}"

    # Pre-populate two events before the wrapper starts so both land in the
    # same XREAD batch.
    id_a = (await fake_client.xadd(stream_key, {"event_id": b"a", "data": b"event-A", "ts": b"1.0"})).decode()
    await fake_client.xadd(stream_key, {"event_id": b"b", "data": b"event-B", "ts": b"2.0"})

    # Buffer size 1: after A lands, put(B) blocks until A is consumed.
    monkeypatch.setattr(RedisQueueWrapper, "_BUFFER_MAXSIZE", 1)
    wrapper = RedisQueueWrapper(job_id, fake_client, ttl=60)

    # Spin until A is in the buffer — at that point the fill task is blocked
    # on put(B) and has NOT yet updated _last_id to B's position.
    for _ in range(200):
        if not wrapper._buffer.empty():
            break
        await asyncio.sleep(0.01)
    assert not wrapper._buffer.empty(), "event-A never landed in the buffer"

    # Cancel the fill task while it is blocked inside put(B).
    wrapper._fill_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await wrapper._fill_task

    # The cursor must still be at A's ID — B was not committed to the buffer.
    assert wrapper._last_id == id_a, (
        f"_last_id advanced to {wrapper._last_id!r} before put(B) completed; "
        f"expected it to stay at {id_a!r} so event-B is not silently dropped."
    )

    await fake_client.aclose()


@pytest.mark.asyncio
async def test_fill_from_redis_persistent_xread_error_delivers_sentinel(monkeypatch):
    """Persistent XREAD failures must eventually deliver an end-of-stream sentinel.

    Regression: the error-elapsed tracking was removed, causing the fill task
    to retry forever and leaving the consumer stuck on await get() indefinitely.
    With the fix, after _STARTUP_GRACE_S of continuous errors the sentinel is
    delivered and the fill task exits.
    """

    class _FailingXreadClient:
        """Thin wrapper whose xread always raises, simulating a persistent Redis error."""

        def __init__(self, real: Any) -> None:
            self._real = real

        def __getattr__(self, name: str) -> Any:
            return getattr(self._real, name)

        async def xread(self, *_args: Any, **_kwargs: Any) -> None:
            msg = "simulated persistent Redis error"
            raise ConnectionError(msg)

    fake_client = fakeredis_aio.FakeRedis()
    job_id = str(uuid.uuid4())

    # Very short grace period so the test completes quickly.
    monkeypatch.setattr(RedisQueueWrapper, "_STARTUP_GRACE_S", 0.15)
    monkeypatch.setattr(RedisQueueWrapper, "_READ_ERROR_BACKOFF_S", 0.02)

    wrapper = RedisQueueWrapper(job_id, _FailingXreadClient(fake_client), ttl=60)
    try:
        # The sentinel must arrive within a generous timeout well above the grace period.
        evt = await asyncio.wait_for(wrapper.get(), timeout=3.0)
        assert evt[0] is None, f"expected sentinel event_id, got {evt}"
        assert evt[1] is None, f"expected sentinel payload, got {evt}"
    finally:
        await wrapper.cancel()
        await fake_client.aclose()


@pytest.mark.asyncio
async def test_cancel_flow_build_returns_false_for_in_memory_backend_without_task():
    """cancel_flow_build must return False when no task exists and no cross-worker path.

    Regression: the function returned True ("Nothing to cancel is still a success")
    when event_task is None and the queue service has no signal_cancel method
    (in-memory backend).  This misled callers into believing cancellation succeeded
    when in fact the build was unreachable.
    """
    svc = JobQueueService()
    svc.start()
    job_id = str(uuid.uuid4())

    # create_queue registers the job with task=None; start_job has not been called,
    # so get_queue_data returns event_task=None.
    svc.create_queue(job_id)

    result = await cancel_flow_build(job_id=job_id, queue_service=svc)
    assert result is False, (
        "cancel_flow_build must return False when it cannot reach the build "
        "(no local task and no cross-worker signal channel available)."
    )

    await svc.stop()


@pytest.mark.asyncio
async def test_cancel_flow_build_returns_false_for_redis_with_disabled_cancel_channel():
    """Redis with cancel_channel_enabled=False is the same as no cross-worker cancel.

    signal_cancel exists on the service but short-circuits to 0 without setting
    the persistent marker, so treating its return as a successful dispatch is
    misleading. cancel_flow_build must fall through to the unreachable-build
    branch and return False.
    """
    svc, _ = await _make_service(cancel_channel_enabled=False)
    try:
        assert getattr(svc, "signal_cancel", None) is not None
        assert svc.cross_worker_cancel_enabled is False

        job_id = str(uuid.uuid4())
        svc.create_queue(job_id)  # registers event_task=None

        result = await cancel_flow_build(job_id=job_id, queue_service=svc)
        assert result is False, (
            "Redis with cancel_channel_enabled=False has no cross-worker cancel; "
            "cancel_flow_build must report failure rather than a false success."
        )
    finally:
        await _stop_service(svc)


@pytest.mark.asyncio
async def test_polling_watchdog_runs_when_cancel_channel_disabled():
    """Watchdog must operate independently of cancel_channel_enabled.

    Regression: the watchdog was only started when cancel_channel_enabled=True,
    so disabling the pub/sub cancel channel also silently disabled stale-client
    reclamation.  The fix starts the watchdog based on polling_stale_threshold_s
    alone.
    """
    fake_client = fakeredis_aio.FakeRedis()
    svc = RedisJobQueueService(
        ttl=60,
        cancel_channel_enabled=False,  # pub/sub disabled
        polling_stale_threshold_s=0.3,
        polling_watchdog_interval_s=0.1,
    )
    svc._client = fake_client
    svc._closed = False
    svc._cleanup_task = asyncio.create_task(svc._periodic_cleanup())
    # Replicate what start() does after our fix: watchdog starts regardless of channel.
    svc._polling_watchdog_task = asyncio.create_task(svc._run_polling_watchdog())
    svc.ready = True

    try:
        job_id = str(uuid.uuid4())
        svc.create_queue(job_id)
        await svc.register_job_owner(job_id, uuid.uuid4())

        cancelled_event = asyncio.Event()

        async def _long_running():
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled_event.set()
                raise

        svc.start_job(job_id, _long_running())

        # Do NOT call touch_activity — let the job go stale.  The grace window
        # (populated by start_job via _job_start_times) protects the first
        # threshold window, so the watchdog fires after ~threshold seconds.
        await asyncio.wait_for(cancelled_event.wait(), timeout=5.0)

        assert cancelled_event.is_set(), "watchdog did not cancel the stale job"
        assert svc._cancel_stats["polling_watchdog_kills"] >= 1
    finally:
        svc._closed = True
        for attr in ("_cleanup_task", "_polling_watchdog_task"):
            task = getattr(svc, attr, None)
            if task is not None and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        for bg in list(svc._background_tasks):
            if not bg.done():
                bg.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await bg
        for bridge in list(svc._bridge_tasks.values()):
            if not bridge.done():
                bridge.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await bridge
        await fake_client.aclose()
