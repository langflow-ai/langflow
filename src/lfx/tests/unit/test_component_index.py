"""Unit tests for component index system."""

import asyncio
import hashlib
import json
import threading
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

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

    def test_read_index_file_not_found(self):
        """Test reading index when file doesn't exist."""
        mock_path = Mock()
        mock_path.exists.return_value = False

        with patch("lfx.interface.components.Path") as mock_path_class:
            mock_path_class.return_value = mock_path
            result = _read_component_index()

        assert result is None

    def test_read_index_valid(self, tmp_path):
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

            result = _read_component_index()

        assert result is not None
        assert result["version"] == "0.1.12"
        assert "entries" in result
        assert result["sha256"] == index["sha256"]

    def test_read_index_invalid_sha256(self, tmp_path):
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

            result = _read_component_index()

        assert result is None

    def test_read_index_version_mismatch(self, tmp_path):
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

            result = _read_component_index()

        assert result is None

    def test_read_index_package_not_found(self, tmp_path):
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

            result = _read_component_index()

        # Should succeed - version check skipped when metadata unavailable
        assert result is not None
        assert result["version"] == "0.4.0"
        assert "entries" in result

    def test_read_index_custom_path_file(self, tmp_path):
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
            result = _read_component_index(str(custom_file))

        assert result is not None
        assert result["version"] == "0.1.12"

    def test_read_index_custom_path_url(self):
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
            result = _read_component_index("https://example.com/index.json")

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

        with (
            patch("lfx.interface.components._read_component_index") as mock_read,
            patch("importlib.metadata.version", return_value="0.1.12"),
        ):
            mock_read.return_value = index

            result = await import_langflow_components()

        assert "components" in result
        assert "category1" in result["components"]
        assert "comp1" in result["components"]["category1"]

    async def test_import_with_missing_index_creates_cache(self, tmp_path, monkeypatch):
        """Test import with missing index falls back to dynamic and caches."""
        monkeypatch.delenv("LFX_DEV", raising=False)
        cache_file = tmp_path / "component_index.json"
        monkeypatch.setattr("lfx.interface.components._get_cache_path", lambda: cache_file)

        with (
            patch("lfx.interface.components._read_component_index") as mock_read,
            patch("lfx.interface.components._process_single_module") as mock_process,
            patch("lfx.interface.components.pkgutil.walk_packages") as mock_walk,
            patch("importlib.metadata.version", return_value="0.1.12"),
        ):
            # Simulate missing built-in index and cache
            mock_read.return_value = None
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

        with (
            patch("lfx.interface.components._read_component_index") as mock_read,
            patch("importlib.metadata.version", return_value="0.1.12"),
        ):
            mock_read.return_value = index

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
# Phase 2 parity test scaffolding (IDX-01 plan lands this; later plans reuse)
# =====================================================================


@pytest.fixture(autouse=True, scope="module")
def _install_mock_llm_for_parity_tests():
    """Install the Phase 1 BaseChatOpenAI mock once per test module. Idempotent.

    Returns False on lfx-only test envs that lack langchain_openai (e.g. the
    monorepo lfx-only venv this test module runs in). The smallest.json parity
    fixture does not invoke an LLM, so the False return is benign here; later
    plans that add LLM-bearing parity fixtures rely on this hook when run in
    environments where langchain_openai IS installed.
    """
    _install_mock_llm()


@pytest.mark.asyncio
class TestIDX01LazyLock:
    """Phase 2 / IDX-01: lazy asyncio.Lock property on ComponentCache.

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

        ``_load_components_dynamically`` itself is replaced by a counting stub (no call
        to the real loader) because the real loader walks every installed lfx component
        package, which in this repo pulls in optional integrations (toolguard) that are
        not installed in the lfx-only test venv. D-08 permits monkey-patching the loader
        with a counter; it does not require the real loader to execute.
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

    def test_cache_built_once_threading(self, monkeypatch):
        """Ten threads, each with its OWN event loop via asyncio.run.

        Purpose per research Code Examples section IDX-01: each thread's event loop
        creates its own asyncio.Lock, so the per-thread counter would be 1 but the
        cross-thread aggregate would be 10. This test asserts "no crashes / no
        deadlocks" under multi-loop conditions, NOT an exact call_count. Guards
        future gunicorn / uvicorn thread-worker configurations.

        Each thread resets the singleton's ``_lock`` and ``all_types_dict`` to None
        inside its own worker, immediately before invoking ``asyncio.run``. This
        matches the research doc's "each thread creates its own Lock via lazy-property
        on first access in that thread's loop" contract. In production today, the
        singleton lives inside a single event loop, so the cross-loop reuse scenario
        is purely a test-time concern guarded by this per-thread reset.

        Also forces the dynamic-load fallback the same way as the async test so the
        fallback path is actually entered; without that, each thread's load short-
        circuits on the shipped built-in index and the test becomes trivial. The
        loader is stubbed (not wrapped around the real loader) for the same reason
        as the async test: real component enumeration brings in optional integrations
        that are not installed in the lfx-only test venv.
        """
        from lfx.interface import components as ci

        _reset_component_cache_singleton(monkeypatch)

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
                # the threading test is asserting on -- see 02-RESEARCH.md T-02-01-03.
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
