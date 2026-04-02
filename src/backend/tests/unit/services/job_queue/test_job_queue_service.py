"""Tests for JobQueueService."""

import asyncio
from uuid import uuid4

import pytest

from langflow.services.job_queue.service import JobQueueNotFoundError, JobQueueService

pytestmark = pytest.mark.asyncio


class TestJobQueueNotFoundError:
    """Tests for JobQueueNotFoundError exception."""

    def test_error_message(self):
        error = JobQueueNotFoundError("job123")
        assert error.job_id == "job123"
        assert "job123" in str(error)

    def test_is_exception(self):
        assert issubclass(JobQueueNotFoundError, Exception)


class TestJobQueueServiceInit:
    """Tests for JobQueueService initialization."""

    def test_initial_state(self):
        service = JobQueueService()
        assert service.name == "job_queue_service"
        assert service._closed is False
        assert service.ready is False
        assert service._cleanup_task is None
        assert len(service._queues) == 0
        assert service.CLEANUP_GRACE_PERIOD == 300

    def test_is_started_false_initially(self):
        service = JobQueueService()
        assert service.is_started() is False


class TestJobQueueServiceCreateQueue:
    """Tests for create_queue."""

    async def test_create_queue(self):
        service = JobQueueService()
        service._closed = False
        queue, event_manager = service.create_queue("job1")
        assert isinstance(queue, asyncio.Queue)
        assert event_manager is not None
        assert "job1" in service._queues

    async def test_create_duplicate_queue_raises(self):
        service = JobQueueService()
        service.create_queue("job1")
        with pytest.raises(ValueError, match="already exists"):
            service.create_queue("job1")

    async def test_create_queue_when_closed_raises(self):
        service = JobQueueService()
        service._closed = True
        with pytest.raises(RuntimeError, match="closed"):
            service.create_queue("job1")


class TestJobQueueServiceStartJob:
    """Tests for start_job."""

    async def test_start_job(self):
        service = JobQueueService()

        async def dummy_task():
            await asyncio.sleep(100)

        service.create_queue("job1")
        service.start_job("job1", dummy_task())
        _, _, task, _ = service._queues["job1"]
        assert task is not None
        assert not task.done()
        # Clean up
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_start_job_no_queue_raises(self):
        service = JobQueueService()
        with pytest.raises(ValueError, match="No queue found"):
            service.start_job("nonexistent", asyncio.sleep(1))

    async def test_start_job_when_closed_raises(self):
        service = JobQueueService()
        service.create_queue("job1")
        service._closed = True
        with pytest.raises(RuntimeError, match="closed"):
            service.start_job("job1", asyncio.sleep(1))

    async def test_start_job_replaces_existing_task(self):
        service = JobQueueService()
        service.create_queue("job1")

        async def task1():
            await asyncio.sleep(100)

        async def task2():
            await asyncio.sleep(100)

        service.start_job("job1", task1())
        _, _, old_task, _ = service._queues["job1"]

        service.start_job("job1", task2())
        _, _, new_task, _ = service._queues["job1"]

        assert old_task is not new_task
        # Give the event loop a chance to process the cancellation
        await asyncio.sleep(0)
        assert old_task.cancelled() or old_task.done()
        # Clean up
        new_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await new_task


class TestJobQueueServiceGetQueueData:
    """Tests for get_queue_data."""

    async def test_get_queue_data(self):
        service = JobQueueService()
        service.create_queue("job1")
        queue, event_manager, task, cleanup_time = service.get_queue_data("job1")
        assert isinstance(queue, asyncio.Queue)
        assert event_manager is not None
        assert task is None
        assert cleanup_time is None

    async def test_get_queue_data_not_found_raises(self):
        service = JobQueueService()
        with pytest.raises(JobQueueNotFoundError):
            service.get_queue_data("nonexistent")

    async def test_get_queue_data_when_closed_raises(self):
        service = JobQueueService()
        service.create_queue("job1")
        service._closed = True
        with pytest.raises(RuntimeError, match="closed"):
            service.get_queue_data("job1")


class TestJobQueueServiceJobOwnership:
    """Tests for job ownership tracking."""

    def test_register_and_get_owner(self):
        service = JobQueueService()
        user_id = uuid4()
        service.register_job_owner("job1", user_id)
        assert service.get_job_owner("job1") == user_id

    def test_get_owner_nonexistent(self):
        service = JobQueueService()
        assert service.get_job_owner("nonexistent") is None

    def test_register_multiple_owners(self):
        service = JobQueueService()
        user1 = uuid4()
        user2 = uuid4()
        service.register_job_owner("job1", user1)
        service.register_job_owner("job2", user2)
        assert service.get_job_owner("job1") == user1
        assert service.get_job_owner("job2") == user2


