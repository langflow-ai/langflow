"""Unit tests for LFX CLI FastAPI serve app."""

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from lfx.cli.serve_app import (
    FlowMeta,
    FlowRegistry,
    create_multi_serve_app,
    verify_api_key,
)
from lfx.graph import Graph
from lfx.graph.schema import ResultData
from lfx.interface.components import component_cache
from lfx.schema.message import Message


def _make_settings_service(*, allow_custom_components: bool = False):
    return SimpleNamespace(
        settings=SimpleNamespace(
            allow_custom_components=allow_custom_components,
        )
    )


def _blocked_raw_graph() -> dict:
    return {
        "nodes": [
            {
                "id": "node-1",
                "data": {
                    "id": "node-1",
                    "type": "TotallyCustom",
                    "node": {
                        "display_name": "Blocked Node",
                        "template": {
                            "code": {"value": "print('blocked')"},
                        },
                    },
                },
            }
        ],
        "edges": [],
    }


@pytest.fixture(autouse=True)
def allow_custom_components_by_default(monkeypatch):
    """Keep constructor-level validation aligned with the serve_app test default path."""
    from lfx.services.deps import get_settings_service

    monkeypatch.setattr(get_settings_service().settings, "allow_custom_components", True)


class TestFlowRegistry:
    def _make_meta(self, flow_id: str) -> FlowMeta:
        return FlowMeta(id=flow_id, relative_path=f"{flow_id}.json", title=flow_id, description=None)

    def test_add_and_get(self):
        registry = FlowRegistry()
        graph = MagicMock()
        meta = self._make_meta("flow-1")
        registry.add(graph, meta)
        result = registry.get("flow-1")
        assert result is not None
        assert result[0] is graph
        assert result[1] == meta

    def test_get_missing_returns_none(self):
        assert FlowRegistry().get("nonexistent") is None

    def test_list_metas_empty(self):
        assert FlowRegistry().list_metas() == []

    def test_list_metas_multiple(self):
        registry = FlowRegistry()
        graph = MagicMock()
        registry.add(graph, self._make_meta("a"))
        registry.add(graph, self._make_meta("b"))
        ids = {m.id for m in registry.list_metas()}
        assert ids == {"a", "b"}

    def test_duplicate_add_raises_without_overwrite(self):
        from lfx.cli.serve_app import FlowAlreadyRegisteredError

        registry = FlowRegistry()
        meta = self._make_meta("flow-1")
        registry.add(MagicMock(), meta)
        with pytest.raises(FlowAlreadyRegisteredError, match="already registered"):
            registry.add(MagicMock(), meta)

    def test_duplicate_add_replaces_with_overwrite(self):
        registry = FlowRegistry()
        g1, g2 = MagicMock(), MagicMock()
        meta = self._make_meta("flow-1")
        registry.add(g1, meta)
        registry.add(g2, meta, overwrite=True)
        assert registry.get("flow-1")[0] is g2

    def test_len(self):
        registry = FlowRegistry()
        assert len(registry) == 0
        registry.add(MagicMock(), self._make_meta("x"))
        assert len(registry) == 1

    def test_len_counts_store_only_flows(self):
        """len() must include flows that are in the store but not yet cache-loaded."""
        raw = {"name": "Store-Only", "data": {}, "id": "store-only-id"}

        class StubStore:
            def write(self, *_a):
                pass

            def read(self, flow_id):
                return raw if flow_id == "store-only-id" else None

            def delete(self, *_a):
                return False

            def list_ids(self):
                return ["store-only-id"]

        registry = FlowRegistry(store=StubStore())
        # Nothing in memory yet — but len() must still report 1 via list_metas().
        assert len(registry) == 1

    def test_len_not_double_counted_memory_and_store(self):
        """len() must not double-count a flow that's both in memory and in the store."""
        raw = {"name": "Shared", "data": {}, "id": "shared-id"}

        class StubStore:
            def write(self, *_a):
                pass

            def read(self, flow_id):
                return raw if flow_id == "shared-id" else None

            def delete(self, *_a):
                return False

            def list_ids(self):
                return ["shared-id"]

        registry = FlowRegistry(store=StubStore())
        graph = MagicMock()
        graph.context = {}
        registry.add(graph, self._make_meta("shared-id"))
        assert len(registry) == 1

    def test_warm_from_store_skips_unloadable_flows(self, tmp_path):
        """A single corrupt/unloadable store file must not abort warm-up of the rest.

        On a shared/PVC store, one bad ``{id}.json`` would otherwise crash every
        worker's startup. warm_from_store must skip it and load the good flows.
        """
        from lfx.cli.flow_store import FilesystemFlowStore

        store = FilesystemFlowStore(tmp_path)
        # Corrupt file: read() returns None -> get() returns None (skipped silently).
        (tmp_path / "corrupt.json").write_text("{ not json ", encoding="utf-8")
        # Valid JSON that fails to reconstruct -> get() raises -> warm_from_store must catch.
        store.write("unloadable", {"name": "Bad", "data": {"nodes": [], "edges": []}, "id": "unloadable"})
        # A good flow that reconstructs fine.
        store.write("good", {"name": "Good", "data": {"nodes": [], "edges": []}, "id": "good"})

        registry = FlowRegistry(store=store)
        good_graph = MagicMock()
        good_graph.context = {}

        def fake_load(raw_json):
            if raw_json.get("id") == "unloadable":
                msg = "component not available in this build"
                raise ValueError(msg)
            return good_graph

        with patch("lfx.cli.serve_app.load_flow_from_json", side_effect=fake_load):
            registry.warm_from_store()  # must NOT raise despite corrupt + unloadable files
            assert registry.get("good") is not None

    def test_remove_existing(self):
        registry = FlowRegistry()
        meta = self._make_meta("flow-1")
        registry.add(MagicMock(), meta)
        assert registry.remove("flow-1") is True
        assert registry.get("flow-1") is None

    def test_remove_nonexistent(self):
        assert FlowRegistry().remove("ghost") is False

    def test_registry_no_env_fallback_stamps_context_on_add(self):
        """FlowRegistry(no_env_fallback=True) must set graph.context['no_env_fallback']=True on add."""
        registry = FlowRegistry(no_env_fallback=True)
        graph = MagicMock()
        graph.context = {}
        meta = self._make_meta("test-flow")
        registry.add(graph, meta)
        assert graph.context.get("no_env_fallback") is True

    def test_registry_default_does_not_stamp_no_env_fallback(self):
        """FlowRegistry() (default) must NOT set no_env_fallback on the graph context."""
        registry = FlowRegistry()
        graph = MagicMock()
        graph.context = {}
        meta = self._make_meta("test-flow")
        registry.add(graph, meta)
        assert "no_env_fallback" not in graph.context

    def test_registry_no_env_fallback_stamps_context_on_overwrite(self):
        """Stamp must also be applied when overwrite=True."""
        registry = FlowRegistry(no_env_fallback=True)
        first_graph = MagicMock()
        first_graph.context = {}
        meta = self._make_meta("test-flow")
        registry.add(first_graph, meta)

        replacement_graph = MagicMock()
        replacement_graph.context = {}
        registry.add(replacement_graph, meta, overwrite=True)
        assert replacement_graph.context.get("no_env_fallback") is True

    def test_registry_get_misses_to_store(self):
        """Cache miss must load from store, cache result, and return it."""
        from unittest.mock import MagicMock, patch

        raw = {
            "name": "Stored Flow",
            "description": "from disk",
            "data": {"nodes": [], "edges": []},
            "id": "flow-from-store",
        }

        class StubStore:
            def write(self, flow_id, flow_json):
                pass

            def read(self, flow_id):
                return raw if flow_id == "flow-from-store" else None

            def delete(self, _flow_id):
                return False

            def list_ids(self):
                return ["flow-from-store"]

        mock_graph = MagicMock()
        mock_graph.context = {}

        registry = FlowRegistry(store=StubStore())

        with patch("lfx.cli.serve_app.load_flow_from_json", return_value=mock_graph):
            result = registry.get("flow-from-store")

        assert result is not None
        graph, meta = result
        assert graph is mock_graph
        assert meta.id == "flow-from-store"
        assert meta.title == "Stored Flow"
        # second call must hit in-memory cache, not store
        with patch("lfx.cli.serve_app.load_flow_from_json", side_effect=AssertionError("should use cache")):
            registry.get("flow-from-store")

    def test_list_metas_caches_store_reads(self):
        """list_metas() must not re-read a store file it already parsed in a prior call."""
        raw = {"name": "Cached", "data": {"nodes": [], "edges": []}, "id": "cached-id"}
        read_count = 0

        class CountingStore:
            def write(self, *_a):
                pass

            def read(self, _flow_id):
                nonlocal read_count
                read_count += 1
                return raw

            def delete(self, *_a):
                return False

            def list_ids(self):
                return ["cached-id"]

        registry = FlowRegistry(store=CountingStore())
        registry.list_metas()  # first call — reads from store, populates cache
        registry.list_metas()  # second call — must use cache, not read again
        assert read_count == 1, f"Expected 1 store read, got {read_count}"

    def test_list_metas_cache_invalidated_after_remove(self):
        """After remove(), a subsequent list_metas() must not serve stale cached metadata."""
        raw = {"name": "Gone", "data": {"nodes": [], "edges": []}, "id": "gone-id"}

        class MemStore:
            def __init__(self):
                self._data = {"gone-id": raw}

            def write(self, fid, v):
                self._data[fid] = v

            def read(self, fid):
                return self._data.get(fid)

            def delete(self, fid):
                return bool(self._data.pop(fid, None))

            def list_ids(self):
                return list(self._data)

        registry = FlowRegistry(store=MemStore())
        metas = registry.list_metas()
        assert any(m.id == "gone-id" for m in metas)

        registry.remove("gone-id")
        metas_after = registry.list_metas()
        assert not any(m.id == "gone-id" for m in metas_after)

    def test_list_metas_skips_store_sourced_flow_deleted_by_other_worker(self):
        """list_metas() must not return a flow that another worker deleted from the store."""
        raw = {"name": "Shared", "data": {"nodes": [], "edges": []}, "id": "shared-id"}

        class DeletableStore:
            is_persistent = True

            def __init__(self):
                self._data = {"shared-id": raw}

            def write(self, fid, v):
                self._data[fid] = v

            def read(self, fid):
                return self._data.get(fid)

            def delete(self, fid):
                return bool(self._data.pop(fid, None))

            def list_ids(self):
                return list(self._data)

            def exists(self, fid):
                return fid in self._data

        store = DeletableStore()
        registry = FlowRegistry(store=store)

        mock_graph = MagicMock()
        mock_graph.context = {}

        # Load flow into registry via get() — simulates warm_from_store on startup
        with patch("lfx.cli.serve_app.load_flow_from_json", return_value=mock_graph):
            registry.get("shared-id")

        assert any(m.id == "shared-id" for m in registry.list_metas())

        # Another worker deletes the file — simulate by removing from the store directly
        store.delete("shared-id")

        # list_metas() must now exclude the stale entry
        assert not any(m.id == "shared-id" for m in registry.list_metas())

    def test_get_evicts_stale_store_sourced_flow(self):
        """get() must return None and evict the entry when the store file was deleted by another worker."""
        raw = {"name": "Evictable", "data": {"nodes": [], "edges": []}, "id": "evict-id"}

        class DeletableStore:
            is_persistent = True

            def __init__(self):
                self._data = {"evict-id": raw}

            def write(self, fid, v):
                self._data[fid] = v

            def read(self, fid):
                return self._data.get(fid)

            def delete(self, fid):
                return bool(self._data.pop(fid, None))

            def list_ids(self):
                return list(self._data)

        store = DeletableStore()
        registry = FlowRegistry(store=store)

        mock_graph = MagicMock()
        mock_graph.context = {}

        with patch("lfx.cli.serve_app.load_flow_from_json", return_value=mock_graph):
            assert registry.get("evict-id") is not None

        # Another worker deletes the file
        store.delete("evict-id")

        # get() must now return None and evict the stale entry
        assert registry.get("evict-id") is None
        assert "evict-id" not in registry._flows

    def test_registry_get_uses_json_id_over_filename_stem(self):
        """When JSON has a different id than the filename stem, meta.id uses the JSON id.

        The flow is reachable by that UUID (not just the filename stem).
        """
        from unittest.mock import MagicMock, patch

        json_uuid = "b0529294-e297-41d1-9303-2c2128b7860a"
        raw = {
            "name": "prompt_one",
            "id": json_uuid,
            "data": {"nodes": [], "edges": []},
        }

        class StubStore:
            def write(self, *_a):
                pass

            def read(self, flow_id):
                return raw if flow_id == "prompt_one" else None

            def delete(self, *_a):
                return False

            def list_ids(self):
                return ["prompt_one"]

        mock_graph = MagicMock()
        mock_graph.context = {}

        registry = FlowRegistry(store=StubStore())

        with patch("lfx.cli.serve_app.load_flow_from_json", return_value=mock_graph):
            result = registry.get("prompt_one")

        assert result is not None
        _, meta = result
        assert meta.id == json_uuid, "meta.id must come from the JSON id field"
        assert meta.title == "prompt_one"
        # flow must also be reachable by UUID without hitting the store again
        with patch("lfx.cli.serve_app.load_flow_from_json", side_effect=AssertionError("should use cache")):
            by_uuid = registry.get(json_uuid)
        assert by_uuid is not None

    def test_list_metas_deduplicates_filename_and_json_id_aliases(self):
        """list_metas() must not return the same flow twice when it's cached under two keys."""
        from unittest.mock import MagicMock, patch

        json_uuid = "b0529294-e297-41d1-9303-2c2128b7860a"
        raw = {"name": "prompt_one", "id": json_uuid, "data": {"nodes": [], "edges": []}}

        class StubStore:
            def write(self, *_a):
                pass

            def read(self, flow_id):
                return raw if flow_id == "prompt_one" else None

            def delete(self, *_a):
                return False

            def list_ids(self):
                return ["prompt_one"]

        mock_graph = MagicMock()
        mock_graph.context = {}

        registry = FlowRegistry(store=StubStore())

        with patch("lfx.cli.serve_app.load_flow_from_json", return_value=mock_graph):
            registry.get("prompt_one")

        metas = registry.list_metas()
        assert len(metas) == 1, f"expected 1 meta, got {len(metas)}: {[m.id for m in metas]}"
        assert metas[0].id == json_uuid

    def test_overwrite_aliased_flow_removes_old_store_file_and_alias(self):
        """add(overwrite=True) on a pre-placed aliased flow must delete the old file.

        Clears the stem alias so new workers don't reconstruct the stale version.
        """
        from unittest.mock import MagicMock, patch

        json_uuid = "b0529294-e297-41d1-9303-2c2128b7860a"
        old_raw = {"name": "prompt_one", "id": json_uuid, "data": {"nodes": [], "edges": []}}
        deleted: list[str] = []
        store_data: dict[str, dict] = {"prompt_one": old_raw}

        class StubStore:
            def write(self, fid, data):
                store_data[fid] = data

            def read(self, fid):
                return store_data.get(fid)

            def delete(self, fid):
                existed = fid in store_data
                store_data.pop(fid, None)
                deleted.append(fid)
                return existed

            def list_ids(self):
                return list(store_data)

        mock_graph = MagicMock()
        mock_graph.context = {}

        registry = FlowRegistry(store=StubStore())
        with patch("lfx.cli.serve_app.load_flow_from_json", return_value=mock_graph):
            registry.get("prompt_one")  # loads and aliases

        # Overwrite via add() (simulating POST /flows/upload/ with replace=True)
        new_graph = MagicMock()
        new_graph.context = {}
        new_meta = FlowMeta(id=json_uuid, relative_path="<uploaded>", title="prompt_one v2", description=None)
        new_raw = {"name": "prompt_one v2", "id": json_uuid, "data": {"nodes": [], "edges": []}}
        registry.add(new_graph, new_meta, overwrite=True, raw_json=new_raw)

        # Old file must be deleted; new file written under the UUID
        assert "prompt_one" in deleted, "old store file must be deleted on overwrite"
        assert json_uuid in store_data, "new file must be written under the UUID"
        assert "prompt_one" not in store_data, "old file must be gone from store"

        # In-memory: stem alias gone, UUID key has new graph
        assert registry.get(json_uuid)[0] is new_graph
        assert "prompt_one" not in registry._flows, "stem alias must be cleared"

        # Simulate a new worker: fresh registry warms from store
        new_registry = FlowRegistry(store=StubStore())
        with patch("lfx.cli.serve_app.load_flow_from_json", return_value=new_graph):
            new_registry.warm_from_store()
        result = new_registry.get(json_uuid)
        assert result is not None
        assert result[1].title == "prompt_one v2", "new worker must serve the updated flow, not the old one"

    def test_overwrite_unaliased_preplaced_flow_removes_old_store_file(self):
        """add(overwrite=True) must delete a pre-placed file even when get() never ran.

        The replace path in upload_flow skips registry.get(), so _store_keys never
        records the stem alias and old_store_key is None. add() must still scan the
        store for a file whose JSON "id" matches and delete it — otherwise both
        prompt_one.json and {uuid}.json survive.
        """
        from unittest.mock import MagicMock

        json_uuid = "b0529294-e297-41d1-9303-2c2128b7860a"
        old_raw = {"name": "prompt_one", "id": json_uuid, "data": {"nodes": [], "edges": []}}
        deleted: list[str] = []
        store_data: dict[str, dict] = {"prompt_one": old_raw}

        class StubStore:
            is_persistent = True

            def write(self, fid, data):
                store_data[fid] = data

            def read(self, fid):
                return store_data.get(fid)

            def delete(self, fid):
                existed = fid in store_data
                store_data.pop(fid, None)
                deleted.append(fid)
                return existed

            def list_ids(self):
                return list(store_data)

        registry = FlowRegistry(store=StubStore())

        # No registry.get("prompt_one") here — the replace path skips it, so the
        # stem alias is never recorded.
        new_graph = MagicMock()
        new_graph.context = {}
        new_meta = FlowMeta(id=json_uuid, relative_path="<uploaded>", title="prompt_one v2", description=None)
        new_raw = {"name": "prompt_one v2", "id": json_uuid, "data": {"nodes": [], "edges": []}}
        registry.add(new_graph, new_meta, overwrite=True, raw_json=new_raw)

        assert "prompt_one" in deleted, "stale stem file must be deleted on overwrite"
        assert json_uuid in store_data, "new file must be written under the UUID"
        assert "prompt_one" not in store_data, "old stem file must be gone — no duplicate"
        assert list(store_data) == [json_uuid], "store must hold a single file"

    def test_registry_add_with_raw_json_writes_to_store(self):
        """add(raw_json=...) must write to store."""
        from unittest.mock import MagicMock

        written = {}

        class SpyStore:
            def write(self, flow_id, flow_json):
                written[flow_id] = flow_json

            def read(self, _flow_id):
                return None

            def delete(self, _flow_id):
                return False

            def list_ids(self):
                return []

        registry = FlowRegistry(store=SpyStore())
        graph = MagicMock()
        graph.context = {}
        meta = self._make_meta("flow-1")
        raw = {"name": "flow-1", "data": {}}
        registry.add(graph, meta, raw_json=raw)

        assert written == {"flow-1": raw}

    def test_registry_add_without_raw_json_skips_store(self):
        """add() without raw_json must NOT write to store."""
        from unittest.mock import MagicMock

        written = {}

        class SpyStore:
            def write(self, flow_id, flow_json):
                written[flow_id] = flow_json

            def read(self, _flow_id):
                return None

            def delete(self, _flow_id):
                return False

            def list_ids(self):
                return []

        registry = FlowRegistry(store=SpyStore())
        graph = MagicMock()
        graph.context = {}
        registry.add(graph, self._make_meta("flow-1"))
        assert written == {}

    def test_registry_remove_deletes_from_store(self):
        """remove() must delete from store in addition to clearing in-memory."""
        from unittest.mock import MagicMock

        deleted = []

        class SpyStore:
            def write(self, *_a):
                pass

            def read(self, *_a):
                return None

            def delete(self, flow_id):
                deleted.append(flow_id)
                return True

            def list_ids(self):
                return []

        registry = FlowRegistry(store=SpyStore())
        graph = MagicMock()
        graph.context = {}
        registry.add(graph, self._make_meta("flow-1"))
        registry.remove("flow-1")
        assert "flow-1" in deleted

    def test_list_metas_includes_store_only_flows(self):
        """list_metas() must include flows that are in the store but not yet cached."""
        raw = {"name": "Store-Only Flow", "description": None, "data": {}, "id": "store-only"}

        class StubStore:
            def write(self, *_a):
                pass

            def read(self, flow_id):
                return raw if flow_id == "store-only" else None

            def delete(self, *_a):
                return False

            def list_ids(self):
                return ["store-only"]

        registry = FlowRegistry(store=StubStore())
        metas = registry.list_metas()
        assert any(m.id == "store-only" for m in metas)
        assert any(m.title == "Store-Only Flow" for m in metas)

    def test_registry_remove_store_only_flow_returns_true(self):
        """remove() must return True when the flow is in the store but not in memory."""
        raw = {"name": "Store-Only", "data": {}, "id": "store-only"}

        class StubStore:
            def write(self, *_a):
                pass

            def read(self, flow_id):
                return raw if flow_id == "store-only" else None

            def delete(self, flow_id):
                return flow_id == "store-only"

            def list_ids(self):
                return ["store-only"]

        registry = FlowRegistry(store=StubStore())
        # do NOT call registry.get() first — flow is store-only, not in memory
        result = registry.remove("store-only")
        assert result is True

    def test_remove_by_uuid_clears_both_aliases(self):
        """remove(uuid) must remove the filename-stem alias too, not leave a dangling entry."""
        from unittest.mock import MagicMock, patch

        json_uuid = "b0529294-e297-41d1-9303-2c2128b7860a"
        raw = {"name": "prompt_one", "id": json_uuid, "data": {"nodes": [], "edges": []}}

        class StubStore:
            def __init__(self):
                self._deleted: set[str] = set()

            def write(self, *_a):
                pass

            def read(self, fid):
                return None if fid in self._deleted else (raw if fid == "prompt_one" else None)

            def delete(self, fid):
                existed = fid == "prompt_one" and fid not in self._deleted
                self._deleted.add(fid)
                return existed

            def list_ids(self):
                return [f for f in ["prompt_one"] if f not in self._deleted]

        mock_graph = MagicMock()
        mock_graph.context = {}

        registry = FlowRegistry(store=StubStore())
        with patch("lfx.cli.serve_app.load_flow_from_json", return_value=mock_graph):
            registry.get("prompt_one")

        result = registry.remove(json_uuid)
        assert result is True
        with patch("lfx.cli.serve_app.load_flow_from_json", side_effect=AssertionError("store already deleted")):
            assert registry.get(json_uuid) is None, "flow must be gone by UUID"
            assert registry.get("prompt_one") is None, "filename alias must be cleared too"
        assert registry.list_metas() == [], "list_metas must not return the removed flow"

    def test_remove_by_stem_clears_both_aliases(self):
        """remove(stem) must remove the UUID alias too, not leave a dangling entry."""
        from unittest.mock import MagicMock, patch

        json_uuid = "b0529294-e297-41d1-9303-2c2128b7860a"
        raw = {"name": "prompt_one", "id": json_uuid, "data": {"nodes": [], "edges": []}}

        deleted: list[str] = []

        class StubStore:
            def __init__(self):
                self._deleted: set[str] = set()

            def write(self, *_a):
                pass

            def read(self, fid):
                return None if fid in self._deleted else (raw if fid == "prompt_one" else None)

            def delete(self, fid):
                deleted.append(fid)
                existed = fid == "prompt_one" and fid not in self._deleted
                self._deleted.add(fid)
                return existed

            def list_ids(self):
                return [f for f in ["prompt_one"] if f not in self._deleted]

        mock_graph = MagicMock()
        mock_graph.context = {}

        registry = FlowRegistry(store=StubStore())
        with patch("lfx.cli.serve_app.load_flow_from_json", return_value=mock_graph):
            registry.get("prompt_one")

        result = registry.remove("prompt_one")
        assert result is True
        with patch("lfx.cli.serve_app.load_flow_from_json", side_effect=AssertionError("store already deleted")):
            assert registry.get(json_uuid) is None, "UUID alias must be cleared too"
            assert registry.get("prompt_one") is None, "stem must be gone"
        assert "prompt_one" in deleted, "must delete the correct file (by stem, not UUID)"

    def test_remove_deletes_both_stem_and_uuid_files_for_cross_worker_propagation(self):
        """remove() must delete both the stem file and the UUID file.

        Any worker, regardless of which key its stale check uses, must see the deletion.

        Scenario: flow-dir has my-flow.json (pre-placed) and {uuid}.json (written by add()).
        Worker A deletes by UUID; Worker B cached by stem alias.  Both files must be gone.
        """
        from unittest.mock import MagicMock, patch

        json_uuid = "b0529294-e297-41d1-9303-2c2128b7860a"
        raw = {"name": "my-flow", "id": json_uuid, "data": {"nodes": [], "edges": []}}

        store_data: dict[str, dict] = {
            "my-flow": raw,  # pre-placed stem file
            json_uuid: raw,  # UUID file written by add() at startup
        }
        deleted: list[str] = []

        class DualKeyStore:
            is_persistent = True  # required to trigger the stem-scan path in remove()

            def write(self, fid, v):
                store_data[fid] = v

            def read(self, fid):
                return store_data.get(fid)

            def delete(self, fid):
                deleted.append(fid)
                existed = fid in store_data
                store_data.pop(fid, None)
                return existed

            def list_ids(self):
                return list(store_data)

        mock_graph = MagicMock()
        mock_graph.context = {}

        registry = FlowRegistry(store=DualKeyStore())

        # Worker A: loaded via UUID (no stem alias created)
        with patch("lfx.cli.serve_app.load_flow_from_json", return_value=mock_graph):
            registry.get(json_uuid)

        # Stale-check key for Worker A is UUID (no alias)
        assert registry._store_keys.get(json_uuid) is None

        # Worker A deletes by UUID
        result = registry.remove(json_uuid)
        assert result is True

        # Both the UUID file AND the stem file must be deleted
        assert json_uuid in deleted, "UUID-keyed file must be deleted"
        assert "my-flow" in deleted, (
            "stem-keyed file must also be deleted so workers with stem alias don't pass stale check"
        )
        assert not store_data, "store must be empty after remove()"

    def test_list_metas_uncached_store_flow_uses_json_id(self):
        """list_metas() uncached branch must use the JSON id, not the filename stem."""
        json_uuid = "b0529294-e297-41d1-9303-2c2128b7860a"
        raw = {"name": "prompt_one", "id": json_uuid, "data": {}}

        class StubStore:
            def write(self, *_a):
                pass

            def read(self, flow_id):
                return raw if flow_id == "prompt_one" else None

            def delete(self, *_a):
                return False

            def list_ids(self):
                return ["prompt_one"]

        registry = FlowRegistry(store=StubStore())
        # Do NOT call registry.get() first — flow stays uncached in the store branch
        metas = registry.list_metas()
        assert len(metas) == 1
        assert metas[0].id == json_uuid, "uncached list_metas must use JSON id, not filename stem"

    def test_len_not_double_counted_with_aliases(self):
        """len() must return 1 when a flow is cached under both filename stem and JSON UUID."""
        from unittest.mock import MagicMock, patch

        json_uuid = "b0529294-e297-41d1-9303-2c2128b7860a"
        raw = {"name": "prompt_one", "id": json_uuid, "data": {"nodes": [], "edges": []}}

        class StubStore:
            def write(self, *_a):
                pass

            def read(self, flow_id):
                return raw if flow_id == "prompt_one" else None

            def delete(self, *_a):
                return False

            def list_ids(self):
                return ["prompt_one"]

        mock_graph = MagicMock()
        mock_graph.context = {}

        registry = FlowRegistry(store=StubStore())
        with patch("lfx.cli.serve_app.load_flow_from_json", return_value=mock_graph):
            registry.get("prompt_one")

        assert len(registry) == 1, f"expected 1 distinct flow, got {len(registry)}"

    def test_warm_from_store_makes_flow_reachable_by_json_uuid(self):
        """After warm_from_store(), a pre-placed file must be reachable by its JSON UUID."""
        from unittest.mock import MagicMock, patch

        json_uuid = "b0529294-e297-41d1-9303-2c2128b7860a"
        raw = {"name": "prompt_one", "id": json_uuid, "data": {"nodes": [], "edges": []}}

        class StubStore:
            def write(self, *_a):
                pass

            def read(self, flow_id):
                return raw if flow_id == "prompt_one" else None

            def delete(self, *_a):
                return False

            def list_ids(self):
                return ["prompt_one"]

        mock_graph = MagicMock()
        mock_graph.context = {}

        registry = FlowRegistry(store=StubStore())
        with patch("lfx.cli.serve_app.load_flow_from_json", return_value=mock_graph):
            registry.warm_from_store()

        result = registry.get(json_uuid)
        assert result is not None, "flow must be reachable by its JSON UUID after warm_from_store()"
        _, meta = result
        assert meta.id == json_uuid


