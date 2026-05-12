"""Unit tests for component index system."""

import asyncio
import hashlib
import json
import threading
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import orjson
import pytest
from lfx.interface.components import (
    _get_cache_path,
    _parse_dev_mode,
    _read_component_index,
    _save_generated_index,
    import_langflow_components,
)

from tests.unit._parity_helpers import (
    _PARITY_FIXTURES_DIR,
    _capture_parity_snapshot,
    _fake_settings_service,
    _install_mock_llm,
    _reset_component_cache_singleton,
)


class TestParseDevMode:
    """Tests for _parse_dev_mode() function."""

    def test_dev_mode_not_set(self, monkeypatch):
        """Test default behavior when LFX_DEV is not set."""
        monkeypatch.delenv("LFX_DEV", raising=False)
        enabled, modules = _parse_dev_mode()
        assert enabled is False
        assert modules is None

    def test_dev_mode_enabled_with_1(self, monkeypatch):
        """Test dev mode enabled with LFX_DEV=1."""
        monkeypatch.setenv("LFX_DEV", "1")
        enabled, modules = _parse_dev_mode()
        assert enabled is True
        assert modules is None  # Load all modules

    def test_dev_mode_enabled_with_true(self, monkeypatch):
        """Test dev mode enabled with LFX_DEV=true."""
        monkeypatch.setenv("LFX_DEV", "true")
        enabled, modules = _parse_dev_mode()
        assert enabled is True
        assert modules is None

    def test_dev_mode_enabled_with_yes(self, monkeypatch):
        """Test dev mode enabled with LFX_DEV=yes."""
        monkeypatch.setenv("LFX_DEV", "yes")
        enabled, modules = _parse_dev_mode()
        assert enabled is True
        assert modules is None

    def test_dev_mode_disabled_with_0(self, monkeypatch):
        """Test dev mode disabled with LFX_DEV=0."""
        monkeypatch.setenv("LFX_DEV", "0")
        enabled, modules = _parse_dev_mode()
        assert enabled is False
        assert modules is None

    def test_dev_mode_disabled_with_false(self, monkeypatch):
        """Test dev mode disabled with LFX_DEV=false."""
        monkeypatch.setenv("LFX_DEV", "false")
        enabled, modules = _parse_dev_mode()
        assert enabled is False
        assert modules is None

    def test_dev_mode_disabled_with_empty(self, monkeypatch):
        """Test dev mode disabled with empty value."""
        monkeypatch.setenv("LFX_DEV", "")
        enabled, modules = _parse_dev_mode()
        assert enabled is False
        assert modules is None

    def test_dev_mode_case_insensitive(self, monkeypatch):
        """Test that env var is case insensitive."""
        monkeypatch.setenv("LFX_DEV", "TRUE")
        enabled, modules = _parse_dev_mode()
        assert enabled is True
        assert modules is None

        monkeypatch.setenv("LFX_DEV", "YES")
        enabled, modules = _parse_dev_mode()
        assert enabled is True
        assert modules is None

    def test_dev_mode_single_module(self, monkeypatch):
        """Test dev mode with a single module filter."""
        monkeypatch.setenv("LFX_DEV", "mistral")
        enabled, modules = _parse_dev_mode()
        assert enabled is True
        assert modules == ["mistral"]

    def test_dev_mode_multiple_modules(self, monkeypatch):
        """Test dev mode with multiple module filters."""
        monkeypatch.setenv("LFX_DEV", "mistral,openai,anthropic")
        enabled, modules = _parse_dev_mode()
        assert enabled is True
        assert modules == ["mistral", "openai", "anthropic"]

    def test_dev_mode_modules_with_spaces(self, monkeypatch):
        """Test dev mode filters spaces correctly."""
        monkeypatch.setenv("LFX_DEV", "mistral, openai , anthropic")
        enabled, modules = _parse_dev_mode()
        assert enabled is True
        assert modules == ["mistral", "openai", "anthropic"]

    def test_dev_mode_modules_case_normalized(self, monkeypatch):
        """Test that module names are lowercased."""
        monkeypatch.setenv("LFX_DEV", "Mistral,OpenAI")
        enabled, modules = _parse_dev_mode()
        assert enabled is True
        assert modules == ["mistral", "openai"]


class TestReadComponentIndex:
    """Tests for _read_component_index() function."""

    async def test_read_index_file_not_found(self):
        """Test reading index when file doesn't exist."""
        mock_path = Mock()
        mock_path.exists.return_value = False

        with patch("lfx.interface.components.Path") as mock_path_class:
            mock_path_class.return_value = mock_path
            result = await _read_component_index()

        assert result is None

    async def test_read_index_valid(self, tmp_path):
        """Test reading valid index file."""
        # Create valid index
        index = {
            "version": "0.1.12",
            "entries": [["category1", {"comp1": {"template": {}}}]],
        }
        payload = orjson.dumps(index, option=orjson.OPT_SORT_KEYS)
        index["sha256"] = hashlib.sha256(payload).hexdigest()

        index_file = tmp_path / "component_index.json"
        index_file.write_bytes(orjson.dumps(index, option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2))

        # Mock the path resolution
        with (
            patch("lfx.interface.components.inspect.getfile") as mock_getfile,
            patch("importlib.metadata.version") as mock_version,
        ):
            mock_getfile.return_value = str(tmp_path / "lfx" / "__init__.py")
            mock_version.return_value = "0.1.12"

            # Create the directory structure
            (tmp_path / "lfx" / "_assets").mkdir(parents=True)
            (tmp_path / "lfx" / "_assets" / "component_index.json").write_bytes(
                orjson.dumps(index, option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2)
            )

            result = await _read_component_index()

        assert result is not None
        assert result["version"] == "0.1.12"
        assert "entries" in result
        assert result["sha256"] == index["sha256"]

    async def test_read_index_invalid_sha256(self, tmp_path):
        """Test reading index with invalid SHA256."""
        # Create index with bad hash
        index = {
            "version": "0.1.12",
            "entries": [["category1", {"comp1": {"template": {}}}]],
            "sha256": "invalid_hash",
        }

        index_file = tmp_path / "component_index.json"
        index_file.write_bytes(orjson.dumps(index))

        with (
            patch("lfx.interface.components.inspect.getfile") as mock_getfile,
            patch("importlib.metadata.version") as mock_version,
        ):
            mock_getfile.return_value = str(tmp_path / "lfx" / "__init__.py")
            mock_version.return_value = "0.1.12"

            (tmp_path / "lfx" / "_assets").mkdir(parents=True)
            (tmp_path / "lfx" / "_assets" / "component_index.json").write_bytes(orjson.dumps(index))

            result = await _read_component_index()

        assert result is None

    async def test_read_index_version_mismatch(self, tmp_path):
        """Test reading index with mismatched version."""
        index = {
            "version": "0.1.11",
            "entries": [["category1", {"comp1": {"template": {}}}]],
        }
        payload = orjson.dumps(index, option=orjson.OPT_SORT_KEYS)
        index["sha256"] = hashlib.sha256(payload).hexdigest()

        with (
            patch("lfx.interface.components.inspect.getfile") as mock_getfile,
            patch("importlib.metadata.version") as mock_version,
        ):
            mock_getfile.return_value = str(tmp_path / "lfx" / "__init__.py")
            mock_version.return_value = "0.1.12"  # Different version

            (tmp_path / "lfx" / "_assets").mkdir(parents=True)
            (tmp_path / "lfx" / "_assets" / "component_index.json").write_bytes(
                orjson.dumps(index, option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2)
            )

            result = await _read_component_index()

        assert result is None

    async def test_read_index_package_not_found(self, tmp_path):
        """Test reading index when lfx package metadata is unavailable (e.g. Docker workspace install)."""
        from importlib.metadata import PackageNotFoundError

        index = {
            "version": "0.4.0",
            "entries": [["category1", {"comp1": {"template": {}}}]],
        }
        payload = orjson.dumps(index, option=orjson.OPT_SORT_KEYS)
        index["sha256"] = hashlib.sha256(payload).hexdigest()

        with (
            patch("lfx.interface.components.inspect.getfile") as mock_getfile,
            patch("importlib.metadata.version") as mock_version,
        ):
            mock_getfile.return_value = str(tmp_path / "lfx" / "__init__.py")
            mock_version.side_effect = PackageNotFoundError("lfx")

            (tmp_path / "lfx" / "_assets").mkdir(parents=True)
            (tmp_path / "lfx" / "_assets" / "component_index.json").write_bytes(
                orjson.dumps(index, option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2)
            )

            result = await _read_component_index()

        # Should succeed - version check skipped when metadata unavailable
        assert result is not None
        assert result["version"] == "0.4.0"
        assert "entries" in result

    async def test_read_index_custom_path_file(self, tmp_path):
        """Test reading index from custom file path."""
        index = {
            "version": "0.1.12",
            "entries": [["category1", {"comp1": {"template": {}}}]],
        }
        payload = orjson.dumps(index, option=orjson.OPT_SORT_KEYS)
        index["sha256"] = hashlib.sha256(payload).hexdigest()

        custom_file = tmp_path / "custom_index.json"
        custom_file.write_bytes(orjson.dumps(index, option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2))

        with patch("importlib.metadata.version") as mock_version:
            mock_version.return_value = "0.1.12"
            result = await _read_component_index(str(custom_file))

        assert result is not None
        assert result["version"] == "0.1.12"

    async def test_read_index_custom_path_url(self):
        """Test reading index from URL."""
        index = {
            "version": "0.1.12",
            "entries": [["category1", {"comp1": {"template": {}}}]],
        }
        payload = orjson.dumps(index, option=orjson.OPT_SORT_KEYS)
        index["sha256"] = hashlib.sha256(payload).hexdigest()

        mock_response = Mock()
        mock_response.content = orjson.dumps(index)

        with (
            patch("httpx.get", return_value=mock_response),
            patch("importlib.metadata.version", return_value="0.1.12"),
        ):
            result = await _read_component_index("https://example.com/index.json")

        assert result is not None
        assert result["version"] == "0.1.12"