class TestJobQueueServiceCleanupJob:
    """Tests for cleanup_job."""

    async def test_cleanup_nonexistent_job(self):
        service = JobQueueService()
        # Should not raise
        await service.cleanup_job("nonexistent")

    async def test_cleanup_removes_job(self):
        service = JobQueueService()
        service.create_queue("job1")
        await service.cleanup_job("job1")
        assert "job1" not in service._queues

    async def test_cleanup_clears_queue(self):
        service = JobQueueService()
        queue, _ = service.create_queue("job1")
        await queue.put("item1")
        await queue.put("item2")
        await service.cleanup_job("job1")
        assert "job1" not in service._queues

    async def test_cleanup_removes_owner(self):
        service = JobQueueService()
        user_id = uuid4()
        service.create_queue("job1")
        service.register_job_owner("job1", user_id)
        await service.cleanup_job("job1")
        assert service.get_job_owner("job1") is None

    async def test_cleanup_cancels_running_task(self):
        service = JobQueueService()
        service.create_queue("job1")

        async def long_task():
            await asyncio.sleep(100)

        service.start_job("job1", long_task())
        _, _, task, _ = service._queues["job1"]
        assert not task.done()

        with pytest.raises(asyncio.CancelledError):
            await service.cleanup_job("job1")


class TestJobQueueServiceLifecycle:
    """Tests for start/stop lifecycle."""

    async def test_start(self):
        service = JobQueueService()
        service.start()
        assert service.is_started()
        assert service._closed is False
        # Clean up
        await service.stop()

    async def test_stop(self):
        service = JobQueueService()
        service.start()
        await service.stop()
        assert service._closed is True

    async def test_stop_cleans_up_all_queues(self):
        service = JobQueueService()
        service.start()
        service.create_queue("job1")
        service.create_queue("job2")
        await service.stop()
        assert len(service._queues) == 0

    async def test_teardown_calls_stop(self):
        service = JobQueueService()
        service.start()
        await service.teardown()
        assert service._closed is True

    async def test_set_ready_starts_service(self):
        service = JobQueueService()
        assert not service.is_started()
        service.set_ready()
        assert service.is_started()
        await service.stop()


class TestJobQueueServiceEventManager:
    """Tests for event manager creation."""

    def test_default_event_manager_events(self):
        service = JobQueueService()
        queue = asyncio.Queue()
        manager = service._create_default_event_manager(queue)
        # Should have registered the predefined events
        assert manager is not None

    def test_create_queue_returns_event_manager(self):
        service = JobQueueService()
        _, event_manager = service.create_queue("job1")
        assert event_manager is not None


class TestJobQueueServiceCleanupOldQueues:
    """Tests for _cleanup_old_queues logic."""

    async def test_marks_orphaned_queues_for_cleanup(self):
        service = JobQueueService()
        service.create_queue("job1")
        # Directly call cleanup logic
        await service._cleanup_old_queues()
        # Should be marked (cleanup_time set)
        _, _, _, cleanup_time = service._queues["job1"]
        assert cleanup_time is not None

    async def test_cleanup_after_grace_period(self):
        service = JobQueueService()
        service.CLEANUP_GRACE_PERIOD = 0  # No grace period
        service.create_queue("job1")
        # First call marks it
        await service._cleanup_old_queues()
        # Second call should clean it up (grace period is 0)
        await service._cleanup_old_queues()
        assert "job1" not in service._queues

    async def test_does_not_cleanup_active_task(self):
        service = JobQueueService()
        service.create_queue("job1")

        async def long_task():
            await asyncio.sleep(100)

        service.start_job("job1", long_task())
        await service._cleanup_old_queues()
        # Active task should NOT be marked for cleanup
        _, _, _, cleanup_time = service._queues["job1"]
        assert cleanup_time is None
        # Clean up
        _, _, task, _ = service._queues["job1"]
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_marks_completed_task_for_cleanup(self):
        service = JobQueueService()
        service.create_queue("job1")

        async def quick_task():
            pass

        service.start_job("job1", quick_task())
        # Wait for task to complete
        _, _, task, _ = service._queues["job1"]
        await task
        # Now cleanup should mark it
        await service._cleanup_old_queues()
        _, _, _, cleanup_time = service._queues["job1"]
        assert cleanup_time is not None
