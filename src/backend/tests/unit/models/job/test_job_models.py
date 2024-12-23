"""Tests for the Job model.

Note: These tests intentionally use pickle.loads to test serialization behavior.
The S301 warnings are suppressed because this is a test file and we're testing
the pickle functionality itself, not using it to deserialize untrusted data in
production code.
"""

import threading
import uuid
from contextlib import suppress
from datetime import datetime, timezone

import pytest
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


# Test classes need to be at module level for pickling
class CustomReduceObject:
    def __init__(self, value):
        self.value = value

    def __reduce__(self):
        return (self.__class__, (self.value,))


class BrokenReduceObject:
    def __reduce__(self):
        return (self.__class__, ())  # Missing required arguments


class ObjectWithLock:
    """Test class with a lock attribute."""

    def __init__(self):
        self.lock = threading.Lock()
        self.data = {"key": "value"}


def unpickleable_func():
    """Test function at module level."""


def test_job_state_serialization_edge_cases():
    """Test problematic serialization cases for job_state."""
    import pickle
    import types
    from io import StringIO

    # Test corrupted pickle data
    corrupted_pickle = b"invalid pickle data"
    job = Job(
        id="test-job-24",
        flow_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Corrupted Pickle Job",
        job_state=corrupted_pickle,
    )
    assert job.job_state == corrupted_pickle
    with pytest.raises((pickle.UnpicklingError, EOFError)):
        pickle.loads(job.job_state)  # noqa: S301

    # Test recursive data structure
    recursive_dict = {}
    recursive_dict["self"] = recursive_dict
    # Python's pickle can handle recursive structures!
    job_state = pickle.dumps(recursive_dict)
    job = Job(
        id="test-job-25", flow_id=uuid.uuid4(), user_id=uuid.uuid4(), name="Recursive Data Job", job_state=job_state
    )
    unpickled = pickle.loads(job.job_state)  # noqa: S301
    assert unpickled["self"] is unpickled  # Verify recursion is preserved

    # Test extremely nested data that might exceed pickle's recursion limit
    deep_list = []
    current = deep_list
    for _ in range(2000):  # Create an extremely deeply nested list
        current.append([])
        current = current[0]

    with pytest.raises((RecursionError, pickle.PicklingError)):
        pickle.dumps(deep_list, protocol=pickle.HIGHEST_PROTOCOL)

    # Test lambda function that can't be pickled
    # Note: Lambda functions raise AttributeError when trying to pickle
    with pytest.raises(AttributeError):
        pickle.dumps(lambda x: x)

    # Test file-like objects
    text_io = StringIO("test data")  # StringIO can be pickled
    job_state = pickle.dumps(text_io)
    job = Job(id="test-job-28", flow_id=uuid.uuid4(), user_id=uuid.uuid4(), name="Text IO Job", job_state=job_state)
    assert isinstance(pickle.loads(job.job_state), StringIO)  # noqa: S301

    # Test generator function that can't be pickled
    def generator_func():
        yield "test"

    gen = generator_func()
    with pytest.raises(TypeError):  # Python raises TypeError for generators
        pickle.dumps(gen)

    # Test module object that shouldn't be pickled
    with pytest.raises(TypeError):  # Python raises TypeError for modules
        pickle.dumps(types)


def test_job_state_with_custom_objects():
    """Test job state with custom objects that implement __reduce__."""
    import pickle

    # Test pickling custom object that implements __reduce__
    custom_obj = CustomReduceObject("test value")
    job_state = pickle.dumps(custom_obj)
    job = Job(
        id="test-job-31", flow_id=uuid.uuid4(), user_id=uuid.uuid4(), name="Custom Reduce Job", job_state=job_state
    )
    assert job.job_state == job_state
    unpickled_obj = pickle.loads(job.job_state)  # noqa: S301
    assert isinstance(unpickled_obj, CustomReduceObject)
    assert unpickled_obj.value == "test value"

    # Test object with broken __reduce__ implementation
    broken_obj = BrokenReduceObject()
    job_state = pickle.dumps(broken_obj)
    job = Job(
        id="test-job-32", flow_id=uuid.uuid4(), user_id=uuid.uuid4(), name="Broken Reduce Job", job_state=job_state
    )
    # The object will be pickled but will be empty when unpickled
    unpickled = pickle.loads(job.job_state)  # noqa: S301
    assert isinstance(unpickled, BrokenReduceObject)


def test_job_state_security_risks():
    """Test potential security risks with job state serialization."""
    import os
    import pickle
    import sys

    # Test attempting to pickle a dangerous command
    class DangerousPickle:
        def __reduce__(self):
            return (os.system, ('echo "DANGER"',))

    # Python's pickle will allow this dangerous payload!
    dangerous_obj = DangerousPickle()
    job_state = pickle.dumps(dangerous_obj)
    job = Job(
        id="test-job-33", flow_id=uuid.uuid4(), user_id=uuid.uuid4(), name="Security Risk Job", job_state=job_state
    )

    # This is why it's crucial to NEVER unpickle untrusted data!
    assert job.job_state == job_state
    # We won't unpickle it as it would execute the command

    # Test attempting to pickle system objects
    with pytest.raises(TypeError):  # Python raises TypeError for modules
        pickle.dumps(sys.modules["os"])


def test_job_state_pickle_protocol_compatibility():
    """Test job state compatibility with different pickle protocols."""
    import pickle

    test_data = {"name": "test", "value": 123, "nested": {"key": "value"}}

    # Test all available pickle protocols
    for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
        job_state = pickle.dumps(test_data, protocol=protocol)
        job = Job(
            id=f"test-job-protocol-{protocol}",
            flow_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            name=f"Protocol {protocol} Job",
            job_state=job_state,
        )
        assert job.job_state == job_state
        # Verify we can unpickle the data
        unpickled_data = pickle.loads(job.job_state)  # noqa: S301
        assert unpickled_data == test_data


def test_job_state_thread_synchronization():
    """Test serialization of thread synchronization primitives."""
    import asyncio
    import multiprocessing
    import pickle
    import threading
    from concurrent.futures import ThreadPoolExecutor

    # Test threading.Lock
    lock = threading.Lock()
    with pytest.raises(TypeError):  # Python raises TypeError for thread locks
        pickle.dumps(lock)

    # Test threading.RLock
    rlock = threading.RLock()
    with pytest.raises(TypeError):
        pickle.dumps(rlock)

    # Test threading.Event
    event = threading.Event()
    with pytest.raises(TypeError):
        pickle.dumps(event)

    # Test threading.Condition
    condition = threading.Condition()
    with pytest.raises(TypeError):
        pickle.dumps(condition)

    # Test multiprocessing.Lock
    mp_lock = multiprocessing.Lock()
    with pytest.raises(RuntimeError):  # Multiprocessing raises RuntimeError
        pickle.dumps(mp_lock)

    # Test ThreadPoolExecutor
    executor = ThreadPoolExecutor(max_workers=1)
    with pytest.raises(TypeError):
        pickle.dumps(executor)
    executor.shutdown()

    # Test asyncio.Lock - Note: asyncio locks can actually be pickled in some cases
    async_lock = asyncio.Lock()
    with suppress(TypeError, AttributeError):
        pickle.dumps(async_lock)

    # Test object containing a lock
    obj_with_lock = ObjectWithLock()
    with pytest.raises(TypeError):
        pickle.dumps(obj_with_lock)

    # Test dictionary containing a lock
    dict_with_lock = {"lock": threading.Lock(), "data": {"key": "value"}}
    with pytest.raises(TypeError):
        pickle.dumps(dict_with_lock)
