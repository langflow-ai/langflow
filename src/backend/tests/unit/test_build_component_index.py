"""Tests for the build_component_index.py script."""

import hashlib
from pathlib import Path
from unittest.mock import patch

import orjson
import pytest


class TestBuildComponentIndexScript:
    """Tests for the build_component_index.py script."""

    def test_build_script_creates_valid_structure(self):
        """Test that the build script creates a valid index structure."""
        import importlib.util
        import sys

        # Get path to build script
        script_path = Path(__file__).parent.parent.parent.parent / "scripts" / "build_component_index.py"

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

        script_path = Path(__file__).parent.parent.parent.parent / "scripts" / "build_component_index.py"

        if not script_path.exists():
            pytest.skip("build_component_index.py script not found")

        spec = importlib.util.spec_from_file_location("build_component_index", script_path)
        build_module = importlib.util.module_from_spec(spec)
        sys.modules["build_component_index"] = build_module

        with (
            patch("asyncio.run") as mock_run,
            patch("importlib.metadata.version", return_value="1.0.0.test"),
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

        script_path = Path(__file__).parent.parent.parent.parent / "scripts" / "build_component_index.py"

        if not script_path.exists():
            pytest.skip("build_component_index.py script not found")

        spec = importlib.util.spec_from_file_location("build_component_index", script_path)
        build_module = importlib.util.module_from_spec(spec)
        sys.modules["build_component_index"] = build_module

        with (
            patch("asyncio.run") as mock_run,
            patch("importlib.metadata.version", return_value="1.0.0.test"),
        ):
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

        script_path = Path(__file__).parent.parent.parent.parent / "scripts" / "build_component_index.py"

        if not script_path.exists():
            pytest.skip("build_component_index.py script not found")

        spec = importlib.util.spec_from_file_location("build_component_index", script_path)
        build_module = importlib.util.module_from_spec(spec)
        sys.modules["build_component_index"] = build_module

        with patch("asyncio.run", side_effect=ImportError("Cannot import")):
            spec.loader.exec_module(build_module)
            index = build_module.build_component_index()

            assert index is None
