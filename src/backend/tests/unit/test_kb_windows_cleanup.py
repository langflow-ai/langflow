"""Tests for Windows-specific Knowledge Base deletion cleanup.

Tests cover both the kb_windows_cleanup module (unit tests)
and the Windows/non-Windows branching in the delete endpoints (integration tests).
"""

import json
import shutil
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def kb_dir(tmp_path):
    """Create a fake KB directory with SQLite files simulating ChromaDB."""
    kb = tmp_path / "test_kb"
    kb.mkdir()
    (kb / "chroma.sqlite3").write_bytes(b"fake-sqlite-data")
    (kb / "chroma.sqlite3-wal").write_bytes(b"wal-data")
    (kb / "chroma.sqlite3-shm").write_bytes(b"shm-data")
    (kb / "embedding_metadata.json").write_text(json.dumps({"id": str(uuid.uuid4())}))
    return kb


@pytest.fixture
def empty_kb_dir(tmp_path):
    """Create a KB directory with no ChromaDB data files."""
    kb = tmp_path / "empty_kb"
    kb.mkdir()
    return kb


# ===========================================================================
# Unit tests for kb_windows_cleanup module
# ===========================================================================


class TestCloseChromaClient:
    """Tests for _close_chroma_client — clears ChromaDB registry and releases handles."""

    @patch("langflow.api.utils.kb_windows_cleanup.time.sleep")
    @patch("langflow.api.utils.kb_windows_cleanup.gc.collect")
    def test_should_clear_registry_when_path_key_exists(self, mock_gc, mock_sleep, tmp_path):
        from langflow.api.utils.kb_windows_cleanup import _close_chroma_client

        fake_registry = {str(tmp_path): "some-system"}
        with patch(
            "langflow.api.utils.kb_windows_cleanup.SharedSystemClient._identifier_to_system",
            fake_registry,
        ):
            _close_chroma_client(tmp_path)
            assert str(tmp_path) not in fake_registry

        mock_gc.assert_called_once()
        mock_sleep.assert_called_once()

    @patch("langflow.api.utils.kb_windows_cleanup.time.sleep")
    @patch("langflow.api.utils.kb_windows_cleanup.gc.collect")
    def test_should_not_raise_when_path_key_missing(self, mock_gc, mock_sleep, tmp_path):
        from langflow.api.utils.kb_windows_cleanup import _close_chroma_client

        fake_registry = {}
        with patch(
            "langflow.api.utils.kb_windows_cleanup.SharedSystemClient._identifier_to_system",
            fake_registry,
        ):
            _close_chroma_client(tmp_path)

        mock_gc.assert_called_once()


class TestTeardownCollection:
    """Tests for _teardown_collection — deletes collection and releases handles."""

    @patch("langflow.api.utils.kb_windows_cleanup._close_chroma_client")
    @patch("langflow.api.utils.kb_windows_cleanup.Chroma")
    @patch("langflow.api.utils.kb_windows_cleanup.chromadb.PersistentClient")
    def test_should_delete_collection_when_chroma_data_exists(
        self, mock_client_cls, mock_chroma_cls, mock_close, kb_dir
    ):
        from langflow.api.utils.kb_windows_cleanup import _teardown_collection

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_chroma = MagicMock()
        mock_chroma_cls.return_value = mock_chroma

        with patch(
            "langflow.api.utils.kb_windows_cleanup.SharedSystemClient._identifier_to_system",
            {},
        ):
            _teardown_collection(kb_dir, "test_kb")

        mock_chroma.delete_collection.assert_called_once()
        mock_close.assert_called_once_with(kb_dir)

    @patch("langflow.api.utils.kb_windows_cleanup._close_chroma_client")
    def test_should_skip_when_no_chroma_data(self, mock_close, empty_kb_dir):
        from langflow.api.utils.kb_windows_cleanup import _teardown_collection

        _teardown_collection(empty_kb_dir, "empty_kb")
        mock_close.assert_not_called()

    @patch("langflow.api.utils.kb_windows_cleanup._close_chroma_client")
    @patch("langflow.api.utils.kb_windows_cleanup.chromadb.PersistentClient")
    def test_should_not_raise_when_client_creation_fails(self, mock_client_cls, mock_close, kb_dir):
        from langflow.api.utils.kb_windows_cleanup import _teardown_collection

        mock_client_cls.side_effect = OSError("Cannot open database")

        with patch(
            "langflow.api.utils.kb_windows_cleanup.SharedSystemClient._identifier_to_system",
            {},
        ):
            _teardown_collection(kb_dir, "test_kb")

        mock_close.assert_called_once_with(kb_dir)


