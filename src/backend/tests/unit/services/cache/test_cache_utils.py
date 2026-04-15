"""Tests for cache utility functions."""

import base64

import pytest
from langflow.services.cache.service import ThreadingInMemoryCache
from langflow.services.cache.utils import (
    CACHE_DIR,
    PREFIX,
    filter_json,
    save_binary_file,
    update_build_status,
)


class TestFilterJson:
    """Tests for filter_json function."""

    def test_removes_viewport(self):
        data = {"viewport": {"x": 0, "y": 0, "zoom": 1}, "nodes": []}
        result = filter_json(data)
        assert "viewport" not in result
        assert "nodes" in result

    def test_removes_chat_history(self):
        data = {"chatHistory": [{"msg": "hello"}], "edges": []}
        result = filter_json(data)
        assert "chatHistory" not in result
        assert "edges" in result

    def test_removes_node_position_fields(self):
        data = {
            "nodes": [
                {
                    "id": "node1",
                    "position": {"x": 100, "y": 200},
                    "positionAbsolute": {"x": 100, "y": 200},
                    "selected": True,
                    "dragging": False,
                    "data": {"type": "test"},
                }
            ]
        }
        result = filter_json(data)
        node = result["nodes"][0]
        assert "position" not in node
        assert "positionAbsolute" not in node
        assert "selected" not in node
        assert "dragging" not in node
        assert node["id"] == "node1"
        assert node["data"] == {"type": "test"}

    def test_preserves_other_fields(self):
        data = {"nodes": [], "edges": [], "custom_field": "value"}
        result = filter_json(data)
        assert result["custom_field"] == "value"

    def test_does_not_modify_original(self):
        data = {"viewport": {"x": 0}, "nodes": []}
        result = filter_json(data)
        assert "viewport" in data  # Original unchanged
        assert "viewport" not in result

    def test_empty_data(self):
        data = {}
        result = filter_json(data)
        assert result == {}

    def test_no_nodes(self):
        data = {"viewport": {"x": 0}}
        result = filter_json(data)
        assert "viewport" not in result


class TestSaveBinaryFile:
    """Tests for save_binary_file function."""

    def test_rejects_invalid_file_type(self):
        content = f"data:application/octet-stream;base64,{base64.b64encode(b'test').decode()}"
        with pytest.raises(ValueError, match="is not accepted"):
            save_binary_file(content, "test.exe", [".txt", ".json"])

    def test_rejects_empty_content(self):
        with pytest.raises(ValueError, match="reload the file"):
            save_binary_file("", "test.txt", [".txt"])

    def test_saves_valid_file(self, tmp_path):
        """Test saving a valid binary file using tmp_path directly."""
        import langflow.services.cache.utils as cache_utils_module

        encoded = base64.b64encode(b"hello world").decode()
        content = f"data:text/plain;base64,{encoded}"

        # Temporarily swap the CACHE_DIR constant on the module
        original_cache_dir = cache_utils_module.CACHE_DIR
        try:
            cache_utils_module.CACHE_DIR = str(tmp_path)
            result = save_binary_file(content, "test.txt", [".txt"])
            assert result.endswith("test.txt")
            # Verify file was actually written
            from pathlib import Path

            saved = Path(result)
            assert saved.exists()
            assert saved.read_bytes() == b"hello world"
        finally:
            cache_utils_module.CACHE_DIR = original_cache_dir


class TestUpdateBuildStatus:
    """Tests for update_build_status function."""

    def test_updates_status(self):
        cache = ThreadingInMemoryCache()
        cache["flow1"] = {"status": "building"}

        update_build_status(cache, "flow1", "completed")

        result = cache["flow1"]
        assert result["status"] == "completed"

    def test_raises_when_flow_not_found(self):
        # update_build_status checks `if cached_flow is None`, so use a plain dict
        # which returns None for missing keys via .get() but raises KeyError for [].
        # A dict subclass that returns None for missing keys matches the expected behavior.
        class NoneDefaultDict(dict):
            def __getitem__(self, key):
                return self.get(key, None)

        cache = NoneDefaultDict()

        with pytest.raises(ValueError, match="not found in cache"):
            update_build_status(cache, "flow1", "completed")


class TestConstants:
    """Test cache constants."""

    def test_cache_dir_is_string(self):
        assert isinstance(CACHE_DIR, str)

    def test_prefix(self):
        assert PREFIX == "langflow_cache"
