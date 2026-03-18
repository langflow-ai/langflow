"""Tests for unified Knowledge Base deletion and resource cleanup.

Covers the delete_storage method, release_chroma_resources, private helpers
(_remove_sqlite_lock_files, _truncate_sqlite_files), and the delete endpoints.
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
# Unit tests: _remove_sqlite_lock_files
# ===========================================================================


class TestRemoveSqliteLockFiles:
    """Tests for _remove_sqlite_lock_files — removes WAL, SHM, journal files."""

    def test_should_remove_all_lock_files(self, kb_dir):
        from langflow.api.utils.kb_helpers import _remove_sqlite_lock_files

        (kb_dir / "chroma.sqlite3-journal").write_bytes(b"journal")
        assert (kb_dir / "chroma.sqlite3-wal").exists()
        assert (kb_dir / "chroma.sqlite3-shm").exists()

        _remove_sqlite_lock_files(kb_dir)

        assert not (kb_dir / "chroma.sqlite3-wal").exists()
        assert not (kb_dir / "chroma.sqlite3-shm").exists()
        assert not (kb_dir / "chroma.sqlite3-journal").exists()
        assert (kb_dir / "chroma.sqlite3").exists()

    def test_should_not_raise_when_no_lock_files(self, empty_kb_dir):
        from langflow.api.utils.kb_helpers import _remove_sqlite_lock_files

        _remove_sqlite_lock_files(empty_kb_dir)

    def test_should_handle_permission_error_gracefully(self, kb_dir):
        from langflow.api.utils.kb_helpers import _remove_sqlite_lock_files

        with patch.object(Path, "unlink", side_effect=OSError("Permission denied")):
            _remove_sqlite_lock_files(kb_dir)


# ===========================================================================
# Unit tests: _truncate_sqlite_files
# ===========================================================================


class TestTruncateSqliteFiles:
    """Tests for _truncate_sqlite_files — truncates .sqlite3 files."""

    def test_should_truncate_sqlite_files_to_zero(self, kb_dir):
        from langflow.api.utils.kb_helpers import _truncate_sqlite_files

        assert (kb_dir / "chroma.sqlite3").stat().st_size > 0

        _truncate_sqlite_files(kb_dir)

        assert (kb_dir / "chroma.sqlite3").stat().st_size == 0

    def test_should_not_raise_when_no_sqlite_files(self, empty_kb_dir):
        from langflow.api.utils.kb_helpers import _truncate_sqlite_files

        _truncate_sqlite_files(empty_kb_dir)

    def test_should_handle_locked_file_gracefully(self, kb_dir):
        from langflow.api.utils.kb_helpers import _truncate_sqlite_files

        with patch("builtins.open", side_effect=OSError("File is locked")):
            _truncate_sqlite_files(kb_dir)


# ===========================================================================
# Unit tests: KBStorageHelper.release_chroma_resources
# ===========================================================================


class TestReleaseChromaResources:
    """Tests for release_chroma_resources — clears registry and forces GC."""

    def test_should_clear_registry_entry_for_path(self, kb_dir):
        from chromadb.api.shared_system_client import SharedSystemClient
        from langflow.api.utils.kb_helpers import KBStorageHelper

        path_key = str(kb_dir)
        SharedSystemClient._identifier_to_system[path_key] = MagicMock()

        KBStorageHelper.release_chroma_resources(kb_dir)

        assert path_key not in SharedSystemClient._identifier_to_system

    def test_should_not_raise_when_path_not_in_registry(self, tmp_path):
        from langflow.api.utils.kb_helpers import KBStorageHelper

        KBStorageHelper.release_chroma_resources(tmp_path / "nonexistent")

    @patch("langflow.api.utils.kb_helpers.gc.collect")
    def test_should_call_gc_collect(self, mock_gc, tmp_path):
        from langflow.api.utils.kb_helpers import KBStorageHelper

        KBStorageHelper.release_chroma_resources(tmp_path)

        mock_gc.assert_called_once()


# ===========================================================================
# Unit tests: KBStorageHelper.delete_storage
# ===========================================================================


class TestDeleteStorage:
    """Tests for KBStorageHelper.delete_storage — unified deletion with retry."""

    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.get_fresh_chroma_client", new=MagicMock())
    @patch("langflow.api.utils.kb_helpers.Chroma", new=MagicMock())
    @patch("langflow.api.utils.kb_helpers.time.sleep", new=MagicMock())
    def test_should_return_true_when_path_does_not_exist(self, tmp_path):
        from langflow.api.utils.kb_helpers import KBStorageHelper

        non_existent = tmp_path / "does_not_exist"
        result = KBStorageHelper.delete_storage(non_existent, "ghost_kb")

        assert result is True

    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.get_fresh_chroma_client", new=MagicMock())
    @patch("langflow.api.utils.kb_helpers.Chroma", new=MagicMock())
    @patch("langflow.api.utils.kb_helpers.time.sleep", new=MagicMock())
    def test_should_delete_directory_on_first_attempt(self, kb_dir):
        from langflow.api.utils.kb_helpers import KBStorageHelper

        result = KBStorageHelper.delete_storage(kb_dir, "test_kb")

        assert result is True
        assert not kb_dir.exists()

    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.get_fresh_chroma_client", new=MagicMock())
    @patch("langflow.api.utils.kb_helpers.Chroma", new=MagicMock())
    @patch("langflow.api.utils.kb_helpers.time.sleep", new=MagicMock())
    def test_should_retry_and_succeed_on_second_attempt(self, kb_dir):
        from langflow.api.utils.kb_helpers import KBStorageHelper

        original_rmtree = shutil.rmtree
        call_count = 0

        def rmtree_fails_once(path, *, ignore_errors=False):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                msg = "[WinError 32] File in use"
                raise OSError(msg)
            original_rmtree(path, ignore_errors=ignore_errors)

        with patch("langflow.api.utils.kb_helpers.shutil.rmtree", side_effect=rmtree_fails_once):
            result = KBStorageHelper.delete_storage(kb_dir, "test_kb")

        assert result is True
        assert call_count == 2

    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.get_fresh_chroma_client", new=MagicMock())
    @patch("langflow.api.utils.kb_helpers.Chroma", new=MagicMock())
    @patch("langflow.api.utils.kb_helpers.time.sleep", new=MagicMock())
    def test_should_rename_as_fallback_when_all_retries_fail(self, kb_dir):
        from langflow.api.utils.kb_helpers import KBStorageHelper

        with patch(
            "langflow.api.utils.kb_helpers.shutil.rmtree",
            side_effect=OSError("[WinError 32] File in use"),
        ):
            result = KBStorageHelper.delete_storage(kb_dir, "test_kb")

        assert result is True
        assert not kb_dir.exists()
        renamed_dirs = [p for p in kb_dir.parent.iterdir() if p.name.startswith(".deleted_test_kb_")]
        assert len(renamed_dirs) == 1

    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.get_fresh_chroma_client", new=MagicMock())
    @patch("langflow.api.utils.kb_helpers.Chroma", new=MagicMock())
    @patch("langflow.api.utils.kb_helpers.time.sleep", new=MagicMock())
    def test_should_return_false_when_all_strategies_fail(self, kb_dir):
        from langflow.api.utils.kb_helpers import KBStorageHelper

        with (
            patch(
                "langflow.api.utils.kb_helpers.shutil.rmtree",
                side_effect=OSError("[WinError 32] File in use"),
            ),
            patch.object(Path, "rename", side_effect=OSError("Cannot rename")),
        ):
            result = KBStorageHelper.delete_storage(kb_dir, "test_kb")

        assert result is False
        assert kb_dir.exists()

    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.get_fresh_chroma_client", new=MagicMock())
    @patch("langflow.api.utils.kb_helpers.Chroma", new=MagicMock())
    @patch("langflow.api.utils.kb_helpers.time.sleep")
    def test_should_use_exponential_backoff_on_retries(self, mock_sleep, kb_dir):
        from langflow.api.utils.kb_helpers import KBStorageHelper

        real_rmtree = shutil.rmtree
        call_count = 0

        def rmtree_fails_three_times(path, *, ignore_errors=False):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                msg = "[WinError 32] File in use"
                raise OSError(msg)
            real_rmtree(path, ignore_errors=ignore_errors)

        with patch("langflow.api.utils.kb_helpers.shutil.rmtree", side_effect=rmtree_fails_three_times):
            result = KBStorageHelper.delete_storage(kb_dir, "test_kb")

        assert result is True
        sleep_values = [call.args[0] for call in mock_sleep.call_args_list]
        assert sleep_values == [1.0, 2.0, 4.0]

    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.get_fresh_chroma_client")
    @patch("langflow.api.utils.kb_helpers.Chroma")
    @patch("langflow.api.utils.kb_helpers.time.sleep", new=MagicMock())
    def test_should_teardown_collection_before_deletion(self, mock_chroma_cls, mock_client_cls, kb_dir):
        from langflow.api.utils.kb_helpers import KBStorageHelper

        mock_chroma = MagicMock()
        mock_chroma_cls.return_value = mock_chroma
        mock_client_cls.return_value = MagicMock()

        KBStorageHelper.delete_storage(kb_dir, "test_kb")

        mock_chroma.delete_collection.assert_called_once()
        assert not kb_dir.exists()

    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.get_fresh_chroma_client")
    @patch("langflow.api.utils.kb_helpers.time.sleep", new=MagicMock())
    def test_should_not_fail_when_teardown_raises(self, mock_client_cls, kb_dir):
        from langflow.api.utils.kb_helpers import KBStorageHelper

        mock_client_cls.side_effect = OSError("Cannot open database")

        result = KBStorageHelper.delete_storage(kb_dir, "test_kb")

        assert result is True
        assert not kb_dir.exists()

    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.get_fresh_chroma_client", new=MagicMock())
    @patch("langflow.api.utils.kb_helpers.Chroma", new=MagicMock())
    @patch("langflow.api.utils.kb_helpers.time.sleep", new=MagicMock())
    def test_should_skip_teardown_when_no_chroma_data(self, empty_kb_dir):
        from langflow.api.utils.kb_helpers import KBStorageHelper

        result = KBStorageHelper.delete_storage(empty_kb_dir, "empty_kb")

        assert result is True
        assert not empty_kb_dir.exists()


# ===========================================================================
# Integration tests: delete endpoints using unified delete_storage
# ===========================================================================


class TestDeleteEndpoint:
    """Tests that delete endpoint uses KBStorageHelper.delete_storage."""

    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.get_fresh_chroma_client", new=MagicMock())
    @patch("langflow.api.utils.kb_helpers.Chroma", new=MagicMock())
    @patch("langflow.api.utils.kb_helpers.time.sleep", new=MagicMock())
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_should_delete_kb_successfully(self, mock_root, client, logged_in_headers, tmp_path):
        mock_root.return_value = tmp_path
        (tmp_path / "activeuser" / "My_KB").mkdir(parents=True)

        response = await client.delete("api/v1/knowledge_bases/My_KB", headers=logged_in_headers)

        assert response.status_code == 200

    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.delete_storage", return_value=False)
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_should_return_500_when_deletion_fails(
        self, mock_root, mock_delete, client, logged_in_headers, tmp_path
    ):
        mock_root.return_value = tmp_path
        (tmp_path / "activeuser" / "My_KB").mkdir(parents=True)

        response = await client.delete("api/v1/knowledge_bases/My_KB", headers=logged_in_headers)

        assert response.status_code == 500
        assert "may be in use" in response.json()["detail"]
        mock_delete.assert_called_once()

    async def test_should_return_404_when_kb_not_found(self, client, logged_in_headers):
        response = await client.delete("api/v1/knowledge_bases/NonExistent_KB", headers=logged_in_headers)

        assert response.status_code == 404


class TestBulkDeleteEndpoint:
    """Tests that bulk delete endpoint uses KBStorageHelper.delete_storage."""

    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.get_fresh_chroma_client", new=MagicMock())
    @patch("langflow.api.utils.kb_helpers.Chroma", new=MagicMock())
    @patch("langflow.api.utils.kb_helpers.time.sleep", new=MagicMock())
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_should_delete_multiple_kbs(self, mock_root, client, logged_in_headers, tmp_path):
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

    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.delete_storage")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_should_handle_partial_failure(self, mock_root, mock_delete, client, logged_in_headers, tmp_path):
        mock_root.return_value = tmp_path
        kb_user_path = tmp_path / "activeuser"
        kb_user_path.mkdir(parents=True)
        (kb_user_path / "KB1").mkdir()
        (kb_user_path / "KB2").mkdir()

        mock_delete.side_effect = [True, False]

        response = await client.request(
            "DELETE",
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={"kb_names": ["KB1", "KB2"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 1

    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.delete_storage", new=MagicMock(return_value=True))
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_should_report_not_found_kbs(self, mock_root, client, logged_in_headers, tmp_path):
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
