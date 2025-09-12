"""Tests for async_helpers.py functions."""

import asyncio
import threading
import time
from unittest.mock import patch

import pytest
from lfx.utils.async_helpers import run_until_complete


class TestRunUntilComplete:
    """Test the run_until_complete function."""

    def test_run_until_complete_no_running_loop(self):
        """Test run_until_complete when no event loop is running."""

        async def simple_coro():
            return "test_result"

        # Should work when no loop is running
        result = run_until_complete(simple_coro())
        assert result == "test_result"

    def test_run_until_complete_simple_coro_with_running_loop(self):
        """Test run_until_complete with a simple coroutine when loop is running."""

        async def simple_coro():
            return "from_thread"

        async def main_test():
            # This should work with our fix - runs in separate thread
            return run_until_complete(simple_coro())

        result = asyncio.run(main_test())
        assert result == "from_thread"

    def test_run_until_complete_complex_coro_with_running_loop(self):
        """Test run_until_complete with a complex async coroutine when loop is running."""

        async def complex_coro():
            await asyncio.sleep(0.01)  # This requires event loop cooperation
            return "complex_result"

        async def main_test():
            # This would deadlock with old implementation that calls loop.run_until_complete
            # using the running loop
            return run_until_complete(complex_coro())

        result = asyncio.run(main_test())
        assert result == "complex_result"

    def test_run_until_complete_with_exception_in_new_thread(self):
        """Test that exceptions in the new thread are properly propagated."""

        async def failing_coro():
            msg = "Test exception"
            raise ValueError(msg)

        async def main_test():
            with pytest.raises(ValueError, match="Test exception"):
                run_until_complete(failing_coro())

        asyncio.run(main_test())

    def test_run_until_complete_preserves_return_value(self):
        """Test that complex return values are preserved across threads."""

        async def return_complex():
            return {"key": "value", "list": [1, 2, 3], "nested": {"inner": "data"}}

        async def main_test():
            return run_until_complete(return_complex())

        result = asyncio.run(main_test())
        expected = {"key": "value", "list": [1, 2, 3], "nested": {"inner": "data"}}
        assert result == expected

    def test_run_until_complete_thread_isolation(self):
        """Test that thread-local data is properly isolated."""
        # Set up thread-local storage
        local_data = threading.local()
        local_data.value = "main_thread"

        async def check_thread_isolation():
            # This should NOT have access to main thread's local data
            try:
                return getattr(local_data, "value", "no_value")
            except AttributeError:
                return "no_value"

        async def main_test():
            # Confirm main thread has the value
            assert getattr(local_data, "value", None) == "main_thread"

            # Check that new thread doesn't have access
            return run_until_complete(check_thread_isolation())

        result = asyncio.run(main_test())
        assert result == "no_value"  # Thread isolation working

    def test_run_until_complete_concurrent_execution(self):
        """Test that multiple concurrent calls work correctly."""

        async def delayed_coro(delay, value):
            await asyncio.sleep(delay)
            return f"result_{value}"

        async def main_test():
            # Run multiple coroutines concurrently
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(run_until_complete, delayed_coro(0.01, i)) for i in range(3)]

                return [f.result() for f in futures]

        results = asyncio.run(main_test())
        expected = ["result_0", "result_1", "result_2"]
        assert results == expected

    def test_run_until_complete_performance_impact(self):
        """Test that the performance impact is reasonable."""

        async def quick_coro():
            return "quick"

        async def main_test():
            # Time multiple executions
            start_time = time.time()

            for _ in range(10):
                result = run_until_complete(quick_coro())
                assert result == "quick"

            end_time = time.time()
            return end_time - start_time

        duration = asyncio.run(main_test())

        # Should complete 10 executions in reasonable time (less than 1 second)
        assert duration < 1.0, f"Performance test took too long: {duration}s"

    def test_run_until_complete_nested_async_operations(self):
        """Test with nested async operations that require event loop."""

        async def inner_async():
            await asyncio.sleep(0.001)
            return "inner"

        async def outer_async():
            # This creates tasks that need event loop scheduling
            tasks = [asyncio.create_task(inner_async()) for _ in range(3)]
            return await asyncio.gather(*tasks)

        async def main_test():
            # This would definitely deadlock with old implementation
            return run_until_complete(outer_async())

        result = asyncio.run(main_test())
        assert result == ["inner", "inner", "inner"]

    def test_run_until_complete_with_timeout(self):
        """Test that timeouts work correctly in the new thread."""

        async def slow_coro():
            await asyncio.sleep(10)  # Very long delay
            return "should_not_reach"

        async def timeout_coro():
            try:
                await asyncio.wait_for(slow_coro(), timeout=0.01)
            except asyncio.TimeoutError:
                return "timeout_occurred"
            return "no_timeout"

        async def main_test():
            return run_until_complete(timeout_coro())

        result = asyncio.run(main_test())
        assert result == "timeout_occurred"

    def test_original_behavior_preserved_no_loop(self):
        """Test that original behavior is preserved when no loop is running."""

        async def test_coro():
            return "original_behavior"

        # Mock asyncio.run to verify it's called when no loop exists
        with patch("asyncio.run", return_value="mocked_result") as mock_run:
            result = run_until_complete(test_coro())

            # Should have called asyncio.run (original behavior)
            mock_run.assert_called_once()
            assert result == "mocked_result"
