import asyncio

import pytest
from langflow.scheduling.async_rlock import AsyncRLock


@pytest.mark.asyncio
async def test_basic_lock_acquire_release():
    """Test basic lock acquisition and release."""
    lock = AsyncRLock()
    assert not lock.locked
    await lock.acquire()
    assert lock.locked
    assert lock.get_owner() == asyncio.current_task()
    lock.release()
    assert not lock.locked
    assert lock.get_owner() is None


@pytest.mark.asyncio
async def test_reentrant_behavior():
    """Test that the lock is reentrant (can be acquired multiple times by same task)."""
    lock = AsyncRLock()

    # First acquisition
    await lock.acquire()
    assert lock.locked

    # Second acquisition (should not block)
    await lock.acquire()
    assert lock.locked

    # Both releases should work
    lock.release()
    assert lock.locked  # Still locked after first release
    lock.release()
    assert not lock.locked  # Now unlocked


@pytest.mark.asyncio
async def test_context_manager():
    """Test async context manager interface."""
    lock = AsyncRLock()

    async with lock:
        assert lock.locked
        assert lock.get_owner() == asyncio.current_task()

        # Nested context should work
        async with lock:
            assert lock.locked
            assert lock.get_owner() == asyncio.current_task()

        assert lock.locked  # Still locked after inner context

    assert not lock.locked  # Unlocked after outer context


@pytest.mark.asyncio
async def test_error_handling():
    """Test error conditions and error handling."""
    lock = AsyncRLock()

    # Test releasing without acquiring
    with pytest.raises(RuntimeError, match="Cannot release lock owned by None"):
        lock.release()

    # Test releasing from wrong task
    await lock.acquire()

    async def other_task():
        with pytest.raises(RuntimeError, match="Cannot release lock owned by"):
            lock.release()

    await asyncio.create_task(other_task())
    lock.release()


@pytest.mark.asyncio
async def test_multiple_tasks():
    """Test lock behavior with multiple tasks."""
    lock = AsyncRLock()
    results = []

    async def worker(id: int):  # noqa: A002
        async with lock:
            results.append(f"Task {id} started")
            await asyncio.sleep(0.1)  # Simulate work
            results.append(f"Task {id} finished")

    # Create and run multiple tasks
    tasks = [asyncio.create_task(worker(i)) for i in range(3)]
    await asyncio.gather(*tasks)

    # Check that tasks executed sequentially
    assert len(results) == 6
    for i in range(3):
        assert results[i * 2].endswith("started")
        assert results[i * 2 + 1].endswith("finished")
        assert results[i * 2].split()[1] == results[i * 2 + 1].split()[1]


@pytest.mark.asyncio
async def test_waiters_tracking():
    """Test tracking of waiting tasks."""
    lock = AsyncRLock(debug=True)

    async def waiter():
        await asyncio.sleep(0.1)  # Ensure main task acquires first
        await lock.acquire()
        await asyncio.sleep(0.1)
        lock.release()

    # Main task acquires the lock
    await lock.acquire()
    assert lock.get_waiters_count() == 0

    # Start a waiting task
    task = asyncio.create_task(waiter())
    await asyncio.sleep(0.2)  # Give time for waiter to start waiting
    assert lock.get_waiters_count() == 1

    # Release and wait for waiter to finish
    lock.release()
    await task
    assert lock.get_waiters_count() == 0


@pytest.mark.asyncio
async def test_debug_mode():
    """Test debug mode functionality."""
    lock = AsyncRLock(debug=True)

    async with lock:
        assert lock.locked
        assert lock._debug
        # Debug logs would be visible in output

        async with lock:
            pass  # Nested acquisition should be logged

    assert not lock.locked


@pytest.mark.asyncio
async def test_exception_handling():
    """Test lock behavior when exceptions occur."""
    lock = AsyncRLock()

    try:
        async with lock:
            assert lock.locked
            msg = "Test exception"
            raise ValueError(msg)
    except ValueError:
        assert not lock.locked  # Lock should be released even if exception occurs

    assert not lock.locked
    assert lock.get_owner() is None


@pytest.mark.asyncio
async def test_over_release():
    """Test handling of over-releasing the lock."""
    lock = AsyncRLock()

    await lock.acquire()
    lock.release()

    # Attempting to release more times than acquired should raise an error
    with pytest.raises(RuntimeError, match="Cannot release lock owned by None"):
        lock.release()


@pytest.mark.asyncio
async def test_repr():
    """Test the string representation of the lock."""
    lock = AsyncRLock()
    repr_str = repr(lock)

    assert "AsyncRLock" in repr_str
    assert "locked=False" in repr_str
    assert "count=0" in repr_str
    assert "waiters=0" in repr_str

    await lock.acquire()
    repr_str = repr(lock)
    assert "locked=True" in repr_str
    assert "count=1" in repr_str

    lock.release()
