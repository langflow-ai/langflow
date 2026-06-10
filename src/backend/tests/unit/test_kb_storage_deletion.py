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
    def test_should_write_sentinel_when_all_retries_fail(self, kb_dir):
        """Locked directory falls back to a ``.kb_deleted`` sentinel file.

        Replaces the previous rename fallback: the dir keeps its original
        name, but the listing layer skips dirs carrying the sentinel.
        """
        from langflow.api.utils.kb_helpers import KB_DELETED_SENTINEL, KBStorageHelper

        with patch(
            "langflow.api.utils.kb_helpers.shutil.rmtree",
            side_effect=OSError("[WinError 32] File in use"),
        ):
            result = KBStorageHelper.delete_storage(kb_dir, "test_kb")

        assert result is True
        assert kb_dir.exists(), "dir should remain on disk; the sentinel hides it from listings"
        assert (kb_dir / KB_DELETED_SENTINEL).is_file()

    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.get_fresh_chroma_client", new=MagicMock())
    @patch("langflow.api.utils.kb_helpers.Chroma", new=MagicMock())
    @patch("langflow.api.utils.kb_helpers.time.sleep", new=MagicMock())
    def test_should_return_false_when_rmtree_and_sentinel_both_fail(self, kb_dir):
        """If even the sentinel write fails, the helper reports the failure.

        Covers the worst case: a lock that prevents both ``rmtree`` and a
        plain ``Path.touch`` inside the dir (e.g. permission denied on the
        directory itself).  The caller can then surface a 200-with-warning
        rather than silently claiming success.
        """
        from langflow.api.utils.kb_helpers import KBStorageHelper

        with (
            patch(
                "langflow.api.utils.kb_helpers.shutil.rmtree",
                side_effect=OSError("[WinError 32] File in use"),
            ),
            patch.object(Path, "touch", side_effect=OSError("Permission denied")),
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
    async def test_should_return_200_with_warning_when_storage_cleanup_fails(
        self, mock_root, mock_delete, client, logged_in_headers, tmp_path
    ):
        """Storage failure must not block the user from removing the KB.

        DB-first ordering: by the time delete_storage() returns False the
        row has already been dropped, so the user no longer sees the KB.
        We surface a warning with the on-disk consequence so an operator
        can follow up, but the request itself succeeds.
        """
        mock_root.return_value = tmp_path
        (tmp_path / "activeuser" / "My_KB").mkdir(parents=True)

        response = await client.delete("api/v1/knowledge_bases/My_KB", headers=logged_in_headers)

        assert response.status_code == 200
        body = response.json()
        assert body["message"].startswith("Knowledge base 'My_KB' deleted")
        assert "could not be cleaned up" in body.get("warning", "")
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
    async def test_should_handle_partial_storage_failure_with_warning(
        self, mock_root, mock_delete, client, logged_in_headers, tmp_path
    ):
        """Storage failure on one KB still counts as deleted, with a warning.

        DB-first ordering: the second KB's row is dropped before storage
        cleanup runs, so the user sees both KBs disappear from the list
        even when delete_storage() returns False on one.  The response
        includes a warning so an operator can follow up on the orphaned
        bytes.
        """
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
        assert data["deleted_count"] == 2
        # Warnings field is named ``remote_warnings`` server-side; test the
        # external contract: a warning string mentioning the failed KB.
        warnings_field = data.get("remote_warnings") or data.get("warnings") or data.get("warning") or ""
        assert "KB2" in str(warnings_field) or "could not be cleaned up" in str(warnings_field)

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


# ===========================================================================
# Unit tests: sentinel helpers
# ===========================================================================


class TestSentinelHelpers:
    """Tests for ``is_kb_dir_deleted`` and ``clear_deletion_sentinel``."""

    def test_is_kb_dir_deleted_false_when_marker_absent(self, kb_dir):
        from langflow.api.utils.kb_helpers import KBStorageHelper

        assert KBStorageHelper.is_kb_dir_deleted(kb_dir) is False

    def test_is_kb_dir_deleted_true_when_marker_present(self, kb_dir):
        from langflow.api.utils.kb_helpers import KB_DELETED_SENTINEL, KBStorageHelper

        (kb_dir / KB_DELETED_SENTINEL).touch()
        assert KBStorageHelper.is_kb_dir_deleted(kb_dir) is True

    def test_is_kb_dir_deleted_false_for_missing_dir(self, tmp_path):
        from langflow.api.utils.kb_helpers import KBStorageHelper

        assert KBStorageHelper.is_kb_dir_deleted(tmp_path / "nope") is False

    def test_clear_deletion_sentinel_removes_marker(self, kb_dir):
        from langflow.api.utils.kb_helpers import KB_DELETED_SENTINEL, KBStorageHelper

        marker = kb_dir / KB_DELETED_SENTINEL
        marker.touch()
        assert marker.exists()

        KBStorageHelper.clear_deletion_sentinel(kb_dir)
        assert not marker.exists()

    def test_clear_deletion_sentinel_no_op_when_absent(self, kb_dir):
        """Clearing when the marker is absent must be a silent no-op.

        The create path always calls this defensively; raising would
        regress every fresh KB creation.
        """
        from langflow.api.utils.kb_helpers import KBStorageHelper

        # Should not raise even with no marker file present.
        KBStorageHelper.clear_deletion_sentinel(kb_dir)


# ===========================================================================
# Unit tests: lfx get_knowledge_bases filter parity
# ===========================================================================


class TestLfxSentinelStringInSync:
    """The lfx package inlines the sentinel filename string.

    lfx is published independently of langflow and cannot import
    ``KB_DELETED_SENTINEL`` from langflow.api.utils.kb_helpers without
    pulling the whole API package into the standalone install.  This test
    pins the two literals together so a rename of the sentinel cannot
    silently desync the listing filter.
    """

    def test_sentinel_constant_matches_lfx_literal(self):
        from langflow.api.utils.kb_helpers import KB_DELETED_SENTINEL

        # The lfx-side literal is intentionally inlined as the string
        # ".kb_deleted" inside ``lfx.base.knowledge_bases.knowledge_base_utils``;
        # see the get_knowledge_bases() implementation.
        assert KB_DELETED_SENTINEL == ".kb_deleted"