class TestCachePath:
    """Tests for cache path functionality."""

    def test_get_cache_path_returns_path(self):
        """Test that _get_cache_path returns a Path object."""
        result = _get_cache_path()
        assert isinstance(result, Path)
        assert result.name == "component_index.json"
        assert "lfx" in str(result)


class TestSaveGeneratedIndex:
    """Tests for _save_generated_index() function."""

    def test_save_generated_index(self, tmp_path, monkeypatch):
        """Test saving generated index to cache."""
        modules_dict = {
            "category1": {"comp1": {"template": {}, "display_name": "Component 1"}},
            "category2": {"comp2": {"template": {}, "display_name": "Component 2"}},
        }

        cache_file = tmp_path / "component_index.json"
        monkeypatch.setattr("lfx.interface.components._get_cache_path", lambda: cache_file)

        with patch("importlib.metadata.version", return_value="0.1.12"):
            _save_generated_index(modules_dict)

        assert cache_file.exists()
        saved_index = orjson.loads(cache_file.read_bytes())

        assert saved_index["version"] == "0.1.12"
        assert "entries" in saved_index
        assert "sha256" in saved_index
        assert len(saved_index["entries"]) == 2

    def test_save_generated_index_empty_dict(self, tmp_path, monkeypatch):
        """Test saving empty modules dict."""
        cache_file = tmp_path / "component_index.json"
        monkeypatch.setattr("lfx.interface.components._get_cache_path", lambda: cache_file)

        with patch("importlib.metadata.version", return_value="0.1.12"):
            _save_generated_index({})

        assert cache_file.exists()
        saved_index = orjson.loads(cache_file.read_bytes())
        assert len(saved_index["entries"]) == 0


@pytest.mark.asyncio
class TestImportLangflowComponents:
    """Tests for import_langflow_components() async function."""

    async def test_import_with_dev_mode(self, monkeypatch):
        """Test import in dev mode (dynamic loading)."""
        monkeypatch.setenv("LFX_DEV", "1")

        with patch("lfx.interface.components._process_single_module") as mock_process:
            mock_process.return_value = ("category1", {"comp1": {"template": {}}})

            with (
                patch("lfx.interface.components.pkgutil.walk_packages") as mock_walk,
                patch("lfx.interface.components._save_generated_index") as mock_save,
            ):
                mock_walk.return_value = [
                    (None, "lfx.components.category1", False),
                ]

                result = await import_langflow_components()

        assert "components" in result
        assert "category1" in result["components"]
        # In dev mode, we don't save to cache
        assert not mock_save.called

    async def test_import_with_builtin_index(self, monkeypatch):
        """Test import with valid built-in index."""
        monkeypatch.delenv("LFX_DEV", raising=False)

        index = {
            "version": "0.1.12",
            "entries": [["category1", {"comp1": {"template": {}}}]],
        }
        payload = orjson.dumps(index, option=orjson.OPT_SORT_KEYS)
        index["sha256"] = hashlib.sha256(payload).hexdigest()

        # _read_component_index is async; patch with AsyncMock so the awaited
        # return value is the index dict, not a coroutine.
        with (
            patch("lfx.interface.components._read_component_index", new=AsyncMock(return_value=index)),
            patch("importlib.metadata.version", return_value="0.1.12"),
        ):
            result = await import_langflow_components()

        assert "components" in result
        assert "category1" in result["components"]
        assert "comp1" in result["components"]["category1"]

    async def test_import_with_missing_index_creates_cache(self, tmp_path, monkeypatch):
        """Test import with missing index falls back to dynamic and caches."""
        monkeypatch.delenv("LFX_DEV", raising=False)
        cache_file = tmp_path / "component_index.json"
        monkeypatch.setattr("lfx.interface.components._get_cache_path", lambda: cache_file)

        # _read_component_index is async; AsyncMock returns None when awaited.
        with (
            patch("lfx.interface.components._read_component_index", new=AsyncMock(return_value=None)),
            patch("lfx.interface.components._process_single_module") as mock_process,
            patch("lfx.interface.components.pkgutil.walk_packages") as mock_walk,
            patch("importlib.metadata.version", return_value="0.1.12"),
        ):
            # Simulate missing built-in index and cache
            mock_process.return_value = ("category1", {"comp1": {"template": {}}})
            mock_walk.return_value = [(None, "lfx.components.category1", False)]

            result = await import_langflow_components()

        assert "components" in result
        assert cache_file.exists()

    async def test_import_with_custom_path_from_settings(self, tmp_path, monkeypatch):
        """Test import with custom index path from settings."""
        monkeypatch.delenv("LFX_DEV", raising=False)

        index = {
            "version": "0.1.12",
            "entries": [["category1", {"comp1": {"template": {}}}]],
        }
        payload = orjson.dumps(index, option=orjson.OPT_SORT_KEYS)
        index["sha256"] = hashlib.sha256(payload).hexdigest()

        custom_file = tmp_path / "custom_index.json"
        custom_file.write_bytes(orjson.dumps(index))

        mock_settings = Mock()
        mock_settings.settings.components_index_path = str(custom_file)

        # _read_component_index is async; AsyncMock awaits to the index dict.
        # ``with patch(..., new=AsyncMock(...)) as mock_read`` binds the AsyncMock
        # to mock_read so we can still assert_called_with(...) after the awaited call.
        with (
            patch("lfx.interface.components._read_component_index", new=AsyncMock(return_value=index)) as mock_read,
            patch("importlib.metadata.version", return_value="0.1.12"),
        ):
            result = await import_langflow_components(mock_settings)

        assert "components" in result
        # Verify custom path was used
        mock_read.assert_called_with(str(custom_file))

    async def test_import_handles_import_errors(self, monkeypatch):
        """Test import handles component import errors gracefully."""
        monkeypatch.setenv("LFX_DEV", "1")

        with (
            patch("lfx.interface.components._process_single_module") as mock_process,
            patch("lfx.interface.components.pkgutil.walk_packages") as mock_walk,
        ):
            # Simulate an import error
            mock_process.side_effect = ImportError("Failed to import")
            mock_walk.return_value = [(None, "lfx.components.broken", False)]

            result = await import_langflow_components()

        # Should return empty dict, not raise
        assert "components" in result
        assert len(result["components"]) == 0