class TestSecurityFunctions:
    """Test security-related functions."""

    def test_verify_api_key_with_query_param(self):
        """Test API key verification with query parameter."""
        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key-123"}):  # pragma: allowlist secret
            result = verify_api_key("test-key-123", None)
            assert result == "test-key-123"

    def test_verify_api_key_with_header_param(self):
        """Test API key verification with header parameter."""
        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key-123"}):  # pragma: allowlist secret
            result = verify_api_key(None, "test-key-123")
            assert result == "test-key-123"

    def test_verify_api_key_query_param_takes_precedence(self):
        """Query param is checked first; when both are provided the query param value is used."""
        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key-123"}):  # pragma: allowlist secret
            result = verify_api_key("test-key-123", "wrong-key")
            assert result == "test-key-123"

    def test_verify_api_key_missing(self):
        """Test error when no API key is provided."""
        with pytest.raises(HTTPException) as exc_info:
            verify_api_key(None, None)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "API key required"

    def test_verify_api_key_invalid(self):
        """Test error when API key is invalid."""
        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "correct-key"}):  # pragma: allowlist secret
            with pytest.raises(HTTPException) as exc_info:
                verify_api_key("wrong-key", None)
            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "Invalid API key"

    def test_verify_api_key_env_not_set(self):
        """Test error when environment variable is not set."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(HTTPException) as exc_info:
                verify_api_key("any-key", None)
            assert exc_info.value.status_code == 500
            assert "LANGFLOW_API_KEY environment variable is not set" in exc_info.value.detail


class TestCreateServeApp:
    """Test FastAPI app creation."""

    @pytest.fixture
    def simple_chat_json(self):
        test_data_dir = Path(__file__).parent.parent.parent / "data"
        json_path = test_data_dir / "simple_chat_no_llm.json"
        with json_path.open() as f:
            return json.load(f)

    @pytest.fixture
    def real_graph(self, simple_chat_json):
        return Graph.from_payload(simple_chat_json, flow_id="00000000-0000-0000-0000-000000000001")

    @pytest.fixture
    def mock_meta(self):
        return FlowMeta(
            id="00000000-0000-0000-0000-000000000001",
            relative_path="test.json",
            title="Test Flow",
            description="A test flow",
        )

    def test_create_multi_serve_app_single_flow(self, real_graph, mock_meta):
        from lfx.cli.serve_app import FlowRegistry

        registry = FlowRegistry()
        registry.add(real_graph, mock_meta)

        app = create_multi_serve_app(registry=registry)

        routes = [route.path for route in app.routes]
        assert "/health" in routes
        assert "/flows" in routes
        assert "/flows/{flow_id}/run" in routes
        assert "/flows/{flow_id}/info" in routes
        assert "/flows/upload/" in routes

    def test_create_multi_serve_app_multiple_flows(self, real_graph, mock_meta, simple_chat_json):
        from lfx.cli.serve_app import FlowRegistry

        graph2 = Graph.from_payload(simple_chat_json, flow_id="flow-2")
        meta2 = FlowMeta(id="flow-2", relative_path="flow2.json", title="Flow 2", description=None)

        registry = FlowRegistry()
        registry.add(real_graph, mock_meta)
        registry.add(graph2, meta2)

        app = create_multi_serve_app(registry=registry)

        routes = [route.path for route in app.routes]
        assert "/flows/{flow_id}/run" in routes
        assert "/flows/{flow_id}/info" in routes
        # Single dispatch route covers all flow IDs — no per-flow routes
        assert "/flows/00000000-0000-0000-0000-000000000001/run" not in routes
        assert "/flows/flow-2/run" not in routes


class TestCreateServeAppFactory:
    """Tests for the create_serve_app() ASGI factory used by uvicorn workers."""

    def test_create_serve_app_empty_start(self):
        """create_serve_app() with no env vars produces an empty but functional app."""
        import os
        from unittest.mock import patch

        from lfx.cli.serve_app import create_serve_app

        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}, clear=False):  # pragma: allowlist secret
            # Remove startup paths env if present
            env = {k: v for k, v in os.environ.items() if not k.startswith("LFX_SERVE_")}
            with patch.dict(os.environ, env, clear=True):
                os.environ["LANGFLOW_API_KEY"] = "test-key"  # pragma: allowlist secret
                app = create_serve_app()

        routes = [r.path for r in app.routes]
        assert "/health" in routes
        assert "/flows" in routes
        assert "/flows/upload/" in routes

    def test_create_serve_app_startup_paths_cleaned_from_env_by_caller(self):
        """LFX_SERVE_STARTUP_PATHS must be consumed by create_serve_app() but not deleted.

        Cleanup is the caller's (serve_command's) responsibility via the prefix sweep.
        """
        import json
        import os
        from unittest.mock import patch

        from lfx.cli.serve_app import _SERVE_STARTUP_PATHS_ENV, create_serve_app

        env_override = {
            "LANGFLOW_API_KEY": "test-key",  # pragma: allowlist secret
            _SERVE_STARTUP_PATHS_ENV: json.dumps([]),
        }

        with patch.dict(os.environ, env_override):
            # Empty paths list → falls through to else branch
            app = create_serve_app()
            # The env var should still be present during the call (not deleted inside)
            assert _SERVE_STARTUP_PATHS_ENV in os.environ

        assert len(app.state.registry) == 0

    def test_create_serve_app_with_flow_dir_skips_startup_paths_uses_store(self, tmp_path):
        """When flow_dir is set, create_serve_app() must NOT call build_registry_from_paths.

        The parent already persisted startup flows to the store; workers load them via
        warm_from_store() only.  Re-reading files would cause redundant store writes and
        is wrong when the startup files are .py (can't be stored).
        """
        import json
        import os
        from unittest.mock import MagicMock, patch

        from lfx.cli.flow_store import FilesystemFlowStore
        from lfx.cli.serve_app import (
            _SERVE_FLOW_DIR_ENV,
            _SERVE_STARTUP_PATHS_ENV,
            create_serve_app,
        )

        # Pre-place a flow in the store (simulating what the parent did)
        store = FilesystemFlowStore(tmp_path)
        raw = {"name": "Pre-persisted", "description": None, "data": {"nodes": [], "edges": []}, "id": "pre-id"}
        store.write("pre-id", raw)

        mock_graph = MagicMock()
        mock_graph.context = {}

        env_override = {
            "LANGFLOW_API_KEY": "test-key",  # pragma: allowlist secret
            _SERVE_FLOW_DIR_ENV: str(tmp_path),
            # Startup paths IS set but must be IGNORED since flow_dir is present
            _SERVE_STARTUP_PATHS_ENV: json.dumps(["/some/startup/flow.json"]),
        }

        with (
            patch.dict(os.environ, env_override),
            patch("lfx.cli.commands.build_registry_from_paths") as mock_brfp,
            patch("lfx.cli.serve_app.load_flow_from_json", return_value=mock_graph),
        ):
            app = create_serve_app()

        # build_registry_from_paths must NOT have been called — flow_dir means use the store
        mock_brfp.assert_not_called()
        # Flow from the store must be in the registry (loaded via warm_from_store)
        assert len(app.state.registry) == 1

    def test_create_serve_app_without_flow_dir_loads_startup_paths_from_files(self, tmp_path):
        """When flow_dir is NOT set, create_serve_app() must load startup flows from file paths."""
        import json
        import os
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        from lfx.cli.serve_app import _SERVE_STARTUP_PATHS_ENV, create_serve_app

        src = Path(__file__).parent.parent.parent / "data" / "simple_chat_no_llm.json"
        flow_path = tmp_path / "flow.json"
        flow_path.write_bytes(src.read_bytes())

        mock_graph = MagicMock()
        mock_graph.context = {}

        env_override = {
            "LANGFLOW_API_KEY": "test-key",  # pragma: allowlist secret
            # No LFX_SERVE_FLOW_DIR — no flow_dir
            _SERVE_STARTUP_PATHS_ENV: json.dumps([str(flow_path)]),
        }

        with (
            patch.dict(os.environ, env_override),
            patch("lfx.cli.commands.load_flow_from_json", return_value=mock_graph),
        ):
            app = create_serve_app()

        assert len(app.state.registry) == 1, "worker must have loaded the startup flow from the file path"

    def test_create_serve_app_startup_path_load_error_propagates(self, tmp_path):
        """create_serve_app() must raise (not swallow) if a startup flow file fails to load.

        This exercises the ThreadPoolExecutor path: the coroutine raises inside the
        thread, and the exception must propagate back to the worker process so the
        worker fails fast instead of silently starting with an empty registry.
        """
        import json
        import os

        from lfx.cli.serve_app import _SERVE_STARTUP_PATHS_ENV, create_serve_app

        bad_file = tmp_path / "bad_flow.json"
        bad_file.write_text(json.dumps({"nodes": [], "edges": []}))

        env_override = {
            "LANGFLOW_API_KEY": "test-key",  # pragma: allowlist secret
            _SERVE_STARTUP_PATHS_ENV: json.dumps([str(bad_file)]),
            # No LFX_SERVE_FLOW_DIR — triggers the ThreadPoolExecutor path
        }

        with (
            patch.dict(os.environ, env_override),
            patch(
                "lfx.cli.commands.load_flow_from_json",
                side_effect=ValueError("corrupt flow"),
            ),
            pytest.raises(Exception, match="corrupt flow"),
        ):
            create_serve_app()


class TestServeAppEndpoints:
    """Test the FastAPI endpoints."""

    @pytest.fixture
    def simple_chat_json(self):
        """Load the simple chat JSON test data."""
        test_data_dir = Path(__file__).parent.parent.parent / "data"
        json_path = test_data_dir / "simple_chat_no_llm.json"
        with json_path.open() as f:
            return json.load(f)

    @pytest.fixture
    def real_graph_with_async(self, simple_chat_json):
        """Create a real graph with async execution capability."""
        # Create graph using from_payload with real test data
        graph = Graph.from_payload(simple_chat_json, flow_id="00000000-0000-0000-0000-000000000001")

        # Store original async_start to restore later if needed
        original_async_start = graph.async_start

        # Mock successful execution with real ResultData
        async def mock_async_start(inputs, **kwargs):  # noqa: ARG001
            # Create real Message and ResultData objects
            message = Message(text="Hello from flow")
            result_data = ResultData(
                results={"message": message},
                component_display_name="Chat Output",
                component_id=graph.vertices[-1].id if graph.vertices else "test-123",
            )

            # Create a mock result that mimics the real structure
            mock_result = MagicMock()
            mock_result.vertex.custom_component.display_name = "Chat Output"
            mock_result.vertex.id = result_data.component_id
            mock_result.result_dict = result_data

            yield mock_result

        graph.async_start = mock_async_start
        graph._original_async_start = original_async_start

        return graph

    @pytest.fixture
    def app_client(self, real_graph_with_async, monkeypatch):
        """Create test client with single flow app."""
        from lfx.services.deps import get_settings_service

        meta = FlowMeta(
            id="00000000-0000-0000-0000-000000000001",
            relative_path="test.json",
            title="Test Flow",
            description="A test flow",
        )

        registry = FlowRegistry()
        registry.add(real_graph_with_async, meta)

        app = create_multi_serve_app(
            registry=registry,
        )

        monkeypatch.setattr(get_settings_service().settings, "allow_custom_components", True)

        # Set up test API key
        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}):  # pragma: allowlist secret
            return TestClient(app)

    @pytest.fixture
    def multi_flow_client(self, real_graph_with_async, simple_chat_json, monkeypatch):
        """Create test client with multiple flows."""
        from lfx.services.deps import get_settings_service

        # Create second real graph using the same JSON structure
        graph2 = Graph.from_payload(simple_chat_json, flow_id="flow-2")

        async def mock_async_start2(inputs, **kwargs):  # noqa: ARG001
            # Return empty results for this test
            yield MagicMock(outputs=[])

        graph2.async_start = mock_async_start2

        meta1 = FlowMeta(
            id="00000000-0000-0000-0000-000000000001",
            relative_path="test.json",
            title="Test Flow",
            description="First flow",
        )
        meta2 = FlowMeta(
            id="flow-2",
            relative_path="flow2.json",
            title="Flow 2",
            description="Second flow",
        )

        registry = FlowRegistry()
        registry.add(real_graph_with_async, meta1)
        registry.add(graph2, meta2)

        app = create_multi_serve_app(
            registry=registry,
        )

        monkeypatch.setattr(get_settings_service().settings, "allow_custom_components", True)

        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}):  # pragma: allowlist secret
            return TestClient(app)

    def test_health_endpoint(self, app_client):
        """Test health check endpoint."""
        response = app_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["flow_count"] == 1

    def test_run_endpoint_success(self, app_client):
        """Test successful flow execution."""
        request_data = {"input_value": "Test input"}
        headers = {"x-api-key": "test-api-key"}

        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
            patch("lfx.cli.common.extract_structured_result") as mock_extract,
        ):
            mock_extract.return_value = {
                "result": "Hello from flow",
                "success": True,
                "type": "message",
                "component": "TestComponent",
            }
            response = app_client.post(
                "/flows/00000000-0000-0000-0000-000000000001/run", json=request_data, headers=headers
            )

        assert response.status_code == 200
        data = response.json()
        assert data["result"] == "Hello from flow"
        assert data["success"] is True
        assert data["type"] == "message"

    def test_run_endpoint_no_auth(self, app_client):
        """Test flow execution without authentication."""
        request_data = {"input_value": "Test input"}

        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}):  # pragma: allowlist secret
            response = app_client.post("/flows/00000000-0000-0000-0000-000000000001/run", json=request_data)

        assert response.status_code == 401
        assert response.json()["detail"] == "API key required"

    def test_run_endpoint_wrong_auth(self, app_client):
        """Test flow execution with wrong API key."""
        request_data = {"input_value": "Test input"}
        headers = {"x-api-key": "wrong-key"}

        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}):  # pragma: allowlist secret
            response = app_client.post(
                "/flows/00000000-0000-0000-0000-000000000001/run", json=request_data, headers=headers
            )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid API key"

    def test_run_endpoint_blocks_custom_components_when_disabled(
        self,
        real_graph_with_async,
    ):
        """Test that /run fails closed before execution when custom components are blocked."""
        real_graph_with_async.raw_graph_data = _blocked_raw_graph()
        meta = FlowMeta(
            id="00000000-0000-0000-0000-000000000001",
            relative_path="test.json",
            title="Test Flow",
            description="A test flow",
        )
        registry = FlowRegistry()
        registry.add(real_graph_with_async, meta)
        app = create_multi_serve_app(
            registry=registry,
        )
        headers = {"x-api-key": "test-api-key"}

        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
            patch(
                "lfx.services.deps.get_settings_service",
                return_value=_make_settings_service(allow_custom_components=False),
            ),
            patch(
                "lfx.utils.flow_validation.ensure_component_hash_lookups_loaded",
                new=AsyncMock(return_value={"ChatInput": {hashlib.sha256(b"known").hexdigest()[:12]}}),
            ),
            patch.object(
                component_cache,
                "type_to_current_hash",
                {"ChatInput": {hashlib.sha256(b"known").hexdigest()[:12]}},
            ),
            patch(
                "lfx.cli.serve_app.execute_graph_with_capture",
                new=AsyncMock(return_value=([], "")),
            ) as mock_execute,
        ):
            client = TestClient(app)
            response = client.post(
                "/flows/00000000-0000-0000-0000-000000000001/run",
                json={"input_value": "Test input"},
                headers=headers,
            )

        assert response.status_code == 500
        assert response.json()["success"] is False
        assert "custom components are not allowed" in response.json()["result"]
        mock_execute.assert_not_called()

    def test_run_endpoint_query_auth(self, app_client):
        """Test flow execution with query parameter authentication."""
        request_data = {"input_value": "Test input"}

        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
            patch("lfx.cli.common.extract_structured_result") as mock_extract,
        ):
            mock_extract.return_value = {
                "result": "Hello from flow",
                "success": True,
                "type": "message",
                "component": "TestComponent",
            }
            response = app_client.post(
                "/flows/00000000-0000-0000-0000-000000000001/run?x-api-key=test-api-key", json=request_data
            )

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_run_endpoint_execution_error(self, app_client):
        """Test flow execution with error."""
        request_data = {"input_value": "Test input"}
        headers = {"x-api-key": "test-api-key"}

        # Mock execute_graph_with_capture to raise an error
        async def mock_execute_error(graph, input_value, session_id=None):  # noqa: ARG001
            msg = "Flow execution failed"
            raise RuntimeError(msg)

        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
            patch("lfx.cli.serve_app.execute_graph_with_capture", mock_execute_error),
        ):
            response = app_client.post(
                "/flows/00000000-0000-0000-0000-000000000001/run", json=request_data, headers=headers
            )

        assert response.status_code == 500
        data = response.json()
        assert data["success"] is False
        assert data["result"] == "Flow execution failed: Flow execution failed"
        assert data["type"] == "error"
        assert "ERROR: Flow execution failed" in data["logs"]

    def test_run_endpoint_no_results(self, app_client):
        """Test flow execution with no results."""
        request_data = {"input_value": "Test input"}
        headers = {"x-api-key": "test-api-key"}

        # Mock execute_graph_with_capture to return empty results
        async def mock_execute_empty(graph, input_value, session_id=None):  # noqa: ARG001
            return [], ""  # Empty results and logs

        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
            patch("lfx.cli.serve_app.execute_graph_with_capture", mock_execute_empty),
        ):
            response = app_client.post(
                "/flows/00000000-0000-0000-0000-000000000001/run", json=request_data, headers=headers
            )

        assert response.status_code == 500
        data = response.json()
        assert data["result"] == "No response generated"
        assert data["success"] is False
        assert data["type"] == "error"

    def test_run_endpoint_forwards_session_id(self, app_client):
        """The /run endpoint must forward session_id from RunRequest to the executor."""
        captured: dict = {}

        async def mock_execute_capture(graph, input_value, session_id=None):  # noqa: ARG001
            captured["session_id"] = session_id
            return [], ""

        request_data = {"input_value": "Test input", "session_id": "my-conversation"}
        headers = {"x-api-key": "test-api-key"}

        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
            patch("lfx.cli.serve_app.execute_graph_with_capture", mock_execute_capture),
        ):
            app_client.post("/flows/00000000-0000-0000-0000-000000000001/run", json=request_data, headers=headers)

        assert captured["session_id"] == "my-conversation"

    def test_stream_endpoint_forwards_session_id(self, app_client):
        """The /stream endpoint must forward session_id from StreamRequest to the executor."""
        captured: dict = {}

        async def mock_execute_capture(graph, input_value, session_id=None):  # noqa: ARG001
            captured["session_id"] = session_id
            return [], ""

        request_data = {"input_value": "Test input", "session_id": "my-stream-conversation"}
        headers = {"x-api-key": "test-api-key"}

        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
            patch("lfx.cli.serve_app.execute_graph_with_capture", mock_execute_capture),
            # Drain the streaming response so the background task completes before we assert.
            app_client.stream(
                "POST", "/flows/00000000-0000-0000-0000-000000000001/stream", json=request_data, headers=headers
            ) as response,
        ):
            assert response.status_code == 200
            for _ in response.iter_bytes():
                pass

        assert captured["session_id"] == "my-stream-conversation"

    def test_list_flows_endpoint(self, multi_flow_client):
        """Test listing flows in multi-flow mode."""
        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}):  # pragma: allowlist secret
            response = multi_flow_client.get("/flows", headers={"x-api-key": "test-api-key"})

        assert response.status_code == 200
        flows = response.json()
        assert len(flows) == 2
        assert any(f["id"] == "00000000-0000-0000-0000-000000000001" for f in flows)
        assert any(f["id"] == "flow-2" for f in flows)

    def test_flow_info_endpoint(self, multi_flow_client):
        """Test getting flow info in multi-flow mode."""
        headers = {"x-api-key": "test-api-key"}

        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}):  # pragma: allowlist secret
            response = multi_flow_client.get("/flows/00000000-0000-0000-0000-000000000001/info", headers=headers)

        assert response.status_code == 200
        info = response.json()
        assert info["id"] == "00000000-0000-0000-0000-000000000001"
        assert info["title"] == "Test Flow"
        assert info["description"] == "First flow"

    def test_flow_run_endpoint_multi_flow(self, multi_flow_client):
        """Test running specific flow in multi-flow mode."""
        request_data = {"input_value": "Test input"}
        headers = {"x-api-key": "test-api-key"}

        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
            patch("lfx.cli.common.extract_structured_result") as mock_extract,
        ):
            mock_extract.return_value = {
                "result": "Hello from flow",
                "success": True,
                "type": "message",
                "component": "TestComponent",
            }
            response = multi_flow_client.post(
                "/flows/00000000-0000-0000-0000-000000000001/run", json=request_data, headers=headers
            )

        assert response.status_code == 200
        data = response.json()
        assert data["result"] == "Hello from flow"
        assert data["success"] is True

    def test_invalid_request_body(self, app_client):
        """Test with invalid request body."""
        headers = {"x-api-key": "test-api-key"}

        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}):  # pragma: allowlist secret
            response = app_client.post("/flows/00000000-0000-0000-0000-000000000001/run", json={}, headers=headers)

        assert response.status_code == 422  # Validation error

    def test_run_endpoint_injects_global_vars_into_context(self, real_graph_with_async, monkeypatch):
        """global_vars in RunRequest must appear in graph_copy.context['request_variables']."""
        from lfx.services.deps import get_settings_service

        meta = FlowMeta(
            id="00000000-0000-0000-0000-000000000001",
            relative_path="test.json",
            title="Test Flow",
            description=None,
        )
        registry = FlowRegistry()
        registry.add(real_graph_with_async, meta)
        app = create_multi_serve_app(registry=registry)
        monkeypatch.setattr(get_settings_service().settings, "allow_custom_components", True)

        captured: dict = {}

        async def mock_execute_capture(graph, input_value, session_id=None):  # noqa: ARG001
            captured["request_variables"] = dict(graph.context.get("request_variables") or {})
            return [], ""

        headers = {"x-api-key": "test-api-key"}
        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
            patch("lfx.cli.serve_app.execute_graph_with_capture", mock_execute_capture),
            TestClient(app) as client,
        ):
            client.post(
                "/flows/00000000-0000-0000-0000-000000000001/run",
                json={
                    "input_value": "hello",
                    "global_vars": {"MY_API_KEY": "secret-value"},  # pragma: allowlist secret
                },
                headers=headers,
            )

        assert captured["request_variables"] == {"MY_API_KEY": "secret-value"}  # pragma: allowlist secret

    def test_run_endpoint_global_vars_do_not_mutate_registry_graph(self, real_graph_with_async, monkeypatch):
        """global_vars must only be set on the deepcopy; the registry's original graph must be unchanged."""
        from lfx.services.deps import get_settings_service

        meta = FlowMeta(
            id="00000000-0000-0000-0000-000000000001",
            relative_path="test.json",
            title="Test Flow",
            description=None,
        )
        registry = FlowRegistry()
        registry.add(real_graph_with_async, meta)
        app = create_multi_serve_app(registry=registry)
        monkeypatch.setattr(get_settings_service().settings, "allow_custom_components", True)

        async def mock_execute_noop(graph, input_value, session_id=None):  # noqa: ARG001
            return [], ""

        headers = {"x-api-key": "test-api-key"}
        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
            patch("lfx.cli.serve_app.execute_graph_with_capture", mock_execute_noop),
            TestClient(app) as client,
        ):
            client.post(
                "/flows/00000000-0000-0000-0000-000000000001/run",
                json={
                    "input_value": "hello",
                    "global_vars": {"MY_API_KEY": "secret-value"},  # pragma: allowlist secret
                },
                headers=headers,
            )

        original_graph = registry.get("00000000-0000-0000-0000-000000000001")[0]
        rv = original_graph.context.get("request_variables") or {}
        assert "MY_API_KEY" not in rv

    def test_run_endpoint_preserves_no_env_fallback_after_deepcopy(self, real_graph_with_async, monkeypatch):
        """no_env_fallback must reach the executed graph_copy, not only the registry graph.

        deepcopy() drops graph.context, so run_flow must re-apply the stamp after the copy.
        """
        from lfx.services.deps import get_settings_service

        meta = FlowMeta(
            id="00000000-0000-0000-0000-000000000001",
            relative_path="test.json",
            title="Test Flow",
            description=None,
        )
        registry = FlowRegistry(no_env_fallback=True)
        registry.add(real_graph_with_async, meta)
        app = create_multi_serve_app(registry=registry)
        monkeypatch.setattr(get_settings_service().settings, "allow_custom_components", True)

        captured: dict = {}

        async def mock_execute_capture(graph, input_value, session_id=None):  # noqa: ARG001
            captured["no_env_fallback"] = graph.context.get("no_env_fallback")
            return [], ""

        headers = {"x-api-key": "test-api-key"}
        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
            patch("lfx.cli.serve_app.execute_graph_with_capture", mock_execute_capture),
            TestClient(app) as client,
        ):
            client.post(
                "/flows/00000000-0000-0000-0000-000000000001/run",
                json={"input_value": "hello"},
                headers=headers,
            )

        assert captured["no_env_fallback"] is True

    def test_stream_endpoint_preserves_no_env_fallback_after_deepcopy(self, real_graph_with_async, monkeypatch):
        """no_env_fallback must reach the executed graph_copy on the stream path too."""
        from lfx.services.deps import get_settings_service

        meta = FlowMeta(
            id="00000000-0000-0000-0000-000000000001",
            relative_path="test.json",
            title="Test Flow",
            description=None,
        )
        registry = FlowRegistry(no_env_fallback=True)
        registry.add(real_graph_with_async, meta)
        app = create_multi_serve_app(registry=registry)
        monkeypatch.setattr(get_settings_service().settings, "allow_custom_components", True)

        captured: dict = {}

        async def mock_execute_capture(graph, input_value, session_id=None):  # noqa: ARG001
            captured["no_env_fallback"] = graph.context.get("no_env_fallback")
            return [], ""

        headers = {"x-api-key": "test-api-key"}
        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
            patch("lfx.cli.serve_app.execute_graph_with_capture", mock_execute_capture),
            TestClient(app) as client,
            client.stream(
                "POST",
                "/flows/00000000-0000-0000-0000-000000000001/stream",
                json={"input_value": "hello"},
                headers=headers,
            ) as response,
        ):
            assert response.status_code == 200
            for _ in response.iter_bytes():
                pass

        assert captured["no_env_fallback"] is True

    def test_stream_endpoint_injects_global_vars_into_context(self, real_graph_with_async, monkeypatch):
        """global_vars in StreamRequest must appear in graph_copy.context['request_variables']."""
        from lfx.services.deps import get_settings_service

        meta = FlowMeta(
            id="00000000-0000-0000-0000-000000000001",
            relative_path="test.json",
            title="Test Flow",
            description=None,
        )
        registry = FlowRegistry()
        registry.add(real_graph_with_async, meta)
        app = create_multi_serve_app(registry=registry)
        monkeypatch.setattr(get_settings_service().settings, "allow_custom_components", True)

        captured: dict = {}

        async def mock_execute_capture(graph, input_value, session_id=None):  # noqa: ARG001
            captured["request_variables"] = dict(graph.context.get("request_variables") or {})
            return [], ""

        headers = {"x-api-key": "test-api-key"}
        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
            patch("lfx.cli.serve_app.execute_graph_with_capture", mock_execute_capture),
            TestClient(app) as client,
            client.stream(
                "POST",
                "/flows/00000000-0000-0000-0000-000000000001/stream",
                json={
                    "input_value": "hello",
                    "global_vars": {"STREAM_KEY": "stream-secret"},  # pragma: allowlist secret
                },
                headers=headers,
            ) as response,
        ):
            assert response.status_code == 200
            for _ in response.iter_bytes():
                pass

        assert captured["request_variables"] == {"STREAM_KEY": "stream-secret"}  # pragma: allowlist secret

    def test_stream_endpoint_no_global_vars_leaves_context_clean(self, real_graph_with_async, monkeypatch):
        """Omitting global_vars must not create request_variables in the graph context."""
        from lfx.services.deps import get_settings_service

        meta = FlowMeta(
            id="00000000-0000-0000-0000-000000000001",
            relative_path="test.json",
            title="Test Flow",
            description=None,
        )
        registry = FlowRegistry()
        registry.add(real_graph_with_async, meta)
        app = create_multi_serve_app(registry=registry)
        monkeypatch.setattr(get_settings_service().settings, "allow_custom_components", True)

        captured: dict = {}

        async def mock_execute_capture(graph, input_value, session_id=None):  # noqa: ARG001
            captured["request_variables"] = graph.context.get("request_variables")
            return [], ""

        headers = {"x-api-key": "test-api-key"}
        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
            patch("lfx.cli.serve_app.execute_graph_with_capture", mock_execute_capture),
            TestClient(app) as client,
            client.stream(
                "POST",
                "/flows/00000000-0000-0000-0000-000000000001/stream",
                json={"input_value": "hello"},  # no global_vars key
                headers=headers,
            ) as response,
        ):
            assert response.status_code == 200
            for _ in response.iter_bytes():
                pass

        assert not captured.get("request_variables")

    def test_stream_endpoint_global_vars_do_not_mutate_registry_graph(self, real_graph_with_async, monkeypatch):
        """global_vars must only be set on the deepcopy; the registry's original graph must be unchanged."""
        from lfx.services.deps import get_settings_service

        meta = FlowMeta(
            id="00000000-0000-0000-0000-000000000001",
            relative_path="test.json",
            title="Test Flow",
            description=None,
        )
        registry = FlowRegistry()
        registry.add(real_graph_with_async, meta)
        app = create_multi_serve_app(registry=registry)
        monkeypatch.setattr(get_settings_service().settings, "allow_custom_components", True)

        async def mock_execute_noop(graph, input_value, session_id=None):  # noqa: ARG001
            return [], ""

        headers = {"x-api-key": "test-api-key"}
        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
            patch("lfx.cli.serve_app.execute_graph_with_capture", mock_execute_noop),
            TestClient(app) as client,
            client.stream(
                "POST",
                "/flows/00000000-0000-0000-0000-000000000001/stream",
                json={
                    "input_value": "hello",
                    "global_vars": {"STREAM_KEY": "stream-secret"},  # pragma: allowlist secret
                },
                headers=headers,
            ) as response,
        ):
            assert response.status_code == 200
            for _ in response.iter_bytes():
                pass

        original_graph = registry.get("00000000-0000-0000-0000-000000000001")[0]
        rv = original_graph.context.get("request_variables") or {}
        assert "STREAM_KEY" not in rv

    def test_flow_execution_with_message_output(self, app_client, real_graph_with_async):
        """Test flow execution with message-type output."""

        # Create a real message output scenario
        async def mock_async_start_message(inputs, **kwargs):  # noqa: ARG001
            # Create real Message and ResultData objects
            message = Message(text="Message output")
            result_data = ResultData(
                results={"message": message}, component_display_name="Chat Output", component_id="test-123"
            )

            # Create result structure
            mock_result = MagicMock()
            mock_result.vertex.custom_component.display_name = "Chat Output"
            mock_result.vertex.id = "test-123"
            mock_result.result_dict = result_data
            # Add message attribute for backwards compatibility
            mock_result.message = message

            yield mock_result

        real_graph_with_async.async_start = mock_async_start_message

        request_data = {"input_value": "Test input"}
        headers = {"x-api-key": "test-api-key"}

        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
            patch("lfx.cli.common.extract_structured_result") as mock_extract,
        ):
            mock_extract.return_value = {
                "result": "Message output",
                "success": True,
                "type": "message",
                "component": "Chat Output",
            }
            response = app_client.post(
                "/flows/00000000-0000-0000-0000-000000000001/run", json=request_data, headers=headers
            )

        assert response.status_code == 200
        data = response.json()
        assert data["result"] == "Message output"
        assert data["success"] is True


