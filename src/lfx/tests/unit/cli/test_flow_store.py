"""Tests for FlowStore implementations."""
from __future__ import annotations

import pytest

from lfx.cli.flow_store import FilesystemFlowStore, NullFlowStore


class TestNullFlowStore:
    def test_write_is_noop(self):
        store = NullFlowStore()
        store.write("abc", {"name": "test"})  # should not raise

    def test_read_always_returns_none(self):
        store = NullFlowStore()
        store.write("abc", {"name": "test"})
        assert store.read("abc") is None

    def test_delete_returns_false(self):
        assert NullFlowStore().delete("abc") is False

    def test_list_ids_empty(self):
        assert NullFlowStore().list_ids() == []


class TestFilesystemFlowStore:
    def test_write_and_read_roundtrip(self, tmp_path):
        store = FilesystemFlowStore(tmp_path)
        data = {"name": "My Flow", "data": {"nodes": [], "edges": []}}
        store.write("flow-1", data)
        result = store.read("flow-1")
        assert result == data

    def test_read_missing_returns_none(self, tmp_path):
        assert FilesystemFlowStore(tmp_path).read("nonexistent") is None

    def test_write_is_atomic(self, tmp_path):
        """Write must use rename so readers never see partial JSON."""
        store = FilesystemFlowStore(tmp_path)
        store.write("flow-1", {"name": "test"})
        assert not (tmp_path / "flow-1.json.tmp").exists()
        assert (tmp_path / "flow-1.json").exists()

    def test_delete_existing_returns_true(self, tmp_path):
        store = FilesystemFlowStore(tmp_path)
        store.write("flow-1", {"name": "test"})
        assert store.delete("flow-1") is True
        assert store.read("flow-1") is None

    def test_delete_missing_returns_false(self, tmp_path):
        assert FilesystemFlowStore(tmp_path).delete("nonexistent") is False

    def test_list_ids_empty(self, tmp_path):
        assert FilesystemFlowStore(tmp_path).list_ids() == []

    def test_list_ids_after_write(self, tmp_path):
        store = FilesystemFlowStore(tmp_path)
        store.write("flow-a", {"name": "A"})
        store.write("flow-b", {"name": "B"})
        assert sorted(store.list_ids()) == ["flow-a", "flow-b"]

    def test_list_ids_excludes_tmp_files(self, tmp_path):
        (tmp_path / "partial.json.tmp").write_text("{}")
        assert FilesystemFlowStore(tmp_path).list_ids() == []

    def test_overwrite_existing(self, tmp_path):
        store = FilesystemFlowStore(tmp_path)
        store.write("flow-1", {"name": "original"})
        store.write("flow-1", {"name": "updated"})
        assert store.read("flow-1")["name"] == "updated"

    def test_creates_directory_if_missing(self, tmp_path):
        nested = tmp_path / "deep" / "nested"
        FilesystemFlowStore(nested)
        assert nested.is_dir()

    def test_rejects_path_traversal_flow_id(self, tmp_path):
        store = FilesystemFlowStore(tmp_path)
        with pytest.raises(ValueError):
            store.write("../escape", {"name": "bad"})

    def test_rejects_slash_in_flow_id(self, tmp_path):
        store = FilesystemFlowStore(tmp_path)
        with pytest.raises(ValueError):
            store.write("a/b", {"name": "bad"})