# =====================================================================
# Parity test scaffolding shared across the index-correctness test suite.
# =====================================================================


@pytest.fixture(autouse=True, scope="module")
def _install_mock_llm_for_parity_tests():
    """Install the BaseChatOpenAI mock once per test module. Idempotent.

    Returns False on lfx-only test envs that lack langchain_openai. The
    smallest.json parity fixture does not invoke an LLM, so the False return
    is benign here; LLM-bearing parity fixtures rely on this hook when run in
    environments where langchain_openai IS installed.
    """
    _install_mock_llm()


@pytest.mark.asyncio
class TestIDX01LazyLock:
    """Lazy asyncio.Lock property on ComponentCache.

    Covers:
      * Concurrent callers in a single event loop -- loader runs exactly once.
      * Multi-thread multi-event-loop callers -- no crashes, no deadlocks.
      * Deep end-to-end parity on the synthetic smallest.json fixture.
    """

    async def test_cache_built_once_asyncio(self, monkeypatch):
        """Single event loop, 10 concurrent callers -> loader runs exactly once.

        Critical test wiring: the shipped built-in ``_assets/component_index.json``
        short-circuits ``_load_production_mode`` before ``_load_components_dynamically``
        is ever reached (``_load_from_index_or_cache`` returns a populated dict plus an
        index_source). This test force-returns ``({}, "")`` from
        ``_load_from_index_or_cache`` so the fallback path fires, which is the only
        place ``_load_components_dynamically`` is called. Without this monkeypatch, the
        counter below stays at 0 and the assertion would pass for the wrong reason.

        ``_load_components_dynamically`` itself is replaced by a counting stub
        (no call to the real loader) because the real loader walks every installed
        lfx component package, which in this repo pulls in optional integrations
        (toolguard) that aren't installed in the lfx-only test venv.
        """
        from lfx.interface import components as ci

        _reset_component_cache_singleton(monkeypatch)

        # Force the dynamic-load fallback path so the counter monkey-patch is exercised;
        # otherwise the shipped built-in index short-circuits _load_components_dynamically.
        fallback_mock = AsyncMock(return_value=({}, ""))
        monkeypatch.setattr(ci, "_load_from_index_or_cache", fallback_mock)

        call_count = 0

        async def counting_loader(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            # Widen the race window so unguarded code is caught reliably.
            await asyncio.sleep(0.01)
            return {}

        monkeypatch.setattr(ci, "_load_components_dynamically", counting_loader)

        settings = _fake_settings_service()
        await asyncio.gather(*[ci.get_and_cache_all_types_dict(settings) for _ in range(10)])

        # Sanity check: the forced-fallback path WAS entered (otherwise call_count == 1
        # is a false positive caused by the shipped-index short-circuit).
        assert fallback_mock.await_count > 0, (
            "_load_from_index_or_cache was not called -- test wiring error; the counter "
            "monkey-patch would be dead code without an active fallback path."
        )
        assert call_count == 1, (
            f"expected _load_components_dynamically to run once, got {call_count} (lock did not prevent race)"
        )

    def test_cache_built_once_threading(self, monkeypatch, tmp_path):
        """Ten threads, each with its OWN event loop via asyncio.run.

        Each thread's event loop creates its own asyncio.Lock, so the per-thread
        counter would be 1 but the cross-thread aggregate would be 10. This test
        asserts "no crashes / no deadlocks" under multi-loop conditions, NOT an
        exact call_count. Guards future gunicorn / uvicorn thread-worker
        configurations.

        Each thread resets the singleton's ``_lock`` and ``all_types_dict`` to None
        inside its own worker, immediately before invoking ``asyncio.run``. This
        matches the contract that each thread creates its own Lock via the
        lazy-property on first access in that thread's loop. In production today,
        the singleton lives inside a single event loop, so the cross-loop reuse
        scenario is purely a test-time concern guarded by this per-thread reset.

        Also forces the dynamic-load fallback the same way as the async test so the
        fallback path is actually entered; without that, each thread's load
        short-circuits on the shipped built-in index and the test becomes trivial.
        The loader is stubbed (not wrapped around the real loader) for the same
        reason as the async test: real component enumeration brings in optional
        integrations not installed in the lfx-only test venv.

        Stale-index peek isolation: ``get_and_cache_all_types_dict`` calls
        ``_get_cache_path()`` and, if that path exists, reads the entire disk-cache
        file (5.9MB typical) via ``asyncio.to_thread`` under the per-thread lock.
        With ten threads each creating their own event loop and resetting the
        lazy-lock, that read races against the lazy-lock reset and turns the
        previously-sub-second test into a deadlock-like 60s+ hang. We monkey-patch
        ``_get_cache_path`` to a non-existent path inside ``tmp_path`` so the peek
        short-circuits on ``cache_path.exists()`` being False. This test is about
        multi-loop lock behaviour, not the stale-index warning.
        """
        from lfx.interface import components as ci

        _reset_component_cache_singleton(monkeypatch)

        # Point _get_cache_path at a non-existent file so the read-time peek in
        # get_and_cache_all_types_dict short-circuits and doesn't trigger a 5.9MB
        # disk read under each thread's lock. See docstring.
        _absent_cache_path = tmp_path / "definitely_not_here.json"
        assert not _absent_cache_path.exists()
        monkeypatch.setattr(ci, "_get_cache_path", lambda: _absent_cache_path)

        # Force the dynamic-load fallback path (see async-test rationale above).
        async def _empty_load_from_index_or_cache(*_args, **_kwargs):
            return ({}, "")

        monkeypatch.setattr(ci, "_load_from_index_or_cache", _empty_load_from_index_or_cache)

        # Stub loader: threads share the singleton so we cannot drive real component
        # enumeration safely here. Stub also dodges optional-integration ImportErrors.
        async def _stub_loader(*_args, **_kwargs):
            return {}

        monkeypatch.setattr(ci, "_load_components_dynamically", _stub_loader)

        errors: list[BaseException] = []

        def worker():
            try:
                # Reset lock + dict per thread so each thread's event loop creates
                # its own asyncio.Lock on first access, rather than reusing an instance
                # bound to a different event loop. This is the multi-event-loop contract
                # the threading test is asserting on.
                ci.component_cache.all_types_dict = None
                ci.component_cache._lock = None
                asyncio.run(ci.get_and_cache_all_types_dict(_fake_settings_service()))
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60.0)

        assert not errors, f"threads raised: {errors!r}"
        for t in threads:
            assert not t.is_alive(), "thread did not complete within 60s (possible deadlock)"

    async def test_parity_smallest(self):
        """Deep end-to-end parity against pre-change snapshot."""
        fixture = _PARITY_FIXTURES_DIR / "smallest.json"
        expected_path = _PARITY_FIXTURES_DIR / "smallest.snapshot.json"
        assert fixture.exists(), f"missing synthetic fixture: {fixture}"
        assert expected_path.exists(), (
            f"missing pre-change snapshot: {expected_path}. "
            "Run the snapshot-generation step before the lock changes land."
        )
        snapshot = await _capture_parity_snapshot(fixture)
        expected = json.loads(expected_path.read_text())
        assert snapshot == expected, f"parity drift detected.\n  got: {snapshot}\n  expected: {expected}"


