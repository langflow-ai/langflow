"""Tests for the correctness/observability fixes in lfx.interface.components.

Covers:
- SHA256 verification on the cache-hit short-circuit (not just version match).
- Auto-deletion of stale-version caches so the rebuild path can write fresh.
- Narrow exception handling and warn-don't-swallow on corrupt cache peeks.
- _save_generated_index OSError vs unexpected log levels.
- Selective dev mode emits a warning when no components were produced.
- _load_components_dynamically emits an aggregate failure summary.

Lives in a separate file from test_component_index.py because that file currently
imports tests.unit._parity_helpers, which doesn't exist on this branch and breaks
collection. These tests are self-contained and runnable in the lfx-only venv.
"""

from __future__ import annotations

import asyncio
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
    """Reset the module-level ComponentCache so tests don't see each other's state."""
    component_cache.all_types_dict = None
    component_cache.fully_loaded_components = {}
    component_cache.type_to_current_hash = None
    component_cache.all_known_hashes = None
    component_cache._lock = None


def _build_cache_blob(version: str, entries: list, *, valid_sha: bool = True) -> bytes:
    """Build a serialized cache file matching the on-disk format.

    With valid_sha=False, the sha256 field is set to a deterministic but wrong value.
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


# ---------------------------------------------------------------------------
# SHA verification on the cache-hit short-circuit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCacheHitShaVerification:
    """The cache-hit short-circuit must verify SHA256, not just version + entries.

    Before the fix, the peek validated only `version` and `entries`, so a corrupt-
    but-version-stamped cache file would load silently. Tests assert that tampered
    caches fall through to the rebuild path.
    """

    async def test_tampered_sha_does_not_short_circuit(self, tmp_path, monkeypatch):
        """A cache with a wrong SHA256 must NOT take the short-circuit; rebuild instead."""
        cache_file = tmp_path / "component_index.json"
        installed = "test-1.0"
        entries = [["cat1", {"comp1": {"template": {}, "display_name": "C"}}]]
        cache_file.write_bytes(_build_cache_blob(installed, entries, valid_sha=False))

        monkeypatch.setattr(ci, "_get_cache_path", lambda: cache_file)
        monkeypatch.setattr("importlib.metadata.version", lambda _name: installed)

        warning_mock = MagicMock()
        monkeypatch.setattr(ci.logger, "warning", warning_mock)

        # Stub the rebuild path so we observe it ran without doing real work.
        rebuild_mock = AsyncMock(return_value={"components": {"rebuilt": {"x": {}}}})
        monkeypatch.setattr(ci, "import_langflow_components", rebuild_mock)
        monkeypatch.setattr(ci, "_determine_loading_strategy", AsyncMock(return_value={}))

        await get_and_cache_all_types_dict(_fake_settings_service())

        rebuild_mock.assert_awaited_once()
        sha_warns = [
            call for call in warning_mock.call_args_list if call.args and "SHA256 integrity" in str(call.args[0])
        ]
        assert len(sha_warns) == 1, f"expected 1 SHA256 integrity warning, got: {warning_mock.call_args_list!r}"

    async def test_missing_sha_does_not_short_circuit(self, tmp_path, monkeypatch):
        """A cache with no sha256 field must NOT take the short-circuit; rebuild instead."""
        cache_file = tmp_path / "component_index.json"
        installed = "test-1.0"
        # Build a blob WITHOUT a sha256 key.
        blob = {
            "version": installed,
            "metadata": {"num_modules": 1, "num_components": 1},
            "entries": [["cat1", {"comp1": {"template": {}, "display_name": "C"}}]],
        }
        cache_file.write_bytes(orjson.dumps(blob))

        monkeypatch.setattr(ci, "_get_cache_path", lambda: cache_file)
        monkeypatch.setattr("importlib.metadata.version", lambda _name: installed)

        warning_mock = MagicMock()
        monkeypatch.setattr(ci.logger, "warning", warning_mock)

        rebuild_mock = AsyncMock(return_value={"components": {}})
        monkeypatch.setattr(ci, "import_langflow_components", rebuild_mock)
        monkeypatch.setattr(ci, "_determine_loading_strategy", AsyncMock(return_value={}))

        await get_and_cache_all_types_dict(_fake_settings_service())

        rebuild_mock.assert_awaited_once()
        missing_warns = [
            call for call in warning_mock.call_args_list if call.args and "missing SHA256" in str(call.args[0])
        ]
        assert len(missing_warns) == 1, f"expected 1 missing-SHA warning, got: {warning_mock.call_args_list!r}"

    async def test_valid_sha_takes_short_circuit(self, tmp_path, monkeypatch):
        """A version-matched, SHA-valid cache short-circuits past import_langflow_components."""
        cache_file = tmp_path / "component_index.json"
        installed = "match-1.0"
        entries = [["cat1", {"comp1": {"template": {}, "display_name": "C"}}]]
        cache_file.write_bytes(_build_cache_blob(installed, entries, valid_sha=True))

        monkeypatch.setattr(ci, "_get_cache_path", lambda: cache_file)
        monkeypatch.setattr("importlib.metadata.version", lambda _name: installed)

        rebuild_mock = AsyncMock(return_value={"components": {}})
        monkeypatch.setattr(ci, "import_langflow_components", rebuild_mock)

        result = await get_and_cache_all_types_dict(_fake_settings_service())

        rebuild_mock.assert_not_awaited()
        assert "cat1" in result, f"cache-hit did not populate result: {result!r}"


# ---------------------------------------------------------------------------
# Stale-cache auto-delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestStaleCacheAutoDelete:
    """When peek detects a version mismatch, the stale cache must be unlinked.

    Before this fix, the warning fired on every cold start indefinitely because
    _save_generated_index only runs in the dynamic-build fallback, which the
    shipped index normally short-circuits.
    """

    async def test_stale_version_cache_is_deleted(self, tmp_path, monkeypatch):
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
        assert len(stale_warns) == 1, f"expected 1 stale-cache warning, got: {warning_mock.call_args_list!r}"

    async def test_stale_delete_failure_logs_warning_and_continues(self, tmp_path, monkeypatch):
        """If unlink raises OSError, warn and continue to rebuild — don't crash."""
        cache_file = tmp_path / "component_index.json"
        cache_file.write_bytes(_build_cache_blob("old-1.0", []))

        monkeypatch.setattr(ci, "_get_cache_path", lambda: cache_file)
        monkeypatch.setattr("importlib.metadata.version", lambda _name: "new-2.0")

        # Force unlink to fail. We patch on the Path instance returned by _get_cache_path.
        original_unlink = type(cache_file).unlink

        def boom(self, *_a, **_kw):
            if self == cache_file:
                msg = "simulated"
                raise PermissionError(msg)
            return original_unlink(self, *_a, **_kw)

        monkeypatch.setattr(type(cache_file), "unlink", boom)

        warning_mock = MagicMock()
        monkeypatch.setattr(ci.logger, "warning", warning_mock)
        monkeypatch.setattr(ci, "import_langflow_components", AsyncMock(return_value={"components": {}}))
        monkeypatch.setattr(ci, "_determine_loading_strategy", AsyncMock(return_value={}))

        # Should not raise.
        await get_and_cache_all_types_dict(_fake_settings_service())

        delete_fail_warns = [
            call
            for call in warning_mock.call_args_list
            if call.args and "Could not remove stale component cache" in str(call.args[0])
        ]
        assert len(delete_fail_warns) == 1


