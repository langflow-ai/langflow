"""Unit tests for thread safety changes in docling_inline component."""

import threading
import time
from multiprocessing import get_context
from queue import Queue as ThreadQueue
from unittest.mock import MagicMock, Mock, patch

import pytest

try:
    from docling_core.types.doc import DoclingDocument  # noqa: F401
except ImportError:
    # Skip entire module if docling not available
    pytest.skip("docling_core not installed", allow_module_level=True)

from lfx.components.docling.docling_inline import DoclingInlineComponent


# Module-level worker functions for multiprocessing (can't pickle local functions)
def process_worker_with_result(q, result):
    """Worker that puts result in queue."""
    time.sleep(0.1)
    q.put(result)


def process_worker_no_result(q):
    """Worker that exits without putting result."""


def process_worker_infinite_loop():
    """Worker that runs indefinitely."""
    while True:
        time.sleep(0.1)


class TestWorkerMonitoring:
    """Test worker monitoring functionality (_wait_for_result_with_worker_monitoring)."""

    def test_wait_for_result_with_thread_success(self):
        """Test successful result retrieval from a thread worker."""
        component = DoclingInlineComponent()
        queue = ThreadQueue()
        expected_result = [{"document": "test_doc", "file_path": "test.pdf"}]

        # Create a simple thread that puts a result in the queue
        def worker_func():
            time.sleep(0.1)
            queue.put(expected_result)

        worker = threading.Thread(target=worker_func)
        worker.start()

        # Wait for result
        result = component._wait_for_result_with_worker_monitoring(queue, worker, timeout=5)

        assert result == expected_result
        worker.join()

    def test_wait_for_result_with_process_success(self):
        """Test successful result retrieval from a process worker."""
        component = DoclingInlineComponent()
        ctx = get_context("spawn")
        queue = ctx.Queue()
        expected_result = [{"document": "test_doc", "file_path": "test.pdf"}]

        worker = ctx.Process(target=process_worker_with_result, args=(queue, expected_result))
        worker.start()

        # Wait for result
        result = component._wait_for_result_with_worker_monitoring(queue, worker, timeout=5)

        assert result == expected_result
        worker.join()
        queue.close()

    def test_wait_for_result_thread_dies_without_result(self):
        """Test handling when thread worker dies without sending result."""
        component = DoclingInlineComponent()
        queue = ThreadQueue()

        # Create a thread that exits without putting anything in queue
        def worker_func():
            pass  # Just exit immediately

        worker = threading.Thread(target=worker_func)
        worker.start()

        # Should raise RuntimeError when thread dies without result
        with pytest.raises(RuntimeError, match="Worker thread completed without producing result"):
            component._wait_for_result_with_worker_monitoring(queue, worker, timeout=5)

        worker.join()

    def test_wait_for_result_process_dies_without_result(self):
        """Test handling when process worker dies without sending result."""
        component = DoclingInlineComponent()
        ctx = get_context("spawn")
        queue = ctx.Queue()

        worker = ctx.Process(target=process_worker_no_result, args=(queue,))
        worker.start()

        # Should raise RuntimeError when process dies without result
        with pytest.raises(RuntimeError, match="Worker process crashed unexpectedly"):
            component._wait_for_result_with_worker_monitoring(queue, worker, timeout=5)

        worker.join()
        queue.close()

    def test_wait_for_result_timeout(self):
        """Test timeout handling when worker doesn't produce result in time."""
        component = DoclingInlineComponent()
        queue = ThreadQueue()

        # Create a thread that never puts anything in queue
        def worker_func():
            time.sleep(10)  # Sleep longer than timeout

        worker = threading.Thread(target=worker_func)
        worker.start()

        # Should raise TimeoutError
        with pytest.raises(TimeoutError, match="Worker timed out after 1 seconds"):
            component._wait_for_result_with_worker_monitoring(queue, worker, timeout=1)

        worker.join(timeout=0.1)

    def test_wait_for_result_polls_worker_health(self):
        """Test that the method polls worker health while waiting."""
        component = DoclingInlineComponent()
        queue = ThreadQueue()

        # Create a thread that takes some time to produce result
        def worker_func():
            time.sleep(0.5)
            queue.put(["result"])

        worker = threading.Thread(target=worker_func)
        worker.start()

        # This should poll the worker multiple times before getting result
        start_time = time.time()
        result = component._wait_for_result_with_worker_monitoring(queue, worker, timeout=5)
        elapsed = time.time() - start_time

        assert result == ["result"]
        assert elapsed >= 0.5  # Should wait at least as long as worker takes
        worker.join()


