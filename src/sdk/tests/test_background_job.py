"""Unit tests for BackgroundJob and AsyncLangflowClient.run_background.

All tests run entirely in-process; no real Langflow instance required.
The async client's ``run`` method is patched directly so only the asyncio
task lifecycle and BackgroundJob status logic is under test.
"""

from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import AsyncMock, patch

import pytest
from langflow_sdk.background_job import BackgroundJob
from langflow_sdk.exceptions import LangflowTimeoutError
from langflow_sdk.models import RunOutput, RunResponse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RUN_RESPONSE = RunResponse(
    session_id="s1",
    outputs=[
        RunOutput(
            results={},
            artifacts={},
            outputs=[{"results": {"message": {"text": "Done!"}}}],
        )
    ],
)


async def _quick_success() -> RunResponse:
    await asyncio.sleep(0)
    return _RUN_RESPONSE


async def _slow_success(delay: float = 0.5) -> RunResponse:
    await asyncio.sleep(delay)
    return _RUN_RESPONSE


async def _always_fail() -> RunResponse:
    await asyncio.sleep(0)
    msg = "flow exploded"
    raise RuntimeError(msg)


# ---------------------------------------------------------------------------
# BackgroundJob status helpers
# ---------------------------------------------------------------------------


class TestBackgroundJobStatus:
    @pytest.mark.asyncio
    async def test_is_running_while_in_flight(self):
        task = asyncio.create_task(_slow_success(0.5))
        job = BackgroundJob(task)
        assert job.is_running() is True
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task

    @pytest.mark.asyncio
    async def test_is_running_false_after_completion(self):
        task = asyncio.create_task(_quick_success())
        job = BackgroundJob(task)
        await task
        assert job.is_running() is False

    @pytest.mark.asyncio
    async def test_is_completed_true_after_success(self):
        task = asyncio.create_task(_quick_success())
        job = BackgroundJob(task)
        await task
        assert job.is_completed() is True

    @pytest.mark.asyncio
    async def test_is_completed_false_while_running(self):
        task = asyncio.create_task(_slow_success(0.5))
        job = BackgroundJob(task)
        assert job.is_completed() is False
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task

    @pytest.mark.asyncio
    async def test_is_completed_false_after_failure(self):
        task = asyncio.create_task(_always_fail())
        job = BackgroundJob(task)
        with contextlib.suppress(RuntimeError):
            await task
        assert job.is_completed() is False

    @pytest.mark.asyncio
    async def test_is_failed_false_while_running(self):
        task = asyncio.create_task(_slow_success(0.5))
        job = BackgroundJob(task)
        assert job.is_failed() is False
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task

    @pytest.mark.asyncio
    async def test_is_failed_true_after_exception(self):
        task = asyncio.create_task(_always_fail())
        job = BackgroundJob(task)
        with contextlib.suppress(RuntimeError):
            await task
        assert job.is_failed() is True

    @pytest.mark.asyncio
    async def test_is_failed_true_after_cancellation(self):
        task = asyncio.create_task(_slow_success(5.0))
        job = BackgroundJob(task)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        assert job.is_failed() is True

    @pytest.mark.asyncio
    async def test_status_helpers_mutually_exclusive_on_success(self):
        task = asyncio.create_task(_quick_success())
        job = BackgroundJob(task)
        await task
        assert job.is_completed() is True
        assert job.is_failed() is False
        assert job.is_running() is False

    @pytest.mark.asyncio
    async def test_status_helpers_mutually_exclusive_on_failure(self):
        task = asyncio.create_task(_always_fail())
        job = BackgroundJob(task)
        with contextlib.suppress(RuntimeError):
            await task
        assert job.is_completed() is False
        assert job.is_failed() is True
        assert job.is_running() is False


# ---------------------------------------------------------------------------
# BackgroundJob.wait_for_completion
# ---------------------------------------------------------------------------


class TestWaitForCompletion:
    @pytest.mark.asyncio
    async def test_returns_run_response_on_success(self):
        task = asyncio.create_task(_quick_success())
        job = BackgroundJob(task)
        result = await job.wait_for_completion()
        assert isinstance(result, RunResponse)
        assert result.get_chat_output() == "Done!"

    @pytest.mark.asyncio
    async def test_raises_langflow_timeout_error_on_expiry(self):
        task = asyncio.create_task(_slow_success(5.0))
        job = BackgroundJob(task)
        with pytest.raises(LangflowTimeoutError):
            await job.wait_for_completion(timeout=0.01)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task

    @pytest.mark.asyncio
    async def test_task_still_running_after_timeout(self):
        """wait_for_completion uses shield() so the task survives a timeout."""
        task = asyncio.create_task(_slow_success(5.0))
        job = BackgroundJob(task)
        with pytest.raises(LangflowTimeoutError):
            await job.wait_for_completion(timeout=0.01)
        # Task should still be alive — shield protects it from cancellation
        assert not task.done() or not task.cancelled()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task

    @pytest.mark.asyncio
    async def test_re_raises_underlying_exception(self):
        task = asyncio.create_task(_always_fail())
        job = BackgroundJob(task)
        with pytest.raises(RuntimeError, match="flow exploded"):
            await job.wait_for_completion()

    @pytest.mark.asyncio
    async def test_none_timeout_waits_indefinitely(self):
        task = asyncio.create_task(_slow_success(0.05))
        job = BackgroundJob(task)
        result = await job.wait_for_completion(timeout=None)
        assert result.is_completed() is True

    @pytest.mark.asyncio
    async def test_can_be_awaited_multiple_times(self):
        task = asyncio.create_task(_quick_success())
        job = BackgroundJob(task)
        r1 = await job.wait_for_completion()
        r2 = await job.wait_for_completion()
        assert r1.get_chat_output() == r2.get_chat_output()


