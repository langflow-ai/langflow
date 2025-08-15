import asyncio
from unittest.mock import MagicMock, Mock, patch

import pytest
from langflow.utils.async_helpers import run_until_complete, timeout_context


class TestTimeoutContext:
    """Test cases for timeout_context async context manager."""

    @pytest.mark.asyncio
    async def test_timeout_context_no_timeout(self):
        """Test timeout_context when operation completes within timeout."""
        async with timeout_context(1.0) as ctx:
            # Simulate a quick operation
            await asyncio.sleep(0.1)
            assert ctx is not None

    @pytest.mark.asyncio
    async def test_timeout_context_with_timeout(self):
        """Test timeout_context when operation exceeds timeout."""
        with pytest.raises((asyncio.TimeoutError, TimeoutError)):
            async with timeout_context(0.1):
                # Simulate a slow operation
                await asyncio.sleep(0.5)

    @pytest.mark.asyncio
    async def test_timeout_context_zero_timeout(self):
        """Test timeout_context with zero timeout."""
        with pytest.raises((asyncio.TimeoutError, TimeoutError)):
            async with timeout_context(0):
                await asyncio.sleep(0.01)

    @pytest.mark.asyncio
    async def test_timeout_context_immediate_completion(self):
        """Test timeout_context with immediate completion."""
        async with timeout_context(1.0):
            # Immediate operation
            result = 42
            assert result == 42

    @pytest.mark.asyncio
    async def test_timeout_context_context_manager_protocol(self):
        """Test that timeout_context follows async context manager protocol."""
        # Test that it can be used as async context manager
        async with timeout_context(1.0) as ctx:
            assert ctx is not None
            # Context should be available during execution

    @pytest.mark.asyncio
    async def test_timeout_context_exception_handling(self):
        """Test timeout_context handles other exceptions properly."""
        msg = "Test exception"
        with pytest.raises(ValueError, match="Test exception"):
            async with timeout_context(1.0):
                raise ValueError(msg)

    @pytest.mark.asyncio
    @patch("asyncio.timeout")
    async def test_timeout_context_with_asyncio_timeout_available(self, mock_timeout):
        """Test timeout_context when asyncio.timeout is available."""
        mock_context = MagicMock()
        mock_timeout.return_value.__enter__ = Mock(return_value=mock_context)
        mock_timeout.return_value.__exit__ = Mock(return_value=None)

        # Force the asyncio.timeout path
        with patch("asyncio.timeout", mock_timeout):
            async with timeout_context(5.0):
                pass

            mock_timeout.assert_called_once_with(5.0)

    def test_timeout_context_different_timeout_values(self):
        """Test timeout_context with different timeout values."""
        # Test with various timeout values
        timeout_values = [0.1, 0.5, 1.0, 2.0, 10.0]

        for timeout_val in timeout_values:
            # Just test that the context manager can be created
            # without errors for different timeout values
            context = timeout_context(timeout_val)
            assert context is not None


