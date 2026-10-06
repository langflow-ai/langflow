"""Tests for unified Knowledge Base deletion and resource cleanup.

Covers retained legacy-directory cleanup and SQLite tombstone-before-row deletion.
No test installs or imports a Chroma SDK.
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


# ===========================================================================
# Unit tests: _truncate_sqlite_files
# ===========================================================================


# ===========================================================================
# Unit tests: KBStorageHelper.release_chroma_resources
# ===========================================================================


# ===========================================================================
# Unit tests: KBStorageHelper.delete_storage
# ===========================================================================


class TestDeleteStorage:
    """Tests for KBStorageHelper.delete_storage — unified deletion with retry."""

    @patch("langflow.api.utils.kb_helpers.time.sleep", new=MagicMock())
    def test_should_return_true_when_path_does_not_exist(self, tmp_path):
        from langflow.api.utils.kb_helpers import KBStorageHelper

        non_existent = tmp_path / "does_not_exist"
        result = KBStorageHelper.delete_storage(non_existent, "ghost_kb")

        assert result is True

    @patch("langflow.api.utils.kb_helpers.time.sleep", new=MagicMock())
    def test_should_delete_directory_on_first_attempt(self, kb_dir):
        from langflow.api.utils.kb_helpers import KBStorageHelper

        result = KBStorageHelper.delete_storage(kb_dir, "test_kb")

        assert result is True
        assert not kb_dir.exists()

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

    @patch("langflow.api.utils.kb_helpers.time.sleep", new=MagicMock())
    def test_should_skip_teardown_when_no_chroma_data(self, empty_kb_dir):
        from langflow.api.utils.kb_helpers import KBStorageHelper

        result = KBStorageHelper.delete_storage(empty_kb_dir, "empty_kb")

        assert result is True
        assert not empty_kb_dir.exists()


# ===========================================================================
# Integration tests: delete endpoints using unified delete_storage
# ===========================================================================


async def _seed_kb_row(active_user, name: str):
    """Create the ``knowledge_base`` row that makes a KB exist.

    The delete endpoints resolve existence from the row, not from a directory,
    so a bare directory is not deletable (and not visible) without one.
    """
    from langflow.api.utils import knowledge_base_service

    return await knowledge_base_service.create_record(
        user_id=active_user.id,
        name=name,
        model_selection={"name": "text-embedding-3-small", "provider": "OpenAI"},
    )


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


@pytest.fixture
def sqlite_storage(active_user, monkeypatch, tmp_path):  # noqa: ARG001 -- initialize application settings
    from langflow.services.deps import get_settings_service

    monkeypatch.setattr(get_settings_service().settings, "knowledge_bases_dir", str(tmp_path / "kb"))
    monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)


@pytest.mark.usefixtures("sqlite_storage")
async def test_delete_endpoint_keeps_routing_on_storage_failure(client, logged_in_headers, active_user, monkeypatch):
    from langflow.api.utils import knowledge_base_service
    from lfx.base.knowledge_bases.backends.sqlite import SQLiteBackend

    record = await _seed_kb_row(active_user, "failed_delete")
    original = SQLiteBackend.delete_collection

    async def failed_delete(_self):
        msg = "disk unavailable"
        raise OSError(msg)

    monkeypatch.setattr(SQLiteBackend, "delete_collection", failed_delete)
    response = await client.delete("api/v1/knowledge_bases/failed_delete", headers=logged_in_headers)
    assert response.status_code == 500
    retained = await knowledge_base_service.get_by_user_and_name(active_user.id, record.name)
    assert retained.id == record.id
    assert retained.storage_state == "deleting"
    monkeypatch.setattr(SQLiteBackend, "delete_collection", original)
    response = await client.delete("api/v1/knowledge_bases/failed_delete", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    assert await knowledge_base_service.get_by_user_and_name(active_user.id, record.name) is None


@pytest.mark.usefixtures("sqlite_storage")
async def test_bulk_delete_counts_only_completed_storage_deletions(client, logged_in_headers, active_user, monkeypatch):
    from langflow.api.utils import knowledge_base_service
    from lfx.base.knowledge_bases.backends.sqlite import SQLiteBackend

    await _seed_kb_row(active_user, "good_delete")
    await _seed_kb_row(active_user, "retry_delete")
    original = SQLiteBackend.delete_collection

    async def sometimes_fails(self):
        if self.kb_name == "retry_delete":
            msg = "disk unavailable"
            raise OSError(msg)
        return await original(self)

    monkeypatch.setattr(SQLiteBackend, "delete_collection", sometimes_fails)
    response = await client.request(
        "DELETE",
        "api/v1/knowledge_bases",
        headers=logged_in_headers,
        json={"kb_names": ["good_delete", "retry_delete", "unknown"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["deleted_count"] == 1
    assert "retry_delete" in response.json()["failed"]
    assert "unknown" in response.json()["not_found"]
    assert await knowledge_base_service.get_by_user_and_name(active_user.id, "good_delete") is None
    retained = await knowledge_base_service.get_by_user_and_name(active_user.id, "retry_delete")
    assert retained.storage_state == "deleting"