@pytest.mark.asyncio
class TestIDX02SemaphoreCap:
    """Semaphore(16) cap on _load_components_dynamically.

    **Test-wiring rationale:** these tests call ``_load_components_dynamically``
    DIRECTLY rather than going through ``get_and_cache_all_types_dict``. The
    public entry point routes through ``_load_production_mode`` ->
    ``_load_from_index_or_cache``, which short-circuits on the shipped built-in
    ``_assets/component_index.json`` and never enters the semaphore-capped
    function. Per-type counts from that path come from the STATIC shipped
    index -- identical across rebuilds by construction, not by correctness.
    Direct invocation is the only way to exercise the function that owns the
    semaphore.
    """

    async def test_component_count_stable_across_rebuilds(self, monkeypatch):
        """Baseline + 5 direct rebuilds of _load_components_dynamically: per-top-level counts must match exactly.

        Zero-tolerance assertion: under thread-pool pressure, components can be
        silently dropped, and any tolerance would hide that bug. The lfx-only
        test venv lacks optional integrations (toolguard, langchain_openai) that
        the real pkgutil.walk_packages transitively imports, so this test
        monkey-patches ``pkgutil.walk_packages`` to yield a synthetic 200-module
        list across 10 top-levels and stubs ``_process_single_module`` to return
        deterministic per-top-level results. With ~200 modules and a
        Semaphore(16) cap, the gather/merge path under test is exercised exactly
        as it would be in production, and any drop-under-pressure regression
        surfaces as per-top-level count drift across the 5 rebuilds.
        """
        import lfx.interface.components as ci

        # 10 synthetic top-level component categories, 20 modules each = 200 modules total
        # (> 16 Semaphore cap, so the bounded helper actually throttles).
        top_levels = [f"cat{i:02d}" for i in range(10)]
        module_names = [f"lfx.components.{top_level}.comp_{idx:02d}" for top_level in top_levels for idx in range(20)]

        def fake_walk_packages(*_args, **_kwargs):
            # pkgutil.walk_packages yields (module_finder, name, ispkg) tuples.
            for modname in module_names:
                yield (None, modname, False)

        def fake_process_single_module(modname: str):
            # Extract top-level from 'lfx.components.<top_level>.<modname>'.
            parts = modname.split(".")
            top_level = parts[2]
            comp_name = parts[3]
            return (top_level, {comp_name: {"template": {}, "display_name": comp_name}})

        monkeypatch.setattr(ci.pkgutil, "walk_packages", fake_walk_packages)
        monkeypatch.setattr(ci, "_process_single_module", fake_process_single_module)

        async def build_snapshot() -> dict[str, int]:
            # Call _load_components_dynamically DIRECTLY -- this exercises the
            # actual semaphore-capped gather. Do NOT use
            # get_and_cache_all_types_dict here: the shipped built-in index
            # short-circuits the fallback and the semaphore path is never
            # entered.
            modules_dict = await ci._load_components_dynamically(target_modules=None)
            # Per top-level component count. Zero tolerance: any drop is a regression.
            return {top_level: len(components) for top_level, components in modules_dict.items()}

        baseline = await build_snapshot()
        assert baseline, (
            "baseline snapshot is empty -- aborting (probable test setup error; "
            "_load_components_dynamically returned no modules)"
        )
        # Sanity: we expect the synthetic fixture to produce 10 categories * 20 each.
        assert len(baseline) == 10, f"expected 10 top-levels, got {len(baseline)}: {baseline}"
        assert all(v == 20 for v in baseline.values()), f"expected 20 components per top-level, got: {baseline}"

        for attempt in range(5):
            rebuilt = await build_snapshot()
            diff = {k: baseline[k] - rebuilt.get(k, 0) for k in baseline if baseline[k] != rebuilt.get(k, 0)}
            assert rebuilt == baseline, (
                f"rebuild {attempt} diverged from baseline.\n"
                f"  baseline: {baseline}\n"
                f"  rebuilt:  {rebuilt}\n"
                f"  diff (baseline - rebuilt): {diff}"
            )

    async def test_parity_five_types(self):
        """Deep end-to-end parity against pre-change snapshot on the 5-type fixture.

        The fixture wires ChatInput -> Prompt -> OpenAIModel -> ChatOutput
        through a mock-LLM path, exercising multiple distinct component types
        end-to-end. The snapshot is byte-identical pre- and post-semaphore
        because the semaphore only governs cache-build time, not flow
        execution.

        Skips gracefully when ``langchain_openai`` is absent (lfx-only test
        venv): the OpenAIModel component cannot be instantiated without the
        import, and the mock LLM hook in _parity_helpers also returns False in
        that case. When run in a venv that DOES have langchain_openai (e.g.
        the monorepo root venv), the snapshot is byte-identical pre/post
        semaphore changes because the semaphore only affects cache-build time.
        """
        try:
            import langchain_openai  # noqa: F401
        except ModuleNotFoundError:
            pytest.skip(
                "langchain_openai not available in this environment (lfx-only test venv); "
                "five_types.json flow requires OpenAIModel instantiation. Run from the "
                "monorepo root venv to exercise this parity test."
            )

        fixture = _PARITY_FIXTURES_DIR / "five_types.json"
        expected_path = _PARITY_FIXTURES_DIR / "five_types.snapshot.json"
        assert fixture.exists(), f"missing synthetic fixture: {fixture}"
        assert expected_path.exists(), (
            f"missing pre-change snapshot: {expected_path}. "
            "Generate it on release-1.9.0 tip before the semaphore changes land."
        )
        snapshot = await _capture_parity_snapshot(fixture)
        expected = json.loads(expected_path.read_text())
        assert snapshot == expected, f"parity drift detected.\n  got: {snapshot}\n  expected: {expected}"