class TestRunUntilComplete:
    """Test cases for run_until_complete function."""

    def test_run_until_complete_no_event_loop(self):
        """Test run_until_complete when no event loop is running."""

        async def simple_coro():
            return "completed"

        # This should work when no event loop is running
        result = run_until_complete(simple_coro())
        assert result == "completed"

    def test_run_until_complete_with_async_operation(self):
        """Test run_until_complete with async operations."""

        async def async_operation():
            await asyncio.sleep(0.01)
            return 42

        result = run_until_complete(async_operation())
        assert result == 42

    def test_run_until_complete_with_exception(self):
        """Test run_until_complete handles exceptions."""

        async def failing_coro():
            msg = "Test error"
            raise ValueError(msg)

        with pytest.raises(ValueError, match="Test error"):
            run_until_complete(failing_coro())

    @patch("asyncio.get_running_loop")
    @patch("asyncio.run")
    def test_run_until_complete_no_running_loop_path(self, mock_run, mock_get_loop):
        """Test run_until_complete when no loop is running."""
        # Simulate no running loop
        mock_get_loop.side_effect = RuntimeError("No running event loop")
        mock_run.return_value = "test_result"

        async def test_coro():
            return "test_result"

        result = run_until_complete(test_coro())

        assert result == "test_result"
        mock_get_loop.assert_called_once()
        mock_run.assert_called_once()

    @patch("asyncio.get_running_loop")
    @patch("concurrent.futures.ThreadPoolExecutor")
    def test_run_until_complete_with_running_loop_path(self, mock_executor_class, mock_get_loop):
        """Test run_until_complete when event loop is already running."""
        # Simulate running loop exists
        mock_get_loop.return_value = Mock()

        # Mock the ThreadPoolExecutor and its context manager behavior
        mock_executor = MagicMock()
        mock_future = Mock()
        mock_future.result.return_value = "threaded_result"
        mock_executor.submit.return_value = mock_future
        mock_executor_class.return_value.__enter__ = Mock(return_value=mock_executor)
        mock_executor_class.return_value.__exit__ = Mock(return_value=None)

        async def test_coro():
            return "threaded_result"

        with patch("asyncio.new_event_loop") as mock_new_loop, patch("asyncio.set_event_loop") as mock_set_loop:
            mock_loop_instance = Mock()
            mock_loop_instance.run_until_complete.return_value = "threaded_result"
            mock_new_loop.return_value = mock_loop_instance

            result = run_until_complete(test_coro())

            assert result == "threaded_result"
            mock_get_loop.assert_called_once()
            mock_new_loop.assert_called_once()
            mock_set_loop.assert_called_once_with(mock_loop_instance)
            mock_loop_instance.run_until_complete.assert_called_once()
            mock_loop_instance.close.assert_called_once()

    def test_run_until_complete_coroutine_validation(self):
        """Test run_until_complete with different coroutine types."""

        # Test with simple coroutine
        async def simple():
            return "simple"

        result = run_until_complete(simple())
        assert result == "simple"

        # Test with coroutine that uses await
        async def with_await():
            await asyncio.sleep(0.001)
            return "awaited"

        result = run_until_complete(with_await())
        assert result == "awaited"

    def test_run_until_complete_multiple_calls(self):
        """Test multiple calls to run_until_complete."""

        async def counter_coro(value):
            await asyncio.sleep(0.001)
            return value * 2

        results = []
        for i in range(3):
            result = run_until_complete(counter_coro(i))
            results.append(result)

        assert results == [0, 2, 4]

    @patch("asyncio.get_running_loop")
    def test_run_until_complete_thread_pool_exception_handling(self, mock_get_loop):
        """Test exception handling in thread pool execution path."""
        # Simulate running loop exists
        mock_get_loop.return_value = Mock()

        async def failing_coro():
            msg = "Thread pool test error"
            raise ValueError(msg)

        with patch("concurrent.futures.ThreadPoolExecutor") as mock_executor_class:
            mock_executor = MagicMock()
            mock_future = Mock()
            mock_future.result.side_effect = ValueError("Thread pool test error")
            mock_executor.submit.return_value = mock_future
            mock_executor_class.return_value.__enter__ = Mock(return_value=mock_executor)
            mock_executor_class.return_value.__exit__ = Mock(return_value=None)

            with pytest.raises(ValueError, match="Thread pool test error"):
                run_until_complete(failing_coro())

    @patch("asyncio.get_running_loop")
    def test_run_until_complete_new_loop_cleanup(self, mock_get_loop):
        """Test that new event loop is properly cleaned up."""
        # Simulate running loop exists
        mock_get_loop.return_value = Mock()

        async def test_coro():
            return "cleanup_test"

        with (
            patch("concurrent.futures.ThreadPoolExecutor") as mock_executor_class,
            patch("asyncio.new_event_loop") as mock_new_loop,
            patch("asyncio.set_event_loop"),
        ):
            mock_loop_instance = Mock()
            mock_loop_instance.run_until_complete.return_value = "cleanup_test"
            mock_new_loop.return_value = mock_loop_instance

            mock_executor = MagicMock()
            mock_future = Mock()
            mock_future.result.return_value = "cleanup_test"
            mock_executor.submit.return_value = mock_future
            mock_executor_class.return_value.__enter__ = Mock(return_value=mock_executor)
            mock_executor_class.return_value.__exit__ = Mock(return_value=None)

            result = run_until_complete(test_coro())

            # Verify cleanup was called
            mock_loop_instance.close.assert_called_once()
            assert result == "cleanup_test"

    @patch("asyncio.get_running_loop")
    def test_run_until_complete_new_loop_exception_cleanup(self, mock_get_loop):
        """Test that new event loop is cleaned up even when exception occurs."""
        # Simulate running loop exists
        mock_get_loop.return_value = Mock()

        async def failing_coro():
            msg = "Loop exception test"
            raise RuntimeError(msg)

        with (
            patch("concurrent.futures.ThreadPoolExecutor") as mock_executor_class,
            patch("asyncio.new_event_loop") as mock_new_loop,
            patch("asyncio.set_event_loop"),
        ):
            mock_loop_instance = Mock()
            mock_loop_instance.run_until_complete.side_effect = RuntimeError("Loop exception test")
            mock_new_loop.return_value = mock_loop_instance

            mock_executor = MagicMock()
            mock_future = Mock()
            mock_future.result.side_effect = RuntimeError("Loop exception test")
            mock_executor.submit.return_value = mock_future
            mock_executor_class.return_value.__enter__ = Mock(return_value=mock_executor)
            mock_executor_class.return_value.__exit__ = Mock(return_value=None)

            with pytest.raises(RuntimeError, match="Loop exception test"):
                run_until_complete(failing_coro())

            # Verify cleanup was still called despite exception
            mock_loop_instance.close.assert_called_once()

    def test_run_until_complete_return_types(self):
        """Test run_until_complete with different return types."""
        # Test different return types
        test_cases = [
            (42, int),
            ("string", str),
            ([1, 2, 3], list),
            ({"key": "value"}, dict),
            (None, type(None)),
            (True, bool),
        ]

        for expected_value, expected_type in test_cases:

            async def typed_coro(val=expected_value):
                return val

            result = run_until_complete(typed_coro())
            assert result == expected_value
            assert isinstance(result, expected_type)

    def test_run_until_complete_concurrent_execution(self):
        """Test run_until_complete behavior with concurrent execution."""
        results = []

        def run_async_task(value):
            async def task():
                await asyncio.sleep(0.01)
                return value * 2

            return run_until_complete(task())

        # Test that multiple calls work (though they'll be sequential due to GIL)
        for i in range(3):
            result = run_async_task(i)
            results.append(result)

        assert results == [0, 2, 4]
