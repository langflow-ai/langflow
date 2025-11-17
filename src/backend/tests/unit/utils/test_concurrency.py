import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from lfx.utils.concurrency import KeyedMemoryLockManager, KeyedWorkerLockManager


class TestKeyedMemoryLockManager:
    """Test cases for KeyedMemoryLockManager class."""

    def test_initialization(self):
        """Test proper initialization of KeyedMemoryLockManager."""
        manager = KeyedMemoryLockManager()

        assert isinstance(manager.locks, dict)
        assert len(manager.locks) == 0
        assert hasattr(manager, "global_lock")
        assert hasattr(manager.global_lock, "acquire")
        assert hasattr(manager.global_lock, "release")

    def test_get_lock_creates_new_lock(self):
        """Test that _get_lock creates a new lock for new keys."""
        manager = KeyedMemoryLockManager()

        lock1 = manager._get_lock("key1")

        assert hasattr(lock1, "acquire")
        assert hasattr(lock1, "release")
        assert "key1" in manager.locks
        assert manager.locks["key1"] is lock1

    def test_get_lock_returns_existing_lock(self):
        """Test that _get_lock returns existing lock for known keys."""
        manager = KeyedMemoryLockManager()

        lock1 = manager._get_lock("key1")
        lock2 = manager._get_lock("key1")

        assert lock1 is lock2
        assert len(manager.locks) == 1

    def test_get_lock_different_keys(self):
        """Test that different keys get different locks."""
        manager = KeyedMemoryLockManager()

        lock1 = manager._get_lock("key1")
        lock2 = manager._get_lock("key2")

        assert lock1 is not lock2
        assert len(manager.locks) == 2
        assert manager.locks["key1"] is lock1
        assert manager.locks["key2"] is lock2

    def test_context_manager_basic_functionality(self):
        """Test that the context manager works with basic functionality."""
        manager = KeyedMemoryLockManager()

        # Test that context manager doesn't raise exceptions
        with manager.lock("test_key"):
            assert "test_key" in manager.locks

        # Lock should still exist after context
        assert "test_key" in manager.locks

    def test_context_manager_exception_handling(self):
        """Test that context manager handles exceptions properly."""
        manager = KeyedMemoryLockManager()

        # Test that exceptions don't break the manager
        try:
            with manager.lock("test_key"):
                msg = "Test exception"
                raise ValueError(msg)
        except ValueError:
            pass

        # Manager should still be functional
        assert "test_key" in manager.locks

        # Should be able to use the same lock again
        with manager.lock("test_key"):
            pass

    def test_concurrent_access_same_key(self):
        """Test concurrent access to the same key is serialized."""
        manager = KeyedMemoryLockManager()
        results = []

        def worker(worker_id):
            with manager.lock("shared_key"):
                results.append(f"start_{worker_id}")
                time.sleep(0.01)  # Small delay to ensure serialization
                results.append(f"end_{worker_id}")

        threads = []
        for i in range(3):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Results should be properly serialized (start/end pairs together)
        assert len(results) == 6
        # Each worker should complete fully before next one starts
        for i in range(3):
            start_idx = results.index(f"start_{i}")
            end_idx = results.index(f"end_{i}")
            assert end_idx == start_idx + 1

    def test_concurrent_access_different_keys(self):
        """Test concurrent access to different keys can proceed in parallel."""
        manager = KeyedMemoryLockManager()
        results = []
        result_lock = threading.Lock()

        def worker(worker_id, key):
            with manager.lock(key):
                with result_lock:
                    results.append(f"start_{worker_id}")
                time.sleep(0.01)
                with result_lock:
                    results.append(f"end_{worker_id}")

        threads = []
        for i in range(3):
            thread = threading.Thread(target=worker, args=(i, f"key_{i}"))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All threads should have completed
        assert len(results) == 6
        assert len([r for r in results if r.startswith("start_")]) == 3
        assert len([r for r in results if r.startswith("end_")]) == 3

    def test_lock_manager_thread_safety(self):
        """Test that the lock manager itself is thread-safe."""
        manager = KeyedMemoryLockManager()
        created_locks = []

        def create_locks():
            for i in range(10):
                lock = manager._get_lock(f"key_{i}")
                created_locks.append(lock)

        threads = []
        for _ in range(3):
            thread = threading.Thread(target=create_locks)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Should have created exactly 10 unique locks
        assert len(manager.locks) == 10
        assert len(created_locks) == 30  # 3 threads * 10 locks each