# ---------------------------------------------------------------------------
# Cache peek narrow exception handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCachePeekErrorHandling:
    """Corrupt or unreadable cache files must emit a warning, not pass silently.

    Before this fix, the bare `except: pass` swallowed everything and the
    justifying comment falsely claimed downstream `_read_component_index` would
    log a warning — but the fall-through actually goes straight to the rebuild
    path, never re-reading the cache.
    """

    async def test_corrupt_json_emits_warning_and_rebuilds(self, tmp_path, monkeypatch):
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
            call
            for call in warning_mock.call_args_list
            if call.args and "Component cache peek failed" in str(call.args[0])
        ]
        assert len(peek_warns) == 1, f"expected 1 peek-fail warning, got: {warning_mock.call_args_list!r}"


# ---------------------------------------------------------------------------
# _save_generated_index log levels
# ---------------------------------------------------------------------------


class TestSaveGeneratedIndexLogging:
    """Cache-write logging.

    Disk-write failures used to be buried at debug level, so cold-start regressions
    were invisible. OSError now surfaces at warning; unexpected at error w/ traceback.
    """

    def test_oserror_logs_at_warning(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "component_index.json"
        monkeypatch.setattr(ci, "_get_cache_path", lambda: cache_file)

        # Force the temp-file write to raise PermissionError (a typical OSError).
        original_write_bytes = type(cache_file).write_bytes

        def deny(self, *_a, **_kw):
            if str(self).endswith(".tmp"):
                msg = "simulated read-only mount"
                raise PermissionError(msg)
            return original_write_bytes(self, *_a, **_kw)

        monkeypatch.setattr(type(cache_file), "write_bytes", deny)

        warning_mock = MagicMock()
        error_mock = MagicMock()
        monkeypatch.setattr(ci.logger, "warning", warning_mock)
        monkeypatch.setattr(ci.logger, "error", error_mock)

        # Must not raise — caller robustness contract.
        _save_generated_index({"cat": {"comp": {"template": {}}}})

        assert warning_mock.call_count == 1, (
            f"expected 1 OSError warning, got {warning_mock.call_count}: {warning_mock.call_args_list!r}"
        )
        assert "PermissionError" in str(warning_mock.call_args.args[0])
        assert error_mock.call_count == 0, "OSError should not also fire the unexpected-error path"

    def test_unexpected_exception_logs_at_error_with_traceback(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "component_index.json"
        monkeypatch.setattr(ci, "_get_cache_path", lambda: cache_file)

        # Force orjson.dumps inside _save_generated_index to raise something non-OSError.
        def boom(*_a, **_kw):
            msg = "simulated encode failure"
            raise ValueError(msg)

        monkeypatch.setattr(ci.orjson, "dumps", boom)

        warning_mock = MagicMock()
        error_mock = MagicMock()
        monkeypatch.setattr(ci.logger, "warning", warning_mock)
        monkeypatch.setattr(ci.logger, "error", error_mock)

        _save_generated_index({"cat": {"comp": {"template": {}}}})

        assert error_mock.call_count == 1, (
            f"expected 1 unexpected-error log, got {error_mock.call_count}: {error_mock.call_args_list!r}"
        )
        assert error_mock.call_args.kwargs.get("exc_info") is True, (
            "unexpected error must include exc_info=True for the traceback"
        )


# ---------------------------------------------------------------------------
# Selective dev mode empty-result warning
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSelectiveDevModeEmptyWarning:
    """When LFX_DEV=foo,bar produces zero components, warn explicitly.

    The worst debug-time UX is a successful empty palette with no signal why.
    """

    async def test_empty_result_emits_warning(self, monkeypatch):
        warning_mock = AsyncMock()
        monkeypatch.setattr(ci.logger, "awarning", warning_mock)
        monkeypatch.setattr(ci, "_load_from_index_or_cache", AsyncMock(return_value=({}, None)))
        monkeypatch.setattr(ci, "_load_components_dynamically", AsyncMock(return_value={}))

        modules, source = await _load_selective_dev_mode(None, ["nonexistent"])

        assert modules == {}, "test setup error: expected empty dict from stubs"
        assert source == "dynamic"
        empty_warns = [
            call for call in warning_mock.call_args_list if call.args and "produced 0 components" in str(call.args[0])
        ]
        assert len(empty_warns) == 1, f"expected empty-result warning, got: {warning_mock.call_args_list!r}"

    async def test_non_empty_result_does_not_warn(self, monkeypatch):
        warning_mock = AsyncMock()
        monkeypatch.setattr(ci.logger, "awarning", warning_mock)
        monkeypatch.setattr(ci, "_load_from_index_or_cache", AsyncMock(return_value=({}, None)))
        monkeypatch.setattr(
            ci,
            "_load_components_dynamically",
            AsyncMock(return_value={"cat1": {"comp1": {"template": {}}}}),
        )

        await _load_selective_dev_mode(None, ["cat1"])

        empty_warns = [
            call for call in warning_mock.call_args_list if call.args and "produced 0 components" in str(call.args[0])
        ]
        assert not empty_warns, f"unexpected empty-result warning on populated load: {empty_warns!r}"


# ---------------------------------------------------------------------------
# _load_components_dynamically aggregate failure summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLoadComponentsDynamicallyAggregateFailure:
    """When N of M modules fail, emit one aggregate error log with the count + types histogram.

    Without this, the user sees N individual warnings interleaved with normal startup
    logs and no overall pass/fail signal.
    """

    async def test_partial_failures_emit_aggregate_summary(self, monkeypatch):
        modnames = [
            "lfx.components.cat1.mod_a",
            "lfx.components.cat1.mod_b",
            "lfx.components.cat2.mod_c",
        ]

        def fake_walk_packages(*_args, **_kwargs):
            for name in modnames:
                yield (None, name, False)

        # Two of three modules raise: one ImportError, one ValueError.
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
        assert len(aggregate_calls) == 1, f"expected 1 aggregate-failure log, got: {error_mock.call_args_list!r}"
        msg = str(aggregate_calls[0].args[0])
        assert "2 of 3" in msg, f"aggregate count missing/wrong in message: {msg!r}"
        # Both failure types should appear in the histogram.
        assert "ImportError" in msg, f"ImportError missing from histogram: {msg!r}"
        assert "ValueError" in msg, f"ValueError missing from histogram: {msg!r}"

    async def test_no_failures_does_not_emit_aggregate_log(self, monkeypatch):
        modnames = ["lfx.components.cat1.good"]

        def fake_walk_packages(*_args, **_kwargs):
            for name in modnames:
                yield (None, name, False)

        def fake_process(_modname: str):
            return ("cat1", {"good": {"template": {}, "display_name": "G"}})

        monkeypatch.setattr(ci.pkgutil, "walk_packages", fake_walk_packages)
        monkeypatch.setattr(ci, "_process_single_module", fake_process)

        error_mock = AsyncMock()
        monkeypatch.setattr(ci.logger, "aerror", error_mock)
        monkeypatch.setattr(ci.logger, "awarning", AsyncMock())

        result = await _load_components_dynamically(target_modules=None)

        assert "cat1" in result
        aggregate_calls = [
            call for call in error_mock.call_args_list if call.args and "modules failed" in str(call.args[0])
        ]
        assert not aggregate_calls, f"unexpected aggregate-failure log on clean run: {aggregate_calls!r}"


# Ensure asyncio import isn't pruned by linters that miss the @pytest.mark.asyncio usage.
_ = asyncio
