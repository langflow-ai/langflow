"""Tests for langflow.services.jobs.service.JobService - execute_with_status logic.

Since JobService methods mostly delegate to DB CRUD functions, we focus on
testing execute_with_status which has complex status-management logic that
can be tested with mocking.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.jobs.service import JobService

pytestmark = pytest.mark.asyncio


@pytest.fixture
def job_service():
    """Create a JobService with mocked dependencies."""
    with patch("langflow.services.jobs.service.session_scope"):
        svc = JobService()
    return svc


@pytest.fixture
def job_id():
    return uuid4()


class TestExecuteWithStatus:
    """Tests for JobService.execute_with_status method."""

    async def test_successful_execution(self, job_service, job_id):
        """On success, status should go IN_PROGRESS -> COMPLETED."""
        status_updates = []

        async def mock_update(jid, status, *, finished_timestamp=False):
            status_updates.append((status, finished_timestamp))

        job_service.update_job_status = mock_update

        async def my_coro(x, y):
            return x + y

        result = await job_service.execute_with_status(job_id, my_coro, 3, 4)
        assert result == 7
        assert status_updates[0] == (JobStatus.IN_PROGRESS, False)
        assert status_updates[1] == (JobStatus.COMPLETED, True)

    async def test_assertion_error_sets_failed(self, job_service, job_id):
        status_updates = []

        async def mock_update(jid, status, *, finished_timestamp=False):
            status_updates.append((status, finished_timestamp))

        job_service.update_job_status = mock_update

        async def failing_coro():
            msg = "bad assertion"
            raise AssertionError(msg)

        with pytest.raises(AssertionError, match="bad assertion"):
            await job_service.execute_with_status(job_id, failing_coro)

        assert status_updates[-1] == (JobStatus.FAILED, True)

    async def test_timeout_error_sets_timed_out(self, job_service, job_id):
        status_updates = []

        async def mock_update(jid, status, *, finished_timestamp=False):
            status_updates.append((status, finished_timestamp))

        job_service.update_job_status = mock_update

        async def timeout_coro():
            raise asyncio.TimeoutError

        with pytest.raises(asyncio.TimeoutError):
            await job_service.execute_with_status(job_id, timeout_coro)

        assert status_updates[-1] == (JobStatus.TIMED_OUT, True)

    async def test_user_cancelled_sets_cancelled(self, job_service, job_id):
        status_updates = []

        async def mock_update(jid, status, *, finished_timestamp=False):
            status_updates.append((status, finished_timestamp))

        job_service.update_job_status = mock_update

        async def user_cancel_coro():
            raise asyncio.CancelledError("LANGFLOW_USER_CANCELLED")

        with pytest.raises(asyncio.CancelledError):
            await job_service.execute_with_status(job_id, user_cancel_coro)

        assert status_updates[-1] == (JobStatus.CANCELLED, True)

    async def test_system_cancelled_sets_failed(self, job_service, job_id):
        status_updates = []

        async def mock_update(jid, status, *, finished_timestamp=False):
            status_updates.append((status, finished_timestamp))

        job_service.update_job_status = mock_update

        async def system_cancel_coro():
            raise asyncio.CancelledError("system shutdown")

        with pytest.raises(asyncio.CancelledError):
            await job_service.execute_with_status(job_id, system_cancel_coro)

        assert status_updates[-1] == (JobStatus.FAILED, True)

    async def test_generic_exception_sets_failed(self, job_service, job_id):
        status_updates = []

        async def mock_update(jid, status, *, finished_timestamp=False):
            status_updates.append((status, finished_timestamp))

        job_service.update_job_status = mock_update

        async def error_coro():
            msg = "something went wrong"
            raise RuntimeError(msg)

        with pytest.raises(RuntimeError, match="something went wrong"):
            await job_service.execute_with_status(job_id, error_coro)

        assert status_updates[-1] == (JobStatus.FAILED, True)

    async def test_args_and_kwargs_passed(self, job_service, job_id):
        """Ensure args and kwargs are correctly forwarded to the coroutine."""
        received = {}

        async def mock_update(jid, status, *, finished_timestamp=False):
            pass

        job_service.update_job_status = mock_update

        async def capture_coro(*args, **kwargs):
            received["args"] = args
            received["kwargs"] = kwargs
            return "done"

        await job_service.execute_with_status(job_id, capture_coro, "a", "b", key="val")
        assert received["args"] == ("a", "b")
        assert received["kwargs"] == {"key": "val"}

    async def test_cancelled_without_args_sets_failed(self, job_service, job_id):
        """CancelledError with no args should set FAILED (system-initiated)."""
        status_updates = []

        async def mock_update(jid, status, *, finished_timestamp=False):
            status_updates.append((status, finished_timestamp))

        job_service.update_job_status = mock_update

        async def cancel_no_args():
            raise asyncio.CancelledError

        with pytest.raises(asyncio.CancelledError):
            await job_service.execute_with_status(job_id, cancel_no_args)

        assert status_updates[-1] == (JobStatus.FAILED, True)