class TestRemoveSqliteLockFiles:
    """Tests for _remove_sqlite_lock_files — removes WAL, SHM, journal files."""

    def test_should_remove_all_lock_files(self, kb_dir):
        from langflow.api.utils.kb_windows_cleanup import _remove_sqlite_lock_files

        (kb_dir / "chroma.sqlite3-journal").write_bytes(b"journal")
        assert (kb_dir / "chroma.sqlite3-wal").exists()
        assert (kb_dir / "chroma.sqlite3-shm").exists()

        _remove_sqlite_lock_files(kb_dir)

        assert not (kb_dir / "chroma.sqlite3-wal").exists()
        assert not (kb_dir / "chroma.sqlite3-shm").exists()
        assert not (kb_dir / "chroma.sqlite3-journal").exists()
        # Main sqlite file should be untouched
        assert (kb_dir / "chroma.sqlite3").exists()

    def test_should_not_raise_when_no_lock_files(self, empty_kb_dir):
        from langflow.api.utils.kb_windows_cleanup import _remove_sqlite_lock_files

        _remove_sqlite_lock_files(empty_kb_dir)

    def test_should_handle_permission_error_gracefully(self, kb_dir):
        from langflow.api.utils.kb_windows_cleanup import _remove_sqlite_lock_files

        with patch.object(Path, "unlink", side_effect=OSError("Permission denied")):
            _remove_sqlite_lock_files(kb_dir)
            # Should not raise; lock files may still exist


class TestTruncateSqliteFiles:
    """Tests for _truncate_sqlite_files — truncates .sqlite3 files."""

    def test_should_truncate_sqlite_files_to_zero(self, kb_dir):
        from langflow.api.utils.kb_windows_cleanup import _truncate_sqlite_files

        assert (kb_dir / "chroma.sqlite3").stat().st_size > 0

        _truncate_sqlite_files(kb_dir)

        assert (kb_dir / "chroma.sqlite3").stat().st_size == 0

    def test_should_not_raise_when_no_sqlite_files(self, empty_kb_dir):
        from langflow.api.utils.kb_windows_cleanup import _truncate_sqlite_files

        _truncate_sqlite_files(empty_kb_dir)

    def test_should_handle_locked_file_gracefully(self, kb_dir):
        from langflow.api.utils.kb_windows_cleanup import _truncate_sqlite_files

        with patch("builtins.open", side_effect=OSError("File is locked")):
            _truncate_sqlite_files(kb_dir)