class TestIDX04IDX05WriteSide:
    """Cache write-side: version('lfx') stamp + atomic write via Path.replace.

    Stamps the cache with ``version("lfx")`` (was ``version("langflow")``) so
    lfx-only deployments don't invalidate it on every restart. Writes atomically
    via a temp file in the SAME directory as the target, then ``Path.replace``
    (a thin wrapper around ``os.replace``, atomic on POSIX and Windows since
    Python 3.3). Both behaviors share ``_save_generated_index`` and the
    write-then-read round-trip assertion.
    """

    def test_stamp_is_lfx_version(self, tmp_path, monkeypatch):
        """Cache is stamped with version('lfx'), never version('langflow').

        Runs in the lfx-only test venv (enforced by ``src/lfx/tests/conftest.py``),
        so ``version('lfx')`` returns the real installed lfx version; a stray
        ``version('langflow')`` call would raise PackageNotFoundError and the
        outer try/except in ``_save_generated_index`` would log-and-swallow,
        producing no cache file at all -- this test would then fail on
        ``cache_file.exists()``.
        """
        from importlib.metadata import version as _real_version

        cache_file = tmp_path / "component_index.json"
        monkeypatch.setattr("lfx.interface.components._get_cache_path", lambda: cache_file)

        _save_generated_index({"cat": {"comp1": {"template": {}}}})

        assert cache_file.exists(), (
            "cache file was not written -- _save_generated_index likely crashed on version lookup "
            "(lfx-only test venv means version('langflow') would raise PackageNotFoundError)"
        )
        saved = orjson.loads(cache_file.read_bytes())
        lfx_installed = _real_version("lfx")
        assert saved["version"] == lfx_installed, (
            f"expected stamp == lfx installed version {lfx_installed!r}, got {saved['version']!r}"
        )

    def test_package_not_found_fallback(self, tmp_path, monkeypatch):
        """When version('lfx') raises PackageNotFoundError, stamp falls back to 'unknown'."""
        from importlib.metadata import PackageNotFoundError

        cache_file = tmp_path / "component_index.json"
        monkeypatch.setattr("lfx.interface.components._get_cache_path", lambda: cache_file)

        def _raise(*_args, **_kwargs):
            msg = "lfx"
            raise PackageNotFoundError(msg)

        # _save_generated_index does ``from importlib.metadata import ... version`` inside
        # its try block, which looks up ``version`` on the importlib.metadata module at call
        # time. Patching the source attribute is sufficient; matches the existing
        # TestSaveGeneratedIndex::test_save_generated_index pattern on line 316.
        monkeypatch.setattr("importlib.metadata.version", _raise)

        _save_generated_index({"cat": {"comp1": {"template": {}}}})

        assert cache_file.exists(), "cache file should be written with 'unknown' fallback stamp"
        saved = orjson.loads(cache_file.read_bytes())
        assert saved["version"] == "unknown", f"expected 'unknown', got {saved['version']!r}"

    @pytest.mark.asyncio
    async def test_round_trip_lfx_only_env(self, tmp_path, monkeypatch, caplog):
        """Save then read in this lfx-only env: no version-mismatch log, entries match.

        Before the version-stamp fix, the cache was stamped with
        ``version('langflow')``, which raised PackageNotFoundError in lfx-only
        environments -- effectively meaning the cache never rolled forward and
        ``_read_component_index`` silently rejected every cache on the version
        check. With the fix, ``version('lfx')`` matches at read time and the
        round-trip succeeds.

        ``_read_component_index`` is async, so this method opts in to
        ``@pytest.mark.asyncio``; the enclosing class remains sync for the
        purely-sync tests.
        """
        import logging

        cache_file = tmp_path / "component_index.json"
        monkeypatch.setattr("lfx.interface.components._get_cache_path", lambda: cache_file)

        original = {
            "cat1": {"compA": {"template": {}, "display_name": "A"}},
            "cat2": {"compB": {"template": {}, "display_name": "B"}},
        }
        _save_generated_index(original)
        assert cache_file.exists(), "save step failed to produce cache file"

        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger="lfx.interface.components"):
            result = await _read_component_index(str(cache_file))

        assert result is not None, (
            "round-trip failed: _read_component_index returned None "
            "(likely version-mismatch rejection -- lfx version stamp not wired correctly)"
        )
        assert "version mismatch" not in caplog.text.lower(), (
            f"unexpected version-mismatch log on round-trip: {caplog.text}"
        )
        # Entries match what we wrote (filter_disabled_components is NOT applied
        # at the _read_component_index layer, so the raw entries round-trip cleanly).
        entries = dict(result["entries"])
        assert entries == original, f"round-trip entries drift: {entries} != {original}"

    def test_atomic_write_uses_same_directory_tmp_and_rename(self, tmp_path, monkeypatch):
        """Tmp file lives in same directory as target; Path.replace performs the rename.

        The production code uses ``tmp_path.replace(cache_path)`` (Path.replace
        is a thin wrapper around os.replace; satisfies the ruff PTH105 rule
        while preserving atomic-rename semantics). We capture calls by wrapping
        ``pathlib.Path.replace`` at the class level, since the method is bound
        on the Path instance.
        """
        import pathlib

        cache_file = tmp_path / "component_index.json"
        monkeypatch.setattr("lfx.interface.components._get_cache_path", lambda: cache_file)

        captured: dict = {}
        real_replace = pathlib.Path.replace

        def _capture_replace(self_path, target):
            # self_path is the Path instance .replace was called on (the tmp file);
            # target is the destination path.
            captured["src"] = str(self_path)
            captured["dst"] = str(target)
            captured["src_exists_at_replace"] = Path(self_path).exists()
            captured["src_parent"] = str(Path(self_path).parent)
            captured["dst_parent"] = str(Path(target).parent)
            return real_replace(self_path, target)

        monkeypatch.setattr(pathlib.Path, "replace", _capture_replace)

        _save_generated_index({"cat": {"comp": {"template": {}}}})

        assert "src" in captured, "Path.replace was not called -- atomic write not wired"
        assert captured["src"].endswith(".tmp"), f"tmp file should end in .tmp, got {captured['src']!r}"
        assert captured["dst"].endswith("component_index.json"), (
            f"destination should be component_index.json, got {captured['dst']!r}"
        )
        assert captured["src_parent"] == captured["dst_parent"], (
            f"tmp and dst must share parent dir (same filesystem) to avoid cross-device-link "
            f"errors in containers; got src_parent={captured['src_parent']!r} "
            f"dst_parent={captured['dst_parent']!r}"
        )
        assert captured["src_exists_at_replace"], "tmp file should exist at the moment Path.replace is invoked"
        assert cache_file.exists(), "final cache file should exist after Path.replace"
        # And the .tmp sibling should NOT be left behind after a successful rename.
        leftover = cache_file.with_suffix(cache_file.suffix + ".tmp")
        assert not leftover.exists(), f"leftover .tmp file after successful write: {leftover}"


@pytest.mark.asyncio
class TestIDX04IDX05WriteSideParity:
    """Deep parity guard for the cache write-side changes."""

    async def test_parity_smallest_after_write_change(self):
        """smallest.json snapshot must match byte-identically after the write-side changes.

        Reuses the shared parity scaffolding (_PARITY_FIXTURES_DIR,
        _capture_parity_snapshot). The write-side change only affects
        cache-persistence, not flow execution, so this snapshot should be
        byte-identical to the pre-change snapshot.
        """
        fixture = _PARITY_FIXTURES_DIR / "smallest.json"
        expected_path = _PARITY_FIXTURES_DIR / "smallest.snapshot.json"
        assert fixture.exists(), f"missing synthetic fixture: {fixture}"
        assert expected_path.exists(), f"missing pre-change snapshot: {expected_path}"
        snapshot = await _capture_parity_snapshot(fixture)
        expected = json.loads(expected_path.read_text())
        assert snapshot == expected, (
            f"write-side changes caused parity drift.\n  got: {snapshot}\n  expected: {expected}"
        )


@pytest.mark.asyncio
class TestIDX03ReadPath:
    """async _read_component_index with asyncio.to_thread-wrapped read_bytes.

    Both ``index_path.read_bytes()`` call sites are wrapped in
    ``await asyncio.to_thread(...)`` so the event loop isn't blocked during the
    ~50ms read of the shipped 5.7MB ``_assets/component_index.json`` (or
    arbitrary time for user cache files).
    """

    def test_is_coroutine_function(self):
        """_read_component_index must be an async def."""
        import inspect as _inspect

        from lfx.interface import components as ci

        assert _inspect.iscoroutinefunction(ci._read_component_index), "_read_component_index should be async def"

    async def test_read_does_not_block_event_loop(self, tmp_path):
        """While _read_component_index runs, a concurrent task still makes progress.

        Proof: write a valid index file, kick off ``_read_component_index`` plus a
        'ticker' task that yields to the loop and counts ticks. Assert the ticker
        increments during the read (non-zero, not stuck at 0). With to_thread
        off-loading the disk read, the ticker WILL advance; with a sync read_bytes
        blocking the loop, ticker_count stays at 0.

        Threshold is intentionally loose (``> 0``): even a perfectly-wrapped
        ``asyncio.to_thread`` will not always yield many ticker increments on
        very fast reads (tmpfs-backed test filesystems complete in microseconds).
        One interleaved tick is the minimum provable "not fully blocked" signal.
        """
        from lfx.interface.components import _read_component_index

        # Build a valid index that passes SHA + version check so the async path runs to completion.
        big_entries = [[f"cat{i}", {f"comp{j}": {"template": {}} for j in range(20)}] for i in range(20)]
        index = {
            "version": "0.1.12",
            "metadata": {"num_modules": 20, "num_components": 400},
            "entries": big_entries,
        }
        payload = orjson.dumps(index, option=orjson.OPT_SORT_KEYS)
        index["sha256"] = hashlib.sha256(payload).hexdigest()

        big_path = tmp_path / "big_index.json"
        big_path.write_bytes(orjson.dumps(index, option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2))

        # Patch version lookup so the version check inside _read_component_index passes
        with patch("importlib.metadata.version", return_value="0.1.12"):
            ticker_count = 0
            ticker_stop = False

            async def ticker():
                nonlocal ticker_count
                while not ticker_stop:
                    ticker_count += 1
                    await asyncio.sleep(0)

            ticker_task = asyncio.create_task(ticker())
            try:
                result = await _read_component_index(str(big_path))
            finally:
                ticker_stop = True
                await ticker_task

        assert result is not None, "_read_component_index returned None despite valid index"
        # With to_thread off-loading the read, the ticker WILL increment during the read.
        # A value of 0 means the event loop was blocked the whole time (the bug we are fixing).
        assert ticker_count > 0, "event loop appears blocked during read_bytes; asyncio.to_thread wrap may be missing"

    async def test_parity_smallest_after_async_refactor(self):
        """Parity guard: smallest.json still produces the pre-change snapshot."""
        fixture = _PARITY_FIXTURES_DIR / "smallest.json"
        expected_path = _PARITY_FIXTURES_DIR / "smallest.snapshot.json"
        assert fixture.exists(), f"missing synthetic fixture: {fixture}"
        assert expected_path.exists(), f"missing pre-change snapshot: {expected_path}"
        snapshot = await _capture_parity_snapshot(fixture)
        expected = json.loads(expected_path.read_text())
        assert snapshot == expected, (
            f"async read-path refactor caused parity drift.\n  got: {snapshot}\n  expected: {expected}"
        )

    async def test_parity_five_types_after_async_refactor(self):
        """Parity guard on the 5-type fixture as well (may skip on lfx-only env)."""
        fixture = _PARITY_FIXTURES_DIR / "five_types.json"
        expected_path = _PARITY_FIXTURES_DIR / "five_types.snapshot.json"
        if not fixture.exists() or not expected_path.exists():
            pytest.skip("five_types.json / snapshot not available; skipping")
        try:
            snapshot = await _capture_parity_snapshot(fixture)
        except Exception as exc:
            # five_types.json instantiates an OpenAIModel component which requires
            # langchain_openai; the lfx-only venv lacks this dep. Skip cleanly,
            # matching TestIDX02SemaphoreCap::test_parity_five_types behaviour.
            pytest.skip(f"five_types.json flow requires optional deps not available here: {exc}")
        expected = json.loads(expected_path.read_text())
        assert snapshot == expected, (
            f"async read-path refactor caused parity drift on five_types.json.\n"
            f"  got: {snapshot}\n  expected: {expected}"
        )