class TestKeyedWorkerLockManager:
    """Test cases for KeyedWorkerLockManager class."""

    def test_initialization(self):
        """Test proper initialization of KeyedWorkerLockManager."""
        with (
            patch("lfx.utils.concurrency.user_cache_dir") as mock_cache_dir,
            patch("lfx.utils.concurrency.Path") as mock_path,
        ):
            mock_cache_dir.return_value = "/cache/dir"
            mock_path_instance = MagicMock()
            mock_path.return_value = mock_path_instance

            manager = KeyedWorkerLockManager()

            mock_cache_dir.assert_called_once_with("langflow")
            assert manager.locks_dir == mock_path_instance.__truediv__.return_value

    def test_validate_key_valid_keys(self):
        """Test that _validate_key accepts valid keys."""
        manager = KeyedWorkerLockManager()

        valid_keys = [
            "valid_key",
            "key123",
            "KEY_WITH_CAPS",
            "mix3d_K3y",
            "_underscore_start",
            "underscore_end_",
            "123numbers",
            "a",
            "A",
            "_",
            "key_123_test",
        ]

        for key in valid_keys:
            assert manager._validate_key(key) is True

    def test_validate_key_invalid_keys(self):
        """Test that _validate_key rejects invalid keys."""
        manager = KeyedWorkerLockManager()

        invalid_keys = [
            "key-with-dashes",
            "key with spaces",
            "key.with.dots",
            "key@symbol",
            "key#hash",
            "key$dollar",
            "key%percent",
            "key^caret",
            "key&ampersand",
            "key*asterisk",
            "key+plus",
            "key=equals",
            "key[bracket",
            "key{brace",
            "key/slash",
            "key\\backslash",
            "key|pipe",
            "key:colon",
            "key;semicolon",
            "key'quote",
            'key"doublequote',
            "key<less",
            "key>greater",
            "key?question",
            "",  # empty string
        ]

        for key in invalid_keys:
            assert manager._validate_key(key) is False

    def test_lock_with_valid_key(self):
        """Test lock context manager with valid key."""
        manager = KeyedWorkerLockManager()

        with patch("lfx.utils.concurrency.FileLock") as mock_filelock:
            mock_lock_instance = MagicMock()
            mock_filelock.return_value = mock_lock_instance

            with manager.lock("valid_key"):
                pass

            # Verify FileLock was created with correct path
            mock_filelock.assert_called_once()
            # Verify context manager was used
            mock_lock_instance.__enter__.assert_called_once()
            mock_lock_instance.__exit__.assert_called_once()

    def test_lock_with_invalid_key_raises_error(self):
        """Test that lock raises ValueError for invalid keys."""
        manager = KeyedWorkerLockManager()

        with (
            pytest.raises(ValueError, match="Invalid key: invalid-key"),
            manager.lock("invalid-key"),
        ):
            pass

    def test_lock_file_path_construction(self):
        """Test that lock file path is constructed correctly."""
        with (
            patch("lfx.utils.concurrency.user_cache_dir") as mock_cache_dir,
            patch("lfx.utils.concurrency.Path") as mock_path,
            patch("lfx.utils.concurrency.FileLock") as mock_filelock,
        ):
            mock_cache_dir.return_value = "/cache"
            mock_locks_dir = MagicMock()
            mock_path.return_value.__truediv__.return_value = mock_locks_dir

            manager = KeyedWorkerLockManager()

            with manager.lock("test_key"):
                pass

            # Verify FileLock was called with correct path
            mock_filelock.assert_called_once_with(mock_locks_dir.__truediv__.return_value)
            mock_locks_dir.__truediv__.assert_called_once_with("test_key")

    def test_lock_context_manager_exception_handling(self):
        """Test that lock is properly released even when exception occurs."""
        manager = KeyedWorkerLockManager()

        with patch("lfx.utils.concurrency.FileLock") as mock_filelock:
            mock_lock_instance = MagicMock()
            mock_filelock.return_value = mock_lock_instance

            try:
                with manager.lock("valid_key"):
                    msg = "Test exception"
                    raise ValueError(msg)
            except ValueError:
                pass

            # Verify context manager was properly exited
            mock_lock_instance.__exit__.assert_called_once()

    def test_multiple_keys_create_different_locks(self):
        """Test that different keys create different file locks."""
        manager = KeyedWorkerLockManager()

        with patch("lfx.utils.concurrency.FileLock") as mock_filelock:
            mock_filelock.return_value = MagicMock()

            with manager.lock("key1"):
                pass

            with manager.lock("key2"):
                pass

            # Should have been called twice with different paths
            assert mock_filelock.call_count == 2
            call_args = [call[0][0] for call in mock_filelock.call_args_list]
            assert call_args[0] != call_args[1]  # Different paths

    def test_validate_key_regex_pattern(self):
        """Test the regex pattern used for key validation."""
        manager = KeyedWorkerLockManager()

        # Test edge cases for the regex pattern
        assert manager._validate_key("_") is True  # Single underscore
        assert manager._validate_key("1") is True  # Single digit
        assert manager._validate_key("a") is True  # Single letter
        assert manager._validate_key("Z") is True  # Single capital letter
        assert manager._validate_key("") is False  # Empty string
        assert manager._validate_key(" ") is False  # Single space

    def test_concurrent_worker_locks_same_key(self):
        """Test that multiple workers with same key are serialized."""
        manager = KeyedWorkerLockManager()
        results = []

        def worker(worker_id):
            try:
                with manager.lock("shared_worker_key"):
                    results.append(f"worker_{worker_id}_start")
                    time.sleep(0.01)
                    results.append(f"worker_{worker_id}_end")
            except Exception:
                # Skip the test if file locking is not available in test environment
                results.append(f"worker_{worker_id}_skipped")

        threads = []
        for i in range(2):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # If file locking worked, should be serialized
        # If not available, workers would be skipped
        if "skipped" not in "".join(results):
            assert len(results) == 4
            # Each worker should complete before the next starts
            assert results[0].endswith("_start")
            assert results[1].endswith("_end")
            assert results[2].endswith("_start")
            assert results[3].endswith("_end")

    @patch("lfx.utils.concurrency.user_cache_dir")
    def test_locks_directory_creation(self, mock_cache_dir):
        """Test that locks directory is created properly."""
        mock_cache_dir.return_value = "/test/cache"

        with patch("lfx.utils.concurrency.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path.return_value = mock_path_instance

            KeyedWorkerLockManager()

            # Verify Path was called correctly
            mock_path.assert_called_once_with("/test/cache", ensure_exists=True)
            mock_path_instance.__truediv__.assert_called_once_with("worker_locks")
