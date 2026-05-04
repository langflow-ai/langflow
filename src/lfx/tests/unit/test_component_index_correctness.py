"""Regression tests for the component-index loader correctness fixes.

Lives in a separate file from test_component_index.py because that file
imports tests.unit._parity_helpers, which does not exist on this branch and
breaks collection.
"""

from __future__ import annotations

import hashlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

import orjson
import pytest
from lfx.interface import components as ci
from lfx.interface.components import (
    _load_components_dynamically,
    _load_selective_dev_mode,
    _save_generated_index,
    component_cache,
    get_and_cache_all_types_dict,
)


def _reset_cache_singleton() -> None:
    component_cache.all_types_dict = None
    component_cache.fully_loaded_components = {}
    component_cache.type_to_current_hash = None
    component_cache.all_known_hashes = None
    component_cache._lock = None


def _build_cache_blob(version: str, entries: list, *, valid_sha: bool = True) -> bytes:
    """Build a serialized cache file matching the on-disk format.

    With valid_sha=False the sha256 field is set to a deterministic but wrong value.
    """
    blob: dict[str, Any] = {
        "version": version,
        "metadata": {"num_modules": len(entries), "num_components": sum(len(c) for _, c in entries)},
        "entries": entries,
    }
    payload = orjson.dumps(blob, option=orjson.OPT_SORT_KEYS)
    blob["sha256"] = hashlib.sha256(payload).hexdigest() if valid_sha else "0" * 64
    return orjson.dumps(blob)


def _fake_settings_service() -> Mock:
    settings = Mock()
    settings.settings = Mock(
        lazy_load_components=False,
        components_path=None,
        components_index_path=None,
    )
    return settings


@pytest.fixture(autouse=True)
def _isolate_cache_state():
    _reset_cache_singleton()
    yield
    _reset_cache_singleton()


@pytest.mark.asyncio
async def test_tampered_sha_does_not_short_circuit(tmp_path, monkeypatch):
    """A version-matched but SHA-tampered cache must fall through to the rebuild path."""
    cache_file = tmp_path / "component_index.json"
    installed = "test-1.0"
    entries = [["cat1", {"comp1": {"template": {}, "display_name": "C"}}]]
    cache_file.write_bytes(_build_cache_blob(installed, entries, valid_sha=False))

    monkeypatch.setattr(ci, "_get_cache_path", lambda: cache_file)
    monkeypatch.setattr("importlib.metadata.version", lambda _name: installed)

    warning_mock = MagicMock()
    monkeypatch.setattr(ci.logger, "warning", warning_mock)

    rebuild_mock = AsyncMock(return_value={"components": {"rebuilt": {"x": {}}}})
    monkeypatch.setattr(ci, "import_langflow_components", rebuild_mock)
    monkeypatch.setattr(ci, "_determine_loading_strategy", AsyncMock(return_value={}))

    await get_and_cache_all_types_dict(_fake_settings_service())

    rebuild_mock.assert_awaited_once()
    sha_warns = [call for call in warning_mock.call_args_list if call.args and "SHA256 integrity" in str(call.args[0])]
    assert len(sha_warns) == 1, f"expected 1 SHA256 integrity warning, got: {warning_mock.call_args_list!r}"


@pytest.mark.asyncio
async def test_stale_version_cache_is_deleted(tmp_path, monkeypatch):
    """When peek detects a version mismatch, the stale cache must be unlinked."""
    cache_file = tmp_path / "component_index.json"
    cache_file.write_bytes(_build_cache_blob("old-1.0", []))

    monkeypatch.setattr(ci, "_get_cache_path", lambda: cache_file)
    monkeypatch.setattr("importlib.metadata.version", lambda _name: "new-2.0")

    warning_mock = MagicMock()
    monkeypatch.setattr(ci.logger, "warning", warning_mock)
    monkeypatch.setattr(ci, "import_langflow_components", AsyncMock(return_value={"components": {}}))
    monkeypatch.setattr(ci, "_determine_loading_strategy", AsyncMock(return_value={}))

    await get_and_cache_all_types_dict(_fake_settings_service())

    assert not cache_file.exists(), "stale cache file must be unlinked"
    stale_warns = [
        call for call in warning_mock.call_args_list if call.args and "Stale component cache" in str(call.args[0])
    ]
    assert len(stale_warns) == 1