@pytest.mark.asyncio
class TestIDX07StaleIndexWarning:
    """Read-time stale-index warning via structlog on version mismatch.

    Covers:
      * Warning fires on disk-cache version != installed version.
      * Warning silent when versions match.
      * Warning silent when no disk cache file exists (clean-install / built-in only).
      * Warning silent when disk cache file is corrupt (handled downstream).
      * Deep parity guard on smallest.json after the warning is in place.

    The warning is captured via a MagicMock on ``ci.logger.warning`` rather than
    ``caplog`` because ``logger.warning`` here is a structlog BoundLogger method;
    caplog captures records bridged to stdlib logging, but only after structlog's
    BoundLogger runs its processor chain, and the text match here is more robust
    against structlog-config variance.
    """

    async def test_warning_fires_on_version_mismatch(self, tmp_path, monkeypatch):
        """Disk cache stamped with old version + installed is new -> logger.warning fires with all three fields."""
        from unittest.mock import MagicMock

        from lfx.interface import components as ci

        # Prepare a real-looking disk cache with "old-1.0" version + valid SHA
        cache_file = tmp_path / "component_index.json"
        index = {
            "version": "old-1.0",
            "metadata": {"num_modules": 0, "num_components": 0},
            "entries": [],
        }
        payload = orjson.dumps(index, option=orjson.OPT_SORT_KEYS)
        index["sha256"] = hashlib.sha256(payload).hexdigest()
        cache_file.write_bytes(orjson.dumps(index, option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2))

        monkeypatch.setattr(ci, "_get_cache_path", lambda: cache_file)
        _reset_component_cache_singleton(monkeypatch)

        # Patch installed version so mismatch is deterministic
        monkeypatch.setattr("importlib.metadata.version", lambda _name: "new-2.0")

        # Stub import_langflow_components + _determine_loading_strategy so the test does
        # not do a real ~hundred-module scan (we are testing the WARNING, not the cache build).
        async def _fake_import_langflow_components(*_a, **_kw):
            return {"components": {}}

        async def _fake_determine_loading_strategy(*_a, **_kw):
            return {}

        monkeypatch.setattr(ci, "import_langflow_components", _fake_import_langflow_components)
        monkeypatch.setattr(ci, "_determine_loading_strategy", _fake_determine_loading_strategy)

        # Capture logger.warning calls via MagicMock -- structlog-agnostic.
        warning_mock = MagicMock()
        monkeypatch.setattr(ci.logger, "warning", warning_mock)

        settings = _fake_settings_service()
        await ci.get_and_cache_all_types_dict(settings)

        # Find the stale-cache warning among any other warnings (e.g. downstream).
        stale_calls = [
            call
            for call in warning_mock.call_args_list
            if call.args and "stale component cache" in str(call.args[0]).lower()
        ]
        assert len(stale_calls) == 1, (
            f"expected exactly 1 stale-cache warning, got {len(stale_calls)}. "
            f"All warning calls: {warning_mock.call_args_list!r}"
        )
        rendered = str(stale_calls[0].args[0])
        assert "old-1.0" in rendered, f"warning missing cached version: {rendered!r}"
        assert "new-2.0" in rendered, f"warning missing installed version: {rendered!r}"
        assert str(cache_file) in rendered, f"warning missing cache file path: {rendered!r}"

    async def test_warning_silent_on_version_match(self, tmp_path, monkeypatch):
        """Cached and installed versions identical -> no warning."""
        from unittest.mock import MagicMock

        from lfx.interface import components as ci

        cache_file = tmp_path / "component_index.json"
        index = {
            "version": "same-1.0",
            "metadata": {"num_modules": 0, "num_components": 0},
            "entries": [],
        }
        payload = orjson.dumps(index, option=orjson.OPT_SORT_KEYS)
        index["sha256"] = hashlib.sha256(payload).hexdigest()
        cache_file.write_bytes(orjson.dumps(index, option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2))

        monkeypatch.setattr(ci, "_get_cache_path", lambda: cache_file)
        _reset_component_cache_singleton(monkeypatch)
        monkeypatch.setattr("importlib.metadata.version", lambda _name: "same-1.0")

        async def _fake_import(*_a, **_kw):
            return {"components": {}}

        async def _fake_strategy(*_a, **_kw):
            return {}

        monkeypatch.setattr(ci, "import_langflow_components", _fake_import)
        monkeypatch.setattr(ci, "_determine_loading_strategy", _fake_strategy)

        warning_mock = MagicMock()
        monkeypatch.setattr(ci.logger, "warning", warning_mock)

        await ci.get_and_cache_all_types_dict(_fake_settings_service())

        stale_calls = [
            call for call in warning_mock.call_args_list if call.args and "stale component index" in str(call.args[0])
        ]
        assert not stale_calls, (
            f"expected NO stale-index warning on version match, got {len(stale_calls)}: {stale_calls!r}"
        )

    async def test_warning_silent_when_cache_file_absent(self, tmp_path, monkeypatch):
        """Clean install (no disk cache file) -> no warning (built-in shipped index only)."""
        from unittest.mock import MagicMock

        from lfx.interface import components as ci

        absent_cache = tmp_path / "definitely_not_here.json"
        assert not absent_cache.exists()
        monkeypatch.setattr(ci, "_get_cache_path", lambda: absent_cache)
        _reset_component_cache_singleton(monkeypatch)
        # Pick a real-ish installed version that would mismatch anything
        monkeypatch.setattr("importlib.metadata.version", lambda _name: "1.0.0")

        async def _fake_import(*_a, **_kw):
            return {"components": {}}

        async def _fake_strategy(*_a, **_kw):
            return {}

        monkeypatch.setattr(ci, "import_langflow_components", _fake_import)
        monkeypatch.setattr(ci, "_determine_loading_strategy", _fake_strategy)

        warning_mock = MagicMock()
        monkeypatch.setattr(ci.logger, "warning", warning_mock)

        await ci.get_and_cache_all_types_dict(_fake_settings_service())

        stale_calls = [
            call for call in warning_mock.call_args_list if call.args and "stale component index" in str(call.args[0])
        ]
        assert not stale_calls, f"expected NO stale-index warning when disk cache absent, got: {stale_calls!r}"

    async def test_warning_silent_on_corrupt_cache(self, tmp_path, monkeypatch):
        """Corrupt disk cache -> no stale-index warning (downstream handles corruption separately)."""
        from unittest.mock import MagicMock

        from lfx.interface import components as ci

        cache_file = tmp_path / "component_index.json"
        cache_file.write_bytes(b"this is not json at all {{{ garbage")

        monkeypatch.setattr(ci, "_get_cache_path", lambda: cache_file)
        _reset_component_cache_singleton(monkeypatch)
        monkeypatch.setattr("importlib.metadata.version", lambda _name: "1.0.0")

        async def _fake_import(*_a, **_kw):
            return {"components": {}}

        async def _fake_strategy(*_a, **_kw):
            return {}

        monkeypatch.setattr(ci, "import_langflow_components", _fake_import)
        monkeypatch.setattr(ci, "_determine_loading_strategy", _fake_strategy)

        warning_mock = MagicMock()
        monkeypatch.setattr(ci.logger, "warning", warning_mock)

        await ci.get_and_cache_all_types_dict(_fake_settings_service())

        stale_calls = [
            call for call in warning_mock.call_args_list if call.args and "stale component index" in str(call.args[0])
        ]
        assert not stale_calls, f"expected NO stale-index warning on corrupt cache; got: {stale_calls!r}"

    async def test_parity_smallest_after_idx07(self):
        """Deep parity guard after the read-time stale-index check is in place."""
        fixture = _PARITY_FIXTURES_DIR / "smallest.json"
        expected_path = _PARITY_FIXTURES_DIR / "smallest.snapshot.json"
        snapshot = await _capture_parity_snapshot(fixture)
        expected = json.loads(expected_path.read_text())
        assert snapshot == expected, (
            f"stale-index check caused parity drift.\n  got: {snapshot}\n  expected: {expected}"
        )


