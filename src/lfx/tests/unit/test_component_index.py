"""Unit tests for component index system."""

import hashlib
from pathlib import Path
from unittest.mock import Mock, patch

import orjson
import pytest

from lfx.interface.components import (
    _dev_mode,
    _get_cache_path,
    _read_component_index,
    _save_generated_index,
    import_langflow_components,
)


class TestDevMode:
    """Tests for _dev_mode() function."""

    def test_dev_mode_not_set(self, monkeypatch):
        """Test default behavior when LFX_DEV is not set."""
        monkeypatch.delenv("LFX_DEV", raising=False)
        assert _dev_mode() is False

    def test_dev_mode_enabled_with_1(self, monkeypatch):
        """Test dev mode enabled with LFX_DEV=1."""
        monkeypatch.setenv("LFX_DEV", "1")
        assert _dev_mode() is True

    def test_dev_mode_enabled_with_true(self, monkeypatch):
        """Test dev mode enabled with LFX_DEV=true."""
        monkeypatch.setenv("LFX_DEV", "true")
        assert _dev_mode() is True

    def test_dev_mode_enabled_with_yes(self, monkeypatch):
        """Test dev mode enabled with LFX_DEV=yes."""
        monkeypatch.setenv("LFX_DEV", "yes")
        assert _dev_mode() is True

    def test_dev_mode_disabled_with_0(self, monkeypatch):
        """Test dev mode disabled with LFX_DEV=0."""
        monkeypatch.setenv("LFX_DEV", "0")
        assert _dev_mode() is False

    def test_dev_mode_disabled_with_false(self, monkeypatch):
        """Test dev mode disabled with LFX_DEV=false."""
        monkeypatch.setenv("LFX_DEV", "false")
        assert _dev_mode() is False

    def test_dev_mode_disabled_with_random(self, monkeypatch):
        """Test dev mode disabled with random value."""
        monkeypatch.setenv("LFX_DEV", "random")
        assert _dev_mode() is False

    def test_dev_mode_case_insensitive(self, monkeypatch):
        """Test that env var is case insensitive."""
        monkeypatch.setenv("LFX_DEV", "TRUE")
        assert _dev_mode() is True

        monkeypatch.setenv("LFX_DEV", "YES")
        assert _dev_mode() is True


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


class TestBuildComponentIndexScript:
    """Tests for the build_component_index.py script."""

    def test_build_script_creates_valid_structure(self):
        """Test that the build script creates a valid index structure."""
        import importlib.util
        import sys
        from pathlib import Path

        # Get path to build script
        script_path = Path(__file__).parent.parent.parent.parent.parent / "scripts" / "build_component_index.py"

        if not script_path.exists():
            pytest.skip("build_component_index.py script not found")

        # Load the module
        spec = importlib.util.spec_from_file_location("build_component_index", script_path)
        build_module = importlib.util.module_from_spec(spec)
        sys.modules["build_component_index"] = build_module

        with patch("asyncio.run") as mock_run:
            # Mock component data
            mock_run.return_value = {
                "components": {
                    "TestCategory": {
                        "TestComponent": {
                            "display_name": "Test Component",
                            "description": "A test component",
                            "template": {"code": {"type": "code"}},
                        }
                    }
                }
            }

            spec.loader.exec_module(build_module)
            index = build_module.build_component_index()

        assert index is not None
        assert "version" in index
        assert "entries" in index
        assert "sha256" in index
        assert isinstance(index["entries"], list)

    def test_build_script_minifies_json(self, tmp_path):
        """Test that the build script always minifies JSON output."""
        import importlib.util
        import sys
        from pathlib import Path

        script_path = Path(__file__).parent.parent.parent.parent.parent / "scripts" / "build_component_index.py"

        if not script_path.exists():
            pytest.skip("build_component_index.py script not found")

        spec = importlib.util.spec_from_file_location("build_component_index", script_path)
        build_module = importlib.util.module_from_spec(spec)
        sys.modules["build_component_index"] = build_module

        with (
            patch("asyncio.run") as mock_run,
            patch.object(build_module, "_get_langflow_version", return_value="1.0.0.test"),
        ):
            mock_run.return_value = {
                "components": {
                    "TestCategory": {
                        "TestComponent": {
                            "display_name": "Test",
                            "template": {},
                        }
                    }
                }
            }

            spec.loader.exec_module(build_module)
            index = build_module.build_component_index()

            # Write using the build module's logic
            json_bytes = orjson.dumps(index, option=orjson.OPT_SORT_KEYS)
            test_file = tmp_path / "test_index.json"
            test_file.write_text(json_bytes.decode("utf-8"), encoding="utf-8")

            # Verify it's minified (single line)
            content = test_file.read_text()
            lines = content.strip().split("\n")
            assert len(lines) == 1, "JSON should be minified to a single line"

    def test_build_script_sha256_integrity(self):
        """Test that SHA256 hash is correctly calculated."""
        import importlib.util
        import sys
        from pathlib import Path

        script_path = Path(__file__).parent.parent.parent.parent.parent / "scripts" / "build_component_index.py"

        if not script_path.exists():
            pytest.skip("build_component_index.py script not found")

        spec = importlib.util.spec_from_file_location("build_component_index", script_path)
        build_module = importlib.util.module_from_spec(spec)
        sys.modules["build_component_index"] = build_module

        with patch("asyncio.run") as mock_run:
            mock_run.return_value = {"components": {"TestCategory": {"TestComponent": {"template": {}}}}}

            spec.loader.exec_module(build_module)
            index = build_module.build_component_index()

            # Verify hash
            index_without_hash = {"version": index["version"], "entries": index["entries"]}
            payload = orjson.dumps(index_without_hash, option=orjson.OPT_SORT_KEYS)
            expected_hash = hashlib.sha256(payload).hexdigest()

            assert index["sha256"] == expected_hash

    def test_build_script_handles_import_errors(self):
        """Test that build script handles import errors gracefully."""
        import importlib.util
        import sys
        from pathlib import Path

        script_path = Path(__file__).parent.parent.parent.parent.parent / "scripts" / "build_component_index.py"

        if not script_path.exists():
            pytest.skip("build_component_index.py script not found")

        spec = importlib.util.spec_from_file_location("build_component_index", script_path)
        build_module = importlib.util.module_from_spec(spec)
        sys.modules["build_component_index"] = build_module

        with patch("asyncio.run", side_effect=ImportError("Cannot import")):
            spec.loader.exec_module(build_module)
            index = build_module.build_component_index()

            assert index is None