class TestForceDeleteKb:
    """Tests for force_delete_kb — the main Windows deletion function."""

    @patch("langflow.api.utils.kb_windows_cleanup._teardown_collection")
    @patch("langflow.api.utils.kb_windows_cleanup.time.sleep")
    def test_should_return_true_when_path_does_not_exist(self, mock_sleep, mock_teardown, tmp_path):
        from langflow.api.utils.kb_windows_cleanup import force_delete_kb

        non_existent = tmp_path / "does_not_exist"
        result = force_delete_kb(non_existent, "ghost_kb")

        assert result is True
        mock_teardown.assert_not_called()

    @patch("langflow.api.utils.kb_windows_cleanup._teardown_collection")
    @patch("langflow.api.utils.kb_windows_cleanup.time.sleep")
    def test_should_delete_directory_on_first_attempt(self, mock_sleep, mock_teardown, kb_dir):
        from langflow.api.utils.kb_windows_cleanup import force_delete_kb

        result = force_delete_kb(kb_dir, "test_kb")

        assert result is True
        assert not kb_dir.exists()
        mock_teardown.assert_called_once_with(kb_dir, "test_kb")

    @patch("langflow.api.utils.kb_windows_cleanup._teardown_collection")
    @patch("langflow.api.utils.kb_windows_cleanup.time.sleep")
    def test_should_retry_and_succeed_on_second_attempt(self, mock_sleep, mock_teardown, kb_dir):
        from langflow.api.utils.kb_windows_cleanup import force_delete_kb

        original_rmtree = shutil.rmtree
        call_count = 0

        def rmtree_fails_once(path, ignore_errors=False):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OSError("[WinError 32] File in use")
            original_rmtree(path, ignore_errors=ignore_errors)

        with patch("langflow.api.utils.kb_windows_cleanup.shutil.rmtree", side_effect=rmtree_fails_once):
            result = force_delete_kb(kb_dir, "test_kb")

        assert result is True
        assert call_count == 2

    @patch("langflow.api.utils.kb_windows_cleanup._teardown_collection")
    @patch("langflow.api.utils.kb_windows_cleanup.time.sleep")
    def test_should_rename_as_fallback_when_all_retries_fail(self, mock_sleep, mock_teardown, kb_dir):
        from langflow.api.utils.kb_windows_cleanup import force_delete_kb

        with patch(
            "langflow.api.utils.kb_windows_cleanup.shutil.rmtree",
            side_effect=OSError("[WinError 32] File in use"),
        ):
            result = force_delete_kb(kb_dir, "test_kb")

        assert result is True
        # Original path should be gone (renamed)
        assert not kb_dir.exists()
        # A renamed directory should exist
        renamed_dirs = [p for p in kb_dir.parent.iterdir() if p.name.startswith(".deleted_test_kb_")]
        assert len(renamed_dirs) == 1

    @patch("langflow.api.utils.kb_windows_cleanup._teardown_collection")
    @patch("langflow.api.utils.kb_windows_cleanup.time.sleep")
    def test_should_return_false_when_all_strategies_fail(self, mock_sleep, mock_teardown, kb_dir):
        from langflow.api.utils.kb_windows_cleanup import force_delete_kb

        with (
            patch(
                "langflow.api.utils.kb_windows_cleanup.shutil.rmtree",
                side_effect=OSError("[WinError 32] File in use"),
            ),
            patch.object(Path, "rename", side_effect=OSError("Cannot rename")),
        ):
            result = force_delete_kb(kb_dir, "test_kb")

        assert result is False
        assert kb_dir.exists()

    @patch("langflow.api.utils.kb_windows_cleanup._teardown_collection")
    @patch("langflow.api.utils.kb_windows_cleanup.time.sleep")
    def test_should_use_exponential_backoff_on_retries(self, mock_sleep, mock_teardown, kb_dir):
        from langflow.api.utils.kb_windows_cleanup import force_delete_kb

        real_rmtree = shutil.rmtree
        call_count = 0

        def rmtree_fails_three_times(path, ignore_errors=False):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise OSError("[WinError 32] File in use")
            real_rmtree(path, ignore_errors=ignore_errors)

        with patch("langflow.api.utils.kb_windows_cleanup.shutil.rmtree", side_effect=rmtree_fails_three_times):
            result = force_delete_kb(kb_dir, "test_kb")

        assert result is True
        # Backoff sleeps: attempt 1 (1.0s), attempt 2 (2.0s), attempt 3 (4.0s)
        sleep_values = [call.args[0] for call in mock_sleep.call_args_list]
        assert sleep_values == [1.0, 2.0, 4.0]


# ===========================================================================
# Integration tests: delete endpoints with Windows/non-Windows branching
# ===========================================================================


class TestDeleteEndpointPlatformBranching:
    """Tests that delete endpoints use the correct path based on platform."""

    @patch("langflow.api.v1.knowledge_bases.platform.system", return_value="Darwin")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.teardown_storage")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_delete_should_use_standard_path_on_macos(
        self, mock_root, mock_teardown, mock_platform, client, logged_in_headers, tmp_path
    ):
        mock_root.return_value = tmp_path
        (tmp_path / "activeuser" / "My_KB").mkdir(parents=True)

        response = await client.delete("api/v1/knowledge_bases/My_KB", headers=logged_in_headers)

        assert response.status_code == 200
        mock_teardown.assert_called_once()

    @patch("langflow.api.v1.knowledge_bases.platform.system", return_value="Linux")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.teardown_storage")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_delete_should_use_standard_path_on_linux(
        self, mock_root, mock_teardown, mock_platform, client, logged_in_headers, tmp_path
    ):
        mock_root.return_value = tmp_path
        (tmp_path / "activeuser" / "My_KB").mkdir(parents=True)

        response = await client.delete("api/v1/knowledge_bases/My_KB", headers=logged_in_headers)

        assert response.status_code == 200
        mock_teardown.assert_called_once()

    @patch("langflow.api.v1.knowledge_bases.platform.system", return_value="Windows")
    @patch("langflow.api.utils.kb_windows_cleanup.force_delete_kb", return_value=True)
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.teardown_storage")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_delete_should_use_windows_path_on_windows(
        self, mock_root, mock_teardown, mock_force_delete, mock_platform, client, logged_in_headers, tmp_path
    ):
        mock_root.return_value = tmp_path
        (tmp_path / "activeuser" / "My_KB").mkdir(parents=True)

        response = await client.delete("api/v1/knowledge_bases/My_KB", headers=logged_in_headers)

        assert response.status_code == 200
        mock_force_delete.assert_called_once()
        # Standard teardown should NOT be called on Windows
        mock_teardown.assert_not_called()

    @patch("langflow.api.v1.knowledge_bases.platform.system", return_value="Windows")
    @patch("langflow.api.utils.kb_windows_cleanup.force_delete_kb", return_value=False)
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_delete_should_return_500_when_windows_deletion_fails(
        self, mock_root, mock_force_delete, mock_platform, client, logged_in_headers, tmp_path
    ):
        mock_root.return_value = tmp_path
        (tmp_path / "activeuser" / "My_KB").mkdir(parents=True)

        response = await client.delete("api/v1/knowledge_bases/My_KB", headers=logged_in_headers)

        assert response.status_code == 500
        assert "may be in use" in response.json()["detail"]