class TestWorkerTermination:
    """Test worker termination functionality (_terminate_worker_gracefully)."""

    def test_terminate_already_dead_worker(self):
        """Test terminating a worker that's already finished."""
        component = DoclingInlineComponent()

        # Create and finish a thread
        def worker_func():
            pass

        worker = threading.Thread(target=worker_func)
        worker.start()
        worker.join()  # Wait for it to finish

        # Should handle gracefully when worker is already dead
        component._terminate_worker_gracefully(worker)
        assert not worker.is_alive()

    def test_terminate_thread_gracefully(self):
        """Test graceful termination of thread worker."""
        component = DoclingInlineComponent()

        # Create a thread that finishes quickly
        def worker_func():
            time.sleep(0.1)

        worker = threading.Thread(target=worker_func)
        worker.start()

        # Terminate should wait for thread to complete
        component._terminate_worker_gracefully(worker, timeout_terminate=2)
        assert not worker.is_alive()

    def test_terminate_thread_timeout_warning(self):
        """Test that a warning is logged when thread doesn't terminate in time."""
        component = DoclingInlineComponent()

        # Create a thread that sleeps longer than timeout
        def worker_func():
            time.sleep(5)

        worker = threading.Thread(target=worker_func, daemon=True)
        worker.start()

        # Mock the log method to capture calls
        with patch.object(component, "log") as mock_log:
            # Terminate with short timeout
            component._terminate_worker_gracefully(worker, timeout_terminate=0.1)

            # Thread should still be alive (can't force-kill threads)
            # Check that warning was logged
            mock_log.assert_called()
            log_messages = " ".join(str(call) for call in mock_log.call_args_list)
            assert "Thread still alive after timeout" in log_messages
            assert "cannot be forcefully terminated" in log_messages

    def test_terminate_process_gracefully(self):
        """Test graceful termination of process worker."""
        component = DoclingInlineComponent()
        ctx = get_context("spawn")

        worker = ctx.Process(target=process_worker_infinite_loop)
        worker.start()

        # Terminate should successfully stop the process
        component._terminate_worker_gracefully(worker, timeout_terminate=2, timeout_kill=1)
        assert not worker.is_alive()

    def test_terminate_process_needs_sigkill(self):
        """Test process termination when SIGTERM is ignored."""
        component = DoclingInlineComponent()

        # Create a process that ignores SIGTERM (via signal handler)
        # In practice, this is hard to test portably, so we'll use a mock
        mock_process = Mock()
        mock_process.is_alive.side_effect = [True, True, False]  # Alive until SIGKILL
        mock_process.terminate = Mock()
        mock_process.kill = Mock()
        mock_process.join = Mock()

        # Mock the log method to capture calls
        with patch.object(component, "log") as mock_log:
            component._terminate_worker_gracefully(mock_process, timeout_terminate=0.1, timeout_kill=0.1)

            # Should have called both terminate and kill
            mock_process.terminate.assert_called_once()
            mock_process.kill.assert_called_once()

            log_messages = " ".join(str(call) for call in mock_log.call_args_list)
            assert "didn't respond to SIGTERM" in log_messages