# ---------------------------------------------------------------------------
# BackgroundJob.cancel
# ---------------------------------------------------------------------------


class TestCancel:
    @pytest.mark.asyncio
    async def test_cancel_returns_true_for_running_task(self):
        task = asyncio.create_task(_slow_success(5.0))
        job = BackgroundJob(task)
        result = await job.cancel()
        assert result is True

    @pytest.mark.asyncio
    async def test_cancel_returns_false_for_finished_task(self):
        task = asyncio.create_task(_quick_success())
        job = BackgroundJob(task)
        await task
        result = await job.cancel()
        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_makes_task_done(self):
        task = asyncio.create_task(_slow_success(5.0))
        job = BackgroundJob(task)
        await job.cancel()
        assert task.done()

    @pytest.mark.asyncio
    async def test_cancel_idempotent(self):
        task = asyncio.create_task(_slow_success(5.0))
        job = BackgroundJob(task)
        await job.cancel()
        result = await job.cancel()
        assert result is False


# ---------------------------------------------------------------------------
# AsyncLangflowClient.run_background integration
# ---------------------------------------------------------------------------


class TestRunBackground:
    @pytest.mark.asyncio
    async def test_returns_background_job_instance(self):
        from langflow_sdk.client import AsyncLangflowClient

        client = AsyncLangflowClient("http://langflow.test", api_key="test-key")  # pragma: allowlist secret
        with patch.object(client, "run", new_callable=AsyncMock, return_value=_RUN_RESPONSE):
            job = await client.run_background("my-flow", input_value="Hello")
        assert isinstance(job, BackgroundJob)
        await job.wait_for_completion()
        await client.aclose()

    @pytest.mark.asyncio
    async def test_run_background_calls_run_with_correct_args(self):
        from langflow_sdk.client import AsyncLangflowClient

        client = AsyncLangflowClient("http://langflow.test", api_key="test-key")  # pragma: allowlist secret
        mock_run = AsyncMock(return_value=_RUN_RESPONSE)
        with patch.object(client, "run", mock_run):
            job = await client.run_background(
                "my-flow",
                "Hello",
                input_type="text",
                output_type="text",
            )
            await job.wait_for_completion()
        mock_run.assert_awaited_once_with(
            "my-flow",
            "Hello",
            input_type="text",
            output_type="text",
            tweaks=None,
        )
        await client.aclose()

    @pytest.mark.asyncio
    async def test_run_background_job_is_running_immediately(self):
        from langflow_sdk.client import AsyncLangflowClient

        async def _slow_run(*_args, **_kwargs) -> RunResponse:
            await asyncio.sleep(5.0)
            return _RUN_RESPONSE

        client = AsyncLangflowClient("http://langflow.test", api_key="test-key")  # pragma: allowlist secret
        with patch.object(client, "run", side_effect=_slow_run):
            job = await client.run_background("my-flow", input_value="Hi")
        assert job.is_running() is True
        await job.cancel()
        await client.aclose()

    @pytest.mark.asyncio
    async def test_run_background_completion_result_matches_run(self):
        from langflow_sdk.client import AsyncLangflowClient

        client = AsyncLangflowClient("http://langflow.test", api_key="test-key")  # pragma: allowlist secret
        with patch.object(client, "run", new_callable=AsyncMock, return_value=_RUN_RESPONSE):
            job = await client.run_background("my-flow")
            response = await job.wait_for_completion()
        assert response.get_chat_output() == "Done!"
        await client.aclose()

    @pytest.mark.asyncio
    async def test_run_background_exported_from_package(self):
        from langflow_sdk import BackgroundJob as ExportedBackgroundJob

        assert ExportedBackgroundJob is BackgroundJob

    @pytest.mark.asyncio
    async def test_langflow_timeout_error_exported_from_package(self):
        from langflow_sdk import LangflowTimeoutError as ExportedError

        assert ExportedError is LangflowTimeoutError