class TestBulkDeleteEndpointPlatformBranching:
    """Tests that bulk delete endpoint uses the correct path based on platform."""

    @patch("langflow.api.v1.knowledge_bases.platform.system", return_value="Darwin")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.teardown_storage")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_bulk_delete_should_use_standard_path_on_macos(
        self, mock_root, mock_teardown, mock_platform, client, logged_in_headers, tmp_path
    ):
        mock_root.return_value = tmp_path
        kb_user_path = tmp_path / "activeuser"
        kb_user_path.mkdir(parents=True)
        (kb_user_path / "KB1").mkdir()
        (kb_user_path / "KB2").mkdir()

        response = await client.request(
            "DELETE",
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={"kb_names": ["KB1", "KB2"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 2
        assert mock_teardown.call_count == 2

    @patch("langflow.api.v1.knowledge_bases.platform.system", return_value="Windows")
    @patch("langflow.api.utils.kb_windows_cleanup.force_delete_kb", return_value=True)
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.teardown_storage")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_bulk_delete_should_use_windows_path_on_windows(
        self, mock_root, mock_teardown, mock_force_delete, mock_platform, client, logged_in_headers, tmp_path
    ):
        mock_root.return_value = tmp_path
        kb_user_path = tmp_path / "activeuser"
        kb_user_path.mkdir(parents=True)
        (kb_user_path / "KB1").mkdir()
        (kb_user_path / "KB2").mkdir()

        response = await client.request(
            "DELETE",
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={"kb_names": ["KB1", "KB2"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 2
        assert mock_force_delete.call_count == 2
        mock_teardown.assert_not_called()

    @patch("langflow.api.v1.knowledge_bases.platform.system", return_value="Windows")
    @patch("langflow.api.utils.kb_windows_cleanup.force_delete_kb")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_bulk_delete_should_handle_partial_windows_failure(
        self, mock_root, mock_force_delete, mock_platform, client, logged_in_headers, tmp_path
    ):
        mock_root.return_value = tmp_path
        kb_user_path = tmp_path / "activeuser"
        kb_user_path.mkdir(parents=True)
        (kb_user_path / "KB1").mkdir()
        (kb_user_path / "KB2").mkdir()

        # KB1 succeeds, KB2 fails but path is gone
        def side_effect(path, name):
            if name == "KB1":
                shutil.rmtree(path)
                return True
            return False

        mock_force_delete.side_effect = side_effect

        response = await client.request(
            "DELETE",
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={"kb_names": ["KB1", "KB2"]},
        )

        assert response.status_code == 200
        data = response.json()
        # KB1 deleted, KB2 failed but path still exists so not counted
        assert data["deleted_count"] == 1

    @patch("langflow.api.v1.knowledge_bases.platform.system", return_value="Darwin")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.teardown_storage")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_bulk_delete_should_report_not_found_kbs(
        self, mock_root, mock_teardown, mock_platform, client, logged_in_headers, tmp_path
    ):
        mock_root.return_value = tmp_path
        kb_user_path = tmp_path / "activeuser"
        kb_user_path.mkdir(parents=True)
        (kb_user_path / "KB1").mkdir()

        response = await client.request(
            "DELETE",
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={"kb_names": ["KB1", "Ghost"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 1
        assert "Ghost" in data["not_found"]
