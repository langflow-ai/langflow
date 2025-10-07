from unittest.mock import Mock, patch

import pytest
from lfx.utils.async_helpers import run_until_complete, timeout_context


class TestTimeoutContext:
    """Test cases for timeout_context function."""

    def test_timeout_context_exists(self):
        """Test that timeout_context function exists and is callable."""
        # Check if timeout_context is callable
        assert callable(timeout_context)

    def test_timeout_context_is_async_context_manager(self):
        """Test that timeout_context returns an async context manager."""
        ctx_manager = timeout_context(1.0)
        # Check it has async context manager methods
        assert hasattr(ctx_manager, "__aenter__")
        assert hasattr(ctx_manager, "__aexit__")
        assert callable(ctx_manager.__aenter__)
        assert callable(ctx_manager.__aexit__)


class TestRunUntilComplete:
    """Test cases for run_until_complete function."""

    def test_run_until_complete_basic(self):
        """Test basic functionality of run_until_complete."""

        async def simple_coro():
            return 42

        result = run_until_complete(simple_coro())
        assert result == 42

    def test_run_until_complete_with_exception(self):
        """Test run_until_complete with exception."""

        async def failing_coro():
            msg = "Test error"
            raise ValueError(msg)

        with pytest.raises(ValueError, match="Test error"):
            run_until_complete(failing_coro())

    def test_run_until_complete_different_return_types(self):
        """Test run_until_complete with different return types."""
        test_cases = [
            (42, int),
            ("hello", str),
            ([1, 2, 3], list),
            ({"key": "value"}, dict),
            (None, type(None)),
        ]

        for expected_value, expected_type in test_cases:

            async def typed_coro(val=expected_value):
                return val

            result = run_until_complete(typed_coro())
            assert result == expected_value
            assert isinstance(result, expected_type)

    @patch("asyncio.get_running_loop")
    def test_run_until_complete_no_running_loop(self, mock_get_running_loop):
        """Test run_until_complete when no event loop is running."""
        # Mock no running loop (raises RuntimeError)
        mock_get_running_loop.side_effect = RuntimeError("No running event loop")

        async def simple_coro():
            return "no_loop"

        with patch("asyncio.run") as mock_run:
            mock_run.return_value = "no_loop"

            result = run_until_complete(simple_coro())

            mock_run.assert_called_once()
            assert result == "no_loop"

    @patch("asyncio.get_running_loop")
    @patch("concurrent.futures.ThreadPoolExecutor")
    def test_run_until_complete_with_running_loop_path(self, mock_executor_class, mock_get_running_loop):
        """Test run_until_complete when event loop is already running."""
        # Mock that there is a running loop
        mock_get_running_loop.return_value = Mock()

        # Mock the ThreadPoolExecutor and future
        mock_executor = Mock()
        mock_future = Mock()
        mock_future.result.return_value = "thread_result"
        mock_executor.submit.return_value = mock_future
        mock_executor_class.return_value.__enter__.return_value = mock_executor

        async def simple_coro():
            return "thread_result"

        result = run_until_complete(simple_coro())

        # Verify ThreadPoolExecutor was used
        mock_executor_class.assert_called_once()
        mock_executor.submit.assert_called_once()
        assert result == "thread_result"

    @patch("asyncio.get_running_loop")
    @patch("concurrent.futures.ThreadPoolExecutor")
    def test_run_until_complete_thread_pool_exception(self, mock_executor_class, mock_get_running_loop):
        """Test run_until_complete handles thread pool exceptions."""
        mock_get_running_loop.return_value = Mock()

        async def failing_coro():
            msg = "Thread pool test error"
            raise ValueError(msg)

        # Mock executor to raise exception
        mock_executor = Mock()
        mock_future = Mock()
        mock_future.result.side_effect = ValueError("Thread pool test error")
        mock_executor.submit.return_value = mock_future
        mock_executor_class.return_value.__enter__.return_value = mock_executor

        with pytest.raises(ValueError, match="Thread pool test error"):
            run_until_complete(failing_coro())

    @patch("asyncio.get_running_loop")
    @patch("concurrent.futures.ThreadPoolExecutor")
    @patch("asyncio.new_event_loop")
    def test_run_until_complete_new_loop_cleanup(self, mock_new_loop, mock_executor_class, mock_get_running_loop):
        """Test that new event loop is properly cleaned up."""
        mock_get_running_loop.return_value = Mock()
        # Event loop setup for thread execution

        mock_loop_instance = Mock()
        mock_loop_instance.run_until_complete.return_value = "cleanup_test"
        mock_new_loop.return_value = mock_loop_instance

        mock_executor = Mock()
        mock_future = Mock()
        mock_future.result.return_value = "cleanup_test"
        mock_executor.submit.return_value = mock_future
        mock_executor_class.return_value.__enter__.return_value = mock_executor

        async def simple_coro():
            return "cleanup_test"

        result = run_until_complete(simple_coro())

        # Verify the loop operations happened in the thread
        assert result == "cleanup_test"
        mock_executor.submit.assert_called_once()

    @patch("asyncio.get_running_loop")
    @patch("concurrent.futures.ThreadPoolExecutor")
    @patch("asyncio.new_event_loop")
    def test_run_until_complete_new_loop_exception_cleanup(
        self, mock_new_loop, mock_executor_class, mock_get_running_loop
    ):
        """Test that event loop is cleaned up even when exception occurs."""
        mock_get_running_loop.return_value = Mock()
        # Event loop setup for thread execution

        async def failing_coro():
            msg = "Loop exception test"
            raise RuntimeError(msg)

        mock_loop_instance = Mock()
        mock_loop_instance.run_until_complete.side_effect = RuntimeError("Loop exception test")
        mock_new_loop.return_value = mock_loop_instance

        mock_executor = Mock()
        mock_future = Mock()
        mock_future.result.side_effect = RuntimeError("Loop exception test")
        mock_executor.submit.return_value = mock_future
        mock_executor_class.return_value.__enter__.return_value = mock_executor

        with pytest.raises(RuntimeError, match="Loop exception test"):
            run_until_complete(failing_coro())

        # Verify executor was still called
        mock_executor.submit.assert_called_once()
