import uuid
from datetime import datetime, timezone

from langflow.services.database.models.job.model import Job, JobRead, JobStatus


def test_job_status_enum():
    """Test JobStatus enum values."""
    assert JobStatus.PENDING == "PENDING"
    assert JobStatus.RUNNING == "RUNNING"
    assert JobStatus.COMPLETED == "COMPLETED"
    assert JobStatus.FAILED == "FAILED"
    assert JobStatus.CANCELLED == "CANCELLED"


def test_create_job():
    """Test creating a job with required fields."""
    job_id = "test-job-1"
    flow_id = uuid.uuid4()
    user_id = uuid.uuid4()
    name = "Test Job"

    job = Job(
        id=job_id,
        flow_id=flow_id,
        user_id=user_id,
        name=name,
    )

    assert job.id == job_id
    assert job.flow_id == flow_id
    assert job.user_id == user_id
    assert job.name == name
    assert job.status == JobStatus.PENDING
    assert job.is_active is True
    assert job.result is None
    assert job.error is None
    assert job.job_state is None
    assert job.next_run_time is None


def test_create_job_with_all_fields():
    """Test creating a job with all fields."""
    job_id = "test-job-2"
    flow_id = uuid.uuid4()
    user_id = uuid.uuid4()
    name = "Test Job Complete"
    next_run_time = datetime.now(timezone.utc)
    job_state = b"serialized_state"
    result = {"output": "test_result"}

    job = Job(
        id=job_id,
        flow_id=flow_id,
        user_id=user_id,
        name=name,
        next_run_time=next_run_time,
        job_state=job_state,
        status=JobStatus.RUNNING,
        result=result,
        error="No error",
        is_active=False,
    )

    assert job.id == job_id
    assert job.flow_id == flow_id
    assert job.user_id == user_id
    assert job.name == name
    assert job.next_run_time == next_run_time
    assert job.job_state == job_state
    assert job.status == JobStatus.RUNNING
    assert job.result == result
    assert job.error == "No error"
    assert job.is_active is False


def test_job_read_model():
    """Test JobRead model creation and field mapping."""
    job_id = "test-job-3"
    flow_id = uuid.uuid4()
    user_id = uuid.uuid4()
    name = "Test Job Read"
    created_at = datetime.now(timezone.utc)
    updated_at = datetime.now(timezone.utc)
    result = {"status": "success"}

    job_read = JobRead(
        id=job_id,
        flow_id=flow_id,
        user_id=user_id,
        name=name,
        status=JobStatus.COMPLETED,
        is_active=True,
        created_at=created_at,
        updated_at=updated_at,
        job_state=None,
        next_run_time=None,
        result=result,
    )

    assert job_read.id == job_id
    assert job_read.flow_id == flow_id
    assert job_read.user_id == user_id
    assert job_read.name == name
    assert job_read.status == JobStatus.COMPLETED
    assert job_read.is_active is True
    assert job_read.created_at == created_at
    assert job_read.updated_at == updated_at
    assert job_read.result == result


def test_job_status_validation():
    """Test job status field behavior."""
    # Test default status
    job = Job(
        id="test-job-4",
        flow_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Status Test Job",
    )
    assert job.status == JobStatus.PENDING

    # Test setting valid status
    job.status = JobStatus.RUNNING
    assert job.status == JobStatus.RUNNING

    # Test setting raw string value
    job.status = "COMPLETED"
    assert job.status == "COMPLETED"

    # Test that invalid status is accepted (no validation at model level)
    job.status = "INVALID_STATUS"
    assert job.status == "INVALID_STATUS"


def test_job_status_transitions():
    """Test typical job status transitions."""
    job = Job(
        id="test-job-8",
        flow_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Status Transition Test",
    )

    # Test initial state
    assert job.status == JobStatus.PENDING

    # Test running transition
    job.status = JobStatus.RUNNING
    assert job.status == JobStatus.RUNNING

    # Test completion transition
    job.status = JobStatus.COMPLETED
    assert job.status == JobStatus.COMPLETED

    # Test failure transition
    job = Job(
        id="test-job-9", flow_id=uuid.uuid4(), user_id=uuid.uuid4(), name="Failed Job Test", status=JobStatus.RUNNING
    )
    job.status = JobStatus.FAILED
    assert job.status == JobStatus.FAILED

    # Test cancellation
    job = Job(
        id="test-job-10",
        flow_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Cancelled Job Test",
        status=JobStatus.RUNNING,
    )
    job.status = JobStatus.CANCELLED
    assert job.status == JobStatus.CANCELLED


