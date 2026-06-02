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

    def test_read_corrupt_json_returns_none(self, tmp_path):
        """A corrupted store file must be treated as absent, not raise.

        On a shared/PVC store a partially-written or corrupted ``{id}.json`` would
        otherwise raise JSONDecodeError into a 500 (or crash warm_from_store at startup).
        """
        store = FilesystemFlowStore(tmp_path)
        (tmp_path / "broken.json").write_text("{ this is not valid json ", encoding="utf-8")
        # list_ids still surfaces it (globs *.json), but read() must contain the damage.
        assert "broken" in store.list_ids()
        assert store.read("broken") is None

    def test_write_leaves_no_temp_files(self, tmp_path):
        """Write must clean up its temp file after the rename."""
        store = FilesystemFlowStore(tmp_path)
        store.write("flow-1", {"name": "test"})
        assert list(tmp_path.glob("*.tmp")) == [], "no temp files should remain after write"
        assert (tmp_path / "flow-1.json").exists()

    def test_write_is_atomic_under_concurrent_reads(self, tmp_path):
        """Concurrent readers must only ever observe a complete old or new payload.

        A reader looping read() while a writer overwrites must never see a partial
        file. A non-atomic write (writing into the target in place) would let a
        reader see truncated JSON, which read() does not guard against, so
        json.loads would raise and surface in the reader thread.
        """
        import threading

        store = FilesystemFlowStore(tmp_path)
        # Large, distinct payloads so a torn write is detectable and a partial
        # read would fail json.loads.
        payload_a = {"name": "A", "data": {"nodes": [{"i": i} for i in range(2000)]}}
        payload_b = {"name": "B", "data": {"edges": [{"j": j} for j in range(2000)]}}
        valid = (payload_a, payload_b)

        store.write("flow-1", payload_a)

        errors: list[Exception] = []
        observed: list[dict | None] = []
        stop = threading.Event()

        def reader() -> None:
            try:
                while not stop.is_set():
                    observed.append(store.read("flow-1"))
            except Exception as exc:
                errors.append(exc)

        readers = [threading.Thread(target=reader) for _ in range(4)]
        for t in readers:
            t.start()
        try:
            for _ in range(200):
                store.write("flow-1", payload_b)
                store.write("flow-1", payload_a)
        finally:
            stop.set()
            for t in readers:
                t.join()

        assert not errors, f"reader saw a corrupt/partial file: {errors[:1]}"
        assert observed, "reader never managed to read"
        assert all(r in valid for r in observed), "reader observed a non-atomic intermediate state"

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
        with pytest.raises(ValueError, match="Invalid flow_id"):
            store.write("../escape", {"name": "bad"})

    def test_rejects_slash_in_flow_id(self, tmp_path):
        store = FilesystemFlowStore(tmp_path)
        with pytest.raises(ValueError, match="Invalid flow_id"):
            store.write("a/b", {"name": "bad"})