class TestThreadVsProcessSelection:
    """Test that the correct worker type is selected based on platform."""

    def test_uses_thread_on_macos(self, monkeypatch):
        """Test that threading.Thread is used on macOS platform."""
        # Mock sys.platform to be darwin (macOS)
        monkeypatch.setattr("sys.platform", "darwin")

        component = DoclingInlineComponent()
        component.pic_desc_llm = None  # Ensure it is None to avoid serialization issues

        # Mock the docling imports and dependencies
        with (
            patch("docling.document_converter.DocumentConverter") as mock_converter,
            patch("lfx.components.docling.docling_inline.docling_worker") as mock_worker,
            patch("lfx.components.docling.docling_inline.threading.Thread") as mock_thread,
            patch("lfx.components.docling.docling_inline.get_context") as mock_get_context,
            patch.object(component, "_wait_for_result_with_worker_monitoring") as mock_wait,
            patch.object(component, "_terminate_worker_gracefully") as mock_terminate,
        ):
            # Setup mocks
            mock_converter.return_value = MagicMock()
            mock_thread_instance = MagicMock()
            mock_thread_instance.start = MagicMock()
            mock_thread.return_value = mock_thread_instance
            mock_wait.return_value = []  # Return empty list as result
            mock_terminate.return_value = None

            # Mock queue to return a result
            mock_queue = MagicMock()
            mock_queue.get.return_value = []

            with patch("lfx.components.docling.docling_inline.queue.Queue", return_value=mock_queue):
                # Create mock file
                mock_file = MagicMock()
                mock_file.path = "/tmp/test.pdf"

                # Call process_files
                component.process_files([mock_file])

            # Verify threading.Thread was called (macOS behavior)
            mock_thread.assert_called_once()

            # Verify multiprocessing.get_context was NOT called (not Linux/Windows)
            mock_get_context.assert_not_called()

            # Verify the Thread was created with correct parameters
            call_kwargs = mock_thread.call_args[1]
            assert call_kwargs["target"] == mock_worker
            assert call_kwargs["daemon"] is False
            assert "queue" in call_kwargs["kwargs"]

    def test_uses_process_on_linux(self, monkeypatch):
        """Test that multiprocessing.Process is used on Linux platform."""
        # Mock sys.platform to be linux
        monkeypatch.setattr("sys.platform", "linux")

        component = DoclingInlineComponent()
        component.pic_desc_llm = None

        # Mock the docling imports and dependencies
        with (
            patch("docling.document_converter.DocumentConverter"),
            patch("lfx.components.docling.docling_inline.docling_worker") as mock_worker,
            patch("lfx.components.docling.docling_inline.threading.Thread") as mock_thread,
            patch("lfx.components.docling.docling_inline.get_context") as mock_get_context,
            patch.object(component, "_wait_for_result_with_worker_monitoring") as mock_wait,
            patch.object(component, "_terminate_worker_gracefully") as mock_terminate,
        ):
            # Setup context mock
            mock_ctx = MagicMock()
            mock_get_context.return_value = mock_ctx
            mock_wait.return_value = []
            mock_terminate.return_value = None

            # Setup process mock
            mock_process_instance = MagicMock()
            mock_process_instance.start = MagicMock()
            mock_process_instance.is_alive.return_value = False
            mock_ctx.Process.return_value = mock_process_instance

            # Mock queue to return a result
            mock_queue = MagicMock()
            mock_queue.get.return_value = []
            mock_ctx.Queue.return_value = mock_queue

            # Create mock file
            mock_file = MagicMock()
            mock_file.path = "/tmp/test.pdf"

            # Call process_files
            component.process_files([mock_file])

            # Verify multiprocessing.Process was used (via get_context)
            mock_get_context.assert_called_once_with("spawn")
            mock_ctx.Process.assert_called_once()

            # Verify threading.Thread was NOT called
            mock_thread.assert_not_called()

            # Verify the Process was created with correct parameters
            call_kwargs = mock_ctx.Process.call_args[1]
            assert call_kwargs["target"] == mock_worker
            assert "queue" in call_kwargs["kwargs"]

    def test_uses_process_on_windows(self, monkeypatch):
        """Test that multiprocessing.Process is used on Windows platform."""
        # Mock sys.platform to be win32
        monkeypatch.setattr("sys.platform", "win32")

        component = DoclingInlineComponent()
        component.pic_desc_llm = None

        # Mock the docling imports and dependencies
        with (
            patch("docling.document_converter.DocumentConverter"),
            patch("lfx.components.docling.docling_inline.docling_worker"),
            patch("lfx.components.docling.docling_inline.threading.Thread") as mock_thread,
            patch("lfx.components.docling.docling_inline.get_context") as mock_get_context,
            patch.object(component, "_wait_for_result_with_worker_monitoring") as mock_wait,
            patch.object(component, "_terminate_worker_gracefully") as mock_terminate,
        ):
            # Setup context mock
            mock_ctx = MagicMock()
            mock_get_context.return_value = mock_ctx
            mock_wait.return_value = []
            mock_terminate.return_value = None

            # Setup process mock
            mock_process_instance = MagicMock()
            mock_process_instance.start = MagicMock()
            mock_process_instance.is_alive.return_value = False
            mock_ctx.Process.return_value = mock_process_instance

            # Mock queue to return a result
            mock_queue = MagicMock()
            mock_queue.get.return_value = []
            mock_ctx.Queue.return_value = mock_queue

            # Create mock file
            mock_file = MagicMock()
            mock_file.path = "/tmp/test.pdf"

            # Call process_files
            component.process_files([mock_file])

            # Verify multiprocessing.Process was used (via get_context)
            mock_get_context.assert_called_once_with("spawn")
            mock_ctx.Process.assert_called_once()

            # Verify threading.Thread was NOT called
            mock_thread.assert_not_called()