@pytest.mark.asyncio
async def test_corrupt_json_cache_emits_warning_and_rebuilds(tmp_path, monkeypatch):
    """Corrupt cache file must warn and fall through, not silently swallow."""
    cache_file = tmp_path / "component_index.json"
    cache_file.write_bytes(b"this is not json at all {{{ garbage")

    monkeypatch.setattr(ci, "_get_cache_path", lambda: cache_file)
    monkeypatch.setattr("importlib.metadata.version", lambda _name: "1.0.0")

    warning_mock = MagicMock()
    monkeypatch.setattr(ci.logger, "warning", warning_mock)

    rebuild_mock = AsyncMock(return_value={"components": {}})
    monkeypatch.setattr(ci, "import_langflow_components", rebuild_mock)
    monkeypatch.setattr(ci, "_determine_loading_strategy", AsyncMock(return_value={}))

    await get_and_cache_all_types_dict(_fake_settings_service())

    rebuild_mock.assert_awaited_once()
    peek_warns = [
        call for call in warning_mock.call_args_list if call.args and "Component cache peek failed" in str(call.args[0])
    ]
    assert len(peek_warns) == 1


def test_save_generated_index_oserror_logs_at_warning(tmp_path, monkeypatch):
    """OSError on cache write must surface at warning so cold-start regressions are visible."""
    cache_file = tmp_path / "component_index.json"
    monkeypatch.setattr(ci, "_get_cache_path", lambda: cache_file)

    original_write_bytes = type(cache_file).write_bytes

    def deny(self, *_a, **_kw):
        if str(self).endswith(".tmp"):
            msg = "simulated read-only mount"
            raise PermissionError(msg)
        return original_write_bytes(self, *_a, **_kw)

    monkeypatch.setattr(type(cache_file), "write_bytes", deny)

    warning_mock = MagicMock()
    monkeypatch.setattr(ci.logger, "warning", warning_mock)

    _save_generated_index({"cat": {"comp": {"template": {}}}})

    assert warning_mock.call_count == 1
    assert "PermissionError" in str(warning_mock.call_args.args[0])


@pytest.mark.asyncio
async def test_selective_dev_mode_empty_result_emits_warning(monkeypatch):
    """Zero-component result in selective dev mode must warn instead of returning silently."""
    warning_mock = AsyncMock()
    monkeypatch.setattr(ci.logger, "awarning", warning_mock)
    monkeypatch.setattr(ci, "_load_from_index_or_cache", AsyncMock(return_value=({}, None)))
    monkeypatch.setattr(ci, "_load_components_dynamically", AsyncMock(return_value={}))

    modules, source = await _load_selective_dev_mode(None, ["nonexistent"])

    assert modules == {}
    assert source == "dynamic"
    empty_warns = [
        call for call in warning_mock.call_args_list if call.args and "produced 0 components" in str(call.args[0])
    ]
    assert len(empty_warns) == 1


@pytest.mark.asyncio
async def test_load_components_dynamically_emits_aggregate_failure_summary(monkeypatch):
    """Partial-failure load must emit one aggregate log with count + types histogram."""
    modnames = [
        "lfx.components.cat1.mod_a",
        "lfx.components.cat1.mod_b",
        "lfx.components.cat2.mod_c",
    ]

    def fake_walk_packages(*_args, **_kwargs):
        for name in modnames:
            yield (None, name, False)

    def fake_process(modname: str):
        if modname.endswith("mod_a"):
            msg = "boom A"
            raise ImportError(msg)
        if modname.endswith("mod_b"):
            msg = "boom B"
            raise ValueError(msg)
        return ("cat2", {"mod_c": {"template": {}, "display_name": "C"}})

    monkeypatch.setattr(ci.pkgutil, "walk_packages", fake_walk_packages)
    monkeypatch.setattr(ci, "_process_single_module", fake_process)

    error_mock = AsyncMock()
    monkeypatch.setattr(ci.logger, "aerror", error_mock)
    monkeypatch.setattr(ci.logger, "awarning", AsyncMock())

    result = await _load_components_dynamically(target_modules=None)

    assert "cat2" in result, "non-failing module should still be loaded"
    aggregate_calls = [
        call for call in error_mock.call_args_list if call.args and "modules failed" in str(call.args[0])
    ]
    assert len(aggregate_calls) == 1
    msg = str(aggregate_calls[0].args[0])
    assert "2 of 3" in msg
    assert "ImportError" in msg
    assert "ValueError" in msg