class TestUploadEndpoint:
    """Tests for POST /flows/upload/."""

    @pytest.fixture
    def app_with_empty_registry(self):
        from lfx.cli.serve_app import FlowRegistry

        registry = FlowRegistry()
        app = create_multi_serve_app(registry=registry)
        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}):  # pragma: allowlist secret
            yield TestClient(app)

    @pytest.fixture
    def valid_flow_data(self):
        test_data_dir = Path(__file__).parent.parent.parent / "data"
        json_path = test_data_dir / "simple_chat_no_llm.json"
        with json_path.open() as f:
            return json.load(f)

    @pytest.fixture
    def full_export(self):
        """Full Langflow export JSON as exported from the UI (name/data/... at top level).

        This is what a user sends when they run:
            curl -X POST .../flows/upload/ -d @myflow.json

        body.data will be {"edges": [...], "nodes": [...]} — the inner graph with NO
        nested "data" key. A regression that calls load_flow_from_json(body.data)
        raises KeyError('data') here; the correct call passes body.model_dump(...).
        """
        test_data_dir = Path(__file__).parent.parent.parent / "data"
        json_path = test_data_dir / "simple_chat_no_llm.json"
        with json_path.open() as f:
            return json.load(f)

    def test_upload_full_export_as_body(self, app_with_empty_registry, full_export):
        """Uploading a Langflow export JSON directly as the body must succeed.

        Regression test: load_flow_from_json must be called with the full model dict
        (which has a top-level "data" key), not body.data alone (which is just the
        inner graph and has no "data" key).
        """
        response = app_with_empty_registry.post(
            "/flows/upload/",
            json=full_export,
            headers={"x-api-key": "test-key"},
        )
        assert response.status_code == 201, response.json()
        body = response.json()
        assert body["name"] == full_export["name"]
        assert body["run_url"].startswith("/flows/")
        assert body["run_url"].endswith("/run")

    def test_upload_valid_flow(self, app_with_empty_registry, valid_flow_data):
        response = app_with_empty_registry.post(
            "/flows/upload/",
            json={"name": "My Uploaded Flow", "data": valid_flow_data},
            headers={"x-api-key": "test-key"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "My Uploaded Flow"
        assert body["run_url"].startswith("/flows/")
        assert body["run_url"].endswith("/run")
        assert "id" in body

    def test_upload_requires_auth(self, app_with_empty_registry, valid_flow_data):
        response = app_with_empty_registry.post(
            "/flows/upload/",
            json={"name": "Flow", "data": valid_flow_data},
        )
        assert response.status_code == 401

    def test_upload_invalid_flow_data_returns_422(self, app_with_empty_registry):
        with patch("lfx.cli.serve_app.load_flow_from_json", side_effect=ValueError("bad flow")):
            response = app_with_empty_registry.post(
                "/flows/upload/",
                json={"name": "Bad Flow", "data": {"nodes": [], "edges": []}},
                headers={"x-api-key": "test-key"},
            )
        assert response.status_code == 422
        assert "bad flow" in response.json()["detail"]

    def test_upload_prepare_failure_returns_422(self, app_with_empty_registry):
        mock_graph = MagicMock()
        mock_graph.prepare.side_effect = RuntimeError("prepare failed")
        with patch("lfx.cli.serve_app.load_flow_from_json", return_value=mock_graph):
            response = app_with_empty_registry.post(
                "/flows/upload/",
                json={"name": "Bad Flow", "data": {"nodes": [], "edges": []}},
                headers={"x-api-key": "test-key"},
            )
        assert response.status_code == 422
        assert "prepare failed" in response.json()["detail"]

    def test_upload_flow_is_immediately_listed(self, app_with_empty_registry, valid_flow_data):
        upload_resp = app_with_empty_registry.post(
            "/flows/upload/",
            json={"name": "Runnable Flow", "data": valid_flow_data},
            headers={"x-api-key": "test-key"},
        )
        assert upload_resp.status_code == 201
        flow_id = upload_resp.json()["id"]

        list_resp = app_with_empty_registry.get("/flows", headers={"x-api-key": "test-key"})
        assert any(f["id"] == flow_id for f in list_resp.json())

    def test_upload_duplicate_without_replace_returns_409(self, app_with_empty_registry, valid_flow_data):
        fixed_id = "aaaabbbb-1111-2222-3333-444455556666"
        r1 = app_with_empty_registry.post(
            "/flows/upload/",
            json={"id": fixed_id, "name": "Flow A", "data": valid_flow_data},
            headers={"x-api-key": "test-key"},
        )
        assert r1.status_code == 201

        r2 = app_with_empty_registry.post(
            "/flows/upload/",
            json={"id": fixed_id, "name": "Flow B", "data": valid_flow_data},
            headers={"x-api-key": "test-key"},
        )
        assert r2.status_code == 409
        assert "already exists" in r2.json()["detail"]

    def test_upload_replace_true_overwrites(self, app_with_empty_registry, valid_flow_data):
        fixed_id = "bbbbcccc-1111-2222-3333-444455556666"
        r1 = app_with_empty_registry.post(
            "/flows/upload/",
            json={"id": fixed_id, "name": "Original Name", "data": valid_flow_data},
            headers={"x-api-key": "test-key"},
        )
        assert r1.status_code == 201
        flow_id = r1.json()["id"]

        r2 = app_with_empty_registry.post(
            "/flows/upload/",
            json={"id": fixed_id, "name": "Updated Name", "data": valid_flow_data, "replace": True},
            headers={"x-api-key": "test-key"},
        )
        assert r2.status_code == 201
        assert r2.json()["id"] == flow_id
        assert r2.json()["name"] == "Updated Name"

        flows = app_with_empty_registry.get("/flows", headers={"x-api-key": "test-key"}).json()
        ids = [f["id"] for f in flows]
        assert ids.count(flow_id) == 1

    def test_upload_with_description(self, app_with_empty_registry, valid_flow_data):
        response = app_with_empty_registry.post(
            "/flows/upload/",
            json={"name": "Flow", "data": valid_flow_data, "description": "my desc"},
            headers={"x-api-key": "test-key"},
        )
        assert response.status_code == 201
        assert response.json()["description"] == "my desc"

    # ------------------------------------------------------------------
    # Execution failures return HTTP 500 not HTTP 200
    # ------------------------------------------------------------------

    def test_run_execution_exception_returns_500(self, app_with_empty_registry, valid_flow_data):
        """An unhandled exception during graph execution must produce HTTP 500, not 200."""
        upload = app_with_empty_registry.post(
            "/flows/upload/",
            json={"name": "Failing Flow", "data": valid_flow_data},
            headers={"x-api-key": "test-key"},
        )
        assert upload.status_code == 201
        flow_id = upload.json()["id"]

        with patch(
            "lfx.cli.serve_app.execute_graph_with_capture",
            side_effect=RuntimeError("boom"),
        ):
            response = app_with_empty_registry.post(
                f"/flows/{flow_id}/run",
                json={"input_value": "hi"},
                headers={"x-api-key": "test-key"},
            )

        assert response.status_code == 500
        body = response.json()
        assert body["success"] is False
        assert "boom" in body["result"]

    def test_run_flow_failure_result_returns_500(self, app_with_empty_registry, valid_flow_data):
        """A flow that returns success=False in its result must also produce HTTP 500."""
        upload = app_with_empty_registry.post(
            "/flows/upload/",
            json={"name": "Bad Result Flow", "data": valid_flow_data},
            headers={"x-api-key": "test-key"},
        )
        assert upload.status_code == 201
        flow_id = upload.json()["id"]

        with (
            patch("lfx.cli.serve_app.execute_graph_with_capture", return_value=([], "")),
            patch(
                "lfx.cli.serve_app.extract_result_data",
                return_value={"success": False, "result": "flow failed", "type": "error"},
            ),
        ):
            response = app_with_empty_registry.post(
                f"/flows/{flow_id}/run",
                json={"input_value": "hi"},
                headers={"x-api-key": "test-key"},
            )

        assert response.status_code == 500
        body = response.json()
        assert body["success"] is False

    # ------------------------------------------------------------------
    # GET /flows requires authentication
    # ------------------------------------------------------------------

    def test_list_flows_requires_auth(self, app_with_empty_registry):
        response = app_with_empty_registry.get("/flows")
        assert response.status_code == 401

    def test_list_flows_with_auth(self, app_with_empty_registry, valid_flow_data):
        upload = app_with_empty_registry.post(
            "/flows/upload/",
            json={"name": "My Flow", "data": valid_flow_data},
            headers={"x-api-key": "test-key"},
        )
        assert upload.status_code == 201

        response = app_with_empty_registry.get("/flows", headers={"x-api-key": "test-key"})
        assert response.status_code == 200
        assert any(f["id"] == upload.json()["id"] for f in response.json())

    # ------------------------------------------------------------------
    # Runtime flow removal via DELETE /flows/{flow_id}
    # ------------------------------------------------------------------

    def test_delete_flow_removes_it(self, app_with_empty_registry, valid_flow_data):
        upload = app_with_empty_registry.post(
            "/flows/upload/",
            json={"name": "Temp Flow", "data": valid_flow_data},
            headers={"x-api-key": "test-key"},
        )
        assert upload.status_code == 201
        flow_id = upload.json()["id"]

        delete_resp = app_with_empty_registry.delete(f"/flows/{flow_id}", headers={"x-api-key": "test-key"})
        assert delete_resp.status_code == 204

        run_resp = app_with_empty_registry.post(
            f"/flows/{flow_id}/run",
            json={"input_value": "hi"},
            headers={"x-api-key": "test-key"},
        )
        assert run_resp.status_code == 404

    def test_delete_nonexistent_flow_returns_404(self, app_with_empty_registry):
        response = app_with_empty_registry.delete("/flows/does-not-exist", headers={"x-api-key": "test-key"})
        assert response.status_code == 404

    def test_delete_flow_requires_auth(self, app_with_empty_registry, valid_flow_data):
        upload = app_with_empty_registry.post(
            "/flows/upload/",
            json={"name": "Flow", "data": valid_flow_data},
            headers={"x-api-key": "test-key"},
        )
        flow_id = upload.json()["id"]
        response = app_with_empty_registry.delete(f"/flows/{flow_id}")
        assert response.status_code == 401

    # ------------------------------------------------------------------
    # body.id must be a valid UUID to prevent path/store injection
    # ------------------------------------------------------------------

    def test_upload_with_valid_uuid_id(self, app_with_empty_registry, valid_flow_data):
        explicit_id = "b0529294-e297-41d1-9303-2c2128b7860a"
        response = app_with_empty_registry.post(
            "/flows/upload/",
            json={"name": "Flow", "data": valid_flow_data, "id": explicit_id},
            headers={"x-api-key": "test-key"},
        )
        assert response.status_code == 201
        assert response.json()["id"] == explicit_id

    def test_upload_with_invalid_id_returns_422(self, app_with_empty_registry, valid_flow_data):
        response = app_with_empty_registry.post(
            "/flows/upload/",
            json={"name": "Flow", "data": valid_flow_data, "id": "not-a-uuid"},
            headers={"x-api-key": "test-key"},
        )
        assert response.status_code == 422