def test_job_timestamps():
    """Test that created_at and updated_at are properly set."""
    job = Job(
        id="test-job-5",
        flow_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Timestamp Test Job",
        # Explicitly set timestamps for testing
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    assert isinstance(job.created_at, datetime)
    assert isinstance(job.updated_at, datetime)
    assert job.created_at.tzinfo is not None  # Ensure timezone is set
    assert job.updated_at.tzinfo is not None  # Ensure timezone is set


def test_job_state_serialization():
    """Test job state serialization with bytes."""
    job_state = b"serialized_state_data"
    job = Job(id="test-job-6", flow_id=uuid.uuid4(), user_id=uuid.uuid4(), name="State Test Job", job_state=job_state)

    assert isinstance(job.job_state, bytes)
    assert job.job_state == job_state


def test_job_result_json():
    """Test job result JSON field."""
    result_data = {"output": "test output", "metrics": {"time": 1.23}, "nested": {"key": ["value1", "value2"]}}
    job = Job(id="test-job-7", flow_id=uuid.uuid4(), user_id=uuid.uuid4(), name="Result Test Job", result=result_data)

    assert job.result == result_data
    assert isinstance(job.result, dict)


def test_job_result_edge_cases():
    """Test edge cases for job result field."""
    # Test non-dict return value (service converts to dict)
    job = Job(
        id="test-job-11",
        flow_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="String Result Job",
        result={"output": "plain string result"},
    )
    assert job.result == {"output": "plain string result"}

    # Test complex nested result
    complex_result = {
        "output": {"text": "Generated text", "tokens": 150, "model": "gpt-3.5-turbo"},
        "metrics": {"time_taken": 2.5, "tokens_per_second": 60, "cost": 0.002},
        "metadata": {
            "version": "1.0",
            "timestamp": "2024-01-01T00:00:00Z",
            "settings": {"temperature": 0.7, "max_tokens": 200},
        },
    }
    job = Job(
        id="test-job-12", flow_id=uuid.uuid4(), user_id=uuid.uuid4(), name="Complex Result Job", result=complex_result
    )
    assert job.result == complex_result
    assert isinstance(job.result["output"], dict)
    assert isinstance(job.result["metrics"], dict)
    assert isinstance(job.result["metadata"], dict)

    # Test empty result
    job = Job(id="test-job-13", flow_id=uuid.uuid4(), user_id=uuid.uuid4(), name="Empty Result Job", result={})
    assert job.result == {}


def test_job_error_edge_cases():
    """Test edge cases for job error field."""
    # Test long error message
    long_error = "Error: " + "very long error message " * 100
    job = Job(
        id="test-job-14",
        flow_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Long Error Job",
        error=long_error,
        status=JobStatus.FAILED,
    )
    assert job.error == long_error
    assert job.status == JobStatus.FAILED

    # Test error with special characters
    special_error = "Error: Something went wrong!\n\tDetails: {'key': 'value'}\n\tStack trace: [...]"
    job = Job(
        id="test-job-15",
        flow_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Special Error Job",
        error=special_error,
        status=JobStatus.FAILED,
    )
    assert job.error == special_error
    assert job.status == JobStatus.FAILED

    # Test empty error
    job = Job(
        id="test-job-16",
        flow_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Empty Error Job",
        error="",
        status=JobStatus.FAILED,
    )
    assert job.error == ""
    assert job.status == JobStatus.FAILED


def test_job_state_edge_cases():
    """Test edge cases for job state field."""
    # Test large job state
    large_state = b"x" * 1000000  # 1MB of data
    job = Job(
        id="test-job-17", flow_id=uuid.uuid4(), user_id=uuid.uuid4(), name="Large State Job", job_state=large_state
    )
    assert job.job_state == large_state
    assert len(job.job_state) == 1000000

    # Test job state with special bytes
    special_state = bytes([0, 1, 2, 3, 255, 254, 253, 252])
    job = Job(
        id="test-job-18", flow_id=uuid.uuid4(), user_id=uuid.uuid4(), name="Special State Job", job_state=special_state
    )
    assert job.job_state == special_state
    assert len(job.job_state) == 8

    # Test empty job state
    job = Job(id="test-job-19", flow_id=uuid.uuid4(), user_id=uuid.uuid4(), name="Empty State Job", job_state=b"")
    assert job.job_state == b""
    assert len(job.job_state) == 0


def test_job_state_result_error_combinations():
    """Test various combinations of job state, result, and error fields."""
    # Test job with all fields populated
    job = Job(
        id="test-job-20",
        flow_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Complete Job",
        job_state=b"state data",
        result={"output": "success"},
        error=None,
        status=JobStatus.COMPLETED,
    )
    assert job.job_state == b"state data"
    assert job.result == {"output": "success"}
    assert job.error is None
    assert job.status == JobStatus.COMPLETED

    # Test failed job with error but no result
    job = Job(
        id="test-job-21",
        flow_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Failed Job",
        job_state=b"state data",
        result=None,
        error="Task failed successfully",
        status=JobStatus.FAILED,
    )
    assert job.job_state == b"state data"
    assert job.result is None
    assert job.error == "Task failed successfully"
    assert job.status == JobStatus.FAILED

    # Test cancelled job
    job = Job(
        id="test-job-22",
        flow_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Cancelled Job",
        job_state=None,
        result=None,
        error=None,
        status=JobStatus.CANCELLED,
    )
    assert job.job_state is None
    assert job.result is None
    assert job.error is None
    assert job.status == JobStatus.CANCELLED
