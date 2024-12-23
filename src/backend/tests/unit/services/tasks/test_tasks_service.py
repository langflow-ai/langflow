import asyncio
import datetime

import pytest
from apscheduler.events import JobExecutionEvent
from langflow.services.database.models.job.model import Job, JobStatus
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.task.service import TaskService, TaskStatus
from sqlmodel import select


@pytest.fixture
async def task_service():
    """Create a task service for testing."""
    service = TaskService(get_settings_service())
    await service.setup()
    yield service
    await service.teardown()


# Create a mock task function that has all the kwargs
def mock_task_func(**kwargs):
    return kwargs


@pytest.fixture
async def sample_job(task_service: TaskService, active_user, simple_api_test):
    """Create a sample job for testing."""
    task_id = await task_service.create_task(
        task_func=mock_task_func,
        run_at=None,
        name="Test Task",
        kwargs={
            "flow": simple_api_test,
            "input_request": {
                "input_value": "test input",
                "input_type": "text",
                "output_type": "text",
                "tweaks": {},
            },
            "stream": False,
            "api_key_user": active_user,
        },
    )
    async with session_scope() as session:
        stmt = select(Job).where(Job.id == task_id)
        job = (await session.exec(stmt)).first()
        assert job is not None, "Job was not created"
    return job


async def test_handle_job_executed(task_service: TaskService, sample_job: Job):
    """Test handling of successful job execution."""
    # Create a JobExecutionEvent
    event = JobExecutionEvent(
        code=0,  # Success code
        job_id=sample_job.id,
        jobstore="default",
        retval={"output": "Test result"},
        scheduled_run_time=sample_job.next_run_time,
    )

    # Handle the event
    await task_service._handle_job_executed(event)

    # Verify the job status was updated
    async with session_scope() as session:
        stmt = select(Job).where(Job.id == sample_job.id)
        updated_job = (await session.exec(stmt)).first()
        assert updated_job is not None, "Job not found"
        assert updated_job.status == JobStatus.COMPLETED, "Job status not updated to COMPLETED"
        assert updated_job.result == {"output": "Test result"}, "Job result not saved correctly"


async def test_handle_job_error(task_service: TaskService, sample_job: Job):
    """Test handling of job execution error."""
    # Create a JobEvent with an error
    test_error = ValueError("Test error message")
    event = JobExecutionEvent(
        code=1,  # Error code
        job_id=sample_job.id,
        jobstore="default",
        exception=test_error,
        scheduled_run_time=sample_job.next_run_time,
    )

    # Handle the error event
    await task_service._handle_job_error(event)

    # Verify the job status and error were updated
    async with session_scope() as session:
        stmt = select(Job).where(Job.id == sample_job.id)
        updated_job = (await session.exec(stmt)).first()
        assert updated_job is not None, "Job not found"
        assert updated_job.status == JobStatus.FAILED, "Job status not updated to FAILED"
        assert updated_job.error == str(test_error), "Job error not saved correctly"


async def test_job_lifecycle(task_service: TaskService, sample_job: Job):
    """Test the complete lifecycle of a job from creation to completion."""
    # Verify initial state
    async with session_scope() as session:
        stmt = select(Job).where(Job.id == sample_job.id)
        job = (await session.exec(stmt)).first()
        assert job is not None, "Job not found"
        assert job.status == JobStatus.PENDING, "Initial job status should be PENDING"
        assert job.result is None, "Initial job result should be None"
        assert job.error is None, "Initial job error should be None"

    # Simulate successful execution
    success_event = JobExecutionEvent(
        code=0,
        job_id=sample_job.id,
        jobstore="default",
        retval={"output": "Success result"},
        scheduled_run_time=sample_job.next_run_time,
    )
    await task_service._handle_job_executed(success_event)

    # Verify successful completion
    async with session_scope() as session:
        stmt = select(Job).where(Job.id == sample_job.id)
        completed_job = (await session.exec(stmt)).first()
        assert completed_job is not None, "Job not found"
        assert completed_job.status == JobStatus.COMPLETED, "Job should be marked as completed"
        assert completed_job.result == {"output": "Success result"}, "Job result should be saved"
        assert completed_job.error is None, "Completed job should not have an error"


async def test_concurrent_job_updates(task_service: TaskService, sample_job: Job):
    """Test handling concurrent updates to the same job."""
    # Create multiple events for the same job
    success_event = JobExecutionEvent(
        code=0,
        job_id=sample_job.id,
        scheduled_run_time=sample_job.next_run_time,
        jobstore="default",
        retval="Success result",
    )
    error_event = JobExecutionEvent(
        code=1,
        job_id=sample_job.id,
        jobstore="default",
        exception=ValueError("Test error"),
        scheduled_run_time=sample_job.next_run_time,
    )

    # Handle events concurrently
    await asyncio.gather(
        task_service._handle_job_executed(success_event),
        task_service._handle_job_error(error_event),
    )

    # Verify final state (one of the updates should succeed, the other should fail gracefully)
    async with session_scope() as session:
        stmt = select(Job).where(Job.id == sample_job.id)
        final_job = (await session.exec(stmt)).first()
        assert final_job is not None, "Job not found"
        assert final_job.status in [TaskStatus.COMPLETED, TaskStatus.FAILED], "Job should be either completed or failed"


@pytest.mark.usefixtures("client")
async def test_invalid_job_id(task_service: TaskService):
    """Test handling events for non-existent jobs."""
    # Create events with invalid job ID
    invalid_success_event = JobExecutionEvent(
        code=0,
        job_id="nonexistent_id",
        jobstore="default",
        retval="Success result",
        scheduled_run_time=datetime.datetime.now(datetime.timezone.utc),
    )
    invalid_error_event = JobExecutionEvent(
        code=1,
        job_id="nonexistent_id",
        jobstore="default",
        exception=ValueError("Test error"),
        scheduled_run_time=datetime.datetime.now(datetime.timezone.utc),
    )

    # Both handlers should handle non-existent jobs gracefully
    await task_service._handle_job_executed(invalid_success_event)
    await task_service._handle_job_error(invalid_error_event)