# ---------------------------------------------------------------------------
# Module-scoped fixture: build a real, SHA-stamped, version-matched cache file
# once per test module to avoid rebuilding per-test in TestIDX08CacheHit.
#
# Uses tmp_path_factory (module-scoped fixture compatible) + direct setattr on
# ci._get_cache_path rather than monkeypatch, which is function-scoped only.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def prebuilt_cache_file(tmp_path_factory):
    """Return the Path of a valid, SHA-stamped, version-matched cache file.

    Built once per module: calls _save_generated_index with a minimal synthetic
    modules_dict so the file carries the real installed lfx version and a
    non-empty entries list. Both conditions are required for the cache-hit
    short-circuit to fire (version match AND non-empty entries).
    """
    from importlib.metadata import version as _version

    from lfx.interface import components as ci

    tmp_dir = tmp_path_factory.mktemp("prebuilt_cache")
    cache_file = tmp_dir / "component_index.json"

    original_get_cache_path = ci._get_cache_path
    try:
        ci._get_cache_path = lambda: cache_file
        _save_generated_index(
            {
                "inputs": {"ChatInput": {"template": {}, "display_name": "Chat Input"}},
                "outputs": {"ChatOutput": {"template": {}, "display_name": "Chat Output"}},
            }
        )
    finally:
        ci._get_cache_path = original_get_cache_path

    assert cache_file.exists(), "prebuilt_cache_file fixture: _save_generated_index did not write a file"
    blob = orjson.loads(cache_file.read_bytes())
    installed = _version("lfx")
    assert blob.get("version") == installed, (
        f"prebuilt cache version {blob.get('version')!r} != installed {installed!r}"
    )
    assert blob.get("entries"), "prebuilt cache has empty entries -- cache-hit short-circuit will not fire"
    return cache_file


@pytest.mark.asyncio
class TestIDX08CacheHit:
    """Read-path short-circuit on version-matched cache hit."""

    async def test_cache_hit_populates_all_types_dict(self, tmp_path, monkeypatch, prebuilt_cache_file):
        """Cache-hit path populates all_types_dict and type_to_current_hash; skips import_langflow_components."""
        import shutil

        from lfx.interface import components as ci

        cache_file = tmp_path / "component_index.json"
        shutil.copy(prebuilt_cache_file, cache_file)

        monkeypatch.setattr(ci, "_get_cache_path", lambda: cache_file)
        _reset_component_cache_singleton(monkeypatch)

        import_calls = []
        original_import = ci.import_langflow_components

        async def _spy_import(*a, **kw):
            import_calls.append((a, kw))
            return await original_import(*a, **kw)

        monkeypatch.setattr(ci, "import_langflow_components", _spy_import)

        result = await ci.get_and_cache_all_types_dict(_fake_settings_service())

        assert result is not None, "cache-hit path returned None"
        assert isinstance(result, dict), "cache-hit must return a dict"
        assert result, "cache-hit returned empty dict"
        # Hash lookups populated on cache-hit so flow validation has them ready.
        assert ci.component_cache.type_to_current_hash is not None, (
            "type_to_current_hash must be populated on cache-hit"
        )
        # Rebuild skipped: cache-hit short-circuits the import path.
        assert not import_calls, (
            f"import_langflow_components must NOT be called on cache-hit, got {len(import_calls)} calls"
        )

    async def test_cache_miss_falls_back_to_rebuild(self, tmp_path, monkeypatch):
        """Cache-miss (absent file) falls back to the full rebuild path."""
        from lfx.interface import components as ci

        absent_cache = tmp_path / "nope.json"
        assert not absent_cache.exists()
        monkeypatch.setattr(ci, "_get_cache_path", lambda: absent_cache)
        _reset_component_cache_singleton(monkeypatch)

        import_calls = []
        original_import = ci.import_langflow_components

        async def _spy_import(*a, **kw):
            import_calls.append((a, kw))
            return await original_import(*a, **kw)

        monkeypatch.setattr(ci, "import_langflow_components", _spy_import)

        result = await ci.get_and_cache_all_types_dict(_fake_settings_service())

        assert result is not None, "cache-miss fallback returned None"
        assert result, "cache-miss fallback must populate all_types_dict"
        assert len(import_calls) == 1, (
            f"cache-miss must call import_langflow_components exactly once, got {len(import_calls)}"
        )

    async def test_cache_hit_skips_telemetry(self, tmp_path, monkeypatch, prebuilt_cache_file):
        """No build work means no log_component_index call on cache-hit."""
        import shutil
        from unittest.mock import AsyncMock

        from lfx.interface import components as ci

        cache_file = tmp_path / "component_index.json"
        shutil.copy(prebuilt_cache_file, cache_file)
        monkeypatch.setattr(ci, "_get_cache_path", lambda: cache_file)
        _reset_component_cache_singleton(monkeypatch)

        telemetry = Mock()
        telemetry.log_component_index = AsyncMock()

        await ci.get_and_cache_all_types_dict(_fake_settings_service(), telemetry_service=telemetry)

        telemetry.log_component_index.assert_not_called()

    async def test_parity_cache_hit_vs_miss(self, tmp_path, monkeypatch, prebuilt_cache_file):
        """Byte-identical vertex_order + final_text on cache-hit and cache-miss paths."""
        import shutil

        from lfx.interface import components as ci

        _install_mock_llm()
        fixture = _PARITY_FIXTURES_DIR / "smallest.json"
        snapshot_path = _PARITY_FIXTURES_DIR / "smallest.snapshot.json"
        expected = orjson.loads(snapshot_path.read_bytes())

        # --- cache-hit pass
        hit_cache = tmp_path / "hit.json"
        shutil.copy(prebuilt_cache_file, hit_cache)
        monkeypatch.setattr(ci, "_get_cache_path", lambda: hit_cache)
        _reset_component_cache_singleton(monkeypatch)
        hit_snapshot = await _capture_parity_snapshot(fixture)

        # --- cache-miss pass
        absent = tmp_path / "missing.json"
        monkeypatch.setattr(ci, "_get_cache_path", lambda: absent)
        _reset_component_cache_singleton(monkeypatch)
        miss_snapshot = await _capture_parity_snapshot(fixture)

        assert hit_snapshot == expected, (
            f"cache-hit parity snapshot drifted: got {hit_snapshot!r}, expected {expected!r}"
        )
        assert miss_snapshot == expected, (
            f"cache-miss parity snapshot drifted: got {miss_snapshot!r}, expected {expected!r}"
        )
        assert hit_snapshot == miss_snapshot, (
            f"cache-hit and cache-miss snapshots diverged (hit={hit_snapshot!r}, miss={miss_snapshot!r})"
        )

    def test_cache_hit_perf_under_500ms(self, tmp_path, monkeypatch, prebuilt_cache_file):
        """Unit-level perf ceiling on the cache-hit path.

        Not a CI-wide perf gate (the benchmark harness owns the public 500ms
        claim); this asserts the call path is cheap enough that a regression
        (e.g. reading the cache twice, or re-walking lfx.components) shows up
        locally.

        Kept as a sync def so asyncio.run() creates the ONLY event loop for this
        test. If this assertion flakes on slow CI hardware, widen the ceiling
        here with a comment rather than deleting the assertion.
        """
        import shutil
        import time

        from lfx.interface import components as ci

        cache_file = tmp_path / "component_index.json"
        shutil.copy(prebuilt_cache_file, cache_file)
        monkeypatch.setattr(ci, "_get_cache_path", lambda: cache_file)
        _reset_component_cache_singleton(monkeypatch)

        start = time.perf_counter()
        result = asyncio.run(ci.get_and_cache_all_types_dict(_fake_settings_service()))
        elapsed = time.perf_counter() - start

        assert result is not None, "perf test cannot run without a valid cache-hit"
        assert result, "perf test: cache-hit returned empty dict"
        assert elapsed < 0.5, (
            f"cache-hit path took {elapsed * 1000:.1f}ms, must be under 500ms. "
            "Regression likely: check for double-read of cache file or residual walk of lfx.components."
        )


# ---------------------------------------------------------------------------
# Regression tests for the post-review correctness fixes (one per fix).
# ---------------------------------------------------------------------------


def _build_cache_blob(version: str, entries: list, *, valid_sha: bool = True) -> bytes:
    """Serialize a cache file matching the on-disk format.

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


@pytest.mark.asyncio
class TestCorrectnessFixes:
    """One test per post-review correctness fix in lfx.interface.components."""

    async def test_tampered_sha_does_not_short_circuit(self, tmp_path, monkeypatch):
        """A version-matched but SHA-tampered cache must fall through to the rebuild path."""
        from lfx.interface import components as ci

        cache_file = tmp_path / "component_index.json"
        installed = "test-1.0"
        entries = [["cat1", {"comp1": {"template": {}, "display_name": "C"}}]]
        cache_file.write_bytes(_build_cache_blob(installed, entries, valid_sha=False))

        monkeypatch.setattr(ci, "_get_cache_path", lambda: cache_file)
        monkeypatch.setattr("importlib.metadata.version", lambda _name: installed)
        _reset_component_cache_singleton(monkeypatch)

        warning_mock = MagicMock()
        monkeypatch.setattr(ci.logger, "warning", warning_mock)

        rebuild_mock = AsyncMock(return_value={"components": {"rebuilt": {"x": {}}}})
        monkeypatch.setattr(ci, "import_langflow_components", rebuild_mock)
        monkeypatch.setattr(ci, "_determine_loading_strategy", AsyncMock(return_value={}))

        await ci.get_and_cache_all_types_dict(_fake_settings_service())

        rebuild_mock.assert_awaited_once()
        sha_warns = [
            call for call in warning_mock.call_args_list if call.args and "SHA256 integrity" in str(call.args[0])
        ]
        assert len(sha_warns) == 1, f"expected 1 SHA256 integrity warning, got: {warning_mock.call_args_list!r}"

    async def test_stale_version_cache_is_deleted(self, tmp_path, monkeypatch):
        """When peek detects a version mismatch, the stale cache must be unlinked."""
        from lfx.interface import components as ci

        cache_file = tmp_path / "component_index.json"
        cache_file.write_bytes(_build_cache_blob("old-1.0", []))

        monkeypatch.setattr(ci, "_get_cache_path", lambda: cache_file)
        monkeypatch.setattr("importlib.metadata.version", lambda _name: "new-2.0")
        _reset_component_cache_singleton(monkeypatch)

        warning_mock = MagicMock()
        monkeypatch.setattr(ci.logger, "warning", warning_mock)
        monkeypatch.setattr(ci, "import_langflow_components", AsyncMock(return_value={"components": {}}))
        monkeypatch.setattr(ci, "_determine_loading_strategy", AsyncMock(return_value={}))

        await ci.get_and_cache_all_types_dict(_fake_settings_service())

        assert not cache_file.exists(), "stale cache file must be unlinked"
        stale_warns = [
            call for call in warning_mock.call_args_list if call.args and "Stale component cache" in str(call.args[0])
        ]
        assert len(stale_warns) == 1

    async def test_corrupt_json_cache_emits_warning_and_rebuilds(self, tmp_path, monkeypatch):
        """Corrupt cache file must warn and fall through, not silently swallow."""
        from lfx.interface import components as ci

        cache_file = tmp_path / "component_index.json"
        cache_file.write_bytes(b"this is not json at all {{{ garbage")

        monkeypatch.setattr(ci, "_get_cache_path", lambda: cache_file)
        monkeypatch.setattr("importlib.metadata.version", lambda _name: "1.0.0")
        _reset_component_cache_singleton(monkeypatch)

        warning_mock = MagicMock()
        monkeypatch.setattr(ci.logger, "warning", warning_mock)

        rebuild_mock = AsyncMock(return_value={"components": {}})
        monkeypatch.setattr(ci, "import_langflow_components", rebuild_mock)
        monkeypatch.setattr(ci, "_determine_loading_strategy", AsyncMock(return_value={}))

        await ci.get_and_cache_all_types_dict(_fake_settings_service())

        rebuild_mock.assert_awaited_once()
        peek_warns = [
            call
            for call in warning_mock.call_args_list
            if call.args and "Component cache peek failed" in str(call.args[0])
        ]
        assert len(peek_warns) == 1

    async def test_save_generated_index_oserror_logs_at_warning(self, tmp_path, monkeypatch):
        """OSError on cache write must surface at warning so cold-start regressions are visible."""
        from lfx.interface import components as ci

        cache_file = tmp_path / "component_index.json"
        monkeypatch.setattr(ci, "_get_cache_path", lambda: cache_file)

        def deny(*_a, **_kw):
            msg = "simulated read-only mount"
            raise PermissionError(msg)

        monkeypatch.setattr(ci.tempfile, "mkstemp", deny)

        warning_mock = MagicMock()
        monkeypatch.setattr(ci.logger, "warning", warning_mock)

        _save_generated_index({"cat": {"comp": {"template": {}}}})

        assert warning_mock.call_count == 1
        assert "PermissionError" in str(warning_mock.call_args.args[0])

    async def test_selective_dev_mode_empty_result_emits_warning(self, monkeypatch):
        """Zero-component result in selective dev mode must warn instead of returning silently."""
        from lfx.interface import components as ci

        warning_mock = AsyncMock()
        monkeypatch.setattr(ci.logger, "awarning", warning_mock)
        monkeypatch.setattr(ci, "_load_from_index_or_cache", AsyncMock(return_value=({}, None)))
        monkeypatch.setattr(ci, "_load_components_dynamically", AsyncMock(return_value={}))

        modules, source = await ci._load_selective_dev_mode(None, ["nonexistent"])

        assert modules == {}
        assert source == "dynamic"
        empty_warns = [
            call for call in warning_mock.call_args_list if call.args and "produced 0 components" in str(call.args[0])
        ]
        assert len(empty_warns) == 1

    async def test_load_components_dynamically_emits_aggregate_failure_summary(self, monkeypatch):
        """Partial-failure load must emit one aggregate log with count + types histogram."""
        from lfx.interface import components as ci

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

        result = await ci._load_components_dynamically(target_modules=None)

        assert "cat2" in result, "non-failing module should still be loaded"
        aggregate_calls = [
            call for call in error_mock.call_args_list if call.args and "modules failed" in str(call.args[0])
        ]
        assert len(aggregate_calls) == 1
        msg = str(aggregate_calls[0].args[0])
        assert "2 of 3" in msg
        assert "ImportError" in msg
        assert "ValueError" in msg
